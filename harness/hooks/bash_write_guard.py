#!/usr/bin/env python3
"""bash_write_guard.py — PostToolUse:Bash advisory (telemetry-class, fail-open).

write_guard (PreToolUse:Write|Edit|MultiEdit) blocks the agent's FILE tools from
editing gate config, but it is structurally blind to a write spelled through the
shell: a redirect (`> file`, `>> file`), `tee`, `sed -i`, or a `python -c
"open(path,'w')"`. This hook closes the visibility gap, not the write: it runs
PostToolUse — AFTER the command already ran — so it CANNOT block. It does the one
honest thing left: detect that a guarded path was written through Bash, record it
to the telemetry ledger, and nudge. The edited file is tracked, so the change
also surfaces as a git diff. Defense-in-depth surfacing (tamper-EVIDENT), exactly
the floor write_guard documents — never an airtight gate.

Deliberately NOT flagged: `cp`/`mv` into a guarded path. That is the SANCTIONED
workaround for editing a guarded file (write to /tmp, then cp/mv into place); it
is explicit and visible, so nagging on it would punish the blessed path. Reading
a guarded file and redirecting ELSEWHERE (`cat guarded > /tmp/x`) is not a write
to it and stays silent — only the WRITE TARGET is matched, never a source arg.

Posture: telemetry-class (default ON, fail-open, always continues). The detection
is a heuristic over the command string, in lockstep with write_guard's GUARD_LIST
and root resolution (one guarded set, two observers).
"""

import os
import re
import sys
from pathlib import Path

# Diagnostic text may carry non-ASCII; guard stderr encoding so a non-UTF-8
# locale degrades to replacement chars instead of raising mid-write (fail-open).
try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")
except Exception:  # noqa: BLE001 — older streams / already detached; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import hook_runtime  # noqa: E402
import write_guard  # noqa: E402 — reuse GUARD_LIST + root + path resolution (DRY)

HOOK_CLASS = "telemetry"
_NAME = Path(__file__).stem

# HIGH priority (H2-resolved, INV-3 F-2): a write_guard bypass through the shell is
# security-relevant and must reach the human, not just stderr-on-exit-0 (spec-invisible).
# core() routes it through the shared systemMessage queue (emit_nudge); main() drains
# that into the hook's ONE terminal JSON blob, so the dispatcher can call core() in
# process without a double write.

# A command line splits into list/pipeline segments on these connectors, so a
# write target in one segment is never paired with a verb in another. Shared
# shape with bash_safety_guard, kept local to avoid a hook→hook import.
_CONNECTOR_RE = re.compile(r"[;&|\n]+")
_COMMENT_RE = re.compile(r"(?:^|\s)#[^\n]*")
# A leading `cd <dir>` in a segment sets the cwd for relative writes in later
# segments (`cd plans/p/artifacts && echo > x.json` lands in that dir). Track it
# so a relative target is resolved against it, closing the cd-relative blind spot.
# Capture the cd target as a quoted span (keeping spaces) or an unquoted token,
# so `cd "some dir"` resolves the full name instead of truncating at the space.
_CD_RE = re.compile(r"""^\s*cd\s+(?:-[\w-]+\s+)*(?:"([^"]+)"|'([^']+)'|([^'"\s|;&]+))""")

# Redirect target: an optional fd digit, `>`/`>>`, an optional clobber-force
# `|`, then the path. `>&2` / `2>&1` carry a `&` right after the operator → the
# negative class rejects them, so an fd-dup is never mistaken for a file write.
_REDIR_RE = re.compile(r"\d*>>?\|?\s*([^\s|;&<>()]+)")
# dd if=… of=PATH — a block-copy write to a file path (raw-device targets are
# bash_safety_guard's job; here we only care about a guarded config path).
_DD_RE = re.compile(r"\bdd\b[^|;&\n]*\bof=([^\s|;&<>()]+)")
# truncate [-s N] FILE — empties/sizes a file (its last bare arg is the target)
_TRUNCATE_RE = re.compile(r"\btruncate\b(?:\s+-\S+|\s+\d+)*\s+([^\s|;&<>()]+)")
# Quoted spans: masked to same-length underscores BEFORE redirect/tee/sed
# matching so a `>` living inside a quoted literal is never read as a real
# operator (the underscores carry no `>` and cannot fnmatch a guarded path).
_QUOTED_RE = re.compile(r"'[^']*'|\"[^\"]*\"")
# tee [opts] FILE...  — group(1) eats option flags, group(2) the file args.
_TEE_RE = re.compile(r"\btee\b((?:\s+-\S+)*)((?:\s+[^\s|;&<>()]+)*)")
# sed in-place: -i / -i.bak / --in-place. Presence flips the whole segment into
# "scan every token" mode (the edited files are bare args; fnmatch filters out
# the script + flags, only a real guarded path can survive).
_SED_INPLACE_RE = re.compile(r"\bsed\b[^|;&\n]*?(?:\s-\w*i\w*\b|\s--in-place\b)")
# python -c "... open('FILE', 'w'|'a'|'x' ...) ..." — write-mode open only.
_PY_C_RE = re.compile(r"\bpython3?\b[^|;&\n]*?\s-c\b")
_PY_OPEN_RE = re.compile(
    r"open\s*\(\s*['\"]([^'\"]+)['\"]\s*,\s*[^)]*['\"][^'\"]*[wax]")
# pathlib: Path('PATH').write_text(...) / .write_bytes(...) — a literal-path write
_PY_WRITE_RE = re.compile(
    r"\(\s*['\"]([^'\"]+)['\"]\s*\)\s*\.\s*write_(?:text|bytes)")
# A redirect/dd target may be QUOTED; the mask underscored it, so recover from raw.
_QUOTED_TARGET_RE = re.compile(r"(['\"])([^'\"]*)\1")
_BARE_TARGET_RE = re.compile(r"[^\s|;&<>()]+")


def _redir_target_raw(raw, start):
    """Redirect target from the RAW segment at `start`. Masking is equal-length so
    positions align; a quoted target (`> 'plans/p/artifacts/x.json'`) was masked to
    underscores and would otherwise be a forgery-gate blind spot — read it back."""
    s = raw[start:]
    mq = _QUOTED_TARGET_RE.match(s)
    if mq:
        return mq.group(2)
    mb = _BARE_TARGET_RE.match(s)
    return mb.group(0) if mb else ""


def _root() -> Path:
    return write_guard._root()


def _guard_patterns() -> tuple:
    """GUARD_LIST plus any write-guard.yaml extra_guarded — the SAME set
    write_guard enforces, so the two observers never drift apart."""
    try:
        return write_guard.GUARD_LIST + write_guard._extra_guarded(
            write_guard._switch_config())
    except Exception:  # noqa: BLE001 — fall back to the constant; never crash
        return write_guard.GUARD_LIST


def _unquote(s: str) -> str:
    """Drop quote chars, keeping content — recovers a quoted target for the
    branches that scan whitespace tokens (sed -i, cp/mv dest)."""
    return s.replace("'", "").replace('"', "")


def _mask(cmd: str) -> str:
    """Mask quoted spans to equal-length underscores FIRST, then blank a
    trailing `# comment` — in that order, so a `#` living inside a quoted
    string (`echo 'a #b' > f`) is already underscored and cannot be misread
    as a comment start eating the rest of the line. Both substitutions are
    length-preserving (spaces/underscores match the consumed span exactly),
    so offsets taken on the result still align with the RAW command. A `>`
    inside a quoted string is then NOT seen as a redirect operator (kills
    false positives like `echo "a > path"`), while an unquoted redirect to a
    quoted target is rare and acceptably missed for an advisory."""
    no_quotes = _QUOTED_RE.sub(lambda m: "_" * len(m.group(0)), cmd)
    return _COMMENT_RE.sub(lambda m: " " * len(m.group(0)), no_quotes)


def _candidate_targets(seg_masked: str, seg_raw: str) -> list:
    """WRITE targets in one segment — the paths a write verb lands ON, never a
    source/arg path. Redirect/tee/dd give precise targets; sed -i scans all
    tokens (its targets are bare args); python open() yields its literal path
    arg (read from the RAW segment, which still carries the quotes)."""
    targets = []
    for m in _REDIR_RE.finditer(seg_masked):
        targets.append(_redir_target_raw(seg_raw, m.start(1)))
    for m in _DD_RE.finditer(seg_masked):
        targets.append(m.group(1))
    for m in _TRUNCATE_RE.finditer(seg_masked):
        targets.append(m.group(1))
    tee = _TEE_RE.search(seg_masked)
    if tee:
        targets.extend(t for t in tee.group(2).split() if not t.startswith("-"))
    seg_unq = _unquote(seg_raw)
    if _SED_INPLACE_RE.search(seg_unq):
        targets.extend(seg_unq.split())
    if _PY_C_RE.search(seg_raw):
        targets.extend(m.group(1) for m in _PY_OPEN_RE.finditer(seg_raw))
        targets.extend(m.group(1) for m in _PY_WRITE_RE.finditer(seg_raw))
    return targets


# cp/mv/install DEST — the LAST non-option token (SRC args are reads). Kept
# behind the include_copy_move flag: the config observer EXCLUDES it (cp/mv into
# a guarded config is the blessed write-to-/tmp-then-move workaround), the
# artifact gate INCLUDES it (an artifact has no sanctioned shell path).
_CP_MV_RE = re.compile(r"\b(?:cp|mv|install|ln)\b((?:\s+-\S+)*)\s+(\S.*)$")


def _copy_move_targets(seg_masked: str) -> list:
    m = _CP_MV_RE.search(seg_masked.strip())
    if not m:
        return []
    args = [t for t in m.group(2).split() if not t.startswith("-")]
    return args[-1:] if len(args) >= 2 else []  # need >=1 src + a dest


def shell_write_targets(command, include_copy_move: bool = False) -> list:
    """Every filesystem WRITE target named in a Bash command, as root-relative
    POSIX paths (deduped, in order). The shared parser behind two observers:
    bash_write_guard (config — copy/move EXCLUDED) and artifact_guard (plan
    artifacts — copy/move INCLUDED). Pure + fail-open: junk input → []."""
    if not isinstance(command, str) or not command.strip():
        return []
    root = _root()
    out, seen = [], set()
    # Clobber-force `>|` is semantically `>`; rewrite to `> ` BEFORE the connector
    # split so its `|` is not mistaken for a pipe (which would sever the target).
    command = command.replace(">|", "> ")
    # Split on connectors found in the MASKED command, so a separator inside quotes
    # (a `;` in a `python -c` payload) does not sever a quoted write. Mask is
    # equal-length, so the RAW command slices at the same offsets.
    masked_full = _mask(command)
    raw_segs, pos = [], 0
    for m in _CONNECTOR_RE.finditer(masked_full):
        raw_segs.append(command[pos:m.start()])
        pos = m.end()
    raw_segs.append(command[pos:])
    cwd = ""
    for seg_raw in raw_segs:
        cdm = _CD_RE.match(seg_raw)
        if cdm:
            d = (cdm.group(1) or cdm.group(2) or cdm.group(3) or "").strip()
            if d and not d.startswith("-"):
                cwd = d if d.startswith("/") else (cwd.rstrip("/") + "/" + d if cwd else d)
            continue
        seg_masked = _mask(seg_raw)
        toks = _candidate_targets(seg_masked, seg_raw)
        if include_copy_move:
            toks = toks + _copy_move_targets(_unquote(seg_raw))
        for tok in toks:
            full = (cwd.rstrip("/") + "/" + tok
                    if cwd and tok and not tok.startswith("/") else tok)
            try:
                rel = write_guard._rel_target(full, root)
            except Exception:  # noqa: BLE001 — a bad token never breaks detection
                rel = None
            if rel and rel not in seen:
                seen.add(rel)
                out.append(rel)
    return out


def bypass_targets(command) -> list:
    """List of (rel_path, matched_pattern) for every guarded CONFIG path written
    through the shell (copy/move excluded — the blessed workaround). Pure +
    fail-open: junk input → []."""
    import fnmatch
    patterns = _guard_patterns()
    hits = []
    for rel in shell_write_targets(command, include_copy_move=False):
        pat = next((p for p in patterns if fnmatch.fnmatch(rel.lower(), p.lower())), None)
        if pat:
            hits.append((rel, pat))
    return hits


def core(data: dict) -> None:
    """Telemetry core: on a guarded-path bypass, record it to the usage ledger
    and write ONE advisory line. stderr only — PostToolUse, so it never blocks;
    the command already ran. Records the TARGET + matched pattern only, never the
    raw command (which could carry secrets from an `echo ... > file`)."""
    if data.get("tool_name") != "Bash":
        return
    cmd = hook_runtime.bash_command(data)
    hits = bypass_targets(cmd)
    if not hits:
        return
    session = data.get("session_id") or os.environ.get("HARNESS_SESSION_ID") or ""
    try:
        from telemetry_paths import append_event
        for rel, pat in hits:
            append_event("hook-telemetry.jsonl", {
                "source": "hook:bash",
                "event": "write_guard_bypass",
                "target": rel,
                "matched": pat,
                "session": session,
            })
    except Exception:  # noqa: BLE001 — telemetry must never break the op
        pass
    targets = ", ".join(rel for rel, _ in hits)
    # Default sink is systemMessage (a SECURITY advisory — an escaped write to gate
    # config the human must see); reroutable via nudge-channels.yaml. Route to the
    # SHARED queue (no terminal write here) so both the standalone main() and the
    # dispatcher own the single stdout blob — makes core() a stdout-free in-process
    # callable (no double write).
    hook_runtime.emit_nudge(
        _NAME,
        "[advisory] bash_write_guard: a gate-config path was written through the "
        "shell (%s), bypassing write_guard. PostToolUse cannot block — the change "
        "already ran. It IS tracked, so it shows as a git diff; verify it was "
        "intended. Edit gate config with a normal editor outside the session, or "
        "via its CLI (e.g. plan_approval.py)." % targets,
        session=session, default_channel="systemMessage")


def main(raw=None) -> None:
    """Read stdin, check enabled, run core inside a fail-open guard, then drain a
    queued systemMessage (the escaped-write advisory) into the single terminal blob,
    else a plain continue — mirrors the hand-rolled nudge mains, and lets the
    dispatcher call core() in-process without a double stdout write."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_NAME, "telemetry"):
            core(data)
    except Exception as e:  # noqa: BLE001 — telemetry must never break the op
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.drain_or_continue()


if __name__ == "__main__":
    main()
