#!/usr/bin/env python3
"""_sidecar — shared sidecar-record helpers for hs:shape (BA).

`_default_actor`, `_now_iso`, and `_render_file` used to be copy-pasted
byte-identical across every hs:shape sidecar writer (`task_model.py`,
`experiment_spec.py`, `poc_gate.py`, `roadmap_rollup.py`) -- one file-per-
record shape, one actor/timestamp/frontmatter-render convention. Collapsed
here so a future change to any of the three (e.g. the frontmatter render
format) lands once instead of drifting across four copies.

Callers reach it with a plain `sys.path.insert(0, str(Path(__file__).resolve()
.parent))` + `from _sidecar import ...` (the same dance already used for
`shape_paths`/`effort_map`). This module itself carries ONE edge onto hs:spec:
it pulls the shared `render_common` neutralization through the sanctioned
`_spec_bridge` loader so both the frontmatter and the body use the single-source
strip set the spec render family uses, never a drifting second copy — `_CONTROL_RE`
for the free-text body, and `strip_control` for the frontmatter VALUES pre-dump
(safe_dump does NOT escape a Unicode bidi char, and a post-dump text strip would
retype an unquoted reserved-word scalar; see `_render_file`).
"""

from __future__ import annotations

import datetime
import getpass
import sys
from pathlib import Path
from typing import Any, Dict

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0) so a same-named sibling module in THIS skill's own
# scripts/ dir keeps winning over a harness/scripts copy.
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

# Reach hs:spec's shared unsafe-char neutralization (C0/DEL + Unicode bidi) through
# the sanctioned isolated-loader dance — the SAME single source the spec render
# family uses, so neither the frontmatter nor the body strip can drift from it.
# BOTH sides need it: a hand-edited/--flag `title`/`subject`/`acceptance` lands RAW
# in the plain-markdown body (a smuggled ANSI/OSC/bidi sequence would execute in the
# terminal of anyone who `cat`s the file), and safe_dump does NOT escape a bidi Cf
# char in a frontmatter value under allow_unicode — so `strip_control` neutralizes
# the frontmatter values pre-dump (see `_render_file`).
sys.path.insert(0, str(Path(__file__).resolve().parent))
from _spec_bridge import load_spec_modules  # noqa: E402

_render_common = load_spec_modules(("render_common",))
_CONTROL_RE = _render_common._CONTROL_RE
_strip_control = _render_common.strip_control


class SidecarError(ValueError):
    """A record could not be rendered/written at the shared sidecar chokepoint.

    Raised (from `write_record`) when `strip_control` refuses a record — e.g. a
    hand-edited frontmatter KEY carrying a bidi/control char collapses onto a real
    key after stripping. A `ValueError` subclass so it reads as the same
    "malformed record" family every hs:shape domain error (`PocError`,
    `ExperimentError`, `RoadmapError`, `TaskError`) already is; each writer's CLI
    catches it alongside its own error so the operator sees a clean `error: ...`
    line instead of a raw render_common traceback three modules removed from the
    command they ran."""

# hs:spec's atomic text writer (same single source build_traceability uses) — so
# every hs:shape sidecar writer lands its fixed path via temp + os.replace and a
# concurrent reader never sees a torn/empty file. Reached through the same bridge.
_write_text_atomic = load_spec_modules(("encoding_utils",)).write_text_atomic


def _default_actor() -> str:
    try:
        return getpass.getuser()
    except Exception:
        return "unknown"


def _now_iso() -> str:
    return datetime.datetime.now(datetime.timezone.utc).isoformat()


def _render_file(record: Dict[str, Any], body: str) -> str:
    # Strip C0/DEL + bidi at this shared chokepoint so all four hs:shape writers
    # (task/poc/experiment/roadmap) are covered by one edit. The frontmatter is
    # neutralized on the RECORD VALUES *before* safe_dump -- safe_dump escapes C0
    # but keeps a Unicode bidi Cf char (U+202E &c) LITERAL under allow_unicode, and
    # stripping the *dumped text* afterward would delete that char out of an
    # unquoted scalar and leave a bare token (`title: <RLO>true` -> `title: true`),
    # silently retyping str -> bool/None/int on re-parse. Pre-stripping the value
    # lets PyYAML quote the neutralized string (`title: 'true'`) so it round-trips.
    # The body is free-text markdown (no YAML type semantics) -- strip it directly.
    fm = yaml_io.safe_dump(_strip_control(record), sort_keys=False, allow_unicode=True)
    return "---\n%s---\n\n%s\n" % (fm, _CONTROL_RE.sub("", body))


def write_record(target: Any, record: Dict[str, Any], body: str) -> None:
    """Render `record`+`body` and write it to `target` ATOMICALLY.

    The single write chokepoint for every hs:shape sidecar writer (task / poc /
    experiment / roadmap). Each of those artifacts lives at ONE fixed path that a
    human or another CLI (`read_poc`/`read_roadmap`, a `cat`) may read while an
    update rewrites it in place — a bare `write_text` truncates-then-refills that
    path, so a concurrent reader can catch a 0-byte or half-written file. Routing
    through `write_text_atomic` (temp + os.replace) closes that torn-read window
    once, for all four writers. Content is regenerable / writer-serialized under a
    flock where it matters, so only the reader side needs the atomic swap.
    """
    try:
        rendered = _render_file(record, body)
    except ValueError as exc:
        # strip_control refuses a record whose key collapses onto another after
        # bidi/control stripping. Re-raise as the typed sidecar error so the
        # caller's CLI funnels it to a clean message, not a bare-ValueError
        # traceback. Narrow to the render step so an unrelated write OSError
        # (from write_text_atomic) still surfaces on its own.
        raise SidecarError(str(exc)) from exc
    _write_text_atomic(Path(target), rendered)
