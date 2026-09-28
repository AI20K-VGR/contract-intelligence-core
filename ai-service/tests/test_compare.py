from app.contracts.models import Citation, ComparisonScope, Disposition, Fact, FindingType
from app.pipeline.compare import compare_facts
from app.pipeline.idp import run_idp
from fixtures.catalog import load_case


def test_cited_annex_present_by_prefix_not_issue():
    facts = [
        Fact(
            fact_id="a",
            raw_value="Xem Phụ lục 1",
            citation=Citation(node_id="n", page_revision_id="p", text_span="Xem Phụ lục 1"),
        )
    ]
    _cands, issues = compare_facts(facts, annex_labels_present={"Phụ lục 1 — Sửa Điều 5"})
    assert issues == []


def test_sale_brd_07_amendment_isolated():
    pack = load_case("SALE-BRD-07")
    job = run_idp(pack.record, pack.envelope)
    c = job.contribution
    assert c is not None
    cands = c.candidates
    assert any(x.disposition == Disposition.CANDIDATE_AMENDMENT and x.item_key == "A" for x in cands)
    assert any(
        x.item_key == "A"
        and x.disposition in {Disposition.NEEDS_EVIDENCE, Disposition.COMPARABLE_DIFFERENCE}
        for x in cands
    )
    assert not any(x.item_key == "B" for x in cands)
    assert any(i.missing.lower() == "phụ lục 9" for i in c.evidence_issues)
    scopes = {x.scope for x in cands}
    assert ComparisonScope.CONTRACT_ANNEX in scopes or ComparisonScope.ANNEX_ANNEX in scopes


def test_service_brd_08_scope_not_comparable():
    pack = load_case("SERVICE-BRD-08")
    job = run_idp(pack.record, pack.envelope)
    c = job.contribution
    assert c is not None
    cands = c.candidates
    assert any(x.disposition == Disposition.COMPARABLE_DIFFERENCE for x in cands)
    assert any(x.disposition == Disposition.NOT_COMPARABLE for x in cands)
    assert any(x.finding_type == FindingType.GAP for x in cands)
    assert not any(x.model_disposition and x.model_disposition.value == "CONFLICTING" for x in cands)
    xy = [x for x in cands if x.disposition == Disposition.NOT_COMPARABLE]
    assert xy
def test_two_sources_same_context_only():
    def F(fid, val, key, role="body", validity=None, cond=None, unit="percent"):
        return Fact(
            fact_id=fid,
            raw_value=val,
            normalized_value=val,
            citation=Citation(node_id=fid, page_revision_id="p", text_span=val),
            item_key=key,
            source_role=role,
            validity=validity,
            condition=cond,
            scope=key,
            unit=unit,
            subject="Điều 5" if role == "body" else None,
        )

    cands, _ = compare_facts(
        [
            F("a", "0.2%", "penalty_general", "body", cond="general"),
            F("b", "0.1%", "penalty_construction", "body", cond="construction"),
            F("c", "0.05%", "penalty_equipment", "body", cond="equipment"),
            F("d", "0.1%", "penalty_general", "annex", "PL1", cond="general"),
            F("e", "0.05%", "penalty_general", "annex", "PL2", cond="general"),
            F("v1", "1000000000", "contract_value", "body", unit="VND"),
            F("v2", "1100000000", "contract_value", "annex", "PL1", unit="VND"),
        ]
    )
    gen = [x for x in cands if x.item_key == "penalty_general"]
    assert len(gen) == 2
    assert all(x.scope == ComparisonScope.CONTRACT_ANNEX for x in gen)
    assert all(x.disposition == Disposition.COMPARABLE_DIFFERENCE for x in gen)
    assert all("Nguồn 1" in x.reason and "Nguồn 2" in x.reason for x in gen)
    assert not any(x.item_key == "penalty_construction" for x in cands)
    price = [x for x in cands if x.item_key == "contract_value"]
    assert len(price) == 1
    assert all(len(x.evidence_left) == 1 and len(x.evidence_right) == 1 for x in cands)


def test_party_identity_facts_are_not_comparable_terms():
    facts = [
        Fact(
            fact_id="party-a",
            raw_value="Cong ty A",
            normalized_value="Cong ty A",
            role="party_a",
            scope="same-dossier",
            citation=Citation(node_id="party-a", page_revision_id="p", text_span="Cong ty A"),
        ),
        Fact(
            fact_id="party-b",
            raw_value="Cong ty B",
            normalized_value="Cong ty B",
            role="party_b",
            scope="same-dossier",
            citation=Citation(node_id="party-b", page_revision_id="p", text_span="Cong ty B"),
        ),
    ]

    candidates, _ = compare_facts(facts)

    assert candidates == []
