import pytest

from app import table_continuity
from app.table_continuity import ContinuityDecision, ContinuityEvidence, ContinuityResult, decide


def evidence(**overrides):
    base = dict(
        same_document=True,
        page_a=1,
        page_b=2,
        column_similarity=1.0,
        header_similarity=1.0,
        last_anchor=5,
        first_anchor=6,
        anchor_continuous=True,
        previous_ends_near_bottom=True,
        next_starts_near_top=True,
        previous_ends_with_total=False,
        heading_between=None,
        previous_tail_rows=["04 | Item four"],
        next_head_rows=["06 | Item six"],
    )
    base.update(overrides)
    return ContinuityEvidence(**base)


# --- Tier 1: hard guards -----------------------------------------------------------


def test_different_document_always_splits():
    result = decide(evidence(same_document=False), {})
    assert result.decision == ContinuityDecision.SPLIT
    assert "different_document" in result.reasons


def test_non_adjacent_pages_always_splits():
    result = decide(evidence(page_a=1, page_b=3), {})
    assert result.decision == ContinuityDecision.SPLIT
    assert "non_adjacent_pages" in result.reasons


def test_previous_table_already_totaled_always_splits():
    result = decide(evidence(previous_ends_with_total=True), {})
    assert result.decision == ContinuityDecision.SPLIT
    assert "previous_table_already_totaled" in result.reasons


def test_annex_heading_between_splits_even_with_perfect_score():
    # Real case: two annexes with an identical item-table header and geometry -- every
    # other signal says MERGE, but "Phụ lục 02" between them means this is a new table.
    result = decide(evidence(heading_between="Phụ lục 02"), {})
    assert result.decision == ContinuityDecision.SPLIT
    assert "new_section_heading" in result.reasons


def test_diacritic_stripped_heading_still_detected():
    result = decide(evidence(heading_between="DIEU 5. Bao hanh"), {})
    assert result.decision == ContinuityDecision.SPLIT


def test_unrelated_text_between_is_not_treated_as_a_heading():
    result = decide(evidence(heading_between="Ghi chú: giao hàng trong 7 ngày"), {})
    assert result.decision != ContinuityDecision.SPLIT


def test_anchor_reset_splits():
    result = decide(
        evidence(last_anchor=12, first_anchor=1, anchor_continuous=False), {}
    )
    assert result.decision == ContinuityDecision.SPLIT
    assert "anchor_reset" in result.reasons


# --- Tier 2: deterministic rule engine ----------------------------------------------


def test_high_score_merges_without_consulting_agent(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when the rule score already merges")

    monkeypatch.setattr(table_continuity, "_ask_agent", boom)
    result = decide(evidence(), {"table_continuity_agent": True})
    assert result.decision == ContinuityDecision.MERGE
    assert result.used_agent is False
    assert result.rule_score >= table_continuity._MERGE_SCORE_FLOOR


def test_low_score_splits_without_consulting_agent(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when the rule score already splits")

    monkeypatch.setattr(table_continuity, "_ask_agent", boom)
    result = decide(
        evidence(
            column_similarity=0.4,
            header_similarity=0.0,
            anchor_continuous=None,
            last_anchor=None,
            first_anchor=None,
            previous_ends_near_bottom=False,
            next_starts_near_top=False,
        ),
        {"table_continuity_agent": True},
    )
    assert result.decision == ContinuityDecision.SPLIT
    assert result.rule_score <= table_continuity._SPLIT_SCORE_CEILING


def _gray_zone_evidence():
    # column_similarity(+3) + no_header_on_continuation(+2) = 5: real case, a
    # continuation row with no STT and no repeated header -- neither confidently
    # mergeable nor splittable by geometry/header alone.
    return evidence(
        header_similarity=None,
        anchor_continuous=None,
        last_anchor=5,
        first_anchor=None,
        previous_ends_near_bottom=False,
        next_starts_near_top=False,
    )


def test_gray_zone_without_agent_needs_review():
    result = decide(_gray_zone_evidence(), {})
    assert result.decision == ContinuityDecision.NEEDS_REVIEW
    assert result.used_agent is False


def test_gray_zone_agent_disabled_by_config_needs_review(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when config disables it")

    monkeypatch.setattr(table_continuity, "_ask_agent", boom)
    result = decide(_gray_zone_evidence(), {"table_continuity_agent": False})
    assert result.decision == ContinuityDecision.NEEDS_REVIEW


@pytest.mark.parametrize("decision", [ContinuityDecision.MERGE, ContinuityDecision.SPLIT,
                                       ContinuityDecision.NEEDS_REVIEW])
def test_gray_zone_agent_enabled_uses_agent_decision(monkeypatch, decision):
    monkeypatch.setattr(
        table_continuity, "_ask_agent",
        lambda ev, score: ContinuityResult(decision, ["agent_reason"], score, True),
    )
    result = decide(_gray_zone_evidence(), {"table_continuity_agent": True})
    assert result.decision == decision
    assert result.used_agent is True
    assert result.reasons == ["agent_reason"]


def test_gray_zone_agent_unavailable_falls_back_to_needs_review(monkeypatch):
    monkeypatch.setattr(table_continuity, "_ask_agent", lambda ev, score: None)
    result = decide(_gray_zone_evidence(), {"table_continuity_agent": True})
    assert result.decision == ContinuityDecision.NEEDS_REVIEW
    assert result.used_agent is False


# --- _ask_agent itself: never raises, degrades to None ------------------------------


def test_ask_agent_returns_none_without_an_api_key(monkeypatch):
    monkeypatch.setattr(table_continuity.settings, "deepseek_api_key", "")
    assert table_continuity._ask_agent(_gray_zone_evidence(), 5) is None


def test_ask_agent_returns_none_on_client_failure(monkeypatch):
    monkeypatch.setattr(table_continuity.settings, "deepseek_api_key", "sk-test")

    class BoomClient:
        def __init__(self, *a, **k):
            raise RuntimeError("network unavailable")

    monkeypatch.setattr("openai.OpenAI", BoomClient)
    assert table_continuity._ask_agent(_gray_zone_evidence(), 5) is None


def _fake_openai_client(content, *, capture=None):
    class FakeCompletions:
        def create(self, **kwargs):
            if capture is not None:
                capture.update(kwargs)
            return FakeResponse()

    class FakeResponse:
        choices = [type("Choice", (), {"message": type("Message", (), {"content": content})()})]

    class FakeClient:
        def __init__(self, *a, **k):
            self.chat = type("Chat", (), {"completions": FakeCompletions()})()

    return FakeClient


def test_ask_agent_parses_a_well_formed_response(monkeypatch):
    monkeypatch.setattr(table_continuity.settings, "deepseek_api_key", "sk-test")
    captured = {}
    content = '{"decision": "merge", "reasons": ["anchor continues"], "blocking_reason": null}'
    monkeypatch.setattr("openai.OpenAI", _fake_openai_client(content, capture=captured))

    result = table_continuity._ask_agent(_gray_zone_evidence(), 5)

    assert result == ContinuityResult(ContinuityDecision.MERGE, ["anchor continues"], 5, True)
    assert captured["response_format"] == {"type": "json_object"}


def test_ask_agent_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setattr(table_continuity.settings, "deepseek_api_key", "sk-test")
    monkeypatch.setattr("openai.OpenAI", _fake_openai_client("not json"))
    assert table_continuity._ask_agent(_gray_zone_evidence(), 5) is None
