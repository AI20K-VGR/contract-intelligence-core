"""Optional vector recall with snapshot and citation safety gates."""

from __future__ import annotations

import hashlib
import json
import math
import os
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Protocol

from app.contracts.models import Citation
from app.llm.embeddings import OpenAICompatibleEmbeddingClient
from app.pipeline.runtime import ProcessingRuntime
from app.tools.store import DossierRecord


MAX_SEGMENT_CHARS = 1600
SEGMENT_OVERLAP = 200


@dataclass(frozen=True)
class EvidenceSegment:
    segment_id: str
    snapshot_digest: str
    node_id: str
    source_file_id: str | None
    source_role: str | None
    page_revision_id: str
    char_start: int
    char_end: int
    text: str
    text_digest: str
    embedding_version: str = "segment-v1"


@dataclass(frozen=True)
class VectorCandidate:
    segment: EvidenceSegment
    score: float
    citation: Citation
    retrieval_method: str = "VECTOR_RECALL"


@dataclass
class VectorRecallResult:
    status: str
    candidates: list[VectorCandidate] = field(default_factory=list)
    trace: dict[str, Any] = field(default_factory=dict)
    issues: list[dict[str, Any]] = field(default_factory=list)


class VectorIndex(Protocol):
    def upsert(self, segments: list[EvidenceSegment], vectors: list[list[float]], *, model: str, dimensions: int) -> None: ...

    def search(self, snapshot_digest: str, vector: list[float], *, k: int, filters: dict[str, Any] | None = None) -> list[tuple[EvidenceSegment, float]]: ...

    def has_snapshot(self, snapshot_digest: str, *, model: str, dimensions: int) -> bool: ...


class SQLiteVectorIndex:
    def __init__(self, path: str | Path | None = None) -> None:
        default_path = Path(__file__).resolve().parents[2] / "data" / "ai2" / "vectors.sqlite"
        self.path = Path(path or os.getenv("AI2_VECTOR_DB") or default_path)

    def _connect(self) -> sqlite3.Connection:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        cx = sqlite3.connect(self.path)
        cx.execute(
            """CREATE TABLE IF NOT EXISTS vector_segments (
                segment_id TEXT PRIMARY KEY,
                snapshot_digest TEXT NOT NULL,
                node_id TEXT NOT NULL,
                source_file_id TEXT,
                source_role TEXT,
                page_revision_id TEXT NOT NULL,
                char_start INTEGER NOT NULL,
                char_end INTEGER NOT NULL,
                text_digest TEXT NOT NULL,
                text TEXT NOT NULL,
                embedding_version TEXT NOT NULL,
                embedding_model TEXT NOT NULL,
                dimensions INTEGER NOT NULL,
                vector_json TEXT NOT NULL
            )"""
        )
        cx.execute("CREATE INDEX IF NOT EXISTS idx_vector_snapshot ON vector_segments(snapshot_digest)")
        cx.commit()
        return cx

    def upsert(self, segments: list[EvidenceSegment], vectors: list[list[float]], *, model: str, dimensions: int) -> None:
        if len(segments) != len(vectors):
            raise ValueError("segments and vectors must have equal length")
        cx = self._connect()
        for segment, vector in zip(segments, vectors):
            if len(vector) != dimensions:
                raise ValueError("vector dimension mismatch")
            cx.execute(
                """INSERT OR REPLACE INTO vector_segments
                (segment_id, snapshot_digest, node_id, source_file_id, source_role,
                 page_revision_id, char_start, char_end, text_digest, text,
                 embedding_version, embedding_model, dimensions, vector_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)""",
                (
                    segment.segment_id,
                    segment.snapshot_digest,
                    segment.node_id,
                    segment.source_file_id,
                    segment.source_role,
                    segment.page_revision_id,
                    segment.char_start,
                    segment.char_end,
                    segment.text_digest,
                    segment.text,
                    segment.embedding_version,
                    model,
                    dimensions,
                    json.dumps(vector),
                ),
            )
        cx.commit()
        cx.close()

    def has_snapshot(self, snapshot_digest: str, *, model: str, dimensions: int) -> bool:
        cx = self._connect()
        row = cx.execute(
            "SELECT 1 FROM vector_segments WHERE snapshot_digest=? AND embedding_model=? AND dimensions=? LIMIT 1",
            (snapshot_digest, model, dimensions),
        ).fetchone()
        cx.close()
        return row is not None

    def search(self, snapshot_digest: str, vector: list[float], *, k: int, filters: dict[str, Any] | None = None) -> list[tuple[EvidenceSegment, float]]:
        filters = filters or {}
        cx = self._connect()
        query = (
            "SELECT segment_id,snapshot_digest,node_id,source_file_id,source_role,page_revision_id,"
            "char_start,char_end,text_digest,text,embedding_version,vector_json "
            "FROM vector_segments WHERE snapshot_digest=?"
        )
        args: list[Any] = [snapshot_digest]
        if filters.get("embedding_model"):
            query += " AND embedding_model=?"
            args.append(filters["embedding_model"])
        if filters.get("dimensions"):
            query += " AND dimensions=?"
            args.append(filters["dimensions"])
        rows = cx.execute(query, args).fetchall()
        cx.close()
        scored: list[tuple[EvidenceSegment, float]] = []
        for row in rows:
            if filters.get("source_role") and row[4] != filters["source_role"]:
                continue
            if filters.get("source_file_id") and row[3] != filters["source_file_id"]:
                continue
            segment = EvidenceSegment(
                segment_id=row[0], snapshot_digest=row[1], node_id=row[2], source_file_id=row[3],
                source_role=row[4], page_revision_id=row[5], char_start=row[6], char_end=row[7],
                text=row[9], text_digest=row[8], embedding_version=row[10],
            )
            score = _cosine(vector, json.loads(row[11]))
            scored.append((segment, score))
        scored.sort(key=lambda item: item[1], reverse=True)
        return scored[: max(1, k)]


class VectorRecallService:
    def __init__(
        self,
        embedding_client: OpenAICompatibleEmbeddingClient | None = None,
        index: VectorIndex | None = None,
        *,
        enabled: bool | None = None,
        runtime: ProcessingRuntime | None = None,
    ) -> None:
        self.embedding_client = embedding_client or OpenAICompatibleEmbeddingClient()
        self.index = index or SQLiteVectorIndex()
        self.batch_size = max(1, int(os.getenv("AI2_EMBEDDING_BATCH_SIZE", "16")))
        self.enabled = enabled if enabled is not None else os.getenv("AI2_VECTOR_RECALL_ENABLED", "false").casefold() in {"1", "true", "yes", "on"}
        self.runtime = runtime

    def recall(self, record: DossierRecord, query: str, *, k: int = 12, filters: dict[str, Any] | None = None) -> VectorRecallResult:
        if not self.enabled:
            return VectorRecallResult("DISABLED", trace={"vector_status": "DISABLED"})
        if record.embedding_budget_hit():
            return VectorRecallResult("BUDGET_EXCEEDED", trace={"vector_status": "BUDGET_EXCEEDED"})
        if not record.egress_approved:
            return VectorRecallResult("EGRESS_DENIED", trace={"vector_status": "EGRESS_DENIED"})
        capability = self.embedding_client.discover(egress_approved=record.egress_approved)
        trace = {"vector_status": capability.status, "embedding_model": capability.selected_model, "embedding_dimensions": capability.dimensions}
        if capability.status != "READY" or not capability.selected_model or not capability.dimensions:
            return VectorRecallResult(capability.status, trace=trace)
        segments = build_segments(record)
        if not segments:
            return VectorRecallResult("UNAVAILABLE", trace={**trace, "reason": "no evidence segments"})
        has_snapshot = getattr(self.index, "has_snapshot", None)
        indexed = bool(has_snapshot and has_snapshot(record.pins.source_snapshot_digest, model=capability.selected_model, dimensions=capability.dimensions))
        if not indexed:
            try:
                vectors: list[list[float]] = []
                for offset in range(0, len(segments), self.batch_size):
                    batch = segments[offset : offset + self.batch_size]
                    if not self._account_embedding_budget([segment.text for segment in batch]):
                        return VectorRecallResult("BUDGET_EXCEEDED", trace={**trace, "vector_status": "BUDGET_EXCEEDED"})
                    vectors.extend(self.embedding_client.embed([segment.text for segment in batch], model=capability.selected_model, egress_approved=record.egress_approved))
                self.index.upsert(segments, vectors, model=capability.selected_model, dimensions=capability.dimensions)
            except Exception as exc:
                return VectorRecallResult("PROVIDER_ERROR", trace={**trace, "error": type(exc).__name__})
        try:
            if not self._account_embedding_budget([query]):
                return VectorRecallResult("BUDGET_EXCEEDED", trace={**trace, "vector_status": "BUDGET_EXCEEDED"})
            query_vector = self.embedding_client.embed([query], model=capability.selected_model, egress_approved=record.egress_approved)[0]
            search_filters = {
                **(filters or {}),
                "embedding_model": capability.selected_model,
                "dimensions": capability.dimensions,
            }
            raw = self.index.search(record.pins.source_snapshot_digest, query_vector, k=k * 4, filters=search_filters)
        except Exception as exc:
            return VectorRecallResult("PROVIDER_ERROR", trace={**trace, "error": type(exc).__name__})
        candidates: list[VectorCandidate] = []
        for segment, score in raw:
            node = next((item for item in record.evidence_nodes() if item.node_id == segment.node_id), None)
            if node is None or node.status == "FAILED" or segment.char_start < 0 or segment.char_end > len(node.text):
                continue
            if node.text[segment.char_start:segment.char_end] != segment.text:
                continue
            candidates.append(
                VectorCandidate(
                    segment=segment,
                    score=score,
                    citation=Citation(
                        node_id=node.node_id,
                        page_revision_id=node.page_revision_id or "",
                        bbox=list(node.bbox),
                        text_span=segment.text[:240],
                    ),
                )
            )
            if len(candidates) >= k:
                break
        return VectorRecallResult("READY", candidates=candidates, trace={**trace, "vector_hits": len(candidates)})

    def _account_embedding_budget(self, texts: list[str]) -> bool:
        if self.runtime is None:
            return True
        estimated_tokens = sum(max(1, (len(text) + 3) // 4) for text in texts)
        return self.runtime.account_embedding_tokens(estimated_tokens)


def build_segments(record: DossierRecord) -> list[EvidenceSegment]:
    roles = {item.file_id: item.role for item in record.source_files}
    digest = record.pins.source_snapshot_digest
    out: list[EvidenceSegment] = []
    for node in record.evidence_nodes():
        text = node.text or node.raw_label or ""
        if not text.strip():
            continue
        start = 0
        while start < len(text):
            end = min(len(text), start + MAX_SEGMENT_CHARS)
            if end < len(text):
                boundary = max(text.rfind("\n", start, end), text.rfind(". ", start, end))
                if boundary > start + MAX_SEGMENT_CHARS // 2:
                    end = boundary + (1 if text[boundary] == "\n" else 2)
            part = text[start:end]
            segment_id = "seg:" + hashlib.sha256(f"{digest}|{node.node_id}|{start}|{end}|{part}".encode("utf-8")).hexdigest()[:24]
            out.append(
                EvidenceSegment(
                    segment_id=segment_id,
                    snapshot_digest=digest,
                    node_id=node.node_id,
                    source_file_id=node.source_file_id,
                    source_role=roles.get(node.source_file_id or ""),
                    page_revision_id=node.page_revision_id or "",
                    char_start=start,
                    char_end=end,
                    text=part,
                    text_digest=hashlib.sha256(part.encode("utf-8")).hexdigest(),
                )
            )
            if end >= len(text):
                break
            start = max(end - SEGMENT_OVERLAP, start + 1)
    return out


def _cosine(left: list[float], right: list[float]) -> float:
    if len(left) != len(right) or not left:
        return -1.0
    dot = sum(a * b for a, b in zip(left, right))
    left_norm = math.sqrt(sum(a * a for a in left))
    right_norm = math.sqrt(sum(b * b for b in right))
    return dot / (left_norm * right_norm) if left_norm and right_norm else -1.0
