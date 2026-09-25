"""Reviewer-controlled gate for AI2 index contributions.

AI2 may propose a contribution, but only an explicit reviewer decision may
move the active pointer. The in-memory store is the seam used by the current
worker/tests; production persistence can implement the same contract without
changing the AI2 wire payload.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any


@dataclass(frozen=True)
class ProposalKey:
    tenant_id: str
    dossier_id: str
    snapshot_digest: str
    proposed_index_version: str

    def with_digest(self, snapshot_digest: str) -> ProposalKey:
        return ProposalKey(
            tenant_id=self.tenant_id,
            dossier_id=self.dossier_id,
            snapshot_digest=snapshot_digest,
            proposed_index_version=self.proposed_index_version,
        )


@dataclass(frozen=True)
class ProposalReceipt:
    key: ProposalKey
    replayed: bool


@dataclass(frozen=True)
class ReviewReceipt:
    key: ProposalKey
    decision: str
    active_pointer: str | None
    replayed: bool


class IndexContributionGate:
    """Small, explicit reviewer gate with scope and idempotency invariants."""

    def __init__(self) -> None:
        self._proposals: dict[ProposalKey, dict[str, Any]] = {}
        self._proposal_requests: dict[str, ProposalKey] = {}
        self._review_requests: dict[str, ReviewReceipt] = {}
        self._active: dict[tuple[str, str], str] = {}
        self.audit_log: list[dict[str, str]] = []

    def propose(self, payload: dict[str, Any], *, idempotency_key: str) -> ProposalReceipt:
        if payload.get("publish") != "propose":
            raise ValueError("publish must be propose")
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        key = ProposalKey(
            tenant_id=str(payload.get("tenant_id") or ""),
            dossier_id=str(payload.get("dossier_id") or ""),
            snapshot_digest=str(payload.get("snapshot_digest") or ""),
            proposed_index_version=str(payload.get("proposed_index_version") or ""),
        )
        if not all(
            (key.tenant_id, key.dossier_id, key.snapshot_digest, key.proposed_index_version)
        ):
            raise ValueError("proposal scope is incomplete")
        previous = self._proposal_requests.get(idempotency_key)
        if previous is not None:
            if previous != key:
                raise ValueError("idempotency key reused for another proposal")
            return ProposalReceipt(key=key, replayed=True)
        self._proposal_requests[idempotency_key] = key
        self._proposals[key] = dict(payload)
        return ProposalReceipt(key=key, replayed=False)

    def review(
        self,
        key: ProposalKey,
        *,
        reviewer_id: str,
        decision: str,
        idempotency_key: str,
    ) -> ReviewReceipt:
        if key not in self._proposals:
            raise KeyError("proposal scope is unknown")
        if not reviewer_id:
            raise ValueError("reviewer_id is required")
        decision = decision.upper()
        if decision not in {"APPROVE", "REJECT"}:
            raise ValueError("decision must be APPROVE or REJECT")
        if not idempotency_key:
            raise ValueError("idempotency_key is required")
        previous = self._review_requests.get(idempotency_key)
        if previous is not None:
            if previous.key != key or previous.decision != decision:
                raise ValueError("idempotency key reused for another review")
            return ReviewReceipt(
                key=previous.key,
                decision=previous.decision,
                active_pointer=previous.active_pointer,
                replayed=True,
            )
        active_pointer = None
        if decision == "APPROVE":
            active_pointer = key.proposed_index_version
            self._active[(key.tenant_id, key.dossier_id)] = active_pointer
        receipt = ReviewReceipt(
            key=key,
            decision=decision,
            active_pointer=active_pointer,
            replayed=False,
        )
        self._review_requests[idempotency_key] = receipt
        self.audit_log.append(
            {
                "tenant_id": key.tenant_id,
                "dossier_id": key.dossier_id,
                "snapshot_digest": key.snapshot_digest,
                "reviewer_id": reviewer_id,
                "decision": decision,
                "idempotency_key": idempotency_key,
            }
        )
        return receipt

    def active_pointer(self, tenant_id: str, dossier_id: str) -> str | None:
        return self._active.get((tenant_id, dossier_id))
