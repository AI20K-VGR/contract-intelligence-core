from __future__ import annotations

import re
from typing import Any

from app.contracts.models import Citation, ReviewState, ToolEnvelope
from app.pipeline.citations import CitationResolver
from app.pipeline.outline import citation_for_node
from app.pipeline.grounding import GroundingGate
from app.tools.gateway import ToolBlocked, ToolGateway


class L3Ground:
    def __init__(self, gateway: ToolGateway) -> None:
        self.gateway = gateway
        self.gate = GroundingGate()

    def _normalize_citations(
        self,
        envelope: ToolEnvelope,
        citations: list[dict[str, Any]] | None,
        allowed: set[str],
    ) -> list[dict[str, Any]]:
        """Re-resolve every citation through the active tree.

        L0 assemblers and older L2 drafts may return only ``node_id`` and a
        short span.  The gateway is the single source of truth for breadcrumb,
        file scope and page revision metadata.
        """

        out: list[dict[str, Any]] = []
        for citation in citations or []:
            if not isinstance(citation, dict):
                continue
            node_id = citation.get("node_id") or citation.get("id")
            if not node_id or (allowed and node_id not in allowed):
                continue
            try:
                node = self.gateway.call("get_node", envelope, node_id=node_id)
            except (ToolBlocked, TypeError):
                continue
            rich = self._registry_citation(envelope, citation) or dict(node.get("citation") or {})
            rich["node_id"] = node_id
            supplied_span = str(citation.get("text_span") or "")
            if supplied_span and supplied_span in str(node.get("text") or ""):
                rich = self._resolve_span(envelope, rich, supplied_span)
            rich["validation_status"] = self._citation_status(envelope, rich)
            out.append(rich)
        return out

    def _resolve_span(self, envelope, rich, span):
        if rich.get("table_id") or span == rich.get("text_span"):
            return rich
        record = self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if record is None:
            return rich
        return citation_for_node(record.evidence_nodes(), record.pages, rich["node_id"], text_span=span) or rich

    def _citation_status(self, envelope: ToolEnvelope, citation: dict[str, Any]) -> str:
        record = self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if record is None:
            return "INVALID"
        try:
            return CitationResolver(record.pages, record.tables, record.evidence_nodes()).verify(Citation.model_validate(citation)).status
        except Exception:
            return "INVALID"

    def _registry_citation(
        self,
        envelope: ToolEnvelope,
        citation: dict[str, Any],
    ) -> dict[str, Any] | None:
        citation_id = citation.get("citation_id") or citation.get("id")
        if not citation_id:
            return None
        record = self.gateway.store.get(envelope.auth.tenant_id, envelope.auth.dossier_id)
        if record is None:
            return None
        registered = record.citation_index.get(str(citation_id))
        return registered.model_dump() if registered is not None else None

    @staticmethod
    def _verified(citations: list[dict[str, Any]]) -> list[dict[str, Any]]:
        return [item for item in citations if item.get("validation_status") == "VALID"]

    def run(
        self,
        envelope: ToolEnvelope,
        task: dict[str, Any],
        *,
        review_state: str,
        answer: Any,
        citations: list[dict[str, Any]],
        outline_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        if review_state == ReviewState.BLOCKED.value:
            return _finalize_grounding(review_state, None, [], grounded=False)

        allowed = set(outline_ids or [])
        if not allowed:
            try:
                outline = self.gateway.call("list_structure", envelope, dossier_id=envelope.auth.dossier_id)
                allowed = {n["node_id"] for n in outline}
            except ToolBlocked:
                allowed = set()

        if task.get("type") in {"count_entity", "too_broad", "party_card", "annex_card", "annex_list", "field_card", "unscoped"}:
            normalized = self._normalize_citations(envelope, citations, allowed)
            return _finalize_grounding(review_state, answer, normalized)

        if review_state in {
            ReviewState.INSUFFICIENT_EVIDENCE.value,
            ReviewState.NOT_COMPARABLE.value,
            ReviewState.NEEDS_REVIEW.value,
        }:
            if task.get("type") in {
                "lookup_insufficient",
                "structure",
                "not_comparable",
                "security",
                "too_broad",
                "count_entity",
                "lookup_clause",
            }:
                normalized = self._normalize_citations(envelope, citations, allowed)
                return _finalize_grounding(review_state, answer, normalized)

        if task.get("type") == "table" and review_state == ReviewState.ANSWERED.value:
            normalized = self._normalize_citations(envelope, citations, allowed)
            return _finalize_grounding(review_state, answer, normalized)

        texts: list[str] = []
        valid_cites = []
        verified_cites = []
        for c in citations or []:
            if isinstance(c, str):
                c = {"node_id": c}
            nid = None
            if isinstance(c, dict):
                nid = c.get("node_id") or c.get("id")
            if not nid or (allowed and nid not in allowed):
                continue
            try:
                node = self.gateway.call("get_node", envelope, node_id=nid)
            except (ToolBlocked, TypeError):
                continue
            blob = " ".join(
                [
                    str(node.get("text") or ""),
                    str(node.get("structured_value") or ""),
                    str(node.get("raw_label") or ""),
                ]
            )
            texts.append(blob)
            span = str((c.get("text_span") if isinstance(c, dict) else "") or "")
            if span and span not in blob:
                span = (node.get("structured_value") or node.get("text") or "")[:200]
            rich = self._registry_citation(envelope, c) or dict(node.get("citation") or {})
            rich["node_id"] = nid
            rich = self._resolve_span(envelope, rich, span or rich.get("text_span") or "")
            rich["validation_status"] = self._citation_status(envelope, rich)
            valid_cites.append(rich)
            if rich["validation_status"] == "VALID":
                verified_cites.append(rich)

        if task.get("forbidden") and "legal_winner" in (task.get("forbidden") or []):
            if isinstance(answer, dict) and answer.get("legal_winner"):
                return _finalize_grounding(
                    ReviewState.NEEDS_REVIEW.value,
                    {k: v for k, v in answer.items() if k != "legal_winner"},
                    valid_cites,
                )

        if review_state == ReviewState.ANSWERED.value and not verified_cites and task.get("must_cite"):
            return _finalize_grounding(
                ReviewState.INSUFFICIENT_EVIDENCE.value,
                answer,
                [],
                grounded=False,
            )

        if _invented_annex(answer, allowed, texts):
            return _finalize_grounding(ReviewState.NEEDS_REVIEW.value, answer, valid_cites)

        if review_state == ReviewState.ANSWERED.value and isinstance(answer, str) and texts:
            if not _extractive(answer, texts, valid_cites):
                return _finalize_grounding(ReviewState.NEEDS_REVIEW.value, answer, valid_cites)

        return _finalize_grounding(
            review_state,
            answer,
            valid_cites or self._normalize_citations(envelope, citations, allowed),
        )


def _filter_cites(citations: list[dict[str, Any]] | None, allowed: set[str]) -> list[dict[str, Any]]:
    out = []
    for c in citations or []:
        if not isinstance(c, dict):
            continue
        nid = c.get("node_id")
        if nid and (not allowed or nid in allowed):
            out.append(c)
    return out


def _finalize_grounding(
    review_state: str,
    answer: Any,
    citations: list[dict[str, Any]],
    *,
    grounded: bool | None = None,
) -> dict[str, Any]:
    """Apply the answer contract after every L3 exit path.

    Source text is data only.  A draft cannot promote itself to ANSWERED: the
    state requires at least one resolver-verified citation and every explicit
    substantive claim must point at a usable claim-level citation.
    """

    verified = [item for item in citations if item.get("validation_status") == "VALID"]
    is_grounded = bool(verified) if grounded is None else grounded
    claims_ok = _claims_have_usable_citations(answer, verified)
    if review_state == ReviewState.ANSWERED.value and (not is_grounded or not claims_ok):
        review_state = ReviewState.NEEDS_REVIEW.value
        is_grounded = False

    result: dict[str, Any] = {
        "review_state": review_state,
        "answer": answer,
        "citations": citations,
        "grounded": is_grounded,
    }
    if isinstance(answer, dict) and isinstance(answer.get("claims"), list):
        result["claims"] = answer["claims"]
    elif review_state == ReviewState.ANSWERED.value and answer:
        result["claims"] = [
            {
                "claim_id": "claim-1",
                "text": str(answer),
                "citation_ids": [item.get("citation_id") or item.get("node_id") for item in verified],
            }
        ]
    return result


def _claims_have_usable_citations(answer: Any, verified: list[dict[str, Any]]) -> bool:
    if not isinstance(answer, dict) or "claims" not in answer:
        return True
    claims = answer.get("claims")
    if not isinstance(claims, list):
        return False
    by_ref = {
        str(value)
        for item in verified
        for value in (item.get("citation_id"), item.get("node_id"))
        if value
    }
    for claim in claims:
        if not isinstance(claim, dict):
            return False
        text = str(claim.get("text") or claim.get("claim") or "").strip()
        if not text:
            continue
        refs = claim.get("citation_ids") or claim.get("citations") or []
        if claim.get("citation_id"):
            refs = [claim["citation_id"], *refs]
        if not refs:
            return False
        if not any(
            (isinstance(ref, dict) and ref.get("validation_status") == "VALID")
            or (not isinstance(ref, dict) and str(ref) in by_ref)
            for ref in refs
        ):
            return False
    return True


def _extractive(answer: str, texts: list[str], cites: list[dict[str, Any]]) -> bool:
    joined = "\n".join(texts).lower()
    if not answer.strip():
        return False
    if answer.lower() in joined:
        return True
    for c in cites:
        span = str(c.get("text_span") or "")
        if len(span) >= 4 and span.lower() in joined:
            return True
    digits = re.findall(r"\d{6,}", answer)
    if digits and any(d in joined.replace(" ", "") for d in digits):
        return True
    words = [w for w in re.split(r"\s+", answer) if len(w) >= 6]
    return bool(words) and sum(1 for w in words if w.lower() in joined) >= max(1, len(words) // 3)


def _invented_annex(answer: Any, allowed: set[str], texts: list[str]) -> bool:
    blob = str(answer).lower() + "\n" + "\n".join(texts).lower()
    for m in re.finditer(r"phụ lục\s+(\d+)", str(answer), re.I):
        lab = f"phụ lục {m.group(1)}"
        if lab not in blob.replace("phu luc", "phụ lục") and not any(lab in t.lower() for t in texts):
            return True
    return False
