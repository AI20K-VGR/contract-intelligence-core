from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from app.contracts.models import (
    Chunk,
    Citation,
    ContractEvent,
    Fact,
    HandoffIssue,
    JobResult,
    LifecycleState,
    PageSnapshot,
    RelationGraph,
    ReviewItem,
    SourceFile,
    StructuralNode,
    TableSnapshot,
    TenantProfile,
    ToolEnvelope,
    VersionPins,
)
from app.tools.store import DossierRecord, InMemorySnapshotStore

ROOT = Path(__file__).resolve().parents[2]
DATA = ROOT.parent / "data" / "ai2"
DB = DATA / "runs.sqlite"


def _conn() -> sqlite3.Connection:
    DATA.mkdir(parents=True, exist_ok=True)
    (DATA / "blobs").mkdir(exist_ok=True)
    cx = sqlite3.connect(DB)
    cx.execute(
        """CREATE TABLE IF NOT EXISTS sessions (
        session_id TEXT PRIMARY KEY,
        payload TEXT NOT NULL,
        updated_ms INTEGER NOT NULL
        )"""
    )
    return cx


def record_to_dict(rec: DossierRecord) -> dict:
    return {
        "tenant_id": rec.tenant_id,
        "dossier_id": rec.dossier_id,
        "lifecycle": rec.lifecycle.value,
        "pins": rec.pins.model_dump(),
        "pages": [p.model_dump() for p in rec.pages],
        "nodes": [n.model_dump() for n in rec.nodes],
        "active_nodes": [n.model_dump() for n in rec.active_nodes] if rec.active_nodes is not None else None,
        "tables": [t.model_dump() for t in rec.tables],
        "profile": rec.profile.model_dump(),
        "acl_revision": rec.acl_revision,
        "permissions_by_actor": rec.permissions_by_actor,
        "source_files": [f.model_dump() for f in rec.source_files],
        "facts": [f.model_dump() for f in rec.facts],
        "input_facts": [f.model_dump() for f in rec.input_facts] if rec.input_facts is not None else None,
        "chunks": [c.model_dump() for c in rec.chunks],
        "active_index_version": rec.active_index_version,
        "processing_index": rec.processing_index,
        "legal_hold": rec.legal_hold,
        "egress_approved": rec.egress_approved,
        "budget_exceeded": rec.budget_exceeded,
        "processing_budget_exceeded": rec.processing_budget_exceeded,
        "embedding_budget_exceeded": rec.embedding_budget_exceeded,
        "index_status": rec.index_status,
        "case_id": rec.case_id,
        "handoff_issues": [issue.model_dump() for issue in rec.handoff_issues],
        "relation_graph": rec.relation_graph.model_dump() if rec.relation_graph else None,
        "citation_index": {key: value.model_dump() for key, value in rec.citation_index.items()},
        "review_items": [item.model_dump() for item in rec.review_items],
        "events": [event.model_dump() for event in rec.events],
    }


def record_from_dict(d: dict) -> DossierRecord:
    return DossierRecord(
        tenant_id=d["tenant_id"],
        dossier_id=d["dossier_id"],
        lifecycle=LifecycleState(d["lifecycle"]),
        pins=VersionPins.model_validate(d["pins"]),
        pages=[PageSnapshot.model_validate(p) for p in d["pages"]],
        nodes=[StructuralNode.model_validate(n) for n in d["nodes"]],
        active_nodes=(
            [StructuralNode.model_validate(n) for n in d["active_nodes"]]
            if d.get("active_nodes") is not None
            else None
        ),
        tables=[TableSnapshot.model_validate(t) for t in d["tables"]],
        profile=TenantProfile.model_validate(d["profile"]),
        acl_revision=d.get("acl_revision", 1),
        permissions_by_actor=d.get("permissions_by_actor") or {},
        source_files=[SourceFile.model_validate(f) for f in d.get("source_files") or []],
        facts=[Fact.model_validate(f) for f in d.get("facts") or []],
        input_facts=[Fact.model_validate(f) for f in d["input_facts"]] if d.get("input_facts") is not None else None,
        chunks=[Chunk.model_validate(c) for c in d.get("chunks") or []],
        active_index_version=d.get("active_index_version"),
        processing_index=d.get("processing_index", False),
        legal_hold=d.get("legal_hold", False),
        egress_approved=d.get("egress_approved", False),
        budget_exceeded=d.get("budget_exceeded", False),
        processing_budget_exceeded=d.get("processing_budget_exceeded", False),
        embedding_budget_exceeded=d.get("embedding_budget_exceeded", False),
        index_status=d.get("index_status", "READY"),
        case_id=d.get("case_id"),
        handoff_issues=[HandoffIssue.model_validate(issue) for issue in d.get("handoff_issues") or []],
        relation_graph=RelationGraph.model_validate(d["relation_graph"]) if d.get("relation_graph") else None,
        citation_index={
            key: Citation.model_validate(value)
            for key, value in (d.get("citation_index") or {}).items()
        },
        review_items=[ReviewItem.model_validate(item) for item in d.get("review_items") or []],
        events=[ContractEvent.model_validate(event) for event in d.get("events") or []],
    )


def save_session(sid: str, s: dict, store: InMemorySnapshotStore) -> None:
    rec: DossierRecord = s["record"]
    env: ToolEnvelope = s["envelope"]
    blobs: dict[str, bytes] = s.get("blobs") or {}
    blob_dir = DATA / "blobs" / sid
    blob_dir.mkdir(parents=True, exist_ok=True)
    blob_meta = {}
    for fid, data in blobs.items():
        path = blob_dir / fid
        path.write_bytes(data)
        blob_meta[fid] = str(path)
    payload = {
        "filename": s["filename"],
        "source": s["source"],
        "step": s["step"],
        "ai1": s.get("ai1") or {},
        "used_llm": s.get("used_llm", False),
        "gold": s.get("gold", False),
        "reviews": s.get("reviews") or {},
        "review_basis": s.get("review_basis") or {},
        "reviews_stale": s.get("reviews_stale", False),
        "published": s.get("published", False),
        "authoritative_publish_blocked": s.get("authoritative_publish_blocked", False),
        "record": record_to_dict(rec),
        "envelope": env.model_dump(),
        "job": s["job"].model_dump() if s.get("job") else None,
        "blobs": blob_meta,
    }
    cx = _conn()
    cx.execute(
        "INSERT OR REPLACE INTO sessions(session_id, payload, updated_ms) VALUES (?,?, strftime('%s','now')*1000)",
        (sid, json.dumps(payload, ensure_ascii=False)),
    )
    cx.commit()
    cx.close()
    store.put(rec)


def load_session(sid: str, store: InMemorySnapshotStore) -> dict | None:
    cx = _conn()
    row = cx.execute("SELECT payload FROM sessions WHERE session_id=?", (sid,)).fetchone()
    cx.close()
    if not row:
        return None
    payload = json.loads(row[0])
    rec = record_from_dict(payload["record"])
    env = ToolEnvelope.model_validate(payload["envelope"])
    store.put(rec)
    blobs = {}
    for fid, path in (payload.get("blobs") or {}).items():
        p = Path(path)
        if p.exists():
            blobs[fid] = p.read_bytes()
    job = JobResult.model_validate(payload["job"]) if payload.get("job") else None
    return {
        "record": rec,
        "envelope": env,
        "filename": payload["filename"],
        "source": payload["source"],
        "step": payload.get("step") or "reconstruct",
        "ai1": payload.get("ai1") or {},
        "job": job,
        "used_llm": payload.get("used_llm", False),
        "blobs": blobs,
        "gold": payload.get("gold", False),
        "reviews": payload.get("reviews") or {},
        "review_basis": payload.get("review_basis") or {},
        "reviews_stale": payload.get("reviews_stale", False),
        "published": payload.get("published", False),
        "authoritative_publish_blocked": payload.get("authoritative_publish_blocked", False),
    }
