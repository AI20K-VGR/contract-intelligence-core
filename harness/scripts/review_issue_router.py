#!/usr/bin/env python3
"""review_issue_router.py — classify a code-review finding category into a handling route.

Routes:
  needs-user  — finding touches a user decision (contract/threshold/scope/schema/
                pricing/compliance/trade-off); do NOT auto-fix; escalate to human.
  auto-fix    — finding is a clear correctness/quality issue; drive hs:fix TDD.

Unknown categories default to "needs-user" (safe default: when in doubt, escalate;
never auto-fix what we cannot recognise).

Usage (debug / skill invocation):
  python3 harness/scripts/review_issue_router.py --category schema
"""

NEEDS_USER: frozenset = frozenset({
    "contract",
    "threshold",
    "scope",
    "schema",
    "pricing",
    "compliance",
    "trade-off",
})

AUTO_FIX: frozenset = frozenset({
    "correctness",
    "bug",
    "dry",
    "cleanup",
    "consistency",
    "security",
    "robustness",
    "edge",
    "test-quality",
})


def classify_finding(category: str) -> str:
    """Return "needs-user" or "auto-fix" for the given category string.

    Input is normalised (lower + strip) before lookup. Any category not in either
    set returns "needs-user" — the safe default prevents silent auto-fixes on
    unrecognised categories.

    Pure function: no I/O, no side-effects, deterministic.
    """
    normalised = category.lower().strip()
    if normalised in AUTO_FIX:
        return "auto-fix"
    # NEEDS_USER members and everything unrecognised both route to needs-user.
    return "needs-user"


def main(argv=None) -> int:
    import argparse
    import sys

    ap = argparse.ArgumentParser(
        description="classify a review finding category → needs-user | auto-fix")
    ap.add_argument(
        "--category", required=True,
        help="finding category to classify (e.g. schema, correctness, trade-off)")
    args = ap.parse_args(argv)
    route = classify_finding(args.category)
    print(route)
    return 0


if __name__ == "__main__":
    import sys
    sys.exit(main())
