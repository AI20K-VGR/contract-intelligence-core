"""Grid depth expander — the injectable-LLM seam that turns one SKELETON
cell into a HIGH / LOW / STUB / MISSING / N-A cell under the anti-confab
contract. Mirrors the FrankCode ``gridExpander.ts`` pure-orchestrator shape:
build a cache-shareable prompt prefix, call an injected invoker, validate
the response against the contract, and degrade gracefully to STUB on any
failure — "honestly incomplete beats convincingly filled".

``expand_cell`` NEVER raises. Every failure path (no invoker wired, the
invoker throwing, a HIGH/LOW response missing required evidence, a
STUB/MISSING/N-A response missing attestation, an unrecognized resolution,
or the remaining budget being too small to spend) degrades to an attested
STUB cell instead of propagating an exception.

Port note (TS async -> Python sync): FrankCode's ``LlmInvoker`` is an async
callable; here ``invoke_llm`` is a plain synchronous callable and
``expand_cell`` is an ordinary function — there is no event loop anywhere
in this module. When ``invoke_llm`` is omitted (the default), expansion
degrades deterministically to STUB, so the whole engine is testable and
runnable without any model.

Cache strategy: ``build_expander_prompt`` returns ``{"prefix", "suffix"}``.
The prefix is byte-identical across every cell in a grid run (anti-confab
clause + policy config + axes, no coordinate) so a caller can warm a
prompt cache and amortize it across the whole loop; the suffix carries the
per-cell coordinates + remaining budget.
"""
import json
from dataclasses import dataclass
from typing import Callable, Dict, List, Literal, Optional

from . import axes
from .density import DensityConfig
from .types import (
    NEVER_FILLED_ATTESTATION,
    CellResolution,
    Grid,
    GridCell,
    evidence_pattern,
)

FallbackReason = Literal[
    "llm-unavailable",
    "invoker-threw",
    "evidence-missing",
    "attestation-missing",
    "unknown-resolution",
]

# Byte-identical across every cell in a grid run (contains no coordinate) —
# verbatim FrankCode prose incl. its own evidence-prefix set (the
# harness-flavored EVIDENCE_PREFIX_PATTERN union is a keyword-lint consumer
# concern, not this module's).
ANTI_CONFAB_PREFIX = (
    "You are expanding one cell of a grid-planning artifact. Output MUST be one of:\n"
    "  - HIGH with cited evidence[] entries matching (src/|tests/|PLAN-|TASK-|RFC-|metric:|axis:)\n"
    "  - LOW with explicit thinness acknowledgment\n"
    "  - STUB with reason (budget / out-of-scope / cannot-ground)\n"
    "  - MISSING with attestation of the gap\n"
    "  - N/A with exclusion rationale\n"
    "NEVER emit HIGH without evidence. If you cannot ground this cell in the\n"
    "provided skeleton, task YAML, or prior plan sections, emit STUB — filler is\n"
    "a worse failure than an honest gap."
)


@dataclass
class ExpanderLlmResponse:
    """What an injected invoker hands back for one cell. ``tokens_used`` is
    required in the FrankCode contract (gridExpander.ts:23-29); it is placed
    ahead of the optional fields here only because Python dataclasses (3.9,
    no ``kw_only``) require every field after the first defaulted one to
    also carry a default."""

    resolution: CellResolution
    tokens_used: int
    content: Optional[str] = None
    evidence: Optional[List[str]] = None
    attestation: Optional[str] = None


@dataclass
class LlmInvokerContext:
    prefix: str
    suffix: str
    max_tokens: int
    cell: GridCell
    grid: Grid


LlmInvoker = Callable[[LlmInvokerContext], ExpanderLlmResponse]


@dataclass
class ExpanderInput:
    grid: Grid
    cell: GridCell
    policy: DensityConfig
    plan_context: Optional[str] = None
    # Injected LLM caller; omitted -> expansion falls back to STUB.
    invoke_llm: Optional[LlmInvoker] = None
    # Immutable token budget reserved for this cell (parallel-mode seam —
    # avoids every parallel cell reading the same stale grid.budget).
    reserved_tokens: Optional[int] = None


@dataclass
class ExpanderResult:
    cell: GridCell
    # Optional: None means the spend was never measured (no invoker, the
    # invoker threw, or a replay filler carried no count) — the cell omits
    # tokens_spent rather than reporting a fake 0. See _measured_tokens.
    tokens_spent: Optional[int]
    fallback_used: bool
    fallback_reason: Optional[FallbackReason] = None


def build_expander_prompt(expander_input: ExpanderInput) -> Dict[str, str]:
    """Build the cache-shareable prompt. The prefix carries no coordinate so
    it is byte-identical across every cell in a run; the suffix carries the
    coordinates + remaining budget (gridExpander.ts:123-152)."""
    grid = expander_input.grid
    cell = expander_input.cell
    policy = expander_input.policy
    plan_context = expander_input.plan_context
    remaining = max(0, grid.budget.depth_tokens_max - grid.budget.depth_tokens_used)

    axis_lines = [f"  - {axis.id} ({axis.label}): [{', '.join(axis.values)}]" for axis in grid.axes]
    prefix = "\n".join(
        [
            ANTI_CONFAB_PREFIX,
            "",
            f"Density policy: density_tier={policy.density_tier.value} density={policy.density.value} "
            f"coverageFloor={policy.coverage_floor} evidence={policy.evidence_required} "
            f"perCellCap={policy.per_cell_token_cap}",
            "",
            "Axes:",
            *axis_lines,
            "",
            f"Plan context:\n{plan_context}\n" if plan_context else "",
        ]
    )

    suffix = "\n".join(
        [
            f"Coordinates: {json.dumps(cell.coordinates)}",
            f"Budget remaining: {remaining} tokens (perCellCap={policy.per_cell_token_cap}).",
            "",
            'Respond with JSON: {"resolution":"HIGH|LOW|STUB|MISSING|N/A","content":"...",'
            '"evidence":["src/...","PLAN-..."],"attestation":"...","tokensUsed":N}',
        ]
    )

    return {"prefix": prefix, "suffix": suffix}


def expand_cell(expander_input: ExpanderInput) -> ExpanderResult:
    """Expand one cell under the anti-confab contract. NEVER raises — every
    error degrades to a STUB cell with an attested reason (gridExpander.ts:
    161-257)."""
    grid = expander_input.grid
    cell = expander_input.cell
    policy = expander_input.policy

    # ``remaining`` sizes the model-call budget below (max_tokens=min(...)) —
    # it is a call-size parameter, not a gate: the low-budget stub branch
    # that used to fall back a cell out purely for low remaining
    # budget (token is telemetry-only at tầng-1, see module docstring).
    remaining = (
        expander_input.reserved_tokens
        if expander_input.reserved_tokens is not None
        else max(0, grid.budget.depth_tokens_max - grid.budget.depth_tokens_used)
    )

    if expander_input.invoke_llm is None:
        return _stub_result(cell, "llm-unavailable", None)

    prompt = build_expander_prompt(expander_input)
    try:
        response = expander_input.invoke_llm(
            LlmInvokerContext(
                prefix=prompt["prefix"],
                suffix=prompt["suffix"],
                max_tokens=min(policy.per_cell_token_cap, remaining),
                cell=cell,
                grid=grid,
            )
        )
    except Exception:
        # Catches ANY invoker failure — the seam call is never allowed to
        # propagate (gridExpander.ts:190-192).
        return _stub_result(cell, "invoker-threw", None)

    # The seam returns raw model output: tokens_used may be None/garbage and
    # resolution may be a plain string ("STUB") rather than a CellResolution —
    # coerce both here so a malformed-but-well-meant response degrades cleanly
    # instead of (a) raising out of a NEVER-raises function or (b) silently
    # dropping real content down the unknown-resolution path.
    tokens_spent = _measured_tokens(response.tokens_used)
    resolution = _coerce_resolution(response.resolution)

    if resolution == CellResolution.HIGH:
        evidence = [e for e in (response.evidence or []) if e]
        if not evidence:
            return _stub_result(cell, "evidence-missing", tokens_spent)
        return ExpanderResult(
            cell=GridCell(
                coordinates=cell.coordinates,
                resolution=CellResolution.HIGH,
                content=(response.content or "").strip(),
                evidence=evidence,
                tokens_spent=tokens_spent,
            ),
            tokens_spent=tokens_spent,
            fallback_used=False,
        )

    if resolution == CellResolution.LOW:
        raw_evidence = response.evidence or []
        if policy.evidence_required == "always" and len(raw_evidence) == 0:
            return _stub_result(cell, "evidence-missing", tokens_spent)
        low_cell = GridCell(
            coordinates=cell.coordinates,
            resolution=CellResolution.LOW,
            content=(response.content or "").strip() or "(thin)",
            tokens_spent=tokens_spent,
        )
        if response.evidence and len(response.evidence) > 0:
            low_cell.evidence = [e for e in response.evidence if e]
        return ExpanderResult(cell=low_cell, tokens_spent=tokens_spent, fallback_used=False)

    if resolution in (CellResolution.STUB, CellResolution.MISSING, CellResolution.NA):
        attestation = (response.attestation or "").strip()
        if not attestation:
            return _stub_result(cell, "attestation-missing", tokens_spent)
        return ExpanderResult(
            cell=GridCell(
                coordinates=cell.coordinates,
                resolution=resolution,
                attestation=attestation,
                tokens_spent=tokens_spent,
            ),
            tokens_spent=tokens_spent,
            fallback_used=False,
        )

    # SKELETON or anything else the contract doesn't recognize.
    return _stub_result(cell, "unknown-resolution", tokens_spent)


def _measured_tokens(value) -> Optional[int]:
    """Token counts arrive untrusted. A numeric value is a real (model
    self-reported) measurement — clamped to a non-negative int. None or an
    unparseable value means the spend was NEVER measured (tầng-1 cannot
    observe a real per-cell spend, e.g. the replay filler carries no count);
    return None so the cell OMITS tokens_spent rather than inventing a 0 that
    is indistinguishable from a genuine measured 0. Never raises."""
    if value is None:
        return None
    try:
        return max(0, int(value))
    except (TypeError, ValueError):
        return None


def _coerce_resolution(value):
    """Accept either a CellResolution or its value-string ("STUB"); an
    unrecognized value returns None so expand_cell falls through to the
    unknown-resolution STUB rather than mistaking a valid string for a miss."""
    if isinstance(value, CellResolution):
        return value
    try:
        return CellResolution(value)
    except (ValueError, KeyError):
        return None


def _stub_result(cell: GridCell, reason: FallbackReason, tokens_spent: Optional[int]) -> ExpanderResult:
    # No path sets `budget_exceeded` anymore — the field stays on
    # GridCell (back-compat + future telemetry) but write-nowhere.
    stub_cell = GridCell(
        coordinates=cell.coordinates,
        resolution=CellResolution.STUB,
        attestation=_stub_attestation_for(reason),
        tokens_spent=tokens_spent,
    )
    return ExpanderResult(cell=stub_cell, tokens_spent=tokens_spent, fallback_used=True, fallback_reason=reason)


_STUB_ATTESTATIONS: Dict[str, str] = {
    # Imported, not re-typed: stopping.py and grid_emit_guard.py both match on
    # this exact string to recognise a never-processed cell, so a copy here
    # would be a third place for it to drift (types.NEVER_FILLED_ATTESTATION).
    "llm-unavailable": NEVER_FILLED_ATTESTATION,
    "invoker-threw": "LLM invoker threw — returning STUB rather than risk confabulation",
    "evidence-missing": "LLM returned HIGH without evidence — downgraded to STUB per anti-confab contract",
    "attestation-missing": "LLM returned STUB/MISSING/N/A without attestation — rewrote with this contract-enforced reason",
    "unknown-resolution": "LLM returned an unsupported resolution — downgraded to STUB",
}


def _stub_attestation_for(reason: FallbackReason) -> str:
    return _STUB_ATTESTATIONS[reason]


def is_evidence_well_anchored(evidence: str) -> bool:
    """Exposed for review.py and diagnostics."""
    return bool(evidence_pattern().match(evidence))


def load_strong_tier_keywords(path=None) -> tuple:
    """Read the STRONG-tier keyword list (security/auth/crypto/...) from its
    real SSOT, ``grid-strength.yaml``, via ``axes.strength_config`` —
    replaces the retired ``STRONG_TIER_KEYWORDS`` Python literal (moved to
    the YAML SSOT). Fail-closed, mirroring ``density.UnknownDensityTierError``: a
    missing or empty ``strong_tier_keywords`` section raises rather than
    returning a silent empty tuple, which would make ``lint_tier_mismatch``
    never fire without anyone noticing the config drifted."""
    cfg = axes.strength_config(path)
    keywords = cfg.get("strong_tier_keywords")
    if not keywords:
        raise axes.GridAxisConfigError(
            "grid-strength.yaml missing/empty 'strong_tier_keywords' section"
        )
    return tuple(keywords)


# Weak (thinly-treated) resolutions lint_tier_mismatch flags a strong-keyword
# cell against — HIGH is deliberately excluded: a critical cell resolved HIGH
# was treated deeply, so it earns no finding.
_WEAK_RESOLUTIONS_FOR_TIER_MISMATCH = frozenset(
    {CellResolution.STUB, CellResolution.MISSING, CellResolution.NA, CellResolution.LOW}
)


@dataclass
class TierMismatchFinding:
    """One post-hoc lint hit: a cell whose coordinates mention a STRONG-tier
    keyword but that was resolved thinly. Carries no severity — review.py
    (the only consumer) assigns severity, keeping this a pure, gate-free
    scan (advisory-not-gate)."""

    coordinates: Dict[str, str]
    keyword: str
    resolution: str
    detail: str


def lint_tier_mismatch(grid: Grid, path=None) -> List[TierMismatchFinding]:
    """POST-HOC advisory lint — replaces the retired pre-hoc tier-suggestion
    router (dead-code removal: it guessed a cell's tier BEFORE expansion
    and fed a context field the sole live invoker never read). This
    scans AFTER expansion instead: a cell whose coordinate values contain a
    STRONG keyword (substring match, same semantics the retired router used)
    but whose resolution is thin (STUB/MISSING/N-A/LOW) earns one finding —
    a critical concern that was treated shallowly. HIGH is never flagged.
    Never raises for lint reasons of its own; ``load_strong_tier_keywords``
    can still raise if the SSOT itself is missing/malformed (fail-closed by
    design)."""
    keywords = load_strong_tier_keywords(path)
    findings: List[TierMismatchFinding] = []
    for cell in grid.cells:
        if cell.resolution not in _WEAK_RESOLUTIONS_FOR_TIER_MISMATCH:
            continue
        all_values = " ".join(cell.coordinates.values()).lower()
        for keyword in keywords:
            if keyword in all_values:
                findings.append(
                    TierMismatchFinding(
                        coordinates=dict(cell.coordinates),
                        keyword=keyword,
                        resolution=cell.resolution.value,
                        detail=(
                            f"cell touches strong-tier keyword {keyword!r} but was "
                            f"resolved {cell.resolution.value} — consider deeper treatment"
                        ),
                    )
                )
                break  # one finding per cell is enough signal
    return findings
