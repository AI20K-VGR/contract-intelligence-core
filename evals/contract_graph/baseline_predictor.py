"""Baseline predictor: the spike rule parser (op_parser_eval.py) ported as-is.

It is the yardstick P2/P3 must beat, not a reference implementation: it reads the op from
the item verb, takes the first address regex hit as target ("Bổ sung khoản 5 vào sau
khoản 4 Điều 6" → "khoản 4 điều 6") and appends only the parent article to sub-items.
Only the operative body is fixed (longest "Điều N." outside quotes, see ``operative_body``).
"""

from __future__ import annotations

import json
import re
import sys
from pathlib import Path

from evals.contract_graph.gold import canonical_address
from evals.contract_graph.normalize import operative_body

AI_SERVICE = Path(__file__).resolve().parents[2] / "ai-service"
OP_HEAD = r"(?:Sửa đổi, bổ sung|Sửa đổi|Bổ sung|Bãi bỏ|Thay thế|Thay cụm từ|Bỏ cụm từ)"
# "(?<!Điều)": the heading "Điều 1. Sửa đổi, bổ sung …" is not item 1 (the spike hid that duplicate in a dict)
_CLAUSE = re.compile(rf"(?:^|(?<!Điều)\s)(\d{{1,2}})\.\s+({OP_HEAD}[^:]{{0,200}})")
_LIST_VALUE = {"điểm": r"[a-zđ]\d*", "khoản": r"\d+[a-zđ]?"}
_POINT = re.compile(rf"(?:^|\s)([a-zđ])\)\s+({OP_HEAD}[^:]{{0,200}})")


def op_of(head: str) -> str:
    low = head.lower()
    if low.startswith("bãi bỏ") or low.startswith("bỏ cụm từ"):
        return "REPEAL"
    if low.startswith("bổ sung"):
        return "INSERTION"
    return "SUBSTITUTION"  # sửa đổi / sửa đổi, bổ sung / thay thế / thay cụm từ


def target_of(head: str) -> str | None:
    low = head.lower()
    m = re.search(r"((?:điểm \w+ )?(?:khoản \d+ )?(?:(?:của )?điều \d+))", low)
    if m:
        return m.group(1)
    m = re.search(
        r"((?:điểm \w+ )?khoản \d+|điểm \w+)", low
    )  # relative: parent article appended by caller
    return m.group(1) if m else None


def listed_targets(head: str, target: str | None) -> list[str | None]:
    """The spike target, once per value of an enumerated list in the head.

    "Bổ sung điểm d1, d2 vào sau điểm d" with target "điểm d1 điều 3" → d1 and d2. Only a
    list whose first value is the one the spike target already holds is expanded, so the
    target itself (and its missing levels) stays exactly the spike's.
    """

    if not target:
        return [target]
    low = head.lower()
    for level, value in _LIST_VALUE.items():
        for m in re.finditer(
            rf"{level} ({value})(?!\w)((?:\s*(?:,|và(?!\w))\s*{value}(?!\w))+)", low
        ):
            first = m.group(1)
            own = re.compile(rf"{level} {re.escape(first)}(?!\w)")
            if not own.search(target):
                continue
            rest = re.findall(rf"(?:,|và(?!\w))\s*({value})(?!\w)", m.group(2))
            return [own.sub(f"{level} {v}", target, count=1) for v in [first, *rest]]
    return [target]


def parse(text: str, article: str = "1") -> list[dict]:
    """Operation items of ``Điều <article>`` in document order (duplicates kept, no dict-by-src)."""

    body = " ".join(operative_body(text, article, str(int(article) + 1)).split())
    marker = _marker()
    items = []

    def item(src: str, head: str, target: str | None) -> dict:
        return {
            "src_address": canonical_address(src),
            "op": op_of(head),
            "target_text": target,
            "target_address": canonical_address(target),
            "target_addresses": [canonical_address(t) for t in listed_targets(head, target)],
            "head": head[:160],
            "marker_hit": bool(marker(head)),
        }

    clauses = list(_CLAUSE.finditer(body))
    for i, k in enumerate(clauses):
        kno, head = k.group(1), k.group(2)
        items.append(item(f"khoản {kno} điều {article}", head, target_of(head)))
        seg = body[k.end() : clauses[i + 1].start() if i + 1 < len(clauses) else len(body)]
        art = re.search(r"điều \d+", head.lower())
        for d in _POINT.finditer(seg):
            sub = d.group(2)
            tgt = target_of(sub)
            if tgt and "điều" not in tgt and art:
                tgt = (
                    f"{tgt} {art.group(0)}"  # sub-item addresses are relative to the parent article
                )
            items.append(item(f"điểm {d.group(1)} khoản {kno} điều {article}", sub, tgt))
    return items


def predict(pair_dir: Path) -> list[dict]:
    pair_dir = Path(pair_dir)
    text = (pair_dir / "amending.txt").read_text(encoding="utf-8")
    return parse(text, _operative_article(pair_dir))


def _operative_article(pair_dir: Path) -> str:
    manifest = pair_dir.parent / "manifest.json"
    if manifest.is_file():
        for entry in json.loads(manifest.read_text(encoding="utf-8")).get("pairs", []):
            if entry.get("pair_id") == pair_dir.name:
                return str(entry.get("operative_article", "1"))
    return "1"


def _marker():
    if str(AI_SERVICE) not in sys.path:
        sys.path.insert(0, str(AI_SERVICE))
    from app.pipeline.relation_markers import has_amend_marker

    return has_amend_marker
