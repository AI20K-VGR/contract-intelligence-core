"""Hermetic adapters that execute the production AI2 query and processing entries."""

from __future__ import annotations

import json
import sys
from collections.abc import Mapping
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE_ROOT = REPOSITORY_ROOT / "ai-service"
QUERY_ENTRY = "app.reasoning.stack.FourLayerReasoner.run"
PROCESSING_ENTRY = "app.pipeline.idp.run_idp"


def _ensure_production_imports() -> None:
    root = str(AI_SERVICE_ROOT)
    if root not in sys.path:
        sys.path.insert(0, root)


def _read_snapshot(source: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    if isinstance(source, Mapping):
        snapshot = dict(source)
    else:
        path = Path(source)
        try:
            snapshot = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise ValueError(f"cannot read AI1 snapshot {path}: {exc}") from exc
    if not isinstance(snapshot, dict) or snapshot.get("schema_version") != "ai1.snapshot.v1":
        raise ValueError("snapshot must be an ai1.snapshot.v1 object")
    return snapshot


def adapt_snapshot(source: str | Path | Mapping[str, Any]):
    """Validate and adapt one official snapshot through the production boundary."""
    _ensure_production_imports()
    from app.pipeline.ai1_snapshot_adapter import adapt_snapshot_v1

    return adapt_snapshot_v1(_read_snapshot(source), tenant_id="eval_tenant", actor_id="eval_actor")


def load_catalog_case(golden_dir: str | Path, contract_id: str) -> dict[str, Any]:
    root = Path(golden_dir)
    try:
        manifest = json.loads((root / "manifest.json").read_text(encoding="utf-8"))
        questions = json.loads((root / "questions.json").read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read golden catalog at {root}: {exc}") from exc
    entry = next((item for item in manifest.get("files", []) if item.get("contract_id") == contract_id), None)
    if not isinstance(entry, Mapping):
        raise KeyError(f"unknown golden contract: {contract_id}")
    snapshot = _read_snapshot(root / str(entry["path"]))
    case_questions = [item for item in questions if item.get("contract_id") == contract_id]
    if not case_questions:
        raise ValueError(f"golden contract {contract_id} has no questions")
    return {"contract_id": contract_id, "split": entry.get("split"), "snapshot": snapshot, "questions": case_questions}


def run_query(snapshot: str | Path | Mapping[str, Any], query: str) -> dict[str, Any]:
    if not isinstance(query, str) or not query.strip():
        raise ValueError("query must be non-empty text")
    try:
        _ensure_production_imports()
        from app.reasoning.query import classify_ask
        from app.reasoning.stack import FourLayerReasoner
        from app.reasoning.vector_recall import VectorRecallService
        from app.tools.gateway import ToolGateway
        from app.tools.store import InMemorySnapshotStore

        adapted = adapt_snapshot(snapshot)
        adapted.record.egress_approved = False
        store = InMemorySnapshotStore()
        store.put(adapted.record)
        reasoner = FourLayerReasoner(
            ToolGateway(store), llm=None, vector_recall=VectorRecallService(enabled=False)
        )
        output = reasoner.run(adapted.envelope, classify_ask(query))
        if not isinstance(output, Mapping):
            return {"status": "FAIL", "reason": "production query entry returned a non-object", "parity_executed": True}
        return {
            "status": "PASS",
            "parity_executed": True,
            "production_entry": QUERY_ENTRY,
            "snapshot_id": adapted.meta.get("snapshot_id") or adapted.record.pins.source_snapshot_digest,
            "output": _jsonable(output),
        }
    except Exception as exc:  # noqa: BLE001 - replay failure is evidence, not a skip
        return {"status": "BLOCKED", "reason": f"production query replay failed: {type(exc).__name__}: {exc}", "parity_executed": True}


def run_processing(snapshot: str | Path | Mapping[str, Any]) -> dict[str, Any]:
    try:
        _ensure_production_imports()
        from app.pipeline.idp import run_idp
        from app.pipeline.runtime import ProcessingRuntime
        from app.tools.store import InMemorySnapshotStore

        adapted = adapt_snapshot(snapshot)
        adapted.record.egress_approved = False
        store = InMemorySnapshotStore()
        store.put(adapted.record)
        result = run_idp(
            adapted.record,
            adapted.envelope,
            llm=None,
            store=store,
            runtime=ProcessingRuntime(egress_allowed=False, use_vector=False, max_llm_calls=0, max_embedding_tokens=0),
        )
        return {
            "status": "PASS",
            "parity_executed": True,
            "production_entry": PROCESSING_ENTRY,
            "snapshot_id": adapted.meta.get("snapshot_id") or adapted.record.pins.source_snapshot_digest,
            "output": _jsonable(result),
        }
    except Exception as exc:  # noqa: BLE001 - replay failure is evidence, not a skip
        return {"status": "BLOCKED", "reason": f"production processing replay failed: {type(exc).__name__}: {exc}", "parity_executed": True}


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (tuple, list)):
        return [_jsonable(item) for item in value]
    if hasattr(value, "__dataclass_fields__"):
        import dataclasses

        return _jsonable(dataclasses.asdict(value))
    return value
