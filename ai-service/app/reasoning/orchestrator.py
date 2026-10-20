from __future__ import annotations

from typing import Any

from app.contracts.models import ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.tools.gateway import ToolBlocked, ToolGateway

MAX_STEPS = 8
MAX_REPLAN = 2


class ReasoningOrchestrator:
    """L2 plan-then-act over allowlisted tools, then caller must L3-ground."""

    def __init__(self, gateway: ToolGateway, llm: NineRouterClient) -> None:
        self.gateway = gateway
        self.llm = llm

    def run(self, envelope: ToolEnvelope, query: str, evidence: list[dict[str, Any]] | None = None) -> dict[str, Any]:
        if not self.llm.configured():
            return {"review_state": ReviewState.INSUFFICIENT_EVIDENCE.value, "answer": None, "steps": []}
        steps: list[dict[str, Any]] = []
        replans = 0
        plan = self._plan(query, evidence or [], None)
        for i in range(MAX_STEPS):
            if i >= len(plan):
                break
            action = plan[i]
            name = action.get("tool")
            args = action.get("args") or {}
            if name not in ToolGateway.ALLOWLIST:
                steps.append({"error": "tool not allowlisted", "tool": name})
                continue
            try:
                result = self.gateway.call(name, envelope, **args)
                steps.append({"tool": name, "ok": True, "result": result})
            except ToolBlocked:
                return {"review_state": ReviewState.BLOCKED.value, "answer": None, "steps": steps}
            except TypeError as exc:
                steps.append({"tool": name, "ok": False, "error": str(exc)})
                if replans < MAX_REPLAN:
                    plan = self._plan(query, evidence or [], steps)
                    replans += 1
        answer = self.llm.complete_json(
            "Answer only from tool results. JSON {answer, citations:[], sufficient:bool}. No legal conclusion.",
            f"query={query}\nsteps={steps[-6:]}",
        )
        state = ReviewState.ANSWERED if answer.get("sufficient") else ReviewState.INSUFFICIENT_EVIDENCE
        return {"review_state": state.value, "answer": answer, "steps": steps}

    def _plan(self, query: str, evidence: list[dict[str, Any]], prior: list | None) -> list[dict[str, Any]]:
        data = self.llm.complete_json(
            "Plan tool calls. JSON {plan:[{tool, args}]}. Tools: list_structure, get_node, list_tables, "
            "get_table_meta, get_table_rows, search_structured, search_semantic. Max 8 steps. Address-passing: IDs first.",
            f"query={query}\nevidence_ids={[e.get('node_id') for e in evidence]}\nprior={prior}",
        )
        plan = data.get("plan")
        if isinstance(plan, list):
            return plan[:MAX_STEPS]
        return [{"tool": "search_structured", "args": {"key": query}}, {"tool": "search_semantic", "args": {"query": query, "k": 5}}]
