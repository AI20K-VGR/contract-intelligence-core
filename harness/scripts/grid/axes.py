"""Grid axis schema for planner (macro), executor (micro), and qa (review).

Planner axes span the territory a plan must cover when turning a brief into a
grid: ``feature x layer x lifecycle x risk_class x stakeholder``. Executor
axes span a single implementation step's failure surface:
``step x precondition x side_effect x failure_mode x rollback x
verification`` [ASSUMED — no direct TS anchor for the executor axis set,
ported from the integration spec's executor section].

Axis values are parametric: ``build_planner_axes``/``build_executor_axes``
raise when their required seed list (``features``/``steps``) is empty — axis
values must come from the plan artifact, never be hand-typed, or the grid
would enumerate a meaningless cell space. They also raise on a DUPLICATE
value within one axis (fail-loud, never a silent dedup): the escalate glue
in ``skeleton.py`` (``cells_to_rows``) inverts a cell's coordinate back to a
value-index via ``axis.values.index(...)``, which is non-injective on a
duplicate — a repeated value would seed ``ca.seeded_extend``/``ca.infer_max_t``
from a corrupted row.

The axis *universe* (default value lists + label + ordered_by, per axis) is
no longer a Python literal here — it lives in the self-documenting
``harness/data/grid-axes.yaml`` SSOT, loaded the same way ``density.py``
loads ``grid-density-tier.yaml``: cached on the default path, bypassed on an
explicit path (fixtures), fail-closed (``GridAxisConfigError``) on an unknown
axis or missing file. ``harness/data/grid-strength.yaml`` is a second,
PARALLEL config file (breadth knobs — the covering-array strength ladder and
absolute row guardrail, read via ``t_for_strength``/``guardrail_rows``)
through ``strength_config()``.

This module deliberately does NOT import ``skeleton`` — ``skeleton.py``'s
CA build (``build_grid_skeleton``) is the only downstream consumer of the
axis lists this module produces, and the dependency stays one-way (this
module only depends on the shared types module).
"""
import copy
from pathlib import Path
from typing import Dict, List, Optional

import yaml_io

from .types import GridAxis

_AXES_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "grid-axes.yaml"
_STRENGTH_DATA = Path(__file__).resolve().parent.parent.parent / "data" / "grid-strength.yaml"

_AXES_TABLE = None
_STRENGTH_TABLE = None


class GridAxisConfigError(Exception):
    """axis/key/file absent from the frozen SSOT — fail closed, never a
    default value list (mirrors ``density.UnknownDensityTierError``)."""


def _load_axes_universe(path=None):
    """Return the ``{planner_axes, executor_axes, constraint_rules, ...}``
    doc. Cached when reading the default SSOT; a custom path (tests) bypasses
    the cache so a fixture can't poison the shared table."""
    global _AXES_TABLE
    if path is None and _AXES_TABLE is not None:
        return _AXES_TABLE
    src = Path(path) if path else _AXES_DATA
    try:
        doc = yaml_io.safe_load(src.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise GridAxisConfigError("grid-axes.yaml unreadable: %s" % exc) from exc
    if "planner_axes" not in doc or "executor_axes" not in doc:
        raise GridAxisConfigError("grid-axes.yaml missing planner_axes/executor_axes")
    if path is None:
        _AXES_TABLE = doc
    return doc


def _load_strength(path=None):
    """Return the strength (breadth) config doc. Same cache/bypass contract
    as ``_load_axes_universe``."""
    global _STRENGTH_TABLE
    if path is None and _STRENGTH_TABLE is not None:
        return _STRENGTH_TABLE
    src = Path(path) if path else _STRENGTH_DATA
    try:
        doc = yaml_io.safe_load(src.read_text(encoding="utf-8")) or {}
    except OSError as exc:
        raise GridAxisConfigError("grid-strength.yaml unreadable: %s" % exc) from exc
    if path is None:
        _STRENGTH_TABLE = doc
    return doc


def _axis_node(section, axis_id):
    """Look up one axis node (``label``/``ordered_by``/``values``) inside a
    section (``planner_axes``/``executor_axes``). Raises
    ``GridAxisConfigError`` on an unknown axis id — never falls back."""
    doc = _load_axes_universe()
    group = doc.get(section) or {}
    if axis_id not in group:
        raise GridAxisConfigError("unknown axis %r in %s" % (axis_id, section))
    return group[axis_id]


def _default_values(section, axis_id):
    """Return the default value list (insertion order preserved) for an axis
    that carries a ``values`` mapping — empty for a ``seeded_from_plan`` axis
    (``feature``/``step``)."""
    node = _axis_node(section, axis_id)
    values = node.get("values")
    return list(values) if values else []


DEFAULT_LAYERS = _default_values("planner_axes", "layer")
DEFAULT_LIFECYCLE = _default_values("planner_axes", "lifecycle")
DEFAULT_RISK_CLASSES = _default_values("planner_axes", "risk_class")
DEFAULT_STAKEHOLDERS = _default_values("planner_axes", "stakeholder")

PLANNER_AXIS_IDS = tuple(_load_axes_universe()["planner_axes"])

# Executor micro-axis defaults — no plan/task input names one, so a
# reasonable spanning set lives in grid-axes.yaml (module-local via the
# loader above, not hand-typed per call site).
DEFAULT_PRECONDITIONS = _default_values("executor_axes", "precondition")
DEFAULT_SIDE_EFFECTS = _default_values("executor_axes", "side_effect")
DEFAULT_FAILURE_MODES = _default_values("executor_axes", "failure_mode")
DEFAULT_ROLLBACKS = _default_values("executor_axes", "rollback")
DEFAULT_VERIFICATIONS = _default_values("executor_axes", "verification")

EXECUTOR_AXIS_IDS = tuple(_load_axes_universe()["executor_axes"])


def strength_config(path=None):
    """Return the strength (breadth) config as a plain dict —
    ``guardrail_rows``/``strength_ladder``/``boost_axes``/``na_ratio_bell``/
    ``strong_tier_keywords`` — for the costing/skeleton/loop/expander modules
    to read instead of hardcoding. Defensive-copies every list/dict so a caller mutating the
    return can't corrupt the shared table (mirror ``density.py``)."""
    doc = _load_strength(path)
    return {
        "guardrail_rows": doc["guardrail_rows"],
        "strength_ladder": copy.deepcopy(doc["strength_ladder"]),
        "boost_axes": list(doc.get("boost_axes") or []),
        "na_ratio_bell": doc["na_ratio_bell"],
        "na_ratio_refit": doc["na_ratio_refit"],
        "strong_tier_keywords": list(doc.get("strong_tier_keywords") or []),
    }


def guardrail_rows(path=None):
    """Return the absolute row-count guardrail (shipped 200) that
    `costing.py` and `skeleton.py` gate against. Thin wrapper over
    ``_load_strength`` — honors the same path-override (test-bypass) contract
    as ``strength_config``/``density_policy(density_tier, path=)``."""
    return _load_strength(path)["guardrail_rows"]


def t_for_strength(level, path=None):
    """Map a strength-ladder level key (e.g. ``"t2"``, ``"t3"``) to its
    integer CA strength. Raises ``GridAxisConfigError`` on an unknown level —
    fail-closed, never a guessed default."""
    ladder = _load_strength(path)["strength_ladder"]
    if level not in ladder:
        raise GridAxisConfigError("unknown strength ladder level %r" % level)
    return ladder[level]["strength"]


def _reject_duplicate_values(axis_id: str, values: List[str]) -> None:
    """Fail loud (never silently dedup) when one axis carries a duplicate
    value: the escalate glue in ``skeleton.cells_to_rows`` inverts a
    coordinate to a value-index via ``.index()``, which silently returns the
    FIRST match on a duplicate and corrupts the CA row it feeds to
    ``ca.seeded_extend``/``ca.infer_max_t``."""
    seen = set()
    dupes: List[str] = []
    for v in values:
        if v in seen and v not in dupes:
            dupes.append(v)
        seen.add(v)
    if dupes:
        raise ValueError(
            f"axis '{axis_id}' has duplicate value(s) {sorted(dupes)!r} — "
            "axis values must be unique"
        )


def _axis_values(inputs: Dict, key: str, default: List[str]) -> Optional[List[str]]:
    """An ABSENT key falls back to the canned ``default``; an EXPLICIT empty
    list DROPS the axis (returns ``None``). The old ``inputs.get(key) or
    default`` fallback treated Python's falsy-empty-list the same as a
    missing key, so a deliberate "this axis is meaningless for my project"
    silently became the 5 canned defaults instead of vanishing."""
    if key not in inputs:
        return list(default)
    values = inputs[key]
    return list(values) if values else None


_PLANNER_INPUT_KEYS = (
    "features", "layers", "lifecycle", "risk_classes", "stakeholders")
_EXECUTOR_INPUT_KEYS = (
    "steps", "preconditions", "side_effects", "failure_modes", "rollbacks",
    "verifications")


def _reject_unknown_input_keys(who: str, inputs: Dict, accepted) -> None:
    """Refuse an ``inputs`` key that is not an axis seed.

    Every key here is plural while the matching axis id (and the matching CLI
    flag, ``--feature``) is singular, so the singular spelling is the natural
    guess — and it used to be dropped in silence. The caller then met "at
    least one feature must be supplied (axis values must come from plan, not
    hand-typed)", which names the wrong mistake: they DID supply features.
    Refuse the key instead, name the near-miss when there is one, and list
    the accepted set, since nothing else does."""
    unknown = [k for k in inputs if k not in accepted]
    if not unknown:
        return
    hints = []
    for key in unknown:
        near = [a for a in accepted
                if a == key + "s" or a.replace("_", "") == key.replace("_", "") + "s"]
        if near:
            hints.append("%r -> did you mean %r?" % (key, near[0]))
        else:
            hints.append(repr(key))
    raise ValueError(
        "%s: unrecognized input key(s): %s. Accepted keys: %s."
        % (who, ", ".join(hints), ", ".join(accepted)))


def build_planner_axes(inputs: Optional[Dict] = None) -> List[GridAxis]:
    """Build the planner macro-axes: always ``feature`` plus whichever of
    ``layer``/``lifecycle``/``risk_class``/``stakeholder`` were not
    explicitly dropped (see ``_axis_values``). Raises ``ValueError`` if
    ``features`` is empty — the feature axis is never droppable, axis
    values must come from plan section 3, not be hand-typed — or if any
    surviving axis carries a duplicate value."""
    inputs = inputs or {}
    _reject_unknown_input_keys("build_planner_axes", inputs, _PLANNER_INPUT_KEYS)
    features = [f for f in (inputs.get("features") or []) if f]
    if not features:
        raise ValueError(
            "build_planner_axes: at least one feature must be supplied "
            "(axis values must come from plan, not hand-typed)."
        )
    _reject_duplicate_values("feature", features)

    optional_axes = (
        ("layer", DEFAULT_LAYERS),
        ("lifecycle", DEFAULT_LIFECYCLE),
        ("risk_class", DEFAULT_RISK_CLASSES),
        ("stakeholder", DEFAULT_STAKEHOLDERS),
    )
    # Callers spell the ``inputs`` keys plural ("layers", "risk_classes",
    # "stakeholders") while the axis id stays singular ("layer",
    # "risk_class", "stakeholder") — mirrors the pre-existing key mapping.
    input_keys = {
        "layer": "layers",
        "lifecycle": "lifecycle",
        "risk_class": "risk_classes",
        "stakeholder": "stakeholders",
    }

    universe = _load_axes_universe()["planner_axes"]
    axes_out = [
        GridAxis(
            id="feature",
            label=universe["feature"]["label"],
            values=list(features),
            ordered_by=universe["feature"]["ordered_by"],
        ),
    ]
    for axis_id, default in optional_axes:
        values = _axis_values(inputs, input_keys[axis_id], default)
        if values is None:
            continue
        _reject_duplicate_values(axis_id, values)
        axes_out.append(
            GridAxis(
                id=axis_id,
                label=universe[axis_id]["label"],
                values=list(values),
                ordered_by=universe[axis_id]["ordered_by"],
            )
        )
    return axes_out


def build_executor_axes(inputs: Optional[Dict] = None) -> List[GridAxis]:
    """Build the 6 executor micro-axes. Raises ``ValueError`` if ``steps`` is
    empty, symmetric with the planner's fail-closed contract — or if any
    axis carries a duplicate value."""
    inputs = inputs or {}
    _reject_unknown_input_keys("build_executor_axes", inputs, _EXECUTOR_INPUT_KEYS)
    steps = [s for s in (inputs.get("steps") or []) if s]
    if not steps:
        raise ValueError(
            "build_executor_axes: at least one step must be supplied "
            "(axis values must come from plan, not hand-typed)."
        )
    _reject_duplicate_values("step", steps)

    # The 5 optional executor axes go through _axis_values so an EXPLICIT
    # empty list ("this axis is meaningless for my project") drops the axis
    # instead of silently becoming the canned default — the exact
    # absent-vs-explicitly-empty distinction _axis_values was written to fix
    # on the planner side (build_planner_axes above); this builder used the
    # old `inputs.get(key) or default` shape, which cannot tell the two
    # apart.
    optional_axes = (
        ("precondition", "preconditions", DEFAULT_PRECONDITIONS),
        ("side_effect", "side_effects", DEFAULT_SIDE_EFFECTS),
        ("failure_mode", "failure_modes", DEFAULT_FAILURE_MODES),
        ("rollback", "rollbacks", DEFAULT_ROLLBACKS),
        ("verification", "verifications", DEFAULT_VERIFICATIONS),
    )

    universe = _load_axes_universe()["executor_axes"]
    axes_out = [
        GridAxis(
            id="step",
            label=universe["step"]["label"],
            values=list(steps),
            ordered_by=universe["step"]["ordered_by"],
        ),
    ]
    for axis_id, input_key, default in optional_axes:
        values = _axis_values(inputs, input_key, default)
        if values is None:
            continue
        _reject_duplicate_values(axis_id, values)
        axes_out.append(
            GridAxis(
                id=axis_id,
                label=universe[axis_id]["label"],
                values=list(values),
                ordered_by=universe[axis_id]["ordered_by"],
            )
        )
    return axes_out


def build_qa_axes(inputs: Optional[Dict] = None) -> List[GridAxis]:
    """QA review reuses the planner's 5-axis schema over the plan artifact —
    thin wrapper, no duplicated logic."""
    return build_planner_axes(inputs)
