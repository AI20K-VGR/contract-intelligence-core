from __future__ import annotations

import json
import re

from evals.scripts import candidate_review


def test_worksheet_is_blind_and_has_95_sources(tmp_path) -> None:
    output = tmp_path / "worksheet.md"
    rows = candidate_review.write_worksheet(output)
    assert len(rows) == 95
    text = output.read_text(encoding="utf-8")
    for row in rows:
        assert row["case_id"] in text
        assert row["source_sha256"] in text
        assert "expected_state" not in row
        assert "system_output" not in row
    assert "expected_state" not in text
    assert "system_output" not in text
    assert "| expected |" not in text.lower()
    cases = candidate_review._load_cases()
    for row in rows:
        rendered = next(line for line in text.splitlines() if line.startswith(f"| {row['case_id']} |"))
        old_label = cases[row["case_id"]].expected_state
        assert re.search(rf"\b{re.escape(old_label)}\b", rendered, flags=re.IGNORECASE) is None
    assert "app.pipeline.idp" not in __import__("sys").modules
    assert "app.reasoning.stack" not in __import__("sys").modules


def test_decisions_template_has_no_prefill(tmp_path) -> None:
    output = tmp_path / "decisions.json"
    decisions = candidate_review.init_decisions(output)
    assert len(decisions) == 95
    assert all(item["decision"] == "PENDING" for item in decisions)
    assert all(item["final_label"] is None for item in decisions)
    assert all(item["basis"] is None for item in decisions)
    assert json.loads(output.read_text(encoding="utf-8")) == decisions


def test_promote_requires_reviewer_and_basis_and_refuses_ci(tmp_path, monkeypatch) -> None:
    candidate_path = tmp_path / "candidate.json"
    golden_path = tmp_path / "golden.json"
    decisions_path = tmp_path / "decisions.json"
    candidate = json.loads(candidate_review.CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    golden_path.write_text('{"schema_version":"ai2.golden.manifest.v1","cases":[]}', encoding="utf-8")
    decisions = candidate_review.init_decisions(tmp_path / "blank.json")
    decisions[0].update(decision="APPROVE", final_label="PASS", basis="reviewed source")
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")

    monkeypatch.delenv("CI", raising=False)
    assert candidate_review.promote(decisions_path, candidate_path, golden_path, reviewer="") == 2
    decisions[0]["basis"] = None
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    assert candidate_review.promote(
        decisions_path, candidate_path, golden_path, reviewer="Reviewer A"
    ) == 2

    decisions[0]["basis"] = "reviewed source"
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")
    monkeypatch.setenv("CI", "true")
    assert candidate_review.promote(
        decisions_path, candidate_path, golden_path, reviewer="Reviewer A"
    ) == 2


def test_promote_is_idempotent_and_keeps_candidate_golden_separation(tmp_path, monkeypatch) -> None:
    from evals.release_verification import validate_corpus_separation

    candidate_path = tmp_path / "candidate.json"
    golden_path = tmp_path / "golden.json"
    decisions_path = tmp_path / "decisions.json"
    candidate = json.loads(candidate_review.CANDIDATE_MANIFEST.read_text(encoding="utf-8"))
    golden = json.loads(candidate_review.GOLDEN_MANIFEST.read_text(encoding="utf-8"))
    candidate_path.write_text(json.dumps(candidate), encoding="utf-8")
    golden_path.write_text(json.dumps(golden), encoding="utf-8")
    decisions = candidate_review.init_decisions(tmp_path / "blank.json")
    decisions[0].update(decision="APPROVE", final_label="PASS", basis="fixture review")
    decisions_path.write_text(json.dumps(decisions), encoding="utf-8")

    monkeypatch.delenv("CI", raising=False)
    assert candidate_review.promote(
        decisions_path, candidate_path, golden_path, reviewer="Reviewer A"
    ) == 0
    once_candidate = json.loads(candidate_path.read_text(encoding="utf-8"))
    once_golden = json.loads(golden_path.read_text(encoding="utf-8"))
    assert once_candidate["case_count"] == 94
    assert len(once_golden["cases"]) == 1
    assert once_golden["cases"][0]["validation_status"] == "GOLDEN"
    validate_corpus_separation(once_candidate, once_golden)

    assert candidate_review.promote(
        decisions_path, candidate_path, golden_path, reviewer="Reviewer A"
    ) == 0
    assert json.loads(candidate_path.read_text(encoding="utf-8")) == once_candidate
    assert json.loads(golden_path.read_text(encoding="utf-8")) == once_golden


def test_agreement_reports_known_accuracy_and_kappa() -> None:
    result = candidate_review.agreement_for_labels(
        ["A", "A", "B", "B"], ["A", "B", "A", "B"]
    )
    assert result["agreement"] == 0.5
    assert result["cohen_kappa"] == 0.0
    assert result["denominator"] == 4
