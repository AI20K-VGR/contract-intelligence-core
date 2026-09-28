#!/usr/bin/env python3
"""loop_handoff — render a plan-intake brief from the BA task sidecar.

The BA task list (`task_model.py`, read via `list_tasks()`) is dev-ready work
that still needs a human to actually drive it through `hs:plan`. This module
does not reinvent phase planning or author a machine-readable plan graph — it
renders one markdown brief (task id / title / serves / depends_on / acceptance
per task, plus an optional originating POC id) that a human feeds into
`hs:plan` intake themselves. `hs:plan` is the only thing that ever writes a
`plan-graph.yaml`; see test_write_brief_output_is_markdown_never_plan_graph_yaml
below, a hard guard on that boundary, not just documentation.

Carrying the POC id is what closes the loop: once a technical POC has gated
closed (`poc_gate.gate()`), the brief for the work it unblocks can cite that
POC id, so whoever reads the brief next can trace straight back to the
verifying plan/review/verification trio that already closed it.
"""

from __future__ import annotations

import argparse
import datetime
import fcntl
import sys
from pathlib import Path
from typing import Any, Dict, Optional, Sequence

# yaml_io (the shared YAML reader/writer, harness/scripts/) is not on sys.path
# by default from a skill's scripts/ dir -- add it before importing. APPEND
# (never insert at 0) so a same-named sibling module in THIS skill's own
# scripts/ dir keeps winning over a harness/scripts copy.
_HARNESS_SCRIPTS = str(Path(__file__).resolve().parents[5] / "scripts")
if _HARNESS_SCRIPTS not in sys.path:
    sys.path.append(_HARNESS_SCRIPTS)
import yaml_io

sys.path.insert(0, str(Path(__file__).resolve().parent))
from shape_paths import shape_path  # noqa: E402
from _spec_bridge import load_spec_modules, load_id_grammar as _load_id_grammar  # noqa: E402
from _sidecar import _now_iso  # noqa: E402
import task_model  # noqa: E402  -- sibling BA task reader, same scripts dir
import poc_gate  # noqa: E402  -- sibling POC reader, for the --poc closed-loop check

RootLike = Any  # str | Path, kept untyped to avoid a PEP-604 union annotation

# Shared C0/DEL + bidi strip set from hs:spec (single source) — the brief body
# embeds hand-editable free-text (a task's `acceptance` items), so a smuggled
# ANSI/OSC/bidi sequence must be neutralized before it reaches the markdown a
# developer `cat`s. Same regex the spec render family and the _sidecar writers use.
# `strip_control` neutralizes the frontmatter VALUES pre-safe_dump (a bidi in a
# --poc id / task id would otherwise ride LITERAL, since safe_dump escapes C0 but
# not bidi under allow_unicode); stripping pre-dump also avoids the str->bool
# retype a post-dump text strip causes on an unquoted reserved-word scalar.
_render_common = load_spec_modules(("render_common",))
_CONTROL_RE = _render_common._CONTROL_RE
_strip_control = _render_common.strip_control


class LoopHandoffError(ValueError):
    """Raised when a brief cannot be rendered (no tasks to hand off, ...)."""


def _now_ts() -> str:
    return datetime.datetime.now(datetime.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def brief_path(root: RootLike, ts: Optional[str] = None) -> Path:
    """`<root>/docs/product/shape/plan-intake-<ts>.md`, resolved via `shape_path()`."""
    return shape_path(root, "plan-intake-%s.md" % (ts or _now_ts()))


# ---------------------------------------------------------------------------
# Render
# ---------------------------------------------------------------------------

def _render_task_section(task: Dict[str, Any], id_grammar) -> str:
    task_id = task.get("id") or "?"
    lines = ["## %s — %s" % (task_id, task.get("title") or task_id), ""]

    # Routed through `id_grammar.normalize_serves` -- the same shared
    # reading the PO gate and the BA `serves_resolver` use -- instead of a
    # bare `", ".join(serves)`: a hand-edited non-list `serves` (a bare
    # string, an int) used to char-iterate or raise an uncaught TypeError
    # here (this module's own `main()` only catches `LoopHandoffError`).
    # Invalid entries are surfaced, not swallowed, so a malformed record
    # doesn't silently render as if `serves` were empty.
    valid_serves, invalid_serves = id_grammar.normalize_serves(task.get("serves"))
    # Dedupe (order-preserving) so a hand-edited `serves:[S1,S1]` renders once,
    # matching serves_resolver/strict_gate's dedupe of the same field.
    valid_serves = list(dict.fromkeys(valid_serves))
    invalid_serves = list(dict.fromkeys(invalid_serves))
    serves_text = ", ".join(valid_serves) if valid_serves else "(none)"
    if invalid_serves:
        serves_text += " (invalid: %s)" % ", ".join(invalid_serves)
    lines.append("serves: %s" % serves_text)

    # depends_on / acceptance are list-ish frontmatter fields a hand edit may
    # leave as a bare scalar; coerce through the shared id_grammar.as_str_list so
    # a bare string never char-splits and a non-str entry never raises an
    # uncaught TypeError past main()'s LoopHandoffError-only guard (same class as
    # serves above).
    depends_on = id_grammar.as_str_list(task.get("depends_on"))
    lines.append("depends_on: %s" % (", ".join(depends_on) if depends_on else "(none)"))
    lines.append("")

    lines.append("Acceptance:")
    acceptance = id_grammar.as_str_list(task.get("acceptance"))
    if acceptance:
        for a in acceptance:
            lines.append("- %s" % a)
    else:
        lines.append("- (none recorded)")
    return "\n".join(lines)


def render_brief(tasks: Sequence[Dict[str, Any]], poc_id: Optional[str] = None) -> str:
    """Render the plan-intake brief markdown. `tasks` is the same frontmatter-dict
    shape `task_model.list_tasks()`/`.author()` return. Raises `LoopHandoffError`
    on an empty task list -- a brief with nothing to hand off is not a brief.
    """
    if not tasks:
        raise LoopHandoffError("no tasks to hand off -- author at least one BA task first")

    fm: Dict[str, Any] = {}
    if poc_id:
        fm["poc"] = poc_id
    fm["task_ids"] = [t.get("id") or "?" for t in tasks]
    fm["generated"] = _now_iso()
    fm_text = yaml_io.safe_dump(_strip_control(fm), sort_keys=False, allow_unicode=True)

    id_grammar = _load_id_grammar()
    sections = [_render_task_section(t, id_grammar) for t in tasks]
    body = "# Plan intake brief\n\n" + "\n\n".join(sections) + "\n"
    # Strip C0/DEL + bidi from the body (free-text acceptance items are hand-
    # editable); the frontmatter values were neutralized pre-safe_dump above.
    body = _CONTROL_RE.sub("", body)

    return "---\n%s---\n\n%s" % (fm_text, body)


def write_brief(
    root: RootLike,
    tasks: Sequence[Dict[str, Any]],
    poc_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> Path:
    text = render_brief(tasks, poc_id=poc_id)
    # The brief filename is second-precision wall-clock. Serialize on a sibling
    # lock and, for an auto (ts=None) stamp, disambiguate a same-second collision
    # so two concurrent briefs never land on one path (the second silently
    # clobbering the first — both callers otherwise get a success + a path).
    lock_path = shape_path(root, ".plan-intake.lock")
    lock_path.parent.mkdir(parents=True, exist_ok=True)
    with open(lock_path, "a+") as lock_fd:
        fcntl.flock(lock_fd.fileno(), fcntl.LOCK_EX)
        try:
            target = brief_path(root, ts=ts)
            if ts is None:
                base = target
                n = 2
                while target.exists():
                    target = base.with_name("%s-%d%s" % (base.stem, n, base.suffix))
                    n += 1
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(text, encoding="utf-8")
            return target
        finally:
            fcntl.flock(lock_fd.fileno(), fcntl.LOCK_UN)


def write_brief_from_dir(
    root: RootLike,
    poc_id: Optional[str] = None,
    ts: Optional[str] = None,
) -> Path:
    """Convenience: hand off every task currently committed to the BA sidecar."""
    return write_brief(root, task_model.list_tasks(root), poc_id=poc_id, ts=ts)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="loop_handoff.py",
        description="Render a plan-intake brief (markdown) from the BA task sidecar, for "
        "a human to feed into hs:plan intake. Never emits a plan-graph.yaml.",
    )
    p.add_argument("--root", required=True, help="workspace root (holds docs/product/)")
    p.add_argument("--poc", default=None, help="POC-<n> id this brief's work is unblocked by")
    return p


def _assert_poc_closed(root: RootLike, poc_id: str) -> None:
    """A cited `--poc` must resolve to a POC that actually gated CLOSED — the
    brief's whole trace-back promise (see module docstring) depends on it. A
    missing, malformed, or still-open/BLOCKED POC is refused loudly (as a
    LoopHandoffError, so the CLI surfaces a clean error, never a traceback)
    rather than written into a brief as a fake closed-loop citation.

    This lives at the CLI edge only: the render/write library helpers stay
    permissive builders (their callers pass their own already-vetted poc ids)."""
    try:
        fm, _body = poc_gate.read_poc(root, poc_id)
    except poc_gate.PocError as exc:
        raise LoopHandoffError("cannot cite --poc %s: %s" % (poc_id, exc)) from exc
    if fm.get("closed") is not True:
        raise LoopHandoffError(
            "cannot cite --poc %s: it has not gated closed (verdict=%r, status=%r) "
            "-- only a POC closed by a PASS review+verification may be cited in a "
            "handoff brief" % (poc_id, fm.get("verdict"), fm.get("status"))
        )


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _build_argparser().parse_args(argv)
    try:
        if args.poc:
            _assert_poc_closed(args.root, args.poc)
        target = write_brief_from_dir(args.root, poc_id=args.poc)
    except LoopHandoffError as exc:
        print("error: %s" % exc, file=sys.stderr)
        return 1
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
