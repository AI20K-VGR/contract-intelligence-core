#!/usr/bin/env python3
"""session_gc.py — reclaim stale per-session state by mtime TTL.

state/sessions/ grows one actor-cache file per session and never shrinks;
state/nudge-inject/ (the observation pointer) and state/skip-marks/ (the
skip-trace markers) accumulate the same way. This sweep removes files older than
a TTL (default 14 days) by mtime, across those subdirs only — the audit trace and
telemetry counters are governed by their own retention and are never touched here.

Telemetry-class, fail-open: a missing dir, an unreadable stat, or a denied unlink
is swallowed per file and the sweep continues. Callable on demand (CLI) or throttled
to once a day from session_init. `now` is injectable for deterministic tests.
"""

import os
import sys
import time
from pathlib import Path

sys.path.append(str(Path(__file__).resolve().parent.parent / "hooks"))
import hook_runtime  # noqa: E402
import model_override  # noqa: E402 — owns the marker dir name this sweep must match

TTL_DAYS = 14
INTERVAL_HOURS = 24
# Per-session caches that grow unbounded. NOT trace/ or telemetry/ — those have
# their own retention (the audit trace never rotates; telemetry rotates at 8MB).
#
# This is an ALLOWLIST, which is the trap it carries: a per-session dir added
# later is not swept and says nothing about it. The last three entries were added
# after that happened — measured on this tree, mutation-guard held 13 snapshots up
# to 47 days old, explore-override 3 grant files expired 24-35 days earlier plus
# 10 orphan .lock companions, delegate-consent 1 file expired 42 days earlier.
# All three are keyed by session (or by sha256(session|agent)), so once that
# session ends nothing can ever open them again — unreclaimable by construction.
#
# The bar for adding a name: the file is keyed to one session AND nothing deletes
# it on the way out. A dir whose contents outlive their session on purpose
# (trace/, telemetry/) belongs to its own retention policy, never here.
# `model-override` was renamed from `explore-override` and this list kept the old
# spelling, so the sweep walked an empty directory while the one being written grew
# without bound. Named from the writer's own constant rather than retyped, so the
# next rename cannot separate them again.
_GC_SUBDIRS = ("sessions", "nudge-inject", "skip-marks",
               "mutation-guard", model_override._MARKER_SUBDIR, "delegate-consent")
_THROTTLE_NAME = "session-gc.last"


def _state_dir() -> Path:
    return hook_runtime._state_dir()


def gc_state(state_dir=None, ttl_days=TTL_DAYS, now=None) -> int:
    """Remove files older than ttl_days (by mtime) from the swept subdirs. Returns
    the count removed. Never raises — every dir/file error is swallowed."""
    root = Path(state_dir) if state_dir is not None else _state_dir()
    cutoff = (now if now is not None else time.time()) - ttl_days * 86400
    removed = 0
    for sub in _GC_SUBDIRS:
        d = root / sub
        try:
            if not d.is_dir():
                continue
            for f in d.iterdir():
                try:
                    if f.is_file() and f.stat().st_mtime < cutoff:
                        f.unlink()
                        removed += 1
                except OSError:
                    continue  # vanished / unreadable / denied — keep sweeping
        except OSError:
            continue
    return removed


def _throttle_path(root: Path) -> Path:
    return root / _THROTTLE_NAME


def gc_if_due(state_dir=None, ttl_days=TTL_DAYS, interval_hours=INTERVAL_HOURS,
              now=None) -> int:
    """Run gc_state at most once per interval_hours. Returns the count removed, or
    -1 when the sweep was skipped (not yet due). The last-run epoch is stored in a
    marker file's CONTENT (not its mtime) so an injected `now` stays deterministic.
    Fail-open: any error degrades to running (or a harmless re-stamp)."""
    root = Path(state_dir) if state_dir is not None else _state_dir()
    t = now if now is not None else time.time()
    marker = _throttle_path(root)
    try:
        if marker.is_file():
            last = float(marker.read_text(encoding="utf-8").strip() or 0)
            if (t - last) < interval_hours * 3600:
                return -1  # not due
    except (OSError, ValueError):
        pass
    try:
        root.mkdir(parents=True, exist_ok=True)
        marker.write_text(str(t), encoding="utf-8")  # stamp the attempt (throttle even on error)
    except OSError:
        pass
    return gc_state(root, ttl_days=ttl_days, now=now)


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    force = "--force" in argv
    ttl = TTL_DAYS
    if "--ttl-days" in argv:
        try:
            ttl = int(argv[argv.index("--ttl-days") + 1])
        except (ValueError, IndexError):
            ttl = TTL_DAYS
    removed = gc_state(ttl_days=ttl) if force else gc_if_due(ttl_days=ttl)
    if removed < 0:
        print("session_gc: not due (throttled)")
    else:
        print("session_gc: removed %d stale file(s)" % removed)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
