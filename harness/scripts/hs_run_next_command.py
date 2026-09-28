#!/usr/bin/env python3
"""hs_run_next_command.py — the ONE place a hs-run verb result gets its
`next_command` field.

`next_action` is the sentence a human reads; `next_command` is a
string a driver hands to `subprocess.run()` VERBATIM, or `null` when the next
step is not a command at all. One field serving both readers served neither:
a relaxed "next_action contains a runnable command" check let `"preflight
clear — open the plan: hs-run cook open <dir>"` pass validation while a
`while exit==11: run(next_action)` driver still could not run it literally.

Why a shared module rather than a copy in each `hs_run_<domain>.py`: this repo
has been bitten repeatedly by one predicate forked across files, and the same
disease is already visible in this very domain set — exit code 11 is declared
under TWO names (`EXIT_STEP_REMAINING` and `EXIT_NEEDS_STEP`), re-declared per
module, so a grep for one name reports 0 for a module that has 16 sites of the
other. `finalize()` below is the single predicate; a ninth domain calls it
instead of re-deriving the rule and drifting from it.

Deliberately NOT importing the exit-code constants from `hs_run.py`: every
domain module re-declares them locally so it carries no load-time dependency
on the dispatcher's internals (hs_run_plan.py / hs_run_cook.py's established
discipline). The tiers are re-declared here for the same reason, and
`test_hs_run_next_command_contract.py` pins them to the dispatcher's own
values so the two can never silently diverge.

This module owns FORMATTING and DEFAULTING only, never enforcement. The
dispatcher (`hs_run.py:main`) is the enforcement point — one check every
current and future domain passes through, including any that forgets to call
this helper at all. A helper that enforced its own rule would be a second,
skippable gate; a domain simply not calling it would then look compliant.
"""
from __future__ import annotations

# The four-tier ladder (D10), IMPORTED rather than re-declared.
# Ten modules used to hand-copy these four constants and had already drifted:
# rung 11 carried two different names across the tree and two modules declared
# the same constant twice. `hs_run` owns the ladder as a closed `Exit` IntEnum;
# both historical spellings of rung 11 are bound to the same member there, so
# this import changes no name any caller in this file uses.
from hs_run import EXIT_BROKEN, EXIT_DONE, EXIT_NEEDS_MODEL, EXIT_STEP_REMAINING  # noqa: E402


def finalize(result: dict, command=None) -> dict:
    """Stamp `next_command` onto one verb result, in place, and return it.

    `command` is the verbatim-runnable string for THIS result, or `None` when
    there is no such step. A result that already carries the key is left
    alone: an explicit value a call site set itself is a CLAIM this helper
    must not overwrite — `setdefault` semantics, deliberately, so wrapping an
    already-correct call site is a no-op rather than a silent downgrade.

    The key is always set, never left absent, because absent and `null` are
    DIFFERENT claims: absent says "this verb never considered it", `null` says
    "this verb considered it and there is no verbatim-runnable step". A driver
    reading an absent key cannot tell a deliberate null from an oversight.

    An empty/whitespace-only `command` normalizes to `None` rather than being
    stored: `""` would satisfy a bare null-check downstream while leaving a
    driver with nothing to run, which is the exact hole this field closes. The
    dispatcher rejects that shape too — normalizing here means an honest
    `null` (with its truthful "no step" meaning) instead of a contract
    violation, for the one case where a caller passes a command string that
    formatted empty.
    """
    if "next_command" in result:
        return result
    if isinstance(command, str) and not command.strip():
        command = None
    result["next_command"] = command
    return result
