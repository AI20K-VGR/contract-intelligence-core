from __future__ import annotations

import unicodedata
from typing import Any

from app.contracts.models import LifecycleState, ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.reasoning.stack import FourLayerReasoner
from app.reasoning.vector_recall import VectorRecallService
from app.tools.gateway import ToolBlocked, ToolGateway
from app.tools.store import InMemorySnapshotStore


def classify_ask(text: str) -> dict[str, Any]:
    from app.reasoning.ask_intent import parse_ask

    spec = parse_ask(text)
    if spec.get("type") == "unscoped" and _count_entity_ask(text or ""):
        spec["type"] = "count_entity"
        spec["attribute"] = "count"
    return spec


def _count_entity_ask(low: str) -> bool:
    from app.reasoning.l0_rules import _count_entity_query

    return _count_entity_query(low)


def _plain_query(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


class QueryRouter:
    def __init__(
        self,
        store: InMemorySnapshotStore,
        gateway: ToolGateway,
        llm: NineRouterClient | None = None,
        vector_recall: VectorRecallService | None = None,
    ) -> None:
        self.store = store
        self.gateway = gateway
        self.llm = llm
        self.stack = FourLayerReasoner(gateway, llm, vector_recall=vector_recall)

    def query(
        self,
        envelope: ToolEnvelope,
        text: str,
        task: dict[str, Any] | None = None,
        policy_flags: dict[str, Any] | None = None,
    ) -> dict[str, Any]:
        rec = self.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if rec is None:
            return {"review_state": ReviewState.BLOCKED.value, "hits": []}
        if rec.lifecycle != LifecycleState.ACTIVE:
            return {"review_state": ReviewState.BLOCKED.value, "hits": []}
        spec = dict(task or classify_ask(text))
        spec["policy_flags"] = dict(policy_flags or spec.get("policy_flags") or {})
        try:
            result = self.stack.run(envelope, spec)
            hits = result.get("citations") or result.get("hits") or []
            retrieval = result.get("retrieval_trace") or {}
            selected = (
                "VECTOR"
                if retrieval.get("vector_status") == "READY"
                else ("LEXICAL" if hits else "NONE")
            )
            result["retrieval_layer"] = {
                "selected": selected,
                "vector_status": retrieval.get("vector_status", "NOT_REQUESTED"),
            }
            result["reasoning_trace"] = result.get("steps") or [
                {"code": "QUERY_RETRIEVAL", "layer": selected}
            ]
            result["used_llm"] = bool(result.get("used_llm", False))
            return result
        except ToolBlocked:
            return {
                "review_state": ReviewState.BLOCKED.value,
                "hits": [],
                "retrieval_layer": {"selected": "POLICY"},
                "reasoning_trace": [{"code": "TOOL_BLOCKED"}],
                "used_llm": False,
            }
