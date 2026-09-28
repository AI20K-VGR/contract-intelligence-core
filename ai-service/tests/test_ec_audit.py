"""Every EC fixture keeps its source shape. Catalog PASS is not a license to
silence the citation gate: several jobs stay NEEDS_REVIEW because the fixture
has no source hash or line ids. That is unverified provenance, not an invented
value.
"""

from fixtures.catalog import BUILDERS, CasePack, all_cases

from app.pipeline.idp import run_idp


def _raw_case(case_id: str) -> CasePack:
    """The fixture as authored, before the eval oracle seals PASS provenance.

    ``all_cases`` hands PASS-labelled cases a document root and line-backed
    text so the oracle can score them; these audits are about what AI2 does
    when that provenance is genuinely missing.
    """
    for build in BUILDERS:
        pack = build()
        if pack.case_id == case_id:
            return pack
    raise KeyError(case_id)


def test_every_ec_keeps_nodes_rows_and_does_not_name_a_legal_winner():
    cases = all_cases()
    ids = [case_id for case_id in cases if case_id.startswith("EC-")]
    assert len(ids) == 56
    for case_id in ids:
        pack = cases[case_id]
        node_ids = [node.node_id for node in pack.record.nodes]
        rows = [list(table.rows) for table in pack.record.tables]
        labels = [node.raw_label for node in pack.record.nodes]
        job = run_idp(pack.record, pack.envelope)
        assert [node.node_id for node in pack.record.nodes] == node_ids, case_id
        assert [node.raw_label for node in pack.record.nodes] == labels, case_id
        assert [list(table.rows) for table in pack.record.tables] == rows, case_id
        assert '"legal_winner": true' not in job.model_dump_json(), case_id


def test_relative_date_is_not_rewritten_as_a_calendar_day():
    pack = all_cases()["EC-022"]
    run_idp(pack.record, pack.envelope)
    raw_values = [fact.raw_value for fact in pack.record.facts]
    assert "trong vòng ba mươi ngày kể từ ngày ký" in raw_values
    assert not any(value and value[:4].isdigit() and "-" in value for value in raw_values)


def test_live_annex_boilerplate_is_not_an_annex_key():
    from app.pipeline.compare import annex_keys_from_labels

    keys = annex_keys_from_labels(
        [
            "PHỤ LỤC 01 - BẢNG KHỐI LƯỢNG, THIẾT BỊ VÀ DỊCH VỤ",
            "Phụ lục này được lập thành 04 bản và có hiệu lực cùng ngày với hợp đồng.",
            "Phụ lục 02",
        ]
    )
    assert keys == {"Phụ lục 01", "Phụ lục 02"}


def test_big_table_is_not_truncated():
    pack = all_cases()["EC-010"]
    run_idp(pack.record, pack.envelope)
    assert len(pack.record.tables) == 1
    assert len(pack.record.tables[0].rows) == 300


def test_duplicate_mst_is_published_once_and_both_nodes_remain():
    pack = _raw_case("EC-038")
    run_idp(pack.record, pack.envelope)
    assert [node.node_id for node in pack.record.nodes] == ["d1", "d2"]
    published = [fact for fact in pack.record.facts if fact.item_key == "mst_seller" and fact.raw_value == "0312345678"]
    assert len(published) == 1


def test_fixtures_missing_provenance_stay_in_review():
    """Catalog PASS is not granted when the fixture citation cannot be verified."""

    from app.contracts.models import ReviewState

    held = [
        "EC-001",
        "EC-009",
        "EC-010",
        "EC-016",
        "EC-022",
        "EC-023",
        "EC-025",
        "EC-030",
        "EC-034",
        "EC-038",
        "EC-051",
    ]
    # EC-036/037 carry real line ids and page hashes, so PASS is earned there.
    for case_id in held:
        pack = _raw_case(case_id)
        job = run_idp(pack.record, pack.envelope)
        assert job.review_state is not ReviewState.PASS, case_id
        assert pack.record.review_items, case_id


def test_injection_is_reviewed_on_the_question_not_by_rewriting_the_page():
    from app.reasoning.query import classify_ask
    from app.reasoning.stack import FourLayerReasoner
    from app.tools.gateway import ToolGateway
    from app.tools.store import InMemorySnapshotStore

    pack = all_cases()["EC-035"]
    before = [node.text for node in pack.record.nodes]
    job = run_idp(pack.record, pack.envelope)
    assert [node.text for node in pack.record.nodes] == before
    assert job.status.value == "SUCCEEDED"
    store = InMemorySnapshotStore()
    store.put(pack.record)
    out = FourLayerReasoner(ToolGateway(store), llm=None).run(pack.envelope, classify_ask(pack.query))
    assert out["review_state"] == "NEEDS_REVIEW"


def test_english_seller_tax_code_cites_the_mst():
    from app.reasoning.query import classify_ask
    from app.reasoning.stack import FourLayerReasoner
    from app.tools.gateway import ToolGateway
    from app.tools.store import InMemorySnapshotStore

    pack = all_cases()["EC-037"]
    spec = classify_ask(pack.query)
    assert spec["type"] == "field_card"
    assert spec["field_key"] == "mst_seller"
    store = InMemorySnapshotStore()
    store.put(pack.record)
    out = FourLayerReasoner(ToolGateway(store), llm=None).run(pack.envelope, spec)
    assert out["review_state"] != "INSUFFICIENT_EVIDENCE"
    blob = str(out)
    assert "0311111111" in blob
    assert out.get("citations")
