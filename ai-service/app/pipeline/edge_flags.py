"""Flags the extraction job must raise without inventing nodes or picking a winner."""

from __future__ import annotations

import re
import unicodedata

from app.contracts.models import HandoffIssue, ReviewState
from app.tools.store import DossierRecord

_DIEU = re.compile(r"^Điều (\d+)$")
_DIEU_HEADING = re.compile(r"^dieu\s+(\d+)\b")
_ART = re.compile(r"^(?:Art|Article) (\d+)$", re.IGNORECASE)


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("đ", "d")


def _issue(code: str, message: str) -> HandoffIssue:
    return HandoffIssue(code=code, message=message, review_state=ReviewState.NEEDS_REVIEW)


def dossier_edge_issues(record: DossierRecord) -> list[HandoffIssue]:
    issues: list[HandoffIssue] = []
    issues.extend(_numbering_gaps(record))
    issues.extend(_header_boundaries(record))
    issues.extend(_bilingual_pairs(record))
    issues.extend(_amended_definitions(record))
    return issues


def _numbering_gaps(record: DossierRecord) -> list[HandoffIssue]:
    grouped: dict[str | None, set[int]] = {}
    for node in record.nodes:
        match = _DIEU_HEADING.match(_fold((node.raw_label or "").strip()))
        if match is None:
            continue
        grouped.setdefault(node.parent_id, set()).add(int(match.group(1)))
    issues = []
    for parent_id, numbers in grouped.items():
        if len(numbers) < 2:
            continue
        missing = [number for number in range(min(numbers), max(numbers) + 1) if number not in numbers]
        if not missing:
            continue
        where = parent_id or "root"
        issues.append(_issue("NUMBERING_GAP", f"missing Điều {missing} under {where}; clause was not invented"))
    return issues


def _header_boundaries(record: DossierRecord) -> list[HandoffIssue]:
    for page in record.pages:
        text = (page.text or "").lstrip()
        # Only the furniture token, not a table title that merely starts with "Header".
        if text.startswith("HEADER ") or text.startswith("FOOTER "):
            return [_issue("RECONSTRUCTION_BOUNDARY", "page furniture sits between clause text; nodes were not joined")]
    return []


def _bilingual_pairs(record: DossierRecord) -> list[HandoffIssue]:
    articles: dict[int, str] = {}
    clauses: dict[int, str] = {}
    for node in record.nodes:
        label = (node.raw_label or "").strip()
        article = _ART.match(label)
        if article:
            articles[int(article.group(1))] = node.text or ""
            continue
        clause = _DIEU.match(label)
        if clause:
            clauses[int(clause.group(1))] = node.text or ""
    issues = []
    for number in sorted(set(articles) & set(clauses)):
        if articles[number].strip() == clauses[number].strip():
            continue
        issues.append(_issue("BILINGUAL_DIVERGENCE", f"Art {number} and Điều {number} differ; neither language was selected"))
    return issues


def _amended_definitions(record: DossierRecord) -> list[HandoffIssue]:
    issues = []
    for node in record.nodes:
        if "mới" not in (node.raw_label or "").casefold():
            continue
        windows = _windows(node.text or "", 3)
        for other in record.nodes:
            if other.node_id == node.node_id:
                continue
            folded_other = _fold(other.text or "")
            if any(window in folded_other for window in windows):
                issues.append(_issue("DEFINITION_CASCADE", "an amended definition is used later; no legal winner was chosen"))
                return issues
    return issues


def _windows(text: str, size: int) -> list[str]:
    words = _fold(text).split()
    return [" ".join(words[index:index + size]) for index in range(len(words) - size + 1)]
