"""Replace pair proposals inside the caller's completion transaction."""
from __future__ import annotations

import hashlib
from collections.abc import Iterable
from typing import Any

from sqlalchemy import delete, insert
from sqlalchemy.engine import Connection

from app.contracts.contract_graph import PairRelation
from app.db.tables import contract_pair_relations
from app.tools.contract_edge_store import _canonical, _citation_json, _clean


def relation_digest(relation: PairRelation) -> str:
    return hashlib.sha256(_canonical(relation.model_dump(mode="json")).encode("utf8")).hexdigest()


def relation_row(
    relation: PairRelation, *, tenant_id: str, dossier_id: str, job_id: str, now_ms: int,
) -> dict[str, Any]:
    row = {
        "tenant_id": tenant_id, "dossier_id": dossier_id, "relation_id": relation.relation_id,
        "job_id": job_id, "source_snapshot_digest": relation.source_snapshot_digest,
        "label": relation.label.value, "directed": int(relation.directed),
        "node_a_id": relation.node_a_id, "node_b_id": relation.node_b_id,
        "candidate_sources_json": _canonical([_clean(s) for s in relation.candidate_sources]),
        "span_a": relation.span_a, "span_b": relation.span_b,
        "citation_a_json": _citation_json(relation.citation_a),
        "citation_b_json": _citation_json(relation.citation_b),
        "classifier_model": relation.classifier_model, "prompt_version": relation.prompt_version,
        "review_state": relation.review_state.value, "digest": relation_digest(relation),
        "created_ms": int(now_ms),
    }
    return {k: _clean(v) if isinstance(v, str) else v for k, v in row.items()}


def replace_pair_relations(
    cx: Connection, *, tenant_id: str, dossier_id: str, job_id: str,
    relations: Iterable[PairRelation], now_ms: int,
) -> int:
    rows = [relation_row(r, tenant_id=tenant_id, dossier_id=dossier_id, job_id=job_id, now_ms=now_ms)
            for r in relations]
    cx.execute(delete(contract_pair_relations).where(
        contract_pair_relations.c.tenant_id == tenant_id,
        contract_pair_relations.c.dossier_id == dossier_id,
    ))
    if rows:
        cx.execute(insert(contract_pair_relations), rows)
    return len(rows)
