#!/usr/bin/env python3
"""afk_exit_gate.py — the dual-condition exit gate.

The loop exits only when BOTH conditions hold:
  (a) >= `threshold` CONSECUTIVE completion indicators (a rolling count), and
  (b) the current iteration carries an explicit `exit_signal`.

A completion indicator is a Status with exit_signal set OR status == "complete".
Either condition alone is not enough: a single burst of verbose "I'm done"
language (one indicator) cannot exit the loop, and a high count with no explicit
signal on the deciding turn cannot either. Pure: in-memory rolling state, no IO.
"""


class ExitGate:
    def __init__(self, threshold: int = 2):
        self._threshold = max(1, int(threshold))
        self._consecutive = 0

    @property
    def consecutive(self) -> int:
        return self._consecutive

    def observe(self, status) -> bool:
        """Feed one iteration's Status; return True iff the loop should exit now."""
        exit_signal = bool(getattr(status, "exit_signal", False))
        is_indicator = exit_signal or getattr(status, "status", "") == "complete"
        self._consecutive = self._consecutive + 1 if is_indicator else 0
        return self._consecutive >= self._threshold and exit_signal
