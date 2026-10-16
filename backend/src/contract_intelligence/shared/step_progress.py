"""In-step progress of a pipeline step (S0..S10): ``{"done", "total", "unit"}``.

Stored as JSON text on ``pipeline_step.progress`` and sent unchanged to the
frontend in ``GET /runs/{id}/steps`` and the SSE ``step.changed`` event
(DOC-05b). ``None`` means the step cannot measure its progress.

Producers (AI1 progress messages, AI2 job polls) may report far more often
than the frontend needs, so a new value is written only when it moved enough
(``should_write``): every write costs one UPDATE and one SSE event.
"""

from __future__ import annotations

import json
from datetime import datetime
from typing import Any

# What ``done`` and ``total`` count; the frontend words "37/202 trang" by it.
UNITS: frozenset[str] = frozenset({"page", "document", "chunk", "clause", "pair"})

# A value that moved by at least 1/MIN_STEP_FRACTION of the total is written
# once MIN_INTERVAL_SECONDS passed; a slow step still refreshes every
# HEARTBEAT_SECONDS. With these, one step writes at most ~20 values plus one
# per 15 s, whatever the producer sends.
MIN_INTERVAL_SECONDS = 1.0
MIN_STEP_FRACTION = 20  # 5 %
HEARTBEAT_SECONDS = 15.0


def normalize(done: Any, total: Any, unit: Any) -> dict[str, Any] | None:
    """Return a valid progress value, or ``None`` when it cannot be shown.

    ``done`` is clamped into ``0..total``: a producer that over-counts must
    not show more than 100 %.
    """
    if type(done) is not int or type(total) is not int or total <= 0:
        return None
    if unit not in UNITS:
        return None
    return {"done": min(max(done, 0), total), "total": total, "unit": unit}


def parse(stored: str | None) -> dict[str, Any] | None:
    """Read ``pipeline_step.progress``; anything unreadable is ``None``."""
    if not stored:
        return None
    try:
        value = json.loads(stored)
    except (TypeError, ValueError):
        return None
    if not isinstance(value, dict):
        return None
    return normalize(value.get("done"), value.get("total"), value.get("unit"))


def dump(progress: dict[str, Any] | None) -> str | None:
    return None if progress is None else json.dumps(progress, sort_keys=True)


def completed(progress: dict[str, Any] | None) -> dict[str, Any] | None:
    """The value of a step that succeeded: ``done = total``."""
    if progress is None:
        return None
    return {**progress, "done": progress["total"]}


def should_write(
    previous: dict[str, Any] | None,
    previous_at: datetime | None,
    new: dict[str, Any],
    now: datetime,
) -> bool:
    """Whether ``new`` is worth one UPDATE and one SSE event after ``previous``."""
    if previous is None or previous_at is None:
        return True
    if (previous["total"], previous["unit"]) != (new["total"], new["unit"]):
        return True
    if new["done"] <= previous["done"]:
        return False  # never move backwards, never repeat
    if new["done"] == new["total"]:
        return True
    elapsed = (now - previous_at).total_seconds()
    if elapsed < MIN_INTERVAL_SECONDS:
        return False
    moved = new["done"] - previous["done"]
    return moved * MIN_STEP_FRACTION >= new["total"] or elapsed >= HEARTBEAT_SECONDS
