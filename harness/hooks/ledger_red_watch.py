#!/usr/bin/env python3
"""ledger_red_watch.py — PostToolUse:{Write|Edit|MultiEdit, Bash} nudge (nudge-class).

`BUGS.md` is the bug ledger, and `scripts/bugs_ledger_check.py` is the gate that
scores it. Until 260908 that gate had never once run over the live file. Its own
suite (`test_the_bug_ledger_says_what_the_tree_says.py:13-14`) exercises it on a
SEEDED ledger in `tmp_path`, deliberately and correctly — a worktree may not have
`plans/` at all, and a rule that only ever ran on one live file has never been
shown to go red on anything. So the rules are proven; the ledger is unwatched.

Measured consequence, 260908: a row whose Trạng thái cell opened with `🔒` instead
of a declared label survived two full merge rounds. Nothing was broken — nothing
was looking.

── WHY A HOOK, AND WHY THIS EVENT ─────────────────────────────────────────────
`BUGS.md` lives under `plans/`, which is gitignored (`.gitignore:345`). Three
consequences, each of which killed an earlier design:

* `git ls-files` does not know the file, so NO pre-commit hook can score it:
  editing the ledger never produces a commit. A pre-commit gate would fire when
  someone commits CODE — precisely when the ledger did not change — and stay
  silent when it did.
* CI never has the file (the clone carries no `plans/`), so no pipeline job can
  score it either.
* Every rops lane holds its own stale copy: measured 260908, twelve lanes, eleven
  different sizes, 62 KB to 269 KB, one lane with no file at all. A test in the
  suite would therefore score whichever snapshot its lane last synced — the same
  commit going red on one lane, green on another and skipped on a third.

That leaves exactly one place where the question is well-posed: the HOST tree,
at the moment of the write. Hence PostToolUse.

── WHY IT WATCHES STATE, NOT TOOL NAMES ───────────────────────────────────────
Registered on BOTH PostToolUse groups and keyed on a DIGEST of the file, never on
`tool_input.file_path`. A ledger edit spelled `python3 - <<PY`, `sed -i`, or
`cat >>` carries no file_path at all, and that spelling is not hypothetical: it
is how the row that survived two merges was written. Digest-keying costs one
sha256 of ~260 KB per tool call (measured: see the commit message) and is blind
to nothing.

── WHY IT DOES NOT BLOCK ──────────────────────────────────────────────────────
PostToolUse runs AFTER the write. `exit 2` cannot un-write anything; it would
only leak the dispatcher's own command line into the transcript
(`hook_dispatch.py:28`). This hook reports, at `rc=0`, and the reporting channel
was chosen by measurement rather than from the table — see below.

── THE CHANNEL, AND THE MEASUREMENT THAT FOUND IT (260908) ────────────────────
The obvious choice, `kind: additionalContext`, is SILENTLY DISCARDED here:
`hook_dispatch.py:61` limits that field to `UserPromptSubmit`/`SessionStart`, so
a PostToolUse core declaring it builds a string that is then dropped, with no
error and no warning. `stderr` at `rc=0` reaches nobody either
(`hook_runtime.py:259`). What works is `systemMessage`, which is the model+user
channel (`hook_runtime.py:263`) — established by running a probe core through the
real dispatcher, not by reading the table.

🛑 The first run of that probe measured BOTH channels dead, and that reading was
wrong. The probe was registered in `hook-dispatch.yaml` but not declared
`enabled` in the hook config, so `hook_dispatch.py:359` skipped it before import.
A hook that does not FIRE and a hook whose channel is dead produce the identical
blob — `{"continue": true}` — and nothing distinguishes them from the outside.
What separated them was a positive control from a DIFFERENT core in the same
group: `backlog_capture_nudge` emitted its `systemMessage` on the same run, so
the channel was open and the silence was ours. Anyone re-measuring this needs
that control; the hook's own output cannot answer the question.

🛑 Being listed in `hook-dispatch.yaml` is NOT what makes a hook run. The config
that is actually read is whatever `HARNESS_HOOK_CONFIG` points at — that env var
REPLACES the base outright (`hook_runtime.py:541`), it does not merge with it;
the shipped `harness/data/harness-hooks.yaml` is the default only when the var is
unset. This is why `enabled` is declared in BOTH files: one keeps the hook alive
on an install that overrides the base (this repo does), the other on a plain
install that reads the shipped default. Check with
`hook_runtime._config_path()`; do not infer it from a filename.

── WHAT IT REPORTS ────────────────────────────────────────────────────────────
Only rows that went red SINCE THE LAST LOOK are named as NEW. Pre-existing red
belongs to whoever wrote it and is listed, once, under its own heading — a hook
that blames the current session for another session's debt is a hook that gets
turned off, which is the failure mode `test_durations_still_describes_this_tree`
documents for the durations budget.

The baseline lives in `<data_root>/state/ledger_red.json`, written with
`os.replace` so two concurrent sessions cannot interleave a half-written file.
The baseline is shared on purpose: it means "the last state anyone saw", so the
session that turns a row red is the session that hears about it.
"""

from __future__ import annotations

import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

try:
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")  # type: ignore[union-attr]
except Exception:  # noqa: BLE001 — older streams; never fatal
    pass

_HOOKS_DIR = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, os.path.join(_HOOKS_DIR, "..", "scripts"))
if _HOOKS_DIR not in sys.path:
    sys.path.append(_HOOKS_DIR)
import harness_paths  # noqa: E402
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = Path(__file__).stem

#: The ledger, relative to the project root. One file: this hook is not a
#: general markdown-table linter, and a glob would make its cost unbounded.
_LEDGER_REL = "plans/260905-1147-whole-project-revolution/BUGS.md"
_CHECKER_REL = "scripts/bugs_ledger_check.py"

#: Ceiling on the checker subprocess. It parses one file and shells out to `git`
#: for ancestry; measured well under a second. This is a "the checker hung"
#: bound, not a budget — a tight one would make the hook flaky under load, and a
#: flaky nudge is a nudge that gets switched off.
_CHECK_TIMEOUT_S = 60


def _project_root() -> Path | None:
    """The tree holding the ledger, or None when this is not that tree.

    `data_root()` is the project zone, and its parent is the project. A worktree
    or lane resolves elsewhere and simply has no ledger — the hook then does
    nothing, which is the correct answer there rather than a warning.
    """
    try:
        return Path(harness_paths.data_root()).parent
    except Exception:  # noqa: BLE001 — a visibility hook never crashes a tool call
        return None


def _digest(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def _state_path(root: Path) -> Path:
    try:
        return Path(harness_paths.data_root()) / "state" / "ledger_red.json"
    except Exception:  # noqa: BLE001
        return root / ".harness" / "state" / "ledger_red.json"


def _read_state(p: Path) -> dict:
    try:
        parsed = json.loads(p.read_text(encoding="utf-8"))
        return parsed if isinstance(parsed, dict) else {}
    except Exception:  # noqa: BLE001 — absent or malformed reads as "never looked"
        return {}


def _write_state(p: Path, payload: dict) -> None:
    """Atomic, because `<data_root>/state/` is shared by every session on this
    tree. A half-written baseline would make the NEXT run diff against garbage
    and report rows nobody touched."""
    try:
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(f".{os.getpid()}.tmp")
        tmp.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        os.replace(tmp, p)
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(_NAME, e)


def _run_checker(root: Path, ledger: Path) -> list[str] | None:
    """The checker's red lines, or None when it could not be run.

    None and `[]` are DIFFERENT answers and are never collapsed: `[]` means the
    ledger is clean, None means nobody asked. Collapsing them would let a broken
    checker read as a clean ledger — the exact shape this hook exists to catch.
    """
    checker = root / _CHECKER_REL
    if not checker.is_file():
        return None
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--quiet", str(ledger)],
            cwd=root, capture_output=True, text=True,
            timeout=_CHECK_TIMEOUT_S, check=False,
        )
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(_NAME, e)
        return None
    # rc: 0 clean, 1 red. Anything else is the checker itself failing, and its
    # stdout is then not a findings list — report nothing rather than parse noise.
    if proc.returncode not in (0, 1):
        return None
    return [ln.removeprefix("🔴").strip() for ln in proc.stdout.splitlines() if ln.startswith("🔴")]


def _run_checker_warn(root: Path, ledger: Path) -> list[str]:
    """The checker's YELLOW lines. Separate call rather than a second return value so the red
    path's None/[] distinction stays exactly as it was; a warning that cannot be read is simply
    absent, never mistaken for a clean ledger."""
    checker = root / _CHECKER_REL
    if not checker.is_file():
        return []
    try:
        proc = subprocess.run(
            [sys.executable, str(checker), "--quiet", str(ledger)],
            cwd=root, capture_output=True, text=True,
            timeout=_CHECK_TIMEOUT_S, check=False,
        )
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(_NAME, e)
        return []
    if proc.returncode not in (0, 1):
        return []
    return [ln.removeprefix("⚠️").strip() for ln in proc.stdout.splitlines() if ln.startswith("⚠️")]


def _row_id(line: str) -> str:
    """`B-125 L157: …` -> `B-125`. Rows move lines on every edit above them, so
    keying the baseline by line number would report every row below an insertion
    as newly red."""
    return line.split(" ", 1)[0] if line else line


def core(data: dict) -> None:
    root = _project_root()
    if root is None:
        return
    ledger = root / _LEDGER_REL
    if not ledger.is_file():
        return

    try:
        digest = _digest(ledger)
    except Exception as e:  # noqa: BLE001
        hook_runtime.log_hook_error(_NAME, e)
        return

    state_p = _state_path(root)
    state = _read_state(state_p)
    if state.get("digest") == digest:
        return  # unchanged since the last look — the common case, and cheap

    findings = _run_checker(root, ledger)
    if findings is None:
        return

    seen_before = state.get("red") is not None
    known = {_row_id(x) for x in (state.get("red") or [])}
    _write_state(state_p, {"digest": digest, "red": findings})

    if not findings:
        return

    fresh = [f for f in findings if _row_id(f) not in known]
    old = [f for f in findings if _row_id(f) in known]

    # First sight of this ledger: there is no baseline, so NOTHING can honestly be
    # called new. List what is there under the debt heading and start the baseline.
    if not seen_before:
        body = "\n".join(f"    {f}" for f in findings)
        text = (
            f"[{_NAME}] {ledger.name}: {len(findings)} dòng đỏ ĐANG CÓ (nền vừa ghi lần đầu — "
            f"chưa quy cho ai):\n{body}\n"
            f"  Chạy: python3 {_CHECKER_REL} {_LEDGER_REL}"
        )
        hook_runtime.emit_nudge(_NAME, text, session=data.get("session_id"),
                                default_channel="systemMessage")
        return

    yellow = _run_checker_warn(root, ledger)
    if not fresh:
        return  # only pre-existing debt: already reported once, stay quiet

    lines = [f"[{_NAME}] {ledger.name}: {len(fresh)} dòng đỏ MỚI sau lượt ghi này:"]
    lines += [f"    {f}" for f in fresh]
    if yellow:
        lines.append(f"  ⚠️  {len(yellow)} cảnh báo (SHA có thật, chưa lên main — không tính đỏ):")
        lines += [f"    {y}" for y in yellow]
    if old:
        lines.append(f"  (còn {len(old)} dòng đỏ CŨ, có chủ khác: "
                     + ", ".join(sorted({_row_id(f) for f in old})) + ")")
    lines.append(f"  Chạy: python3 {_CHECKER_REL} {_LEDGER_REL}")
    hook_runtime.emit_nudge(_NAME, "\n".join(lines), session=data.get("session_id"),
                            default_channel="systemMessage")


def main(raw: str | None = None) -> None:
    """Standalone entry. The dispatcher calls `core()` in-process instead, so the
    enabled-check and the single terminal stdout write live here, not in core()."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_NAME, HOOK_CLASS):
            core(data)
    except Exception as e:  # noqa: BLE001 — a visibility nudge never breaks the op
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.drain_or_continue()


if __name__ == "__main__":
    main()
