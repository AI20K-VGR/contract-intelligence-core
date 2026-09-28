"""humanize_dashes.py — deterministic em/en-dash remover for generated reports.

The humanizer rule bans em (—) and en (–) dashes from human-facing prose because
they are an AI-writing tell. Stripping them is mechanical, so an LLM should never
hand-rewrite them: this script does it deterministically and reproducibly.

It is the OPT-IN, mechanical half of the humanizer pass. Per the harness policy,
the dash ban is advisory for internal reports and only applied when a report is
published externally or the user asks; run this then, instead of editing by hand.

Scope (intentionally conservative — it must never corrupt evidence):
  - Only `—` (U+2014) and `–` (U+2013) are touched. ASCII hyphens, double hyphens
    (`--`, `---`: markdown rules, tables, front-matter, CLI flags) and arrows
    (`->`, `→`, `=>`) are left alone — they are not the tell and rewriting them
    breaks code.
  - Fenced code blocks (```), and inline code spans (`...`) survive verbatim: a
    dash inside them is a citation, not prose.
  - A dash between word characters with no surrounding space is a range
    (`3–5`, `W0–W3`) and becomes an ASCII hyphen (`3-5`), not the chosen
    punctuation.
  - A line-leading spaced dash (only indentation before it) is a list bullet /
    leading separator, not an aside, so it survives verbatim; collapsing it would
    eat the line's first character and corrupt the markdown.
  - Every other em/en dash, with its surrounding whitespace, collapses to the
    chosen punctuation (default a comma — always grammatical, including the
    parenthetical `A — aside — B` case).

Contract (mirrors the other report scripts):
  - Default is a DRY-RUN: it reports what would change on stdout (JSON) and never
    writes. Only `--fix` rewrites the file, and only when something changed.
  - Always exits 0. It is a fixer, not a gate.
  - Picking the replacement punctuation is the one non-mechanical choice; the
    default is a comma and `--replacement {comma,colon,period}` overrides it. The
    changed line numbers are reported so a writer can hand-polish the few spots
    that wanted a colon.
"""
import argparse
import json
import re
import sys
from pathlib import Path

# Punctuation a spaced dash collapses to. Each carries its own trailing space so
# the dash plus its surrounding whitespace becomes exactly one separator.
REPLACEMENTS = {"comma": ", ", "colon": ": ", "period": ". "}

# A dash flanked by word chars with no spaces is a range → ASCII hyphen.
_RANGE_RE = re.compile(r"(\w)[–—](\w)")
# Any remaining em/en dash, with whitespace on either side, collapses to one separator.
_DASH_RE = re.compile(r"\s*[–—]\s*")
# A line-leading spaced dash: the dash sits at the start of the line (only
# optional indentation before it). It is a list bullet / leading separator, not a
# mid-sentence aside — collapsing it would eat the line's opening character and
# corrupt the markdown, so it is left verbatim and only MID-line dashes convert.
_LEADING_DASH_RE = re.compile(r"^\s*[–—]\s*")
# Inline code span; its body is preserved verbatim.
_CODE_SPAN_RE = re.compile(r"`[^`]*`")


def _transform_segment(seg: str, repl: str, at_line_start: bool) -> str:
    """Apply the dash rules to a stretch of prose (no inline code inside).

    When `at_line_start` is True this segment opens its line, so a dash at the
    very start is line-leading and must survive untouched; the conversion picks
    up only after that leading run.
    """
    seg = _RANGE_RE.sub(r"\1-\2", seg)
    offset = 0
    if at_line_start:
        lead = _LEADING_DASH_RE.match(seg)
        if lead:
            offset = lead.end()  # keep the line-leading dash verbatim
    return seg[:offset] + _DASH_RE.sub(repl, seg[offset:])


def _transform_line(line: str, repl: str) -> str:
    """Transform a line, leaving inline `code` spans untouched."""
    out = []
    last = 0
    for m in _CODE_SPAN_RE.finditer(line):
        out.append(_transform_segment(line[last:m.start()], repl, last == 0))
        out.append(m.group(0))  # code span verbatim
        last = m.end()
    out.append(_transform_segment(line[last:], repl, last == 0))
    return "".join(out)


def humanize_text(text: str, replacement: str = "comma"):
    """Return (new_text, changed_line_numbers).

    Lines inside a fenced code block (``` or ~~~) and the fence markers
    themselves pass through unchanged; a fence closes only on its own marker.
    Splitting and rejoining on "\\n" preserves the trailing newline.
    """
    repl = REPLACEMENTS[replacement]
    lines = text.split("\n")
    out = []
    changes = []
    fence_marker = None  # "```" or "~~~" while inside a fence, else None
    for i, line in enumerate(lines, start=1):
        stripped = line.lstrip()
        if fence_marker is None and (stripped.startswith("```")
                                     or stripped.startswith("~~~")):
            fence_marker = stripped[:3]
            out.append(line)
            continue
        if fence_marker is not None:
            # A fence CLOSES only on a bare marker line: a run of the fence char
            # (at least the opener's length, here 3) with no info-string, ignoring
            # trailing whitespace. An open may carry an info-string (```python),
            # so "starts with the marker" is too loose — it would misread such a
            # body line as a close, desync the in/out-of-code state, and let
            # dashes inside the block get rewritten.
            bare = stripped.rstrip()
            if bare == fence_marker[0] * len(bare) and len(bare) >= len(fence_marker):
                fence_marker = None
            out.append(line)
            continue
        new = _transform_line(line, repl)
        if new != line:
            changes.append(i)
        out.append(new)
    return "\n".join(out), changes


def process_file(path: str, fix: bool = False, replacement: str = "comma") -> dict:
    """Humanize one file. Dry-run by default; writes only with fix=True and a change."""
    p = Path(path)
    if not p.is_file():
        return {"tool": "humanize_dashes", "path": str(path),
                "skipped": "not a file", "fixed": False, "count": 0, "changes": []}
    try:
        text = p.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        return {"tool": "humanize_dashes", "path": str(path),
                "skipped": "unreadable: %s" % exc.__class__.__name__,
                "fixed": False, "count": 0, "changes": []}

    new_text, changes = humanize_text(text, replacement)
    fixed = False
    if fix and new_text != text:
        p.write_text(new_text, encoding="utf-8")
        fixed = True
    return {
        "tool": "humanize_dashes",
        "path": str(path),
        "replacement": replacement,
        "fixed": fixed,
        "count": len(changes),
        "changes": changes,
    }


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Deterministic em/en-dash remover for reports (opt-in).")
    ap.add_argument("path", help="report file to humanize")
    ap.add_argument("--fix", action="store_true",
                    help="rewrite the file in place (default: dry-run, report only)")
    ap.add_argument("--replacement", choices=sorted(REPLACEMENTS), default="comma",
                    help="punctuation that replaces a spaced dash (default: comma)")
    args = ap.parse_args(argv)
    result = process_file(args.path, fix=args.fix, replacement=args.replacement)
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0  # a fixer, never a gate


if __name__ == "__main__":
    sys.exit(main())
