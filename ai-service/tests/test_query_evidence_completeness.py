from __future__ import annotations

from app.reasoning.l1_retrieval import expand_logical_tables
from app.reasoning.l2_plan import L2Planner, _grounded_user_prompt
from fixtures import envelope


class ScheduleGateway:
    def __init__(self, rows, total_rows=None):
        self.rows = rows
        self.total_rows = len(rows) if total_rows is None else total_rows
        self.requested_end = None

    def call(self, tool, _envelope, **kwargs):
        if tool == "list_tables":
            return [{"table_id": "payments", "n_rows": self.total_rows, "n_cols": 3}]
        if tool == "get_table_meta":
            return {
                "table_id": "payments",
                "header": ["Đợt", "Tỷ lệ", "Mốc thanh toán"],
                "n_rows": self.total_rows,
                "n_cols": 3,
                "source_role": "annex",
            }
        if tool == "get_table_rows":
            self.requested_end = kwargs["end"]
            return self.rows[kwargs["start"] : kwargs["end"]]
        raise AssertionError(tool)


def _rows(count=5):
    return [
        {
            "row_index": index,
            "cells": [f"M{index + 1}", "20%", f"Trigger {index + 1}"],
            "cell_citations": {
                "1": {
                    "node_id": f"table-{index}",
                    "page_revision_id": f"page-{index + 1}",
                    "text_span": "20%",
                    "table_id": "payments",
                    "cell_id": f"row-{index}-percent",
                }
            },
        }
        for index in range(count)
    ]


def test_full_payment_schedule_keeps_every_row_identity_and_cell_citation():
    gateway = ScheduleGateway(_rows())

    tables = expand_logical_tables(gateway, envelope(), "So sánh lịch thanh toán")

    assert len(tables) == 1
    assert tables[0]["coverage"] == {
        "complete": True,
        "source_rows": 5,
        "processed_rows": 5,
        "source_cells": 15,
        "processed_cells": 15,
        "reason": None,
    }
    assert [row["cells"][0] for row in tables[0]["rows"]] == ["M1", "M2", "M3", "M4", "M5"]
    assert tables[0]["rows"][4]["cell_citations"]["1"]["cell_id"] == "row-4-percent"


def test_row_cap_is_explicit_and_does_not_claim_the_source_lacks_m5():
    gateway = ScheduleGateway(_rows(), total_rows=7)

    tables = expand_logical_tables(gateway, envelope(), "Payment schedule", max_rows=4)

    assert gateway.requested_end == 4
    assert tables[0]["coverage"]["complete"] is False
    assert tables[0]["coverage"]["source_rows"] == 7
    assert tables[0]["coverage"]["processed_rows"] == 4
    assert "cap" in tables[0]["coverage"]["reason"]
    assert all("absent" not in row.get("reason", "").lower() for row in tables[0]["rows"])


def test_llm_evidence_prompt_preserves_all_five_milestones_as_one_logical_table():
    table = expand_logical_tables(ScheduleGateway(_rows()), envelope(), "Payment schedule")[0]

    prompt = _grounded_user_prompt(
        {"query": "Tóm tắt lịch thanh toán", "type": "compare"},
        [{"tool": "get_table_rows", "ok": True, "result": table}],
    )

    assert all(f"M{index}" in prompt for index in range(1, 6))
    assert "'complete': True" in prompt


class DraftLLM:
    def __init__(self, answer):
        self.answer = answer

    def configured(self):
        return True

    def complete_json(self, _system, _user):
        return {
            "answer": self.answer,
            "citations": [{"node_id": "table-0", "text_span": "20%"}],
            "sufficient": True,
            "legal_winner": False,
        }


class InvalidDraftLLM(DraftLLM):
    def complete_json(self, _system, _user):
        return {"answer": "untrusted", "citations": "not a list", "sufficient": True}


class PlanningGateway:
    ALLOWLIST = {"list_structure"}
    store = None

    def call(self, tool, _envelope, **_kwargs):
        assert tool == "list_structure"
        return []


def test_schema_valid_answer_missing_m5_is_downgraded_to_insufficient():
    table = expand_logical_tables(ScheduleGateway(_rows()), envelope(), "Payment schedule")[0]
    planner = L2Planner(PlanningGateway(), DraftLLM("M1, M2, M3, and M4 are listed."))

    result = planner.run(
        envelope(),
        {"query": "Summarize the full payment schedule", "type": "compare"},
        {"hits": [], "logical_tables": [table]},
    )

    assert result["draft"]["sufficient"] is False
    assert result["llm_called"] is True


def test_invalid_draft_shape_falls_back_without_trusting_claimed_sufficiency():
    planner = L2Planner(PlanningGateway(), InvalidDraftLLM("bad"))

    result = planner.run(
        envelope(),
        {"query": "Compare two payment clauses", "type": "compare"},
        {"hits": [], "logical_tables": []},
    )

    assert result["fallback"] is True
    assert result["llm_called"] is True
