#!/usr/bin/env python3
"""find_flaky.py — confirm and quantify a flaky test by re-running it in isolation.

A test that fails intermittently must NOT be bisected (the search oracle lies) and
must not be "fixed" off a single red run. Run the target N times and report the
pass/fail split + a verdict: STABLE_PASS (all pass), STABLE_FAIL (all fail), or
FLAKY (mixed — the pass rate is the flakiness). Exit 1 on FLAKY so a CI step or
hs:debug can gate on it before spending effort on the wrong cause.

    find_flaky.py <target_node_id> [-n 20] [-- <extra pytest args>]
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from find_polluter import _passed_from_output  # noqa: E402 — shared pass/fail oracle


def classify(passes: int, total: int) -> str:
    """Verdict from a pass-count over `total` runs. Pure — unit-tested directly."""
    if total <= 0:
        return "NONE"
    if passes == total:
        return "STABLE_PASS"
    if passes == 0:
        return "STABLE_FAIL"
    return "FLAKY"


def _run_once(target, extra):
    """(target_passed, target_ran). target_ran is False when pytest collected no
    matching test (exit 4/5) -- a mistyped / never-run node-id, NOT a failure."""
    args = [sys.executable, "-m", "pytest", "-q", "-p", "no:randomly",
            "--tb=no", "-rA", *extra, target]
    res = subprocess.run(args, capture_output=True, text=True)
    passed = _passed_from_output(res.stdout + "\n" + res.stderr, target)
    return passed, res.returncode not in (4, 5)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if not argv:
        print("usage: find_flaky.py <target_node_id> [-n N] [-- <pytest args>]",
              file=sys.stderr)
        return 2
    target = argv[0]
    rest = argv[1:]
    n = 20
    if rest and rest[0] == "-n":
        if len(rest) < 2:
            print("-n needs an integer", file=sys.stderr)
            return 2
        try:
            n = max(1, int(rest[1]))
        except ValueError:
            print("-n needs an integer", file=sys.stderr)
            return 2
        rest = rest[2:]
    extra = rest[1:] if rest and rest[0] == "--" else rest
    first_passed, ran = _run_once(target, extra)
    if not ran:
        print("%r matched no test (mistyped node-id?)" % target, file=sys.stderr)
        return 2
    passes = int(first_passed) + sum(int(_run_once(target, extra)[0])
                                     for _ in range(n - 1))
    verdict = classify(passes, n)
    print("%s: %d/%d passed over %d runs" % (verdict, passes, n, n))
    if verdict == "FLAKY":
        print("  -> %r is FLAKY (%.0f%% pass). Do NOT bisect or 'fix' off one run; "
              "stabilize it first." % (target, 100.0 * passes / n))
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
