"""Independent batch runner for the two-document AI1 OCR-lab handoff."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any, Sequence

from app.contracts.models import JobResult, ReviewState
from app.llm.client import NineRouterClient
from app.pipeline.ai1_snapshot_adapter import SnapshotContractError, adapt_ai1_input
from app.pipeline.idp import run_idp
from app.pipeline.index import IndexStore
from app.tools.store import InMemorySnapshotStore


@dataclass
class Ai2DocumentResult:
    path: str
    document_id: str | None
    snapshot_id: str | None
    meta: dict[str, Any] = field(default_factory=dict)
    job: JobResult | None = None
    error: dict[str, Any] | None = None

    def model_dump(self) -> dict[str, Any]:
        return {
            "path": self.path,
            "document_id": self.document_id,
            "snapshot_id": self.snapshot_id,
            "meta": self.meta,
            "job": self.job.model_dump(mode="json") if self.job else None,
            "error": self.error,
        }


@dataclass
class Ai2BatchResult:
    dossier_id: str | None
    relation_policy: str
    use_llm: bool
    documents: list[Ai2DocumentResult] = field(default_factory=list)
    batch_issues: list[dict[str, Any]] = field(default_factory=list)

    def model_dump(self) -> dict[str, Any]:
        states = [item.job.review_state for item in self.documents if item.job]
        if any(state == ReviewState.BLOCKED for state in states):
            overall = ReviewState.BLOCKED.value
        elif any(state in {ReviewState.NEEDS_REVIEW, ReviewState.INSUFFICIENT_EVIDENCE} for state in states) or self.batch_issues:
            overall = ReviewState.NEEDS_REVIEW.value
        elif states and all(state == ReviewState.PASS for state in states):
            overall = ReviewState.PASS.value
        else:
            overall = ReviewState.NEEDS_REVIEW.value
        return {
            "dossier_id": self.dossier_id,
            "relation_policy": self.relation_policy,
            "use_llm": self.use_llm,
            "overall_review_state": overall,
            "cross_document_findings": [],
            "batch_issues": self.batch_issues,
            "documents": [item.model_dump() for item in self.documents],
        }


def run_ai2_from_ai1_files(
    paths: Sequence[str | Path],
    *,
    relation_policy: str = "INDEPENDENT",
    use_llm: bool = False,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
) -> Ai2BatchResult:
    """Load and process each AI1 JSON independently.

    A bad document is represented in the batch result and does not prevent a
    valid sibling document from completing.  Every successful document gets a
    unique effective dossier scope so the in-memory tool store cannot overwrite
    another document with the same upstream dossier_id.
    """

    if relation_policy != "INDEPENDENT":
        raise ValueError("only relation_policy=INDEPENDENT is enabled for OCR-lab replay")
    llm = NineRouterClient() if use_llm else None
    if use_llm and (llm is None or not llm.configured()):
        raise RuntimeError("LLM_UNAVAILABLE: configure AI2_LLM_API_KEY/OPENAI_API_KEY and AI2_LLM_BASE_URL")

    result = Ai2BatchResult(dossier_id=None, relation_policy=relation_policy, use_llm=use_llm)
    for raw_path in paths:
        path = Path(raw_path)
        document_id: str | None = None
        snapshot_id: str | None = None
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
            if not isinstance(payload, dict):
                raise SnapshotContractError("top-level JSON must be an object", code="OCR_LAB_INPUT_INVALID")
            document_id = str(payload.get("document_id")) if payload.get("document_id") is not None else None
            snapshot_id = str(payload.get("snapshot_id")) if payload.get("snapshot_id") is not None else None
            if result.dossier_id is None:
                result.dossier_id = str(payload.get("dossier_id")) if payload.get("dossier_id") is not None else None
            elif payload.get("dossier_id") != result.dossier_id:
                result.batch_issues.append({
                    "code": "DOSSIER_ID_MISMATCH",
                    "message": f"{path.name} has dossier_id={payload.get('dossier_id')}, expected {result.dossier_id}",
                    "path": str(path),
                })
            scope_id = f"{payload.get('dossier_id')}:{payload.get('document_id')}"
            adapted = adapt_ai1_input(
                payload,
                tenant_id=tenant_id,
                actor_id=actor_id,
                scope_id=scope_id,
            )
            job = run_idp(
                adapted.record,
                adapted.envelope,
                llm=llm,
                store=InMemorySnapshotStore(),
                index=IndexStore(),
            )
            result.documents.append(Ai2DocumentResult(
                path=str(path),
                document_id=document_id,
                snapshot_id=snapshot_id,
                meta=adapted.meta,
                job=job,
            ))
        except Exception as exc:
            result.documents.append(Ai2DocumentResult(
                path=str(path),
                document_id=document_id,
                snapshot_id=snapshot_id,
                error={
                    "code": getattr(exc, "code", "AI2_BATCH_INPUT_FAILED"),
                    "message": f"{type(exc).__name__}: {exc}",
                    "retryable": False,
                },
            ))
    return result


def run_ai2_from_ai1_payloads(
    payloads: Sequence[dict[str, Any]],
    *,
    relation_policy: str = "INDEPENDENT",
    use_llm: bool = False,
    tenant_id: str = "tenant_a",
    actor_id: str = "user_001",
) -> Ai2BatchResult:
    """Run the same full pipeline for already-loaded AI1 JSON objects."""

    if relation_policy != "INDEPENDENT":
        raise ValueError("only relation_policy=INDEPENDENT is enabled for OCR-lab replay")
    llm = NineRouterClient() if use_llm else None
    if use_llm and (llm is None or not llm.configured()):
        raise RuntimeError("LLM_UNAVAILABLE: configure AI2_LLM_API_KEY/OPENAI_API_KEY and AI2_LLM_BASE_URL")

    result = Ai2BatchResult(dossier_id=None, relation_policy=relation_policy, use_llm=use_llm)
    for index, payload in enumerate(payloads):
        document_id: str | None = None
        snapshot_id: str | None = None
        source_label = f"payload[{index}]"
        try:
            if not isinstance(payload, dict):
                raise SnapshotContractError("top-level JSON must be an object", code="OCR_LAB_INPUT_INVALID")
            document_id = str(payload.get("document_id")) if payload.get("document_id") is not None else None
            snapshot_id = str(payload.get("snapshot_id")) if payload.get("snapshot_id") is not None else None
            if result.dossier_id is None:
                result.dossier_id = str(payload.get("dossier_id")) if payload.get("dossier_id") is not None else None
            elif payload.get("dossier_id") != result.dossier_id:
                result.batch_issues.append({
                    "code": "DOSSIER_ID_MISMATCH",
                    "message": f"{source_label} has dossier_id={payload.get('dossier_id')}, expected {result.dossier_id}",
                    "path": source_label,
                })
            scope_id = f"{payload.get('dossier_id')}:{payload.get('document_id')}"
            adapted = adapt_ai1_input(payload, tenant_id=tenant_id, actor_id=actor_id, scope_id=scope_id)
            job = run_idp(
                adapted.record,
                adapted.envelope,
                llm=llm,
                store=InMemorySnapshotStore(),
                index=IndexStore(),
            )
            result.documents.append(Ai2DocumentResult(
                path=source_label,
                document_id=document_id,
                snapshot_id=snapshot_id,
                meta=adapted.meta,
                job=job,
            ))
        except Exception as exc:
            result.documents.append(Ai2DocumentResult(
                path=source_label,
                document_id=document_id,
                snapshot_id=snapshot_id,
                error={
                    "code": getattr(exc, "code", "AI2_BATCH_INPUT_FAILED"),
                    "message": f"{type(exc).__name__}: {exc}",
                    "retryable": False,
                },
            ))
    return result
