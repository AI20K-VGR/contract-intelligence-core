"""Guardrails found by the live-LLM benchmark (2026-09-29)."""

import json
from pathlib import Path

import pytest

from app.pipeline.fact import FactExtractor
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures.catalog import PROFILE_V5, load_case

TASKS = {
    t["id"]: t
    for t in json.loads(
        (Path(__file__).resolve().parents[1] / "fixtures/reasoning/hd_tong_hop_tasks.json").read_text(encoding="utf-8")
    )
}


class EchoLLM:
    """Returns a fixed normalization and records whether it was asked."""

    def __init__(self, normalized):
        self.normalized = normalized
        self.calls = 0

    def configured(self):
        return True

    def complete_json(self, system, user, *, strong=False):
        self.calls += 1
        return {"normalized": self.normalized, "unit": None}


def _hd_stack():
    pack = load_case("HD-TONG-HOP")
    store = InMemorySnapshotStore()
    store.put(pack.record)
    return pack, FourLayerReasoner(ToolGateway(store))


@pytest.mark.parametrize("task_id", ["T-FX", "T-SCOPE", "T-TABLE300", "T-GAP3", "T-SUMMARY"])
def test_vector_policy_does_not_bypass_deterministic_rules(task_id):
    pack, stack = _hd_stack()
    task = TASKS[task_id]
    plain = stack.run(pack.envelope, dict(task))
    with_vector = stack.run(
        pack.envelope,
        {**task, "policy_flags": {"use_vector": True, "use_llm": False, "egress_allowed": False}},
    )

    assert with_vector["review_state"] == plain["review_state"] == task["expected_state"]


def test_vector_request_answered_by_rules_reports_not_needed():
    pack, stack = _hd_stack()
    out = stack.run(pack.envelope, {**TASKS["T-FX"], "policy_flags": {"use_vector": True}})

    assert out["layers_used"] == ["L0", "L3"]
    assert out["retrieval_trace"]["vector_status"] == "NOT_NEEDED"


@pytest.mark.parametrize("raw", ["1.000.•••", "????????", "MST không rõ", "không đọc được", "Giá: 12***"])
def test_masked_or_illegible_value_is_never_sent_for_normalization(raw):
    llm = EchoLLM("1000")
    norm, provenance = FactExtractor(gateway=None, llm=llm)._normalize(raw, raw, PROFILE_V5)

    assert norm is None and provenance == "L0"
    assert llm.calls == 0


@pytest.mark.parametrize(
    "raw,model_output",
    [
        ("Phụ lục 9", "Appendix 9"),
        ("trong vòng ba mươi ngày kể từ ngày ký", "30 days from the date of signing"),
        ("giá 105 nghìn", "150000"),
    ],
)
def test_translated_or_invented_normalization_is_rejected(raw, model_output):
    norm, provenance = FactExtractor(gateway=None, llm=EchoLLM(model_output))._normalize(raw, raw, PROFILE_V5)

    assert norm is None and provenance == "L0"


@pytest.mark.parametrize(
    "raw,model_output",
    [
        ("trong vòng ba mươi ngày kể từ ngày ký", "30 ngày kể từ ngày ký"),
        ("Cong ty ABC", "Công ty ABC"),
        ("15 days", "15"),
    ],
)
def test_grounded_normalization_is_kept(raw, model_output):
    norm, provenance = FactExtractor(gateway=None, llm=EchoLLM(model_output))._normalize(raw, raw, PROFILE_V5)

    assert (norm, provenance) == (model_output, "L2")
