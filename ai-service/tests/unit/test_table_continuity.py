"""Section 11: cross-page table continuity -- hard guards -> deterministic score ->
optional DeepSeek gray-zone agent -> merge/split/needs_review. With the agent
disabled (the default), a genuinely ambiguous pair must land on NEEDS_REVIEW, never
a guess."""

import pytest

from contract_ocr.application.use_cases import table_continuity as table_continuity_module
from contract_ocr.application.use_cases.table_continuity import link_continuities
from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Cell, Row, Table


def _table(
    table_id: str,
    header: list[str],
    y1: float,
    y2: float,
    n_data_rows: int = 1,
    *,
    row_texts: list[list[str]] | None = None,
    heading_before: str | None = None,
) -> Table:
    cols = len(header)
    if row_texts is not None:
        rows = [Row(cells=[Cell(text=t) for t in texts]) for texts in row_texts]
    else:
        rows = [Row(cells=[Cell(text=f"v{r}{c}") for c in range(cols)]) for r in range(n_data_rows)]
    return Table(
        table_id=table_id,
        bbox=BBox(x1=0.1, y1=y1, x2=0.9, y2=y2),
        geometry_provenance="MEASURED",
        header=header,
        rows=rows,
        heading_before=heading_before,
    )


def test_matching_columns_at_page_edges_with_repeated_header_merges():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)  # bottom of page 1
    nxt = _table("t2", header, y1=0.05, y2=0.4)  # top of page 2
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert len(links) == 1
    link = links[0]
    assert link.decision == "MERGE"
    assert link.from_table_id == "t1" and link.to_table_id == "t2"
    assert "REPEATED_TABLE_HEADER" in link.reason_codes


def test_matching_columns_at_edges_without_repeated_header_is_needs_review():
    prev = _table("t1", ["STT", "Ten hang", "So luong"], y1=0.5, y2=0.9)
    nxt = _table("t2", ["", "", ""], y1=0.05, y2=0.4)  # continuation page: no header row
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"
    assert "INSUFFICIENT_EVIDENCE" in links[0].reason_codes


def test_incompatible_column_count_splits():
    prev = _table("t1", ["STT", "Ten hang", "So luong"], y1=0.5, y2=0.9)
    nxt = _table("t2", ["Ma so", "Gia tri"], y1=0.05, y2=0.4)
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert links[0].confidence == 1.0
    assert "INCOMPATIBLE_COLUMN_SCHEMA" in links[0].reason_codes


def test_tables_not_near_page_edges_split_even_with_matching_columns():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.3, y2=0.5)  # mid-page, not near bottom
    nxt = _table("t2", header, y1=0.4, y2=0.6)  # mid-page, not near top
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert "NOT_AT_PAGE_EDGES" in links[0].reason_codes


def test_non_adjacent_pages_produce_no_link():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4)
    # A table-less page 2 sits between them -- page 3's table must not be compared
    # against page 1's as if they were adjacent.
    links = link_continuities([(1, [prev]), (2, []), (3, [nxt])])
    assert links == []


def test_two_tables_on_the_same_page_do_not_self_link():
    header = ["STT", "Ten hang", "So luong"]
    t1 = _table("t1", header, y1=0.1, y2=0.3)
    t2 = _table("t2", header, y1=0.5, y2=0.9)
    links = link_continuities([(1, [t1, t2])])
    assert links == []


def test_missing_geometry_is_needs_review_not_a_guess():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4)
    nxt = nxt.model_copy(update={"bbox": None, "geometry_provenance": None})
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"
    assert "MISSING_GEOMETRY" in links[0].reason_codes
    assert links[0].confidence == 0.0


# --- Tier 1: additional hard guards (backend/app/table_continuity.py parity) --------


def test_previous_table_already_totaled_always_splits():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table(
        "t1", header, y1=0.5, y2=0.9, row_texts=[["1", "Item one", "2"], ["", "Tổng cộng", "10"]]
    )
    nxt = _table("t2", header, y1=0.05, y2=0.4)
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert links[0].confidence == 1.0
    assert "PREVIOUS_TABLE_ALREADY_TOTALED" in links[0].reason_codes


def test_annex_heading_between_splits_even_with_perfect_score():
    # Real case: two annexes with an identical item-table header and geometry -- every
    # other signal says MERGE, but "Phụ lục 02" right above the second table means
    # this is a new table, not a continuation.
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4, heading_before="Phụ lục 02")
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert "NEW_SECTION_HEADING" in links[0].reason_codes


def test_unrelated_text_before_is_not_treated_as_a_heading():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4, heading_before="Ghi chú: giao hàng trong 7 ngày")
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision != "SPLIT" or "NEW_SECTION_HEADING" not in links[0].reason_codes


def test_anchor_reset_splits():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9, row_texts=[["12", "Item twelve", "1"]])
    nxt = _table("t2", header, y1=0.05, y2=0.4, row_texts=[["1", "Item one", "1"]])
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "SPLIT"
    assert "ANCHOR_RESET" in links[0].reason_codes


# --- Tier 2: leading-column sequence-number continuity as a scoring signal ----------


def test_anchor_continuity_merges_even_without_a_repeated_header():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9, row_texts=[["5", "Item five", "1"]])
    # Continuation page: no header row, but STT picks up right where page 1 left off.
    nxt = _table("t2", ["", "", ""], y1=0.05, y2=0.4, row_texts=[["6", "Item six", "1"]])
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "MERGE"
    assert "ANCHOR_CONTINUOUS" in links[0].reason_codes


def test_non_sequential_anchor_gets_no_bonus_but_does_not_split():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9, row_texts=[["5", "Item five", "1"]])
    nxt = _table("t2", ["", "", ""], y1=0.05, y2=0.4, row_texts=[["9", "Item nine", "1"]])
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"
    assert "ANCHOR_CONTINUOUS" not in links[0].reason_codes


# --- Tier 3: DeepSeek gray-zone agent, opt-in via config -----------------------------


def _gray_zone_pair():
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", ["", "", ""], y1=0.05, y2=0.4)  # no repeated header, no anchor -> 0.6
    return prev, nxt


def test_high_score_merges_without_consulting_agent(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when the rule score already merges")

    monkeypatch.setattr(table_continuity_module, "_ask_agent", boom)
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", header, y1=0.05, y2=0.4)  # repeated header -> 0.8, MERGE
    links = link_continuities([(1, [prev]), (2, [nxt])], config={"table_continuity_agent": True})
    assert links[0].decision == "MERGE"


def test_low_score_splits_without_consulting_agent(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when a hard guard already splits")

    monkeypatch.setattr(table_continuity_module, "_ask_agent", boom)
    header = ["STT", "Ten hang", "So luong"]
    prev = _table("t1", header, y1=0.5, y2=0.9)
    nxt = _table("t2", ["Ma so", "Gia tri"], y1=0.05, y2=0.4)  # incompatible schema -> SPLIT
    links = link_continuities([(1, [prev]), (2, [nxt])], config={"table_continuity_agent": True})
    assert links[0].decision == "SPLIT"


def test_gray_zone_without_agent_needs_review():
    prev, nxt = _gray_zone_pair()
    links = link_continuities([(1, [prev]), (2, [nxt])])
    assert links[0].decision == "NEEDS_REVIEW"


def test_gray_zone_agent_disabled_by_config_needs_review(monkeypatch):
    def boom(*a, **k):
        raise AssertionError("agent must not be consulted when config disables it")

    monkeypatch.setattr(table_continuity_module, "_ask_agent", boom)
    prev, nxt = _gray_zone_pair()
    links = link_continuities([(1, [prev]), (2, [nxt])], config={"table_continuity_agent": False})
    assert links[0].decision == "NEEDS_REVIEW"


@pytest.mark.parametrize("decision", ["MERGE", "SPLIT", "NEEDS_REVIEW"])
def test_gray_zone_agent_enabled_uses_agent_decision(monkeypatch, decision):
    monkeypatch.setattr(
        table_continuity_module, "_ask_agent", lambda payload: (decision, ["agent_reason"])
    )
    prev, nxt = _gray_zone_pair()
    links = link_continuities([(1, [prev]), (2, [nxt])], config={"table_continuity_agent": True})
    assert links[0].decision == decision
    assert "AGENT_CONSULTED" in links[0].reason_codes
    assert "agent_reason" in links[0].reason_codes


def test_gray_zone_agent_unavailable_falls_back_to_needs_review(monkeypatch):
    monkeypatch.setattr(table_continuity_module, "_ask_agent", lambda payload: None)
    prev, nxt = _gray_zone_pair()
    links = link_continuities([(1, [prev]), (2, [nxt])], config={"table_continuity_agent": True})
    assert links[0].decision == "NEEDS_REVIEW"
    assert "AGENT_CONSULTED" not in links[0].reason_codes


# --- _ask_agent itself: never raises, degrades to None -------------------------------


def test_ask_agent_returns_none_without_an_api_key(monkeypatch):
    monkeypatch.delenv("DEEPSEEK_API_KEY", raising=False)
    assert table_continuity_module._ask_agent({}) is None


def test_ask_agent_returns_none_on_client_failure(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")

    class BoomClient:
        def __init__(self, *a, **k):
            raise RuntimeError("network unavailable")

    monkeypatch.setattr("openai.OpenAI", BoomClient)
    assert table_continuity_module._ask_agent({}) is None


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
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    captured = {}
    content = '{"decision": "merge", "reasons": ["anchor continues"]}'
    monkeypatch.setattr("openai.OpenAI", _fake_openai_client(content, capture=captured))

    result = table_continuity_module._ask_agent({"page_gap": 1})

    assert result == ("MERGE", ["anchor continues"])
    assert captured["response_format"] == {"type": "json_object"}


def test_ask_agent_returns_none_on_malformed_json(monkeypatch):
    monkeypatch.setenv("DEEPSEEK_API_KEY", "sk-test")
    monkeypatch.setattr("openai.OpenAI", _fake_openai_client("not json"))
    assert table_continuity_module._ask_agent({}) is None
