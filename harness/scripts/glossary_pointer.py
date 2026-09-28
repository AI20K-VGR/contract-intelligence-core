#!/usr/bin/env python3
"""glossary_pointer — build the one-line session pointer at the glossary.

Read-only: counts the terms in the glossary SSOT (docs/glossary.yaml) and returns
a single advisory line reminding the session to consult the settled vocabulary
before naming things. Returns None when there is nothing useful to say (no SSOT,
or an empty/unreadable one) — the SessionStart hook turns None into a silent
continue. NEVER writes.

CLI:
    glossary_pointer.py --root <dir>     # print the pointer line (or nothing)
"""

import argparse
import sys
from pathlib import Path
from typing import Optional

sys.path.append(str(Path(__file__).resolve().parent))


def _yaml_path(root) -> Path:
    return Path(root) / "docs" / "glossary.yaml"


def count_terms(root) -> int:
    """Number of terms in the glossary SSOT (0 when absent/empty/unreadable —
    the read is fail-soft so a broken SSOT degrades to a silent pointer)."""
    try:
        import glossary_register
        # count_terms, not len(list_terms): the count is all this needs, and
        # list_terms parses the whole SSOT to build records nobody here reads
        # (44.06 ms vs 0.58 ms on the live file). See its docstring for the
        # structural invariant and the one limitation it accepts.
        return glossary_register.count_terms(root)
    except Exception:  # noqa: BLE001 — advisory: never raise on a read
        return 0


def build_pointer(root) -> Optional[str]:
    """One advisory line naming the term count + the read-before-naming rule, or
    None when the SSOT is absent or empty (nothing worth surfacing)."""
    if not _yaml_path(root).is_file():
        return None
    n = count_terms(root)
    if n <= 0:
        return None
    return ("glossary: %d settled term(s) — read docs/GLOSSARY.md (the view of "
            "docs/glossary.yaml) before naming a term/file/hook/prose, and "
            "respect its forbidden wording." % n)


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--root", default=".")
    args = ap.parse_args(argv)
    try:
        line = build_pointer(Path(args.root).resolve())
    except Exception:  # noqa: BLE001
        line = None
    if line:
        print(line)
    return 0


if __name__ == "__main__":
    sys.exit(main())
