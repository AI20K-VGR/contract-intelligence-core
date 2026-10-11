"""Safe, snapshot-bound projection of persisted contract-graph rows."""

from __future__ import annotations

import hashlib
import json
from typing import Any

GRAPH_KINDS = frozenset({"operation", "pair"})


def validate_graph_kind(value: str) -> str:
    if value not in GRAPH_KINDS:
        raise ValueError("unsupported graph kind")
    return value


def validate_graph_cursor(value: str | None, graph_kind: str) -> str | None:
    if value is None:
        return None
    prefix = "cedge:" if graph_kind == "operation" else "cpair:"
    if not value.startswith(prefix) or len(value) > 80:
        raise ValueError("invalid graph cursor")
    return value


def graph_read_status(*, stage_status: str, persistence_status: str | None, row_count: int) -> str:
    if persistence_status == "FAILED":
        return "PERSIST_FAILED"
    if stage_status == "SKIPPED":
        return "SKIPPED"
    if stage_status != "COMPLETED":
        return stage_status if stage_status in {"FAILED", "PENDING", "UNAVAILABLE"} else "PERSISTENCE_UNKNOWN"
    if persistence_status is None:
        return "PERSISTENCE_UNKNOWN"
    if persistence_status == "SKIPPED":
        return "SKIPPED"
    if persistence_status == "COMMITTED" and row_count >= 0:
        return "READY"
    return "PERSISTENCE_UNKNOWN"


def _citation_ref(raw: str) -> str:
    """Return an opaque stable handle; never project citation text or spans."""
    citation = json.loads(raw)
    if citation.get("citation_id"):
        return str(citation["citation_id"])
    safe_location = {
        key: citation.get(key)
        for key in ("node_id", "page_revision_id", "source_file_id", "page", "page_range", "line_ids", "bbox")
        if citation.get(key) is not None
    }
    return "cite:" + hashlib.sha256(
        json.dumps(safe_location, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode("utf-8")
    ).hexdigest()[:24]


def _citation_source_file_id(raw: str) -> str | None:
    """Project only the source document identity from a persisted citation."""
    value = json.loads(raw).get("source_file_id")
    return value if isinstance(value, str) and value else None


def project_operation_edge(row: Any) -> dict[str, Any]:
    return {
        "tenant_id": row["tenant_id"],
        "dossier_id": row["dossier_id"],
        "job_id": row["job_id"],
        "snapshot_digest": row["source_snapshot_digest"],
        "id": row["edge_id"],
        "kind": "OPERATION",
        "label": row["op"],
        "directed": True,
        "source_node_id": row["source_node_id"],
        "target_node_id": row["target_node_id"],
        "source_document_id": _citation_source_file_id(row["source_citation_json"]),
        "target_document_id": _citation_source_file_id(row["target_citation_json"]),
        "target_address": row["target_address"],
        "review_state": row["review_state"],
        "source_citation_ref": _citation_ref(row["source_citation_json"]),
        "target_citation_ref": _citation_ref(row["target_citation_json"]),
        "digest": row["digest"],
    }


def project_pair_relation(row: Any) -> dict[str, Any]:
    return {
        "tenant_id": row["tenant_id"],
        "dossier_id": row["dossier_id"],
        "job_id": row["job_id"],
        "snapshot_digest": row["source_snapshot_digest"],
        "id": row["relation_id"],
        "kind": "PAIR",
        "label": row["label"],
        "directed": bool(row["directed"]),
        "source_node_id": row["node_a_id"],
        "target_node_id": row["node_b_id"],
        "source_document_id": _citation_source_file_id(row["citation_a_json"]),
        "target_document_id": _citation_source_file_id(row["citation_b_json"]),
        "review_state": row["review_state"],
        "source_citation_ref": _citation_ref(row["citation_a_json"]),
        "target_citation_ref": _citation_ref(row["citation_b_json"]),
        "digest": row["digest"],
    }
