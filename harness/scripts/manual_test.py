#!/usr/bin/env python3
"""manual_test.py — admissibility of a manual-test result.

The anti-fabrication floor: a telemetry-anchored
output proves "a real command ran and this is its real output" — it defeats pure
hallucination — but it does NOT prove the command exercised the right thing (an
agent with a shell can run a real command against the WRONG endpoint and cite a
real trace). So anchored is a FLOOR, never a correctness proof:

  - evidence_tier `claimed` (agent-written) is below the floor — never hard-admissible.
  - `anchored` is honored only when the cited anchor id is actually present in
    the manual-test anchor telemetry the hook wrote; a fabricated id is REJECTED.
  - a hard gate additionally needs a human charter CO-SIGN — a rostered reviewer
    distinct from the author. Anchored-without-co-sign stays SOFT.

This is presence + tamper-evidence, NOT authentication. The co-sign is the human
judgement the machine cannot supply; the anchor is the floor that makes pure
fabrication cost a real command run.
"""

import argparse
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

ANCHOR_SINK = "manual-test-anchor.jsonl"


def anchor_id_for(command: str) -> str:
    """Deterministic anchor id for a Bash command (sha256, 16 hex). No clock /
    randomness, so the citing artifact and the hook record agree."""
    return hashlib.sha256((command or "").encode("utf-8")).hexdigest()[:16]


def build_anchor(command, output=None, *, session=None, source="hook") -> dict:
    """The anchor record the PostToolUse hook writes (actor + ts are added by
    telemetry_paths on append). output_hash links the trace to the real output
    without storing it.

    `source` records which creation path wrote the anchor — "hook" (the
    PostToolUse telemetry hook) or "cli" (the explicit `manual_test.py --anchor`
    path). It defaults to "hook", so a record written before this field existed
    reads as hook-sourced."""
    rec = {
        "anchor_id": anchor_id_for(command),
        "cmd_hash": anchor_id_for(command),
        "source": source,
    }
    if output is not None:
        rec["output_hash"] = hashlib.sha256(
            str(output).encode("utf-8")).hexdigest()[:16]
    if session:
        rec["session"] = session
    return rec


def _anchor_sink(root) -> Path:
    return Path(root) / "telemetry" / ANCHOR_SINK


# ---------------------------------------------------------------------------
# Session marker gate — arm anchoring without the env var
# ---------------------------------------------------------------------------
#
# The anchor hook only records during an explicit manual-test session. Keying
# that solely on the HARNESS_MANUAL_TEST_SESSION env var has a hole: a forgotten
# export, or a subagent that does not inherit the parent's env, silently records
# ZERO anchors. A session MARKER file under the shared state dir closes that hole
# — the hook records when the env var is set OR a marker for the session exists,
# and the marker survives a subagent boundary because it lives on disk, not in
# the process env. The marker's PRESENCE is what arms anchoring; its content is
# attribution only.

SESSION_MARKER_DIR = "manual-test-session"


def _safe_session(session_id) -> str:
    """Sanitize a session id into a single safe path component. Mirrors
    hook_runtime.safe_session_id — duplicated here (not imported) because this
    module runs as a standalone script/CLI without hooks/ on sys.path, and the
    sanitizer is a path-traversal guard that must never be skipped. Any char
    outside [A-Za-z0-9_-] collapses to '_' so a hostile id cannot traverse dirs."""
    return "".join(
        c if (c.isalnum() or c in "-_") else "_" for c in (str(session_id) if session_id else "_")
    )


def _real_session(session_id) -> bool:
    """True only for a session id that survives sanitization with at least one
    real (alphanumeric) character. A falsy or all-sanitized-away id (None, '',
    '/', '___') would collapse to the single shared '_' bucket — arming that
    bucket would record an anchor for EVERY non-session Bash command, defeating
    the session scoping the marker exists to enforce. So a degenerate id can
    neither arm nor match a marker."""
    return bool(session_id) and any(c.isalnum() for c in _safe_session(session_id))


def session_marker_path(root, session_id) -> Path:
    """The marker file that arms anchoring for `session_id`, under the state dir
    (`root`) so it is shared between the main agent and its subagents."""
    return Path(root) / SESSION_MARKER_DIR / _safe_session(session_id)


def _soft_actor(session_id=None) -> str:
    """Best-effort acting identity for a marker record. hook_runtime may be
    unimportable when this runs as a standalone script — fall back rather than
    fail (the marker's value is presence, the actor is attribution)."""
    try:
        import hook_runtime
        return hook_runtime.resolve_actor(session_id=session_id)
    except Exception:  # noqa: BLE001
        return "user:unknown"


def arm_session(root, session_id, actor=None):
    """Create the session marker so the anchor hook records without the env var
    set (arms subagents too). Write-once-if-absent / idempotent: an already-armed
    session is a no-op (the existing marker is left byte-for-byte untouched).
    Returns the marker path, or None when `session_id` is degenerate (falsy or
    all-sanitized-away) — such an id is REFUSED so it cannot arm the shared '_'
    bucket. The record carries actor + ts for attribution; presence is what
    gates."""
    if not _real_session(session_id):
        return None
    p = session_marker_path(root, session_id)
    p.parent.mkdir(parents=True, exist_ok=True)
    if not p.exists():
        from datetime import datetime, timezone
        rec = {
            "session": session_id,
            "actor": actor or _soft_actor(session_id),
            "ts": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        }
        p.write_text(json.dumps(rec, ensure_ascii=False) + "\n", encoding="utf-8")
    return p


def session_armed(root, session_id) -> bool:
    """True when a marker for `session_id` exists under `root`. A degenerate id
    (falsy or all-sanitized-away) is never armed — it must not match the shared
    '_' bucket. Fail-soft: a missing marker reads as not-armed, never a crash."""
    if not _real_session(session_id):
        return False
    try:
        return session_marker_path(root, session_id).is_file()
    except Exception:  # noqa: BLE001
        return False


def anchor_exists(anchor_id, root) -> bool:
    """True when `anchor_id` is present in the anchor sink under `root`
    (root = the state dir holding telemetry/). Fail-soft on a missing/corrupt
    sink — a missing record reads as 'not anchored', never a crash.

    Unions the legacy sink with every per-session shard. The hook writes through
    the sharding writer, so a session-bearing run lands in
    `manual-test-anchor-<disc>.jsonl` while this read used to open only the
    unsharded path — and every real manual test carries a session, so every real
    anchor graded as a fabricated citation."""
    import telemetry_paths
    for p in telemetry_paths.sink_read_files(Path(root) / "telemetry",
                                             ANCHOR_SINK):
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            continue
        for ln in text.splitlines():
            try:
                rec = json.loads(ln)
            except ValueError:
                continue
            if isinstance(rec, dict) and rec.get("anchor_id") == anchor_id:
                return True
    return False


def admissibility(check, root):
    """(tier, reason) for a manual-test check. tier ∈ anchored | claimed |
    rejected. `root` is the state dir holding telemetry/."""
    tier = (check or {}).get("evidence_tier")
    if tier != "anchored":
        return "claimed", ("evidence_tier is %r (agent-written) — below the "
                           "anchored floor" % tier)
    aid = check.get("anchor_id") or check.get("trace_id")
    if not aid:
        return "rejected", "evidence_tier is anchored but no anchor id is cited"
    if anchor_exists(aid, root):
        return "anchored", "anchor %s witnessed by the telemetry hook" % aid
    return "rejected", ("cited anchor %s is not in the manual-test anchor "
                        "telemetry — fabricated citation" % aid)


LEDGER_NAME = "manual-test-log.md"

_LEDGER_HEADER = (
    "# Manual-test discovery log\n\n"
    "A committed marker that a manual test ran — so a human reading the PR can "
    "DISCOVER it.\nThis is NOT a second evidence tier: the evidence floor stays "
    "the telemetry anchor plus a\ncharter co-sign distinct from the author "
    "(see `hs:manual-test`). A row here proves nothing\nabout admissibility; it "
    "only points a reader at a manual pass that happened.\n\n"
    "| when | actor | charter | story | anchor_ids | cosign |\n"
    "|---|---|---|---|---|---|\n"
)


def _md_cell(value) -> str:
    """Make a value safe inside a single markdown table cell: a literal `|`
    would split the row into extra columns and a newline would break the table,
    so both are neutralized (backslash first, so the pipe-escape is not itself
    re-escaped)."""
    text = "" if value is None else str(value)
    return (text.replace("\\", "\\\\").replace("|", "\\|")
            .replace("\n", " ").replace("\r", " "))


def append_ledger(plan_dir, row, actor=None):
    """Append one row to the committed manual-test discovery ledger at
    plans/<plan>/manual-test-log.md. Append-only: the header is written exactly
    once (when the file is absent) and each call adds one row without ever
    rewriting an earlier one. `row` is a dict with charter/story/anchor_ids/
    cosign; `actor` + a `when` ts are stamped for attribution. This is a
    discovery MARKER for humans, committed so it shows in the PR diff — never an
    admissibility tier (the evidence floor is unchanged). Returns the ledger
    path."""
    from datetime import datetime, timezone
    row = row or {}
    p = Path(plan_dir) / LEDGER_NAME
    p.parent.mkdir(parents=True, exist_ok=True)
    if actor is None:
        actor = _soft_actor(row.get("session"))
    anchor_ids = row.get("anchor_ids")
    if isinstance(anchor_ids, (list, tuple)):
        anchor_ids = ", ".join(str(a) for a in anchor_ids)
    when = datetime.now(timezone.utc).isoformat(timespec="seconds")
    cells = [when, actor, row.get("charter"), row.get("story"), anchor_ids, row.get("cosign")]
    line = "| " + " | ".join(_md_cell(c) for c in cells) + " |\n"
    if not p.exists():
        p.write_text(_LEDGER_HEADER + line, encoding="utf-8")
    else:
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(line)
    return p


_LESSON_KINDS = ("feedback", "project")


def record_lesson(kind, payload, *, root=None, actor=None, session=None) -> bool:
    """Append one manual-testing lesson to state/manual-tester/<kind>.jsonl
    (append-only, actor+ts enriched). `feedback` = a setup gotcha; `project` = a
    real bug + how it reproduced. These compound across sessions so a later
    charter starts from known traps — they are LESSONS, never test evidence.
    Returns True when written. Invalid kind → False (never raises)."""
    if kind not in _LESSON_KINDS:
        return False
    try:
        import json
        from datetime import datetime, timezone
        if root is None:
            import harness_paths
            base = harness_paths.state_dir()
        else:
            base = Path(root)
        d = base / "manual-tester"
        d.mkdir(parents=True, exist_ok=True)
        if actor is None:
            try:
                import hook_runtime
                actor = hook_runtime.resolve_actor(session_id=session)
            except Exception:  # noqa: BLE001
                actor = "user:unknown"
        rec = {"kind": kind, "payload": payload, "actor": actor,
               "ts": datetime.now(timezone.utc).isoformat(timespec="seconds")}
        if session:
            rec["session"] = session
        with open(d / ("%s.jsonl" % kind), "a", encoding="utf-8") as fh:
            fh.write(json.dumps(rec, ensure_ascii=False) + "\n")
        return True
    except Exception:  # noqa: BLE001 — a lesson write must never break a session
        return False


def hard_admissible(check, root, team_path=None, team=None):
    """(ok, reason): a manual-test check is HARD-admissible only when its output
    is genuinely anchored AND the charter carries a co-sign. Personal-first: the
    co-sign is attribution (who vouched the command tested the right thing), not a
    roster check. Claimed/rejected, or anchored-without-co-sign, stays soft. The
    team/team_path params are accepted for caller compatibility, now unused."""
    tier, reason = admissibility(check, root)
    if tier != "anchored":
        return False, "manual evidence is %s — %s" % (tier, reason)
    cosign = (check or {}).get("charter_cosign")
    if not cosign:
        return False, ("anchored output but no charter co-sign — a hard manual "
                       "gate needs a co-sign vouching the charter (the anchor "
                       "proves a real command ran, not that it tested the right "
                       "thing)")
    actor = (check or {}).get("actor")
    if not actor or cosign == actor:
        # A hard gate needs a co-sign DISTINCT from the author. An absent/empty
        # actor cannot establish distinctness, so it is NOT hard either — else an
        # agent could simply omit `actor` to dodge the self-co-sign check.
        return False, ("charter co-sign must be present AND distinct from the "
                       "author (actor) — the schema promises a rostered reviewer "
                       "distinct from the author; a self or unattributed co-sign "
                       "vouches for one's own work and stays soft")
    return True, "anchored output + distinct charter co-sign present"


def verify_portable(check, observed_output=None):
    """Transport-INTEGRITY only — NOT anti-fabrication, NOT a gate input, and it
    grants NO evidence tier. It lets a reviewer on another machine confirm a
    cited manual-check's hashes are internally consistent, and (when the reviewer
    RE-RUNS THE REAL COMMAND THEMSELVES and passes its output) that the output
    hash matches what was cited.

    It never executes anything itself. That is deliberate: a self-referential
    command (`printf PASS`, `echo OK`) recomputes to a matching hash yet proves
    nothing, so a match here is evidence the record survived transit intact —
    NEVER that the command ran, and never that it tested the right thing. The
    reviewer must run the real command in the real environment and judge whether
    it exercised the right thing; this helper only guards against a record being
    altered between machines. It is intentionally NOT called by `admissibility`
    / `hard_admissible` / the DoD gate — portability must not move the floor.

    Returns (ok, reason)."""
    check = check or {}
    cmd = check.get("cmd") or check.get("command")
    cmd_hash = check.get("cmd_hash")
    if cmd is None or cmd_hash is None:
        return False, "cited check lacks cmd/cmd_hash — nothing to integrity-check"
    if anchor_id_for(cmd) != cmd_hash:
        return False, ("cmd_hash does not match the cited command — the record "
                       "was altered in transit")
    if observed_output is not None:
        expected = check.get("output_hash")
        got = hashlib.sha256(str(observed_output).encode("utf-8")).hexdigest()[:16]
        if expected != got:
            return False, ("re-run output hash does not match the cited "
                           "output_hash — output differs from what was cited")
        return True, ("cmd_hash + your re-run output_hash both match (transit "
                      "intact — you must still confirm the command tested the "
                      "right thing)")
    return True, ("cmd_hash matches the cited command (transit intact; re-run "
                  "the real command to confirm the output and that it tested "
                  "the right thing)")


# ---------------------------------------------------------------------------
# Explicit CLI anchor — a SECOND creation path (subagent-safe, self-exec only)
# ---------------------------------------------------------------------------
#
# `--anchor --cmd "<command>"` stamps ONE deliberate probe without depending on
# the session env. It runs in a subagent (it is just a Bash call). It is closed
# against the self-authentication hole a naive design would open: the CLI SELF-
# EXECUTES the command and hashes the output IT captured. There is deliberately
# NO way for the caller to supply the output (no --output-file / --output-stdin),
# so the agent cannot write an anchor for a command that never ran. This puts the
# CLI at exactly the hook's trust level: "the harness ran a real command, this is
# its real output". It does NOT prove the command tested the right thing — the
# command the agent chose can still be trivial (`echo PASS`); the ceiling stays
# the human charter co-sign (hard_admissible), never the anchor itself.

_ANCHOR_TIMEOUT_S = 120


def run_and_anchor(command, session=None, timeout=_ANCHOR_TIMEOUT_S):
    """Self-execute `command`, hash the REAL captured output, and append a
    cli-sourced anchor. Returns (anchor_id, exit_code), or (None, None) when the
    command could not be executed at all (spawn failure / timeout) — a run that
    never happened is not anchored. A command that runs and exits non-zero DID
    run: it is anchored, with its exit code recorded.

    `errors="replace"` keeps a probe that emits non-UTF-8 bytes (a binary curl
    body, an openssl dump) fail-SOFT: the command ran, so its output is captured
    and hashed with the undecodable bytes replaced, rather than a strict decode
    raising UnicodeDecodeError and turning a real run into a crash."""
    try:
        proc = subprocess.run(
            ["bash", "-c", command],
            capture_output=True, text=True, timeout=timeout, errors="replace",
        )
    except (OSError, subprocess.SubprocessError):
        return None, None
    output = proc.stdout if proc.stdout else proc.stderr
    rec = build_anchor(command, output, session=session, source="cli")
    rec["exit_code"] = proc.returncode
    import telemetry_paths
    telemetry_paths.append_event(ANCHOR_SINK, rec)
    return rec["anchor_id"], proc.returncode


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="manual_test.py",
        description="Manual-test evidence helper. --anchor self-executes a "
        "command and records a cli-sourced anchor (the caller cannot supply the "
        "output; the harness captures it).",
    )
    p.add_argument("--anchor", action="store_true",
                   help="self-execute --cmd and record a cli-sourced anchor")
    p.add_argument("--cmd", help="the command to self-execute and anchor")
    p.add_argument("--session", default=None, help="optional session id to stamp")
    return p


def main(argv=None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.anchor:
        if not args.cmd:
            print("--anchor requires --cmd", file=sys.stderr)
            return 2
        anchor_id, exit_code = run_and_anchor(args.cmd, session=args.session)
        if anchor_id is None:
            print("command could not be executed — no anchor written", file=sys.stderr)
            return 1
        print("anchor_id=%s exit_code=%s" % (anchor_id, exit_code))
        return 0
    _build_argparser().print_help()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
