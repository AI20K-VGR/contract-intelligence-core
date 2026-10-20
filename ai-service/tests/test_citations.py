from __future__ import annotations

from app.contracts.models import Citation, PageSnapshot, StructuralNode, TableCell, TableSnapshot
from app.pipeline.citations import CitationResolver, quote_digest


def _page() -> PageSnapshot:
    return PageSnapshot(
        page_revision_id="rev-1",
        page_number=1,
        source_file_id="doc-1",
        page_in_file=1,
        text="ABC\nDEF",
        line_texts={"line-1": "ABC", "line-2": "DEF"},
        source_hash="a" * 64,
    )


def _citation(**overrides) -> Citation:
    values = {
        "citation_id": "cite-1",
        "node_id": "node-1",
        "page_revision_id": "rev-1",
        "source_file_id": "doc-1",
        "page": 1,
        "line_ids": ["line-1"],
        "text_span": "ABC",
        "char_start": 0,
        "char_end": 3,
        "source_hash": "a" * 64,
        "quote_sha256": quote_digest("ABC"),
    }
    values.update(overrides)
    return Citation(**values)


def test_exact_citation_is_valid():
    check = CitationResolver([_page()]).verify(_citation())
    assert check.status == "VALID"


def test_missing_source_hash_is_unverified_not_valid():
    check = CitationResolver([_page()]).verify(_citation(source_hash=None))
    assert check.status == "UNVERIFIED"


def test_wrong_hash_or_offset_is_invalid():
    resolver = CitationResolver([_page()])
    assert resolver.verify(_citation(source_hash="b" * 64)).status == "INVALID"
    assert resolver.verify(_citation(char_start=1, char_end=4)).status == "INVALID"


def test_whitespace_folded_quote_cannot_pass_as_exact():
    citation = _citation(text_span="A B", char_start=0, char_end=3, quote_sha256=quote_digest("A B"))
    assert CitationResolver([_page()]).verify(citation).status == "INVALID"


def test_unknown_page_revision_is_invalid():
    assert CitationResolver([_page()]).verify(_citation(page_revision_id="rev-other")).status == "INVALID"


def test_authoritative_resolver_checks_node_and_source_scope():
    node = StructuralNode(
        node_id="node-1",
        type="CLAUSE",
        raw_label="Clause",
        text="ABC",
        page_range=[1],
        page_revision_id="rev-1",
        source_file_id="doc-1",
    )
    resolver = CitationResolver([_page()], nodes=[node])
    assert resolver.verify(_citation()).status == "VALID"
    assert resolver.verify(_citation(node_id="other-node")).status == "INVALID"
    assert resolver.verify(_citation(source_file_id="other-doc")).status == "INVALID"
    assert resolver.verify(_citation(page=2)).status == "INVALID"


def test_claimed_table_cell_keeps_raw_value_but_is_not_verified():
    cell = TableCell(
        cell_id="cell-1",
        row_index=0,
        column_index=0,
        text="0\u200b,5 “%”",
        bbox=[0.1, 0.1, 0.4, 0.2],
        geometry_provenance="CLAIMED",
    )
    table = TableSnapshot(
        table_id="table-1",
        header=["rate"],
        rows=[[cell.text]],
        node_id="table-node-1",
        page_revision_id="rev-1",
        cells=[cell],
    )
    citation = _citation(
        node_id="table-node-1",
        text_span=cell.text,
        quote_sha256=quote_digest(cell.text),
        table_id="table-1",
        cell_id="cell-1",
        bbox=cell.bbox,
        char_start=None,
        char_end=None,
        line_ids=[],
    )
    check = CitationResolver([_page()], tables=[table]).verify(citation)
    assert check.status == "UNVERIFIED"
    assert cell.text == "0\u200b,5 “%”"


def test_utf8_nfc_nfd_and_control_characters_are_exact_round_trip():
    raw = "Café e\u0301 — “nghiệm”\u200b\n\t\x01"
    page = PageSnapshot(
        page_revision_id="unicode-rev",
        page_number=1,
        source_file_id="unicode-doc",
        text=raw,
        line_texts={"line-1": raw},
        source_hash="c" * 64,
    )
    citation = Citation(
        node_id="unicode-node",
        page_revision_id="unicode-rev",
        source_file_id="unicode-doc",
        page=1,
        line_ids=["line-1"],
        text_span=raw,
        char_start=0,
        char_end=len(raw),
        source_hash="c" * 64,
        quote_sha256=quote_digest(raw),
    )
    assert CitationResolver([page]).verify(citation).status == "VALID"
    assert CitationResolver([page]).verify(citation.model_copy(update={"text_span": raw.replace("é", "e\u0301")})).status == "INVALID"
