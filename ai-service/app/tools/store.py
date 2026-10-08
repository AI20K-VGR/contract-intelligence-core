from __future__ import annotations

from dataclasses import dataclass, field
from typing import TYPE_CHECKING

from app.contracts.models import (
    Chunk,
    Citation,
    ContractEvent,
    Fact,
    HandoffIssue,
    LifecycleState,
    PageSnapshot,
    RelationGraph,
    ReviewItem,
    SourceFile,
    StructuralNode,
    TableSnapshot,
    TenantProfile,
    VersionPins,
)

if TYPE_CHECKING:  # flag off must not import the contract-graph model
    from app.contracts.contract_graph import ContractEdge


@dataclass
class DossierRecord:
    tenant_id: str
    dossier_id: str
    lifecycle: LifecycleState
    pins: VersionPins
    pages: list[PageSnapshot]
    nodes: list[StructuralNode]
    tables: list[TableSnapshot]
    profile: TenantProfile
    acl_revision: int
    permissions_by_actor: dict[str, list[str]]
    source_files: list[SourceFile] = field(default_factory=list)
    facts: list[Fact] = field(default_factory=list)
    input_facts: list[Fact] | None = None
    chunks: list[Chunk] = field(default_factory=list)
    active_index_version: str | None = None
    processing_index: bool = False
    legal_hold: bool = False
    # Backward-compatible legacy flag. New inputs should use explicit gates.
    egress_approved: bool = True
    budget_exceeded: bool = False
    processing_budget_exceeded: bool = False
    embedding_budget_exceeded: bool = False
    index_status: str = "READY"
    case_id: str | None = None
    handoff_issues: list[HandoffIssue] = field(default_factory=list)
    relation_graph: RelationGraph | None = None
    active_nodes: list[StructuralNode] | None = None
    citation_index: dict[str, Citation] = field(default_factory=dict)
    review_items: list[ReviewItem] = field(default_factory=list)
    events: list[ContractEvent] = field(default_factory=list)
    # D8: edges reach the job store on the record, never on ``JobResult`` (its dump is persisted).
    # Not part of ``record_to_dict``; ``contract_graph_ran`` False keeps the stored edges as they are.
    contract_edges: list[ContractEdge] = field(default_factory=list)
    contract_graph_ran: bool = False

    def evidence_nodes(self) -> list[StructuralNode]:
        """Nodes allowed for UI/reasoning; raw ``nodes`` remains immutable."""

        return self.active_nodes if self.active_nodes is not None else self.nodes

    def processing_budget_hit(self) -> bool:
        if self.processing_budget_exceeded:
            return True
        return self.budget_exceeded and not self.embedding_budget_exceeded

    def embedding_budget_hit(self) -> bool:
        if self.embedding_budget_exceeded:
            return True
        return self.budget_exceeded and not self.processing_budget_exceeded


class InMemorySnapshotStore:
    def __init__(self) -> None:
        self._dossiers: dict[tuple[str, str], DossierRecord] = {}

    def put(self, rec: DossierRecord) -> None:
        self._dossiers[(rec.tenant_id, rec.dossier_id)] = rec

    def get(self, tenant_id: str, dossier_id: str) -> DossierRecord | None:
        return self._dossiers.get((tenant_id, dossier_id))

    def get_for_scope(
        self, tenant_id: str, dossier_id: str, snapshot_digest: str
    ) -> DossierRecord | None:
        """Return a record only when its immutable snapshot pin matches scope."""

        record = self.get(tenant_id, dossier_id)
        if record is None:
            return None
        record_digest = record.pins.snapshot_digest or record.pins.source_snapshot_digest
        return record if _same_digest(record_digest, snapshot_digest) else None


def _same_digest(left: str | None, right: str | None) -> bool:
    def normalized(value: str | None) -> str:
        text = str(value or "").strip().lower()
        return text[7:] if text.startswith("sha256:") else text

    return bool(normalized(left)) and normalized(left) == normalized(right)
