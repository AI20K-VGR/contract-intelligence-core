import json
import re
from dataclasses import dataclass, field
from enum import Enum

from app.config import settings
from app.structure import strip_diacritics

# Matched against strip_diacritics(text): a scanned annex/article heading routinely
# loses its diacritics the same way structure.ARTICLE_PATTERN's targets do (see that
# module). A table fragment starting right after one of these is a NEW table, however
# closely its column layout happens to resemble the one before it (real case: two
# annexes with an identical item-table header, "Phụ lục 01" then "Phụ lục 02").
_ANNEX_HEADING_PATTERN = re.compile(r"^(Phu\s*luc|Bieu(?:\s+so)?|Chuong|Muc|Dieu|Article)\b",
                                     re.IGNORECASE)

# Rule-engine score thresholds (see _rule_score): at or above this, the fragments are
# confidently one table without needing the agent; at or below this, they are
# confidently two. Only the range between the two is genuinely ambiguous.
_MERGE_SCORE_FLOOR = 8
_SPLIT_SCORE_CEILING = 2

# Evidence sent to the agent is metadata and a couple of short row previews only —
# never a full table or a page image. Capped here as a last line of defense even if a
# caller passes a longer preview in.
_MAX_ROW_PREVIEW_CHARS = 60
_MAX_ROW_PREVIEWS = 2


def is_annex_heading(text: str) -> bool:
    """True when `text` looks like a new section/annex heading (Phụ lục, Điều, Chương,
    Biểu, Mục, or their English equivalents) rather than an ordinary table row or
    caption. Diacritic-insensitive for the same reason structure.ARTICLE_PATTERN is.
    """
    return bool(text and _ANNEX_HEADING_PATTERN.match(strip_diacritics(text.strip())))


class ContinuityDecision(str, Enum):
    MERGE = "merge"
    SPLIT = "split"
    NEEDS_REVIEW = "needs_review"


@dataclass
class ContinuityEvidence:
    """Everything the Table Continuity Agent is allowed to see about one candidate
    pair of adjacent-page table fragments — small metadata and, at most, a couple of
    short row previews. Never the full table, never a page image.
    """

    same_document: bool
    page_a: int
    page_b: int
    column_similarity: float
    header_similarity: float | None  # None: fragment B has no header row at all
    last_anchor: int | None
    first_anchor: int | None
    anchor_continuous: bool | None
    previous_ends_near_bottom: bool
    next_starts_near_top: bool
    previous_ends_with_total: bool
    heading_between: str | None
    previous_tail_rows: list[str] = field(default_factory=list)
    next_head_rows: list[str] = field(default_factory=list)


@dataclass
class ContinuityResult:
    decision: ContinuityDecision
    reasons: list[str]
    rule_score: float
    used_agent: bool


def _hard_guard(evidence: ContinuityEvidence) -> ContinuityResult | None:
    """Cases that never need scoring or the agent: the answer is certain from a single
    signal. Returns None when nothing here applies, so the caller falls through to the
    rule engine.
    """
    if not evidence.same_document:
        return ContinuityResult(ContinuityDecision.SPLIT, ["different_document"], 0, False)
    if evidence.page_b != evidence.page_a + 1:
        return ContinuityResult(ContinuityDecision.SPLIT, ["non_adjacent_pages"], 0, False)
    if evidence.previous_ends_with_total:
        return ContinuityResult(ContinuityDecision.SPLIT, ["previous_table_already_totaled"], 0, False)
    if evidence.heading_between and is_annex_heading(evidence.heading_between):
        return ContinuityResult(ContinuityDecision.SPLIT, ["new_section_heading"], 0, False)
    if (
        evidence.anchor_continuous is False
        and evidence.first_anchor == 1
        and (evidence.last_anchor or 0) > 1
    ):
        return ContinuityResult(ContinuityDecision.SPLIT, ["anchor_reset"], 0, False)
    return None


def _rule_score(evidence: ContinuityEvidence) -> tuple[float, list[str]]:
    score = 0.0
    reasons = []
    if evidence.column_similarity >= 0.97:
        score += 3
        reasons.append("column_signature_match")
    if evidence.anchor_continuous is True:
        score += 3
        reasons.append("anchor_continuity")
    if evidence.header_similarity is not None and evidence.header_similarity >= 0.9:
        score += 2
        reasons.append("header_match")
    elif evidence.header_similarity is None:
        score += 2
        reasons.append("no_header_on_continuation")
    if evidence.previous_ends_near_bottom:
        score += 1
        reasons.append("previous_ends_near_bottom")
    if evidence.next_starts_near_top:
        score += 1
        reasons.append("next_starts_near_top")
    return score, reasons


_AGENT_SYSTEM_PROMPT = """\
You are a Table Continuity judge for scanned contract tables. You are given ONLY a \
small metadata packet about two table fragments found on consecutive pages — never \
the full table and never an image. Decide whether fragment B is a direct continuation \
of fragment A (MERGE), a different table (SPLIT), or genuinely unclear from the \
evidence given (NEEDS_REVIEW). Prefer NEEDS_REVIEW over guessing when the evidence is \
insufficient or conflicting. Respond with strict JSON only:
{"decision": "merge" | "split" | "needs_review", "reasons": [string, ...], \
"blocking_reason": string | null}"""


def _ask_agent(evidence: ContinuityEvidence, rule_score: float) -> ContinuityResult | None:
    """Consults the DeepSeek-hosted agent for a genuinely ambiguous pair. Never raises:
    a missing key, disabled config, timeout, rate limit, or malformed response all
    degrade to None — the caller then falls back to NEEDS_REVIEW rather than guessing,
    same posture as _gpt_vision_lines in document_processing.py.
    """
    if not settings.deepseek_api_key:
        return None
    try:
        from openai import OpenAI

        client = OpenAI(api_key=settings.deepseek_api_key, base_url=settings.deepseek_base_url)
        payload = {
            "same_document": evidence.same_document,
            "page_gap": evidence.page_b - evidence.page_a,
            "column_similarity": evidence.column_similarity,
            "header_similarity": evidence.header_similarity,
            "last_anchor": evidence.last_anchor,
            "first_anchor": evidence.first_anchor,
            "anchor_continuous": evidence.anchor_continuous,
            "previous_ends_near_bottom": evidence.previous_ends_near_bottom,
            "next_starts_near_top": evidence.next_starts_near_top,
            "heading_between": evidence.heading_between,
            "previous_tail_rows": [
                row[:_MAX_ROW_PREVIEW_CHARS] for row in evidence.previous_tail_rows[-_MAX_ROW_PREVIEWS:]
            ],
            "next_head_rows": [
                row[:_MAX_ROW_PREVIEW_CHARS] for row in evidence.next_head_rows[:_MAX_ROW_PREVIEWS]
            ],
        }
        response = client.chat.completions.create(
            model=settings.deepseek_model,
            temperature=0,
            max_tokens=512,
            response_format={"type": "json_object"},
            messages=[
                {"role": "system", "content": _AGENT_SYSTEM_PROMPT},
                {"role": "user", "content": json.dumps(payload, ensure_ascii=False)},
            ],
        )
        data = json.loads(response.choices[0].message.content or "{}")
        decision = ContinuityDecision(data["decision"])
        reasons = [str(r) for r in data.get("reasons") or []]
        return ContinuityResult(decision, reasons, rule_score, True)
    except Exception:
        return None


def decide(evidence: ContinuityEvidence, config: dict) -> ContinuityResult:
    """The full three-tier decision: hard guards, then the deterministic rule engine,
    then — only for the genuine gray zone, and only when config enables it — the
    DeepSeek agent. Always returns a result; never raises.
    """
    guard = _hard_guard(evidence)
    if guard is not None:
        return guard
    score, reasons = _rule_score(evidence)
    if score >= _MERGE_SCORE_FLOOR:
        return ContinuityResult(ContinuityDecision.MERGE, reasons, score, False)
    if score <= _SPLIT_SCORE_CEILING:
        return ContinuityResult(ContinuityDecision.SPLIT, reasons, score, False)
    if config.get("table_continuity_agent"):
        result = _ask_agent(evidence, score)
        if result is not None:
            return result
    return ContinuityResult(ContinuityDecision.NEEDS_REVIEW, [*reasons, "ambiguous_score_no_agent"],
                             score, False)
