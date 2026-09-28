from __future__ import annotations

from app.contracts.models import (
    Citation,
    Fact,
    FindingType,
    ModelDisposition,
)
from app.pipeline.compare import compare_facts
from app.pipeline.fact import FactExtractor
from fixtures import PROFILE, envelope


def _fact(
    fact_id: str,
    value: str,
    *,
    role: str,
    source_file_id: str,
    node_id: str,
    item_key: str = "payment_term",
) -> Fact:
    return Fact(
        fact_id=fact_id,
        raw_value=value,
        normalized_value=value,
        subject="Điều 5",
        item_key=item_key,
        source_role=role,
        scope=item_key,
        citation=Citation(
            node_id=node_id,
            page_revision_id=f"{node_id}:rev-1",
            source_file_id=source_file_id,
            text_span=value,
        ),
        provenance="L0",
    )


def test_cross_document_body_annex_requires_relation_evidence():
    body = _fact("body-1", "30 ngày", role="body", source_file_id="body-doc", node_id="body-node")
    annex = _fact("annex-1", "45 ngày", role="annex", source_file_id="annex-doc", node_id="annex-node")

    candidates, issues = compare_facts([body, annex])

    assert candidates == []
    assert any(issue.missing == "BODY_ANNEX_RELATION" for issue in issues)


def test_relation_evidence_allows_body_annex_finding_without_legal_winner():
    body = _fact("body-1", "30", role="body", source_file_id="body-doc", node_id="body-node")
    annex = _fact("annex-1", "45", role="annex", source_file_id="annex-doc", node_id="annex-node")

    candidates, issues = compare_facts(
        [body, annex],
        relation_pairs={("body-node", "annex-node")},
    )

    assert issues == []
    assert len(candidates) == 1
    finding = candidates[0]
    assert finding.model_disposition == ModelDisposition.UNCLEAR
    assert finding.finding_type != FindingType("MATCH")
    assert "LEGAL_WINNER" not in finding.model_dump_json()


def test_fact_extraction_preserves_typed_evidence_layers():
    class Gateway:
        def call(self, _tool: str, _envelope, *, node_id: str) -> dict:
            assert node_id == "node-1"
            return {
                "text": "Payment term: 30%",
                "structured_value": "30%",
                "structured_key": "item:payment_term",
                "raw_label": "Payment term",
                "ancestors": ["Clause 5"],
                "citation": {
                    "node_id": "node-1",
                    "page_revision_id": "page-1",
                    "text_span": "30%",
                },
            }

    fact = FactExtractor(Gateway()).extract(envelope(), "node-1", PROFILE)

    assert fact.raw_value == "30%"
    assert fact.normalized_value == "30"
    assert fact.subject == "Payment term"
    assert fact.citation.node_id == "node-1"
    assert fact.provenance == "L0"
