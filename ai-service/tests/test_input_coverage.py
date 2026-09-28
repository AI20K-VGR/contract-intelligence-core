import json
from pathlib import Path

from fastapi.testclient import TestClient

from app.api.main import app
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
from scripts.validate_input_coverage import validate_manifest


ROOT = Path(__file__).resolve().parents[1]


def test_input_coverage_manifest_validates_all_catalog_cases():
    result = validate_manifest()
    assert result["catalog_cases"] == 95
    assert result["valid_inputs"] == 7
    assert result["rejected_inputs"] == 4
    assert result["coverage_groups"] == 8


def test_explicit_not_present_table_is_a_valid_non_table_document():
    path = ROOT / "fixtures" / "eval_inputs" / "snapshots" / "ai1.no-table.v1.json"
    result = adapt_ai1_input(json.loads(path.read_text(encoding="utf-8")))
    assert result.meta["table_coverage"] == "NOT_PRESENT"
    assert result.record.tables == []
    assert not any(issue.code.startswith("TABLE_") for issue in result.record.handoff_issues)


def test_valid_coverage_snapshots_open_through_public_ai2_endpoint():
    manifest = json.loads(
        (ROOT / "fixtures" / "eval_inputs" / "manifest.json").read_text(encoding="utf-8")
    )
    client = TestClient(app)
    for item in manifest["input_files"]:
        if not item.get("valid") or item.get("kind") == "legacy_ocr_json":
            continue
        payload = json.loads((ROOT / item["path"]).read_text(encoding="utf-8"))
        response = client.post("/api/workspace/ai1-snapshot", json=payload)
        assert response.status_code == 200, (item["id"], response.text)


def test_no_table_snapshot_is_visible_as_not_present_in_workspace():
    payload = json.loads(
        (
            ROOT
            / "fixtures"
            / "eval_inputs"
            / "snapshots"
            / "ai1.no-table.v1.json"
        ).read_text(encoding="utf-8")
    )
    response = TestClient(app).post("/api/workspace/ai1-snapshot", json=payload)
    assert response.status_code == 200
    body = response.json()
    assert body["n_tables"] == 0
    assert body["table_coverage"] == {"NOT_PRESENT": 1}
