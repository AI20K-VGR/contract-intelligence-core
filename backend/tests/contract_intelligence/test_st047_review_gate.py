from __future__ import annotations

import pytest

from contract_intelligence.shared.ai.index_gate import IndexContributionGate


def _proposal(*, digest: str = "sha256:current", version: str = "idx-1") -> dict:
    return {
        "tenant_id": "tenant-a",
        "dossier_id": "dossier-1",
        "snapshot_digest": digest,
        "proposed_index_version": version,
        "publish": "propose",
        "facts": [],
        "findings": [],
    }


def test_reviewer_gate_keeps_proposal_inactive_until_approval_and_is_idempotent():
    gate = IndexContributionGate()
    proposal = gate.propose(_proposal(), idempotency_key="proposal-1")

    assert proposal.replayed is False
    assert gate.active_pointer("tenant-a", "dossier-1") is None

    rejected = gate.review(
        proposal.key,
        reviewer_id="reviewer-1",
        decision="REJECT",
        idempotency_key="review-1",
    )
    assert rejected.active_pointer is None
    assert gate.active_pointer("tenant-a", "dossier-1") is None

    approved = gate.review(
        proposal.key,
        reviewer_id="reviewer-1",
        decision="APPROVE",
        idempotency_key="review-2",
    )
    replay = gate.review(
        proposal.key,
        reviewer_id="reviewer-1",
        decision="APPROVE",
        idempotency_key="review-2",
    )
    assert approved.active_pointer == "idx-1"
    assert replay.replayed is True
    assert gate.active_pointer("tenant-a", "dossier-1") == "idx-1"
    assert [entry["decision"] for entry in gate.audit_log] == ["REJECT", "APPROVE"]


def test_reviewer_gate_rejects_cross_scope_and_non_proposal_payloads():
    gate = IndexContributionGate()

    with pytest.raises(ValueError, match="publish must be propose"):
        gate.propose({**_proposal(), "publish": "active"}, idempotency_key="bad-1")

    proposal = gate.propose(_proposal(), idempotency_key="proposal-1")
    with pytest.raises(KeyError, match="proposal scope"):
        gate.review(
            proposal.key.with_digest("sha256:other"),
            reviewer_id="reviewer-1",
            decision="APPROVE",
            idempotency_key="review-3",
        )
