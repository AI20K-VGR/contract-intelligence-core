from __future__ import annotations

import copy
from pathlib import Path

import pytest


@pytest.fixture(autouse=True)
def isolated_approval_environment(monkeypatch):
    monkeypatch.delenv("CI", raising=False)


def _question(category="answerable"):
    return {"question_id": "test-1", "category": category, "text": "Giá trị?",
            "expected_state": "ANSWERED", "approval": None}


def test_unapproved_questions_are_not_executed_or_counted():
    from evals.eval_types.ai2_grounded_query.questions import report_questions

    report = report_questions([_question()], execute=lambda _: pytest.fail("unapproved question executed"))
    assert report["status"] == "pending_review"
    assert report["approved_count"] == 0
    assert report["categories"]["answerable"]["total"] == 0


def test_approval_is_bound_to_content_and_requires_reviewer_and_basis():
    from evals.scripts.approve_question import approve_question, is_approved

    question = _question()
    with pytest.raises(ValueError):
        approve_question(question, reviewer="", basis="checked")
    approved = approve_question(question, reviewer="human-test", basis="checked source")
    assert is_approved(approved)
    changed = copy.deepcopy(approved)
    changed["text"] = "Khác?"
    assert not is_approved(changed)


def test_complete_requires_ten_approved_questions_in_every_category():
    from evals.eval_types.ai2_grounded_query.questions import report_questions
    from evals.scripts.approve_question import approve_question

    questions = []
    for category in ("answerable", "not_in_document", "permission"):
        for i in range(10):
            question = {**_question(category), "question_id": f"{category}-{i}"}
            question["expected_state"] = {"answerable": "ANSWERED", "not_in_document": "INSUFFICIENT_EVIDENCE", "permission": "BLOCKED"}[category]
            questions.append(approve_question(question, reviewer="human-test", basis="fixture source"))
    def execute(question):
        return {"state": "ANSWERED" if question["category"] == "not_in_document" else question["expected_state"],
                "citations": [{"node_id": "source"}], "http_status": 200}
    report = report_questions(questions, execute=execute)
    assert report["status"] == "complete"
    assert report["categories"]["not_in_document"] == {"total": 10, "correct": 0, "incorrect": 10, "accuracy": 0.0}
    assert report_questions(questions[:-1], execute=execute)["status"] == "pending_review"


def test_candidates_have_three_categories_and_no_fabricated_approvals():
    from evals.eval_types.ai2_grounded_query.questions import load_questions

    path = Path(__file__).resolve().parents[1] / "golden/questions_v1.jsonl"
    questions = load_questions(path)
    assert len(questions) == 30
    assert len({question["question_id"] for question in questions}) == 30
    assert all(question["approval"] is None for question in questions)
    assert {category: sum(question["category"] == category for question in questions)
            for category in ("answerable", "not_in_document", "permission")} == {
                "answerable": 10, "not_in_document": 10, "permission": 10}


def test_permission_replay_calls_signed_api_boundary():
    from evals.eval_types.ai2_grounded_query.questions import execute_question

    root = Path(__file__).resolve().parents[2]
    question = {**_question("permission"), "source": "evals/data/golden/snapshots/G01.json",
                "permission_case": "wrong_dossier", "expected_state": "BLOCKED"}
    result = execute_question(question, root=root)
    assert result["production_entry"] == "POST /query"
    assert result["http_status"] == 401
    assert result["citations"] == []


def test_approval_cannot_be_written_in_ci(monkeypatch):
    from evals.scripts.approve_question import approve_question

    monkeypatch.setenv("CI", "true")
    with pytest.raises(ValueError, match="CI"):
        approve_question(_question(), reviewer="human", basis="checked")


def test_answered_state_alone_does_not_pass_wrong_value_or_citation():
    from evals.eval_types.ai2_grounded_query.questions import report_questions
    from evals.scripts.approve_question import approve_question

    question = {**_question(), "gold_values": [{"normalized": "100000"}],
                "required_spans": [{"line_ids": ["expected-line"]}]}
    approved = approve_question(question, reviewer="human-test", basis="source line")
    wrong = lambda _: {"state": "ANSWERED", "answer": "100.000", "citations": [{"node_id": "other-line"}]}
    assert report_questions([approved], execute=wrong)["categories"]["answerable"]["incorrect"] == 1
