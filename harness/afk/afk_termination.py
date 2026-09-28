#!/usr/bin/env python3
"""afk_termination.py — the AFK loop's termination taxonomy.

A named reason + stable exit code for every way the native loop controller can
stop, so the controller, telemetry, and CI all speak one vocabulary instead of
ad-hoc integers. Pure (no IO).

Exit-code grouping:
  0  clean finish    — COMPLETED / EXPLICIT_STOP / EXIT_SIGNAL_CONFIRMED
  1  budget/stall    — MAX_ITERATIONS / STALE_LOOP
  2  guard tripped   — CIRCUIT_OPEN / WORKSPACE_GONE
  3  restart         — RESTART_REQUESTED (a supervisor re-invokes a fresh loop)
  42 human handoff   — AWAITING_USER (needs a decision; distinct from every fail)
"""

import enum


class Termination(enum.Enum):
    COMPLETED = ("completed", 0)
    EXPLICIT_STOP = ("explicit_stop", 0)
    EXIT_SIGNAL_CONFIRMED = ("exit_signal_confirmed", 0)
    MAX_ITERATIONS = ("max_iterations", 1)
    STALE_LOOP = ("stale_loop", 1)
    CIRCUIT_OPEN = ("circuit_open", 2)
    WORKSPACE_GONE = ("workspace_gone", 2)
    RESTART_REQUESTED = ("restart_requested", 3)
    AWAITING_USER = ("awaiting_user", 42)

    def __init__(self, reason: str, exit_code: int):
        self.reason = reason
        self.exit_code = exit_code

    @property
    def is_success(self) -> bool:
        """True only for a clean (exit 0) finish."""
        return self.exit_code == 0

    @classmethod
    def by_reason(cls, reason: str) -> "Termination":
        """Look up a member by its reason string. Unknown → ValueError (a typo'd
        reason must fail loudly, not silently map to a wrong exit code)."""
        for m in cls:
            if m.reason == reason:
                return m
        raise ValueError("unknown termination reason: %r" % reason)
