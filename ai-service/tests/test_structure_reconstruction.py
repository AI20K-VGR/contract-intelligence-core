from pathlib import Path

from app.pipeline.ai1_ingest import ingest_files
from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
from app.pipeline.grounding import repair_active_nodes
from app.pipeline.outline import build_tree, citation_for_node
from fixtures.catalog import make_node, make_page, make_record
from app.reasoning.query import classify_ask
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore


ROOT = Path(__file__).resolve().parents[1]


def _master_record():
    contracts = ROOT / "fixtures" / "contracts"
    return ingest_files(
        [
            ("AI2-TEST-MASTER.body.pdf", (contracts / "AI2-TEST-MASTER.body.pdf").read_bytes(), "body"),
            ("AI2-TEST-MASTER.annexes.pdf", (contracts / "AI2-TEST-MASTER.annexes.pdf").read_bytes(), "annex"),
        ]
    )


def test_master_contract_reconstruction_keeps_scopes_and_does_not_promote_inline_annex_reference():
    record, _, _, _ = _master_record()
    active, issues = repair_active_nodes(record)
    tree = build_tree(active)

    assert len(tree) == 2
    body_root, annex_root = tree
    assert body_root["raw_label"] == "Hợp đồng"
    assert [item["raw_label"] for item in body_root["children"]] == [
        f"Điều {number}. " + title
        for number, title in [
            (1, "Các bên"),
            (2, "Giải thích từ ngữ"),
            (3, "Phạm vi công việc"),
            (4, "Giá trị, tiền tệ và thuế"),
            (5, "Tiến độ, giao hàng và nghiệm thu"),
            (6, "Tạm ứng và thanh toán"),
            (7, "Phạt và giới hạn trách nhiệm"),
            (8, "Bảo hành, bảo mật và dữ liệu"),
            (9, "Sửa đổi, phụ lục và quan hệ giữa các nguồn"),
            (10, "Các trường hợp không đánh số"),
            (11, "Bất khả kháng và thời hạn"),
            (12, "Luật áp dụng và giải quyết tranh chấp"),
            (13, "Chữ ký"),
        ]
    ]
    annex_labels = {item["raw_label"] for item in annex_root["children"]}
    for number in (1, 2, 3, 4, 5, 6, 8, 9, 10, 11, 12, 13):
        assert any(label.startswith(f"Phụ lục {number} ") for label in annex_labels)
    assert not any(label.startswith("Phụ lục 7") for label in annex_labels)

    inline = next(
        node
        for node in active
        if node.type == "UNNUMBERED_BLOCK"
        and node.parent_id == "cl_6"
        and " 2 " in (node.text or "")
        and "quy" in (node.text or "").lower()
    )
    assert inline.type == "UNNUMBERED_BLOCK"
    assert inline.parent_id == "cl_6"
    assert any(issue.code == "AMBIGUOUS_HEADING_AS_BLOCK" for issue in issues)

    assert not any(
        node.raw_label == "Bên A" and node.source_file_id == annex_root["source_file_id"]
        for node in active
    )


def test_citation_contains_full_structure_path_and_source_scope():
    record, _, _, _ = _master_record()
    active, _ = repair_active_nodes(record)

    clause = citation_for_node(active, record.pages, "cl_6")
    annex_node = next(
        node
        for node in active
        if node.type == "SECTION"
        and node.source_file_id == record.source_files[1].file_id
        and (node.raw_label or "").startswith("Ph")
        and " 2 " in (node.raw_label or "")
    )
    annex = citation_for_node(active, record.pages, annex_node.node_id)
    assert clause is not None
    assert clause["breadcrumb"] == ["Hợp đồng", "Điều 6. Tạm ứng và thanh toán"]
    assert clause["structure_path"] == "Hợp đồng › Điều 6. Tạm ứng và thanh toán"
    assert clause["source_file_id"]
    assert "Bên A tạm ứng" in clause["text_span"]
    assert clause["geometry_available"] is False

    assert annex is not None
    assert annex["breadcrumb"] == ["Phụ lục — AI2-TEST-MASTER.annexes.pdf", "Phụ lục 2 — Định nghĩa và thanh toán sửa đổi"]
    assert annex["page"] == 5


def test_flat_ai1_snapshot_gets_a_synthetic_root_and_clause_parenting():
    payload = {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-structure",
        "dossier_id": "dossier-structure",
        "document_id": "doc-structure",
        "run_id": "run-structure",
        "source_digest": "a" * 64,
        "execution": {},
        "producer": {},
        "status": "SUCCESS",
        "pages": [
            {
                "page_no": 1,
                "status": "SUCCESS",
                "text": "Điều 1. Các bên\nBên A thanh toán.\nĐiều 2. Phạm vi",
                "lines": [
                    {"line_id": "l1", "raw_text": "Điều 1. Các bên"},
                    {"line_id": "l2", "raw_text": "Bên A thanh toán."},
                    {"line_id": "l3", "raw_text": "Điều 2. Phạm vi"},
                ],
                "tables": [],
            }
        ],
    }
    adapted = adapt_ai1_input(payload)
    active, _ = repair_active_nodes(adapted.record)
    tree = build_tree(active)
    assert len(tree) == 1
    assert tree[0]["is_synthetic"] is True
    assert [item["raw_label"] for item in tree[0]["children"]] == [
        "Điều 1. Các bên",
        "Điều 2. Phạm vi",
    ]
    block = next(node for node in active if node.node_id.endswith("l2"))
    assert block.parent_id == "line:1:l1"


def test_pdf_party_declarations_are_not_confused_with_clause_mentions():
    record, env, _, _ = _master_record()
    record.active_nodes, _ = repair_active_nodes(record)
    store = InMemorySnapshotStore()
    store.put(record)
    stack = FourLayerReasoner(ToolGateway(store), llm=None)

    expected = {
        "A": ("Công ty TNHH Giải pháp ABC", "0311111111"),
        "B": ("Công ty Cổ phần Thiết bị XYZ", "0322222222"),
        "C": ("Công ty TNHH Dịch vụ Kiểm định DEF", "0333333333"),
    }
    for letter, (name, mst) in expected.items():
        result = stack.run(env, classify_ask(f"Thong tin ben {letter}?"))
        assert result["review_state"] == "ANSWERED"
        assert name in result["answer"]
        assert mst in result["answer"]
        assert "031111111103222222220333333333" not in result["answer"]


def test_structure_repair_deduplicates_without_inventing_missing_parent():
    record = make_record(
        case_id="STRUCTURE-REPAIR",
        dossier="d-structure-repair",
        pages=[make_page(1, "Điều 1. Nội dung")],
        nodes=[
            make_node("root", "SECTION", "Hợp đồng", "", order=9),
            make_node("clause", "CLAUSE", "Điều 1", "Điều 1. Nội dung", parent_id="missing", order=2),
            make_node("clause", "CLAUSE", "Điều 1 duplicate", "Điều 1. Nội dung", parent_id="root", order=2),
        ],
    )
    active, issues = repair_active_nodes(record)
    assert [node.node_id for node in active] == ["root", "clause"]
    assert active[1].parent_id == "root"
    assert [node.order for node in active] == [0, 1]
    assert any(issue.code == "STRUCTURE_DUPLICATE_NODE_ID" for issue in issues)
