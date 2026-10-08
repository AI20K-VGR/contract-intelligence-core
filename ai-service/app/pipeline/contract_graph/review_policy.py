"""PASS gate of contract-graph edges (K5, D13): closed until reviewed calibration says otherwise.

An edge is ``PASS`` only when the operator enabled auto-pass, the edge is a standard,
explicit, exactly resolved operation with two VALID citations, **and** its op has at least
``MIN_N`` approved calibration records whose Wilson 95% lower bound reaches
``MIN_WILSON_LOWER``. Anything else stays ``NEEDS_REVIEW``. The thresholds are code, never
configuration; the committed ``calibration.json`` has ``n=0`` for every op.
"""

from __future__ import annotations

import json
import math
import os
from pathlib import Path
from typing import Any

from app.contracts.contract_graph import ContractEdge, EdgeMethod
from app.contracts.models import ReviewState

MIN_N = 60
MIN_WILSON_LOWER = 0.85

AUTO_PASS_ENV = "AI2_CONTRACT_GRAPH_AUTO_PASS"
CALIBRATION_PATH = Path(__file__).with_name("calibration.json")
CALIBRATION_SCHEMA = "contract-graph-calibration.v1"
APPROVED_ONLY = "approved-only"
_TRUTHY = {"1", "true", "yes", "on"}


def auto_pass_enabled() -> bool:
    return os.getenv(AUTO_PASS_ENV, "false").strip().casefold() in _TRUTHY


def wilson_lower(k: int, n: int, z: float = 1.96) -> float:
    """Lower bound of the Wilson score interval; same arithmetic as ``evals`` ``score.wilson``."""

    if n == 0:
        return 0.0
    p = k / n
    denom = 1 + z * z / n
    center = (p + z * z / (2 * n)) / denom
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / denom
    return max(0.0, center - margin)


def load_calibration(path: Path = CALIBRATION_PATH) -> dict[str, Any]:
    return json.loads(Path(path).read_text(encoding="utf-8"))


def calibration_problems(calibration: dict[str, Any], root: Path) -> list[str]:
    """Every op with ``n > 0`` must point at a report file under ``root`` that exists."""

    problems = []
    for op, entry in sorted(calibration.get("ops", {}).items()):
        if int(entry.get("n") or 0) <= 0:
            continue
        report = entry.get("report")
        if not report:
            problems.append(f"{op}: n={entry['n']} without a report")
        elif not (Path(root) / report).is_file():
            problems.append(f"{op}: report {report} does not exist")
    return problems


def review_state_for(edge: ContractEdge, calibration: dict[str, Any], enabled: bool) -> ReviewState:
    if not (
        enabled
        and edge.standard
        and edge.method == EdgeMethod.EXACT
        and not edge.implicit
        and edge.source_citation.validation_status == "VALID"
        and edge.target_citation.validation_status == "VALID"
    ):
        return ReviewState.NEEDS_REVIEW
    if (
        calibration.get("schema") != CALIBRATION_SCHEMA
        or calibration.get("ground_truth") != APPROVED_ONLY
    ):
        return ReviewState.NEEDS_REVIEW
    entry = calibration.get("ops", {}).get(edge.op.value) or {}
    n, k = entry.get("n"), entry.get("k")
    if not isinstance(n, int) or not isinstance(k, int) or not 0 <= k <= n:
        return ReviewState.NEEDS_REVIEW
    if n < MIN_N or wilson_lower(k, n) < MIN_WILSON_LOWER:
        return ReviewState.NEEDS_REVIEW
    return ReviewState.PASS
