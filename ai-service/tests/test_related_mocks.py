"""Related mock contracts: body/annex value, padded annex numbers, missing annex, titled numbering."""

from __future__ import annotations

from app.contracts.models import Disposition, ReviewState
from app.pipeline.ai1_snapshot_adapter import adapt_snapshot
from app.pipeline.idp import run_idp
from app.tools.store import InMemorySnapshotStore


def _page(number: int, lines: list[str]) -> dict:
    return {
        "page_no": number,
        "input_type": "SCANNED_OCR",
        "status": "SUCCESS",
        "raw_text_digest": "b" * 64,
        "render": {},
        "transform": {"rotation_degrees": 0, "profile_version": "test"},
        "lines": [
            {
                "line_id": f"p{number}:l{index}",
                "raw_text": text,
                "bbox": [0.1, min(0.9, 0.08 + index * 0.05), 0.9, min(0.95, 0.12 + index * 0.05)],
            }
            for index, text in enumerate(lines, start=1)
        ],
        "tables": [],
        "warnings": [],
        "text": "\n".join(lines),
    }


def _snapshot(name: str, pages: list[dict]) -> dict:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": f"snap-{name}",
        "dossier_id": f"dos-{name}",
        "document_id": f"doc-{name}",
        "run_id": f"run-{name}",
        "source_digest": "c" * 64,
        "execution": {},
        "producer": {},
        "status": "SUCCESS",
        "pages": pages,
    }


def _run(name: str, pages: list[dict]):
    adapted = adapt_snapshot(_snapshot(name, pages))
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    return adapted, job


def test_body_and_annex_totals_conflict_without_a_winner():
    _adapted, job = _run(
        "value-conflict",
        [
            _page(1, [
                "ĐIỀU 1. GIÁ TRỊ HỢP ĐỒNG",
                "1.1. Tổng giá trị hợp đồng là 1.000.000.000 đồng.",
                "Chi tiết theo Phụ lục 01.",
            ]),
            _page(2, [
                "PHỤ LỤC 01 - BẢNG GIÁ",
                "Tổng giá trị hợp đồng là 1.200.000.000 đồng.",
            ]),
        ],
    )
    assert job.contribution is not None
    facts = [fact for fact in job.contribution.facts if fact.item_key == "contract_value"]
    assert {fact.raw_value for fact in facts} == {"1000000000", "1200000000"}
    conflict = [
        item
        for item in job.contribution.candidates
        if item.item_key == "contract_value" and item.disposition == Disposition.COMPARABLE_DIFFERENCE
    ]
    assert conflict
    assert "không kết luận bên nào thắng" in conflict[0].reason
    assert job.review_state is ReviewState.NEEDS_REVIEW


def test_padded_annex_heading_links_to_unpadded_body_reference():
    _adapted, job = _run(
        "padded-ref",
        [
            _page(1, [
                "ĐIỀU 2. TÀI LIỆU",
                "Nhân sự thực hiện theo Phụ lục 1.",
            ]),
            _page(2, [
                "PHỤ LỤC 01 - NHÂN SỰ",
                "Danh sách nhân sự triển khai.",
            ]),
        ],
    )
    findings = job.contribution.contract_context.findings
    assert any(item.kind == "PART_LINK" for item in findings)
    assert not any(item.kind == "CONTEXT_GAP" for item in findings)


def test_missing_annex_mention_stays_a_gap_and_does_not_invent_a_node():
    adapted, job = _run(
        "missing-annex",
        [_page(1, ["ĐIỀU 2. TÀI LIỆU KÈM THEO", "Chi tiết nhân sự thực hiện theo Phụ lục 07."])],
    )
    labels = [node.raw_label for node in adapted.record.evidence_nodes()]
    assert not any(str(label).casefold().startswith("phụ lục 07") or str(label).casefold().startswith("phu luc 07") for label in labels)
    findings = job.contribution.contract_context.findings
    gap = [item for item in findings if item.kind == "CONTEXT_GAP" and "07" in item.reason]
    assert gap
    assert job.review_state is ReviewState.NEEDS_REVIEW


def test_titled_dieu_headings_report_a_numbering_gap_without_inventing_dieu_2():
    adapted, job = _run(
        "titled-gap",
        [_page(1, ["ĐIỀU 1. ĐỊNH NGHĨA", "ĐIỀU 3. THANH TOÁN", "3.1. Bên A thanh toán trong vòng 07 ngày."])],
    )
    labels = [node.raw_label for node in adapted.record.nodes]
    assert not any(str(label).casefold().startswith("điều 2") or str(label).casefold().startswith("dieu 2") for label in labels)
    assert any(getattr(issue, "code", None) == "NUMBERING_GAP" for issue in job.handoff_issues)


def test_page_furniture_is_not_stored_as_clause_body():
    adapted, _job = _run(
        "furniture",
        [
            _page(
                1,
                [
                    "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
                    "4.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng.",
                    "Trang 3/20",
                    "09/2026/HĐKT-PT-MH",
                ],
            )
        ],
    )
    heading = next(node for node in adapted.record.evidence_nodes() if node.raw_label.startswith("ĐIỀU 4"))
    children = [node.raw_label for node in adapted.record.evidence_nodes() if node.parent_id == heading.node_id]
    assert any(label.startswith("4.1") for label in children)
    assert not any(label.startswith("Trang ") or label.startswith("09/2026/") for label in children)


def test_word_moi_meaning_every_is_not_an_amended_definition():
    from app.pipeline.edge_flags import dossier_edge_issues

    adapted, _job = _run(
        "moi-every",
        [
            _page(
                1,
                [
                    "Mọi thông báo phải gửi bằng văn bản.",
                    "Các bên xác nhận mọi thông báo phải gửi bằng văn bản trước khi có hiệu lực.",
                ],
            )
        ],
    )
    assert not any(issue.code == "DEFINITION_CASCADE" for issue in dossier_edge_issues(adapted.record))


def test_compare_without_a_configured_llm_answers_in_text():
    from app.reasoning.query import QueryRouter
    from app.tools.gateway import ToolGateway

    adapted, _job = _run(
        "text-answer",
        [
            _page(1, ["ĐIỀU 1. ĐỊNH NGHĨA", "Hệ thống là phần mềm nền tảng."]),
            _page(2, ["ĐIỀU 3. THANH TOÁN", "Bên A thanh toán trong vòng 07 ngày."]),
        ],
    )
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    result = QueryRouter(store, ToolGateway(store)).query(
        adapted.envelope,
        "Điều 1 liên quan đến Điều 3 thế nào?",
        policy_flags={"egress_allowed": True, "use_llm": True, "use_vector": False},
    )
    assert isinstance(result["answer"], str)
    assert "ĐIỀU 1" in result["answer"]
    assert result["used_llm"] is False


def test_unpadded_annex_query_matches_padded_heading():
    from app.reasoning.l1_retrieval import _exact_label_ids

    outline = [
        {"node_id": "annex-01", "raw_label": "PHỤ LỤC 01 - BẢNG GIÁ", "type": "SECTION"},
        {"node_id": "annex-10", "raw_label": "PHỤ LỤC 10 - KHÁC", "type": "SECTION"},
    ]
    ids = _exact_label_ids("Chi tiết theo Phụ lục 1", outline)
    assert ids == ["annex-01"]


def test_repeated_annex_heading_is_not_a_second_source():
    from app.reasoning.l1_retrieval import L1Retrieval
    from app.tools.gateway import ToolGateway

    adapted, _job = _run(
        "annex-continue",
        [
            _page(1, ["ĐIỀU 1. GIÁ", "Chi tiết theo Phụ lục 01."]),
            _page(2, ["PHỤ LỤC 01 - BẢNG GIÁ", "Dòng máy chủ."]),
            _page(3, ["PHỤ LỤC 01 - BẢNG GIÁ", "Dòng tiếp theo của bảng."]),
        ],
    )
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    hits = L1Retrieval(ToolGateway(store)).run(
        adapted.envelope,
        {
            "type": "compare",
            "query": "Điều 1 liên quan đến Phụ lục 01 thế nào?",
            "policy_flags": {},
        },
    )["hits"]
    labels = []
    by_id = {node.node_id: node.raw_label for node in adapted.record.evidence_nodes()}
    for hit in hits:
        labels.append(by_id.get(hit.get("node_id"), ""))
    assert sum(label.startswith("PHỤ LỤC 01") for label in labels) == 1


def test_model_sentence_survives_when_two_sources_are_cited():
    from app.reasoning.stack import FourLayerReasoner
    from app.tools.gateway import ToolGateway

    adapted, _job = _run(
        "keep-model",
        [
            _page(1, ["ĐIỀU 1. GIÁ TRỊ HỢP ĐỒNG", "Tổng giá trị hợp đồng là 1.000.000.000 đồng."]),
            _page(2, ["PHỤ LỤC 01 - BẢNG GIÁ", "Tổng giá trị hợp đồng là 1.200.000.000 đồng."]),
        ],
    )
    ids = [node.node_id for node in adapted.record.evidence_nodes() if not node.node_id.startswith("ai2-root")][:3]
    assert len(ids) >= 3

    class Spy:
        def configured(self) -> bool:
            return True

        def complete_json(self, system: str, user: str, **kwargs):
            return {
                "answer": "Mô hình: thân và phụ lục khác giá, không chọn bên thắng.",
                "citations": [
                    {"node_id": ids[0], "text_span": adapted.record.evidence_nodes()[1].text[:40]},
                    {"node_id": ids[1], "text_span": adapted.record.evidence_nodes()[2].text[:40]},
                ],
                "sufficient": False,
                "legal_winner": False,
            }

    store = InMemorySnapshotStore()
    store.put(adapted.record)
    reasoner = FourLayerReasoner(ToolGateway(store), Spy())

    def fake_l1(envelope, task):
        return {
            "hits": [{"node_id": node_id, "citation": {"node_id": node_id, "text_span": node_id}} for node_id in ids],
            "outline_ids": [{"node_id": node_id} for node_id in ids],
            "blocked": False,
            "relations": [],
            "relation_edges": [],
            "relation_issues": [],
            "retrieval_trace": {},
        }

    reasoner.l1.run = fake_l1
    result = reasoner.run(
        adapted.envelope,
        {
            "type": "compare",
            "query": "Điều 1 liên quan đến Phụ lục 01 thế nào?",
            "policy_flags": {"egress_allowed": True, "use_llm": True, "use_vector": False},
        },
    )
    assert "Mô hình:" in str(result.get("answer"))
    cited = {item.get("node_id") for item in result.get("citations") or []}
    assert ids[2] in cited


def test_mention_of_dieu_1_is_not_the_same_clause_as_the_heading():
    from app.reasoning.relations import related_node_ids

    outline = [
        {
            "node_id": "d1",
            "raw_label": "ĐIỀU 1. ĐỊNH NGHĨA",
            "text": "ĐIỀU 1. ĐỊNH NGHĨA",
        },
        {
            "node_id": "close",
            "raw_label": "Hai bên xác nhận các nội dung từ Điều 1 đến Điều 18",
            "text": "Hai bên xác nhận các nội dung từ Điều 1 đến Điều 18 và các phụ lục kèm theo.",
        },
        {"node_id": "d4", "raw_label": "ĐIỀU 4. GIÁ", "text": "ĐIỀU 4. GIÁ"},
    ]
    _extra, rels = related_node_ids(["d4", "close"], outline)
    assert not any(item.get("clause") == "Điều 1" for item in rels)


def test_repeated_heading_text_is_not_printed_twice():
    from app.reasoning.relations import render_related_answer

    answer = render_related_answer(
        [
            {
                "side": "Thân HĐ",
                "path": "Hợp đồng › ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
                "label": "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
                "text": "ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN",
            },
            {
                "side": "Thân HĐ",
                "path": "Hợp đồng › ĐIỀU 4. GIÁ",
                "label": "ĐIỀU 4. GIÁ",
                "text": "4.1. Tổng giá trị hợp đồng là 1.000.000.000 đồng.",
            },
        ],
        [],
    )
    assert answer.count("ĐIỀU 4. GIÁ TRỊ HỢP ĐỒNG VÀ THANH TOÁN") == 1
    assert "1.000.000.000" in answer


def test_clause_reference_resolves_to_the_heading_not_a_mention():
    from types import SimpleNamespace

    from app.reasoning.relations import _resolve_reference

    heading = SimpleNamespace(node_id="d1", type="CLAUSE", raw_label="ĐIỀU 1. ĐỊNH NGHĨA", text="ĐIỀU 1. ĐỊNH NGHĨA")
    mention = SimpleNamespace(
        node_id="close",
        type="UNNUMBERED_BLOCK",
        raw_label="Hai bên xác nhận các nội dung từ Điều 1 đến Điều 18",
        text="Hai bên xác nhận các nội dung từ Điều 1 đến Điều 18.",
    )
    source = SimpleNamespace(node_id="d9", type="CLAUSE", raw_label="ĐIỀU 9. DẪN CHIẾU", text="Chi tiết theo Điều 1.")
    annex = SimpleNamespace(node_id="pl", type="SECTION", raw_label="PHỤ LỤC 01 - BẢNG GIÁ", text="PHỤ LỤC 01 - BẢNG GIÁ")
    other = SimpleNamespace(node_id="pl10", type="SECTION", raw_label="PHỤ LỤC 10 - KHÁC", text="PHỤ LỤC 10 - KHÁC")
    ask = SimpleNamespace(node_id="body", type="CLAUSE", raw_label="ĐIỀU 2. TÀI LIỆU", text="Nhân sự theo Phụ lục 1.")
    assert _resolve_reference("CLAUSE", "1", source, [heading, mention, source]) == ["d1"]
    assert _resolve_reference("ANNEX", "1", ask, [annex, other, ask]) == ["pl"]




