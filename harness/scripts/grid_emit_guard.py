#!/usr/bin/env python3
"""grid_emit_guard.py — deterministic, filesystem-only check that a grid-mode
run actually produced the ``coverage-grid`` gate artifact.

0-token, 0 model: reads ``plans/<active>/artifacts/`` only. Grid-mode ON and
the artifact is missing is an ADVISORY signal to the calling skill (this
script exits non-zero) — it is NOT a hook block; nothing in ``hook-dispatch``
or ``stage-policy.yaml`` wires this script's exit code into a compliance
gate. Grid-mode OFF and the artifact is missing is the expected, silent case
(exit 0) — ``coverage-grid`` stays optional outside grid mode, consistent
with the consumer-side contract (`code-review`/`test` read it if present,
absent -> silent).

Mirrors the active-plan resolution convention used by ``grid_engine.py emit``
(``artifact_check.resolve_active_plan``) and the CLI shape of sibling
advisory checkers such as ``plan_layout_check.py``.
"""
import argparse
import re
import sys
from pathlib import Path

_ARTIFACT_NAMES = ("coverage-grid.json", "coverage-grid.yaml")


def _never_filled_attestation() -> str:
    """The exact attestation the expander stamps when NO model invoker was wired
    (``grid.expander._STUB_ATTESTATIONS['llm-unavailable']``) — the fingerprint of
    a fill loop that never ran. Read from the engine SSOT so this guard can never
    drift from the string the expander actually writes; a hardcoded fallback keeps
    the guard usable if the import ever breaks (fail-open to the known literal)."""
    try:
        from grid.expander import _STUB_ATTESTATIONS
        return _STUB_ATTESTATIONS["llm-unavailable"]
    except Exception:  # noqa: BLE001 — import must not break a filesystem-only guard
        return ("no LLM invoker wired — returning SKELETON→STUB fallback per "
                "graceful-degradation contract")


def _cell_has_real_content(cell, no_run_sig: str) -> bool:
    """A single cell carries real content iff it is neither SKELETON (built,
    never expanded) nor the no-invoker degradation STUB (attestation matches
    the fingerprint ``_never_filled_attestation`` returns exactly). A STUB
    with a DIFFERENT, real attestation ([JUSTIFIED-THIN] or any other
    human-authored reason) counts as real content — that cell was processed,
    just legitimately thin.

    Delegates to ``grid.types.cell_is_resolved`` so this gate and the
    expansion loop's stop referee cannot drift on what "processed" means —
    they did, and the loop then declared itself done at a state this gate
    refused, with no engine path out. The local branches remain as the
    fail-open fallback for the same reason ``_never_filled_attestation``
    keeps one: an import fault must not break a filesystem-only guard.
    """
    resolution = cell.get("resolution")
    attestation = cell.get("attestation")
    try:
        from grid.types import cell_is_resolved
        return cell_is_resolved(resolution, attestation)
    except Exception:  # noqa: BLE001 — import must not break this guard
        pass
    if resolution == "SKELETON":
        return False
    if resolution == "STUB" and attestation == no_run_sig:
        return False
    return True


def _has_no_real_content(grid_path) -> bool:
    """True iff AT LEAST ONE cell still lacks real content — the fill loop has
    NOT fully run. Replaces an ``all(STUB and exact-attestation)`` predicate
    that two shapes walked straight through: a build->emit grid (every cell
    SKELETON, never matches "STUB") and a 49-empty + 1-real grid (``all()``
    was False, so the whole arm switched off and the one real cell excused
    the other 49). Under this predicate a single resolved cell no longer
    excuses the rest: passing requires EVERY cell to carry real content.
    Deterministic, 0-token: reads the artifact only. Fail-open to False — an
    unreadable / oddly-shaped / cell-less grid never manufactures a block
    (the legacy presence-only pass stands)."""
    try:
        import json
        text = Path(grid_path).read_text(encoding="utf-8")
        if str(grid_path).endswith((".yaml", ".yml")):
            import yaml_io
            data = yaml_io.safe_load(text)
        else:
            data = json.loads(text)
        cells = (data or {}).get("cells")
        if not cells:
            return False
        sig = _never_filled_attestation()
        return any(not _cell_has_real_content(c, sig) for c in cells)
    except Exception:  # noqa: BLE001 — a read/parse failure never fabricates a block
        return False


def _has_zero_cells(grid_path) -> bool:
    """True iff ``grid_path``'s record carries a ``cells`` field that is
    PRESENT but EXPLICITLY EMPTY (``[]``) — a grid describing zero cells at
    all, never produced by a real ``build``/``expand`` (CA always yields at
    least one cell). Distinct from ``_has_no_real_content``, whose own
    ``if not cells: return False`` treats an explicitly-empty list the same
    as a genuinely absent ``cells`` key — collapsing "this grid has zero
    cells" into "no problem found" is what let a forged
    ``{"cells": [], ...}`` record, stamped with nothing more than
    ``grid.provenance.stamp`` (no engine call at all — see the module
    docstring in ``grid/provenance.py``), pass every arm of this gate. A
    genuinely MISSING ``cells`` key is a different, pre-existing shape this
    function does not touch (fail-open to False, matching this module's
    other filesystem-only checks — an unreadable/oddly-shaped artifact never
    manufactures a block here)."""
    try:
        import json
        text = Path(grid_path).read_text(encoding="utf-8")
        if str(grid_path).endswith((".yaml", ".yml")):
            import yaml_io
            data = yaml_io.safe_load(text)
        else:
            data = json.loads(text)
        cells = (data or {}).get("cells")
        return isinstance(cells, list) and len(cells) == 0
    except Exception:  # noqa: BLE001 — a read/parse failure never fabricates a block
        return False


def _provenance_ok(grid_path):
    """Returns a ``(state, detail)`` tuple, ``state`` one of ``"ok"`` /
    ``"tampered"`` / ``"unverifiable"`` — three outcomes, not a bool, so a
    genuine integrity failure (digest mismatch, hand-written artifact) is
    never conflated with an environment failure (the grid package failed to
    import). Both still fail-CLOSED (the caller blocks on either), but only
    ``"tampered"`` is reported to a human as an accusation; ``"unverifiable"``
    says plainly that the gate could not check, not that it caught something.

    - ``"ok"`` — ``grid.provenance.verify`` confirms ``emitted_by`` == engine
      AND ``content_sha256`` matches a recomputation over the artifact's own
      stable content.
    - ``"tampered"`` — the file is readable but fails verification: a
      hand-written artifact, a missing/forged mark, or a post-emit hand-edit
      that broke the digest.
    - ``"unverifiable"`` — ``ImportError``/``ModuleNotFoundError`` while
      importing ``grid.provenance`` itself: the check could not run at all,
      distinct from the check running and finding a problem.

    HONEST LIMITATION: no secret exists in a file-based harness, so this binds
    the artifact to the engine's schema + content integrity, not to an
    unforgeable signature (see grid/provenance.py). It defeats the lazy skip
    and any post-emit hand-edit; a deliberate re-implementation of the engine
    serialization is out of scope, the same posture as the anchor self-auth
    provenance."""
    try:
        import json
        text = Path(grid_path).read_text(encoding="utf-8")
        if str(grid_path).endswith((".yaml", ".yml")):
            import yaml_io
            data = yaml_io.safe_load(text)
        else:
            data = json.loads(text)
        from grid.provenance import verify as _verify
        return ("ok", "") if _verify(data) else ("tampered", "")
    except ImportError as e:
        return ("unverifiable", str(e))
    except Exception:  # noqa: BLE001 — fail-closed: a non-verifiable artifact blocks
        return ("tampered", "")


def _load_grid_record(grid_path) -> dict:
    """Parse a coverage-grid json/yaml file into a plain dict. Raises on a
    read/parse failure — callers decide the fail-open/closed posture."""
    import json
    text = Path(grid_path).read_text(encoding="utf-8")
    if str(grid_path).endswith((".yaml", ".yml")):
        import yaml_io
        return yaml_io.safe_load(text) or {}
    return json.loads(text) or {}


def _is_macro_grid_path(grid_path) -> bool:
    """True iff ``grid_path``'s basename is the macro plan-level artifact
    name (``coverage-grid.json``/``coverage-grid.yaml``) — never a per-phase
    ``coverage-grid-<phase>.<fmt>`` micro-grid. Decided by the FILE PATH, the
    one thing an artifact cannot declare about itself."""
    return Path(grid_path).name in _ARTIFACT_NAMES


def _axis_receipt_required(grid_path, record: dict) -> bool:
    """True iff ``grid_path``'s record MUST carry a valid ``axis_selection``
    receipt: it sits at the MACRO plan-level path (a per-phase micro-grid is
    exempt by PATH — see ``_is_macro_grid_path``). Every macro-path grid
    needs the receipt, full stop — no grandfather by ``provenance.mark_version``
    or any other field.

    PATH IS THE ONLY DISCRIMINATOR, deliberately. An earlier shape also asked
    whether the record was structurally planner-shaped (did it carry a
    ``feature`` axis) — measured, that just relocated the bypass it replaced:
    dropping ``feature`` from ``axes`` and re-stamping recomputes a digest
    that verifies, the grid stops "needing" a receipt, and the gate vanishes
    exactly as it did when the discriminator was the ``agent`` field. A LATER
    shape keyed this off ``record["provenance"]["mark_version"]`` (grandfather
    a mark stamped before the requirement existed) — that relocated the exact
    same bypass a third time: ``provenance`` is itself in
    ``grid.provenance._VOLATILE`` (excluded from the digest ``verify()``
    checks), so ``mark_version`` can be deleted, stringified, or downgraded
    to 1 AFTER a real emit with zero effect on ``verify()`` — the requirement
    silently switches off. Any signal READ FROM the artifact, INCLUDING its
    own provenance block, can be edited by whoever writes the artifact. The
    path cannot: a per-phase grid earns its exemption by being written to
    ``coverage-grid-<phase>.<fmt>``, and the plan-level path is the one the
    approval gate reads. A pre-existing artifact from before this enforcement
    is not exempt either — it fails with a message telling the user to
    re-emit (one command), which costs less than a gate a self-declared field
    can switch off by typing a number."""
    return _is_macro_grid_path(grid_path)


def _axis_selection_ok(grid_path) -> bool:
    """True iff ``grid_path`` does not need an axis-selection receipt at all
    (see ``_axis_receipt_required``), or it does and carries a valid,
    feature-axis-consistent one (the mark ``grid_engine.py emit --axes-src``
    stamps: ``{"axes": [...], "src_sha256": ...}``).

    Inverted from an EXEMPTION to a REQUIREMENT, TWICE. First shape: the
    retired predicate exempted any record whose self-declared ``agent`` field
    was not planner-family, so relabelling ``agent`` -> ``executor`` (or
    deleting the key outright and re-stamping — ``provenance.stamp`` excludes
    ``agent`` from nothing it checks, so the recomputed digest still
    verifies) removed the gate entirely. Second shape (measured after the
    first fix): requiring the receipt only when the grid's own ``axes``
    structurally carried a ``feature`` axis just relocated the same bypass —
    drop ``feature`` from ``axes`` and re-stamp, and the grid "doesn't need"
    a receipt either. Macro-vs-per-phase is now decided by the FILE PATH
    ALONE (see ``_axis_receipt_required``) — the one thing a record cannot
    declare about itself, because it isn't a field IN the record.

    For a grid that DOES need the receipt, ALL of the following must hold:
      - ``axis_selection`` is a dict;
      - ``axis_selection["axes"]`` is a non-empty list;
      - ``axis_selection["src_sha256"]`` is a non-empty string;
      - ``"feature"`` appears in ``axis_selection["axes"]`` — this blocks
        pasting an executor-axis receipt (e.g. ``{"axes": ["step", ...]}``)
        onto a planner grid.

    HONEST LIMITATION: ``src_sha256`` is checked ONLY for being a non-empty
    string — it is never recomputed or compared against any actual
    ``grid-axis-src.json`` file on disk (that file need not even still
    exist by verify time). It is recorded for a later human audit trail, not
    independently verified here; do not read its presence as proof the
    receipt matches a real axis-selection artifact.

    STANDARDIZED POSTURE (matches ``_ruleset_mark_ok``): fails CLOSED
    (returns False) on ANY fault past the point where the caller already
    holds a required-artifact decision to make — including a read/parse
    failure of the artifact itself. This function does NOT independently
    fail open on that read failure (an earlier docstring here claimed it
    did; the code always returned False, which IS fail-closed — the prose
    was simply wrong). Failing closed here costs nothing extra: an earlier
    arm in ``require_emit``'s cascade (provenance / no-real-content) already
    catches a genuinely broken artifact and blocks on it FIRST, so by the
    time this function runs the artifact has already been proven readable
    once; a fresh failure to read it now is not a case worth passing
    silently."""
    try:
        record = _load_grid_record(grid_path)
    except Exception:  # noqa: BLE001 — fails CLOSED (see docstring above);
        # an earlier arm (provenance/no-real-content) already blocks a
        # genuinely broken artifact before this one ever runs.
        return False
    if not _axis_receipt_required(grid_path, record):
        return True
    mark = record.get("axis_selection")
    if not isinstance(mark, dict):
        return False
    axes = mark.get("axes")
    if not isinstance(axes, list) or not axes:
        return False
    src_sha256 = mark.get("src_sha256")
    if not isinstance(src_sha256, str) or not src_sha256:
        return False
    return "feature" in axes


# `.+` (not `[^.]+`): a phase id MAY itself contain a literal dot (e.g.
# "1.2", a common sub-phase numbering scheme) -- `write_coverage_grid`
# accepts any string for `phase` and never validated it against what this
# regex could parse back. `[^.]+` could not match past an embedded dot, so
# `coverage-grid-1.2.json` was invisible to `count_phase_grids` even though
# `grid_engine.py emit --phase 1.2` wrote it successfully -- the close gate
# then demanded a phase grid that re-emitting the SAME phase id could never
# satisfy. `.+` is greedy and anchored at the END (`\.(?:json|yaml)$`), so it
# backtracks to the RIGHTMOST `.json`/`.yaml` suffix regardless of how many
# dots `phase` itself contains.
_PHASE_GRID_RE = re.compile(r"^coverage-grid-(?P<phase>.+)\.(?:json|yaml)$")


def _phase_grid_covers(grid_path) -> bool:
    """True iff a per-phase micro-grid at ``grid_path`` actually counts
    toward cook's per-phase promise -- exactly TWO arms, not the full
    ``require_emit`` cascade:

      - ``_has_zero_cells`` is False (a real build/expand always yields at
        least one cell; an explicitly-empty ``cells: []`` is never one).
      - ``_provenance_ok`` reports ``"ok"`` (genuinely written by
        ``grid_engine.py``, not a zero-effort ``touch(1)`` or a hand-written
        stand-in).

    Deliberately NOT the macro cascade (``_has_no_real_content``,
    axis-selection receipt, ruleset mark, plan binding, freshness): those
    arms are calibrated for the MACRO plan-level artifact and several are
    already PATH-exempt for a per-phase grid by design
    (``_is_macro_grid_path``/``_axis_receipt_required``/
    ``_plan_binding_required``). ``_has_no_real_content`` in particular
    returns True on a real, fully engine-emitted per-phase grid -- measured
    against a genuine ``build_coverage_grid_record`` output -- so running it
    here would block every legitimate per-phase grid this counting gate
    exists to accept. Fails CLOSED on a read/parse fault via
    ``_provenance_ok``'s own posture (``"tampered"``/``"unverifiable"`` both
    read as not-covered here) -- a per-phase grid this gate cannot verify is
    not a per-phase grid it can count as present."""
    if _has_zero_cells(grid_path):
        return False
    state, _detail = _provenance_ok(grid_path)
    return state == "ok"


def count_phase_grids(plan_dir) -> dict:
    """Executor per-phase micro-grids present under ``plan_dir/artifacts/``,
    keyed by phase id (the ``coverage-grid-<phase>.<fmt>`` filename's own
    ``<phase>`` segment) — the mechanically checkable form of cook's
    per-phase grid promise. Presence only, sorted filename scan
    (deterministic); a read/list failure returns ``{}`` rather than raising
    (fail-open, matching this module's other filesystem-only checks)."""
    art = Path(plan_dir) / "artifacts"
    found: dict = {}
    try:
        names = sorted(p.name for p in art.iterdir() if p.is_file())
    except OSError:
        return {}
    for name in names:
        m = _PHASE_GRID_RE.match(name)
        if m:
            found.setdefault(m.group("phase"), art / name)
    return found


def require_phase_grids(plan_dir, expected_phases) -> list:
    """Which of ``expected_phases`` (e.g. ``plan-graph.yaml``'s ``subtasks:``
    keys) have NO executor micro-grid yet under ``artifacts/`` — preserves
    the input order, does not sort or dedupe (a caller passing a dict's keys
    already gets a stable, deduped order for free). A phase whose file
    EXISTS but does not clear ``_phase_grid_covers`` (a zero-byte/garbage
    touch, or a hand-written non-engine record) counts as missing too --
    presence alone is not coverage."""
    present = count_phase_grids(plan_dir)
    return [p for p in expected_phases
            if p not in present or not _phase_grid_covers(present[p])]


def _expected_phases_from_plan_graph(plan_dir):
    """``(phases, error)``: the declared phase ids read from
    ``plan_dir/plan-graph.yaml``'s ``subtasks:`` mapping — that sidecar is
    already the source of truth for the phase graph (never counts files
    under ``phases/``). ``error`` is a short reason string when the sidecar
    is missing/malformed/unimportable; ``phases`` is always ``[]`` in that
    case (never fabricated)."""
    try:
        import plan_graph
    except Exception as e:  # noqa: BLE001 — advisory resolution must not raise
        return [], "cannot import plan_graph (%s)" % e
    graph = plan_graph.parse_phase_graph(plan_dir)
    if graph.get("error"):
        return [], graph["error"]
    return list((graph.get("subtasks") or {}).keys()), None


def require_phase_grids_cli(plan_dir):
    """``(message, exit_code)`` for ``--require-phase-grids`` — the closing
    counterpart to ``--require``'s macro-grid presence gate, meant for cook's
    plan-close step (NEVER plan approval: at approval time no per-phase grid
    can exist yet, so gating approval on this would mint a new circular
    deadlock).

    - grid mode off (``resolve_grid_mode``, the ``grid: false`` opt-out
      included) -> ``(msg, 0)``, skipped.
    - no ``plan-graph.yaml`` / malformed / unimportable -> ``(msg, 0)``: this
      gate is NOT the sidecar-presence gate (``plan_graph.py --require``
      already enforces that elsewhere, mandatory in cook's Phase-DAG
      preflight) — it must never manufacture its own block for a reason that
      belongs to a different door.
    - any declared phase missing its micro-grid -> ``(msg, 2)`` naming every
      missing phase.
    - every declared phase covered -> ``(msg, 0)``."""
    enabled, mode_reason, _evidence = resolve_grid_mode(plan_dir)
    if not enabled:
        return ("grid mode off — %s (ok, --require-phase-grids skipped)" % mode_reason, 0)
    phases, err = _expected_phases_from_plan_graph(plan_dir)
    if err:
        return ("cannot determine declared phases (%s) — sidecar presence is "
                 "enforced by plan_graph.py --require, not this gate; "
                 "--require-phase-grids skipped (ok)" % err, 0)
    missing = require_phase_grids(plan_dir, phases)
    if missing:
        return ("missing executor micro-grid for phase(s): %s — run "
                 "`grid_engine.py emit --phase <id>` for each before closing "
                 "the plan" % ", ".join(missing), 2)
    return ("all %d declared phase(s) carry an executor micro-grid — ok" % len(phases), 0)


def _claims_na_credit(record: dict) -> bool:
    """True iff at least one cell claims ``rule:<id>`` N/A credit (an
    attestation matching the shared ``rule:<id>`` prefix
    ``grid.preregister.parse_na_rule_ref`` recognizes) — determined from the
    CELLS themselves, never a self-declared summary field, so a caller
    cannot suppress this check by omitting one.

    Deliberately does NOT catch an import fault here (same ``grid.X`` import
    style as the rest of this module, e.g. ``_provenance_ok``'s
    ``from grid.provenance import verify``): swallowing it into a bare
    ``return False`` used to make this say "no credit claimed", which makes
    the WHOLE ruleset-mark gate below vanish silently (no credit -> no mark
    needed) whenever the import merely failed to resolve, not because the
    grid genuinely claims none — the same fail-open class blocker 3 closed
    for the grid-mode resolver. The caller (``_ruleset_mark_ok``) lets the
    ``ImportError`` propagate so ``require_emit`` can report it as an
    ENVIRONMENT fault, the same ``unverifiable`` posture ``_provenance_ok``
    already uses."""
    from grid.preregister import parse_na_rule_ref
    for cell in (record or {}).get("cells") or []:
        if isinstance(cell, dict) and parse_na_rule_ref(cell.get("attestation") or "") is not None:
            return True
    return False


def _ruleset_mark_ok(grid_path, plan_dir) -> bool:
    """True iff ``grid_path`` does not claim N/A credit at all, OR it does
    and also carries a ``ruleset`` mark (``{ruleset_hash, rule_count}``)
    recording WHICH frozen ruleset granted it, AND that hash is the one
    actually anchored in ``plan_dir/plan.md``'s own `grid_ruleset_hash:`
    line.

    SECOND LAYER (the shape check alone was not enough): a well-shaped mark
    naming a hash that was never frozen/reviewed anywhere still passed —
    nothing tied the mark back to what a human actually saw at Approve time.
    This closes that: the same anchor line `preregister` appends into the
    plan body (and `plan_approval.plan_hash` covers) is re-derived here via
    ``preregister.extract_ruleset_hash_from_plan`` and compared against the
    mark's own claimed hash.

    A grid claiming credit with no mark at all is unauditable — no one can
    tell after the fact which ruleset (if any) actually justified the N/A.
    STANDARDIZED POSTURE (matches ``_axis_selection_ok``, which reads the
    SAME artifact moments earlier in ``require_emit``'s cascade — the two
    used to disagree on this exact failure mode, one blocking and one
    passing, for no reason either docstring could actually justify): fails
    CLOSED (returns False) on EVERY fault here, including the grid
    artifact's own read/parse. This costs nothing extra in practice — an
    earlier arm (provenance / no-real-content) already reads the same file
    successfully before this one ever runs, so a fresh failure to read it
    now would be a genuinely new, worth-blocking-on condition, never a
    routine one to wave through. ``_claims_na_credit``'s ``ImportError`` is
    let through uncaught (see its own docstring) so ``require_emit`` can
    report that specific ENVIRONMENT fault distinctly, rather than this
    function folding it into the same generic False."""
    try:
        record = _load_grid_record(grid_path)
    except Exception:  # noqa: BLE001 — fails CLOSED (see docstring above);
        # an earlier arm (provenance/no-real-content) already blocks a
        # genuinely broken artifact before this one ever runs.
        return False
    if not _claims_na_credit(record):  # may raise ImportError -- propagates on purpose
        return True
    mark = record.get("ruleset")
    if not (isinstance(mark, dict) and bool(mark.get("ruleset_hash"))
            and isinstance(mark.get("rule_count"), int)):
        return False
    try:
        from grid.preregister import extract_ruleset_hash_from_plan
        plan_text = (Path(plan_dir) / "plan.md").read_text(encoding="utf-8")
    except OSError:
        return False
    anchored = extract_ruleset_hash_from_plan(plan_text)
    return anchored is not None and anchored == mark["ruleset_hash"]


def _plan_binding_required(grid_path) -> bool:
    """True iff ``grid_path``'s record MUST carry a ``plan_id`` binding it to
    THIS plan directory: it sits at the MACRO plan-level path (a per-phase
    micro-grid is exempt by PATH — see ``_is_macro_grid_path``, the same
    discriminator ``_axis_receipt_required`` already uses). An executor grid
    carries ``task_id``, not ``plan_id``, and lives at the per-phase path
    under the current design — never checked here.

    PATH IS THE ONLY DISCRIMINATOR, for the same reason it is the only one
    for the axis-selection receipt above: any field read FROM the record
    (including its own ``plan_id``) is a field whoever writes the artifact
    also controls."""
    return _is_macro_grid_path(grid_path)


def _plan_binding_ok(grid_path, plan_dir) -> bool:
    """True iff ``grid_path`` does not need a plan binding at all (see
    ``_plan_binding_required``), or it does and its own ``plan_id`` field
    equals ``Path(plan_dir).name`` exactly.

    THE OBSERVED BYPASS: a ``coverage-grid.json`` engine-emitted for one plan
    — valid provenance, a valid axis-selection receipt, every cell resolved —
    physically copied into a DIFFERENT plan's ``artifacts/`` directory still
    cleared every arm above, because nothing asked whether the grid's OWN
    ``plan_id`` claim matches the plan directory it now sits in. Mirrors the
    binding ``artifact_check._check_plan_approval`` already does for
    ``plan-approval`` (``rec.get("plan") != plan_dir.name``) — the same
    pattern, the same reason: a real record for plan X does not become valid
    evidence for plan Y just because someone `cp`'d the file.

    MISSING ``plan_id`` FAILS CLOSED, deliberately — a macro-path record with
    no ``plan_id`` field at all is NOT treated as "binding not applicable".
    That distinction (a required check quietly waiving itself when the field
    it reads is simply absent) is the exact shape of every prior bypass this
    module has already closed for the axis-selection receipt: relabel
    ``agent``, drop the ``feature`` axis, delete/downgrade ``mark_version`` —
    each one relocated the same hole by turning a REQUIREMENT into something
    an absent/edited field could switch off. A legitimately emitted macro
    grid always carries ``plan_id`` (``grid.skeleton.build_grid_skeleton``
    raises when a planner-family agent — ``planner``/``qa``/
    ``frankode-planner`` — has none), so requiring it here costs a real emit
    nothing; it only catches a record with the field stripped out.

    HONEST LIMITATION (same register as ``grid/provenance.py``'s module
    docstring and ``_provenance_ok`` above): this defeats the LAZY COPY — the
    observed failure, a grid physically copied between plan directories — not
    a DELIBERATE FORGE. ``plan_id`` is a plain content field covered by the
    provenance digest, so a determined forger can edit it to the target
    plan's own directory name and re-stamp via ``from grid.provenance import
    stamp`` — three lines, no engine call — and the recomputed digest still
    verifies. This binding does not make that unforgeable; it only makes the
    lazy, no-effort copy fail instead of silently passing."""
    if not _plan_binding_required(grid_path):
        return True
    try:
        record = _load_grid_record(grid_path)
    except Exception:  # noqa: BLE001 — fails CLOSED (see docstring above);
        # an earlier arm (provenance/no-real-content) already blocks a
        # genuinely broken artifact before this one ever runs.
        return False
    plan_id = record.get("plan_id")
    return isinstance(plan_id, str) and bool(plan_id) and plan_id == Path(plan_dir).name


def _import_plan_approval():
    """Lazy, for the same reason ``plan_approval`` imports THIS module lazily:
    the two reference each other and a module-scope import either way would
    make whichever loads first import a half-built partner."""
    here = str(Path(__file__).resolve().parent)
    if here not in sys.path:
        sys.path.insert(0, here)
    import plan_approval
    return plan_approval


def _plan_freshness_ok(grid_path, plan_dir):
    """``(ok, detail)`` — whether this grid was built against the plan as it
    reads NOW.

    Every other arm binds to the plan's NAME; a plan revised after emit keeps
    the same name, so a grid describing text that no longer exists passed
    everything. Re-approval does not catch it either: approval re-hashes the
    plan and then asks this guard, which had nothing to compare.

    Scope, stated honestly: applies exactly where ``_plan_binding_required``
    does (the macro, plan-level path). A per-phase grid carries ``task_id``,
    not ``plan_id``, and is not held to this — a phase grid can still go stale
    against a revised phase file, and that gap is open.

    NO grandfather for a missing hash. An exemption keyed on a field read FROM
    the artifact is the bypass this gate has already grown twice; "no hash
    means an older engine, let it through" would be the third, and it is one
    ``del`` away from any author. The repo carries no pre-hash grid for such a
    clause to protect."""
    if not _plan_binding_required(grid_path):
        return True, None
    try:
        record = _load_grid_record(grid_path)
    except Exception:  # noqa: BLE001 — fails CLOSED, as _plan_binding_ok does
        return False, "coverage-grid could not be read"

    claimed = record.get("plan_sha256")
    if not isinstance(claimed, str) or not claimed:
        return False, (
            "coverage-grid carries no `plan_sha256`, so there is no way to tell "
            "whether it describes the plan as it reads now — re-emit it "
            "(`grid_engine.py emit --plan <plan.md>`)")

    try:
        actual = _import_plan_approval().plan_hash(plan_dir)
    except Exception as e:  # noqa: BLE001
        return False, ("cannot hash the plan to check the grid is current: %s" % e)

    if claimed != actual:
        return False, (
            "the plan changed after this coverage-grid was emitted (grid was "
            "built against plan %s, plan is now %s), so the grid is stale and "
            "describes text that no longer exists — re-run "
            "`grid_engine.py emit --plan <plan.md>` against the current plan"
            % (claimed, actual))
    return True, None


def find_coverage_grid(plan_dir) -> "Path | None":
    """The first existing ``coverage-grid.<json|yaml>`` under
    ``plan_dir/artifacts/``, or ``None``."""
    art = Path(plan_dir) / "artifacts"
    for name in _ARTIFACT_NAMES:
        cand = art / name
        if cand.is_file():
            return cand
    return None


# Engine-emitted names only. Deliberately EXCLUDES grid-axis-src.json /
# grid-fill-src.json (agent-written -- an agent can write them BEFORE the
# engine ever runs, so counting them would falsely block an abandoned
# mid-session draft), grid-rules-in.yaml (hand-written), and
# auto-decisions.jsonl (not grid-family at all). Every name here is
# something ONLY `grid_engine.py` writes.
_GRID_EVIDENCE_NAMES = (
    "coverage-grid.json", "coverage-grid.yaml",
    "grid.json",
    "grid-axes-build.json",
    "grid-preregistration.json",
    "grid-verdict.json",
)


def _find_grid_evidence(plan_dir) -> list:
    """Basenames of ``_GRID_EVIDENCE_NAMES`` present under
    ``plan_dir/artifacts/``, sorted. Presence-only -- content is never
    inspected here (that is `find_coverage_grid` + the cascade below's job
    for the two names that matter for quality)."""
    art = Path(plan_dir) / "artifacts"
    try:
        return sorted(name for name in _GRID_EVIDENCE_NAMES if (art / name).is_file())
    except OSError:
        return []


def resolve_grid_mode(plan_dir):
    """The ONE activation decision every door (this module's ``require_emit``,
    ``plan_approval.write_approval``, ``grid_flag_carry.resolve_grid_carry``)
    must read from — a prior split implementation let approval and the CLI
    disagree. Returns ``(enabled: bool, reason: str, evidence: list[str])``;
    never raises.

    Four frontmatter states, not two:
      - ``grid: true``  -> enabled; ``evidence`` is always ``[]`` (the
        declaration alone decides -- irrelevant to WHY this is enabled).
      - ``grid: false`` -> disabled, ALWAYS, even with grid files on disk --
        an explicit opt-out must not trap a plan carrying leftovers from an
        earlier round.
      - key absent, or present but not the boolean True/False (``is True``/
        ``is False`` stay strict -- the string ``"true"`` does not enable) ->
        inferred from ``_GRID_EVIDENCE_NAMES`` on disk: enabled iff any
        exist, and ``evidence`` names exactly which ones.
      - frontmatter unparseable -> same evidence-inference path (a corrupt
        declaration must not suppress a real grid on disk); ``reason`` always
        names the parse error so a disabled-branch caller can still warn.
    """
    plan_dir = Path(plan_dir)
    evidence = _find_grid_evidence(plan_dir)
    try:
        import frontmatter_parser
        parsed = frontmatter_parser.parse_file(plan_dir / "plan.md")
    except Exception as e:  # noqa: BLE001 — this function must never raise
        parsed = {"ok": False, "error": str(e)}

    if not parsed.get("ok"):
        err = parsed.get("error") or "unknown parse error"
        if evidence:
            return (True,
                    "plan.md frontmatter is unparseable (%s), AND grid "
                    "evidence was found on disk (%s) — treating grid mode as "
                    "required so the evidence is not silently ignored"
                    % (err, ", ".join(evidence)), evidence)
        return (False,
                "plan.md frontmatter is unparseable (%s) — grid mode "
                "presumed off, but the declaration could not actually be "
                "read" % err, [])

    fm = parsed.get("frontmatter") or {}
    grid_key = fm.get("grid")
    if grid_key is True:
        return (True, "explicit grid: true", [])
    if grid_key is False:
        return (False,
                "explicit grid: false (an opt-out; wins over any evidence "
                "on disk)", [])

    if evidence:
        return (True,
                "no grid: key declared, but grid evidence found on disk "
                "(%s) — inferred from grid files on disk"
                % ", ".join(evidence), evidence)
    return (False, "no grid: key and no grid evidence on disk", [])


def require_emit(plan_dir):
    """Hard presence gate (parity ``plan_graph.py --require``). Reads grid mode
    via ``resolve_grid_mode`` ITSELF — never trusts a caller-passed ``--grid``
    — and returns ``(message, exit_code)``:

    - grid disabled -> ``(msg, 0)`` — coverage-grid stays optional.
    - grid enabled by INFERENCE (no working `grid:` declaration, evidence
      found on disk) -> ``(msg, 2)`` — blocks immediately naming the files,
      without running the quality cascade below: a plan that never opted in
      gets a prompt to declare intent, not a verdict on evidence it never
      asked to be checked.
    - grid enabled by explicit ``grid: true`` + artifact present -> ``(msg, 0)``.
    - grid enabled by explicit ``grid: true`` + artifact MISSING -> ``(msg, 2)``.

    The coverage-grid VERDICT is never read here, so a `reject` verdict never
    blocks (that stays advisory). TWO shapes are a hard fail under an explicit
    declaration: "grid declared but the artifact was never emitted" (missing),
    and "grid declared but the fill loop has not FULLY run" (present but AT
    LEAST ONE cell is still SKELETON or the no-invoker degradation STUB). The
    second is the opt-in contract: using ``--grid`` is the author's choice, but
    once it is on EVERY cell must be resolved — a single real cell does not
    excuse the rest, and an all-SKELETON build->emit grid is caught the same
    way. A thin grid whose cells carry real JUSTIFIED-THIN reasons passes (that
    is a resolved grid); only an unresolved cell is caught.

    A macro-path grid must also be BOUND to this plan — its own ``plan_id``
    field must equal ``plan_dir.name`` (``_plan_binding_ok``) — so an
    otherwise-valid, otherwise-fully-resolved grid physically copied from a
    DIFFERENT plan's ``artifacts/`` directory does not clear this gate. See
    ``_plan_binding_ok`` for the honest limitation (defeats the lazy copy,
    not a deliberate forge)."""
    enabled, mode_reason, evidence = resolve_grid_mode(plan_dir)
    if not enabled:
        return ("grid mode off — %s (ok)" % mode_reason, 0)

    if evidence:
        if "unparseable" in mode_reason:
            return ("%s. Fix the frontmatter YAML, then either add `grid: "
                     "true` (if grid mode is intended) or `grid: false` (if "
                     "these files are leftovers from an earlier round and "
                     "grid mode is genuinely off)." % mode_reason, 2)
        if "grid-preregistration.json" in evidence:
            # A frozen ruleset is not a leftover from an abandoned round —
            # it is a REAL, deliberate pre-approval step (`preregister`).
            # Offering `grid: false` here as an equally-valid fix would be
            # actively wrong: `grid: false` ALWAYS wins over evidence on
            # disk (resolve_grid_mode's own opt-out contract), so following
            # that advice would silently discard a ruleset someone froze on
            # purpose and switch this whole gate off for a plan that did
            # everything right. Only `grid: true` is offered.
            return (
                "grid artifacts found in %s/artifacts/ (%s), including a "
                "frozen ruleset (grid-preregistration.json) — this plan has "
                "already run the pre-approval freeze, a deliberate grid-mode "
                "step, so plan.md is missing its `grid: true` declaration. "
                "Add `grid: true` to plan.md frontmatter (never `grid: "
                "false` here — that would discard the frozen ruleset and "
                "silently switch this gate off)."
                % (plan_dir, ", ".join(evidence)), 2)
        return (
            "grid artifacts found in %s/artifacts/ (%s) but plan.md "
            "declares no `grid:` key — this looks like grid mode and the "
            "declaration is missing. Either add `grid: true` to plan.md "
            "frontmatter (then the coverage-grid gate applies), or add "
            "`grid: false` if these files are leftovers from an earlier "
            "round and grid mode is genuinely off."
            % (plan_dir, ", ".join(evidence)), 2)

    found = find_coverage_grid(plan_dir)
    if found is not None:
        if _has_zero_cells(found):
            return ("coverage-grid present but its `cells` list is EMPTY — a "
                    "real build/expand always yields at least one cell; a "
                    "zero-cell record describes no coverage at all and was "
                    "not produced by the engine's normal CA path. Re-emit "
                    "via `grid_engine.py build`/`expand`, or drop `grid: "
                    "true` if grid mode was not intended", 2)
        if _has_no_real_content(found):
            return ("coverage-grid present but the fill loop has NOT fully run — "
                    "at least one cell is still SKELETON (built, never expanded) "
                    "or the no-invoker degradation STUB (coverage 0.0 for that "
                    "cell). --grid is opt-in, but once on EVERY cell must be "
                    "resolved: fill the remaining cells (spawn @grid-filler + "
                    "grid_fill_replay, or grid_engine.py expand with an invoker) "
                    "OR attest each thin cell [JUSTIFIED-THIN] with a reason, "
                    "then re-emit", 2)
        prov_state, prov_detail = _provenance_ok(found)
        if prov_state == "unverifiable":
            return ("cannot verify coverage-grid provenance — the grid package "
                    "failed to import (%s). This is an ENVIRONMENT fault, NOT a "
                    "tampered artifact. The package needs harness/scripts/ on "
                    "sys.path and nothing else; check that harness/scripts/grid/ "
                    "is intact." % prov_detail, 2)
        if prov_state == "tampered":
            return ("coverage-grid present but carries NO valid grid_engine "
                    "provenance — it was hand-written or tampered, not produced by "
                    "`grid_engine.py emit`. --grid is opt-in, but once declared the "
                    "grid MUST run through the engine (build → review → emit); a "
                    "hand-built artifact does not clear the gate. Run the engine to "
                    "re-emit (its invariant/confab/verdict pass is the point), or "
                    "drop `grid: true` if grid mode was not intended", 2)
        if not _axis_selection_ok(found):
            return ("coverage-grid present but the macro planner grid carries NO valid "
                    "axis-selection receipt (axis_selection mark absent/empty, or its axes "
                    "do not include the grid's feature axis). Run @grid-axis-selector "
                    "(subagent_type hs:grid-axis-selector) to produce grid-axis-src.json, "
                    "then re-emit with `grid_engine.py emit --axes-src <grid-axis-src.json>` "
                    "so the receipt is stamped; or drop `grid: true`", 2)
        try:
            ruleset_ok = _ruleset_mark_ok(found, plan_dir)
        except ImportError as e:
            return ("cannot verify the coverage-grid ruleset mark — the grid "
                     "package failed to import (%s). This is an ENVIRONMENT "
                     "fault, NOT a forged mark." % e, 2)
        if not ruleset_ok:
            return ("coverage-grid present but at least one cell claims `rule:<id>` "
                    "N/A credit with a `ruleset` mark that is missing, malformed, or "
                    "names a ruleset hash never anchored (or anchoring a DIFFERENT "
                    "hash) in this plan's own plan.md `grid_ruleset_hash:` line — "
                    "unauditable. Re-emit via `grid_engine.py emit --rules "
                    "<grid-preregistration.json> --plan <plan.md>` so the mark matches "
                    "a ruleset actually frozen into this plan, or drop the `rule:<id>` "
                    "reference if the credit was not actually earned", 2)
        if not _plan_binding_ok(found, plan_dir):
            try:
                claimed = _load_grid_record(found).get("plan_id")
            except Exception:  # noqa: BLE001 — message-building only; the read
                # already succeeded once earlier in this cascade, so this is
                # belt-and-suspenders, never the reason the block itself fires.
                claimed = None
            return ("coverage-grid present but its `plan_id` (%r) does not match "
                    "the active plan directory (%r) — this grid was emitted for a "
                    "DIFFERENT plan (or its `plan_id` is missing entirely) and was "
                    "likely copied between plan directories. Re-emit for THIS plan: "
                    "`grid_engine.py build/expand --plan-id %s ...`, or move this "
                    "artifact back to the plan it actually describes"
                    % (claimed, Path(plan_dir).name, Path(plan_dir).name), 2)
        fresh, why = _plan_freshness_ok(found, plan_dir)
        if not fresh:
            return ("coverage-grid present but not current: %s" % why, 2)
        return ("present (%s) — ok" % found.name, 0)
    return ("missing coverage-grid but plan declares grid: true — emit it "
            "before proceeding (hs:plan Step 6 / cook grid step: "
            "grid_engine.py emit)", 2)


def check_emit(plan_dir, grid_mode: bool):
    """Return ``(message, ok)`` for ``plan_dir`` under grid-mode ``grid_mode``.

    - artifact present -> always ``ok`` (grid-mode ON or OFF).
    - artifact missing, grid-mode ON -> NOT ok, ``"missing (grid-mode: must emit)"``
      (advisory signal to the calling skill, never a hook block).
    - artifact missing, grid-mode OFF -> ``ok``, ``"absent (ok)"`` (silent —
      coverage-grid stays optional outside grid mode)."""
    found = find_coverage_grid(plan_dir)
    if found is not None:
        return ("present (%s) — ok" % found.name, True)
    if grid_mode:
        return ("missing (grid-mode: must emit)", False)
    return ("absent (ok)", True)


def _resolve_plan(root: str, explicit: str):
    if explicit:
        return Path(explicit)
    try:
        import artifact_check
        d = artifact_check.resolve_active_plan(root)
        return Path(d) if d else None
    except Exception:  # noqa: BLE001 — advisory resolution must not raise
        return None


class _UsageParser(argparse.ArgumentParser):
    """Exit 64 (EX_USAGE) on a CLI syntax error so an automated caller can tell
    a real gate block (exit 2) from a malformed invocation."""

    def error(self, message):
        self.print_usage(sys.stderr)
        sys.stderr.write("%s: error: %s\n" % (self.prog, message))
        raise SystemExit(64)


def main(argv=None) -> int:
    ap = _UsageParser(
        description="Deterministic check: does plans/<active>/artifacts/ "
                     "carry a coverage-grid.<json|yaml> artifact? Grid-mode "
                     "ON and missing is an ADVISORY signal to the calling "
                     "skill (non-zero exit here), never a hook block. "
                     "Grid-mode OFF and missing is expected and silent "
                     "(exit 0).")
    ap.add_argument("plan_dir", nargs="?", default=None,
                     help="plan dir (positional, parity plan_graph.py)")
    ap.add_argument("--plan", default=None, help="plan dir (default: active "
                     "plan; wins over the positional when both are given and "
                     "agree — a disagreement between the two is a usage error)")
    ap.add_argument("--root", default=".", help="repo root for active-plan resolve")
    ap.add_argument("--grid", dest="grid_mode", action="store_true", default=False,
                     help="grid-mode is ON for this run (the calling plan/cook "
                          "invocation passed --grid)")
    ap.add_argument("--require", dest="require", action="store_true", default=False,
                     help="HARD presence gate (parity plan_graph.py --require): "
                          "self-reads grid: true from plan.md frontmatter and "
                          "exits 2 when grid is declared but the coverage-grid "
                          "artifact is missing (a STOP). Presence-only — the "
                          "verdict is never read.")
    ap.add_argument("--require-phase-grids", dest="require_phase_grids",
                     action="store_true", default=False,
                     help="HARD counting gate for cook's per-phase micro-grid "
                          "promise: every phase declared in plan-graph.yaml's "
                          "subtasks: must carry a coverage-grid-<phase>.<fmt> "
                          "artifact. Meant for cook's plan-close step, NEVER "
                          "plan approval (no per-phase grid can exist yet at "
                          "approval time). Respects the same grid: false "
                          "opt-out as --require (resolve_grid_mode).")
    args = ap.parse_args(argv)

    explicit_plan = args.plan
    if args.plan_dir is not None:
        if explicit_plan is not None and args.plan_dir != explicit_plan:
            ap.error("conflicting plan dir: positional %r != --plan %r — pass "
                      "one, or make them match" % (args.plan_dir, explicit_plan))
        if explicit_plan is None:
            explicit_plan = args.plan_dir

    plan_dir = _resolve_plan(args.root, explicit_plan)
    if plan_dir is None:
        sys.stderr.write("grid-emit-guard: no active plan to check\n")
        if args.require or args.require_phase_grids:
            # A HARD gate cannot silently pass just because nothing
            # resolved (wrong cwd, a resolver fault, no active plan at
            # --root): that is indistinguishable from "grid mode off" to
            # anything reading only the exit code, so a wrong cwd used to
            # look identical to a clean pass. Refuse and name the way out.
            sys.stderr.write(
                "grid-emit-guard: cannot evaluate a HARD gate (--require%s) "
                "with no active plan resolved -- pass --plan <path>, set "
                "HARNESS_ACTIVE_PLAN, or ensure a plans/*/plan.md with "
                "`status: in_progress` exists under --root %r\n"
                % ("-phase-grids" if args.require_phase_grids else "", args.root))
            return 2
        return 1 if args.grid_mode else 0

    if (args.require or args.require_phase_grids) and not (plan_dir / "plan.md").is_file():
        # Same HARD-gate posture as the `plan_dir is None` branch above, for
        # the one path it cannot reach: an EXPLICIT --plan is never None (see
        # _resolve_plan), so a nonexistent/typo'd/wrong-cwd-relative explicit
        # path used to fall through resolve_grid_mode's "unparseable ->
        # grid mode presumed off" branch and read as a clean pass. A HARD
        # gate cannot evaluate a plan it cannot find plan.md for.
        sys.stderr.write(
            "grid-emit-guard: cannot evaluate a HARD gate (--require%s) -- "
            "%r has no plan.md (wrong path, a typo, or the plan dir does not "
            "exist)\n"
            % ("-phase-grids" if args.require_phase_grids else "", str(plan_dir)))
        return 2

    if args.require:
        message, code = require_emit(plan_dir)
        sys.stderr.write("grid-emit-guard (--require): %s — %s\n" % (plan_dir, message))
        return code

    if args.require_phase_grids:
        message, code = require_phase_grids_cli(plan_dir)
        sys.stderr.write("grid-emit-guard (--require-phase-grids): %s — %s\n" % (plan_dir, message))
        return code

    message, ok = check_emit(plan_dir, args.grid_mode)
    sys.stderr.write("grid-emit-guard: %s — %s\n" % (plan_dir, message))
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
