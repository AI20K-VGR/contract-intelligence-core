from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evals.contract_graph.pairs import review

SEED = 20261008


def _records(label: str, stratum: str, n: int, direction: str | None = None) -> list[dict]:
    out = []
    for i in range(n):
        pid = f"{label[:4]}-{stratum}-{i:04d}"
        out.append(
            {
                "pair_id": pid,
                "doc_id": f"pd-{i % 3}",
                "a": f"pd-{i % 3}:n{i}",
                "b": f"pd-{i % 3}:n{i + 1}",
                "stratum": stratum,
                "label": label,
                "label_invalid": False,
                "general": direction if label == "GENERAL_SPECIFIC" else None,
                "referrer": direction if label == "REFERENCE" else None,
                "span_a": "x",
                "span_b": "y",
                "grounded": True,
            }
        )
    return out


def _labels_by_stratum() -> dict[str, list[dict]]:
    return {
        "S1": _records("GENERAL_SPECIFIC", "S1", 70, "A") + _records("UNRELATED", "S1", 600),
        "S2": _records("GENERAL_SPECIFIC", "S2", 50, "B") + _records("UNRELATED", "S2", 150)
        + _records("CONFLICT", "S2", 30),
        "S3": _records("UNRELATED", "S3", 50),
    }


def test_selection_caps_and_pi():
    selection = review.select_for_review(_labels_by_stratum(), SEED)
    by_cell: dict[tuple[str, str], list[dict]] = {}
    for row in selection:
        by_cell.setdefault((row["gpt_label"], row["stratum"]), []).append(row)

    gs = [r for r in selection if r["gpt_label"] == "GENERAL_SPECIFIC"]
    assert len(gs) == review.POSITIVE_CAP == 75
    assert {r["pi"] for r in gs} == {75 / 120}
    conflict = [r for r in selection if r["gpt_label"] == "CONFLICT"]
    assert len(conflict) == 30 and {r["pi"] for r in conflict} == {1.0}
    unrelated = {s: len(by_cell.get(("UNRELATED", s), [])) for s in ("S1", "S2", "S3")}
    # proportional 60/15/5 of 80, S3 raised to the floor of 10, taken from the largest cell
    assert unrelated == {"S1": 55, "S2": 15, "S3": 10}
    assert {r["pi"] for r in by_cell[("UNRELATED", "S1")]} == {55 / 600}
    assert {r["pi"] for r in by_cell[("UNRELATED", "S2")]} == {15 / 150}
    assert {r["pi"] for r in by_cell[("UNRELATED", "S3")]} == {10 / 50}
    assert len(selection) == 75 + 30 + 80
    assert len({r["pair_id"] for r in selection}) == len(selection)
    assert all({"pair_id", "doc_id", "a", "b", "stratum", "gpt_label", "pi"} <= set(r)
               for r in selection)


def test_selection_skips_invalid_labels_and_takes_all_when_small():
    labels = {"S1": _records("UNRELATED", "S1", 20) + _records("DUPLICATE", "S1", 3)}
    labels["S1"][0] = {**labels["S1"][0], "label": None, "label_invalid": True}
    selection = review.select_for_review(labels, SEED)

    assert len(selection) == 19 + 3
    assert {r["pi"] for r in selection} == {1.0}


def test_selection_over_row_cap_errors():
    with pytest.raises(review.ReviewCapExceeded) as excinfo:
        review.select_for_review(_labels_by_stratum(), SEED, row_cap=100)

    assert "185" in str(excinfo.value)
    assert excinfo.value.rows == 185


def test_selection_deterministic():
    first = review.select_for_review(_labels_by_stratum(), SEED)

    assert review.select_for_review(_labels_by_stratum(), SEED) == first
    reordered = {k: list(reversed(v)) for k, v in reversed(list(_labels_by_stratum().items()))}
    assert review.select_for_review(reordered, SEED) == first
    assert review.select_for_review(_labels_by_stratum(), SEED + 1) != first


def _sheet(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "sheet.csv"
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        for row in rows:
            writer.writerow({c: row.get(c, "") for c in review.SHEET_COLUMNS})
    return path


def _row(pid: str, decision: str, **kw) -> dict:
    return {"pair_id": pid, "doc_id": "pd-0", "gpt_label": "CONFLICT", "gpt_direction": "",
            "decision": decision, **kw}


def test_import_requires_label_for_relabel(tmp_path: Path):
    path = _sheet(
        tmp_path,
        [
            _row("p1", "approve"),
            _row("p2", "relabel"),
            _row("p3", "relabel", label_fixed="GENERAL_SPECIFIC"),
            _row("p4", "relabel", label_fixed="GENERAL_SPECIFIC", direction_fixed="A"),
        ],
    )
    with pytest.raises(review.SheetError) as excinfo:
        review.import_sheet(path)

    message = str(excinfo.value)
    assert "dòng 3" in message and "dòng 4" in message
    assert "dòng 2" not in message and "dòng 5" not in message

    ok = _sheet(tmp_path, [_row("p4", "relabel", label_fixed="GENERAL_SPECIFIC",
                                direction_fixed="a")])
    assert review.import_sheet(ok) == [
        {"pair_id": "p4", "gold_label": "GENERAL_SPECIFIC", "gold_direction": "A",
         "approved": True, "source": "user-review"}
    ]


def test_import_reject_is_not_approved(tmp_path: Path):
    path = _sheet(tmp_path, [_row("p1", "reject"), _row("p2", " Approve ")])
    decisions = review.import_sheet(path)

    assert decisions[0] == {"pair_id": "p1", "gold_label": None, "gold_direction": None,
                            "approved": False, "source": "user-review"}
    assert decisions[1]["approved"] is True
    assert decisions[1]["gold_label"] == "CONFLICT"


def test_import_unknown_decision_is_error(tmp_path: Path):
    path = _sheet(tmp_path, [_row("p1", "approve"), _row("p2", "maybe"), _row("p3", "")])

    with pytest.raises(review.SheetError) as excinfo:
        review.import_sheet(path)
    assert "dòng 3" in str(excinfo.value) and "dòng 4" in str(excinfo.value)


def test_labeler_confusion_counts_by_stratum():
    selection = [
        {"pair_id": "p1", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 1.0},
        {"pair_id": "p2", "stratum": "S1", "gpt_label": "CONFLICT", "pi": 1.0},
        {"pair_id": "p3", "stratum": "S2", "gpt_label": "UNRELATED", "pi": 0.5},
        {"pair_id": "p4", "stratum": "S2", "gpt_label": "DUPLICATE", "pi": 1.0},
    ]
    decisions = [
        {"pair_id": "p1", "gold_label": "CONFLICT", "gold_direction": None, "approved": True},
        {"pair_id": "p2", "gold_label": "UNRELATED", "gold_direction": None, "approved": True},
        {"pair_id": "p3", "gold_label": "UNRELATED", "gold_direction": None, "approved": True},
        {"pair_id": "p4", "gold_label": None, "gold_direction": None, "approved": False},
    ]
    confusion = review.labeler_confusion(selection, decisions)

    assert confusion["by_stratum"]["S1"]["CONFLICT"] == {"CONFLICT": 1, "UNRELATED": 1}
    assert confusion["by_stratum"]["S2"]["UNRELATED"] == {"UNRELATED": 1}
    assert confusion["by_stratum"]["S2"]["DUPLICATE"] == {"REJECTED": 1}
    assert confusion["overall"]["CONFLICT"] == {"CONFLICT": 1, "UNRELATED": 1}
    assert confusion["agreement"] == {"passed": 2, "denominator": 3}
    assert "cận trên" in confusion["note"]


def test_export_roundtrip_utf8_bom(tmp_path: Path):
    labels = _labels_by_stratum()
    selection = review.select_for_review(labels, SEED)[:3]
    labels_by_pair = {r["pair_id"]: r for rows in labels.values() for r in rows}
    nodes = {}
    for row in selection:
        nodes[row["a"]] = {"heading": "Điều 1. Giá", "text": "Giá là 10 “triệu”, đồng\nhết."}
        nodes[row["b"]] = {"heading": "Phụ lục 01", "text": "Thanh toán; 30 ngày."}
    path = tmp_path / "hg1.csv"
    review.export_sheet(path, selection, labels_by_pair, nodes)

    assert path.read_bytes().startswith(b"\xef\xbb\xbf")
    with open(path, encoding="utf-8-sig", newline="") as fh:
        rows = list(csv.DictReader(fh))
    assert list(rows[0]) == review.SHEET_COLUMNS
    assert rows[0]["text_a"] == "Giá là 10 “triệu”, đồng\nhết."
    assert [r["pair_id"] for r in rows] == [r["pair_id"] for r in selection]
    for row in rows:
        row["decision"] = "approve"
    with open(path, "w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=review.SHEET_COLUMNS)
        writer.writeheader()
        writer.writerows(rows)
    decisions = review.import_sheet(path)
    assert [d["gold_label"] for d in decisions] == [r["gpt_label"] for r in selection]
    assert all(d["approved"] for d in decisions)
