#!/usr/bin/env python3
"""register_store — shared primitives for append-only fenced-record registers
(the Decision Register `DEC-<n>` today; any future register reuses this).

One ruling per `---`-fenced YAML block. This module is the single home for the
structural machinery — the block-splitter regex, the record-fence/heading
injection escape, the best-effort file lock, and the raw id scan — so a fix
lands once. Register modules keep only their own specifics (field schema,
render template, alloc/append flow).

Lock posture: POSIX uses fcntl.flock. On platforms without it (or when flock
refuses) the lock degrades to a no-op BUT warns once per process: multiple
agents appending the same register concurrently on this machine can overwrite
each other's records. The warning informs — it never blocks the write; one
clone per developer (the deployment model) makes the race rare, and the
notebook files are typically written by the main agent at task end.
# TODO research: cross-platform lock (portalocker?) for Windows multi-agent
"""

import contextlib
import os
import re
import sys
from pathlib import Path
from typing import List


def atomic_write(path: Path, text: str) -> None:
    """Write `text` to `path` atomically AND durably so neither a concurrent reader
    nor a crash/power-loss ever sees a half-written or empty register. Delegates to
    artifact_io.atomic_write_text (same-dir .tmp fsync'd before os.replace + same-dev
    assert), preserving newline="" for literal newlines. Shared by the register
    writers (decision_register, backlog_register, glossary, cook/output config)."""
    import artifact_io
    artifact_io.atomic_write_text(path, text, newline="")

# Splits a register file into its `---`-fenced record blocks: each starts at a
# line-anchored `---` fence; `fm` = the YAML mini-frontmatter, `body` = prose.
RECORD_RE = re.compile(
    r"^---\s*\n(?P<fm>.*?)\n---\s*\n(?P<body>.*?)(?=^---\s*$|\Z)",
    re.DOTALL | re.MULTILINE,
)
# A body line that is a bare `---` fence would split the file into a phantom
# record under RECORD_RE; neutralized on write (see escape_injection).
INJ_FENCE_RE = re.compile(r"(?m)^(---+\s*)$")


def escape_injection(text, heading_re) -> str:
    """Backslash-escape record-fence + register-heading line anchors in
    caller-supplied MULTILINE prose (the rationale) so it cannot smuggle a
    phantom record or heading, while preserving the text (markdown-correct:
    `\\---`, `\\## ` render literally but no longer match the line-anchored
    patterns). `heading_re` is the register's own heading anchor."""
    out = INJ_FENCE_RE.sub(r"\\\1", text or "")
    return heading_re.sub(r"\\\1", out)


def sanitize_field(text, heading_re) -> str:
    """Neutralize injection in SINGLE-LINE fields (title, affects): collapse
    newlines to spaces — a one-line field has no legitimate line breaks, and
    without them no line-anchored fence/heading can form — then run the same
    escape for defense in depth."""
    flat = re.sub(r"[\r\n]+", " ", text or "").strip()
    return escape_injection(flat, heading_re)


_warned_degraded = False  # once-per-process guard for the degraded-lock warning


def _flock(fh, op) -> bool:
    """Try fcntl.flock; op is 'ex' (exclusive) or 'un' (unlock). True on
    success, False when fcntl is unavailable or the lock is refused."""
    try:
        import fcntl
        fcntl.flock(fh.fileno(), fcntl.LOCK_EX if op == "ex" else fcntl.LOCK_UN)
        return True
    except (ImportError, OSError):
        return False


def _warn_degraded() -> None:
    global _warned_degraded
    if _warned_degraded:
        return
    _warned_degraded = True
    sys.stderr.write(
        "[register_store] warning: file lock unavailable on this platform — "
        "multiple agents appending the same register concurrently on this "
        "machine may overwrite each other's records. Single-writer use is "
        "unaffected.\n"
    )


@contextlib.contextmanager
def register_lock(lock_path):
    """Best-effort exclusive lock so alloc-id + append happen as ONE critical
    section (closes the TOCTOU window where two looped allocs could collide).
    Degrades to a warn-once no-op where flock is unavailable — informs about
    the concurrent-overwrite risk, never blocks the write."""
    lock_path = Path(lock_path)
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    fh = open(lock_path, "w")
    locked = _flock(fh, "ex")
    if not locked:
        _warn_degraded()
    try:
        yield
    finally:
        if locked:
            try:
                _flock(fh, "un")
            except OSError:
                pass  # unlock is advisory; close must still happen
        fh.close()


def scan_record_ids(text: str) -> List[str]:
    """Every raw `id:` value across all `---`-fenced blocks, INCLUDING blocks
    whose YAML is otherwise unparseable — the source-of-truth for id allocation
    so a corrupt-but-id-bearing block still reserves its number (a later repair
    can never collide with an id allocated meanwhile)."""
    ids: List[str] = []
    for m in RECORD_RE.finditer(text):
        im = re.search(r"^id:\s*(\S+)\s*$", m.group("fm"), re.MULTILINE)
        if im:
            ids.append(im.group(1).strip())
    return ids
