from __future__ import annotations

import re
import unicodedata
from typing import Any

from app.contracts.models import ReviewState, ToolEnvelope
from app.llm.client import NineRouterClient
from app.pipeline.result_structure import _is_running_furniture
from app.reasoning.l0_rules import L0Rules, query_too_broad
from app.reasoning.l1_retrieval import COMPARE_TYPES, L1Retrieval
from app.reasoning.l2_plan import L2Planner
from app.reasoning.l3_ground import L3Ground
from app.reasoning.relations import doc_side, render_comparison_answer, render_related_answer
from app.reasoning.vector_recall import VectorRecallService
from app.tools.gateway import ToolBlocked, ToolGateway


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
        # L0 runs even when vector recall is allowed: skipping it made the
        # "full" configuration answer 11/24 benchmark questions correctly
        # against 21/24 without vector. A vector request answered by L0
        # reports NOT_NEEDED, not NOT_REQUESTED.
        policy_flags = task.get("policy_flags") or {}
        l0 = None if task.get("type") == "unscoped" else self.l0.run(envelope, task)
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
                "retrieval_trace": {
                    "vector_status": "NOT_NEEDED"
                    if policy_flags.get("use_vector") is True
                    else "NOT_REQUESTED"
                },
            }

        layers.append("L0")
        l1 = self.l1.run(envelope, task)
        l1 = _restrict_selected_members(l1, task, envelope, self.l1.gateway)
        layers.append("L1")
        outline_ids = [n["node_id"] for n in (l1.get("outline_ids") or [])]
        coverage_group_ids = [str(node_id) for node_id in (l1.get("coverage_groups") or []) if node_id]
        planner_task = (
            {**task, "coverage_group_ids": coverage_group_ids}
            if coverage_group_ids
            else task
        )
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
            return {
                **grounded, "layers_used": layers, "steps": [], "used_llm": False,
                "retrieval_trace": {"vector_status": "NOT_REQUESTED"},
            }

        ttype = task.get("type")
        if ttype in COMPARE_TYPES and not (l1.get("hits") or l1.get("logical_tables")):
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
                "used_llm": False,
                "logical_tables": [],
            }
        allow_llm = (
            policy_flags.get("egress_allowed") is True
            and policy_flags.get("use_llm") is True
        )
        # Unflagged direct stack callers retain the deterministic L2 fallback
        # contract. API requests always carry policy flags and therefore stay
        # fail-closed when external reasoning is not allowed.
        legacy_unflagged = not policy_flags
        freeform = ttype == "unscoped" and not _is_evaluation_query(task.get("query") or "")
        need_l2 = (ttype in COMPARE_TYPES or freeform) and not query_too_broad(task.get("query") or "") and (
            allow_llm or legacy_unflagged
        )
        draft = None
        steps: list = []
        llm_invoked = False
        if need_l2:
            layers.append("L2")
            l2 = self.l2.run(envelope, planner_task, l1)
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
                return {
                    **grounded, "layers_used": layers, "steps": l2.get("steps") or [],
                    "used_llm": bool(l2.get("llm_called")),
                    "retrieval_trace": l1.get("retrieval_trace") or {"vector_status": "NOT_REQUESTED"},
                }
            steps = l2.get("steps") or []
            draft = l2.get("draft")
            llm_invoked = l2.get(
                "llm_called",
                not l2.get("fallback") and not l2.get("skipped") and not l2.get("blocked"),
            )

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
            if coverage_group_ids and ttype == "unscoped":
                draft = _complete_grouped_draft(
                    self.l1.gateway,
                    envelope,
                    draft,
                    coverage_group_ids,
                )
                citations = draft.get("citations") or []
                answer = draft.get("answer")
            # A single cited node is not a comparison, so the renderer lists
            # every source. Two cited nodes keep the model sentence; any
            # source it skipped is still attached for review.
            if ttype in COMPARE_TYPES:
                required_ids = list(dict.fromkeys(
                    str(node_id)
                    for node_id in (l1.get("anchor_ids") or [])
                    if node_id
                ))
                if len(required_ids) < 2:
                    required_ids.extend(
                        str(hit.get("node_id") or hit.get("chunk_id"))
                        for hit in (l1.get("hits") or [])[:8]
                        if (hit.get("node_id") or hit.get("chunk_id"))
                        and str(hit.get("node_id") or hit.get("chunk_id")) not in required_ids
                    )
                required_ids = required_ids[:8]
                cited_ids = {
                    str(c.get("node_id"))
                    for c in citations
                    if isinstance(c, dict) and c.get("node_id")
                }
                # Citing "M1" or "4.2" covers the heading L1 retrieved; the
                # model quotes the sub-clause that carries the value.
                record = self.l1.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
                parent_of = {n.node_id: n.parent_id for n in record.evidence_nodes()} if record else {}
                # Each citation covers one source: itself, else its parent.
                # Counting both would let a single quote pass as a comparison.
                covered = {
                    required_id
                    for required_id in required_ids
                    if required_id in cited_ids
                    or str(parent_of.get(required_id) or "") in cited_ids
                }
                # One cited node is not a comparison. Two or more keep the
                # model sentence; sources it skipped stay attached for review.
                if len(required_ids) > 1 and len(covered) < 2:
                    draft = None
                else:
                    required_set = set(required_ids)
                    for hit in (l1.get("hits") or [])[:8]:
                        nid = str(hit.get("node_id") or hit.get("chunk_id") or "")
                        if nid and nid in required_set and nid not in cited_ids:
                            citations.append(hit.get("citation") or {"node_id": nid})
        if not draft and l1.get("logical_tables") and not l1.get("hits"):
            tables = l1["logical_tables"]
            citations = [
                citation
                for table in tables for row in table.get("rows", [])
                for citation in row.get("cell_citations", {}).values()
            ]
            answer = {
                "logical_tables": tables,
                "coverage": [table.get("coverage") for table in tables],
                "note": "Source table rows are shown for human review.",
            }
            state = ReviewState.NEEDS_REVIEW.value
        elif not draft and l1.get("hits"):
            packed = []
            citations = []
            seen_ids: set[str] = set()
            comparison_ids = (
                _comparison_fallback_ids(self.l1.gateway, envelope, planner_task, l1)
                if ttype in COMPARE_TYPES
                else []
            )
            compare_ids = set(l1.get("anchor_ids") or []) if ttype in COMPARE_TYPES else set()
            if comparison_ids:
                candidate_hits = [
                    {"node_id": node_id, "citation": {"node_id": node_id}}
                    for node_id in comparison_ids
                ]
            else:
                candidate_hits = [
                    h for h in (l1.get("hits") or [])
                    if not compare_ids
                    or str(h.get("node_id") or h.get("chunk_id") or "") in compare_ids
                ]
                if ttype in COMPARE_TYPES and len(candidate_hits) < 2:
                    candidate_hits = list(l1["hits"][:8])
            for h in candidate_hits[:8]:
                nid = h.get("node_id")
                if not nid:
                    continue
                candidate_nodes = (
                    [str(nid)]
                    if comparison_ids
                    else _node_and_children(self.l1.gateway, envelope, str(nid))
                )
                for candidate in candidate_nodes:
                    if candidate in seen_ids or len(packed) >= 12:
                        continue
                    seen_ids.add(candidate)
                    try:
                        full = self.l1.gateway.call("get_node", envelope, node_id=candidate)
                    except Exception:
                        citations.append(h.get("citation") or {"node_id": candidate})
                        continue
                    packed.append(
                        {
                            "node_id": candidate,
                            "label": full.get("raw_label"),
                            "path": " › ".join(
                                (full.get("ancestors") or []) + [full.get("raw_label") or ""]
                            ),
                            "text": (full.get("text") or "")[:800],
                            "side": doc_side(full.get("ancestors"), full.get("raw_label")),
                            "is_root": str(full.get("type") or "") in {"CLAUSE", "SECTION"},
                            "type": full.get("type"),
                        }
                    )
                    citations.append(full.get("citation") or {"node_id": candidate})
            rels = l1.get("relations") or []
            multi = len(packed) > 1 or bool(rels)
            answer = (
                render_comparison_answer(packed, str(task.get("query") or ""))
                if comparison_ids
                else None
            )
            answer = answer or (render_related_answer(packed, rels) if packed else {"hits": l1["hits"][:6]})
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

        if ttype == "unscoped" and _is_evaluation_query(task.get("query") or ""):
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
            "anchor_ids": l1.get("anchor_ids") or [],
            "retrieval_trace": l1.get("retrieval_trace") or {},
            "last_prompt_chars": getattr(self.l2, "last_prompt_chars", 0),
            "used_llm": llm_invoked,
            "logical_tables": l1.get("logical_tables") or [],
        }


def _normalized_query(query: str) -> str:
    normalized = "".join(
        char
        for char in unicodedata.normalize("NFD", str(query or "").casefold())
        if unicodedata.category(char) != "Mn"
    )
    return normalized.replace("đ", "d")


def _is_evaluation_query(query: str) -> bool:
    """Keep explicit legal/validity judgements behind the review gate."""

    normalized = _normalized_query(query)
    return any(
        phrase in normalized
        for phrase in (
            "on khong",
            "is it okay",
            "is this valid",
            "is this safe",
            "is this legal",
            "co hop phap",
            "co hop le",
            "hop dong nay co dung",
            "hop dong nay co an toan",
            "co nen ky",
            "nen ky hop dong",
        )
    )


def _complete_grouped_draft(
    gateway: ToolGateway,
    envelope: ToolEnvelope,
    draft: dict[str, Any],
    group_ids: list[str],
) -> dict[str, Any]:
    """Add grounded sibling clauses omitted by a freeform LLM draft."""

    cited_ids = {
        str(citation.get("node_id"))
        for citation in draft.get("citations") or []
        if isinstance(citation, dict) and citation.get("node_id")
    }
    missing = [node_id for node_id in group_ids if node_id not in cited_ids]
    if not missing:
        return draft

    completed = dict(draft)
    citations = list(draft.get("citations") or [])
    answer = str(draft.get("answer") or "").strip()
    additions: list[str] = []
    for node_id in missing:
        try:
            node = gateway.call("get_node", envelope, node_id=node_id)
        except (ToolBlocked, TypeError):
            continue
        text = str(node.get("text") or node.get("raw_label") or "").strip()
        if not text:
            continue
        if text not in answer:
            additions.append(f"- {text}")
        citations.append(node.get("citation") or {"node_id": node_id, "text_span": text[:200]})
    if additions:
        suffix = "Các điều khoản cùng nhóm được truy xuất:\n" + "\n".join(additions)
        completed["answer"] = f"{answer}\n\n{suffix}" if answer else suffix
    completed["citations"] = citations
    return completed


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
    allowed_tables = {
        table.table_id
        for table in record.tables
        if table.node_id in allowed or table.table_id in allowed
    }
    bounded["logical_tables"] = [
        table for table in result.get("logical_tables") or []
        if table.get("table_id") in allowed_tables
    ]
    bounded["coverage_groups"] = [
        node_id for node_id in result.get("coverage_groups") or [] if node_id in allowed
    ]
    return bounded


def _comparison_fallback_ids(
    gateway: ToolGateway,
    envelope: ToolEnvelope,
    task: dict[str, Any],
    l1: dict[str, Any],
) -> list[str]:
    """Choose stable representative nodes for a body-versus-annex fallback.

    L1 may rank a nearby row or a clause child differently across lexical and
    vector retrieval.  For a structural comparison, walk back to the named
    article/appendix roots and select their evidence in document order.  A
    working-day definition and the first table row are preferred when present;
    these are grounded examples, not contract-wide inferences.
    """

    record = gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
    if record is None:
        return []
    nodes = sorted(record.evidence_nodes(), key=lambda item: (item.order, item.node_id))
    by_id = {node.node_id: node for node in nodes}
    source_roles = {source.file_id: source.role for source in record.source_files}

    def fold(value: str | None) -> str:
        text = unicodedata.normalize("NFD", str(value or "").casefold())
        text = "".join(char for char in text if unicodedata.category(char) != "Mn")
        return text.replace("đ", "d")

    def labels(node) -> list[str]:
        chain: list[str] = []
        current = node
        guard = 0
        while current is not None and guard < 20:
            chain.append(current.raw_label or "")
            current = by_id.get(current.parent_id) if current.parent_id else None
            guard += 1
        return list(reversed(chain))

    def side(node) -> str:
        role = source_roles.get(node.source_file_id or "")
        if role in {"body", "annex"}:
            return role
        return "annex" if any("phu luc" in fold(label) or "annex" in fold(label) for label in labels(node)) else "body"

    def is_root(node) -> bool:
        label = fold(node.raw_label)
        return bool(
            re.match(r"^(?:dieu|article)\s+\d+", label)
            or re.match(r"^(?:phu luc|annex|appendix)\s+\d+", label)
        )

    def number(node, kind: str) -> int | None:
        label = fold(node.raw_label)
        pattern = r"(?:dieu|article)\s+0*(\d+)" if kind == "body" else r"(?:phu luc|annex|appendix)\s+0*(\d+)"
        match = re.search(pattern, label)
        return int(match.group(1)) if match else None

    roots = [node for node in nodes if is_root(node)]
    body_roots = [node for node in roots if side(node) == "body"]
    annex_roots = [node for node in roots if side(node) == "annex"]
    query = fold(str(task.get("query") or ""))
    article_match = re.search(r"(?:dieu|article)\s+0*(\d+)", query)
    annex_match = re.search(r"(?:phu luc|annex|appendix)\s+0*(\d+)", query)
    # Topic-specific comparisons (payment, tax, value, penalty, progress)
    # need their existing semantic/table path; this renderer is for the
    # structural "Điều n và Phụ lục n" question only.
    if (
        not article_match
        or not annex_match
        or not any(cue in query for cue in ("so sanh", "compare", "doi chieu", "versus", " vs "))
        or any(
        cue in query
        for cue in ("thanh toan", "payment", "gia tri", "contract value", "phat", "penalty", "tien do", "thue", "tax")
        )
    ):
        return []
    article_number = int(article_match.group(1)) if article_match else None
    annex_number = int(annex_match.group(1)) if annex_match else None

    def choose_root(candidates: list, wanted: int | None, seed_ids: list[str]):
        if wanted is not None:
            exact = [node for node in candidates if number(node, side(node)) == wanted]
            if exact:
                return exact[0]
        seeded = [node for node in candidates if node.node_id in seed_ids]
        if seeded:
            return seeded[0]
        return candidates[0] if candidates else None

    seed_ids = [
        str(item)
        for item in [*(l1.get("anchor_ids") or []), *(h.get("node_id") or h.get("chunk_id") for h in l1.get("hits") or [])]
        if item
    ]

    def root_from_seed(node_id: str):
        current = by_id.get(node_id)
        while current is not None:
            if is_root(current):
                return current
            current = by_id.get(current.parent_id) if current.parent_id else None
        return None

    for seed_id in seed_ids:
        root = root_from_seed(seed_id)
        if root is None:
            continue
        target = annex_roots if side(root) == "annex" else body_roots
        if root not in target:
            target.append(root)

    body_root = choose_root(body_roots, article_number, seed_ids)
    annex_root = choose_root(annex_roots, annex_number, seed_ids)
    if body_root is None or annex_root is None:
        return []

    def children(root) -> list:
        return [
            node
            for node in nodes
            if node.parent_id == root.node_id and not _is_running_furniture(node.raw_label or "")
        ]

    body_children = children(body_root)
    annex_children = children(annex_root)
    body_detail = next(
        (node for node in body_children if "ngay lam viec" in fold(node.text or node.raw_label)),
        None,
    )
    body_detail = body_detail or (body_children[0] if body_children else body_root)
    annex_detail = next(
        (node for node in annex_children if re.match(r"^\s*\|\s*\d+\s*\|", node.text or node.raw_label)),
        None,
    )
    annex_detail = annex_detail or (annex_children[0] if annex_children else annex_root)
    selected: list[str] = []
    for node in (body_root, body_detail, annex_root, annex_detail):
        if node.node_id not in selected:
            selected.append(node.node_id)
    return selected


def _node_and_children(gateway: ToolGateway, envelope: ToolEnvelope, node_id: str, limit: int = 6) -> list[str]:
    """Return a heading plus the body lines stored under it."""

    record = gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
    if record is None:
        return [node_id]
    children = [
        node.node_id
        for node in record.evidence_nodes()
        if node.parent_id == node_id and node.node_id != node_id and not _is_running_furniture(node.raw_label or "")
    ]
    return [node_id, *children[:limit]]
