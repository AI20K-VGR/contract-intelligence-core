#!/usr/bin/env python3
"""run_native_slice.py — end-to-end acceptance over REAL Claude Code transport.

The sibling `run_vertical_slice.py` proves the gate logic with a SIMULATED
transport: it pipes stdin JSON into the hook subprocesses itself. That proves the
hooks are correct given a payload; it does NOT prove Claude Code's own hook wire
delivers that payload. This slice closes that gap by driving a real headless
`claude -p` session whose PreToolUse hooks are the harness gates — so the block is
produced by Claude Code's native transport, not by us hand-feeding stdin.

Scenario (block-then-pass, native):
  1. claude is told to Edit a GUARDED file (harness/data/harness-hooks.yaml).
     write_guard fires at PreToolUse:Edit and BLOCKS → the file is unchanged AND
     a write_guard `gate_block` event lands in the trace (the trace event, not the
     unchanged file alone, is the proof: an unchanged file could also mean claude
     never tried — a traced block means it tried and the gate stopped it).
  2. claude is told to Edit a NORMAL file (notes.txt). No guard matches → the edit
     lands → the file is changed (claude attempted + the gate allowed, natively).

OPT-IN + auto-skip: this runs a real model call (slow, costs tokens), so it stays
OUT of the default CI. It runs only when BOTH hold:
  - the env HARNESS_E2E_NATIVE=1 is set (explicit opt-in), and
  - `claude` resolves on PATH.
Otherwise it prints a SKIP line and exits 0 — the fast simulated slice is the CI
gate; this one is the on-demand native proof.

Usage: HARNESS_E2E_NATIVE=1 python3 harness/e2e/run_native_slice.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_E2E = Path(__file__).resolve().parent
_HARNESS = _E2E.parent

_GUARDED_REL = "harness/data/harness-hooks.yaml"
_NORMAL_REL = "notes.txt"
_PROBE_LINE = "# native-e2e-probe"

_PASSED = []
_FAILED = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    (_PASSED if ok else _FAILED).append((name, detail))
    print("  %s %s%s" % ("✓" if ok else "✗", name,
                         (" — " + detail) if (detail and not ok) else ""))


_SETTINGS = {
    "hooks": {
        "PreToolUse": [
            {
                "matcher": "Write|Edit|MultiEdit",
                "hooks": [{
                    "type": "command",
                    "command": (sys.executable + " \"$CLAUDE_PROJECT_DIR\""
                                "/harness/hooks/write_guard.py"),
                }],
            },
        ],
    },
}


def _env(root: Path) -> dict:
    env = dict(os.environ)
    # Don't let the OUTER harness session's context leak into the child run.
    for k in ("HARNESS_HOOK_CONFIG", "HARNESS_ACTIVE_PLAN",
              "HARNESS_STAGE_POLICY", "PYTEST_CURRENT_TEST"):
        env.pop(k, None)
    env["HARNESS_ROOT"] = str(root)
    env["HARNESS_STATE_DIR"] = str(root / "harness" / "state")
    env["HARNESS_USER"] = "native-e2e"
    env["CLAUDE_PROJECT_DIR"] = str(root)
    return env


def _claude(root: Path, prompt: str, timeout: int = 240):
    """One headless Claude turn in `root`. `--setting-sources project` makes the
    temp repo's .claude/settings.json (the harness gates) the only settings in
    play; `--permission-mode acceptEdits` removes the permission prompt so the
    HARNESS HOOK — not the permission system — is the thing that gates the edit."""
    argv = [
        "claude", "-p", prompt,
        "--output-format", "json",
        "--setting-sources", "project",
        "--permission-mode", "acceptEdits",
        "--max-turns", "4",
    ]
    return subprocess.run(argv, cwd=str(root), capture_output=True, text=True,
                          env=_env(root), timeout=timeout)


def _trace_events(root: Path):
    out = []
    trace = root / "harness" / "state" / "trace"
    if trace.is_dir():
        for f in sorted(trace.glob("trace-*.jsonl")):
            for line in f.read_text(encoding="utf-8").splitlines():
                try:
                    out.append(json.loads(line))
                except json.JSONDecodeError:
                    pass
    return out


def seed_git_repo(root: Path) -> None:
    subprocess.run(["git", "init", "-q"], cwd=str(root), check=True,
                   capture_output=True)
    subprocess.run(["git", "add", "-A"], cwd=str(root), check=True,
                   capture_output=True)
    subprocess.run(["git", "-c", "user.email=native@local", "-c",
                    "user.name=native-e2e", "commit", "-qm", "seed"],
                   cwd=str(root), check=True, capture_output=True)


def _should_skip():
    if os.environ.get("HARNESS_E2E_NATIVE") != "1":
        return ("opt-in: set HARNESS_E2E_NATIVE=1 to run the native slice "
                "(the fast simulated slice is the CI gate)")
    if not shutil.which("claude"):
        return "claude not on PATH (native transport unavailable)"
    return None


def main() -> int:
    skip = _should_skip()
    if skip:
        print("e2e native slice: SKIP — %s" % skip)
        return 0

    tmp = Path(tempfile.mkdtemp(prefix="harness-native-e2e-"))
    print("e2e native slice in %s (transport: real claude -p)" % tmp)
    try:
        root = tmp / "proj"
        root.mkdir(parents=True)
        for sub in ("hooks", "scripts", "data", "install"):
            shutil.copytree(_HARNESS / sub, root / "harness" / sub)
        (root / ".claude").mkdir()
        (root / ".claude" / "settings.json").write_text(
            json.dumps(_SETTINGS, indent=2), encoding="utf-8")
        (root / _NORMAL_REL).write_text("notes\n", encoding="utf-8")
        seed_git_repo(root)

        guarded = root / _GUARDED_REL
        normal = root / _NORMAL_REL
        guarded_before = guarded.read_text(encoding="utf-8")

        # 1. BLOCK — native edit of a guarded file must be stopped by write_guard.
        proc = _claude(root,
                       "Use the Edit tool to append a new line that is exactly "
                       "'%s' to the file %s. Do only that one edit."
                       % (_PROBE_LINE, _GUARDED_REL))
        _check("claude -p ran (block scenario)", proc.returncode == 0,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))
        _check("guarded file UNCHANGED after native edit attempt",
               guarded.read_text(encoding="utf-8") == guarded_before)
        events = _trace_events(root)
        wg_blocks = [e for e in events
                     if e.get("hook") == "write_guard"
                     and e.get("event") == "gate_block"]
        _check("write_guard gate_block traced (proves the edit was attempted "
               "AND natively gated)", bool(wg_blocks),
               "no write_guard gate_block in trace")

        # 2. PASS — native edit of a normal file goes through.
        proc = _claude(root,
                       "Use the Edit tool to append a new line that is exactly "
                       "'%s' to the file %s. Do only that one edit."
                       % (_PROBE_LINE, _NORMAL_REL))
        _check("claude -p ran (pass scenario)", proc.returncode == 0,
               "rc=%s stderr=%s" % (proc.returncode, proc.stderr[:200]))
        _check("normal file CHANGED (native edit allowed through the gate)",
               _PROBE_LINE in normal.read_text(encoding="utf-8"))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = not _FAILED
    summary = "%s | %d passed, %d failed | transport=native-claude-p" % (
        datetime.now(timezone.utc).isoformat(), len(_PASSED), len(_FAILED))
    print("\ne2e:", summary)
    try:
        with open(_E2E / "RUN-LOG.md", "a", encoding="utf-8") as fh:
            fh.write("- %s\n" % summary)
            for name, detail in _FAILED:
                fh.write("  - FAILED: %s — %s\n" % (name, detail))
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
