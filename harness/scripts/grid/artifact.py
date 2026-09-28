"""grid/artifact.py — build + write the ``coverage-grid`` gate artifact.

Every write routes through ``harness/scripts/artifact_io.py::stamp_and_write``
(atomic ``.tmp`` + fsync + ``os.replace``, ``run_seq`` stamp from
``HARNESS_RUN_SEQ``) — never a raw ``open().write()``. ``coverage-grid`` is
advisory-only (see ``artifact_check.py``'s ``_REQUIRED_FIELDS`` entry): a
``reject`` verdict is surfaced for a consumer to read, this module never
enforces it as a hard local block.

EVIDENCE_PREFIX note: ``harness.scripts.grid.types.EVIDENCE_PREFIX_PATTERN``
IS the shipped default — a harness-flavored UNION of the FrankCode-original
prefixes (``src/``, ``tests/``, ``PLAN-``, ``TASK-``, ``RFC-``, ``metric:``,
``axis:``) plus the tầng-1 prefixes (``harness/``, ``plans/``, ``docs/``,
``DEC-``) real harness evidence actually uses. That union is defined ONCE in
``types.py`` and every invariant/confab module imports it from there — this
module never redefines or overrides what ``invariants.py``/``confab.py`` read.
``EVIDENCE_PREFIX_SETS`` below is a WRITER-BOUNDARY-ONLY override: a caller
may record a narrower named set as artifact metadata (e.g. a non-harness
install declaring it only trusts the FrankCode-original prefixes), but
picking one here never mutates or shadows the ``types.py`` constant the
review/invariant/confab pass actually validates evidence against.
"""
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable, Dict, Optional

# Sibling in harness/scripts/, reachable by either entrance — the long name
# with the repo root on sys.path, the bare name with only harness/scripts.
# A relative `from .. import` cannot serve both: under the bare entrance this
# package IS top-level and has no parent to climb to. Binding it twice in one
# process is harmless — artifact_io holds no module state, and stamp_and_write
# re-reads run_seq from the environment on every call.
try:
    from harness.scripts import artifact_io
except ImportError:
    import artifact_io
from . import provenance
from .types import (
    EVIDENCE_PREFIX_PATTERN,
    Grid,
    configured_extra_prefixes,
)

# Provenance cross-ref: a future merge between this independent tầng-1 grid
# engine and the tầng-2 orchestrator's own grid copy needs to know both exist
# (a cross-tier awareness marker) — a plain string, never an import of orchestrator/.
CROSS_REF = "orchestrator/grid"

# Writer-boundary override sets, keyed by name. "union" (default) is the
# shipped types.py pattern re-exposed under a name; "frankcode"/"harness" are
# narrower named subsets a caller may opt into explicitly (module docstring).
EVIDENCE_PREFIX_SETS: Dict[str, str] = {
    "union": EVIDENCE_PREFIX_PATTERN.pattern,
    "frankcode": r"^(src/|tests/|PLAN-|TASK-|RFC-|metric:|axis:)",
    "harness": r"^(harness/|plans/|DEC-|docs/)",
}
DEFAULT_EVIDENCE_PREFIX_SET = "union"


def build_coverage_grid_record(
    grid: Grid,
    verdict: Dict[str, Any],
    *,
    evidence_prefix_set: str = DEFAULT_EVIDENCE_PREFIX_SET,
    now: Optional[Callable[[], str]] = None,
    axis_selection: Optional[Dict[str, Any]] = None,
    diff_attest: Optional[Dict[str, Any]] = None,
    ruleset: Optional[Dict[str, Any]] = None,
    plan_sha256: Optional[str] = None,
) -> Dict[str, Any]:
    """Build the ``coverage-grid`` record: ``grid.to_dict()`` (schema
    ``harness/schemas/coverage-grid.json``) plus the gate envelope
    (``gate``/``verdict``/``ts``/``cross_ref``/``evidence_prefix_set``).

    ``verdict`` is the plain-dict form of a ``GridReviewVerdict`` (e.g.
    ``dataclasses.asdict(review_grid(...))``) — this module does not import
    ``grid/review.py`` to stay a leaf writer the review pass does not depend
    on back. An unknown ``evidence_prefix_set`` raises ``ValueError`` rather
    than silently falling back to the default, so a caller's typo surfaces
    instead of quietly recording the wrong declared set.

    ``axis_selection`` is an additive, opt-in gate-envelope mark (the
    engine-consumed ``--axes-src`` receipt: ``{"axes": [...], "src_sha256":
    ...}``) — ``None`` (the default) writes nothing, so a caller that never
    passes it gets a byte-identical record to the pre-mark baseline. When
    given, it is set BEFORE the provenance stamp so the digest covers it.

    ``diff_attest`` is likewise an additive, opt-in gate-envelope mark (the
    ``--checklist``-driven diff against a frozen, independently-derived
    feature-risk-checklist — see ``grid/diff_attest.py``) — ``None`` (the
    default) writes nothing (byte-compat). When given, it is set BEFORE the
    provenance stamp so the digest covers it.

    ``ruleset`` is likewise an additive, opt-in gate-envelope mark (the
    ``--rules``-verified ``FrozenRuleset`` identity that granted this grid's
    N/A credit: ``{"ruleset_hash": ..., "rule_count": ...}``) — ``None`` (the
    default) writes nothing (byte-compat). Nothing previously recorded WHICH
    ruleset granted N/A credit, so no one could audit it after the fact; this
    mark makes that auditable. It proves which ruleset was used, NOT that a
    human read the rendered rule table before approving -- that limit is
    unchanged (the anchor-hash chain into an approved plan.md is what proves
    the ruleset was visible at Approve time). Set BEFORE the provenance
    stamp so the digest covers it. Checking this mark against the plan's own
    anchored ruleset is a downstream gate's job, not this writer's.

    ``plan_sha256`` binds the grid to the plan's CONTENT, not just its name:
    ``plan_id`` says which plan this grid claims, this says which VERSION of
    it the grid was built against. Without it a plan revised after the grid
    was emitted keeps a grid describing text that no longer exists, and every
    other arm still reads green. Value is ``plan_approval.plan_hash(plan_dir)``
    — the same digest approval uses, reused rather than redefined so the two
    never disagree about what "the plan changed" means (it strips the mutable
    frontmatter region, so cook's status flip is not a change). Set BEFORE the
    provenance stamp so the digest covers it."""
    if evidence_prefix_set not in EVIDENCE_PREFIX_SETS:
        raise ValueError(
            "build_coverage_grid_record: unknown evidence_prefix_set %r — choose "
            "one of %s" % (evidence_prefix_set, sorted(EVIDENCE_PREFIX_SETS))
        )
    ts = now() if callable(now) else (now or datetime.now(timezone.utc).isoformat())
    record: Dict[str, Any] = dict(grid.to_dict())
    record["gate"] = "grid"
    record["verdict"] = verdict.get("verdict") if isinstance(verdict, dict) else verdict
    record["ts"] = ts
    record["cross_ref"] = CROSS_REF
    record["evidence_prefix_set"] = evidence_prefix_set
    # The per-project extension (HARNESS_GRID_EVIDENCE_PREFIXES) was invisible
    # in the artifact, so the same grid file passed PHANTOM_EVIDENCE where it
    # was emitted and failed anywhere the env was not exported — a verdict
    # nobody could reproduce or even diagnose from the file. Recorded here as
    # CONTEXT, never as authority: the judging path calls evidence_pattern(),
    # which reads the live environment, so an author cannot widen the accepted
    # set by editing their own artifact. Omitted when empty (byte-compat with
    # every artifact emitted before this field existed), and set before the
    # provenance stamp so an after-the-fact edit is visible.
    extra_prefixes = configured_extra_prefixes()
    if extra_prefixes:
        record["evidence_prefixes_extra"] = extra_prefixes
    if isinstance(verdict, dict):
        record["review"] = verdict
    if axis_selection is not None:
        record["axis_selection"] = axis_selection
    if diff_attest is not None:
        record["diff_attest"] = diff_attest
    if ruleset is not None:
        record["ruleset"] = ruleset
    if plan_sha256 is not None:
        record["plan_sha256"] = plan_sha256
    # Provenance mark — binds this artifact to grid_engine emit so the hard
    # presence gate (grid_emit_guard --require) can reject a hand-written /
    # non-engine coverage-grid. Stamp LAST, over the fully-built record.
    record["provenance"] = provenance.stamp(record)
    return record


def write_coverage_grid(
    plan_dir, record: Dict[str, Any], *, fmt: str = "json", phase: Optional[str] = None,
) -> Dict[str, Any]:
    """Write ``record`` through ``stamp_and_write`` (atomic + ``run_seq``) to
    ``plan_dir/artifacts/coverage-grid.<fmt>`` (the macro planner/qa grid,
    ``phase=None`` — byte-identical to the pre-``phase``-parameter shape) or
    ``plan_dir/artifacts/coverage-grid-<phase>.<fmt>`` (an executor per-phase
    micro-grid, ``phase`` being the caller's own phase identifier — the same
    id family ``plan-graph.yaml``'s ``subtasks:`` and ``verification-<phase>
    .json`` already use) when ``phase`` is given. Returns the stamped record.

    The macro grid is the ONE artifact ``grid_emit_guard.find_coverage_grid``
    (and therefore plan approval) reads — a per-phase executor grid must
    NEVER land on that path, or it silently overwrites the grid approval was
    granted against (the observed defect this parameter closes: a fixed
    filename meant a naive "run emit every phase" would have the phase-1
    grid destroy the plan-level grid)."""
    if fmt not in ("json", "yaml"):
        raise ValueError("write_coverage_grid: fmt must be 'json' or 'yaml', got %r" % fmt)
    art_dir = Path(plan_dir) / "artifacts"
    stem = "coverage-grid" if phase is None else "coverage-grid-%s" % phase
    path = art_dir / ("%s.%s" % (stem, fmt))
    art_dir.mkdir(parents=True, exist_ok=True)
    stamped = artifact_io.stamp_and_write(path, record)
    # Remove a stale sibling in the OTHER FORMAT OF THIS SAME STEM ONLY, AFTER
    # a successful write, so a consumer that prefers one extension can't read
    # a superseded verdict for the SAME artifact. Scoped to `stem` (not a
    # hardcoded "coverage-grid") is the fix: writing a per-phase grid in one
    # format must never delete the MACRO grid in the other format — that is a
    # DIFFERENT artifact (the plan-level grid approval was granted against),
    # not a stale sibling of this write.
    sibling = art_dir / ("%s.%s" % (stem, "yaml" if fmt == "json" else "json"))
    if sibling.exists():
        sibling.unlink()
    return stamped
