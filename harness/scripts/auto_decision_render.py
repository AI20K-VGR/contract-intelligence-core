#!/usr/bin/env python3
"""auto_decision_render.py — the human-readable view over the auto-decision ledger.

The JSONL store is the source of truth (append-only, machine-written). This renders a
DERIVED `auto-decisions.md` from it, full-regen each time — the glossary.yaml->GLOSSARY.md
pattern (code-standards §3). Full-regen of a derived view does not violate no-read-modify-
write: that rule guards the append-only SOURCE, never a view.

Write is ATOMIC: a UNIQUE mkstemp temp per pid + os.replace, never a fixed `.tmp`
sibling — two concurrent renders (in-place --parallel cook) must not clobber a shared temp,
and a mid-write failure must leave the old view byte-intact.

The header disambiguates from the human-approved DEC register (docs/decisions.md): this
ledger records what an AI decided ON ITS OWN, not a user-approved decision — naming honesty.
"""
import os
import sys
import tempfile
from pathlib import Path
from typing import List, Optional

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_MUST_REVIEW_HEADING = "## ⚠ Phải soát (chưa)"
_REVIEWED_HEADING = "## Đã soát"
_TRACE_HEADING = "## Chỉ truy-vết"
_COLUMNS = ("id", "label", "in_plan", "skill/mode", "what", "why", "evidence", "reviewed")


def md_path_for(jsonl_path) -> Path:
    """The view path beside the JSONL store. Plan store lives in artifacts/, its view sits
    one level up (plan_dir/auto-decisions.md); a reports fallback store swaps .jsonl->.md in
    place."""
    p = Path(jsonl_path)
    if p.parent.name == "artifacts":
        return p.parent.parent / "auto-decisions.md"
    return p.with_suffix(".md")


def _slug_for(md_path: Path) -> str:
    parent = md_path.parent.name
    return md_path.stem if parent == "reports" else (parent or "unscoped")


def _fmt_cell(v) -> str:
    """One table cell: stringified, pipes escaped, newlines flattened (a torn row breaks the
    whole markdown table)."""
    s = "" if v is None else str(v)
    return s.replace("|", "\\|").replace("\n", " ").strip()


def _row(d: dict) -> str:
    skill_mode = "%s/%s" % (d.get("skill", ""), d.get("mode", ""))
    cells = [
        d.get("id", ""),
        d.get("label", ""),
        "yes" if d.get("in_plan") else "no",
        skill_mode,
        d.get("what", ""),
        d.get("why", ""),
        d.get("evidence", ""),
        "yes" if d.get("reviewed") else "no",
    ]
    return "| " + " | ".join(_fmt_cell(c) for c in cells) + " |"


def _table(rows: List[dict]) -> str:
    if not rows:
        return "_(none)_\n"
    head = "| " + " | ".join(_COLUMNS) + " |"
    sep = "| " + " | ".join("---" for _ in _COLUMNS) + " |"
    body = "\n".join(_row(d) for d in rows)
    return "\n".join([head, sep, body]) + "\n"


def _render_md(folded: List[dict], slug: str, must_review_basket) -> str:
    """Build the full view. Ordering is deterministic (by id) so the render is idempotent —
    fold_state returns dict-insertion order, which mirrors append order; sort by id to be
    stable regardless of that."""
    must_unreviewed, reviewed, trace = [], [], []
    for d in sorted(folded, key=lambda x: x.get("id", "")):
        if d.get("reviewed"):
            reviewed.append(d)
        elif d.get("label") in must_review_basket:
            must_unreviewed.append(d)
        else:
            trace.append(d)

    lines = [
        "# Auto-Decision Ledger — %s" % slug,
        "",
        "> Quyết-định con-AI TỰ ra ở chế-độ tự-quyết (KHÔNG phải sổ DEC user-duyệt "
        "`docs/decisions.md`). Sổ **chỉ để đọc, advisory** — không chặn việc gì. "
        "Nguồn sự-thật = `artifacts/auto-decisions.jsonl`; file này là VIEW sinh ra.",
        "",
        _MUST_REVIEW_HEADING,
        "",
        _table(must_unreviewed),
        "",
        _REVIEWED_HEADING,
        "",
        _table(reviewed),
        "",
        _TRACE_HEADING,
        "",
        _table(trace),
    ]
    return "\n".join(lines) + "\n"


def _atomic_write(md_path: Path, text: str) -> None:
    """Write via a UNIQUE temp in the target dir, then os.replace (atomic same-dir rename).
    On any failure the temp is removed and the exception re-raised — the in-place view is
    never touched."""
    md_path = Path(md_path)
    md_path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp = tempfile.mkstemp(dir=str(md_path.parent), prefix=".auto-decisions-", suffix=".tmp")
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as fh:
            fh.write(text)
        os.replace(tmp, md_path)
    except BaseException:
        try:
            os.unlink(tmp)
        except OSError:
            pass
        raise


def render(jsonl_path, md_path=None, slug: Optional[str] = None) -> Path:
    """Re-render the view from the JSONL source. Lazy-imports auto_decision_log so the log
    module can wire the reverse call (append->render) without a circular top-level import."""
    import auto_decision_log as adl
    md_path = Path(md_path) if md_path is not None else md_path_for(jsonl_path)
    slug = slug or _slug_for(md_path)
    must_review = {name for name, basket in adl.load_labels().items() if basket == "must_review"}
    folded = adl.fold_state(adl.load_events(jsonl_path))
    _atomic_write(md_path, _render_md(folded, slug, must_review))
    return md_path


def main(argv=None) -> int:
    import argparse
    ap = argparse.ArgumentParser(description="Render the auto-decision ledger view from JSONL.")
    ap.add_argument("--store", required=True, help="the JSONL source path")
    ap.add_argument("--md", default=None, help="view path (default: derived beside the store)")
    args = ap.parse_args(argv)
    try:
        out = render(args.store, args.md)
    except OSError as exc:
        sys.stderr.write("[auto_decision_render] render failed: %s\n" % exc)
        return 1
    sys.stderr.write("[auto_decision_render] wrote %s\n" % out)
    return 0


if __name__ == "__main__":
    sys.exit(main())
