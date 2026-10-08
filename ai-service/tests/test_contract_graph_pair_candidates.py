from __future__ import annotations

import copy

import pytest

from app.contracts.models import StructuralNode
from app.pipeline.contract_graph import pair_candidates as pc
from app.pipeline.contract_graph.pair_candidates import (
    PairSource,
    clause_context,
    generate_pair_candidates,
    topic_of,
)
from app.pipeline.contract_graph.resolver import StructureIndex

LONG = " với đầy đủ nội dung để vượt ngưỡng độ dài tối thiểu"


def _node(node_id, label, parent=None, *, text="", kind="CLAUSE", file="f-body"):
    return StructuralNode(
        node_id=node_id, type=kind, raw_label=label, parent_id=parent, text=text,
        source_file_id=file,
    )


def _build(nodes):
    for order, node in enumerate(nodes):
        node.order = order
    return nodes, StructureIndex.build(nodes, {"f-body": "body"})


def _pairs(result, source=None):
    return {
        (c.node_a, c.node_b)
        for c in result.candidates
        if source is None or source in c.sources
    }


def _contract():
    return _build([
        _node("d1", "Điều 1", text="Hàng hóa và số lượng"),
        _node("d1k1", "1.", "d1", text="Bên B cung cấp máy phát điện" + LONG),
        _node("d1k2", "2.", "d1", text="Số lượng giao theo đơn đặt hàng" + LONG),
        _node("d2", "Điều 2", text="Thanh toán"),
        _node("d2k1", "1.", "d2", text="Bên A trả trước 30% giá trị hợp đồng" + LONG),
        _node("d2k2", "2.", "d2", text="Phần còn lại trả trong 15 ngày sau nghiệm thu" + LONG),
        _node("d3", "Điều 3", text="Quyền và nghĩa vụ của các bên"),
        _node("d3k1", "1.", "d3", text="Bên B có nghĩa vụ thanh toán phí vận chuyển khi giao" + LONG),
        _node("d4", "Điều 4", text="Phạt vi phạm"),
        _node("d4k1", "1.", "d4",
              text="Chậm thanh toán theo khoản 2 Điều 2 của Hợp đồng này bị phạt 8%" + LONG),
        _node("d4k2", "2.", "d4", text="Các trường hợp nêu trên không áp dụng khi bất khả kháng"),
    ])


def test_clause_context_inherits_article_heading_and_lead():
    nodes, index = _build([
        _node("d5", "Điều 5", text="Giao hàng"),
        _node("d5k1", "1.", "d5", text="Bên B giao hàng theo các điều kiện sau:"),
        _node("d5k1a", "a)", "d5k1", text="Tại kho Bên A trong giờ hành chính" + LONG),
    ])
    context = clause_context(index, {n.node_id: n for n in nodes}, "d5k1a")
    assert "Điều 5. Giao hàng" in context
    assert "Bên B giao hàng theo các điều kiện sau" in context
    assert "Tại kho" not in context
    assert len(context) <= pc.CONTEXT_CHARS_MAX


def test_topic_from_heading_before_text():
    assert topic_of("Điều 2. Thanh toán", "Bên B giao hàng trong 10 ngày") == "PAYMENT"
    assert topic_of("", "Bên B giao hàng trong 10 ngày") == "DELIVERY"
    assert topic_of("", "Nội dung không có chủ đề nào") is None


def test_rights_and_obligations_is_not_a_topic():
    assert topic_of("Điều 3. Quyền và nghĩa vụ của các bên", "Bên A có quyền kiểm tra") is None
    assert topic_of("Điều 3. Quyền và nghĩa vụ", "Bên A thanh toán đúng hạn") == "PAYMENT"


def test_same_article_pairs():
    nodes, index = _contract()
    found = _pairs(generate_pair_candidates(index, nodes), PairSource.SAME_ARTICLE)
    assert ("d2k1", "d2k2") in found
    assert ("d1k1", "d1k2") in found
    assert ("d1k1", "d2k1") not in found


def test_explicit_ref_resolves_clause_level():
    nodes, index = _contract()
    found = _pairs(generate_pair_candidates(index, nodes), PairSource.EXPLICIT_REF)
    assert ("d2k2", "d4k1") in found
    assert ("d2", "d4k1") not in found


@pytest.mark.parametrize(
    "ref",
    [
        "khoản 2 Điều 2 Luật Thương mại 2005",
        "Điều 2 Luật Thương mại",
        "khoản 1 Điều 2 Nghị định số 37/2015/NĐ-CP",
        "Điều 2 Bộ luật Dân sự",
    ],
)
def test_explicit_ref_to_external_law_dropped(ref):
    nodes, index = _contract()
    nodes[9].text = f"Mức phạt áp dụng theo {ref} khi chậm trả tiền" + LONG
    result = generate_pair_candidates(index, nodes)
    assert not {p for p in _pairs(result, PairSource.EXPLICIT_REF) if "d4k1" in p}
    assert result.stats["excluded_external_ref"] >= 1


def test_explicit_ref_to_this_contract_kept():
    nodes, index = _contract()
    result = generate_pair_candidates(index, nodes)
    assert ("d2k2", "d4k1") in _pairs(result, PairSource.EXPLICIT_REF)
    assert result.stats["excluded_external_ref"] == 0


def test_same_key_across_articles():
    nodes, index = _contract()
    found = _pairs(generate_pair_candidates(index, nodes), PairSource.SAME_KEY)
    assert ("d2k1", "d3k1") in found  # PAYMENT heading ↔ PAYMENT text under "Quyền và nghĩa vụ"
    assert ("d2k1", "d2k2") not in found  # same article is SAME_ARTICLE, not SAME_KEY


def test_reference_cue_links_nearest_preceding_same_topic():
    nodes, index = _build([
        _node("d1", "Điều 1", text="Phạt vi phạm"),
        _node("d1k1", "1.", "d1", text="Chậm giao hàng bị phạt 0,5% mỗi ngày" + LONG),
        _node("d2", "Điều 2", text="Giao hàng"),
        _node("d2k1", "1.", "d2", text="Giao hàng tại kho Bên A" + LONG),
        _node("d3", "Điều 3", text="Phạt vi phạm bổ sung"),
        _node("d3k1", "1.", "d3", text="Ngoài các mức phạt nêu trên, Bên B bồi thường thiệt hại"),
    ])
    found = _pairs(generate_pair_candidates(index, nodes), PairSource.REFERENCE_CUE)
    assert ("d1k1", "d3k1") in found
    assert ("d2k1", "d3k1") not in found


def test_reference_cue_with_numeric_address_is_explicit_not_cue():
    nodes, index = _contract()
    nodes[9].text = "Mức phạt nêu trên tại khoản 2 Điều 2 áp dụng khi chậm thanh toán" + LONG
    result = generate_pair_candidates(index, nodes)
    by_pair = {(c.node_a, c.node_b): c.sources for c in result.candidates}
    assert PairSource.EXPLICIT_REF in by_pair[("d2k2", "d4k1")]
    # a cue links the cue node (later) to earlier nodes: none may start from d4k1
    assert not any(PairSource.REFERENCE_CUE in s for (_, b), s in by_pair.items() if b == "d4k1")


def test_luong1_pairs_excluded():
    nodes, index = _contract()
    result = generate_pair_candidates(index, nodes, excluded_pairs=frozenset({("d4k1", "d2k2")}))
    assert ("d2k2", "d4k1") not in _pairs(result)
    assert result.stats["excluded_luong1"] == 1


def test_ancestor_descendant_excluded():
    nodes, index = _contract()
    nodes[3].text = "Thanh toán theo các khoản dưới đây" + LONG
    found = _pairs(generate_pair_candidates(index, nodes))
    assert ("d2", "d2k1") not in found and ("d2", "d2k2") not in found


def test_field_table_and_short_nodes_skipped():
    nodes, index = _build([
        _node("d1", "Điều 1", text="Thanh toán"),
        _node("d1k1", "1.", "d1", text="Bên A thanh toán bằng chuyển khoản" + LONG),
        _node("d1k2", "2.", "d1", text="Ngắn"),
        _node("f1", "Giá", "d1", text="Đơn giá thanh toán 100.000 đồng mỗi đơn vị", kind="FIELD"),
        _node("t1", "Bảng", "d1", text="Bảng thanh toán theo đợt giao hàng hằng tháng", kind="TABLE"),
        _node("d1k3", "3.", "d1", text="Bên A thanh toán trong 15 ngày làm việc" + LONG),
    ])
    result = generate_pair_candidates(index, nodes)
    ids = {n for p in _pairs(result) for n in p}
    assert ids.isdisjoint({"d1k2", "f1", "t1", "d1"})
    assert result.stats["excluded_short"] >= 2  # "Ngắn" and the heading-only article


def test_scores_and_order():
    nodes, index = _contract()
    result = generate_pair_candidates(index, nodes)
    by_pair = {(c.node_a, c.node_b): c for c in result.candidates}
    assert by_pair[("d2k1", "d2k2")].score == pc.WEIGHTS[PairSource.SAME_ARTICLE] + 1 + (
        pc.WEIGHTS[PairSource.SAME_KEY] if PairSource.SAME_KEY in by_pair[("d2k1", "d2k2")].sources
        else 0
    )
    explicit = by_pair[("d2k2", "d4k1")]
    assert explicit.score >= pc.WEIGHTS[PairSource.EXPLICIT_REF]
    keys = [(-c.score, index.position(c.node_a), index.position(c.node_b))
            for c in result.candidates]
    assert keys == sorted(keys)


def test_body_annex_bonus():
    nodes, index = _build([
        _node("d1", "Điều 1", text="Giá"),
        _node("d1k1", "1.", "d1", text="Đơn giá máy phát điện theo Phụ lục 01" + LONG),
        _node("pl1", "Phụ lục 01", text="Bảng giá"),
        _node("pl1k1", "1.", "pl1", text="Đơn giá máy phát điện 500 triệu đồng" + LONG),
    ])
    result = generate_pair_candidates(index, nodes)
    by_pair = {(c.node_a, c.node_b): c for c in result.candidates}
    pair = by_pair[("d1k1", "pl1k1")]
    base = sum(pc.WEIGHTS[s] for s in pair.sources)
    assert pair.score == base + 1


def test_top_k_cap_counts_capped():
    nodes, index = _contract()
    full = generate_pair_candidates(index, nodes, top_k=10**6)
    capped = generate_pair_candidates(index, nodes, top_k=2)
    assert len(capped.candidates) == 2
    assert capped.candidates == full.candidates[:2]
    assert capped.stats["candidates_total"] == len(full.candidates)
    assert capped.stats["candidates_capped"] == len(full.candidates) - 2
    assert capped.stats["candidates_kept"] == 2


def test_sources_filter_for_variant_b():
    nodes, index = _contract()
    variant_b = {PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF}
    result = generate_pair_candidates(index, nodes, sources=frozenset(variant_b))
    assert all(c.sources <= variant_b for c in result.candidates)
    assert set(result.stats["candidates_by_source"]) <= {s.value for s in variant_b}


def test_deterministic_and_no_mutation():
    nodes, index = _contract()
    before = copy.deepcopy([n.model_dump() for n in nodes])
    first = generate_pair_candidates(index, nodes)
    second = generate_pair_candidates(index, list(reversed(nodes)))
    assert first == second
    assert [n.model_dump() for n in nodes] == before


def test_node_order_a_before_b():
    nodes, index = _contract()
    result = generate_pair_candidates(index, nodes)
    assert all(index.position(c.node_a) < index.position(c.node_b) for c in result.candidates)


def test_candidates_version_constant_present():
    assert pc.CANDIDATES_VERSION.startswith("pairs-cand-")
    assert isinstance(pc.PAIRS_TOP_K, int) and pc.PAIRS_TOP_K > 0
    assert (pc.CONTEXT_CHARS_MAX, pc.MIN_CLAUSE_CHARS, pc.CUE_LOOKBACK) == (300, 25, 3)
