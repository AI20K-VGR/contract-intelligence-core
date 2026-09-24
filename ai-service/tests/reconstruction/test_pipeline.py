import pytest

from contract_ocr.reconstruction.llm_resolver import MockLLMResolver
from contract_ocr.reconstruction.models import (
    Action,
    EntityType,
    ReconstructionAction,
    Relationship,
    ResolutionMethod,
    ScoreBreakdown,
    SourceBlockRef,
)
from contract_ocr.reconstruction.pipeline import reconstruct_document, resolve_boundary

from .factories import make_block, make_page


def _llm_action(
    relationship: Relationship,
    confidence: float,
    action: Action = Action.MERGE_BLOCKS,
    entity_type: EntityType = EntityType.PARAGRAPH,
) -> ReconstructionAction:
    """Build a canned "LLM answer" `ReconstructionAction` for `MockLLMResolver`."""
    return ReconstructionAction(
        action=action,
        relationship=relationship,
        entity_type=entity_type,
        source_blocks=[SourceBlockRef(page=1, block_id="stub")],
        confidence=confidence,
        requires_review=False,
        method=ResolutionMethod.LLM,
        scores=ScoreBreakdown(model_score=confidence),
    )


def _running_header(block_id: str) -> object:
    return make_block(
        block_id, "ABC CORPORATION - CONFIDENTIAL", type="header", bbox=(100, 20, 1000, 60)
    )


def _page_number(block_id: str, page_no: int, total: int) -> object:
    return make_block(
        block_id, f"Page {page_no} of {total}", type="page_number", bbox=(700, 2280, 900, 2320)
    )


def _build_sample_document():
    """A small synthetic contract exercising cases 1, 2, 4, 7 and 10 in one
    pass: a paragraph split mid-sentence across pages 1/2, a new clause
    starting cleanly on page 3, a list continuing from page 3 into page 4,
    and running headers/footers/page numbers on every page."""
    page1 = make_page(
        "contract_001",
        1,
        [
            _running_header("p1_hdr"),
            make_block("p1_b01", "Điều 5. THANH TOÁN", type="heading", bbox=(100, 200, 1450, 270)),
            make_block(
                "p1_b02",
                "5.1 Bên mua phải thanh toán trong vòng",
                bbox=(100, 1700, 1450, 1870),
            ),
            _page_number("p1_pg", 1, 4),
        ],
    )
    page2 = make_page(
        "contract_001",
        2,
        [
            _running_header("p2_hdr"),
            make_block(
                "p2_b01", "30 ngày kể từ ngày nhận được hóa đơn hợp lệ.", bbox=(100, 200, 1450, 270)
            ),
            _page_number("p2_pg", 2, 4),
        ],
    )
    page3 = make_page(
        "contract_001",
        3,
        [
            _running_header("p3_hdr"),
            make_block("p3_b01", "5.2 Phương thức thanh toán", bbox=(100, 200, 1450, 270)),
            make_block("p3_b02", "(a) Chuyển khoản ngân hàng.", bbox=(100, 300, 1450, 360)),
            make_block("p3_b03", "(b) Tiền mặt tại văn phòng.", bbox=(100, 380, 1450, 440)),
            _page_number("p3_pg", 3, 4),
        ],
    )
    page4 = make_page(
        "contract_001",
        4,
        [
            _running_header("p4_hdr"),
            make_block("p4_b01", "(c) Séc bảo chi.", bbox=(100, 200, 1450, 260)),
            _page_number("p4_pg", 4, 4),
        ],
    )
    return [page1, page2, page3, page4]


def test_reconstruct_document_builds_expected_clause_tree():
    document = reconstruct_document(_build_sample_document())

    assert document.document_id == "contract_001"
    assert document.metadata.total_pages == 4

    assert len(document.sections) == 1
    section_5 = document.sections[0]
    assert section_5.clause_id == "5"
    assert section_5.title == "THANH TOÁN"

    clause_ids = [c.clause_id for c in section_5.children]
    assert clause_ids == ["5.1", "5.2"]

    clause_5_1 = section_5.children[0]
    assert clause_5_1.text == (
        "5.1 Bên mua phải thanh toán trong vòng 30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
    )
    assert clause_5_1.reconstruction.was_merged is True
    assert clause_5_1.page_start == 1
    assert clause_5_1.page_end == 2

    # Case 10: provenance survives the merge.
    source_pairs = {(ref.page, ref.block_id) for ref in clause_5_1.source_blocks}
    assert source_pairs == {(1, "p1_b02"), (2, "p2_b01")}

    clause_5_2 = section_5.children[1]
    assert [c.clause_id for c in clause_5_2.children] == ["5.2.a", "5.2.b", "5.2.c"]
    assert clause_5_2.children[2].page_start == 4

    # Case 7: header/footer/page-number text must never leak into clause text.
    for clause in document.clauses:
        assert "CONFIDENTIAL" not in clause.text
        assert "Page " not in clause.text


def test_reconstruct_document_is_idempotent():
    pages = _build_sample_document()
    first = reconstruct_document(pages)
    second = reconstruct_document(pages)
    assert first.model_dump() == second.model_dump()


def test_reconstruct_document_requires_at_least_one_page():
    with pytest.raises(ValueError):
        reconstruct_document([])


def test_ambiguous_boundary_is_not_merged_and_becomes_a_review_item():
    page1 = make_page(
        "doc2",
        1,
        [make_block("p1_b01", "Các bên đồng ý về nguyên tắc chung.", bbox=(100, 300, 1000, 360))],
    )
    page2 = make_page(
        "doc2",
        2,
        [make_block("p2_b01", "hợp tác lâu dài trong tương lai.", bbox=(100, 300, 1000, 360))],
    )

    document = reconstruct_document([page1, page2])

    assert len(document.review_items) == 1
    review = document.review_items[0]
    assert review.status == "NEEDS_REVIEW"
    assert review.previous_page == 1
    assert review.next_page == 2

    # Not merged means: paragraph_merger's character-level join (which could
    # e.g. drop a hyphen) never runs across this boundary, and both original
    # sentences stay fully intact and individually traceable — unlike
    # `test_reconstruct_document_builds_expected_clause_tree`'s clause 5.1,
    # no single `source_blocks` entry spans both pages here.
    all_texts = [c.text for c in document.clauses]
    assert not any("nguyên tắc chunghợp tác" in t for t in all_texts)
    assert any("Các bên đồng ý về nguyên tắc chung." in t for t in all_texts)
    assert any("hợp tác lâu dài trong tương lai." in t for t in all_texts)
    for clause in document.clauses:
        for ref in clause.source_blocks:
            assert ref.block_id in ("p1_b01", "p2_b01")


def test_llm_confirmation_can_tip_a_rule_uncertain_boundary_to_auto_accept():
    # The rule engine sees a clean mid-sentence split (no terminal
    # punctuation, lowercase continuation) but a typography mismatch, so it
    # is confident enough to propose CONTINUE_PARAGRAPH yet not confident
    # enough to auto-accept on its own (below the "strong" band). A
    # confirming LLM answer for the same relationship should be enough to
    # tip the blended confidence over the threshold.
    page1 = make_page(
        "doc2",
        1,
        [make_block("p1_b01", "Bên mua phải thanh toán trong vòng", font_size=11.0, bold=False)],
    )
    page2 = make_page(
        "doc2",
        2,
        [
            make_block(
                "p2_b01",
                "30 ngày kể từ ngày nhận được hóa đơn hợp lệ.",
                font_size=16.0,
                bold=True,
            )
        ],
    )
    resolver = MockLLMResolver({(1, 2): _llm_action(Relationship.CONTINUE_PARAGRAPH, 1.0)})

    document = reconstruct_document([page1, page2], llm_resolver=resolver)

    assert document.review_items == []
    clause_texts = [c.text for c in document.clauses]
    assert any(
        t == "Bên mua phải thanh toán trong vòng 30 ngày kể từ ngày nhận được hóa đơn hợp lệ."
        for t in clause_texts
    )


def test_ambiguous_boundary_with_no_rule_signal_stays_needs_review_even_with_llm():
    # When the rule engine has *zero* deterministic evidence (returns None),
    # the LLM's opinion alone — at most 10% of the blended score — can never
    # reach the "strong" threshold. This is deliberate: an LLM's
    # self-reported confidence is never trusted as the sole signal.
    page1 = make_page(
        "doc2",
        1,
        [make_block("p1_b01", "Các bên đồng ý về nguyên tắc chung.", bbox=(100, 300, 1000, 360))],
    )
    page2 = make_page(
        "doc2",
        2,
        [make_block("p2_b01", "hợp tác lâu dài trong tương lai.", bbox=(100, 300, 1000, 360))],
    )
    resolver = MockLLMResolver({(1, 2): _llm_action(Relationship.NEW_PARAGRAPH, 1.0)})

    document = reconstruct_document([page1, page2], llm_resolver=resolver)

    assert len(document.review_items) == 1


def test_resolve_boundary_public_api():
    page1 = make_page("doc3", 1, [make_block("p1_b01", "5.4 Bên B có nghĩa vụ")])
    page2 = make_page("doc3", 2, [make_block("p2_b01", "bàn giao sản phẩm đúng hạn.")])

    action = resolve_boundary(page1, page2)
    assert action.relationship == Relationship.CONTINUE_CLAUSE
    assert action.action == Action.MERGE_BLOCKS
    assert not action.requires_review
