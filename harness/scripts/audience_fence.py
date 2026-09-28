#!/usr/bin/env python3
"""audience_fence.py — on-demand advisory evidence-fence checker.

DETECTION ONLY: compares two report texts and asserts that evidence tokens are
identical across audience levels. This does NOT prove LLM behaviour — it catches
violations in artifact pairs that are compared after the fact. On-demand advisory
only: not a gate, not a CI blocker, not equivalent to humanize_dashes.py (which
post-processes dash characters); audience_fence checks evidence-token invariance
at low audience levels and exits non-zero only as an advisory signal.

API:
  extract_evidence(text) -> list[str]   extract all evidence tokens
  compare(text_a, text_b) -> list[str]  tokens in A but not B, or B but not A

CLI:
  python3 audience_fence.py a.md b.md
    exit 0  — evidence tokens identical
    exit 1  — diff printed, exit 1

Evidence token classes (five):
  1. file:line    e.g. harness/scripts/foo.py:42 or path/file.ext:123
  2. ID           e.g. DEC-123  F-12  P-5  (capital letter + digits, hyphen-separated)
  3. SHA (hex)    7–40 hex chars that appear as a standalone "word" token
  4. Numbers      standalone integers (not part of identifiers or shas)
  5. Backtick     tokens inside backticks `...`; also fenced code blocks ```...```
"""

import re
import sys
from pathlib import Path
from typing import List, Set


# --- Regex patterns ---

# file:line: a path token (slash-separated, no spaces) followed by colon + int
_RE_FILELINE = re.compile(
    r'(?<!\w)'                          # not preceded by a word char
    r'(?:[a-zA-Z0-9_\-./]+/'           # at least one directory segment
    r'[a-zA-Z0-9_\-.]+)'               # filename
    r':[0-9]+'                          # :line
    r'(?!\w)',
    re.ASCII,
)

# Structured IDs: uppercase letter(s) + hyphen + digits, optionally with more segments
# Matches DEC-123, F-12, P-5, RT-4, VL-3, etc.
_RE_ID = re.compile(r'\b[A-Z]{1,6}-[0-9]+(?:-[0-9A-Z]+)*\b')

# SHA: a sequence of 7–40 hex chars that reads as a standalone token
# Must be preceded and followed by a non-hex / non-word boundary.
# We require >= 7 chars to avoid matching small hex numbers used as values.
_RE_SHA = re.compile(r'(?<![0-9a-fA-F])([0-9a-fA-F]{7,40})(?![0-9a-fA-F])')

# Numbers: standalone integers not inside file:line or SHA contexts.
# Matched AFTER file:line and SHA so we don't double-count.
_RE_NUMBER = re.compile(r'(?<!\w)([0-9]+)(?!\w)')

# Backtick tokens: content inside single backticks `...` (non-greedy, no newline)
_RE_BACKTICK = re.compile(r'`([^`\n]+)`')

# Fenced code blocks: entire ```...``` block (multiline)
_RE_FENCE = re.compile(r'```.*?```', re.DOTALL)


def extract_evidence(text: str) -> List[str]:
    """Extract all evidence tokens from a report text.

    Returns a list (may contain duplicates — use set() for equality checks).
    Preserves token strings verbatim for comparison.

    Token classes (processed in order to avoid double-counting):
      1. Fenced code blocks (```...```) as a unit
      2. file:line anchors
      3. Structured IDs (DEC-N, F-N, etc.)
      4. SHAs (7-40 hex, standalone)
      5. Backtick-quoted tokens
      6. Standalone numbers (after the above are removed to avoid overlap)
    """
    tokens: List[str] = []
    consumed: Set[int] = set()  # character positions already claimed

    def _add(match, value):
        start, end = match.span()
        if any(i in consumed for i in range(start, end)):
            return  # overlaps a higher-priority match
        for i in range(start, end):
            consumed.add(i)
        tokens.append(value)

    # 1. Fenced code blocks — treat the whole block as one token
    for m in _RE_FENCE.finditer(text):
        # Normalize whitespace inside block for comparison stability
        block = re.sub(r'\s+', ' ', m.group().strip())
        _add(m, block)

    # 2. file:line
    for m in _RE_FILELINE.finditer(text):
        _add(m, m.group())

    # 3. Structured IDs
    for m in _RE_ID.finditer(text):
        _add(m, m.group())

    # 4. SHAs (7-40 hex, standalone)
    for m in _RE_SHA.finditer(text):
        val = m.group(1)
        # Exclude pure-numeric sequences already captured as numbers later,
        # and short 1-6 char sequences (too noisy). Already enforced by {7,40}.
        _add(m, val)

    # 5. Backtick tokens
    for m in _RE_BACKTICK.finditer(text):
        _add(m, m.group(1).strip())

    # 6. Standalone numbers (after all other tokens consumed their chars)
    for m in _RE_NUMBER.finditer(text):
        _add(m, m.group(1))

    return tokens


def compare(text_a: str, text_b: str) -> List[str]:
    """Return evidence tokens present in one text but not the other.

    Returns a list of diff lines (empty list = no diff = evidence is identical).
    Uses set comparison so order and count differences inside one report don't
    trigger a false positive (the fence cares about presence, not multiplicity).
    """
    set_a = set(extract_evidence(text_a))
    set_b = set(extract_evidence(text_b))
    diff = []
    for tok in sorted(set_a - set_b):
        diff.append("MISSING from B: %r" % tok)
    for tok in sorted(set_b - set_a):
        diff.append("MISSING from A: %r" % tok)
    return diff


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(
        description=(
            "Evidence-fence checker: compare two reports for identical evidence tokens. "
            "Exit 0 = identical; exit 1 = diff printed. "
            "DETECTION only — does not prove LLM behaviour."
        )
    )
    ap.add_argument("report_a", help="First report (e.g. audience=0 variant)")
    ap.add_argument("report_b", help="Second report (e.g. audience=5 variant)")
    args = ap.parse_args(argv)

    pa = Path(args.report_a)
    pb = Path(args.report_b)
    try:
        text_a = pa.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write("Cannot read %s: %s\n" % (pa, e))
        return 2
    try:
        text_b = pb.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as e:
        sys.stderr.write("Cannot read %s: %s\n" % (pb, e))
        return 2

    diff = compare(text_a, text_b)
    if not diff:
        return 0
    print("Evidence token diff between %s and %s:" % (pa, pb))
    for line in diff:
        print("  " + line)
    return 1


if __name__ == "__main__":
    sys.exit(main())
