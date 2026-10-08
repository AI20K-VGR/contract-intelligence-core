"""HG-1 review sample (D18, RT-01): weighted selection, review sheet export/import, GPT↔human
confusion.

Selection is pre-registered and weighted: each GPT-positive label is taken whole up to
``POSITIVE_CAP`` and seed-sampled above it; GPT-UNRELATED gets ``UNRELATED_SAMPLE`` rows spread
over strata in proportion to their UNRELATED counts (largest remainder), each stratum raised to
``UNRELATED_FLOOR`` when it has that many, the units taken from the largest allocation. Every
row carries ``pi``, its cell's inclusion probability, so the scorer can weight by ``1/pi``.
"""

from __future__ import annotations

import csv
import hashlib
import random
from collections.abc import Iterable, Mapping
from pathlib import Path

from evals.contract_graph.pairs.labeler import DIRECTED, DIRECTIONS, LABELS, UNRELATED

POSITIVE_LABELS = tuple(label for label in LABELS if label != UNRELATED)
POSITIVE_CAP = 75
UNRELATED_SAMPLE = 80
UNRELATED_FLOOR = 10
REVIEW_ROW_CAP = 380
DECISIONS = ("approve", "relabel", "reject")
SHEET_COLUMNS = [
    "pair_id", "doc_id", "heading_a", "text_a", "heading_b", "text_b", "gpt_label",
    "gpt_direction", "gpt_span_a", "gpt_span_b", "grounded", "decision", "label_fixed",
    "direction_fixed", "note",
]
CONFUSION_NOTE = (
    "Đồng thuận GPT↔người là cận trên: người duyệt thấy nhãn GPT khi duyệt (không có người gán "
    "mù thứ hai)."
)


class ReviewCapExceeded(ValueError):
    def __init__(self, rows: int, cap: int) -> None:
        super().__init__(f"review selection has {rows} rows > cap {cap}; not truncated")
        self.rows = rows
        self.cap = cap


class SheetError(ValueError):
    """Every invalid row of an imported review sheet, by line number (header = dòng 1)."""


def select_for_review(
    labels_by_stratum: Mapping[str, Iterable[dict]],
    seed: int,
    *,
    positive_cap: int = POSITIVE_CAP,
    unrelated_sample: int = UNRELATED_SAMPLE,
    unrelated_floor: int = UNRELATED_FLOOR,
    row_cap: int | None = REVIEW_ROW_CAP,
) -> list[dict]:
    """Label records (``pair_id, doc_id, a, b, label, label_invalid``) per stratum → selected rows
    ``{pair_id, doc_id, a, b, stratum, gpt_label, pi}`` sorted by (label, stratum, pair_id).
    Invalid labels are never selected. Over ``row_cap`` ⇒ ``ReviewCapExceeded``."""

    cells: dict[tuple[str, str], list[dict]] = {}
    for stratum, records in labels_by_stratum.items():
        for record in records:
            label = record.get("label")
            if record.get("label_invalid") or label not in LABELS:
                continue
            cells.setdefault((label, stratum), []).append({**record, "stratum": stratum})
    for rows in cells.values():
        rows.sort(key=lambda r: r["pair_id"])

    selected: list[dict] = []
    for label in POSITIVE_LABELS:
        pool = sorted(
            (r for (lab, _), rows in cells.items() if lab == label for r in rows),
            key=lambda r: r["pair_id"],
        )
        take = _sample(pool, positive_cap, seed, label)
        pi = len(take) / len(pool) if pool else 1.0
        selected.extend(_row(r, label, pi) for r in take)
    unrelated = {s: rows for (lab, s), rows in cells.items() if lab == UNRELATED}
    quota = allocate({s: len(rows) for s, rows in unrelated.items()}, unrelated_sample,
                     unrelated_floor)
    for stratum in sorted(unrelated):
        rows = unrelated[stratum]
        take = _sample(rows, quota[stratum], seed, f"{UNRELATED}:{stratum}")
        selected.extend(_row(r, UNRELATED, quota[stratum] / len(rows)) for r in take)
    if row_cap is not None and len(selected) > row_cap:
        raise ReviewCapExceeded(len(selected), row_cap)
    order = {label: i for i, label in enumerate(LABELS)}
    return sorted(selected, key=lambda r: (order[r["gpt_label"]], r["stratum"], r["pair_id"]))


def allocate(counts: Mapping[str, int], total: int, floor: int) -> dict[str, int]:
    """Split ``total`` over strata ∝ ``counts`` (largest remainder, ties by name), then raise each
    stratum to ``min(floor, count)`` with units taken from the largest allocation above its own
    floor. ``sum(counts) ≤ total`` ⇒ every stratum whole."""

    n = sum(counts.values())
    if n <= total:
        return dict(counts)
    quotas = {s: total * c / n for s, c in counts.items()}
    alloc = {s: int(q) for s, q in quotas.items()}
    by_remainder = sorted(counts, key=lambda s: (-(quotas[s] - alloc[s]), s))
    for s in by_remainder[: total - sum(alloc.values())]:
        alloc[s] += 1
    need = {s: min(floor, c) for s, c in counts.items()}
    for s in sorted(counts):
        while alloc[s] < need[s]:
            donor = max(
                (d for d in counts if alloc[d] > need[d]), key=lambda d: (alloc[d], d), default=None
            )
            if donor is None:
                break
            alloc[donor] -= 1
            alloc[s] += 1
    return alloc


def _sample(rows: list[dict], k: int, seed: int, cell: str) -> list[dict]:
    if len(rows) <= k:
        return list(rows)
    rng = random.Random(seed ^ int(hashlib.sha256(cell.encode("utf-8")).hexdigest()[:8], 16))
    return sorted(rng.sample(rows, k), key=lambda r: r["pair_id"])


def _row(record: dict, label: str, pi: float) -> dict:
    return {
        "pair_id": record["pair_id"],
        "doc_id": record.get("doc_id"),
        "a": record.get("a"),
        "b": record.get("b"),
        "stratum": record["stratum"],
        "gpt_label": label,
        "pi": pi,
    }


def gpt_direction(record: Mapping) -> str:
    key = DIRECTED.get(record.get("label") or "")
    return (record.get(key) or "") if key else ""


def export_sheet(
    path: Path,
    selection: Iterable[dict],
    labels_by_pair: Mapping[str, Mapping],
    nodes_by_id: Mapping[str, Mapping],
) -> int:
    """Review sheet (CSV, UTF-8 with BOM for spreadsheet apps), one row per selected pair, in
    selection order. Returns the row count. The sheet holds clause text: write it outside the
    repo (``AI2_CG_PAIRS_DATA_DIR``)."""

    rows = 0
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=SHEET_COLUMNS)
        writer.writeheader()
        for sel in selection:
            label = labels_by_pair[sel["pair_id"]]
            a, b = nodes_by_id[sel["a"]], nodes_by_id[sel["b"]]
            writer.writerow(
                {
                    "pair_id": sel["pair_id"],
                    "doc_id": sel.get("doc_id") or "",
                    "heading_a": a.get("heading", ""),
                    "text_a": a.get("text", ""),
                    "heading_b": b.get("heading", ""),
                    "text_b": b.get("text", ""),
                    "gpt_label": sel["gpt_label"],
                    "gpt_direction": gpt_direction(label),
                    "gpt_span_a": label.get("span_a") or "",
                    "gpt_span_b": label.get("span_b") or "",
                    "grounded": str(bool(label.get("grounded"))).lower(),
                    "decision": "",
                    "label_fixed": "",
                    "direction_fixed": "",
                    "note": "",
                }
            )
            rows += 1
    return rows


def import_sheet(path: Path) -> list[dict]:
    """Filled sheet → ``{pair_id, gold_label, gold_direction, approved, source}`` per row.
    ``approve`` keeps the GPT label/direction, ``relabel`` needs ``label_fixed`` (+ direction for
    a directed label), ``reject`` is never approved. Any invalid row ⇒ ``SheetError`` listing all."""

    with open(path, encoding="utf-8-sig", newline="") as fh:
        reader = csv.DictReader(fh)
        missing = [c for c in ("pair_id", "gpt_label", "gpt_direction", "decision",
                               "label_fixed", "direction_fixed") if c not in (reader.fieldnames or [])]
        if missing:
            raise SheetError(f"dòng 1: thiếu cột {missing}")
        rows = list(reader)
    decisions, errors = [], []
    for line, row in enumerate(rows, start=2):
        decision = (row.get("decision") or "").strip().casefold()
        pair_id = (row.get("pair_id") or "").strip()
        if not pair_id:
            errors.append(f"dòng {line}: thiếu pair_id")
            continue
        if decision not in DECISIONS:
            errors.append(f"dòng {line}: decision {row.get('decision')!r} ∉ {DECISIONS}")
            continue
        if decision == "reject":
            decisions.append(_decision(pair_id, None, None, approved=False))
            continue
        if decision == "approve":
            label = (row.get("gpt_label") or "").strip()
            direction = (row.get("gpt_direction") or "").strip().upper() or None
        else:
            label = (row.get("label_fixed") or "").strip().upper()
            direction = (row.get("direction_fixed") or "").strip().upper() or None
        if label not in LABELS:
            errors.append(f"dòng {line}: nhãn {label!r} ∉ {LABELS}")
            continue
        if label in DIRECTED:
            if direction not in DIRECTIONS:
                errors.append(f"dòng {line}: {label} cần hướng A|B ({DIRECTED[label]})")
                continue
        else:
            direction = None
        decisions.append(_decision(pair_id, label, direction, approved=True))
    if errors:
        raise SheetError("\n".join(errors))
    return decisions


def _decision(pair_id: str, label: str | None, direction: str | None, *, approved: bool) -> dict:
    return {
        "pair_id": pair_id,
        "gold_label": label,
        "gold_direction": direction,
        "approved": approved,
        "source": "user-review",
    }


def labeler_confusion(selection: Iterable[dict], decisions: Iterable[dict]) -> dict:
    """GPT label → human label counts, overall and per stratum; a rejected row is ``REJECTED``.
    ``agreement`` counts approved rows whose human label equals the GPT label."""

    by_pair = {d["pair_id"]: d for d in decisions}
    by_stratum: dict[str, dict[str, dict[str, int]]] = {}
    overall: dict[str, dict[str, int]] = {}
    passed = denominator = 0
    for sel in sorted(selection, key=lambda s: s["pair_id"]):
        decision = by_pair.get(sel["pair_id"])
        if decision is None:
            continue
        human = decision["gold_label"] if decision["approved"] else "REJECTED"
        for table in (by_stratum.setdefault(sel["stratum"], {}), overall):
            cell = table.setdefault(sel["gpt_label"], {})
            cell[human] = cell.get(human, 0) + 1
        if decision["approved"]:
            denominator += 1
            passed += human == sel["gpt_label"]
    return {
        "by_stratum": by_stratum,
        "overall": overall,
        "agreement": {"passed": passed, "denominator": denominator},
        "note": CONFUSION_NOTE,
    }
