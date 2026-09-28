"""Pure-fn confabulation signal extractor — scans an expanded Grid's cells
for heuristic signals that content is plausible-but-hollow. Deterministic and
sub-second; no AI call. Everything here is advisory-severity — blocking is
decided upstream by the evidence-policy invariant or the review advisor, not
by this module.

Signals:
  UNANCHORED_HIGH   - HIGH cell, evidence is empty
  PHANTOM_EVIDENCE  - evidence entries fail the shared anchor prefix regex
  DUPLICATE_CONTENT - >=70% 3-gram shingle overlap with another cell
  COORDINATE_LEAK   - content restates coordinates without expansion
  HEDGING_DENSITY   - >=3 hedge/vagueness regex hits
  STUB_AVOIDANCE    - HIGH cell with content shorter than 40 chars
"""
import json
import re
from dataclasses import dataclass
from typing import Dict, List, Pattern

from .types import CellResolution, Grid, GridCell, evidence_pattern

DUPLICATE_SHINGLE_THRESHOLD = 0.7
HEDGING_HIT_THRESHOLD = 3
STUB_AVOIDANCE_MIN_CHARS = 40
SHINGLE_SIZE = 3

# Hedge / vagueness patterns. Mirrors the sophistication classifier's
# vagueness signals, extended with evaluative/empty-phrase patterns common in
# plausible-but-hollow LLM cell content.
HEDGE_PATTERNS: List[Pattern] = [
    re.compile(r"\bsome\s+kind\s+of\b", re.I),
    re.compile(r"\b(maybe|perhaps|sort\s+of|kind\s+of)\b", re.I),
    re.compile(r"\b(things?|stuff)\b", re.I),
    re.compile(r"\b(various|several|many|multiple)\b", re.I),
    re.compile(r"\b(appropriate|suitable|relevant|necessary)\b", re.I),
    re.compile(r"\b(as\s+needed|as\s+appropriate|as\s+required)\b", re.I),
    re.compile(r"\b(robust|scalable|flexible|elegant)\b", re.I),
    re.compile(r"\b(best\s+practices?)\b", re.I),
]


@dataclass
class ConfabFinding:
    signal: str
    coordinates: Dict[str, str]
    details: str


def detect_confabulation(grid: Grid) -> List[ConfabFinding]:
    findings: List[ConfabFinding] = []
    for cell in grid.cells:
        findings.extend(_inspect_cell(cell))
    findings.extend(_find_duplicate_content(grid.cells))
    return findings


def signals_by_cell(findings: List[ConfabFinding]) -> Dict[str, List[str]]:
    """Group findings by coordinates -> signal[] — used by the loop to decide
    if a cell has accumulated enough signals to downgrade."""
    grouped: Dict[str, List[str]] = {}
    for finding in findings:
        key = json.dumps(finding.coordinates, sort_keys=True)
        grouped.setdefault(key, []).append(finding.signal)
    return grouped


def cells_exceeding_signal_threshold(findings: List[ConfabFinding], threshold: int) -> List[Dict[str, str]]:
    """Cells with signal-count >= threshold — candidates for downgrade to
    STUB in the expansion loop."""
    grouped = signals_by_cell(findings)
    out = []
    for key, signals in grouped.items():
        if len(signals) >= threshold:
            out.append(json.loads(key))
    return out


def _inspect_cell(cell: GridCell) -> List[ConfabFinding]:
    out: List[ConfabFinding] = []

    if cell.resolution == CellResolution.HIGH:
        if not cell.evidence:
            out.append(
                ConfabFinding(
                    signal="UNANCHORED_HIGH",
                    coordinates=cell.coordinates,
                    details="HIGH cell lacks any evidence entries",
                )
            )
        content_len = len((cell.content or "").strip())
        if content_len < STUB_AVOIDANCE_MIN_CHARS:
            out.append(
                ConfabFinding(
                    signal="STUB_AVOIDANCE",
                    coordinates=cell.coordinates,
                    details=f"HIGH content is {content_len} chars (< {STUB_AVOIDANCE_MIN_CHARS})",
                )
            )

    if cell.evidence:
        bad = [e for e in cell.evidence
               if not evidence_pattern().match(e)]
        if bad:
            out.append(
                ConfabFinding(
                    signal="PHANTOM_EVIDENCE",
                    coordinates=cell.coordinates,
                    details=f"{len(bad)} entry/entries fail prefix regex",
                )
            )

    content = (cell.content or "").strip()
    if content:
        if content_just_restates_coordinates(content, cell.coordinates):
            out.append(
                ConfabFinding(
                    signal="COORDINATE_LEAK",
                    coordinates=cell.coordinates,
                    details="content reduces to coordinate keywords with no expansion",
                )
            )
        hedge_hits = count_pattern_hits(content)
        if hedge_hits >= HEDGING_HIT_THRESHOLD:
            out.append(
                ConfabFinding(
                    signal="HEDGING_DENSITY",
                    coordinates=cell.coordinates,
                    details=f"{hedge_hits} hedge-pattern hits (threshold {HEDGING_HIT_THRESHOLD})",
                )
            )

    return out


def count_pattern_hits(text: str) -> int:
    """Total number of regex matches across all hedge patterns — NOT the
    count of distinct patterns that matched (e.g. "things things things" is
    3 hits from 1 pattern)."""
    return sum(len(pattern.findall(text)) for pattern in HEDGE_PATTERNS)


def content_just_restates_coordinates(content: str, coordinates: Dict[str, str]) -> bool:
    coord_values = [v.lower() for v in coordinates.values() if v]
    if not coord_values:
        return False
    words = re.sub(r"[^a-z0-9\s]", " ", content.lower()).split()
    if not words:
        return False
    if len(words) > 10:
        return False
    coord_words = set()
    for value in coord_values:
        coord_words.update(w for w in value.split() if w)
    if not coord_words:
        return False
    overlap = sum(1 for w in words if w in coord_words)
    return overlap / len(words) >= 0.75


def _find_duplicate_content(cells: List[GridCell]) -> List[ConfabFinding]:
    with_content = [c for c in cells if (c.content or "").strip()]
    shingles = [shingle_set(c.content) for c in with_content]
    flagged = set()
    findings: List[ConfabFinding] = []

    for i in range(len(with_content)):
        for j in range(i + 1, len(with_content)):
            overlap = jaccard(shingles[i], shingles[j])
            if overlap < DUPLICATE_SHINGLE_THRESHOLD:
                continue
            for idx in (i, j):
                if idx in flagged:
                    continue
                flagged.add(idx)
                findings.append(
                    ConfabFinding(
                        signal="DUPLICATE_CONTENT",
                        coordinates=with_content[idx].coordinates,
                        details=f"{overlap * 100:.0f}% shingle overlap with another cell",
                    )
                )
    return findings


def shingle_set(text: str) -> set:
    words = " ".join(text.lower().split()).split(" ")
    words = [w for w in words if w]
    if len(words) < SHINGLE_SIZE:
        return {" ".join(words)} if words else set()
    shingles = set()
    for i in range(len(words) - SHINGLE_SIZE + 1):
        shingles.add(" ".join(words[i : i + SHINGLE_SIZE]))
    return shingles


def jaccard(a: set, b: set) -> float:
    if not a and not b:
        return 0
    intersection = len(a & b)
    union = len(a) + len(b) - intersection
    return 0 if union == 0 else intersection / union
