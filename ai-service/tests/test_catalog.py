from fixtures.catalog import all_cases
from app.contracts.models import LifecycleState
from app.pipeline.handoff import HandoffValidator
from app.sandbox import run_user_code
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import InMemorySnapshotStore


def test_all_ec_and_happy_present():
    cases = all_cases()
    for i in range(1, 57):
        assert f"EC-{i:03d}" in cases
    for i in range(1, 7):
        assert f"HAPPY-{i:03d}" in cases
    assert "HD-TONG-HOP" in cases
    assert "SALE-BRD-07" in cases
    assert "SERVICE-BRD-08" in cases
    assert len(cases) >= 65


def test_happy_001_tree_does_not_invent_articles_and_contains_both_parties():
    rec = all_cases()["HAPPY-001"].record
    assert not any((n.raw_label or "").startswith("Điều ") for n in rec.nodes)
    assert {n.structured_value for n in rec.nodes if n.structured_key == "party_a"} == {"Công ty ABC"}
    assert {n.structured_value for n in rec.nodes if n.structured_key == "party_b"} == {"Công ty XYZ"}
    assert {n.structured_value for n in rec.nodes if n.structured_key == "mst_party_b"} == {"0322222222"}
    root = next(n for n in rec.nodes if n.node_id == "doc_contract")
    assert all(n.parent_id == root.node_id for n in rec.nodes if n.node_id != root.node_id)


def test_hd_tong_hop_covers_long_body_and_annexes():
    pack = all_cases()["HD-TONG-HOP"]
    rec = pack.record
    assert len(rec.pages) == 65
    assert rec.pages[0].page_number == 1
    assert rec.pages[49].page_number == 50
    labels = {n.raw_label for n in rec.nodes}
    assert "Điều 3" not in labels
    assert any(n.raw_label == "Điều 5" and n.parent_id == "doc_contract" for n in rec.nodes)
    assert any(n.raw_label == "Điều 5" and n.parent_id == "doc_pl1" for n in rec.nodes)
    assert any(n.type == "UNNUMBERED_BLOCK" for n in rec.nodes)
    assert any(n.structured_value == "0312345678" for n in rec.nodes)
    assert any(n.structured_value == "0399999999" for n in rec.nodes)
    t300 = next(t for t in rec.tables if t.table_id == "table_300")
    assert len(t300.rows) == 300
    assert pack.expected_state == "REVIEW"



def test_ec001_has_62_pages():
    rec = all_cases()["EC-001"].record
    assert len(rec.pages) == 62
    mst = next(n for n in rec.nodes if n.structured_key == "mst_seller")
    assert mst.structured_value == "0312345678"


def test_ec010_has_300_rows_meta_sample():
    rec = all_cases()["EC-010"].record
    assert len(rec.tables[0].rows) == 300
    assert rec.tables[0].rows[0][0] == "R001"
    assert rec.tables[0].rows[-1][0] == "R300"


def test_ec015_sentinels_not_zero():
    rows = all_cases()["EC-015"].record.tables[0].rows
    amounts = [r[1] for r in rows]
    assert None in amounts
    assert "-" in amounts
    assert "N/A" in amounts
    assert "0" in amounts
    code = """
result = []
for i, row in enumerate(rows):
    val = decimal(row[1])
    result.append(val)
"""
    out = run_user_code(code, rows, ["item", "amount"])
    # dash/N/A/empty/None -> None, literal 0 stays 0
    assert out["rows_out"][1] is None
    assert out["rows_out"][4] == 0 or str(out["rows_out"][4]) == "0"


def test_ec017_two_tables_not_one():
    rec = all_cases()["EC-017"].record
    assert len(rec.tables) == 2
    assert rec.tables[0].title != rec.tables[1].title


def test_ec045_encrypted_blocked_by_handoff():
    pack = all_cases()["EC-045"]
    rec = pack.record
    out = HandoffValidator().validate(
        tenant_id=rec.tenant_id,
        dossier_id=rec.dossier_id,
        pins=rec.pins,
        pages=rec.pages,
        nodes=rec.nodes,
        tables=rec.tables,
        profile=rec.profile,
        lifecycle=rec.lifecycle,
    )
    assert out.blocked


def test_ec053_cross_tenant_blocked():
    pack = all_cases()["EC-053"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gw = ToolGateway(store)
    try:
        gw.call("list_structure", pack.envelope)
        assert False
    except ToolBlocked:
        pass


def test_ec054_acl_revision_blocked():
    pack = all_cases()["EC-054"]
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gw = ToolGateway(store)
    try:
        gw.call("list_structure", pack.envelope)
        assert False
    except ToolBlocked:
        pass


def test_ec056_soft_deleted_blocked():
    pack = all_cases()["EC-056"]
    assert pack.record.legal_hold is True
    assert pack.record.lifecycle == LifecycleState.SOFT_DELETED
    store = InMemorySnapshotStore()
    store.put(pack.record)
    gw = ToolGateway(store)
    try:
        gw.call("list_structure", pack.envelope)
        assert False
    except ToolBlocked:
        pass


def test_ec003_unnumbered():
    rec = all_cases()["EC-003"].record
    assert rec.nodes[0].type == "UNNUMBERED_BLOCK"
    assert rec.nodes[0].raw_label == "Thanh toán"


def test_expected_no_legal_winner_flags():
    cases = all_cases()
    for cid in ["EC-027", "EC-029", "EC-031", "EC-033"]:
        assert "legal_winner" in cases[cid].expected_no_claims
