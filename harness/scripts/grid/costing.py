"""Costing & guardrail (grid/v2) — the counting engine. `ca.py` is
deterministic, so the exact row count a covering array will produce is known
BEFORE any fill work happens, at 0 token cost. This module does three things:
(1) count rows exactly by delegating to `ca.greedy_ca`/`ca.seeded_extend`
(DRY — never reimplements the CA algorithm), (2) compare that count against
an ABSOLUTE row guardrail (never token-derived, never a lower-bound
multiple), and (3) build a deterministic machine-readable receipt.

Two invariants this module's tests lock on the SOURCE, not just behavior:
  - Engine/skill separation: no interactive-question call path, no
    skill/prompt import. This module only counts and reports; the skill
    layer (`grid-mode.md`) is what interrupts the user about an
    over-guardrail grid — a plain module has no way to interrupt a human
    anyway.
  - Two-tier landmine: no per-request usage-counter or spend-limit
    vocabulary of any kind. Tầng-1 harness cannot observe a real per-request
    usage figure (the model self-reports, the harness sees none), so a limit
    derived from one here would be a fabricated number. The guardrail is
    `axes.guardrail_rows()` — an absolute row count from
    `grid-strength.yaml` (the strength SSOT).

This module never auto-degrades: an over-guardrail verdict still reports the
FULL count. Lowering strength or trimming rows is a decision only the user
can make, relayed through the skill layer — never something this engine does
on its own.
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, List, Optional

from . import ca


def count_rows(shape: List[int], t: int) -> int:
    """Exact row count for `shape` at strength `t` — delegates to
    `ca.greedy_ca` (the single source of truth for CA generation; this
    module never reimplements it)."""
    return len(ca.greedy_ca(shape, t))


def cost_table(shape: List[int], strengths: List[int]) -> Dict[int, int]:
    """Row count per strength level — the "what does the next tier cost"
    table a user sees before choosing to escalate.

    A rung above ``len(shape)`` is OMITTED, not counted and not clamped: a
    2-axis grid has no 3-tuples, so t3 has no honest answer for it. Counting
    it crashed (``ca.greedy_ca`` requires ``t <= len(shape)``) and took the
    whole build with it, because the shipped ladder offers t2 AND t3 while
    the table is built from every shipped rung regardless of the shape in
    front of it. Clamping instead of omitting would be worse than either:
    the t2 row-count printed under a t3 label reads as "t3 costs nothing"."""
    k = len(shape)
    return {t: count_rows(shape, t) for t in strengths if 1 <= t <= k}


@dataclass
class GuardrailVerdict:
    count: int
    guardrail_rows: int
    over: bool
    margin: int


def guardrail_verdict(count: int, guardrail_rows: int) -> GuardrailVerdict:
    """Compare `count` against the absolute row guardrail. Strict `>` (never
    `>=`) — equal to the guardrail is NOT over. Absolute compare only: never
    multiplied by a lower bound, never derived from a token count."""
    return GuardrailVerdict(
        count=count,
        guardrail_rows=guardrail_rows,
        over=count > guardrail_rows,
        margin=count - guardrail_rows,
    )


def build_receipt(shape, strength, t, guardrail_rows, ship_strengths) -> dict:
    """Machine-readable record of one counting decision — shape, chosen
    strength, the row count, whether it crossed the guardrail, and the full
    cost table across the strengths a skill is deciding among. Deterministic
    (0-token): calling twice with the same args returns an equal dict."""
    if not 1 <= t <= len(shape):
        # The CHOSEN strength, unlike a cost_table column, cannot be quietly
        # dropped — the caller asked for a grid at this t. Say so in a
        # sentence carrying both numbers rather than surfacing ca.py's
        # internal bound, which reads like an engine fault instead of an
        # impossible request.
        raise ValueError(
            "strength t=%d needs at least %d axes, but this grid has %d axes "
            "(shape %r) — a %d-tuple cannot exist here. Choose t <= %d, or "
            "add an axis." % (t, t, len(shape), shape, t, len(shape)))
    count = count_rows(shape, t)
    verdict = guardrail_verdict(count, guardrail_rows)
    return {
        "shape": shape,
        "strength": strength,
        "t": t,
        "count": count,
        "guardrail_rows": guardrail_rows,
        "over": verdict.over,
        "cost_table": cost_table(shape, ship_strengths),
        "generator": "greedy_ca",
    }


def emit_receipt(receipt: dict, out_path: Optional[str] = None) -> str:
    """Serialize a receipt to deterministic JSON (no argless clock — mirrors
    `grid_engine._emit_json`). Writes to `out_path` when given; always
    returns the JSON text."""
    text = json.dumps(receipt, indent=2, ensure_ascii=False)
    if out_path:
        Path(out_path).write_text(text + "\n", encoding="utf-8")
    return text


def escalation_verdict(existing_rows, shape, t_new, guardrail_rows) -> dict:
    """Guardrail verdict for a strength escalation. The guardrail compares
    against the FULL post-escalation grid (`ca.seeded_extend`, existing rows
    + delta) — the scope that actually ships — while the cost charged to the
    user is `delta_count` only (existing rows already paid their fill cost
    at the prior strength)."""
    full_rows = ca.seeded_extend(existing_rows, shape, t_new)
    full_count = len(full_rows)
    seed_count = len(existing_rows)
    delta_count = full_count - seed_count
    return {
        "full_count": full_count,
        "delta_count": delta_count,
        "seed_count": seed_count,
        "over": full_count > guardrail_rows,
        "cost_scope": "delta",
    }
