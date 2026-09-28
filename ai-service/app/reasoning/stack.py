from __future__ import annotations

import unicodedata
from typing import Any

from app.contracts.models import ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.reasoning.l0_rules import L0Rules, query_too_broad
from app.reasoning.l1_retrieval import COMPARE_TYPES, L1Retrieval
from app.reasoning.l2_plan import L2Planner
from app.reasoning.l3_ground import L3Ground
from app.reasoning.relations import doc_side, render_related_answer
from app.reasoning.vector_recall import VectorRecallService
from app.tools.gateway import ToolGateway


class FourLayerReasoner:
    def __init__(
        self,
        gateway: ToolGateway,
        llm: NineRouterClient | None = None,
        vector_recall: VectorRecallService | None = None,
    ) -> None:
        self.l0 = L0Rules(gateway)
        self.l1 = L1Retrieval(gateway, vector_recall=vector_recall)
        self.l2 = L2Planner(gateway, llm)
        self.l3 = L3Ground(gateway)

    def run(self, envelope: ToolEnvelope, task: dict[str, Any]) -> dict[str, Any]:
        selected = {str(item) for item in (task.get("selected_member_ids") or []) if item}
        if selected:
            record = self.l1.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
            known = set(envelope.auth.member_ids)
            if record is not None:
                known.update(node.node_id for node in record.evidence_nodes())
                known.update(
                    node.source_file_id for node in record.evidence_nodes() if node.source_file_id
                )
                known.update(node.scope_id for node in record.evidence_nodes() if node.scope_id)
            if not selected.issubset(known):
                return {
                    "review_state": ReviewState.BLOCKED.value,
                    "answer": None,
                    "citations": [],
                    "layers_used": ["POLICY"],
                    "steps": [],
                    "blocked_reason": "selected member is outside dossier scope",
                }
            scoped_auth = envelope.auth.model_copy(update={"member_ids": sorted(selected)})
            envelope = envelope.model_copy(update={"auth": scoped_auth})
        layers: list[str] = []

        # An unscoped natural-language question still gets bounded lexical
        # retrieval before the outline hint; the hint is the last resort.
        # Explicit vector policy also bypasses the deterministic L0 shortcut,
        # otherwise a vector request can incorrectly report NOT_REQUESTED.
        policy_flags = task.get("policy_flags") or {}
        l0 = (
            None
            if task.get("type") == "unscoped" or policy_flags.get("use_vector") is True
            else self.l0.run(envelope, task)
        )
        if l0:
            layers.append("L0")
            grounded = self.l3.run(
                envelope,
                task,
                review_state=l0["review_state"],
                answer=l0.get("answer"),
                citations=l0.get("citations") or [],
            )
            layers.append("L3")
            return {
                **grounded,
                "layers_used": layers,
                "l0_notes": l0.get("notes"),
                "steps": [],
                "last_prompt_chars": 0,
            }

        layers.append("L0")
        l1 = self.l1.run(envelope, task)
        l1 = _restrict_selected_members(l1, task, envelope, self.l1.gateway)
        layers.append("L1")
        outline_ids = [n["node_id"] for n in (l1.get("outline_ids") or [])]
        if l1.get("blocked"):
            grounded = self.l3.run(
                envelope,
                task,
                review_state=ReviewState.BLOCKED.value,
                answer=None,
                citations=[],
                outline_ids=outline_ids,
            )
            layers.append("L3")
            return {**grounded, "layers_used": layers, "steps": []}

        ttype = task.get("type")
        if ttype in COMPARE_TYPES and not (l1.get("hits") or []):
            grounded = self.l3.run(
                envelope,
                task,
                review_state=ReviewState.INSUFFICIENT_EVIDENCE.value,
                answer="Không đủ source để dựng quan hệ. Không suy đoán từ toàn bộ outline.",
                citations=[],
                outline_ids=outline_ids,
            )
            layers.append("L3")
            return {
                **grounded,
                "layers_used": layers,
                "steps": [],
                "relation_edges": l1.get("relation_edges") or [],
                "relation_issues": l1.get("relation_issues") or [],
                "retrieval_trace": l1.get("retrieval_trace") or {},
            }
        allow_llm = (
            policy_flags.get("use_llm") is True
            and policy_flags.get("use_vector") is True
            and policy_flags.get("egress_allowed") is True
        )
        # Unflagged direct stack callers retain the deterministic L2 fallback
        # contract. API requests always carry policy flags and therefore stay
        # fail-closed when external reasoning is not allowed.
        legacy_unflagged = not policy_flags
        need_l2 = ttype in COMPARE_TYPES and not query_too_broad(task.get("query") or "") and (
            allow_llm or legacy_unflagged
        )
        draft = None
        steps: list = []
        if need_l2:
            layers.append("L2")
            l2 = self.l2.run(envelope, task, l1)
            if l2.get("blocked"):
                grounded = self.l3.run(
                    envelope,
                    task,
                    review_state=ReviewState.BLOCKED.value,
                    answer=None,
                    citations=[],
                    outline_ids=outline_ids,
                )
                layers.append("L3")
                return {**grounded, "layers_used": layers, "steps": l2.get("steps") or []}
            steps = l2.get("steps") or []
            draft = l2.get("draft")

        if draft:
            state = (
                ReviewState.ANSWERED.value
                if draft.get("sufficient")
                else ReviewState.NEEDS_REVIEW.value
            )
            if ttype in {"compare", "cascade"}:
                state = ReviewState.NEEDS_REVIEW.value
            citations = draft.get("citations") or []
            answer = draft.get("answer")
            # A relation answer is incomplete when the live model cites only
            # one side of a multi-source comparison. Keep the LLM draft only
            # when it addresses every deterministic candidate; otherwise the
            # graph-backed renderer below supplies all sources and citations.
            if ttype in COMPARE_TYPES:
                required_ids = {
                    str(hit.get("node_id") or hit.get("chunk_id"))
                    for hit in (l1.get("hits") or [])[:8]
                    if hit.get("node_id") or hit.get("chunk_id")
                }
                cited_ids = {
                    str(c.get("node_id"))
                    for c in citations
                    if isinstance(c, dict) and c.get("node_id")
                }
                if len(required_ids) > 1 and not required_ids.issubset(cited_ids):
                    draft = None
        if not draft and l1.get("hits"):
            packed = []
            citations = []
            for h in l1["hits"][:8]:
                nid = h.get("node_id")
                if not nid:
                    continue
                try:
                    full = self.l1.gateway.call("get_node", envelope, node_id=nid)
                except Exception:
                    citations.append(h.get("citation") or {"node_id": nid})
                    continue
                packed.append(
                    {
                        "node_id": nid,
                        "label": full.get("raw_label"),
                        "path": " › ".join(
                            (full.get("ancestors") or []) + [full.get("raw_label") or ""]
                        ),
                        "text": (full.get("text") or "")[:800],
                        "side": doc_side(full.get("ancestors"), full.get("raw_label")),
                    }
                )
                citations.append(full.get("citation") or {"node_id": nid})
            rels = l1.get("relations") or []
            multi = len(packed) > 1 or bool(rels)
            answer = render_related_answer(packed, rels) if packed else {"hits": l1["hits"][:6]}
            state = (
                ReviewState.NEEDS_REVIEW.value
                if multi
                else (
                    ReviewState.ANSWERED.value
                    if ttype == "lookup_term"
                    else ReviewState.NEEDS_REVIEW.value
                )
            )
        elif not draft:
            state = ReviewState.INSUFFICIENT_EVIDENCE.value
            citations = []
            answer = None

        normalized_query = "".join(
            char
            for char in unicodedata.normalize("NFD", str(task.get("query") or "").casefold())
            if unicodedata.category(char) != "Mn"
        )
        if ttype == "unscoped" and any(
            phrase in normalized_query
            for phrase in ("on khong", "is it okay", "is this valid", "is this safe")
        ):
            state = ReviewState.INSUFFICIENT_EVIDENCE.value
            citations = []
            answer = None

        grounded = self.l3.run(
            envelope,
            task,
            review_state=state,
            answer=answer,
            citations=citations,
            outline_ids=outline_ids,
        )
        if ttype in COMPARE_TYPES and not (grounded.get("citations") or []) and l1.get("hits"):
            fallback_cites = [
                h.get("citation") or {"node_id": h.get("node_id")} for h in l1["hits"][:6]
            ]
            grounded = self.l3.run(
                envelope,
                task,
                review_state=ReviewState.NEEDS_REVIEW.value,
                answer=grounded.get("answer") or answer,
                citations=fallback_cites,
                outline_ids=outline_ids,
            )
        layers.append("L3")
        return {
            **grounded,
            "layers_used": layers,
            "steps": steps,
            "l1_hits": len(l1.get("hits") or []),
            "structured_keys": l1.get("structured_keys") or [],
            "relation_edges": l1.get("relation_edges") or [],
            "relation_issues": l1.get("relation_issues") or [],
            "retrieval_trace": l1.get("retrieval_trace") or {},
            "last_prompt_chars": getattr(self.l2, "last_prompt_chars", 0),
        }


def _restrict_selected_members(
    result: dict, task: dict, envelope: ToolEnvelope, gateway: ToolGateway
) -> dict:
    """Keep retrieval output inside the caller-selected dossier members."""

    selected = {str(item) for item in (task.get("selected_member_ids") or []) if item}
    if not selected:
        return result
    record = gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
    if record is None:
        # The gateway already enforces envelope scope; this fallback is only
        # for callers that pass a task without duplicated auth fields.
        return result
    allowed = {
        node.node_id
        for node in record.evidence_nodes()
        if node.node_id in selected or (node.source_file_id and node.source_file_id in selected)
    }
    bounded = dict(result)
    bounded["outline_ids"] = [
        item for item in result.get("outline_ids") or [] if item.get("node_id") in allowed
    ]
    bounded["hits"] = [
        item
        for item in result.get("hits") or []
        if (item.get("node_id") or item.get("chunk_id")) in allowed
    ]
    return bounded
