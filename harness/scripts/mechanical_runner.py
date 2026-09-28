#!/usr/bin/env python3
"""mechanical_runner.py — the unified mechanical-detector runner.

One entry for the two mechanical detector kinds a rule can declare:

  - grep  ({type: grep, pattern})  — a line-scan over in-scope changed files. No
    process exec, so it ALWAYS runs (safe regardless of trust). Bounded by a
    per-file size cap, a path-containment guard (never reads outside the tree),
    and a per-(rule,file) ReDoS wall-clock budget.
  - shell ({type: shell, cmd})    — an arbitrary command. RCE vector, so it
    auto-fires ONLY when the rule is base-verified (bytes match the manifest) OR
    the repo is trusted (hs-cli trust). Otherwise it is SKIPPED with an advisory
    finding — dropped to grep-only, never executed.

ADVISORY-FIRST: run() always returns a findings list and never raises; a finding
NEVER auto-sets a blocking verdict. This module MUST NOT be wired into a hook —
the trust gate bounds the auto-fire RCE risk, it does not eliminate it, so the
operator/CI/review-time caller stays the only invoker.
"""

import os
import re
import signal
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List

sys.path.append(str(Path(__file__).resolve().parent))

import trust_store
from scope_match import scope_matches as _canonical_scope_matches

# A shell detector that hangs must not wedge the runner; bound every command.
_CMD_TIMEOUT_S = 60

# Each char of a detector `flags` string is a single regex-flag code. Only these
# are honored; an unrecognized flags string enables NOTHING rather than silently
# turning on IGNORECASE because it happens to contain 'i'.
_GREP_FLAG_CODES = {"i": re.IGNORECASE, "m": re.MULTILINE, "s": re.DOTALL}

# Robustness bounds for the advisory grep scan.
_MAX_DETECTOR_FILE_BYTES = 2_000_000   # skip files larger than this (bounded memory)
_DETECTOR_SEARCH_BUDGET_S = 2.0        # per-(rule,file) wall-clock budget for ReDoS


class _DetectorBudgetExceeded(Exception):
    """Raised when a detector's per-file search blows its wall-clock budget."""


def _grep_flags(raw) -> int:
    """Resolve a detector `flags` string to an re flag mask. Honors flags only
    when EVERY char is a known single-char code; any unknown char -> 0."""
    s = str(raw or "")
    if not s or any(c not in _GREP_FLAG_CODES for c in s):
        return 0
    mask = 0
    for c in s:
        mask |= _GREP_FLAG_CODES[c]
    return mask


def _scope_matches(scope, changed_files) -> bool:
    """Case-sensitive (gitignore semantics) scope match via scope_match."""
    return _canonical_scope_matches(scope, changed_files, case_insensitive=False)


def _contained_path(root: Path, f):
    """Resolve a changed-file entry to a path INSIDE root, or None if it escapes
    (absolute path or `..` traversal) — the scan never reads outside the tree."""
    try:
        p = (root / f).resolve()
        p.relative_to(root.resolve())
    except (ValueError, OSError):
        return None
    return p


def _run_budgeted(fn, seconds):
    """Run fn() under a best-effort wall-clock budget via SIGALRM. Active only on
    the main thread of a POSIX interpreter; elsewhere it runs unbounded. Raises
    _DetectorBudgetExceeded on timeout. A caller's pre-existing ITIMER_REAL alarm
    is preserved (re-armed at its original deadline on exit)."""
    if (seconds <= 0 or not hasattr(signal, "SIGALRM")
            or threading.current_thread() is not threading.main_thread()):
        return fn()

    def _handler(signum, frame):
        raise _DetectorBudgetExceeded()

    prev_handler = signal.signal(signal.SIGALRM, _handler)
    started = time.monotonic()
    prev_remaining, prev_interval = signal.setitimer(signal.ITIMER_REAL, seconds)
    try:
        return fn()
    finally:
        signal.setitimer(signal.ITIMER_REAL, 0)        # cancel ours first
        signal.signal(signal.SIGALRM, prev_handler)    # restore caller's handler
        if prev_remaining > 0:                          # re-arm caller's alarm
            elapsed = time.monotonic() - started
            signal.setitimer(signal.ITIMER_REAL,
                             max(1e-6, prev_remaining - elapsed), prev_interval)


def _scan_lines(rx, text):
    """Collect (lineno, line) for every rx match. Isolated so the wall-clock
    budget can wrap exactly the (potentially catastrophic) search work."""
    return [(i, line) for i, line in enumerate(text.splitlines(), 1)
            if rx.search(line)]


def _run_shell(cmd: str, cwd, timeout: int = _CMD_TIMEOUT_S) -> Dict[str, Any]:
    """The single shell-exec primitive shared by the runner and
    standards_compliance_run. Captures stdout/stderr; never raises. shell=True is
    intentional (checks like `grep -q x f || true` need a shell); the RCE risk is
    bounded by the trust gate at the auto-fire caller and by this module never
    being wired into a hook."""
    try:
        proc = subprocess.run(
            cmd, shell=True, cwd=str(cwd), capture_output=True,
            text=True, timeout=timeout)
    except subprocess.TimeoutExpired:
        return {"executed": True, "timeout": True, "rc": None,
                "stdout": "", "stderr": "", "detail": "timeout after %ds" % timeout}
    except OSError as exc:
        return {"executed": True, "error": str(exc), "rc": None,
                "stdout": "", "stderr": "", "detail": "exec error: %s" % exc}
    return {"executed": True, "rc": proc.returncode,
            "stdout": proc.stdout, "stderr": proc.stderr}


def run_grep_detectors(rules, changed_files, root=".") -> List[Dict[str, Any]]:
    """Run the grep-type mechanical detectors over `changed_files` (line-scan).

    A rule with a non-grep / null detector contributes nothing; a bad-regex
    detector is skipped; a file outside scope, outside the repo tree, oversized,
    or unreadable is skipped; a pattern that backtracks past its budget is
    skipped. Never raises."""
    findings: List[Dict[str, Any]] = []
    try:
        root = Path(root)
    except TypeError:
        return findings  # malformed root → no findings (never raise)
    for rule in rules:
        det = rule.get("detector")
        if not isinstance(det, dict) or det.get("type") != "grep":
            continue
        pattern = det.get("pattern")
        if not isinstance(pattern, str) or not pattern:
            continue
        flags = _grep_flags(det.get("flags"))
        try:
            rx = re.compile(pattern, flags)
        except re.error:
            continue
        scope = rule.get("scope") or []
        for f in changed_files:
            if not _scope_matches(scope, [f]):
                continue
            fp = _contained_path(root, f)
            if fp is None:
                continue
            try:
                if fp.stat().st_size > _MAX_DETECTOR_FILE_BYTES:
                    continue
                text = fp.read_text(encoding="utf-8")
            except (OSError, UnicodeDecodeError):
                continue
            try:
                matches = _run_budgeted(
                    lambda: _scan_lines(rx, text), _DETECTOR_SEARCH_BUDGET_S)
            except _DetectorBudgetExceeded:
                continue
            for i, line in matches:
                findings.append({
                    "rule_id": rule.get("id"),
                    "file": f,
                    "line": i,
                    "match": line.strip()[:200],
                    "severity": rule.get("severity", "info"),
                })
    return findings


def run_shell_detectors(rules, changed_files, root=".") -> List[Dict[str, Any]]:
    """Run the shell-type mechanical detectors, trust-gated. Each fires ONLY when
    the repo is trusted (an explicit operator vet via hs-cli trust); base-verify
    is an integrity signal, NOT an authorizer (a hostile clone controls
    both the rule bytes and the in-tree manifest, so a self-attesting manifest
    cannot grant exec). Otherwise a `skipped` advisory finding records that it was
    dropped to grep-only. Never raises."""
    findings: List[Dict[str, Any]] = []
    # Snapshot the trust decision + exec cwd ONCE (TOCTOU): every shell in
    # this call execs under the same resolved root that was trust-checked. A
    # malformed root (None/non-path) yields no shell findings rather than raising
    # (the run() never-raises contract; fail-closed).
    try:
        repo_trusted = trust_store.is_trusted(root)
        safe_root = Path(os.path.realpath(root)) if repo_trusted else Path(root)
    except (TypeError, ValueError, OSError):
        return findings
    for rule in rules:
        det = rule.get("detector")
        if not isinstance(det, dict) or det.get("type") != "shell":
            continue
        cmd = det.get("cmd")
        if not isinstance(cmd, str) or not cmd.strip():
            continue
        scope = rule.get("scope") or []
        if not any(_scope_matches(scope, [f]) for f in changed_files):
            continue
        if not repo_trusted:
            findings.append({
                "rule_id": rule.get("id"), "file": None, "line": None,
                "match": "shell detector skipped: repo not trusted (hs-cli trust)",
                "severity": rule.get("severity", "info"), "skipped": True})
            continue
        res = _run_shell(cmd, cwd=safe_root)
        findings.append({
            "rule_id": rule.get("id"), "file": None, "line": None,
            "match": (res.get("stdout") or res.get("detail") or "").strip()[:200],
            "severity": rule.get("severity", "info"),
            "rc": res.get("rc"), "executed": res.get("executed", False)})
    return findings


def run(rules, changed_files, root=".") -> List[Dict[str, Any]]:
    """Run both detector kinds: grep (always) + shell (trust-gated). Advisory —
    returns findings, never raises, exit-0 semantics."""
    return (run_grep_detectors(rules, changed_files, root)
            + run_shell_detectors(rules, changed_files, root))


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(
        description="Run mechanical detectors (advisory; always exit 0).")
    ap.add_argument("--root", default=".")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args(argv)
    import rule_view
    loaded = rule_view.load_rules_from_tree(args.root, args.files)
    findings = run(loaded["rules"], args.files, root=args.root)
    print(json.dumps(findings, indent=2, ensure_ascii=False, default=str))
    return 0


if __name__ == "__main__":
    sys.exit(main())
