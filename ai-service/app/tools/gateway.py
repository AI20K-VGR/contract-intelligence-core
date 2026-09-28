from __future__ import annotations

from typing import Any

from app.contracts.models import LifecycleState, ReviewState, ToolEnvelope
from app.pipeline.outline import citation_for_node
from app.tools.store import InMemorySnapshotStore


class ToolBlocked(Exception):
    def __init__(self, state: ReviewState = ReviewState.BLOCKED) -> None:
        super().__init__(state.value)
        self.state = state


class ToolGateway:
    ALLOWLIST = {
        "list_structure",
        "get_node",
        "list_tables",
        "get_table_meta",
        "get_table_rows",
        "search_structured",
        "search_semantic",
    }

    def __init__(self, store: InMemorySnapshotStore) -> None:
        self.store = store

    def call(self, name: str, envelope: ToolEnvelope, **kwargs: Any) -> Any:
        if name not in self.ALLOWLIST:
            raise ToolBlocked()
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if rec is None:
            raise ToolBlocked()
        if rec.lifecycle in {LifecycleState.SOFT_DELETED, LifecycleState.PURGED, LifecycleState.PURGE_PENDING}:
            raise ToolBlocked()
        if "READ_CONTENT" not in envelope.auth.permissions:
            raise ToolBlocked()
        actor_perms = rec.permissions_by_actor.get(envelope.auth.actor_id, [])
        if "READ_CONTENT" not in actor_perms:
            raise ToolBlocked()
        if envelope.auth.acl_revision != rec.acl_revision:
            raise ToolBlocked()
        if envelope.auth.dossier_id != rec.dossier_id:
            raise ToolBlocked()
        pin_ok = (
            envelope.pins.manifest_version == rec.pins.manifest_version
            and envelope.pins.source_snapshot_digest == rec.pins.source_snapshot_digest
            and envelope.pins.tenant_profile_version == rec.pins.tenant_profile_version
            and envelope.pins.policy_version == rec.pins.policy_version
            and envelope.pins.ocr_run_version == rec.pins.ocr_run_version
            and envelope.pins.reconstruction_version == rec.pins.reconstruction_version
            and envelope.pins.extraction_version == rec.pins.extraction_version
        )
        if not pin_ok:
            raise ToolBlocked()
        return getattr(self, name)(envelope, **kwargs)

    def list_structure(self, envelope: ToolEnvelope, dossier_id: str | None = None) -> list[dict[str, Any]]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        return [
            {
                "node_id": n.node_id,
                "type": n.type,
                "raw_label": n.raw_label,
                "parent": n.parent_id,
                "order": n.order,
                "has_children": n.has_children,
                "source_file_id": getattr(n, "source_file_id", None),
                "page_range": list(n.page_range),
                "page_revision_id": n.page_revision_id or "",
                "bbox": list(n.bbox),
                "structured_key": n.structured_key,
                "structured_value": n.structured_value,
                "text": (n.text or "")[:240],
                "structure_level": n.structure_level,
                "scope_id": n.scope_id,
                "breadcrumb": _breadcrumb(rec.evidence_nodes(), n),
            }
            for n in rec.evidence_nodes()
            if self._member_allowed(envelope, n.source_file_id, n.scope_id, n.node_id)
        ]

    def get_node(self, envelope: ToolEnvelope, node_id: str) -> dict[str, Any]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        nodes = rec.evidence_nodes()
        node = next((n for n in nodes if n.node_id == node_id), None)
        if node is None or not self._member_allowed(envelope, node.source_file_id, node.scope_id, node.node_id):
            raise ToolBlocked()
        ancestors = []
        cur = node.parent_id
        while cur:
            parent = next((n for n in nodes if n.node_id == cur), None)
            if parent is None:
                break
            ancestors.append(parent.raw_label)
            cur = parent.parent_id
        citation = citation_for_node(rec.evidence_nodes(), rec.pages, node.node_id) or {
            "node_id": node.node_id,
            "page_revision_id": node.page_revision_id or "",
            "bbox": node.bbox,
            "text_span": node.text[:200],
        }
        return {
            "node_id": node.node_id,
            "text": node.text,
            "page_range": node.page_range,
            "ancestors": list(reversed(ancestors)),
            "citation": citation,
            "structured_key": node.structured_key,
            "structured_value": node.structured_value,
            "type": node.type,
            "raw_label": node.raw_label,
            "source_file_id": getattr(node, "source_file_id", None),
        }

    def list_tables(self, envelope: ToolEnvelope, dossier_id: str | None = None) -> list[dict[str, Any]]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        return [
            {"table_id": t.table_id, "title": t.title, "n_rows": len(t.rows), "n_cols": len(t.header)}
            for t in rec.tables
            if self._table_allowed(envelope, t)
        ]

    def get_table_meta(self, envelope: ToolEnvelope, table_id: str) -> dict[str, Any]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        table = next((t for t in rec.tables if t.table_id == table_id), None)
        if table is None or not self._table_allowed(envelope, table):
            raise ToolBlocked()
        first = table.rows[:2]
        last = table.rows[-2:] if len(table.rows) > 2 else table.rows
        return {
            "header": table.header,
            "n_rows": len(table.rows),
            "n_cols": len(table.header),
            "first_rows": first,
            "last_rows": last,
            "continuation": table.continuation,
            "header_row_indices": table.header_row_indices,
            "source_role": table.source_role,
            "section_scope": table.section_scope,
        }

    def get_table_rows(self, envelope: ToolEnvelope, table_id: str, start: int, end: int) -> list[dict[str, Any]]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        table = next((t for t in rec.tables if t.table_id == table_id), None)
        if table is None or not self._table_allowed(envelope, table):
            raise ToolBlocked()
        sliced = table.rows[start:end]
        out = []
        for i, row in enumerate(sliced):
            idx = start + i
            citations = []
            for c, _ in enumerate(row):
                key = f"{idx}:{c}"
                if key in table.cell_citations:
                    citations.append(table.cell_citations[key].model_dump())
            out.append({"row_index": idx, "cells": row, "citations": citations,
                        "cell_citations": {str(c): table.cell_citations[f"{idx}:{c}"].model_dump()
                                           for c in range(len(row)) if f"{idx}:{c}" in table.cell_citations}})
        return out

    def search_structured(self, envelope: ToolEnvelope, key: str, filters: dict[str, Any] | None = None) -> list[dict[str, Any]]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        hits = []
        needle = key.lower()
        for n in rec.evidence_nodes():
            if n.structured_key and n.structured_key.lower() == needle and self._member_allowed(envelope, n.source_file_id, n.scope_id, n.node_id):
                hits.append(
                    {
                        "node_id": n.node_id,
                        "value": n.structured_value,
                        "structured_key": n.structured_key,
                        "citation": citation_for_node(
                            rec.evidence_nodes(),
                            rec.pages,
                            n.node_id,
                            text_span=n.text[:240] or n.structured_value or "",
                        )
                        or {
                            "node_id": n.node_id,
                            "page_revision_id": n.page_revision_id or "",
                            "bbox": n.bbox,
                            "text_span": n.text[:240] or n.structured_value or "",
                        },
                    }
                )
        return hits

    def search_semantic(self, envelope: ToolEnvelope, query: str, k: int = 5) -> list[dict[str, Any]]:
        from app.reasoning.l1_retrieval import bm25_lite_score

        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        assert rec is not None
        k = min(max(int(k), 1), 8)
        items: list[dict[str, Any]] = []
        docs: list[str] = []
        corpus = rec.chunks or []
        if not corpus:
            for n in rec.evidence_nodes():
                if not self._member_allowed(envelope, n.source_file_id, n.scope_id, n.node_id):
                    continue
                text = n.text or n.raw_label or ""
                docs.append(text)
                items.append(
                    {
                        "chunk_id": n.node_id,
                        "node_id": n.node_id,
                        "citation": citation_for_node(
                            rec.evidence_nodes(), rec.pages, n.node_id, text_span=text[:200]
                        )
                        or {
                            "node_id": n.node_id,
                            "page_revision_id": n.page_revision_id or "",
                            "bbox": n.bbox,
                            "text_span": text[:200],
                        },
                    }
                )
        else:
            for ch in corpus:
                docs.append(ch.text_span)
                parent = next((n for n in rec.evidence_nodes() if n.node_id == ch.parent_node_id), None)
                items.append(
                    {
                        "chunk_id": ch.chunk_id,
                        "node_id": ch.parent_node_id,
                        "citation": citation_for_node(
                            rec.evidence_nodes(), rec.pages, ch.parent_node_id, text_span=ch.text_span[:200]
                        )
                        or {
                            "node_id": ch.parent_node_id,
                            "page_revision_id": (parent.page_revision_id if parent else "") or "",
                            "bbox": ch.bbox_fragments[0] if ch.bbox_fragments else [],
                            "text_span": ch.text_span[:200],
                        },
                    }
                )
        scores = bm25_lite_score(query, docs)
        ranked = sorted(zip(scores, items), key=lambda x: x[0], reverse=True)
        out = []
        for score, item in ranked:
            if score <= 0:
                continue
            item = dict(item)
            item["score"] = float(score)
            out.append(item)
            if len(out) >= k:
                break
        return out
    def run_code(self, envelope: ToolEnvelope, code: str, table_id: str) -> dict[str, Any]:
        raise ToolBlocked()

    @staticmethod
    def _member_allowed(envelope: ToolEnvelope, *values: str | None) -> bool:
        allowed = {str(value) for value in envelope.auth.member_ids if value}
        allowed.update(
            envelope.auth.member_documents.get(member_id, "")
            for member_id in tuple(allowed)
            if envelope.auth.member_documents.get(member_id)
        )
        return not allowed or bool(allowed.intersection(str(value) for value in values if value))

    def _table_allowed(self, envelope: ToolEnvelope, table: Any) -> bool:
        return self._member_allowed(envelope, table.node_id, table.source_role, table.section_scope)


def _breadcrumb(nodes, node) -> list[str]:
    by_id = {item.node_id: item for item in nodes}
    labels = []
    current = node
    seen = set()
    while current is not None and current.node_id not in seen:
        seen.add(current.node_id)
        labels.append(current.raw_label)
        current = by_id.get(current.parent_id) if current.parent_id else None
    return list(reversed(labels))
