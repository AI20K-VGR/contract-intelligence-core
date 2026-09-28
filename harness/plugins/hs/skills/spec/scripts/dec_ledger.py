#!/usr/bin/env python3
"""dec_ledger.py — per-workspace DEC ledger allocator for hs:spec.

Ledger file: ``<root>/docs/product/decisions.md`` — a hand-maintained markdown
file, one ``---``-fenced YAML frontmatter block (id/status/date/actor/ts/affects)
per DEC, followed by a ``## DEC-<n>`` heading and prose. Append-only: prior bytes
are never rewritten, only appended to.

Allocation rule: new id = max existing id + 1, where the existing ids are EVERY
``DEC-<n>`` token found anywhere in the ledger text (a heading, a frontmatter
``id:``, or even a body reference). This widest-possible scan is deliberate: a
collision only comes from UNDER-counting the max, so no heading style a hand
edit might use (indented, tab-prefixed, setext, comment-wrapped, italic
``_DEC-<n>_``, or an id carried only in frontmatter) can hide a live id.
``max + 1`` is strictly greater than every existing id, so a fresh allocation
can NEVER collide — a pre-existing hand-edit duplicate does not block a new
``--add`` (the old whole-ledger uniq gate bricked every future alloc on a corrupt
ledger). The only cost is that a body quoting a DEC number ABOVE the current max
nudges the counter to a gap; ``_render_block`` defuses tool-written title/body
tokens so that only happens on a hand edit, and gaps are allowed. Gaps are NOT filled.

Race-safety: the whole critical section {read max -> allocate -> append} runs
under an exclusive ``fcntl.flock`` held on a sibling
``<root>/docs/product/.decisions.lock`` file (created if absent). flock is
advisory POSIX and only serializes cooperating callers on the same machine —
see references/dec-ledger.md for the Linux-only assumption this rests on.

This module is scoped to the per-workspace *product* ledger only. It does
**not** import or call the harness's own architecture register script (see
references/dec-ledger.md for its file name), and does **not** use that
script's atomic-allocation CLI flag: that allocator is built for a
tool-managed YAML SSOT and double-allocates when pointed at a hand-maintained
markdown ledger (the exact bug this module exists to avoid — see
references/dec-ledger.md for the two-ledger split).
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import getpass
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Union

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0): this skill directory may shadow a harness/scripts name
# with its own copy (see harness/tests/_spec_skill_import.py's docstring).
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

sys.path.insert(0, str(Path(__file__).resolve().parent))
from id_grammar import DEC_ID_PATTERN  # noqa: E402
from encoding_utils import write_text_atomic  # noqa: E402

RootLike = Union[str, Path]

# Ids are token-scanned from every markdown heading line: a heading is the id
# location BOTH tool-written and legacy heading-only entries carry. Matching
# every `DEC-<n>` token ON a heading line (rather than a single anchored group)
# means a combined `## DEC-<j> & DEC-<k>` or a decorated `## ~~DEC-<k>~~` heading is
# counted in full, so the max is never undercounted into a live-id collision.
# The `#`-prefix is matched with or without a following space so a hand-typo
# heading (`##DEC-<k>`) is still counted (a false match on a `#comment` body line
# is harmless — it carries no DEC token). Over-count is a harmless gap;
# under-count is the collision this must never allow.
#
# A heading line that carries a DEC id — used to anchor frontmatter parsing to
# its own entry (so a stray `---` thematic break in a body cannot desync the
# block pairing). Same lookaround boundary as `_existing_ids` below, not `\b`:
# `\b` treats `_` as a word char, so it misses an emphasis-wrapped
# `## _DEC-<n>_ — Title` heading (no word/non-word transition between `_` and
# `D`) — that block would then read as `followed_by_heading=False` and get
# silently dropped from `_parse_blocks`/`list_decisions`. Up to 3 leading
# spaces are tolerated before the `#` because CommonMark treats an ATX heading
# indented 0–3 spaces as still a valid heading (4+ is a code block) — a
# linter/copy-paste that indents a real DEC heading must not make that
# decision invisible to `list_decisions()` while `_existing_ids` still counts
# it.
_HEADING_WITH_DEC_RE = re.compile(r"^ {0,3}#{1,6}.*(?<![A-Za-z0-9])DEC-[0-9]+(?![0-9])")
_FENCE_LINE_RE = re.compile(r"^---[ \t]*$")

# A body line that would be mis-read as a structural marker by `_parse_blocks`:
# a markdown heading (`## DEC-<k>`) or a `---`/`...` fence. `_render_block`
# defuses these before writing so a decision body that quotes an example heading
# or a sample frontmatter block is never mis-listed as its own entry.
_BODY_STRUCTURAL_LINE_RE = re.compile(
    r"^( {0,3}#{1,6}\s|---\s*$|\.\.\.\s*$|id:[ \t]*DEC-[0-9])"
)


def _decisions_path(root: RootLike) -> Path:
    return Path(root) / "docs" / "product" / "decisions.md"


def _lock_path(root: RootLike) -> Path:
    return Path(root) / "docs" / "product" / ".decisions.lock"


def _ensure_ledger(path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    if not path.exists():
        # Atomic create (temp + os.replace) so a lock-free reader (list_decisions
        # / session_staleness) never catches the ledger transiently empty during
        # this one-time creation.
        write_text_atomic(path, "# Decision Register\n")


def _parse_blocks(text: str) -> List[Dict[str, str]]:
    """Parse each ``---``-fenced frontmatter block into a flat dict via real
    YAML parsing — not a naive ``key.partition(":")`` line-split. A value
    ``_render_block`` had to quote (e.g. ``date: '2026-07-13'``, forced by
    ``yaml.safe_dump`` so the string never collides with YAML's implicit
    date/timestamp type) must round-trip back to the clean string every
    caller expects, and a hand-edited block's bare (unquoted) date/timestamp
    auto-resolves to a ``datetime.date``/``datetime.datetime`` under the same
    implicit resolver either way — every value is coerced to ``str`` so
    ``list_decisions`` keeps its ``Dict[str, str]`` contract regardless of
    which shape produced it.

    Read-only helper (no lock): callers that need a linearizable read while a
    writer may be mid-append should take their own flock via ``_lock_path``.
    """
    # Line-based scan rather than a greedy multi-block regex: a `---` thematic
    # break inside a decision body would otherwise desync `---`-pair matching and
    # silently drop real entries (a live bug — the in-repo ledger has body `---`
    # rules). A `---`...`---` block is accepted as an entry's frontmatter ONLY
    # when it parses to a mapping with a valid DEC `id:` AND is immediately
    # followed (blank lines allowed) by that entry's `## DEC-` heading; anything
    # else (a body thematic break, a fenced code sample) is skipped by advancing
    # past just the opening fence so it cannot swallow the next real block.
    lines = text.split("\n")
    n = len(lines)
    blocks: List[Dict[str, str]] = []
    i = 0
    while i < n:
        if not _FENCE_LINE_RE.match(lines[i]):
            i += 1
            continue
        j = i + 1
        while j < n and not _FENCE_LINE_RE.match(lines[j]):
            j += 1
        if j >= n:  # no closing fence — not a block
            break
        try:
            raw = yaml_io.safe_load("\n".join(lines[i + 1:j]))
        except Exception:  # noqa: BLE001 — deliberate fail-soft
            # A hand-edited block must never crash a read: PyYAML raises a whole
            # family (bare ValueError on `date: 2026-13-99`, bare AttributeError
            # on `!!timestamp 'not a ts'`), not just yaml_io.YAMLError.
            raw = None
        k = j + 1
        while k < n and lines[k].strip() == "":
            k += 1
        followed_by_heading = k < n and _HEADING_WITH_DEC_RE.match(lines[k]) is not None
        if (isinstance(raw, dict)
                and DEC_ID_PATTERN.match(str(raw.get("id", "")))
                and followed_by_heading):
            blocks.append({str(key): ("" if v is None else str(v)) for key, v in raw.items()})
            i = j + 1
        else:
            # Not a real DEC frontmatter — advance past ONLY the opening fence so
            # a lone body `---` does not consume the next entry's real fence.
            i += 1
    return blocks


def _existing_ids(text: str) -> List[str]:
    """Every ``DEC-<n>`` token anywhere in the ledger — the widest possible read
    so the allocation max can NEVER be under-counted.

    The one invariant this allocator must hold is "never re-hand-out a live id".
    A collision comes only from UNDER-counting the max; an OVER-count is a
    harmless gap (gaps are allowed). Scanning every token — not just col-0
    ``## DEC-<n>`` headings or frontmatter ``id:`` lines — means no heading style
    a hand edit might use (indented, tab-prefixed, setext, comment-wrapped, an
    emphasis-wrapped ``_DEC-<n>_``, or an id carried only in frontmatter) can hide
    an id and let ``max + 1`` re-hit it. The boundary is ``(?<![A-Za-z0-9])`` /
    ``(?![0-9])`` rather than ``\b``: ``\b`` treats ``_`` as a word char and would
    miss an italic ``## _DEC-<k>_`` — this boundary still counts an ``_``-adjacent
    id (over-count = safe gap) while never splitting ``DEC-<k><d>`` into ``DEC-<k>``.
    The cost is only that a body that quotes a DEC number HIGHER than the current
    max nudges the counter forward to a gap — which is why ``_render_block``
    still defuses tool-written body/title tokens (the common case), and why a
    real ledger of prior-referencing bodies is unaffected (verified: the in-repo
    115 KB ledger scans to a max with no body token above it, so next = max + 1)."""
    return [m.group(1) for m in re.finditer(r"(?<![A-Za-z0-9])(DEC-[0-9]+)(?![0-9])", text)
            if DEC_ID_PATTERN.match(m.group(1))]


def _max_id_num(ids: Sequence[str]) -> int:
    nums = [int(i.split("-", 1)[1]) for i in ids]
    return max(nums) if nums else 0


def _default_actor() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _render_block(
    dec_id: str, status: str, date: str, actor: str, ts: str,
    affects: Sequence[str], title: str, body: str,
) -> str:
    """Render one appendable ``---``-fenced DEC block.

    The frontmatter is built as a dict and serialized via ``yaml.safe_dump`` —
    never raw ``%``-interpolation — so a caller-supplied value (``actor``,
    ``status``, an ``affects`` entry) that happens to contain a colon, a
    newline, or a ``---``-looking line can never prematurely close the fence
    or forge a second frontmatter block; safe_dump quotes/escapes it as an
    inert YAML scalar instead.
    """
    frontmatter = {
        "id": dec_id,
        "status": status,
        "date": date,
        "actor": actor,
        "ts": ts,
        "affects": ", ".join(affects) if affects else "",
    }
    fm_text = yaml_io.safe_dump(frontmatter, default_flow_style=False, sort_keys=False).rstrip("\n")
    # A title is a single heading line: collapse any newline the caller slipped
    # in (e.g. `title="x\n## DEC-<k>"`) to a space so it cannot forge a second
    # heading line the id scan would count.
    safe_title = " ".join((title or "").splitlines()).strip()
    heading = "## %s — %s" % (dec_id, safe_title) if safe_title else "## %s" % dec_id
    return (
        "\n---\n"
        "%s\n"
        "---\n"
        "\n"
        "%s\n"
        "\n"
        "%s\n"
    ) % (fm_text, heading, _defuse_body(body or ""))


def _defuse_body(body: str) -> str:
    """Neutralize any body line that the ledger's structural parse would
    mis-read: a markdown heading (``## DEC-<k>`` an example quotes), a ``---``
    fence, or a ``...`` YAML doc-end.

    A ``---`` fence / ``...`` doc-end / ``id:`` line anchors strictly at column
    0, so a single leading space renders it inert. A heading is different: the
    heading scan tolerates 0–3 leading spaces (CommonMark), so one space does
    NOT break a col-0 ``## DEC-<k>`` — it must be pushed to a >=4-space indent
    (an indented code line, no longer a heading). The heading trigger is
    ``_HEADING_WITH_DEC_RE`` itself (not the narrower ``_BODY_STRUCTURAL_LINE_RE``
    heading alt, which requires a space after the ``#``s): that scan also counts
    a no-space hand-typo ``##DEC-<k>``, so the defuse must cover the same shape
    to fully neutralize what a later parse could re-read. Preserves the author's
    text (aside from normalizing CR/CRLF line endings to LF — see below); only
    shifts a would-be marker out of structural range."""
    # Normalize CR / CRLF to LF FIRST, so the defuse pass sees exactly the lines
    # the later ledger read (read_text — universal-newline) will. Otherwise a body
    # gluing a forged fence+id+heading block with lone \r is one opaque segment to
    # this \n-only split (nothing neutralized), yet re-materializes as real column-0
    # structural lines on re-parse — forging a second, never-allocated DEC entry.
    body = body.replace("\r\n", "\n").replace("\r", "\n")
    out = []
    for line in body.split("\n"):
        if _HEADING_WITH_DEC_RE.match(line):
            line = "    " + line.lstrip(" ")  # >=4 spaces: past the ATX heading window
        elif _BODY_STRUCTURAL_LINE_RE.match(line):
            stripped = line.lstrip(" ")
            if stripped.startswith("#"):
                line = "    " + stripped
            else:
                line = " " + line
        out.append(line)
    return "\n".join(out)


def alloc(
    root: RootLike,
    status: str = "active",
    affects: Optional[Sequence[str]] = None,
    title: str = "",
    body: str = "",
    actor: Optional[str] = None,
) -> str:
    """Allocate + append the next DEC id for ``root``'s workspace ledger.

    Whole critical section {read max -> compute id -> append} holds an exclusive
    ``fcntl.flock`` on the sibling ``.decisions.lock`` file, so concurrent
    callers on the same workspace serialize instead of racing to the same id.
    """
    root = Path(root)
    path = _decisions_path(root)
    lock_path = _lock_path(root)
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            _ensure_ledger(path)
            # A non-regular ledger (FIFO/device, or a symlink to one) would block
            # the read_text below forever inside the flock. is_file() stats only;
            # raise a clean error so the CLI exits instead of freezing.
            if not path.is_file():
                raise ValueError(
                    "decision ledger is not a regular file (FIFO/socket/device): %s" % path)
            text = path.read_text(encoding="utf-8")
            ids_before = _existing_ids(text)

            new_num = _max_id_num(ids_before) + 1
            dec_id = "DEC-%d" % new_num
            if not DEC_ID_PATTERN.match(dec_id):
                raise ValueError("allocated id failed grammar check: %s" % dec_id)

            # `new_num = max + 1` is strictly greater than every existing id, so
            # the allocation can never collide — no whole-ledger uniqueness gate
            # is needed, and crucially one must NOT run here: a pre-existing
            # hand-edit duplicate in this hand-maintained ledger would otherwise
            # raise and brick every future --add. This defensive check can only
            # trip on an internal miscount, never on prior ledger corruption.
            if dec_id in ids_before:
                raise RuntimeError("allocator miscount: %s already present" % dec_id)

            resolved_actor = actor or _default_actor()
            ts = _now_iso()
            date = ts[:10]
            block = _render_block(
                dec_id, status, date, resolved_actor, ts, affects or [], title, body
            )

            with open(path, "a", encoding="utf-8") as f:
                f.write(block)

            return dec_id
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def list_decisions(root: RootLike) -> List[Dict[str, str]]:
    """Return parsed frontmatter dicts for every DEC block in ``root``'s ledger,
    de-duplicated by ``id`` (first wins). The dedupe guards a hand-pasted sample
    block inside a decision body that mimics a real fenced block + heading — it
    must not surface as a phantom duplicate ruling to the staleness sweep."""
    path = _decisions_path(root)
    if not path.exists():
        return []
    # A non-regular ledger (FIFO/device, or a symlink to one) would block read_text
    # forever; is_file() stats only. Fail soft to [] (no readable ledger).
    if not path.is_file():
        return []
    blocks = _parse_blocks(path.read_text(encoding="utf-8"))
    seen, out = set(), []
    for b in blocks:
        bid = b.get("id", "")
        if bid and bid in seen:
            continue
        seen.add(bid)
        out.append(b)
    return out


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="dec_ledger.py",
        description="Per-workspace DEC ledger allocator: grep-max+1 "
        "under flock, never the harness's tool-managed atomic allocator.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--add", action="store_true", help="allocate + append a new DEC block")
    mode.add_argument("--list", action="store_true", help="list existing DEC blocks")
    p.add_argument("--status", default="active")
    p.add_argument("--affects", default="", help="comma-separated affected ids")
    p.add_argument("--title", default="")
    p.add_argument("--body", default="")
    p.add_argument("--actor", default=None)
    return p


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    if args.add:
        affects = [a.strip() for a in args.affects.split(",") if a.strip()]
        dec_id = alloc(
            args.root, status=args.status, affects=affects,
            title=args.title, body=args.body, actor=args.actor,
        )
        print(dec_id)
        return 0
    if args.list:
        for rec in list_decisions(args.root):
            print("%s\t%s\t%s" % (rec.get("id", ""), rec.get("status", ""), rec.get("date", "")))
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
