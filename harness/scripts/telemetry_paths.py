#!/usr/bin/env python3
"""telemetry_paths.py — write-path for the USAGE telemetry ledger.

Ported from the source corpus and re-homed for the harness: sinks live under
harness/state/telemetry/ (via harness_paths), env knobs are HARNESS_*, and
every record is enriched with `actor` (+ `ts`, + `session` when known) so
multi-user usage stays attributable.

Two-ledger split: THIS is the usage ledger — rotation 8MB with ONE
.bak generation is fine, losing old usage data costs nothing. The audit trace
(trace_log) never rotates; do not write audit events here.

Contract: a telemetry write must NEVER break the hook/op it observes. Every
function is fail-open — any error (unwritable dir, non-serializable record)
is swallowed. json.dumps is the ONLY serialization path (no manual field
concat → no forged-record injection from skill names / script paths).
"""

import hashlib
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import harness_paths  # noqa: E402

MAX_SINK_BYTES = 8 * 1024 * 1024  # 8 MB → one .bak generation, then overwrite
DEDUP_TTL_S = 60 * 60  # 1 h — bounds the marker dir size

# Session id from the env contract, read ONCE at import (a process belongs to
# one session; re-reading per event would let a mid-process env change split
# one session's records across two ids).
_SESSION = os.environ.get("HARNESS_SESSION_ID") or None

_actor_cache = None  # lazy per-process actor; resolve_actor shells out to git


def parse_iso_ts(raw):
    """Parse an ISO-8601 ts to an aware datetime (UTC-normalized if naive), or
    None if unparseable. Shared by the read-side lenses: a tz-naive ts cannot be
    compared to an aware --days cutoff (it raises TypeError and collapses the
    lens), so a malformed-but-parseable line is placed in the window, never
    crashed on. (NOT claims._parse_ts — that one reads a different ts shape.)"""
    try:
        dt = datetime.fromisoformat(str(raw).replace("Z", "+00:00"))
    except (ValueError, AttributeError):
        return None
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=timezone.utc)


def percentile(values, q):
    """Nearest-rank percentile of a numeric iterable ``values`` (q in 0..100), or
    None when empty. Sorts internally; a single element returns itself. The ONE
    shared copy for the read-side lenses (was re-implemented per lens with the same
    nearest-rank formula — drift risk)."""
    if not values:
        return None
    s = sorted(values)
    if len(s) == 1:
        return s[0]
    k = max(0, min(len(s) - 1, int(round(q / 100.0 * (len(s) - 1)))))
    return s[k]


def iter_records_in_window(sink_name: str, days: int):
    """Yield each dict record from telemetry sink ``sink_name`` whose ts is within
    the last ``days``. The single read-path every lens shares: it skips a missing
    file, an unparseable line, a parseable NON-OBJECT line, and a record with a
    missing/unplaceable ts — so no lens can forget the non-object guard (the bug
    class the lens review found re-implemented inconsistently). Fail-soft."""
    from datetime import timedelta
    cutoff = datetime.now(timezone.utc) - timedelta(days=days)
    d = harness_paths.telemetry_dir()  # read-side resolver
    # Union the legacy sink `<stem>.jsonl` with every per-session shard
    # `<stem>-<disc>.jsonl` (P2 write-side). Excludes rotated `.bak` (glob
    # `*.jsonl` never matches `.jsonl.bak`). This is THE chokepoint: unioning here
    # fixes all 9 usage lenses at once, so no lens re-implements the union.
    for p in sink_read_files(d, sink_name):
        # Stream line-by-line (O(1) memory regardless of sink size). errors=
        # "replace" keeps the FAIL-SOFT contract — a corrupt byte neutralizes its
        # one line instead of crashing the whole read.
        try:
            fh = open(p, "r", encoding="utf-8", errors="replace")
        except OSError:
            continue
        with fh:
            for line in fh:
                try:
                    rec = json.loads(line)
                except (ValueError, TypeError):
                    continue
                if not isinstance(rec, dict):
                    continue
                ts = parse_iso_ts(rec.get("ts", ""))
                if ts is None or ts < cutoff:
                    continue
                yield rec


def sink_read_files(telemetry_dir: Path, sink_name: str) -> list:
    """Read-side sink resolver: the exact legacy `<stem>.jsonl` plus every
    per-session shard `<stem>-<disc>.jsonl`, sorted, deduped, `.bak` excluded.
    The ONE place the shard read pattern lives — a reader that hardcodes a single
    sink name (or a `glob(...)[0]` first-match) instead of calling this is what the
    completeness guard test catches."""
    if not telemetry_dir.is_dir():
        return []
    stem, dot, ext = sink_name.rpartition(".")
    seen, out = set(), []
    legacy = telemetry_dir / sink_name
    if legacy.is_file():
        seen.add(legacy)
        out.append(legacy)
    # Shard glob must mirror sink_path's shard NAME exactly: dotted names shard
    # to "<stem>-<disc>.<ext>", a dotless name to "<name>-<disc>". Keep the two
    # in lockstep so a shard is never written to a name the reader cannot find.
    shard_glob = "%s-*.%s" % (stem, ext) if dot else "%s-*" % sink_name
    for p in sorted(telemetry_dir.glob(shard_glob)):
        if p in seen or p.name.endswith(".bak"):
            continue
        seen.add(p)
        out.append(p)
    return out


def telemetry_dir() -> Path:
    """The telemetry sink dir. Stays a pure resolver (never raises) — two
    read-side callers (discover_isolation_nudge, cook_isolation_nudge) depend
    on always getting a Path back, missing or not. Only the mkdir is guarded:
    under a global layout with no resolvable project, harness_paths.telemetry_dir()
    returns state_dir()/telemetry rooted at the fail-closed marker, and
    mkdir(parents=True) on that would materialise a directory at the FILESYSTEM
    ROOT (see harness_paths.writable_state_dir()'s docstring). Every writer here
    already swallows the resulting FileNotFoundError/OSError, so skipping the
    mkdir preserves the fail-open contract without ever touching `/`."""
    d = harness_paths.telemetry_dir()
    if harness_paths.writable_state_dir() is not None:
        d.mkdir(parents=True, exist_ok=True)
    return d


def _shard_discriminator(session):
    """Per-session sink discriminator via the SSOT in hook_runtime, or None.
    Lazy import (hook_runtime pulls harness_paths); fail-open to None so a
    resolution hiccup keeps the shared legacy sink, never breaks the write."""
    if not session:
        return None
    try:
        hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
        if str(hooks_dir) not in sys.path:
            sys.path.append(str(hooks_dir))
        import hook_runtime
        return hook_runtime.shard_discriminator(session)
    except Exception:
        return None


def sink_path(name: str, session=None) -> Path:
    """The telemetry sink path. A real session shards to `<stem>-<disc>.jsonl`
    (R2 — no pid); a sessionless write keeps the shared legacy `<stem>.jsonl`."""
    disc = _shard_discriminator(session)
    if disc is not None:
        stem, dot, ext = name.rpartition(".")
        name = "%s-%s.%s" % (stem, disc, ext) if dot else "%s-%s" % (name, disc)
    return telemetry_dir() / name


def _actor() -> str:
    global _actor_cache
    if _actor_cache is None:
        try:
            hooks_dir = Path(__file__).resolve().parent.parent / "hooks"
            if str(hooks_dir) not in sys.path:
                sys.path.append(str(hooks_dir))
            import hook_runtime
            _actor_cache = hook_runtime.resolve_actor(session_id=_SESSION)
        except Exception:
            _actor_cache = "user:unknown"
    return _actor_cache


# --- Low-volume gate ----------------------------------------------------------
# Below this many data points a usage lens shows raw counts + an
# "insufficient data" caveat and SUPPRESSES recommendations (sparse data -> noise).
LOW_VOLUME_THRESHOLD = 5


def low_volume_gate(count, threshold: int = LOW_VOLUME_THRESHOLD) -> bool:
    """True when ``count`` is below ``threshold`` → data-starved, suppress
    advice (boundary: count == threshold is NOT gated)."""
    try:
        return int(count) < int(threshold)
    except (TypeError, ValueError):
        return True  # unknown volume → treat as gated (conservative)


def disabled() -> bool:
    # Usage telemetry is off when explicitly disabled OR during a pytest run
    # (PYTEST_CURRENT_TEST is set per-test) — test runs never pollute real sinks.
    return bool(os.environ.get("HARNESS_TELEMETRY_DISABLED")
                or os.environ.get("PYTEST_CURRENT_TEST"))


def append_event(name: str, record: dict) -> None:
    """Append one enriched JSONL record to the named sink. Fail-open."""
    if disabled():
        return
    try:
        rec = dict(record)
        rec.setdefault("actor", _actor())
        # isoformat() — NOT strftime("%z"): the lens read side parses with
        # datetime.fromisoformat, which before Python 3.11 only accepts the
        # colon'd offset isoformat emits (+07:00, never +0700).
        rec.setdefault("ts", datetime.now(timezone.utc).astimezone()
                       .isoformat(timespec="seconds"))
        if _SESSION:
            rec.setdefault("session", _SESSION)
        # Serialize FIRST: a non-serializable record raises here, before any
        # file side-effect, so a bad record never leaves a half-written sink.
        line = json.dumps(rec, ensure_ascii=False) + "\n"
        # Shard AFTER session enrichment: the effective session is on the record
        # now (from the payload or the import-time _SESSION default above).
        p = sink_path(name, session=rec.get("session"))
        try:
            if p.stat().st_size > MAX_SINK_BYTES:
                p.replace(str(p) + ".bak")
        except OSError:
            pass  # sink may not exist yet — nothing to rotate
        with open(p, "a", encoding="utf-8") as fh:
            fh.write(line)
    except Exception:
        pass  # fail-open: telemetry must never break the observed op


def _dedup_marker_path(key: str) -> Path:
    # Sanitize to a safe filename; key carries its own uniqueness.
    safe = "".join(
        c if c in "ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789._|-"
        else "_" for c in str(key)
    )[:200]
    return telemetry_dir() / ".dedup" / safe


def _prune_dedup(d: Path) -> None:
    try:
        now = time.time()
        for entry in d.iterdir():
            try:
                if now - entry.stat().st_mtime > DEDUP_TTL_S:
                    entry.unlink()
            except OSError:
                pass  # skip un-stat-able / racing entries
    except OSError:
        pass  # dir may not exist yet — nothing to prune


# --- session-transcript resolver (read-side, for emit_session_summary) --------
# Claude Code keeps per-project session JSONL (the transcript) under
# ~/.claude/projects/<encoded-root>/. emit_session_summary reads it to
# reconstruct a session's shape. HARNESS_SESSIONS_DIR overrides for tests.

def project_dir() -> str:
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def _encoded_project_slug() -> str:
    """Claude Code's per-project id: the absolute repo root with every ASCII
    non-alphanumeric char mapped to '-' (verified against the shipped `claude`
    binary's slug encoder, which is `[^a-zA-Z0-9]` — NOT `'/'.replace` and NOT
    Python's Unicode-aware `str.isalnum()`, which would keep a non-ASCII letter
    the real encoder dashes). Resolved dynamically per checkout — never a
    hardcoded machine path."""
    text = project_dir()
    return "".join(c if ("a" <= c <= "z" or "A" <= c <= "Z" or "0" <= c <= "9")
                   else "-" for c in text)


def sessions_dir() -> Path:
    """Per-project session-JSONL (transcript) dir. HARNESS_SESSIONS_DIR overrides
    it (tests point it at a tmp dir). Read-side: no mkdir."""
    env = os.environ.get("HARNESS_SESSIONS_DIR")
    if env:
        return Path(env)
    # learn: reads the host Claude session-transcript directory under the user's
    # home (HARNESS_SESSIONS_DIR overrides this for tests); read-only, no mkdir.
    return Path.home() / ".claude" / "projects" / _encoded_project_slug()


# --- Bash-script duration timers (Pre/Post:Bash pairing) ----------------------
# mark_bash_start (PreToolUse:Bash) stamps a monotonic start under
# .bashtimers/<key>; track_script_execution (PostToolUse:Bash) reads + clears it
# to compute `ms`. Dumb + fail-open; lives under the (gitignored) telemetry dir.
# Monotonic is system-wide on Linux → comparable across the two hook PIDs.
#
# Key = hash of the COMMAND ONLY (session deliberately excluded): the live
# PreToolUse and PostToolUse Bash payloads do not reliably carry the same
# session id, so including it would desync the pair and drop `ms`. Keying on the
# command alone makes pairing robust; the only cost is a rare collision when the
# identical command runs concurrently — acceptable for a tool whose duration is
# explicitly "approx". `session` stays in the signatures for call-site clarity
# but is not part of the key.
_BASHTIMER_MAX = 256  # cap the timer dir; opportunistic prune over this


def _bash_timer_path(session: str, command: str) -> Path:
    key = hashlib.sha1(command.encode("utf-8")).hexdigest()[:16]
    return telemetry_dir() / ".bashtimers" / key


def _prune_bash_timers(d: Path) -> None:
    try:
        entries = list(d.iterdir())
        if len(entries) <= _BASHTIMER_MAX:
            return
        # Oldest-first; drop the excess. Stale markers are harmless (a missing
        # pair just degrades to no-`ms`), so a coarse prune is fine.
        entries.sort(key=lambda e: e.stat().st_mtime)
        for e in entries[:-_BASHTIMER_MAX]:
            try:
                e.unlink()
            except OSError:
                pass
    except OSError:
        pass


def write_bash_start(session: str, command: str) -> None:
    """Stamp a monotonic start mark for a (session, command) Bash run. Fail-open."""
    if disabled():
        return
    try:
        p = _bash_timer_path(session, command)
        p.parent.mkdir(parents=True, exist_ok=True)
        _prune_bash_timers(p.parent)
        p.write_text(repr(time.monotonic()), encoding="utf-8")
    except Exception:
        pass  # fail-open: a missing mark just means no `ms`


def read_and_clear_bash_start(session: str, command: str):
    """Return elapsed milliseconds since the matching start mark (int ≥ 0), or
    None if no mark exists / it is unreadable. Clears the mark on read so it is
    never reused. Fail-open."""
    try:
        p = _bash_timer_path(session, command)
        if not p.exists():
            return None
        try:
            start = float(p.read_text(encoding="utf-8").strip())
        except (ValueError, OSError):
            start = None
        try:
            p.unlink()
        except OSError:
            pass
        if start is None:
            return None
        return max(0, round((time.monotonic() - start) * 1000))
    except Exception:
        return None


def append_event_once(name: str, record: dict, dedup_key: str) -> None:
    """append_event guarded by a cross-process dedup marker: when two hooks
    fire for ONE logical invocation, only the first (same dedup_key) records.
    An atomic O_CREAT|O_EXCL create is the lock; FileExistsError → skip."""
    if disabled():
        return
    try:
        marker = _dedup_marker_path(dedup_key)
        marker.parent.mkdir(parents=True, exist_ok=True)
        _prune_dedup(marker.parent)
        try:
            fd = os.open(str(marker), os.O_CREAT | os.O_EXCL | os.O_WRONLY)
            os.close(fd)
        except FileExistsError:
            return  # another event already logged this invocation
        except OSError:
            pass  # any other marker error → fall through and still record
        append_event(name, record)
    except Exception:
        pass  # fail-open
