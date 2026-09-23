"""Section 8: the clause/section hierarchy must be real, and every node must
resolve back to real evidence (real line ids on a real page)."""

from pathlib import Path

import pymupdf
import pytest
from pydantic import ValidationError

from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.build_structure import BuildStructure
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.domain.entities import Document, Experiment, Line, Page
from contract_ocr.domain.enums import Status
from contract_ocr.domain.snapshot import StructuralNode
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor

# Khoản numbers repeat the article number as a dotted prefix ("1.1", "1.2" under
# "Điều 1") -- the convention clause_parser/hierarchy_builder actually implement
# (see tests/reconstruction/test_hierarchy_builder.py's own "Điều 5" -> "5.1"/"5.2"
# case). A bare "1."/"2." reset per article is a DIFFERENT, equally real Vietnamese
# drafting convention that this module does not support: it parses as its own
# top-level (tier 0, level 1) marker and does not nest under the article. Also
# note `_SECTION_RE` requires actual diacritics ("Điều"/"ĐIỀU") or the English
# forms ("Article"/"Section") -- a diacritic-stripped "Dieu" (common on a
# degraded scan) is NOT recognized and falls through as plain body text. Both
# are real, disclosed limitations of the reused module, not something this
# phase changes -- see docs/ai1-current-state.md.
LINES = [
    "Điều 1. Đối tượng hợp đồng",
    "1.1 Bên A cam kết giao hàng đúng hạn.",
    "a) Giao tại kho của Bên B.",
    "b) Chịu chi phí vận chuyển.",
    "1.2 Bên B cam kết thanh toán đầy đủ.",
    "Điều 2. Giá trị hợp đồng",
    "2.1 Giá trị hợp đồng là 100000000 đồng.",
]


def _synthetic_document() -> Document:
    page = Page(
        page_number=1, width=1, height=1, engine="native", model="native", status=Status.SUCCESS
    )
    page.lines = [Line(line_id=f"l{i}", text=text) for i, text in enumerate(LINES, 1)]
    return Document(document_id="doc-1", source_file="unused.pdf", pages=[page])


def test_hierarchy_has_real_types_parents_and_traceable_line_ids():
    nodes = BuildStructure().execute(_synthetic_document())
    by_id = {n.node_id: n for n in nodes}
    assert len(by_id) == len(nodes), "node ids collided -- some node overwrote another"

    article_1 = by_id["1"]
    assert article_1.type == "ARTICLE"
    assert article_1.label_normalized == "ARTICLE_1"
    assert article_1.parent_id is None
    assert article_1.line_ids == ["l1"]

    clause_1_1 = by_id["1.1"]
    assert clause_1_1.type == "CLAUSE"
    assert clause_1_1.parent_id == "1"
    assert clause_1_1.line_ids == ["l2"]

    point_a = by_id["1.1.a"]
    assert point_a.type == "POINT"
    assert point_a.parent_id == "1.1"
    assert point_a.line_ids == ["l3"]

    clause_1_2 = by_id["1.2"]
    assert clause_1_2.parent_id == "1"

    article_2 = by_id["2"]
    assert article_2.type == "ARTICLE"
    assert article_2.parent_id is None
    assert article_2.label_normalized == "ARTICLE_2"

    clause_2_1 = by_id["2.1"]
    assert clause_2_1.parent_id == "2"

    # No fallback "UNMARKED" root should have been needed -- every line here
    # carries a marker this module actually recognizes.
    assert all(node.type != "UNMARKED" for node in nodes)

    # Every node id in the tree is unique and every referenced line id was a
    # real line of the input document.
    all_line_ids = {line.line_id for page in _synthetic_document().pages for line in page.lines}
    for node in nodes:
        assert set(node.line_ids) <= all_line_ids


def test_unrecognized_marker_becomes_an_unmarked_node_not_lost_text():
    # A diacritic-stripped "Dieu" is not recognized by _SECTION_RE (a real,
    # disclosed limitation) -- prove it becomes a traceable UNMARKED node
    # rather than silently vanishing.
    page = Page(
        page_number=1, width=1, height=1, engine="native", model="native", status=Status.SUCCESS
    )
    page.lines = [Line(line_id="l1", text="Dieu 1. Khong duoc nhan dien")]
    document = Document(document_id="doc-1", source_file="unused.pdf", pages=[page])
    nodes = BuildStructure().execute(document)
    assert len(nodes) == 1
    assert nodes[0].type == "UNMARKED"
    assert nodes[0].line_ids == ["l1"]


def test_skipped_and_failed_pages_contribute_no_nodes():
    page = Page(
        page_number=1, width=1, height=1, engine="native", model="native", status=Status.FAILED
    )
    page.lines = [Line(line_id="l1", text="Điều 1. Should not appear")]
    document = Document(document_id="doc-1", source_file="unused.pdf", pages=[page])
    assert BuildStructure().execute(document) == []


def test_structural_node_rejects_bbox_without_provenance_and_vice_versa():
    kwargs = dict(
        node_id="1", type="ARTICLE", label_normalized="ARTICLE_1", page_start=1, page_end=1
    )
    with pytest.raises(ValidationError):
        StructuralNode(**kwargs, bbox_normalized=[0.1, 0.1, 0.5, 0.5])
    with pytest.raises(ValidationError):
        StructuralNode(**kwargs, geometry_provenance="DERIVED")
    assert StructuralNode(**kwargs) is not None  # neither set is valid too


def test_real_pdf_produces_nodes_whose_line_ids_resolve_to_real_snapshot_lines(tmp_path: Path):
    # PyMuPDF's built-in base-14 font cannot encode Vietnamese diacritics (they
    # render as replacement characters, tripping the section-3 garbled-text
    # check from Phase 2 -- a real font-embedding limitation of generating a
    # synthetic PDF in this environment, not of the classifier). Use the
    # English "Article"/marker forms clause_parser also recognizes so this
    # test exercises real PDF -> OCR -> snapshot -> structure end-to-end
    # without depending on a bundled Unicode font.
    pdf_lines = [
        "Article 1. Subject of the contract",
        "1.1 Party A commits to deliver on time.",
        "a) Delivered to Party B's warehouse.",
        "b) Party A bears shipping cost.",
        "1.2 Party B commits to pay in full.",
        "Article 2. Contract value",
        "2.1 The contract value is 100000000 VND.",
    ]
    path = tmp_path / "clauses.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=600)
        y = 50
        for line in pdf_lines:
            page.insert_text((30, y), line, fontsize=11)
            y += 25
        pdf.save(path)

    processor = ProcessDocument(
        PyMuPDFExtractor(), PdfRenderer(), ImagePreprocessor(), PdfPageClassifier()
    )
    document = processor.execute(
        str(path),
        "doc-1",
        Experiment(id="E1", engine="pymupdf"),
        None,
        tmp_path / "raw",
        "TEST",
        72,
    )
    snap = BuildSnapshot(PdfRenderer(), image_dpi=72).execute(
        document,
        snapshot_id="run-1",
        dossier_id="dossier-1",
        document_role="contract",
        filename="clauses.pdf",
        engine_name="pymupdf",
        engine_version="test",
        image_output_dir=tmp_path / "images",
        image_uri_prefix="storage://ocr/run-1",
    )

    assert snap.nodes, "expected at least one structural node from real clause markers"
    real_line_ids = {line.line_id for page in snap.pages for line in page.lines}
    for node in snap.nodes:
        assert set(node.line_ids) <= real_line_ids
        # Native extraction gives every line a MEASURED-derived bbox, so a
        # union over real lines must produce DERIVED region geometry here.
        if node.line_ids:
            assert node.geometry_provenance == "DERIVED"
            assert node.bbox_normalized is not None
    types = {node.type for node in snap.nodes}
    assert types == {"ARTICLE", "CLAUSE", "POINT"}
