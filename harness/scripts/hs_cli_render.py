#!/usr/bin/env python3
"""hs_cli_render.py — the DISPLAY layer for one `hs-run` result.

Renders ONE already-parsed hs-run envelope (the dict decoded from its JSON
stdout line) and stops. This is deliberate, not an omission — see
plans/260726-1837-sequence-ownership-hs-cli/final-actions/04-thu-tu-thi-cong.md
section B.MINUS-6 before adding anything that looks like a "run next step"
button or a driver loop.

hs-run's exit ladder is 0 done / 10 a MODEL must judge / 11 one more
deterministic step / 2 broken. A UI convenience button that runs "the next
step" for both 10 and 11 collapses the whole judgment layer into a click —
10 specifically means a human/model call is required, and the `record`
verbs (the ones that persist a decision) are themselves exit-11 while still
carrying judgment, so "only automate 11" is not a safe simplification
either. Display-only sidesteps the hazard by construction rather than by
policy: this module never executes anything, so it structurally cannot
violate either rule.

Three rules, enforced (not merely documented) by test_hs_cli_render.py:
  (a) never auto-advance on exit code 10
  (b) never auto-run a `record` verb, at any exit code
  (c) every element of `warnings` renders verbatim and unfolded — never
      truncated, summarised, or collapsed behind "show more"

(a) and (b) hold structurally: this module imports no shell-out or dynamic-
dispatch mechanism (subprocess / os.system / os.popen / importlib
dispatch — nothing that could re-invoke hs-run to "advance"), and it
imports no hs_run domain module directly either (nothing that could call a
`record` verb's entry function in-process, bypassing the shell-out route
entirely). (c) is behavioural: the warnings loop below has no `[:N]` slice,
no truncation branch, no summary-only fallback.

Callers pass an ALREADY-PARSED dict — this module never shells out to
hs_run.py itself, which is what keeps it trivially testable without a
subprocess in the loop and is what makes it "display-only" rather than a
thin wrapper that still drives execution.

rich renders the tty path; every code path below has a plain-text fallback
that a script piping this output can parse byte-stably — that fallback runs
when stdout is not a terminal OR rich is not installed, never a hard
failure either way. rich is imported LAZILY inside `_rich_bundle()`, never
at module top level: measured cold-import cost is ~35.8ms in this
environment, and hs-run's own hot path (`plan next` / `cook next`) never
touches this file, so nothing pays that cost unless a human is actually
looking at a terminal.

NOT yet wired into hs_cli.py's subcommand table — that is a deliberate,
separate step; this module is a display library, not an entry point.
"""
from __future__ import annotations

import sys


# ------------------------------------------------------------------ tty gate


def _stream_is_tty(stream) -> bool:
    """False on any doubt (no `isatty` attribute, or `isatty()` itself
    raising) — the safe default is always the byte-stable plain-text path,
    never a rich render nobody asked for."""
    try:
        return bool(stream.isatty())
    except Exception:
        return False


def _rich_bundle():
    """The ONLY place this module imports rich, and only ever called after
    the tty gate above has already passed. A separate function (rather than
    inlining the import) so tests can monkeypatch this one seam to simulate
    rich being entirely absent, without needing to uninstall the real
    package."""
    from rich.console import Console
    from rich.panel import Panel
    from rich.table import Table
    from rich.text import Text

    return Console, Panel, Table, Text


# A skipped row used to render identically to a passed one: the mark reads
# `done`, and a gate that never applied is marked done because there was nothing
# left to do. So the one channel a person actually looks at reported "the grid
# leg passed" for a plan that never ran a grid.
#
# Three marks, because there are three states and a reader given two will map the
# third onto whichever it resembles.
_MARK_BY_KIND = {"flag-waived": "~", "not-applicable": "-"}
_NOTE_BY_KIND = {
    "flag-waived": "  (waived by flag)",
    "not-applicable": "  (n/a — gate does not apply to this plan)",
}


def _mark(item: dict) -> str:
    """`x` ran and passed · `~` somebody waived it · `-` it never applied."""
    kind = item.get("skip_kind")
    if kind:
        return _MARK_BY_KIND.get(kind, "?")
    return "x" if item.get("done") else " "


def _skip_note(item: dict) -> str:
    """Why the row did not run, in words. The mark alone is a legend nobody has."""
    kind = item.get("skip_kind")
    return _NOTE_BY_KIND.get(kind, "") if kind else ""


# --------------------------------------------------------------- plain text


def render_plain_text(envelope: dict) -> str:
    """Pure function, zero I/O — the byte-stable plain-text rendering a
    script piping hs-run's output through this module must be able to
    parse unchanged. Also the exact fallback used when stdout is not a tty
    or rich is unavailable, so there is exactly ONE plain-text format to
    keep correct rather than two that can silently drift apart."""
    lines = []
    lines.append("state: %s" % envelope.get("state", ""))
    lines.append("next_action: %s" % envelope.get("next_action", ""))

    numbers = envelope.get("summary_numbers")
    if numbers:
        lines.append("summary_numbers: %s" % numbers)

    # Rule (d): the step-routing fields come BEFORE artifacts, because they are what
    # the reader is meant to act on first. Shown only when non-empty -- unlike
    # `warnings`, an empty list here is the normal case for a step the table does not
    # route, and a "(none)" line on every call would be noise the JSON already
    # self-declares. Which fields belong here is not this module's decision: it is
    # declared by `hs_run.Envelope`'s `render` metadata and enforced against BOTH
    # renderers by test_hs_run_envelope_contract.py.
    for key in ("rules", "references"):
        values = envelope.get(key) or []
        if values:
            lines.append("%s (%d):" % (key, len(values)))
            for value in values:
                lines.append("  - %s" % value)

    advisory = envelope.get("advisory")
    if advisory:
        lines.append("advisory: %s" % advisory)

    # The road ahead. Shown only when non-empty, like the routing fields above: an
    # empty `pending` on a finished plan is the normal case, and the reader is being
    # told what remains, not reassured that nothing does.
    pending = envelope.get("pending") or []
    if pending:
        lines.append("pending (%d): %s" % (len(pending), ", ".join(str(p) for p in pending)))

    artifacts = envelope.get("artifacts") or []
    lines.append("artifacts: (none)" if not artifacts else "artifacts:")
    for artifact in artifacts:
        lines.append("  - %s" % artifact)

    checklist = envelope.get("checklist")
    if checklist:
        lines.append("checklist:")
        for item in checklist:
            lines.append("  [%s] %s%s" % (_mark(item), item.get("step", "?"),
                                          _skip_note(item)))
            evidence = item.get("evidence")
            if evidence:
                lines.append("      evidence: %s" % evidence)
            for reason in item.get("reasons") or []:
                lines.append("      reason: %s" % reason)

    skipped = envelope.get("skipped")
    if skipped:
        lines.append("skipped: %s" % ", ".join(skipped))

    next_command = envelope.get("next_command")
    if next_command:
        lines.append("next_command: %s" % next_command)

    # Rule (c): every warning, verbatim, unfolded. No `[:N]` slice, no
    # summary-only fallback, no "show more" gate. The count line states the
    # true total so a reader can tell nothing was silently dropped.
    warnings = envelope.get("warnings") or []
    lines.append("warnings: (none)" if not warnings else "warnings (%d):" % len(warnings))
    for warning in warnings:
        lines.append("  - %s" % warning)

    root = envelope.get("root")
    if root:
        lines.append("root: %s (%s)" % (root, envelope.get("root_source", "?")))

    return "\n".join(lines) + "\n"


# --------------------------------------------------------------------- rich


def _render_rich(envelope: dict, stream, bundle) -> None:
    """tty rendering. Every value that came from the envelope (not a literal
    label this module wrote itself) is wrapped in `Text(...)`, never handed
    to Console/Panel/Table as a raw str — `Text()` never interprets rich
    markup (unlike `Text.from_markup`/a bare str under `console.markup`),
    so a warning or next_action containing a literal `[...]` cannot be
    parsed as a style tag and silently eaten. `no_color=True` +
    `highlight=False` keep the render deterministic (no ANSI escapes
    interleaved into the middle of a warning's text); `soft_wrap=True`
    makes 'unfolded' literal — no word-wrap insertion, no width-based
    cropping — which is what rule (c) actually requires for the warnings
    section below."""
    Console, Panel, Table, Text = bundle
    console = Console(file=stream, no_color=True, highlight=False, soft_wrap=True)

    state = str(envelope.get("state", ""))
    body = Text(str(envelope.get("next_action", "")))
    numbers = envelope.get("summary_numbers")
    if numbers:
        body.append("\nsummary_numbers: %s" % numbers)
    console.print(Panel(body, title="state: %s" % state, expand=False))

    # Same ordering and same non-empty rule as the plain path -- see the comment
    # there. Every envelope-sourced value goes through `Text()` for the reason in
    # this function's docstring: a rule path or advisory containing `[...]` must not
    # be eaten as a rich style tag.
    for key in ("rules", "references"):
        values = envelope.get(key) or []
        if values:
            table = Table(title=key)
            table.add_column(key.rstrip("s"))
            for value in values:
                table.add_row(Text(str(value)))
            console.print(table)

    advisory = envelope.get("advisory")
    if advisory:
        console.print(Text("advisory: %s" % advisory))

    pending = envelope.get("pending") or []
    if pending:
        console.print(Text("pending (%d): %s"
                           % (len(pending), ", ".join(str(p) for p in pending))))

    artifacts = envelope.get("artifacts") or []
    if artifacts:
        table = Table(title="artifacts")
        table.add_column("path")
        for artifact in artifacts:
            table.add_row(Text(str(artifact)))
        console.print(table)
    else:
        console.print("artifacts: (none)")

    checklist = envelope.get("checklist")
    if checklist:
        table = Table(title="checklist")
        table.add_column("done")
        table.add_column("step")
        table.add_column("evidence")
        for item in checklist:
            table.add_row(
                _mark(item),
                str(item.get("step", "?")) + _skip_note(item),
                Text(str(item.get("evidence") or "")),
            )
        console.print(table)

    skipped = envelope.get("skipped")
    if skipped:
        console.print("skipped: %s" % ", ".join(skipped))

    next_command = envelope.get("next_command")
    if next_command:
        console.print(Text("next_command: %s" % next_command))

    # Rule (c) — see the module and function docstrings; this loop is the
    # one place that rule actually lives. Do not add a `[:N]`/summary path
    # here without also deleting the test that guards it.
    warnings = envelope.get("warnings") or []
    console.print("warnings: (none)" if not warnings else "warnings (%d):" % len(warnings))
    for warning in warnings:
        console.print(Text(str(warning)))

    root = envelope.get("root")
    if root:
        console.print(Text("root: %s (%s)" % (root, envelope.get("root_source", "?"))))


# ---------------------------------------------------------------- entry point


def render_envelope(envelope: dict, stream=None) -> None:
    """Render ONE hs-run envelope to `stream` (default sys.stdout) and
    return. No loop, no return code, nothing to chain onto the next call —
    see the module docstring for why that is exactly the point."""
    stream = stream if stream is not None else sys.stdout
    if _stream_is_tty(stream):
        try:
            bundle = _rich_bundle()
        except ImportError:
            pass
        else:
            _render_rich(envelope, stream, bundle)
            if hasattr(stream, "flush"):
                stream.flush()
            return
    stream.write(render_plain_text(envelope))
    if hasattr(stream, "flush"):
        stream.flush()


if __name__ == "__main__":
    # Manual, read-only smoke entry — pipes a real hs-run envelope in via
    # stdin, e.g.:
    #   python3 harness/scripts/hs_run.py plan status 2>/dev/null | head -1 \
    #     | python3 harness/scripts/hs_cli_render.py
    import json as _json

    render_envelope(_json.loads(sys.stdin.readline()))
