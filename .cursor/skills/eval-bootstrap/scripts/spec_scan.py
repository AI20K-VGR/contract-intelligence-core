#!/usr/bin/env python3
"""spec_scan.py — OPTIONAL R10b helper: list candidate independent-spec docs.

R10b (sealed-room re-derivation) needs an "exam question" the answer key was
NOT derived from — a requirement/AC/DEC/ADR/README that states what the code is
SUPPOSED to do. This helper scans the target repo for files whose NAME looks
like such a spec and prints the candidates so the main agent can ask the user
which one is authoritative.

It deliberately does the least possible: it LISTS candidate paths by filename
pattern. It never reads a doc's contents, never ranks them, and never decides
which is the real spec — that judgment is the user's (deciding it by machine
would re-introduce the exact self-grading trap R10b breaks). LOUD when nothing
matches: it says so, never a silent empty pass.

Stdlib only; never imports harness/scripts/ — self-contained like the rest of
this skill.
"""

from __future__ import annotations

import argparse
import os
import sys

from pathlib import Path

# Filename stems that usually name an independent spec (case-insensitive
# substring match on the file's stem). Deliberately about the NAME only — the
# helper never opens the file to judge its contents.
_SPEC_STEMS = (
    "decision", "requirement", "acceptance", "criteria", "spec",
    "adr", "readme", "prd", "brd", "story", "rfc", "design", "contract",
)

# Directories that never hold a hand-authored spec — skip them so a vendored
# README or a build artifact does not masquerade as the exam question.
_SKIP_DIRS = {".git", "node_modules", "__pycache__", "venv", ".venv", "dist",
              "build", "site-packages", "evals", ".claude", "target"}


def find_candidates(target: Path):
    """Walk the repo with os.walk so skip-dirs are PRUNED before descending
    (never buffering node_modules/.git) and an unreadable dir is skipped
    gracefully rather than crashing the scan."""
    candidates = []
    for dirpath, dirnames, filenames in os.walk(str(target), onerror=lambda e: None):
        # prune skip-dirs IN PLACE so os.walk never descends into them
        dirnames[:] = [d for d in dirnames if d not in _SKIP_DIRS]
        for name in filenames:
            p = Path(dirpath) / name
            # allow the doc extensions AND extensionless files (a bare README /
            # DESIGN is a common spec) -- the stem filter below still gates it.
            if p.suffix.lower() not in (".md", ".rst", ".txt", ".adoc", ""):
                continue
            if any(marker in p.stem.lower() for marker in _SPEC_STEMS):
                candidates.append(p.relative_to(target))
    return sorted(candidates)


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(
        description="List candidate independent-spec docs for R10b (lists only; "
                    "never reads contents, never decides which is authoritative).")
    parser.add_argument("--target", required=True, help="repo root to scan")
    args = parser.parse_args(argv)

    target = Path(args.target)
    candidates = find_candidates(target)

    if not candidates:
        print("no spec candidate docs found by name under %s — R10b has no "
              "independent exam question to use; fall back to a human-approved "
              "derived-spec (confidence LOW)." % target)
        return 0

    print("spec candidates (the USER picks which is authoritative — this list "
          "is by filename only, NOT a judgment):")
    for rel in candidates:
        print("  - %s" % rel)
    return 0


if __name__ == "__main__":
    sys.exit(main())
