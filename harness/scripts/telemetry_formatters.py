"""telemetry_formatters.py — output formatting: markdown tables and JSON.

Ported verbatim (framework-agnostic) from the source corpus formatters for the
telemetry lenses. No skill-id dependency, stdlib only. Handles Vietnamese
display-width (NFC + East-Asian width) so VI narration tables align in a terminal.
"""
import json
import sys
import unicodedata
from typing import Optional

_MIN_SEP = 3  # GFM needs at least 3 dashes per column separator cell


def _disp_width(s: str) -> int:
    """Terminal display width of a string. NFC-normalizes first so Vietnamese
    diacritics (often authored as NFD base+combining) count as one cell, and
    treats East-Asian wide/fullwidth glyphs as two cells, combining marks as zero."""
    s = unicodedata.normalize("NFC", str(s))
    w = 0
    for ch in s:
        if unicodedata.combining(ch):
            continue
        w += 2 if unicodedata.east_asian_width(ch) in ("W", "F") else 1
    return w


def _pad(s: str, width: int) -> str:
    """Left-justify by DISPLAY width (str.ljust pads by code points → misaligns)."""
    s = str(s)
    return s + " " * max(0, width - _disp_width(s))


def _cell(s) -> str:
    """A cell rendered safe for a GFM table: a literal pipe is escaped and any newline
    folded to a space, so cell content can never inject an extra column or row."""
    return str(s).replace("|", "\\|").replace("\r", " ").replace("\n", " ")


def markdown_table(headers: list, rows: list, align: Optional[list] = None) -> str:
    """Generate a markdown table. align: list of 'l', 'r', 'c' per column. Cells are
    escaped (pipe/newline) and rows of any arity are normalized — a short row is padded,
    a wider row widens the table — so the output is always valid GFM whatever the cells
    contain (current lenses feed fixed-arity structured rows; this keeps a future
    free-form-text lens from corrupting the render)."""
    headers = [_cell(h) for h in headers]
    ncols = max(len(headers), max((len(r) for r in rows), default=0))
    headers = headers + [""] * (ncols - len(headers))
    if not rows:
        return "| %s |\n| %s |\n| _(empty)_ |" % (
            " | ".join(headers), " | ".join(["---"] * ncols))

    def cell(r, i):
        return _cell(r[i]) if i < len(r) else ""

    widths = [max(_disp_width(headers[i]),
                  max((_disp_width(cell(r, i)) for r in rows), default=0))
              for i in range(ncols)]
    sep = []
    for i, w in enumerate(widths):
        a = (align[i] if align and i < len(align) else "l")
        if a == "r":
            sep.append("-" * max(_MIN_SEP - 1, w - 1) + ":")
        elif a == "c":
            sep.append(":" + "-" * max(_MIN_SEP - 2, w - 2) + ":")
        else:
            sep.append("-" * max(_MIN_SEP, w))
    lines = [
        "| " + " | ".join(_pad(headers[i], widths[i]) for i in range(ncols)) + " |",
        "| " + " | ".join(sep) + " |",
    ]
    for row in rows:
        lines.append("| " + " | ".join(_pad(cell(row, i), widths[i]) for i in range(ncols)) + " |")
    return "\n".join(lines)


def json_output(data, pretty: bool = True) -> str:
    """Format data as JSON string."""
    return json.dumps(data, ensure_ascii=False, indent=2 if pretty else None, default=str)


def eprint(*args, **kwargs):
    """Print to stderr."""
    print(*args, file=sys.stderr, **kwargs)
