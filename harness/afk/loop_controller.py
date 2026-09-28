#!/usr/bin/env python3
"""loop_controller.py — the native AFK iteration driver.

The harness drives each AFK iteration directly instead of delegating the loop to
Ralph: invoke Claude → capture stdout → parse the AFK_STATUS block → feed the
guards → continue or stop with a named Termination. The invoker is INJECTED, so
the loop logic is fully unit-testable without a live Claude (the way ralph-cc
covers its loop with fakes); `make_claude_invoker` is the thin live seam.

Per-iteration order:
  1. restart sentinel present → RESTART_REQUESTED (exit 3, supervisor re-invokes)
  2. stop sentinel present    → EXPLICIT_STOP (exit 0)
  3. invoke(iteration, session_id)
  4. is_error → drop the session id (never resume a broken context)
  5. parse status; record fingerprint → STALE_LOOP if the same call repeats N×
  6. circuit breaker update → CIRCUIT_OPEN on stagnation/permission wall
  7. dual-condition exit gate → EXIT_SIGNAL_CONFIRMED
  loop exhausted → MAX_ITERATIONS.
"""

import argparse
import hashlib
import os
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(_HERE))
import afk_circuit_breaker as _cb  # noqa: E402
import afk_exit_gate as _eg  # noqa: E402
import afk_output_parser as _op  # noqa: E402
import afk_stale_guard as _sg  # noqa: E402
from afk_termination import Termination  # noqa: E402


@dataclass
class InvocationResult:
    """One iteration's outcome, as the invoker reports it."""
    stdout: str = ""
    is_error: bool = False
    permission_denied: bool = False
    question: bool = False
    diff_count: int = 0          # progress signal: >0 when HEAD advanced (a commit landed)
    signature: str = ""          # opaque action signature for stale detection
    session_id: str = ""         # session to resume next iteration (dropped on error)
    workspace_gone: bool = False  # the repo/workspace vanished mid-run (unattended)


def build_claude_command(prompt, session_id=None, output_format="json",
                         extra_args=None, settings="project,local",
                         claude_bin=None):
    """Build the Claude Code argv with host-settings isolation.

    `--setting-sources project,local` keeps the operator's global ~/.claude hooks
    from leaking into a harness-controlled run. `--resume <id>` continues a
    session when one is carried over."""
    binary = claude_bin or os.environ.get("CLAUDE_BIN", "claude")
    argv = [binary, "-p", str(prompt), "--output-format", output_format,
            "--setting-sources", settings]
    if session_id:
        argv += ["--resume", str(session_id)]
    if extra_args:
        argv += list(extra_args)
    return argv


AFK_STATUS_INSTRUCTION = (
    "\n\n---\n"
    "AFK loop protocol: at the VERY END of your response, emit exactly one status "
    "block on its own line so the controller can read your progress:\n"
    '<<<AFK_STATUS>>>{"status":"in_progress|complete|blocked",'
    '"exit_signal":false,"files_modified":<int>,"note":"<short>"}'
    "<<<END_AFK_STATUS>>>\n"
    "Set status=complete AND exit_signal=true ONLY when the task is fully done and "
    "verified — that explicit signal, confirmed across two consecutive turns, is "
    "what ends the loop. Use status=blocked with exit_signal=false when you need "
    "the operator. files_modified = the number of files you changed this turn."
)


def wrap_prompt(prompt: str) -> str:
    """Append the AFK_STATUS block contract so Claude emits the signal the parser
    and guards consume. Without it the loop is fail-safe but never exits early."""
    return "%s%s" % (prompt, AFK_STATUS_INSTRUCTION)


class LoopController:
    def __init__(self, invoke, max_iterations, *, state_dir=None,
                 restart_sentinel=None, stop_sentinel=None,
                 exit_threshold=2, half_open_at=2, open_at=3, stale_at=3,
                 awaiting_user_at=3):
        self._invoke = invoke
        self._max = max(1, int(max_iterations))
        # Consecutive blocked-on-question turns before the loop hands off to the
        # human (AWAITING_USER, exit 42). Mirrors open_at: "stuck making no
        # progress" trips the breaker at open_at; "stuck waiting on the human"
        # hands off here at the same cadence.
        self._awaiting_user_at = max(1, int(awaiting_user_at))
        self._restart = Path(restart_sentinel) if restart_sentinel else None
        self._stop = Path(stop_sentinel) if stop_sentinel else None
        sd = Path(state_dir) if state_dir else None
        cb_ledger = (sd / "cb.jsonl") if sd else None
        stale_ledger = (sd / "stale.jsonl") if sd else None
        self._gate = _eg.ExitGate(threshold=exit_threshold)
        self._stale_guard = _sg.StaleGuard(threshold=stale_at, ledger_path=stale_ledger)
        # Rehydrate the breaker from its ledger so a RESTART_REQUESTED re-invocation
        # resumes the accumulated no-progress state instead of starting fresh at
        # CLOSED — otherwise a supervisor restart would silently reset the
        # stagnation watchdog every time. A missing ledger yields a fresh breaker.
        if cb_ledger is not None and Path(cb_ledger).is_file():
            self._breaker = _cb.CircuitBreaker.restore_from(
                cb_ledger, half_open_at=half_open_at, open_at=open_at)
        else:
            self._breaker = _cb.CircuitBreaker(half_open_at=half_open_at,
                                               open_at=open_at, ledger_path=cb_ledger)
        self._session_id = None

    def run(self) -> Termination:
        """Drive the invoke loop until a terminal condition is reached.

        Sentinel contract: a sentinel is CONSUMED (unlinked) the moment this
        controller acts on it. No writer in the repo ever deletes the stop or
        restart sentinel (verified across every file type and CI workflow), so
        leaving it on disk would make the NEXT invocation — a fresh unattended
        run, or the supervisor's own re-invocation after RESTART_REQUESTED —
        observe the same leftover flag on iteration 1 and terminate instantly
        with zero real iterations run. Consuming it here means a request is
        acted on exactly once.
        """
        blocked_streak = 0
        for i in range(1, self._max + 1):
            if self._restart is not None and self._restart.exists():
                self._restart.unlink(missing_ok=True)
                return Termination.RESTART_REQUESTED
            if self._stop is not None and self._stop.exists():
                self._stop.unlink(missing_ok=True)
                return Termination.EXPLICIT_STOP

            result = self._invoke(i, self._session_id)

            # The workspace disappeared mid-run (deleted / unmounted) — terminate
            # with the honest cause instead of letting the empty git diff read as
            # no-progress and route to CIRCUIT_OPEN.
            if result.workspace_gone:
                return Termination.WORKSPACE_GONE

            # A result flagged is_error means the session is poisoned — drop it so
            # the next iteration starts clean rather than resuming garbage.
            if result.is_error:
                self._session_id = None
            elif result.session_id:
                self._session_id = result.session_id

            status = _op.parse(result.stdout)
            needs_user = bool(result.question or _op.is_blocked(status))

            # The stale guard must NOT fire while Claude is blocked asking the
            # operator: a stuck-on-question loop repeats its output verbatim, so
            # the signature is identical every turn and the stale guard would
            # trip first — mislabeling a "needs a decision" handoff (AWAITING_USER,
            # exit 42) as a generic STALE_LOOP (exit 1). Suppress it on question
            # turns, mirroring how the circuit breaker suppresses its no-progress
            # counter; the AWAITING_USER streak below is the right terminator here.
            if not needs_user:
                sig = result.signature or status.note or result.stdout
                self._stale_guard.record("afk_iteration", "afk", sig)
                if self._stale_guard.is_stale():
                    return Termination.STALE_LOOP

            progress = (result.diff_count > 0 or _op.is_complete(status)
                        or status.files_modified > 0)
            self._breaker.update(
                progress,
                permission_denied=result.permission_denied,
                question=needs_user,
            )
            if self._breaker.is_open():
                return Termination.CIRCUIT_OPEN

            # The breaker SUPPRESSES the no-progress counter while Claude is blocked
            # asking the operator, so a loop that stays blocked would otherwise burn
            # every iteration and end as MAX_ITERATIONS — a budget failure that
            # hides "needs a decision". Count consecutive blocked-on-question turns
            # and hand off as AWAITING_USER once they reach the threshold. A
            # progress turn (or a non-question stagnation, which is the breaker's
            # job) resets the streak. permission_denied is not part of this streak:
            # when set (injected tests) it routes to CIRCUIT_OPEN via the breaker
            # above; on the live path it is never set (see the invoker note), so the
            # streak is driven solely by the status-block `blocked` signal.
            if progress or not needs_user:
                blocked_streak = 0
            else:
                blocked_streak += 1
                if blocked_streak >= self._awaiting_user_at:
                    return Termination.AWAITING_USER

            if self._gate.observe(status):
                return Termination.EXIT_SIGNAL_CONFIRMED

        return Termination.MAX_ITERATIONS


# --- live seam (integration; exercised by AFK e2e, not unit tests) -------------

def _git_diff_count(repo_root) -> int:
    """Changed-file count via `git diff --numstat HEAD` (staged+unstaged). 0 on error.

    The SECONDARY progress signal — uncommitted work in flight. The PRIMARY signal
    is commit-wise (HEAD advanced, see `_committed_progress`), because the loop
    commits per iteration and a freshly-committed iteration leaves a clean tree
    that this count alone would misread as no-progress."""
    try:
        out = subprocess.run(
            ["git", "diff", "--numstat", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return 0
        return len([ln for ln in out.stdout.splitlines() if ln.strip()])
    except Exception:  # noqa: BLE001 — a progress probe must never break the loop
        return 0


def _git_head(repo_root) -> str:
    """Current HEAD commit sha, or "" when there is no repo / no commit / on error.

    The AFK loop commits per iteration, so HEAD advancing is the contract's
    progress signal. A bare "" (no repo or pre-first-commit) is treated as "no
    commit yet" by the caller, never as an error."""
    try:
        out = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(repo_root), capture_output=True, text=True, timeout=10,
        )
        if out.returncode != 0:
            return ""
        return out.stdout.strip()
    except Exception:  # noqa: BLE001 — a progress probe must never break the loop
        return ""


def _committed_progress(prev_head: str, cur_head: str) -> bool:
    """Commit-wise progress: HEAD advanced to a real commit this iteration.

    The loop contract is commit-per-iteration. Measuring progress from the dirty
    working tree (`git diff HEAD`) reads a freshly-committed iteration as clean →
    "no progress" → a false stagnation trip. Comparing HEAD across iterations
    instead counts a landed commit as progress, even though the tree is clean.

    A real sha that differs from the previous one is progress; an unchanged HEAD
    is not; an empty current HEAD (no repo / no commit) is never progress."""
    return bool(cur_head) and cur_head != prev_head


def make_claude_invoker(prompt, repo_root, *, timeout=3600):
    """Thin live invoker: run one headless Claude iteration and report the result.

    Kept deliberately small — the loop logic it feeds is unit-tested; this adapter
    is the integration boundary. is_error comes from Claude's own JSON result
    field; progress is measured commit-wise (HEAD advanced since the last
    iteration), matching the commit-per-iteration loop contract; a `blocked`
    AFK_STATUS maps to a pending question via the controller."""
    import json as _json

    # Track the HEAD seen at the end of the previous iteration so an iteration
    # that lands a commit reads as progress even after it leaves a clean tree.
    # Seed from the pre-loop HEAD so the very first iteration compares correctly.
    head_state = {"prev": _git_head(repo_root)}

    def invoke(iteration, session_id) -> InvocationResult:
        argv = build_claude_command(wrap_prompt(prompt), session_id=session_id)
        is_error, new_session = False, ""
        try:
            proc = subprocess.run(argv, cwd=str(repo_root), capture_output=True,
                                  text=True, timeout=timeout)
            stdout = proc.stdout or ""
            if proc.returncode != 0:
                is_error = True
            try:
                payload = _json.loads(stdout)
                if isinstance(payload, dict):
                    is_error = bool(payload.get("is_error", is_error))
                    new_session = str(payload.get("session_id") or "")
            except ValueError:
                pass  # not JSON wrapper — treat stdout as the model text
        except Exception:  # noqa: BLE001 — surface as an error iteration, never crash
            stdout, is_error = "", True
        # Fingerprint the model payload ALONE — no iteration prefix. The stale
        # guard's whole job is to catch two identical turns; mixing the iteration
        # number into the hash makes consecutive identical outputs hash
        # differently, so the guard would never trip on a live run.
        sig = hashlib.sha1(stdout.encode("utf-8")).hexdigest()[:16]
        # The workspace DIRECTORY vanishing mid-run (deleted / unmounted) is a
        # real unattended failure mode — report it so the controller terminates
        # with the honest cause rather than reading the empty diff as no-progress.
        # Test on the dir itself, not .git: a non-git workspace is "not a repo",
        # not "gone", and must not false-trip.
        gone = not Path(repo_root).is_dir()
        # Progress signal the controller reads (result.diff_count > 0). The fix the
        # loop contract needs is the PRIMARY, commit-wise check: did HEAD advance
        # since the previous iteration? The loop commits per iteration, so a
        # freshly-committed turn leaves a clean tree that a `git diff HEAD` count
        # alone misreads as no-progress, false-tripping the stagnation breaker.
        # Comparing HEAD across iterations counts the landed commit as progress.
        # A dirty working tree (work in flight, not yet committed) is kept as a
        # SECONDARY signal so an iteration mid-edit is not punished — it can only
        # ADD progress, never re-introduce the clean-after-commit false stop.
        cur_head = _git_head(repo_root)
        progressed = (_committed_progress(head_state["prev"], cur_head)
                      or _git_diff_count(repo_root) > 0)
        head_state["prev"] = cur_head
        diff_count = 1 if progressed else 0
        # NOTE: `permission_denied` and `question` are intentionally left at their
        # False defaults on the LIVE path. The unattended handoff contract is the
        # AFK_STATUS block: a turn that needs the operator emits `status: blocked`,
        # which the controller reads via _op.is_blocked(status) → needs_user →
        # AWAITING_USER. There is no live signal for a distinct permission-wall yet,
        # so the breaker's permission_denied→CIRCUIT_OPEN route is exercised only by
        # injected tests; do NOT read the controller comments as implying a live
        # permission route exists. Wire these two from real signals (a parsed
        # permission-error type; an explicit ask) only once that signal is defined.
        return InvocationResult(
            stdout=stdout, is_error=is_error, diff_count=diff_count,
            signature=sig, session_id=new_session, workspace_gone=gone,
        )
    return invoke


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Native AFK loop controller")
    ap.add_argument("prompt")
    ap.add_argument("iterations", type=int)
    ap.add_argument("--repo-root", default=".")
    ap.add_argument("--state-dir", default=None)
    ap.add_argument("--restart-sentinel", default=None)
    ap.add_argument("--stop-sentinel", default=None)
    args = ap.parse_args(argv)
    invoke = make_claude_invoker(args.prompt, args.repo_root)
    controller = LoopController(
        invoke, args.iterations, state_dir=args.state_dir,
        restart_sentinel=args.restart_sentinel, stop_sentinel=args.stop_sentinel,
    )
    term = controller.run()
    sys.stderr.write("[afk] terminated: %s (exit %d)\n" % (term.reason, term.exit_code))
    return term.exit_code


if __name__ == "__main__":
    sys.exit(main())
