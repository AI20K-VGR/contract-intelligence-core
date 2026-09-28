#!/usr/bin/env python3
"""_harden_bin.py — opt-in OS-level read-only hardening of the shared binary.

write_guard blocks the agent's TOOL writes into ${bin}, but it is blind to a
Bash `cp`/`sed -i` into the bin (the honest F3 residual). The real fence for a
shared binary is OS read-only permissions to the runtime user. This step is
OPT-IN (`--harden-bin`, default OFF): forcing it would block a dev editing the
harness during dogfood, and a recipient who only consumes the binary wants it.

Removes the write bits (u/g/o -w) from every file under ${bin} — read + execute
survive so hooks still run. Reversible with a normal `chmod -R u+w`.
"""
import os
import stat
from pathlib import Path


def harden_bin(bin_root, *, dry_run: bool = False) -> int:
    """Strip the write bits from every regular file + dir under `bin_root`.
    Returns the count of paths that would change. Dry-run changes nothing."""
    root = Path(bin_root)
    changed = 0
    for dirpath, dirnames, filenames in os.walk(root):
        for name in list(dirnames) + filenames:
            p = Path(dirpath) / name
            try:
                mode = os.stat(p).st_mode
            except OSError:
                continue
            if mode & 0o222:  # any write bit set
                changed += 1
                if not dry_run:
                    os.chmod(p, mode & ~0o222 & 0o7777)
    return changed
