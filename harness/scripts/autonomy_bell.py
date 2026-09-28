#!/usr/bin/env python3
"""autonomy_bell.py — consecutive-empty counter for the autonomy bell.

An unattended /goal-style loop must decide WHEN to stop. Resting that on the
model remembering to stop is unreliable: an autonomous loop bypasses the
context-injection path, so the rule to stop is never re-read. This makes the
off-decision deterministic instead — a counter of consecutive "nothing left to
do" scans that trips at a threshold.

The cron prompt carries the protocol on every fire (post-check ->
`autonomy_bell.py --report empty|found` -> on STOP, `CronDelete <id>` + report
done), so no extra hook is needed to re-remind the loop. This script owns only
the counter state.

State mirrors the afk circuit-breaker store contract: APPEND-ONLY JSONL, one
record per update, last-record-wins on restore — so a re-fired cron resumes the
same count rather than starting over. Persistence is best-effort; a write error
never breaks the loop.

CLI:
  autonomy_bell.py --init [--cron-id ID] [--threshold K]   # seed a fresh run
  autonomy_bell.py --report empty|found                    # advance; prints CONTINUE|STOP
  autonomy_bell.py --status                                 # prints CONTINUE|STOP
  autonomy_bell.py --reset                                  # count -> 0
  (--state PATH overrides the ledger; --session KEY selects the per-run ledger)
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

CONTINUE, STOP = "CONTINUE", "STOP"
DEFAULT_THRESHOLD = 2
STATE_SUBDIR = "autonomy-bell"

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
try:
    import hook_runtime as _hr  # noqa: E402
    _resolve_actor = _hr.resolve_actor
    _state_dir = _hr._state_dir
except Exception:  # noqa: BLE001 — attribution/state-dir helpers must never block the loop
    def _resolve_actor(session_id=None):  # type: ignore
        return "unknown"

    def _state_dir():  # type: ignore
        raw = os.environ.get("HARNESS_STATE_DIR")
        return Path(raw) if raw else (Path(__file__).resolve().parent.parent / "state")


def _now_ts() -> str:
    return datetime.now(timezone.utc).isoformat()


def backlog_signal(root, source_ref=None):
    """Run-scoped backlog evidence for the per-fire empty/found decision.

    Returns one of:
      'found'  — ≥1 OPEN backlog record tagged to THIS run (source_ref).
      'empty'  — a run tag was given but no open record matches it.
      None     — no run tag → the backlog ABSTAINS; the bell falls back to its
                 other scope evidence (open phases / failing tests).

    The STOP regression this guards: the query is ALWAYS scoped to the
    run's source_ref, NEVER a global `--status open`. A global open query would
    pin the bell to `found` forever on any one unrelated open backlog item — a
    false `found` never lets the loop end. So a global open item must contribute
    NOTHING to `found`; only this run's own open work does.

    Determinism boundary: this is a deterministic QUERY the protocol
    consults — the model still REPORTS empty/found and the counter still owns
    STOP. The script does not compute the stop-decision.

    Graceful degradation: when `docs/backlog.yaml` does not exist yet
    (pre-migration window), fall back to a content scan of `BACKLOG.md` — never
    crash. Neither file present → abstain.
    """
    if not source_ref:
        return None  # abstain — a global open item must not force found

    root = Path(root)
    yaml_path = root / "docs" / "backlog.yaml"
    if yaml_path.is_file():
        # Import the query fn rather than shelling out (testable, no subprocess).
        try:
            import backlog_register
            open_for_run = backlog_register.query(
                root, status="open", source_ref=source_ref)
        except Exception:  # noqa: BLE001 — never break the loop on a query error
            return None
        return "found" if open_for_run else "empty"

    # Fallback: no SSOT yet — scan the prose BACKLOG.md for the run tag.
    md_path = root / "BACKLOG.md"
    try:
        text = md_path.read_text(encoding="utf-8", errors="replace")
    except (FileNotFoundError, OSError):
        return None
    return "found" if source_ref in text else "empty"


class BellCounter:
    """Consecutive-empty counter. `empty` advances, `found` resets; STOP once the
    count reaches `threshold`. Append-only ledger; rehydrate via `restore_from`."""

    def __init__(self, threshold: int = DEFAULT_THRESHOLD, ledger_path=None,
                 _count: int = 0, _cron_id=None):
        self._threshold = max(1, int(threshold))
        self._ledger = Path(ledger_path) if ledger_path else None
        self._count = max(0, int(_count))
        self._cron_id = _cron_id

    @property
    def count(self) -> int:
        return self._count

    @property
    def threshold(self) -> int:
        return self._threshold

    @property
    def cron_id(self):
        return self._cron_id

    def status(self) -> str:
        """STOP once enough consecutive empty scans have accrued, else CONTINUE."""
        return STOP if self._count >= self._threshold else CONTINUE

    def report(self, outcome: str) -> str:
        """Fold one scan outcome into the counter and return the new status.

        `empty` (nothing left to do) advances toward STOP; `found` (work remains)
        resets the streak — the bell only trips on CONSECUTIVE empties."""
        if outcome not in ("empty", "found"):
            raise ValueError("outcome must be 'empty' or 'found', got %r" % outcome)
        if outcome == "found":
            self._count = 0
        else:
            self._count += 1
        self._append(outcome)
        return self.status()

    def init(self) -> str:
        """Seed a fresh run: count 0, recording the cron id + threshold so the
        protocol can later CronDelete that id."""
        self._count = 0
        self._append("init")
        return self.status()

    def reset(self) -> str:
        self._count = 0
        self._append("reset")
        return self.status()

    def _append(self, outcome: str) -> None:
        if self._ledger is None:
            return
        try:
            self._ledger.parent.mkdir(parents=True, exist_ok=True)
            line = json.dumps({
                "outcome": outcome,
                "count": self._count,
                "threshold": self._threshold,
                "cron_id": self._cron_id,
                "status": self.status(),
                "actor": _resolve_actor(),
                "ts": _now_ts(),
            }, ensure_ascii=False) + "\n"
            # Heal a torn previous append: if the file does not end in a newline (a
            # writer was killed mid-line), separate our record so it lands on its own
            # parseable line instead of fusing onto the partial fragment.
            if self._needs_newline_prefix():
                line = "\n" + line
            with self._ledger.open("a", encoding="utf-8") as f:
                f.write(line)
        except OSError:
            pass

    def _needs_newline_prefix(self) -> bool:
        try:
            if self._ledger.exists() and self._ledger.stat().st_size > 0:
                with self._ledger.open("rb") as rf:
                    rf.seek(-1, 2)
                    return rf.read(1) != b"\n"
        except OSError:
            return False
        return False  # best-effort audit; never break the loop on a write error

    @classmethod
    def restore_from(cls, ledger_path, threshold=None, cron_id=None, **kw) -> "BellCounter":
        """Reconstruct from the last JSONL record (last-record-wins). An explicit
        `threshold`/`cron_id` overrides the persisted one; missing or unreadable
        ledger -> a fresh counter at the default threshold."""
        count, kept_threshold, kept_cron = 0, None, None
        try:
            p = Path(ledger_path)
            if p.is_file():
                lines = [ln for ln in p.read_text(encoding="utf-8").splitlines()
                         if ln.strip()]
                if lines:
                    # Walk from the tail to the last PARSEABLE record. A cron killed
                    # mid-append leaves a torn last line; falling back to count 0 on
                    # that would silently drop the streak AND revert the threshold —
                    # the opposite of resuming an exact count across a kill.
                    rec = None
                    for ln in reversed(lines):
                        try:
                            rec = json.loads(ln)
                            break
                        except ValueError:
                            continue
                    if rec is not None:
                        count = int(rec.get("count", 0))
                        kept_threshold = rec.get("threshold")
                        kept_cron = rec.get("cron_id")
        except (OSError, ValueError):
            count, kept_threshold, kept_cron = 0, None, None
        eff_threshold = (threshold if threshold is not None
                         else kept_threshold if kept_threshold is not None
                         else DEFAULT_THRESHOLD)
        eff_cron = cron_id if cron_id is not None else kept_cron
        return cls(threshold=eff_threshold, ledger_path=ledger_path,
                   _count=count, _cron_id=eff_cron, **kw)


def _resolve_ledger(args) -> Path:
    if args.state:
        return Path(args.state)
    key = args.session or os.environ.get("HARNESS_BELL_SESSION") or "current"
    return _state_dir() / STATE_SUBDIR / ("%s.jsonl" % key)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    ap = argparse.ArgumentParser(description="autonomy bell consecutive-empty counter")
    ap.add_argument("--state", help="explicit ledger path (overrides --session)")
    ap.add_argument("--session", help="per-run ledger key (default: $HARNESS_BELL_SESSION or 'current')")
    ap.add_argument("--report", choices=("empty", "found"), help="fold one scan outcome")
    ap.add_argument("--status", action="store_true", help="print CONTINUE|STOP")
    ap.add_argument("--init", action="store_true", help="seed a fresh run (count 0)")
    ap.add_argument("--reset", action="store_true", help="reset count to 0")
    ap.add_argument("--cron-id", dest="cron_id", help="cron job id to record at --init")
    ap.add_argument("--threshold", type=int, help="consecutive-empty STOP threshold")
    ap.add_argument("--backlog-signal", action="store_true",
                    help="print the run-scoped backlog signal (found|empty|abstain)")
    ap.add_argument("--source-ref", dest="source_ref",
                    help="run tag scoping the backlog query")
    ap.add_argument("--root", default=".",
                    help="repo root holding docs/backlog.yaml + BACKLOG.md")
    args = ap.parse_args(argv)

    if args.backlog_signal:
        # Deterministic, run-scoped backlog evidence for the per-fire decision —
        # NOT the report itself (the model still reports empty/found).
        sig = backlog_signal(Path(args.root).resolve(), source_ref=args.source_ref)
        sys.stdout.write(("abstain" if sig is None else sig) + "\n")
        return 0

    ledger = _resolve_ledger(args)

    if args.init:
        threshold = args.threshold if args.threshold is not None else DEFAULT_THRESHOLD
        cron_id = args.cron_id
        if cron_id is None:
            # A re-init that omits --cron-id must not drop a previously seeded id;
            # the STOP cleanup needs it for CronDelete.
            cron_id = BellCounter.restore_from(ledger).cron_id
        bell = BellCounter(threshold=threshold, ledger_path=ledger, _cron_id=cron_id)
        sys.stdout.write(bell.init() + "\n")
        return 0

    bell = BellCounter.restore_from(ledger, threshold=args.threshold, cron_id=args.cron_id)
    if args.report:
        sys.stdout.write(bell.report(args.report) + "\n")
    elif args.reset:
        sys.stdout.write(bell.reset() + "\n")
    elif args.status:
        sys.stdout.write(bell.status() + "\n")
    else:
        ap.error("one of --init / --report / --status / --reset is required")
    return 0


if __name__ == "__main__":
    sys.exit(main())
