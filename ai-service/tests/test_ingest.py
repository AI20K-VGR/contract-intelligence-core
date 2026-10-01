from app.pipeline.ai1_ingest import ingest_files, ingest_upload
from app.pipeline.handoff import HandoffValidator
from app.pipeline.outline import build_tree, locate
from app.reasoning.query import classify_ask
from app.reasoning.stack import FourLayerReasoner
from app.tools.gateway import ToolGateway
from app.tools.store import InMemorySnapshotStore


def test_upload_does_not_feed_pdf_bytes_to_ai2():
    rec, env, meta, blobs = ingest_upload("hop-dong.md", b"Dieu 1\nMST 0312345678\n---\nDieu 5 Gia")
    assert rec.pages
    assert env.auth.dossier_id == rec.dossier_id
    assert "text" in meta["engine"]
    hv = HandoffValidator()
    out = hv.validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
        expected_page_count=len(rec.pages),
        lifecycle=rec.lifecycle,
        pdf_bytes=None,
    )
    assert out.blocked is False
    blocked = hv.validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
        pdf_bytes=b"%PDF",
    )
    assert blocked.blocked is True
    assert blobs


def test_two_files_tree_and_locate():
    body = "PHẦN 1\nĐiều 9. Bảo mật. Xem Phụ lục 7 về bảo mật.\nMST 0312345678".encode("utf-8")
    annex = "PHỤ LỤC 1\nĐiều 5. Phạt chậm 0,1%/ngày.".encode("utf-8")
    rec, env, meta, blobs = ingest_files(
        [("HD.body.md", body, "body"), ("HD.annex.md", annex, "annex")]
    )
    assert len(rec.source_files) == 2
    tree = build_tree(rec.nodes)
    assert len(tree) == 2
    dieu9 = next(n for n in rec.nodes if (n.raw_label or "").startswith("Điều 9"))
    loc = locate(rec.nodes, rec.pages, dieu9.node_id)
    assert loc["file_id"] == dieu9.source_file_id
    assert loc["page_in_file"] == 1
    mst = next(n for n in rec.nodes if n.structured_key == "mst_seller")
    mloc = locate(rec.nodes, rec.pages, mst.node_id)
    assert mloc["text_span"] == "0312345678"
    assert mloc["page_in_file"] == mst.page_in_file
    store = InMemorySnapshotStore()
    store.put(rec)
    out = FourLayerReasoner(ToolGateway(store), llm=None).run(env, classify_ask("Điều 9 nói về gì?"))
    assert out["review_state"] == "ANSWERED"
    assert "Phụ lục 7" in str(out["answer"])


def test_ingest_compare_item_and_fee_fields():
    text = (
        "Điều 3. Giá\nItem A: 100000 VND\nItem B: 200000 VND\n"
        "Hợp đồng viện dẫn Phụ lục 9.\nPhí X: 50%\n"
        "Phụ lục 1\nsửa A thành 110000 VND từ 01/07\nPhí X: 40%\n"
        "Phụ lục 2\nA: 105000 VND\nPhí Y: 10%\n"
    ).encode("utf-8")
    rec, env, meta, blobs = ingest_files([("SALE-BRD.md", text, "body")])
    keys = {(n.structured_key, n.structured_value) for n in rec.nodes if n.structured_key}
    assert ("item:A", "100000") in keys
    assert ("item:B", "200000") in keys
    assert ("scope:X", "50%") in keys
    assert ("scope:Y", "10%") in keys
    assert any(n.structured_key == "annex_ref" for n in rec.nodes)
    from app.pipeline.idp import run_idp
    from app.contracts.models import Disposition

    job = run_idp(rec, env)
    cands = job.contribution.candidates if job.contribution else []
    assert any(x.disposition == Disposition.CANDIDATE_AMENDMENT for x in cands)
    assert any(x.disposition == Disposition.NOT_COMPARABLE for x in cands)


def test_ingest_party_b_not_all_cong_ty():
    body = "Bên A: Công ty ABC MST 0312345678\nBên B: Công ty XYZ MST 0322222222\nCông ty khác không vai.\n".encode("utf-8")
    rec, env, meta, blobs = ingest_files([("p.md", body, "body")])
    roles = {n.structured_key: n.structured_value for n in rec.nodes if n.structured_key in {"party_a", "party_b"}}
    assert roles.get("party_a", "").startswith("Công ty ABC")
    assert roles.get("party_b", "").startswith("Công ty XYZ")
    assert not any(
        n.structured_key == "party_a" and "không vai" in (n.text or "") for n in rec.nodes
    )


def test_ingest_same_line_extracts_all_parties_msts_and_value():
    body = (
        "Hợp đồng số 01. Bên A: Công ty ABC MST 0311111111. "
        "Bên B: Công ty XYZ MST 0322222222. Giá trị: 1.000.000.000 VND."
    ).encode("utf-8")
    rec, env, meta, blobs = ingest_files([("short.md", body, "body")])
    values = {(n.structured_key, n.structured_value) for n in rec.nodes if n.structured_key}
    assert ("party_a", "Công ty ABC") in values
    assert ("party_b", "Công ty XYZ") in values
    assert ("mst_party_a", "0311111111") in values
    assert ("mst_party_b", "0322222222") in values
    assert any(
        n.structured_key == "item:contract_value" and n.structured_value == "1000000000"
        for n in rec.nodes
    )


def test_hd_tong_hop_sample_pdf_extracts_and_answers_dieu_9():
    from pathlib import Path

    from app.pipeline.idp import run_idp

    pdf = Path(__file__).resolve().parents[1] / "fixtures" / "contracts" / "HD-TONG-HOP.sample.pdf"
    rec, env, meta, blobs = ingest_files([(pdf.name, pdf.read_bytes(), "body")])
    assert rec.pages
    job = run_idp(rec, env)
    assert job.status.value == "SUCCEEDED"
    assert job.contribution is not None
    assert job.contribution.facts
    missing = {i.missing.lower() for i in job.contribution.evidence_issues}
    assert "phụ lục 1" not in missing
    store = InMemorySnapshotStore()
    store.put(rec)
    out = FourLayerReasoner(ToolGateway(store), llm=None).run(env, classify_ask("Dieu 9 noi ve gi?"))
    assert out["review_state"] == "ANSWERED"
    ans = str(out["answer"]).lower()
    assert "giá" in ans or "gia" in ans or "tạm ứng" in ans or "tam ung" in ans
    assert classify_ask("Thong tin ben A?")["type"] == "party_card"
    party = FourLayerReasoner(ToolGateway(store), llm=None).run(env, classify_ask("Thong tin ben A?"))
    assert party["review_state"] in {"ANSWERED", "NEEDS_REVIEW"}
    assert "Bên A" in str(party.get("answer")) or "ben a" in str(party.get("answer")).lower() or "ABC" in str(party.get("answer"))
    mst_findings = [x for x in job.contribution.candidates if x.item_key == "mst_party_a"]
    assert any(
        x.disposition and x.disposition.value == "COMPARABLE_DIFFERENCE" for x in mst_findings
    )
    assert not any(
        x.item_key == "mst_seller" and x.disposition and x.disposition.value == "COMPARABLE_DIFFERENCE"
        for x in job.contribution.candidates
    )
    keys = {n.structured_key for n in rec.nodes}
    assert "item:penalty_general" in keys
    assert "item:penalty_construction" in keys
    assert "item:contract_value" in keys
    assert any(
        x.item_key == "penalty_general"
        and x.scope
        and x.scope.value == "CONTRACT_ANNEX"
        and x.disposition
        and x.disposition.value in {"COMPARABLE_DIFFERENCE", "CANDIDATE_AMENDMENT"}
        for x in job.contribution.candidates
    )
    assert any(
        x.item_key == "contract_value" and x.scope and x.scope.value == "CONTRACT_ANNEX"
        for x in job.contribution.candidates
    )
    assert not any(
        x.item_key == "penalty"
        for x in job.contribution.candidates
    )
    party_a = [n for n in rec.nodes if n.structured_key == "party_a"]
    assert len(party_a) < 15


def test_clause_body_keeps_following_lines():
    rec, env, meta, blobs = ingest_files(
        [("c.md", "Điều 9. Giá hợp đồng\nTạm ứng 10 phần trăm.\nĐiều 10. Khác\n".encode("utf-8"), "body")]
    )
    dieu9 = next(n for n in rec.nodes if (n.raw_label or "").startswith("Điều 9"))
    assert "Tạm ứng" in (dieu9.text or "")
