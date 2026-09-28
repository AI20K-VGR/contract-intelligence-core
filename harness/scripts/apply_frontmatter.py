#!/usr/bin/env python3
"""apply_frontmatter.py — RETIRED: fields removed per standardization (S2).

This script used to auto-fill `category`/`license`/`keywords` on any SKILL.md
that lacked them. Those three fields were retired as part of the S1/S2
frontmatter standardization pass: they had no real consumer and only cost
listing-budget weight. `harness/schemas/skill-schema.json` no longer declares
them, so this script must NOT regenerate them on any skill, ever.

Kept as a no-op stub (not deleted) so existing imports/tooling referencing
this module path do not break. `main()` never reads or writes a SKILL.md;
it only reports that the rollout is retired.

Usage:
    python3 harness/scripts/apply_frontmatter.py [--root .] [--dry-run]
"""

import argparse
import sys


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--root", default=".")
    ap.add_argument("--dry-run", action="store_true")
    ap.parse_args(argv)
    print("apply_frontmatter: retired — category/license/keywords are no longer "
          "auto-filled (dead fields, see harness/schemas/skill-schema.json). "
          "0 skill(s) changed.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
