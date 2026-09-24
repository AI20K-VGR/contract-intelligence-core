"""LLM fallback for boundaries the rule engine could not resolve confidently.

The resolver is a `Protocol`, so reconstruction never imports a specific
vendor SDK directly (section 22 of the module README) — swap
`OpenAIBoundaryResolver` for a Gemini/local/mock implementation without
touching the pipeline.

`SYSTEM_PROMPT` mirrors the Document Reconstruction Agent specification: the
agent only ever proposes one of the allowed actions, never rewrites,
paraphrases, summarizes, corrects, completes or infers missing content, and
returns `NEEDS_REVIEW` rather than guessing when evidence is weak. Its
self-reported confidence is only one of several weighted signals
(`config.compute_final_confidence`), never trusted alone.
"""

from __future__ import annotations

import json
import os
from typing import Any, Protocol

from .models import (
    Action,
    BoundaryContext,
    EntityType,
    ReasonCode,
    ReconstructionAction,
    ReconstructionTarget,
    Relationship,
    ResolutionMethod,
    ScoreBreakdown,
    SourceBlockRef,
)

SYSTEM_PROMPT = """You are a Document Reconstruction Agent for a Contract Intelligence / \
Legal IDP system.

You are NOT an OCR engine. You are NOT a legal advisor. You are NOT allowed to \
rewrite, paraphrase, summarize, correct, complete, or infer missing contract content.

Your job is only to decide whether blocks across a page boundary belong together, \
detect clause/section/list hierarchy, and detect multi-page table/row continuation. \
You ONLY propose an action; a deterministic executor performs the actual mutation:

LLM decides relationship. Code performs mutation.

Allowed actions:
NO_ACTION, MERGE_BLOCKS, CONTINUE_CLAUSE, NEW_CLAUSE, NEW_SECTION, NEW_PARAGRAPH, \
ATTACH_CHILD, CONTINUE_LIST, MERGE_TABLE, CONTINUE_TABLE, CONTINUE_ROW, IGNORE_HEADER, \
IGNORE_FOOTER, NEEDS_REVIEW

Allowed relationships:
CONTINUE_PARAGRAPH, NEW_PARAGRAPH, CONTINUE_CLAUSE, NEW_CLAUSE, NEW_SECTION, \
LIST_CONTINUE, TABLE_CONTINUE, ROW_CONTINUE, UNKNOWN

Allowed entity types:
SECTION, CLAUSE, PARAGRAPH, LIST_ITEM, TABLE, TABLE_ROW, HEADER, FOOTER

Allowed reason codes — use only these, never free-form chain-of-thought:
BOTTOM_TO_TOP, NO_END_PUNCTUATION, HAS_END_PUNCTUATION, NEW_NUMBERING, \
NUMBERING_SEQUENCE, SAME_INDENTATION, DIFFERENT_INDENTATION, SAME_STYLE, NEW_HEADING, \
SAME_ACTIVE_CLAUSE, TABLE_COLUMN_MATCH, TABLE_HEADER_MATCH, TABLE_LAYOUT_MATCH, \
INCOMPLETE_TABLE_ROW, REPEATED_TABLE_HEADER, LIST_SEQUENCE, REPEATED_HEADER, \
REPEATED_FOOTER, LOW_OCR_CONFIDENCE, AMBIGUOUS_STRUCTURE, INSUFFICIENT_EVIDENCE

Rules:
1. Use only information explicitly available in the input `document_state`, \
`previous_page` and `next_page`. Never invent content missing because of OCR.
2. Never change numbers, dates, money, percentages, durations, party names, tax \
codes, contract numbers or any other critical legal value — reproduce OCR text \
unchanged, spelling errors included.
3. Never guess table cells or rows; only report which cells/rows should be connected.
4. Classify text as a header/footer only when the evidence given supports repetition \
across pages — never from a single page's position alone.
5. If evidence is weak, or a merge could change the interpretation of a critical \
legal value, return `NEEDS_REVIEW` with `relationship` "UNKNOWN" and `target` null \
rather than guessing.
6. Confidence bands: 0.95-1.00 very strong, 0.85-0.94 strong, 0.70-0.84 ambiguous, \
below 0.70 insufficient evidence.
7. Return JSON only. No Markdown, no explanation outside the JSON. Schema:
{"action": "...", "relationship": "..." | null, "entity_type": "...", \
"source_blocks": [{"page": 0, "block_id": "..."}], "target": {"node_id": "...", \
"parent_id": "..."} | null, "reason_codes": ["..."], "confidence": 0.0, \
"requires_review": false}
"""


class EngineUnavailable(RuntimeError):
    """The LLM resolver's dependency/credentials are unavailable."""


class BoundaryLLMResolver(Protocol):
    """Anything that can classify a boundary can be plugged in here."""

    def resolve(self, context: BoundaryContext) -> ReconstructionAction: ...


def _block_payload(block: Any) -> dict[str, Any]:
    return {
        "block_id": block.block_id,
        "type": block.type,
        "text": block.text,
        "bbox": list(block.bbox),
        "ocr_confidence": block.confidence,
    }


def context_payload(context: BoundaryContext) -> dict[str, Any]:
    """Serialize a `BoundaryContext` into exactly the input shape from
    section 2 of the agent specification."""
    return {
        "document_id": context.document_id,
        "document_state": context.document_state.model_dump(),
        "previous_page": {
            "page": context.previous_page,
            "height": context.previous_page_height,
            "blocks": [_block_payload(b) for b in context.previous_blocks],
        },
        "next_page": {
            "page": context.next_page,
            "height": context.next_page_height,
            "blocks": [_block_payload(b) for b in context.next_blocks],
        },
    }


def _fallback_needs_review(context: BoundaryContext) -> ReconstructionAction:
    return ReconstructionAction(
        action=Action.NEEDS_REVIEW,
        relationship=Relationship.UNKNOWN,
        entity_type=EntityType.CLAUSE,
        source_blocks=[
            SourceBlockRef(page=context.previous_page, block_id=b.block_id)
            for b in context.previous_blocks[-1:]
        ]
        + [
            SourceBlockRef(page=context.next_page, block_id=b.block_id)
            for b in context.next_blocks[:1]
        ],
        target=None,
        reason_codes=[ReasonCode.AMBIGUOUS_STRUCTURE],
        confidence=0.0,
        requires_review=True,
        method=ResolutionMethod.LLM,
    )


def _parse_response(context: BoundaryContext, raw: str) -> ReconstructionAction:
    try:
        payload = json.loads(raw)
        action = Action(payload["action"])
        relationship = Relationship(payload["relationship"]) if payload.get("relationship") else None
        entity_type = EntityType(payload["entity_type"])
        source_blocks = [
            SourceBlockRef(
                page=b["page"],
                block_id=b.get("block_id"),
                table_id=b.get("table_id"),
                row_id=b.get("row_id"),
                cell_id=b.get("cell_id"),
            )
            for b in payload.get("source_blocks", [])
        ]
        target_payload = payload.get("target")
        target = ReconstructionTarget(**target_payload) if target_payload else None
        model_confidence = max(0.0, min(1.0, float(payload.get("confidence", 0.0))))
        reason_codes = [
            ReasonCode(code) for code in payload.get("reason_codes", []) if code in ReasonCode.__members__
        ]
    except (json.JSONDecodeError, KeyError, ValueError, TypeError):
        return _fallback_needs_review(context)

    scores = ScoreBreakdown(model_score=model_confidence)
    return ReconstructionAction(
        action=action,
        relationship=relationship,
        entity_type=entity_type,
        source_blocks=source_blocks or _fallback_needs_review(context).source_blocks,
        target=target,
        reason_codes=reason_codes,
        confidence=model_confidence,
        requires_review=bool(payload.get("requires_review", False)),
        method=ResolutionMethod.LLM,
        scores=scores,
    )


class MockLLMResolver:
    """Deterministic, canned resolver for tests and offline development.

    Never calls out to a real model, so pipeline behavior stays
    reproducible (section 17 of the module README). Looks up a fixed
    answer keyed by `(previous_page, next_page)`, defaulting to
    `NEEDS_REVIEW`/`UNKNOWN` at zero confidence.
    """

    def __init__(
        self,
        answers: dict[tuple[int, int], ReconstructionAction] | None = None,
    ) -> None:
        self._answers = answers or {}

    def resolve(self, context: BoundaryContext) -> ReconstructionAction:
        key = (context.previous_page, context.next_page)
        if key in self._answers:
            return self._answers[key]
        return _fallback_needs_review(context)


class OpenAIBoundaryResolver:
    """Sends only the small boundary window to an OpenAI model, temperature 0,
    JSON-only output — never the whole contract (section 20 of the spec)."""

    def __init__(self, **config: Any) -> None:
        self.config = config
        self.model = config.get("model", "gpt-5.6-luna")
        self._client = None

    def _load(self) -> Any:
        if self._client is not None:
            return self._client
        api_key = self.config.get("api_key") or os.environ.get("OPENAI_API_KEY")
        if not api_key:
            raise EngineUnavailable("OPENAI_API_KEY is not set")
        try:
            from openai import OpenAI
        except ImportError as exc:
            raise EngineUnavailable("openai package is not installed") from exc
        client_kwargs: dict[str, Any] = {"api_key": api_key}
        if self.config.get("base_url"):
            client_kwargs["base_url"] = self.config["base_url"]
        self._client = OpenAI(**client_kwargs)
        return self._client

    def resolve(self, context: BoundaryContext) -> ReconstructionAction:
        client = self._load()
        response = client.chat.completions.create(
            model=self.model,
            temperature=0,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(context_payload(context))},
            ],
        )
        raw = response.choices[0].message.content or "{}"
        return _parse_response(context, raw)
