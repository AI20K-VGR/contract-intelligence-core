#!/usr/bin/env python3
"""shrink_failure.py — minimize a failing input to a 1-minimal reproducer (delta-debugging).

A multi-hundred-line repro is hard to reason about. Given the failing input and a test
command that exits 0 while the input STILL reproduces the failure ("interesting"),
this applies Zeller's ddmin to shrink the input to a 1-minimal subset — removing any
single remaining unit makes the failure disappear. Pairs with bisect_run.py (which
commit) and find_flaky.py (is it even deterministic) to round out the debug toolkit.

    shrink_failure.py <input_file> [--char] -- <test command that exits 0 if STILL failing>
    shrink_failure.py crash_input.txt -- ./repro.sh        # reduce by lines (default)
    shrink_failure.py payload.bin --char -- ./repro.sh     # reduce by characters

The command is re-run against <input_file> at each step (the script rewrites the file
to each candidate). The original is backed up to <input_file>.orig. CONFIRM the failure
is deterministic first (find_flaky.py) — a flaky oracle makes the search lie.

Exit: 0 = reduced (minimal left in <input_file>); 2 = usage / input does not reproduce.
"""
from __future__ import annotations

import os
import subprocess
import sys


def ddmin(items, is_interesting):
    """Return a 1-minimal sublist of `items` (order preserved) that still satisfies
    is_interesting. Zeller's delta-debugging, operating POSITIONALLY so duplicate
    values reduce correctly. Precondition: is_interesting(list(items)) is True."""
    items = list(items)
    n = 2
    while len(items) > 1:
        chunk_size = max(1, len(items) // n)
        chunks = [items[i:i + chunk_size] for i in range(0, len(items), chunk_size)]
        # 1) reduce to a single chunk (the failure lives entirely inside one slice)
        for c in chunks:
            if len(c) < len(items) and is_interesting(c):
                items, n = c, 2
                break
        else:
            # 2) remove one chunk at a time (the complement still reproduces)
            for i in range(len(chunks)):
                complement = [x for j, ch in enumerate(chunks) if j != i for x in ch]
                if complement and is_interesting(complement):
                    items, n = complement, max(n - 1, 2)
                    break
            else:
                if n >= len(items):
                    break  # already 1-minimal at the finest granularity
                n = min(len(items), 2 * n)
    return items


def _split(data: bytes, by_char: bool):
    """(units, joiner) where join(split(x)) == x EXACTLY — no newline added or dropped,
    no encoding round-trip. Operates on BYTES, so a binary or non-UTF8 input is never
    corrupted (and the minimal reproducer keeps the original's exact trailing newline)."""
    if by_char:
        return [data[i:i + 1] for i in range(len(data))], lambda us: b"".join(us)
    return data.split(b"\n"), lambda us: b"\n".join(us)


def parse_args(argv):
    """(<input_file>, by_char, <test command list>). Raises ValueError on a usage error."""
    by_char = False
    rest = list(argv)
    if "--char" in rest:
        by_char = True
        rest = [a for a in rest if a != "--char"]
    if not rest:
        raise ValueError("an <input_file> is required")
    input_file = rest[0]
    rest = rest[1:]
    if not rest or rest[0] != "--" or len(rest) < 2:
        raise ValueError("a test command is required after `--`")
    return input_file, by_char, rest[1:]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    try:
        input_file, by_char, cmd = parse_args(argv)
    except ValueError as e:
        print("usage: shrink_failure.py <input_file> [--char] -- <test command...>",
              file=sys.stderr)
        print("error: %s" % e, file=sys.stderr)
        return 2

    if not os.path.isfile(input_file):
        print("error: %r is not a file" % input_file, file=sys.stderr)
        return 2

    with open(input_file, "rb") as fh:
        original = fh.read()
    units, join = _split(original, by_char)

    # Create backup immediately, before any write mutates the input file.
    backup = input_file + ".orig"
    n = 1
    while os.path.exists(backup):
        backup = "%s.orig.%d" % (input_file, n)
        n += 1
    with open(backup, "wb") as fh:
        fh.write(original)

    def write(data: bytes):
        with open(input_file, "wb") as fh:
            fh.write(data)

    def is_interesting(candidate) -> bool:
        write(join(candidate))
        return subprocess.run(cmd, capture_output=True).returncode == 0

    # precondition: the FULL input must currently reproduce, or the search is meaningless
    if not is_interesting(units):
        write(original)  # restore — we changed nothing meaningful
        print("error: the input does not reproduce (the test command must exit 0 on the "
              "full input). Confirm the repro — and that it is not flaky — first.",
              file=sys.stderr)
        return 2

    # guard: the EMPTY input must NOT reproduce, else the failure is INDEPENDENT of the
    # file content (the command never reads it) and "reducing" would silently mislead.
    if is_interesting([]):
        write(original)
        print("error: the failure is independent of the input — the command exits 0 even "
              "on an EMPTY file, so it is not reading this input. Nothing to minimize.",
              file=sys.stderr)
        return 2

    minimal = ddmin(units, is_interesting)
    write(join(minimal))

    unit = "chars" if by_char else "lines"
    print("reduced %d -> %d %s (1-minimal under a deterministic oracle). "
          "Original saved to %s" % (len(units), len(minimal), unit, backup))
    return 0


if __name__ == "__main__":
    sys.exit(main())
