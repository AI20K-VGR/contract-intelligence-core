#!/usr/bin/env python3
"""config_io.py — shared helpers for the YAML config WRITE CLIs.

The guard / team / output `--set` writers each rewrite their YAML programmatically
and must preserve the file's leading comment header (the shipped doc-comment plus
any hand notes). That extraction lived copy-pasted in three modules; this is its
one home so the writers cannot drift.
"""

from pathlib import Path


def leading_comment_block(path, default: str) -> str:
    """The leading run of comment/blank lines from ``path``, returned verbatim so
    a CLI rewrite keeps the header. Stops at the first non-comment, non-blank
    line. A missing file → ``default`` (the caller's minimal header); a file with
    no leading comments → empty string."""
    try:
        lines = Path(path).read_text(encoding="utf-8").splitlines()
    except FileNotFoundError:
        return default
    head = []
    for ln in lines:
        if ln.strip() == "" or ln.lstrip().startswith("#"):
            head.append(ln)
        else:
            break
    return ("\n".join(head) + "\n") if head else ""
