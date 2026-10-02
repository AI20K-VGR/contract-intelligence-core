import json
import re
from pathlib import Path

import pytest

from app.reasoning.l3_ground import L3Ground
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore
from fixtures.catalog import load_case

TASKS = json.loads(
    (Path(__file__).resolve().parents[1] / "fixtures/reasoning/hd_tong_hop_tasks.json").read_text(encoding="utf-8")
)


def _stack():
    pack = load_case("HD-TONG-HOP")
    store = InMemorySnapshotStore()
    store.put(pack.record)
    return pack, FourLayerReasoner(ToolGateway(store), llm=None)


def test_ask_dieu_9():
    from app.reasoning.query import classify_ask

    pack, stack = _stack()
    task = classify_ask("Điều 9 nói về gì?")
    assert task["type"] == "lookup_clause"
    out = stack.run(pack.envelope, task)
    assert out["review_state"] == "ANSWERED"
    assert "Phụ lục 7" in str(out["answer"])
    assert any(c.get("node_id") == "cl_9" for c in out["citations"])


def test_locate_dieu_9():
    from app.pipeline.outline import build_tree, locate

    pack = load_case("HD-TONG-HOP")
    tree = build_tree(pack.record.nodes)
    assert tree
    loc = locate(pack.record.nodes, pack.record.pages, "cl_9")
    assert loc["node_id"] == "cl_9"
    assert loc["page"] == 9

    ids = {t["id"] for t in TASKS}
    assert "T-MST" in ids and "T-PL7" in ids and "T-TABLE300" in ids
    assert all(t.get("layers") for t in TASKS)


def test_l0_pl7_insufficient():
    pack, stack = _stack()
    task = next(t for t in TASKS if t["id"] == "T-PL7")
    out = stack.run(pack.envelope, task)
    assert "L0" in out["layers_used"] and "L3" in out["layers_used"]
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"


def test_l0_gap_dieu_3():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-GAP3"))
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert "L2" not in out["layers_used"]


def test_l0_jailbreak_no_l2():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-INJECT"))
    assert out["review_state"] == "NEEDS_REVIEW"
    assert "L2" not in out["layers_used"]


def test_l0_mst_conflict_review():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-MST"))
    assert out["review_state"] == "NEEDS_REVIEW"
    assert len(out.get("citations") or []) >= 2
    ans = str(out["answer"])
    assert "cùng mã" in ans or "cùng một" in ans
    assert "0312345678" in ans and "0399999999" in ans
    assert ans.lower().count("0312345678") <= 3


def test_party_card_does_not_promote_generic_mentions_to_party_name():
    from app.reasoning.ask_assemble import assemble_party

    result = assemble_party(
        "A",
        outline=[],
        party_hits=[
            {
                "node_id": "line-1",
                "value": "khac phuc trong thoi han DKCT; qua han Ben A duoc thue ben khac",
                "citation": {"node_id": "line-1", "text_span": "Ben A"},
            },
            {
                "node_id": "line-2",
                "value": "Ben A la Ben giao thau",
                "citation": {"node_id": "line-2", "text_span": "Ben A"},
            },
        ],
        mst_hits=[
            {
                "node_id": "mst-1",
                "structured_key": "mst_seller",
                "value": "0399999999",
                "citation": {"node_id": "mst-1", "text_span": "0399999999"},
            }
        ],
    )

    assert "khac phuc trong thoi han" not in result["answer"]
    assert "Ben A la Ben giao thau" not in result["answer"]
    assert "(kh\u00f4ng t\u00e1ch \u0111\u01b0\u1ee3c t\u00ean)" in result["answer"]


def test_party_card_does_not_promote_generic_outline_mentions_to_party_name():
    from app.reasoning.ask_assemble import assemble_party

    result = assemble_party(
        "A",
        outline=[
            {
                "type": "CLAUSE",
                "node_id": "line-1",
                "raw_label": "Bên A được quyền tạm dừng điểm thi công liên quan.",
                "text": "Bên A được quyền tạm dừng điểm thi công liên quan.",
            }
        ],
        party_hits=[],
        mst_hits=[],
    )

    assert "tạm dừng điểm thi công" not in result["answer"]
    assert "(kh\u00f4ng t\u00e1ch \u0111\u01b0\u1ee3c t\u00ean)" in result["answer"]


def test_party_card_keeps_explicit_company_declaration_from_generic_evidence():
    from app.reasoning.ask_assemble import assemble_party

    result = assemble_party(
        "A",
        outline=[
            {
                "type": "CLAUSE",
                "node_id": "line-1",
                "raw_label": "Bên A được ghi: Công ty ABC, MST 0399999999.",
                "text": "Bên A được ghi: Công ty ABC, MST 0399999999.",
            }
        ],
        party_hits=[],
        mst_hits=[],
    )

    assert "Công ty ABC" in result["answer"]
    assert "khắc phục" not in result["answer"]


def test_mst_duplicate_is_same_fact():
    from app.reasoning.fact_link import relate_mst

    hits = [
        {"node_id": "field_mst_1", "value": "0311111111", "citation": {"node_id": "field_mst_1", "text_span": "0311111111"}},
        {"node_id": "field_mst_2", "value": "0312345678", "citation": {"node_id": "field_mst_2", "text_span": "0312345678"}},
        {"node_id": "field_mst_3", "value": "0322222222", "citation": {"node_id": "field_mst_3", "text_span": "0322222222"}},
        {"node_id": "field_mst_4", "value": "0399999999", "citation": {"node_id": "field_mst_4", "text_span": "0399999999"}},
        {"node_id": "field_mst_5", "value": "0311111111", "citation": {"node_id": "field_mst_5", "text_span": "0311111111"}},
    ]
    linked = relate_mst(hits)
    assert linked["review_state"] == "NEEDS_REVIEW"
    assert len(linked["groups"]) == 4
    same = next(g for g in linked["groups"] if g["canonical"] == "0311111111")
    assert same["count"] == 2
    assert set(same["node_ids"]) == {"field_mst_1", "field_mst_5"}
    assert "field_mst_1" in linked["answer"] and "field_mst_5" in linked["answer"]
    assert "4 MST khác nhau" in linked["answer"]



def test_l0_fx_not_comparable():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-FX"))
    assert out["review_state"] == "NOT_COMPARABLE"


def test_l0_table_300():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-TABLE300"))
    assert out["review_state"] == "ANSWERED"
    assert out["answer"]["meta"]["n_rows"] == 300


def test_compare_does_not_stop_at_l0():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-DIEU5"))
    assert "L1" in out["layers_used"]
    assert "L3" in out["layers_used"]
    assert "L2" in out["layers_used"]
    assert out["review_state"] == "NEEDS_REVIEW"


@pytest.mark.llm
@pytest.mark.live
def test_optional_l2_llm():
    from app.llm.client import NineRouterClient

    llm = NineRouterClient()
    if not llm.configured():
        pytest.skip("9Router not configured")
    pack = load_case("HD-TONG-HOP")
    store = InMemorySnapshotStore()
    store.put(pack.record)
    out = FourLayerReasoner(ToolGateway(store), llm).run(
        pack.envelope, next(t for t in TASKS if t["id"] == "T-CASCADE")
    )
    assert "L2" in out["layers_used"]
    assert "legal_winner" not in str(out.get("answer")).lower()


def test_l3_rejects_empty_must_cite_answered():
    pack, stack = _stack()
    fake = {
        "id": "x",
        "type": "lookup",
        "query": "x",
        "must_cite": ["no_such"],
        "forbidden": [],
    }
    grounded = L3Ground(stack.l3.gateway).run(
        pack.envelope,
        fake,
        review_state="ANSWERED",
        answer="not-in-source-zzz",
        citations=[],
    )
    assert grounded["review_state"] == "INSUFFICIENT_EVIDENCE"


def test_l1_does_not_use_raw_query_as_structured_key():
    pack, stack = _stack()
    gw = stack.l1.gateway
    seen: list[str] = []
    orig = gw.search_structured

    def wrap(envelope, key, filters=None):
        seen.append(key)
        return orig(envelope, key, filters)

    gw.search_structured = wrap
    q = "How are working days defined versus payment after acceptance?"
    out = stack.l1.run(pack.envelope, {"type": "lookup_term", "query": q})
    assert q not in seen
    assert all(k.islower() and " " not in k for k in seen)
    assert out["hits"]


def test_paraphrase_working_days():
    pack, stack = _stack()
    task = next(t for t in TASKS if t["id"] == "T-PARA")
    out = stack.run(pack.envelope, task)
    assert "L1" in out["layers_used"]
    assert out["review_state"] in {"ANSWERED", "NEEDS_REVIEW"}
    nids = {c.get("node_id") for c in out.get("citations") or []}
    outline = {n.node_id for n in pack.record.nodes}
    assert nids <= outline
    assert nids & {"cl_1_1", "cl_8"}


def test_summary_refused():
    pack, stack = _stack()
    from app.reasoning.query import classify_ask

    task = classify_ask("Tóm tắt toàn bộ hợp đồng")
    assert task["type"] == "too_broad"
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-SUMMARY"))
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert "L2" not in out["layers_used"]
    assert out.get("last_prompt_chars", 0) == 0


def test_missing_pl7_not_invented():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-PL7"))
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert "không bịa" in str(out["answer"]).lower() or "Không" in str(out["answer"])


def test_l2_fallback_compare_has_citations():
    pack, stack = _stack()
    out = stack.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-DIEU5"))
    assert "L2" in out["layers_used"]
    assert out["review_state"] == "NEEDS_REVIEW"
    assert len(out.get("citations") or []) >= 2
    outline = {n.node_id for n in pack.record.nodes}
    assert {c["node_id"] for c in out["citations"]} <= outline
    assert "legal_winner" not in str(out.get("answer")).lower()


def test_l3_drops_fake_node_id():
    pack, stack = _stack()
    grounded = L3Ground(stack.l3.gateway).run(
        pack.envelope,
        {"type": "compare", "query": "x", "must_cite": [], "forbidden": ["legal_winner"]},
        review_state="NEEDS_REVIEW",
        answer="Phụ lục 99 bịa",
        citations=[{"node_id": "ghost_node", "text_span": "fake"}, {"node_id": "cl_8", "text_span": "Ngày làm việc"}],
    )
    nids = {c["node_id"] for c in grounded["citations"]}
    assert "ghost_node" not in nids
    assert "cl_8" in nids


def test_gold_remap_by_label():
    from app.reasoning.gold import remap_must_cite

    pack = load_case("HD-TONG-HOP")
    mapped = remap_must_cite(["cl_9"], pack.record.nodes)
    assert mapped == ["cl_9"]


def test_party_card_ben_a():
    from app.reasoning.query import classify_ask

    task = classify_ask("Thông tin bên A?")
    assert task["type"] == "party_card"
    assert task["role"] == "A"
    assert classify_ask("Thong tin ben A?")["type"] == "party_card"
    pack, stack = _stack()
    out = stack.run(pack.envelope, task)
    ans = str(out["answer"])
    assert "Bên A" in ans
    assert "Điều 8" not in ans or "thanh toán" not in ans.lower()
    nids = {c.get("node_id") for c in out.get("citations") or []}
    assert "cl_8" not in nids


def test_annex_missing_pl7():
    from app.reasoning.query import classify_ask

    pack, stack = _stack()
    out = stack.run(pack.envelope, classify_ask("Phụ lục 7 gồm gì?"))
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert "không bịa" in str(out["answer"]).lower() or "Không" in str(out["answer"])


def test_unscoped_ask():
    from app.reasoning.query import classify_ask

    pack, stack = _stack()
    task = classify_ask("Hợp đồng này có ổn không?")
    assert task["type"] == "unscoped"
    out = stack.run(pack.envelope, task)
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"

    from app.reasoning.fact_link import count_parties
    from app.reasoning.query import classify_ask

    task = classify_ask("Có bao nhiêu bên trong hợp đồng?")
    assert task["type"] == "count_entity"
    pack, stack = _stack()
    out = stack.run(pack.envelope, task)
    assert "L2" not in out["layers_used"]
    assert re.search(r"Có \d+ bên", str(out["answer"]))
    assert "Bên A" in str(out["answer"])
    assert out["review_state"] in {"ANSWERED", "NEEDS_REVIEW"}

    linked = count_parties(
        [
            {"node_id": "a", "raw_label": "Bên A", "text": "Bên A: ABC"},
            {"node_id": "a2", "raw_label": "Bên A", "text": "Bên A lặp"},
            {"node_id": "b", "raw_label": "Bên B", "text": "Bên B: XYZ"},
        ],
        [],
    )
    assert linked["count"] == 2
    assert "2 bên" in linked["answer"]
    from app.reasoning.query import classify_ask

    task = classify_ask("Có bao nhiêu bên trong hợp đồng?")
    assert task["type"] == "count_entity"
    pack, stack = _stack()
    out = stack.run(pack.envelope, task)
    assert "L2" not in out["layers_used"]
    assert re.search(r"Có \d+ bên", str(out["answer"]))
    assert "Bên A" in str(out["answer"])
    assert out["review_state"] in {"ANSWERED", "NEEDS_REVIEW"}

    from app.reasoning.query import classify_ask

    task = classify_ask("Có bao nhiêu pháp nhân trong hợp đồng?")
    assert task["type"] == "count_entity"
    pack, stack = _stack()
    out = stack.run(pack.envelope, task)
    assert "L0" in out["layers_used"]
    assert "pháp nhân" in str(out["answer"]).lower()
    assert re.search(r"Có \d+ pháp nhân", str(out["answer"]))
    assert "không chọn" in str(out["answer"]).lower() or "Không chọn" in str(out["answer"])


def test_dieu5_surfaces_body_and_annex():
    from app.reasoning.query import classify_ask

    pack, stack = _stack()
    out = stack.run(pack.envelope, classify_ask("Điều 5 nói gì?"))
    nids = {c.get("node_id") for c in out.get("citations") or []}
    assert {"cl_5_body", "a_5_pl1", "a_5_pl2"} <= nids
    ans = str(out["answer"])
    assert "Thân HĐ" in ans and "Phụ lục" in ans
    assert "không suy ra" in ans.lower()
    assert out["review_state"] == "NEEDS_REVIEW"


def test_count_entities_dedupes_same_mst():
    from app.reasoning.fact_link import count_legal_entities

    mst = [
        {"node_id": "a", "value": "0311111111", "citation": {"node_id": "a", "text_span": "0311111111"}},
        {"node_id": "b", "value": "0311111111", "citation": {"node_id": "b", "text_span": "0311111111"}},
        {"node_id": "c", "value": "0312345678", "citation": {"node_id": "c", "text_span": "0312345678"}},
    ]
    out = count_legal_entities(mst, [])
    assert out["count"] == 2
    assert "2 pháp nhân" in out["answer"]



def test_ask_intent_does_not_swallow_the_question():
    from app.reasoning.query import classify_ask

    payment = classify_ask("Bên A phải thanh toán khi nào?")
    assert payment["type"] == "lookup_term"
    assert payment["attribute"] == "payment"
    penalty = classify_ask("Điều 5 phạt bao nhiêu?")
    assert penalty["type"] == "attribute_lookup"
    assert penalty["attribute"] == "penalty"
    assert classify_ask("tỷ suất hợp đồng là bao nhiêu?")["type"] != "compare"
    assert classify_ask("Gộp phạt xây lắp và phạt thiết bị")["type"] == "not_comparable"
    assert classify_ask("Quy đổi 100 USD sang VND theo hợp đồng")["type"] == "not_comparable"
    assert classify_ask("Điều 9 nói về gì?")["type"] == "lookup_clause"


def test_penalty_question_stays_inside_the_clause():
    from app.reasoning.query import classify_ask

    pack, stack = _stack()
    out = stack.run(pack.envelope, classify_ask("Điều 5 phạt bao nhiêu?"))
    answer = str(out["answer"])
    assert "phạt" in answer.lower()
    assert "các đoạn liên quan" not in answer.lower()
    assert "a_5_pl1" not in {c.get("node_id") for c in out.get("citations") or []}


def test_relation_question_answers_yes_or_missing():
    from app.contracts.models import SourceFile, TenantProfile
    from app.reasoning.query import classify_ask
    from fixtures.catalog import make_envelope, make_node, make_page, make_pins, make_record

    task = classify_ask("Điều khoản trong hợp đồng và phụ lục có liên quan đến nhau không?")
    assert task["type"] == "relation_ask"
    nodes = [
        make_node("cl_5", "CLAUSE", "Điều 5", "Điều 5 thân.", page=1, source_file_id="body_file"),
        make_node("pl_5", "CLAUSE", "Điều 5", "Phụ lục 1 Điều 5.", page=2, source_file_id="annex_file"),
    ]
    record = make_record(
        case_id="REL",
        dossier="rel-1",
        pages=[make_page(1, "Điều 5 thân."), make_page(2, "Phụ lục 1 Điều 5.")],
        nodes=nodes,
        pins=make_pins(source_snapshot_digest="c" * 64),
        profile=TenantProfile(version=1),
        source_files=[
            SourceFile(file_id="body_file", filename="body.pdf", role="body"),
            SourceFile(file_id="annex_file", filename="annex.pdf", role="annex"),
        ],
    )
    store = InMemorySnapshotStore()
    store.put(record)
    stack = FourLayerReasoner(ToolGateway(store), llm=None)
    out = stack.run(make_envelope(dossier="rel-1", pins=record.pins), task)
    assert str(out["answer"]).startswith("Có.")
    assert "các đoạn liên quan" not in str(out["answer"]).lower()
    assert {c.get("node_id") for c in out.get("citations") or []} >= {"cl_5", "pl_5"}


def test_contract_value_reads_labelled_line_without_a_fact():
    from app.contracts.models import TenantProfile
    from app.reasoning.query import classify_ask
    from fixtures.catalog import make_envelope, make_node, make_page, make_pins, make_record

    nodes = [make_node("price", "CLAUSE", "Giá", "Giá trị hợp đồng: 1.000.000.000 đồng", page=1)]
    record = make_record(
        case_id="VAL",
        dossier="val-1",
        pages=[make_page(1, "Giá trị hợp đồng: 1.000.000.000 đồng")],
        nodes=nodes,
        pins=make_pins(source_snapshot_digest="d" * 64),
        profile=TenantProfile(version=1),
    )
    store = InMemorySnapshotStore()
    store.put(record)
    stack = FourLayerReasoner(ToolGateway(store), llm=None)
    out = stack.run(make_envelope(dossier="val-1", pins=record.pins), classify_ask("Giá trị hợp đồng là bao nhiêu?"))
    assert out["review_state"] == "NEEDS_REVIEW"
    assert "1000000000" in str(out["answer"])
    assert out.get("l0_notes") == "value_from_text_not_fact"


def test_contract_value_ignores_penalty_amounts():
    from app.contracts.models import TenantProfile
    from app.reasoning.query import classify_ask
    from fixtures.catalog import make_envelope, make_node, make_page, make_pins, make_record

    nodes = [make_node("pen", "CLAUSE", "Phạt", "Phạt chậm 0,1%/ngày.", page=1)]
    record = make_record(
        case_id="PEN",
        dossier="pen-1",
        pages=[make_page(1, "Phạt chậm 0,1%/ngày.")],
        nodes=nodes,
        pins=make_pins(source_snapshot_digest="e" * 64),
        profile=TenantProfile(version=1),
    )
    store = InMemorySnapshotStore()
    store.put(record)
    stack = FourLayerReasoner(ToolGateway(store), llm=None)
    out = stack.run(make_envelope(dossier="pen-1", pins=record.pins), classify_ask("Giá trị hợp đồng là bao nhiêu?"))
    assert out["review_state"] == "INSUFFICIENT_EVIDENCE"
    assert "0,1" not in str(out["answer"])


def test_contract_value_question_lists_extracted_amounts():
    from app.pipeline.ai1_ingest import ingest_files
    from app.pipeline.idp import run_idp
    from app.reasoning.query import classify_ask

    root = Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "demo-xung-dot"
    body = root / "Hop-dong-mua-ban-thiet-bi-xet-nghiem.pdf"
    annex = root / "Phu-luc-01-sua-doi-gia-va-phat.pdf"
    if not body.exists() or not annex.exists():
        return
    rec, env, _, _ = ingest_files([
        (body.name, body.read_bytes(), "body"),
        (annex.name, annex.read_bytes(), "annex"),
    ])
    job = run_idp(rec, env, llm=None)
    rec.facts = job.contribution.facts
    store = InMemorySnapshotStore()
    store.put(rec)
    task = classify_ask("So sánh giá trị hợp đồng giữa thân và phụ lục")
    assert task["type"] == "field_card"
    assert task["attribute"] == "contract_value"
    out = FourLayerReasoner(ToolGateway(store), llm=None).run(env, task)
    assert out["layers_used"] == ["L0", "L3"]
    answer = str(out["answer"])
    assert "Các đoạn liên quan" not in answer
    assert "2450000000" in answer
    assert "2860000000" in answer
    assert "2180000000" in answer


@pytest.mark.llm
@pytest.mark.live
def test_llm_compare_dieu5_guardrails():
    from app.llm.client import NineRouterClient

    llm = NineRouterClient()
    if not llm.configured():
        pytest.skip("9Router not configured")
    pack = load_case("HD-TONG-HOP")
    store = InMemorySnapshotStore()
    store.put(pack.record)
    reasoner = FourLayerReasoner(ToolGateway(store), llm)
    out = reasoner.run(pack.envelope, next(t for t in TASKS if t["id"] == "T-DIEU5"))
    assert "L2" in out["layers_used"]
    assert out["review_state"] == "NEEDS_REVIEW"
    assert "legal_winner" not in str(out.get("answer")).lower()
    outline = {n.node_id for n in pack.record.nodes}
    cites = [c for c in (out.get("citations") or []) if c.get("node_id") in outline]
    assert len(cites) >= 2
    assert out.get("last_prompt_chars", 0) < 80_000


@pytest.mark.llm
@pytest.mark.live
def test_llm_summary_no_dump():
    from app.llm.client import NineRouterClient

    llm = NineRouterClient()
    if not llm.configured():
        pytest.skip("9Router not configured")
    pack, _ = _stack()
    store = InMemorySnapshotStore()
    store.put(pack.record)
    out = FourLayerReasoner(ToolGateway(store), llm).run(
        pack.envelope, next(t for t in TASKS if t["id"] == "T-SUMMARY")
    )
    assert out["review_state"] in {"INSUFFICIENT_EVIDENCE", "NEEDS_REVIEW"}
    assert out["review_state"] != "ANSWERED"
    assert out.get("last_prompt_chars", 0) == 0
    assert "L2" not in out["layers_used"]
