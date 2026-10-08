"""Rows of ``ai2.contract_edges`` (P4, D7): replace-per-dossier on a caller's transaction.

PostgreSQL only; the SQLite job store has no edge table. Every text column is stripped of
``\\x00`` because PostgreSQL rejects NUL in ``text`` (RT-04) — a bad span must not cost the job.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.engine import Connection

from app.contracts.contract_graph import ContractEdge
from app.db.tables import contract_edges


def _canonical(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def edge_digest(edge: ContractEdge) -> str:
    """sha256 of the edge's canonical JSON; same snapshot and retry ⇒ same digest."""

    return hashlib.sha256(_canonical(edge.model_dump(mode="json")).encode("utf-8")).hexdigest()


def _clean(value: str | None) -> str | None:
    return None if value is None else value.replace("\x00", "")


def _citation_json(citation) -> str:
    dumped = citation.model_dump(mode="json")
    # strip before serializing: json.dumps would turn NUL into a literal "\u0000"
    return _canonical({k: _clean(v) if isinstance(v, str) else v for k, v in dumped.items()})


def edge_row(
    edge: ContractEdge, *, tenant_id: str, dossier_id: str, job_id: str, now_ms: int
) -> dict[str, Any]:
    row: dict[str, Any] = {
        "tenant_id": tenant_id,
        "dossier_id": dossier_id,
        "edge_id": edge.edge_id,
        "job_id": job_id,
        "source_snapshot_digest": edge.source_snapshot_digest,
        "op": edge.op.value,
        "source_node_id": edge.source_node_id,
        "target_node_id": edge.target_node_id,
        "anchor_node_id": edge.anchor_node_id,
        "target_address": edge.target_address,
        "method": edge.method.value,
        "support": edge.support.value,
        "standard": int(edge.standard),
        "implicit": int(edge.implicit),
        "review_state": edge.review_state.value,
        "source_citation_json": _citation_json(edge.source_citation),
        "target_citation_json": _citation_json(edge.target_citation),
        "new_text": edge.new_text,
        "scope_text": edge.scope_text,
        "digest": edge_digest(edge),
        "created_ms": int(now_ms),
    }
    return {k: _clean(v) if isinstance(v, str) else v for k, v in row.items()}


def replace_contract_edges(
    cx: Connection,
    *,
    tenant_id: str,
    dossier_id: str,
    job_id: str,
    edges: Iterable[ContractEdge],
    now_ms: int,
) -> int:
    """Delete the dossier's rows and insert ``edges``; never commits (caller owns the transaction)."""

    rows = [
        edge_row(edge, tenant_id=tenant_id, dossier_id=dossier_id, job_id=job_id, now_ms=now_ms)
        for edge in edges
    ]
    cx.execute(delete(contract_edges).where(
        contract_edges.c.tenant_id == tenant_id, contract_edges.c.dossier_id == dossier_id,
    ))
    if rows:
        cx.execute(insert(contract_edges), rows)
    return len(rows)
