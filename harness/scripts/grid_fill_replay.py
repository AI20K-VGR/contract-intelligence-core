"""grid_fill_replay.py — a replay ``LlmInvoker`` for the grid depth-expander
seam (``harness/scripts/grid/expander.py:111``: ``LlmInvoker =
Callable[[LlmInvokerContext], ExpanderLlmResponse]``).

Ship a default filler WITHOUT writing a new model client: a `@grid-filler`
subagent reads a skeleton grid, writes ONE JSON file of raw
per-cell content, and this module replays that file's entries back through
the SAME seam every other invoker uses. It grants no trust of its own —
``expand_cell`` runs the exact anti-confab validation
(``expander.py:225-274``) on whatever ``invoke()`` returns here, exactly as
it would on any other invoker's raw response: evidence-missing still
degrades HIGH to STUB, attestation-missing still degrades STUB/MISSING/N-A,
and a wrong-prefix evidence entry still trips ``PHANTOM_EVIDENCE`` in the
downstream confab pass. The model only produces raw text; it is NEVER
trusted blindly.

Source file contract (produced by ``@grid-filler`` or any other writer that
honors the same shape) — a JSON ARRAY of per-cell entries:

    [
      {"coordinates": {"feature": "checkout"}, "resolution": "HIGH",
       "content": "...", "evidence": ["src/x.py:12"], "tokens_used": 120},
      {"coordinates": {"feature": "refunds"}, "resolution": "STUB",
       "attestation": "cannot ground refunds in the provided skeleton"}
    ]

A cell's ``coordinates`` dict is matched by VALUE — key order never
matters, in the source file or in the grid itself. A cell absent from the
array degrades to STUB via ``expand_cell``'s own unknown-resolution path
(this module never raises and never invents a resolution for a cell it
was not told about).

Source path resolution: ``HARNESS_GRID_FILL_SRC`` env wins outright;
otherwise falls back to the active plan's own
``artifacts/grid-fill-src.json``, resolved the exact same way
``grid_engine.py emit --root`` resolves the active plan
(``artifact_check.resolve_active_plan``) — never a bespoke lookup.

``--validate`` CLI (gate-1, in front of ``expand_cell``'s gate-2): a
malformed / not-a-list / typo'd-field source file collapses silently to
all-STUB through ``invoke()`` above — same exit code, zero diagnostics,
indistinguishable from an honest all-STUB run. ``python3
grid_fill_replay.py --validate --grid <grid.json> [--src <fill.json>]``
closes that gap as a SEPARATE, read-only path: a hard structural break
(missing file / malformed JSON / non-array top level) exits non-zero with
a reason on stderr; a structurally sound file always exits 0 with a
one-line ``entries=/matched=/orphan=/unfilled=/will_degrade=`` coverage
summary. It never runs ``expand_cell`` itself — ``will_degrade`` only
PREDICTS gate-2's outcome from the same resolution/evidence/attestation
rules, and never changes ``invoke()``'s behavior or signature.

Hard constraints (this module only, never relaxed):
  - NEVER add a dependency on the ``orchestrator`` package — the tầng-1
    grid copy is independent.
  - NEVER ``import grid_engine`` — that would cycle (grid_engine imports
    this module by dotted path via ``--invoker grid_fill_replay:invoke``).
  - This is a passive relay: it never calls a model, a CLI, or a proxy — it
    only reads a file another process already wrote.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

import artifact_check  # noqa: E402 — bare sibling-module import (scripts/ on sys.path), mirrors grid_engine.py

from grid.density import DensityConfig, density_policy  # noqa: E402
from grid.expander import ExpanderLlmResponse, LlmInvokerContext  # noqa: E402
from grid.types import CellResolution, Grid  # noqa: E402

ENV_SRC_PATH = "HARNESS_GRID_FILL_SRC"
_FALLBACK_REL_PATH = ("artifacts", "grid-fill-src.json")

# invoke() is a fixed LlmInvoker (Callable[[LlmInvokerContext],
# ExpanderLlmResponse]) -- expander.py's seam, shared by every invoker, is
# not this module's to widen with an extra parameter (see
# test_diagnostic_invoke_signature_unchanged). A caller that resolves an
# EXPLICIT --root (grid_engine.py's `expand --root X --invoker
# grid_fill_replay:invoke`) has no other channel to hand that root to
# invoke() than module state -- set_root() below is that channel. None
# (the default) preserves the original Path.cwd() fallback.
_ROOT_OVERRIDE: Optional[Path] = None


def set_root(root: Optional[Path]) -> None:
    """Bind the repo root ``invoke()`` resolves the active plan against.
    Called by ``grid_engine.py`` right after it loads this module as the
    ``--invoker`` target and sees an explicit ``--root`` — the SAME root
    ``--validate --root X`` already honours (``resolve_source_path``),
    closing the divergence where ``invoke()`` silently fell back to
    ``Path.cwd()`` regardless of ``--root``. Pass ``None`` to clear the
    override and restore the ``Path.cwd()`` fallback."""
    global _ROOT_OVERRIDE
    _ROOT_OVERRIDE = root


_CoordKey = Tuple[Tuple[str, str], ...]

# Plausible typos of ENV_SRC_PATH, fixed rather than computed: a
# difflib.get_close_matches sweep over the whole environment was considered
# and rejected — a real environment carries hundreds of vars (false-positive
# hints), and scanning all of os.environ from a pure file-reading module is
# scope this module does not need. Extend this list by hand as real typos
# turn up.
_NEAR_MISS_HINTS = (
    "GRID_FILL_SRC",
    "HARNESS_FILL_SRC",
    "HARNESS_GRID_FILL",
    "GRID_FILL_SOURCE",
    "HARNESS_GRID_SRC",
)

# One warning per key per process, not per cell: _load_entries can run once
# per grid cell, and 51 identical stderr lines is noise, not signal. Tests
# MUST clear this between cases (fixture, not manual) or a warning already
# consumed by an earlier case makes a later assertion pass for the wrong
# reason.
_WARNED: set = set()


def _warn_once(key: str, message: str) -> None:
    """Write one diagnostic line to stderr, at most once per ``key`` per
    process. Never stdout — stdout carries this module's JSON/summary
    output, and a warning line there would corrupt it."""
    if key in _WARNED:
        return
    _WARNED.add(key)
    sys.stderr.write("grid-fill-replay: %s\n" % message)


def _near_miss_env_names():
    """Which of ``_NEAR_MISS_HINTS`` are actually set right now — a typo'd
    env var is otherwise indistinguishable from "no source configured at
    all", and the observed cost of that ambiguity was several debugging
    rounds plus a wrong accusation aimed at the filler subagent."""
    return [name for name in _NEAR_MISS_HINTS if name in os.environ]


def _hint_suffix() -> str:
    names = _near_miss_env_names()
    if not names:
        return ""
    hints = " ".join(
        "found env var `%s` — did you mean `%s`?" % (name, ENV_SRC_PATH)
        for name in names
    )
    return " " + hints


def _coord_key(coordinates: Dict[str, str]) -> _CoordKey:
    """Order-independent identity for a cell's coordinates dict — both this
    reader and any writer compare by VALUE, never by a specific key
    ordering or a specific JSON serialization of the dict."""
    return tuple(sorted(coordinates.items()))


def resolve_source_path(root: Optional[Path] = None) -> Optional[Path]:
    """``HARNESS_GRID_FILL_SRC`` wins outright; otherwise the active plan's
    ``artifacts/grid-fill-src.json``, resolved the same way
    ``grid_engine.py emit --root`` resolves the active plan. Returns
    ``None`` when neither resolves — the caller then degrades every cell
    to STUB via the normal absent-entry path; this never raises. Warns
    (stderr, once) only for the no-source-at-all case — the two file-
    existence cases are only knowable to the caller, which checks
    ``path.is_file()``."""
    env_path = os.environ.get(ENV_SRC_PATH)
    if env_path:
        return Path(env_path)
    plan_dir = artifact_check.resolve_active_plan(root or Path.cwd())
    if plan_dir is None:
        _warn_once(
            "no-source",
            "no fill source: %s unset and no active plan found. "
            "Every cell will degrade to STUB.%s" % (ENV_SRC_PATH, _hint_suffix()),
        )
        return None
    return plan_dir.joinpath(*_FALLBACK_REL_PATH)


def _load_entries(root: Optional[Path] = None) -> Dict[_CoordKey, dict]:
    path = resolve_source_path(root)
    if path is None:
        return {}
    if not path.is_file():
        if os.environ.get(ENV_SRC_PATH):
            _warn_once(
                "path-missing",
                "%s points at %s — file does not exist. "
                "Every cell will degrade to STUB." % (ENV_SRC_PATH, path),
            )
        else:
            _warn_once(
                "path-missing",
                "no fill source: %s unset and %s does not exist. "
                "Every cell will degrade to STUB.%s" % (ENV_SRC_PATH, path, _hint_suffix()),
            )
        return {}
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as e:
        _warn_once(
            "parse-error",
            "cannot parse %s as JSON: %s. Every cell will degrade to STUB." % (path, e),
        )
        return {}
    if not isinstance(raw, list):
        _warn_once(
            "wrong-type",
            "%s must be a JSON array, got %s. Every cell will degrade to STUB."
            % (path, type(raw).__name__),
        )
        return {}
    index: Dict[_CoordKey, dict] = {}
    for entry in raw:
        if not isinstance(entry, dict):
            continue
        coords = entry.get("coordinates")
        if not isinstance(coords, dict):
            continue
        index[_coord_key(coords)] = entry
    return index


def invoke(ctx: LlmInvokerContext) -> ExpanderLlmResponse:
    """The replay ``LlmInvoker``. Looks up ``ctx.cell.coordinates`` in the
    source file and relays that entry's raw fields back verbatim — it never
    validates evidence/attestation itself; ``expand_cell`` runs that check
    on whatever this returns, exactly as on any other invoker's response."""
    entries = _load_entries(_ROOT_OVERRIDE)
    entry = entries.get(_coord_key(ctx.cell.coordinates))
    if entry is None:
        # Cell absent from the source file -> resolution=None ->
        # expander._coerce_resolution(None) falls through to the
        # unknown-resolution STUB path. Never raises, never invents.
        # tokens_used=None: the harness never measured a spend for a cell it
        # was not told about — the expander omits tokens_spent (never a fake 0).
        return ExpanderLlmResponse(resolution=None, tokens_used=None)

    # tokens_used passes through verbatim (None when the entry omits it) — the
    # filler cannot self-report a truthful count, so an absent field stays
    # UNMEASURED and the expander omits tokens_spent rather than emitting 0.
    return ExpanderLlmResponse(
        resolution=entry.get("resolution"),
        tokens_used=entry.get("tokens_used"),
        content=entry.get("content"),
        evidence=entry.get("evidence"),
        attestation=entry.get("attestation"),
    )


# ---------------------------------------------------------------------------
# --validate: gate-1, loud input-structure checks in front of expand_cell's
# anti-confab gate-2. ``invoke()`` above stays a passive relay that never
# raises and never reports — a malformed/typo'd source file collapses every
# cell to an honest-looking STUB with zero diagnostics. This CLI is the
# separate, read-only surface that makes that collapse loud instead of
# silent, and reports fill-source coverage against the real grid. It never
# touches ``invoke()``'s behavior or signature.
# ---------------------------------------------------------------------------

# SKELETON is deliberately excluded: it is a non-terminal placeholder state
# (never a valid FILLED resolution), and expand_cell's own branching sends it
# down the unknown-resolution -> STUB path (expander.py:278-279) exactly like
# any other value outside the contract.
_VALID_RESOLUTION_VALUES = frozenset(
    r.value for r in CellResolution if r != CellResolution.SKELETON
)
_ATTESTATION_RESOLUTIONS = frozenset(
    {CellResolution.STUB.value, CellResolution.MISSING.value, CellResolution.NA.value}
)


def _load_grid_for_validate(grid_path: Path) -> Grid:
    """Mirrors ``grid_engine.py``'s own ``_load_grid_file`` — duplicated
    rather than imported, since importing ``grid_engine`` here would cycle
    (it dotted-path-imports this module's ``invoke``)."""
    raw = json.loads(grid_path.read_text(encoding="utf-8"))
    return Grid.from_dict(raw)


def _predicts_degrade(entry: dict, policy: DensityConfig) -> bool:
    """Predict whether ``expand_cell`` (gate-2) would degrade this entry to
    STUB — mirrors its resolution branching (``expander.py:225-279``)
    WITHOUT running it: HIGH needs non-empty evidence; LOW needs non-empty
    evidence too, but ONLY when the grid's density policy sets
    ``evidence_required == "always"`` (the HIGH density_tier; see
    ``expander.py:249-252``) — under any other policy an evidence-less LOW
    stays a survivable LOW; STUB/MISSING/N-A need a non-empty attestation;
    SKELETON and any resolution outside that set fall through the
    unknown-resolution path. Takes the density policy explicitly (unlike
    ``expand_cell``, which reads it off ``ExpanderInput.policy``) since
    ``--validate`` never builds one — it derives the SAME policy once from
    the grid's own density_tier and threads it through every entry."""
    resolution = entry.get("resolution") if isinstance(entry, dict) else None
    if resolution not in _VALID_RESOLUTION_VALUES:
        return True
    if resolution == CellResolution.HIGH.value:
        evidence = [e for e in (entry.get("evidence") or []) if e]
        return not evidence
    if resolution == CellResolution.LOW.value:
        if policy.evidence_required != "always":
            return False
        evidence = entry.get("evidence") or []
        return len(evidence) == 0
    if resolution in _ATTESTATION_RESOLUTIONS:
        attestation = (entry.get("attestation") or "").strip()
        return not attestation
    return False


def _run_validate(grid_path: Path, src_path: Optional[Path]) -> Tuple[int, str]:
    """Gate-1: hard-fail (non-zero, message names the reason) on structural
    breakage — missing file, malformed JSON, or a non-array top level.
    A structurally sound array always exits 0 with a one-line coverage
    summary; orphan/unfilled/will_degrade are informational, never a
    failure — an honest gap is a legitimate outcome, the point is making it
    visible before it silently reaches gate-2."""
    if src_path is None or not src_path.is_file():
        return 1, "fill-src not found: %s" % src_path
    try:
        raw_text = src_path.read_text(encoding="utf-8")
    except OSError as e:
        return 1, "fill-src not found: %s (%s)" % (src_path, e)
    try:
        raw = json.loads(raw_text)
    except ValueError as e:
        return 1, "malformed JSON in %s: %s" % (src_path, e)
    if not isinstance(raw, list):
        return 1, "fill-src must be a JSON array, got %s" % type(raw).__name__

    try:
        grid = _load_grid_for_validate(grid_path)
    except (OSError, ValueError) as e:
        return 1, "cannot load grid %s: %s" % (grid_path, e)

    grid_cells_by_key = {_coord_key(cell.coordinates): cell for cell in grid.cells}
    unfilled_keys = {
        key for key, cell in grid_cells_by_key.items() if cell.resolution == CellResolution.SKELETON
    }
    policy = density_policy(grid.density_tier)

    # Dedup by coordinate key, LAST-WINS — mirrors _load_entries exactly (the
    # real replay path indexes the source file the SAME way), so
    # matched/will_degrade reflect what invoke() will actually apply, not the
    # raw per-entry count. An entry with no valid coordinates dict can't be
    # deduped (it has no key) — each such entry is counted below as its own
    # orphan, same as before this fix.
    deduped_by_key: Dict[_CoordKey, dict] = {}
    unkeyed_orphans = 0
    for entry in raw:
        if not isinstance(entry, dict):
            unkeyed_orphans += 1
            continue
        coords = entry.get("coordinates")
        if not isinstance(coords, dict):
            unkeyed_orphans += 1
            continue
        deduped_by_key[_coord_key(coords)] = entry

    matched = 0
    will_degrade = 0
    matched_keys = set()
    orphan_keys = set()
    for key, entry in deduped_by_key.items():
        if key not in grid_cells_by_key:
            orphan_keys.add(key)
            continue
        matched += 1
        matched_keys.add(key)
        if _predicts_degrade(entry, policy):
            will_degrade += 1

    # orphan = distinct orphan coordinate keys (a coord repeated twice with
    # no matching cell is still ONE orphan) + each unkeyed/malformed entry
    # counted individually (it never had a key to dedup by in the first
    # place).
    orphan = len(orphan_keys) + unkeyed_orphans
    unfilled = len(unfilled_keys - matched_keys)
    summary = (
        "fill-src validate: entries=%d matched=%d orphan=%d unfilled=%d will_degrade=%d"
        % (len(raw), matched, orphan, unfilled, will_degrade)
    )
    return 0, summary


def _build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="grid_fill_replay.py",
        description=(
            "Replay LlmInvoker for the grid depth-expander seam. --validate runs "
            "gate-1 (loud input-structure checks + coverage report) on a fill-source "
            "file, ahead of expand_cell's own gate-2 anti-confab validation."
        ),
    )
    parser.add_argument("--validate", action="store_true", help="Run gate-1 structural validation + coverage report; read-only, never mutates the fill-source or the grid.")
    parser.add_argument("--grid", type=Path, help="Grid/skeleton JSON to cross-check fill-source coordinates against (required with --validate).")
    parser.add_argument("--src", type=Path, default=None, help="Fill-source JSON path; defaults to the same resolution invoke() uses — HARNESS_GRID_FILL_SRC env, else the active plan's artifacts/grid-fill-src.json.")
    parser.add_argument("--root", type=Path, default=None, help="Repo root for active-plan resolution when --src is omitted.")
    return parser


def main(argv=None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)
    if not args.validate:
        parser.error("nothing to do — pass --validate")
    if args.grid is None:
        parser.error("--validate requires --grid <grid.json>")
    src_path = args.src if args.src is not None else resolve_source_path(args.root)
    exit_code, message = _run_validate(args.grid, src_path)
    sys.stderr.write(message + "\n")
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
