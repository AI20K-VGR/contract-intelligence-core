from __future__ import annotations

import pytest

from app.contracts.models import StructuralNode
from app.pipeline.contract_graph.address import Address, parse_addresses
from app.pipeline.contract_graph.resolver import (
    Method,
    Resolution,
    Status,
    StructureIndex,
    default_target_parts,
    disambiguate_by_order,
)

BODY = "body:f-body"


def _node(node_id, label, parent=None, *, text="", file="f-body", kind="CLAUSE", level="BLOCK"):
    return StructuralNode(
        node_id=node_id,
        type=kind,
        raw_label=label,
        parent_id=parent,
        text=text,
        source_file_id=file,
        structure_level=level,
    )


def _tree() -> list[StructuralNode]:
    nodes = [
        _node("d1", "Điều 1"),
        _node("d3", "Điều 3"),
        _node("d3k1", "1.", "d3"),
        _node("d3k1a", "a)", "d3k1"),
        _node("d3k1b", "b)", "d3k1"),
        _node("d3k1c", "c)", "d3k1"),
        _node("d3k2", "2.", "d3"),
        _node("d3k2a", "a)", "d3k2"),
        _node("d3k2c", "c)", "d3k2"),
        _node("d3k2d", "d)", "d3k2"),
        _node("d3k2d1", "d1)", "d3k2"),
        _node("d4", "Điều 4"),
        _node("d4k4", "4.", "d4"),
        _node("d53", "Điều 5.3"),
        _node("d6", "Điều 6", text="Nội dung chung của Điều 6.\nc) Điểm c chưa tách thành node."),
        _node("f7", "Điều 7", kind="FIELD"),
        _node("t8", "Điều 8", kind="TABLE"),
        _node("d18", "Điều 18"),
        _node("d18k5", "5.", "d18"),
        _node("d30", "Điều 30"),
        _node("d30a", "Điều 30a"),
        _node("pl1", "Phụ lục 1"),
        _node("pl1d1", "Điều 1", "pl1"),
        _node("ax1", "1.", file="f-annex", text="Bãi bỏ khoản 2 Điều 3."),
    ]
    for order, node in enumerate(nodes):
        node.order = order
    return nodes


ROLES = {"f-body": "body", "f-annex": "annex"}


@pytest.fixture
def index() -> StructureIndex:
    return StructureIndex.build(_tree(), ROLES)


def _resolve(index: StructureIndex, addr: Address, **kwargs) -> Resolution:
    return index.resolve(addr, parts={BODY}, **kwargs)


def test_exact_unique(index):
    res = _resolve(index, Address(dieu="3", khoan="1", diem="c"))

    assert (res.status, res.method, res.node_id) == (Status.UNIQUE, Method.EXACT, "d3k1c")
    assert res.canonical == "diem c khoan 1 dieu 3"
    assert res.residual == ()


def test_contract_style_label_indexed(index):
    res = _resolve(index, Address(dieu="5", khoan="3"))

    assert (res.status, res.method, res.node_id) == (Status.UNIQUE, Method.EXACT, "d53")
    assert index.canonical_of("d53") == "khoan 3 dieu 5"


def test_duplicate_numbering_is_ambiguous():
    nodes = [_node("a", "Điều 2"), _node("b", "Điều 2"), _node("c", "Điều 3")]
    for order, node in enumerate(nodes):
        node.order = order
    index = StructureIndex.build(nodes, {"f-body": "body"})

    res = index.resolve(Address(dieu="2"), parts={BODY})

    assert res.status == Status.AMBIGUOUS
    assert res.node_id is None
    assert set(res.candidates) == {"a", "b"}


def test_missing_target_not_found_never_invents(index):
    res = _resolve(index, Address(dieu="99", khoan="1"))

    assert res.status == Status.NOT_FOUND
    assert res.node_id is None
    assert res.candidates == ()


def test_field_and_table_nodes_are_not_addressable(index):
    assert _resolve(index, Address(dieu="7")).status == Status.NOT_FOUND
    assert _resolve(index, Address(dieu="8")).status == Status.NOT_FOUND


def test_ancestor_with_label_in_text(index):
    res = _resolve(index, Address(dieu="6", diem="c"))

    assert (res.status, res.method, res.node_id) == (Status.UNIQUE, Method.ANCESTOR, "d6")
    assert res.residual == ("diem c",)
    assert res.canonical == "diem c dieu 6"


def test_ancestor_without_label_evidence_is_not_found(index):
    res = _resolve(index, Address(dieu="6", diem="e"), require_existing=True)

    assert res.status == Status.NOT_FOUND
    assert res.node_id is None


def test_insertion_resolves_container_when_anchor_exists(index):
    (addr,) = parse_addresses("Bổ sung khoản 5 vào sau khoản 4 Điều 4")

    res = _resolve(index, addr, require_existing=False)

    assert (res.status, res.node_id) == (Status.UNIQUE, "d4")
    assert res.canonical == "khoan 5 dieu 4"

    (missing,) = parse_addresses("Bổ sung khoản 7 vào sau khoản 6 Điều 4")
    gone = _resolve(index, missing, require_existing=False)
    assert gone.status == Status.NOT_FOUND
    assert gone.node_id is None


def test_insertion_into_container_without_anchor(index):
    (addr,) = parse_addresses("Bổ sung điểm đ vào khoản 2 Điều 3")

    res = _resolve(index, addr, require_existing=False)

    assert (res.status, res.node_id, res.canonical) == (
        Status.UNIQUE,
        "d3k2",
        "diem đ khoan 2 dieu 3",
    )


def test_insertion_suffix_never_resolves_to_existing_anchor(index):
    (addr,) = parse_addresses("Bổ sung khoản 5a vào sau khoản 5 Điều 18")

    res = _resolve(index, addr, require_existing=False)

    assert res.status == Status.UNIQUE
    assert res.canonical == "khoan 5a dieu 18"
    assert res.node_id == "d18"
    assert res.node_id != "d18k5"


def test_insertion_new_equal_anchor_is_not_found(index):
    addr = Address(dieu="18", khoan="5", insert_after=Address(dieu="18", khoan="5"))

    res = _resolve(index, addr, require_existing=False)

    assert res.status == Status.NOT_FOUND
    assert res.node_id is None
    assert res.residual == ("insert_equals_anchor",)


def test_insertion_of_article_after_article(index):
    (addr,) = parse_addresses("Bổ sung Điều 30a vào sau Điều 30")

    res = _resolve(index, addr, require_existing=False)

    assert (res.status, res.canonical) == (Status.UNIQUE, "dieu 30a")
    # an article has no container node: the edge targets the part, never the anchor node
    assert res.node_id is None


def test_insertion_of_a_new_annex_targets_no_node(index):
    addr = Address(phu_luc="3")

    res = index.resolve(addr, parts=default_target_parts(index, None, addr), require_existing=False)

    assert (res.status, res.node_id, res.canonical) == (Status.UNIQUE, None, "phu luc 3")


def test_insertion_of_an_article_into_an_existing_annex(index):
    addr = Address(dieu="2", phu_luc="1")

    res = index.resolve(addr, parts=default_target_parts(index, None, addr), require_existing=False)

    assert (res.status, res.node_id, res.canonical) == (Status.UNIQUE, "pl1", "dieu 2 phu luc 1")


def test_suffix_labels_indexed(index):
    point = _resolve(index, Address(dieu="3", khoan="2", diem="d1"))
    article = _resolve(index, Address(dieu="30a"))

    assert (point.status, point.method, point.node_id) == (Status.UNIQUE, Method.EXACT, "d3k2d1")
    assert (article.status, article.method, article.node_id) == (
        Status.UNIQUE,
        Method.EXACT,
        "d30a",
    )
    assert _resolve(index, Address(dieu="3", khoan="2", diem="d")).node_id == "d3k2d"
    assert _resolve(index, Address(dieu="30")).node_id == "d30"


def test_multi_clause_parent_existence_filter(index):
    res = _resolve(index, Address(dieu="3", diem="b", khoan_options=("1", "2")))

    assert (res.status, res.method, res.node_id) == (Status.UNIQUE, Method.EXACT, "d3k1b")
    assert res.canonical == "diem b khoan 1 dieu 3"


def test_multi_clause_parent_both_exist_is_ambiguous(index):
    res = _resolve(index, Address(dieu="3", diem="c", khoan_options=("1", "2")))

    assert res.status == Status.AMBIGUOUS
    assert res.node_id is None
    assert set(res.candidates) == {"d3k1c", "d3k2c"}


def test_multi_clause_parent_none_exist_is_not_found(index):
    res = _resolve(index, Address(dieu="3", diem="g", khoan_options=("1", "2")))

    assert res.status == Status.NOT_FOUND


def test_order_inference_forces_monotone_assignment(index):
    parent = Address(dieu="3", khoan_options=("1", "2"))
    first = _resolve(index, Address(dieu=parent.dieu, diem="c", khoan_options=("1", "2")))
    second = _resolve(index, Address(dieu=parent.dieu, diem="a", khoan_options=("1", "2")))
    assert first.status == second.status == Status.AMBIGUOUS

    out = disambiguate_by_order([first, second], index)

    assert [(r.status, r.method, r.node_id) for r in out] == [
        (Status.UNIQUE, Method.ORDER_INFERENCE, "d3k1c"),
        (Status.UNIQUE, Method.ORDER_INFERENCE, "d3k2a"),
    ]
    assert [r.canonical for r in out] == ["diem c khoan 1 dieu 3", "diem a khoan 2 dieu 3"]


def test_order_inference_keeps_ambiguous_when_not_forced(index):
    first = _resolve(index, Address(dieu="3", diem="a", khoan_options=("1", "2")))
    second = _resolve(index, Address(dieu="3", diem="c", khoan_options=("1", "2")))

    out = disambiguate_by_order([first, second], index)

    assert [r.status for r in out] == [Status.AMBIGUOUS, Status.AMBIGUOUS]
    assert out == [first, second]


def test_order_inference_uses_unique_siblings_as_fixed_points(index):
    fixed = _resolve(index, Address(dieu="3", khoan="2", diem="a"))
    open_ = _resolve(index, Address(dieu="3", diem="c", khoan_options=("1", "2")))

    out = disambiguate_by_order([fixed, open_], index)

    assert out[0] == fixed
    assert (out[1].status, out[1].node_id) == (Status.UNIQUE, "d3k2c")


def test_order_inference_treats_insertion_container_as_a_span(index):
    # "a) sửa điểm b khoản 1; b) bổ sung điểm a2 vào sau điểm a": the new point may sit inside
    # khoản 1 after b) just as well as in khoản 2, so the order must not decide it
    fixed = _resolve(index, Address(dieu="3", khoan="1", diem="b"))
    (insert,) = parse_addresses("Bổ sung điểm a2 vào sau điểm a")
    insert = Address(
        dieu="3",
        diem=insert.diem,
        khoan_options=("1", "2"),
        insert_after=Address(dieu="3", diem="a", khoan_options=("1", "2")),
    )
    open_ = _resolve(index, insert, require_existing=False)
    assert open_.status == Status.AMBIGUOUS
    assert set(open_.candidates) == {"d3k1", "d3k2"}

    out = disambiguate_by_order([fixed, open_], index)

    assert out == [fixed, open_]


def test_annex_address_limited_to_annex_parts(index):
    addr = Address(dieu="1", phu_luc="1")
    parts = default_target_parts(index, None, addr)

    res = index.resolve(addr, parts=parts)

    assert parts == {"annex:pl1", "annex:file:f-annex"}  # every annex part; the number filters
    assert (res.status, res.node_id) == (Status.UNIQUE, "pl1d1")
    assert res.canonical == "dieu 1 phu luc 1"
    assert index.resolve(Address(dieu="1", phu_luc="2"), parts=parts).status == Status.NOT_FOUND
    # the body article 1 is never reached through an annex address
    assert _resolve(index, Address(dieu="1")).node_id == "d1"


def test_annex_root_resolves_by_number(index):
    res = index.resolve(
        Address(phu_luc="1"), parts=default_target_parts(index, None, Address(phu_luc="1"))
    )

    assert (res.status, res.node_id, res.canonical) == (Status.UNIQUE, "pl1", "phu luc 1")


def test_default_parts_annex_source_targets_body(index):
    assert index.part_of("ax1") == "annex:file:f-annex"
    assert default_target_parts(index, "ax1", Address(dieu="3")) == {BODY}


def test_default_parts_body_source_stays_in_own_part(index):
    assert default_target_parts(index, "d4k4", Address(dieu="3")) == {BODY}


def test_source_subtree_is_never_a_target(index):
    res = index.resolve(Address(dieu="3", khoan="1"), parts={BODY}, source_node_id="d3k1")

    assert res.status == Status.NOT_FOUND


def test_self_reference_walks_source_ancestors(index):
    clause = index.resolve(Address(self_level="khoan"), parts={BODY}, source_node_id="d3k2d1")
    article = index.resolve(Address(self_level="dieu"), parts={BODY}, source_node_id="d3k2d1")
    clause_of_article = index.resolve(
        Address(khoan="1", self_level="dieu"), parts={BODY}, source_node_id="d3k2d1"
    )

    assert (clause.status, clause.method, clause.node_id) == (Status.UNIQUE, Method.SELF, "d3k2")
    assert (article.node_id, article.canonical) == ("d3", "dieu 3")
    assert (clause_of_article.status, clause_of_article.node_id) == (Status.UNIQUE, "d3k1")
    no_source = index.resolve(Address(self_level="khoan"), parts={BODY})
    assert no_source.status == Status.NOT_FOUND
    above = index.resolve(Address(self_level="diem"), parts={BODY}, source_node_id="d3")
    assert above.status == Status.NOT_FOUND


def test_relative_without_parent_is_not_found(index):
    (addr,) = parse_addresses("điểm a")

    res = _resolve(index, addr)

    assert res.status == Status.NOT_FOUND
    assert res.node_id is None


def test_sequential_context_when_parent_is_missing():
    nodes = [
        _node("a3", "Điều 3"),
        _node("k1", "1."),
        _node("pa", "a)"),
        _node("a4", "Điều 4"),
        _node("k2", "2."),
    ]
    for order, node in enumerate(nodes):
        node.order = order
    index = StructureIndex.build(nodes, {"f-body": "body"})

    assert index.canonical_of("pa") == "diem a khoan 1 dieu 3"
    assert index.canonical_of("k2") == "khoan 2 dieu 4"


def test_resolved_node_ids_are_always_input_nodes(index):
    input_ids = {node.node_id for node in _tree()}
    addresses = [
        Address(dieu="3", khoan="1", diem="c"),
        Address(dieu="5", khoan="3"),
        Address(dieu="99"),
        Address(dieu="6", diem="c"),
        Address(dieu="6", diem="e"),
        Address(dieu="3", diem="c", khoan_options=("1", "2")),
        Address(dieu="3", diem="a", khoan_options=("1", "2")),
        Address(dieu="1", phu_luc="1"),
        Address(phu_luc="1"),
        Address(diem="a"),
        *parse_addresses("Bổ sung khoản 5a vào sau khoản 5 Điều 18"),
        *parse_addresses("Bổ sung điểm d1, d2 vào sau điểm d khoản 2 Điều 3"),
        *parse_addresses("Bổ sung Điều 30a vào sau Điều 30"),
    ]
    results = []
    for addr in addresses:
        for require_existing in (True, False):
            parts = default_target_parts(index, None, addr)
            results.append(index.resolve(addr, parts=parts, require_existing=require_existing))
    results += disambiguate_by_order(results, index)

    for res in results:
        assert res.node_id is None or res.node_id in input_ids
        assert set(res.candidates) <= input_ids
        if res.status != Status.UNIQUE:
            assert res.node_id is None
    assert len(index.node_ids()) == len(input_ids)
