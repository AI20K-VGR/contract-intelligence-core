from __future__ import annotations

import csv
from pathlib import Path

import pytest

from evals.spikes.clause_key.import_heldout import FIELDS, HeldoutError, import_csv


def _write(tmp_path: Path, rows: list[dict]) -> Path:
    path = tmp_path / "heldout.csv"
    with path.open("w", encoding="utf-8-sig", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=FIELDS)
        writer.writeheader()
        for row in rows:
            writer.writerow({k: row.get(k, "") for k in FIELDS})
    return path


REMEDY = {
    "clause_id": "H01",
    "profile": "SALES",
    "text": "Bên B giao hàng chậm quá 10 ngày thì chịu phạt 5.000.000 đồng.",
    "context_parties": "Bên B=SELLER",
    "frame_type": "REMEDY",
    "bearer": "SELLER",
    "action": "DELIVER",
    "qualifier": "LATE",
    "anchor": "chịu phạt 5.000.000 đồng",
    "consequence_type": "PENALTY_FIXED",
    "consequence_value": "5000000",
}


def test_import_remedy_row(tmp_path):
    clauses = import_csv(_write(tmp_path, [REMEDY]))
    assert len(clauses) == 1
    c = clauses[0]
    assert c["context"] == {"parties": {"Bên B": "SELLER"}}
    f = c["frames"][0]
    assert f["gold_key"] == ["SELLER", "DELIVER", "LATE"]
    assert f["anchor"] == "chịu phạt 5.000.000 đồng"
    assert f["gold_consequence"] == {"type": "PENALTY_FIXED", "value": "5000000"}
    assert "spans" not in f


def test_import_groups_frames_of_one_clause_and_inherits_text(tmp_path):
    second = {**REMEDY, "text": "", "context_parties": "", "qualifier": "LATE",
              "anchor": "chịu phạt", "consequence_value": ""}
    clauses = import_csv(_write(tmp_path, [REMEDY, second]))
    assert len(clauses) == 1 and len(clauses[0]["frames"]) == 2


def test_import_none_action_means_no_key(tmp_path):
    row = {**REMEDY, "action": "NONE", "qualifier": ""}
    assert import_csv(_write(tmp_path, [row]))[0]["frames"][0]["gold_key"] is None


def test_import_parameter_row(tmp_path):
    row = {"clause_id": "H02", "profile": "LEASE", "text": "Tiền thuê hàng tháng là 40.000.000 đồng.",
           "frame_type": "PARAMETER", "param": "RENT", "object": "", "anchor": "Tiền thuê"}
    f = import_csv(_write(tmp_path, [row]))[0]["frames"][0]
    assert f["gold_key"] == ["PARAM", "RENT", None]


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("action", "SHIP", "action"),
        ("bearer", "VENDOR", "bearer"),
        ("profile", "LOAN", "profile"),
        ("anchor", "không có trong câu", "anchor"),
        ("consequence_type", "FINE", "consequence_type"),
    ],
)
def test_import_rejects_invalid_labels(tmp_path, field, value, message):
    with pytest.raises(HeldoutError, match=message):
        import_csv(_write(tmp_path, [{**REMEDY, field: value}]))
