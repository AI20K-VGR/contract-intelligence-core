#!/usr/bin/env python3
"""nudge_context_inject.py — UserPromptSubmit hook (telemetry-class) re-surfacing
turn-end nudge observations to the MODEL as additionalContext.

Several nudges record an observation at turn-end (stderr + trace) but the model
never re-reads stderr or the trace. This hook closes that loop: at a later
UserPromptSubmit it reads the latest same-session observation(s) and injects a
one-line additionalContext so the model can act. Two kinds are surfaced:

  - decision-capture (`decision_capture_observation`) -> point at /hs:remember.
  - standards-drift (`standards_drift_observation` / `..._commit_observation`)
    -> point at /hs:docs (arch/standards code changed without resyncing the
    auto-loaded prose docs).
  - memory-gap (`memory_gap_observation`) -> point at the memory-gap detail
    (H2-resolved: the model-aimed "memory_gap thường" leg; a fence_breach signal
    ALSO gets an immediate systemMessage from memory_gap_hook itself — this relay
    is the belt-and-suspenders follow-up next turn, not the only channel).
  - backlog-capture (`backlog_capture_observation`) -> point at
    backlog_register.py add (H2-resolved MEDIUM).
  - goal-cycle (`goal_cycle_observation`) -> point at the cycle_N.md breadcrumb
    convention (H2-resolved MEDIUM).

Single-shot PER KIND: each kind carries its own per-session marker (the last
surfaced ts), so surfacing one kind never suppresses the other, and neither
re-nags on every subsequent prompt. A NEWER observation supersedes its marker.

INTERACTIVE-ONLY by construction. The AFK loop drives `claude -p`, which never
fires UserPromptSubmit, so this inject is inert in an autonomous run.

Advisory only (telemetry contract): it never blocks. On any error — or when
telemetry is disabled, or no fresh observation exists — it emits no context
(fail-open: a broken inject degrades to "no reminder", never to a blocked session).
"""

import json
import os
import sys
import time
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
import hook_runtime  # noqa: E402

HOOK_CLASS = "telemetry"
NAME = "nudge_context_inject"
_EVENT = "decision_capture_observation"
_DRIFT_EVENTS = ("standards_drift_observation", "standards_drift_commit_observation")
_DRIFT_MARKER = "standards_drift"
_MEMORY_GAP_EVENTS = ("memory_gap_observation",)
_MEMORY_GAP_MARKER = "memory_gap"
_BACKLOG_EVENTS = ("backlog_capture_observation",)
_BACKLOG_MARKER = "backlog_capture"
_GOAL_CYCLE_EVENTS = ("goal_cycle_observation",)
_GOAL_CYCLE_MARKER = "goal_cycle"
_STATE_SUBDIR = "nudge-inject"


def _trace_dir() -> Path:
    return hook_runtime._state_dir() / "trace"


_TAIL_BYTES = 256 * 1024  # bound each trace-file read (observations sit at the tail)


def _tail_lines(path, max_bytes=_TAIL_BYTES):
    """The last ~max_bytes of a file as lines. Append-only traces put the newest
    records at the end, so reading the tail finds this session's latest observation
    without paying for the full (multi-week) history each prompt. A partial first
    line after the seek is dropped. Any OS error → [] (fail-open)."""
    try:
        size = path.stat().st_size
        with path.open("rb") as fh:
            if size > max_bytes:
                fh.seek(size - max_bytes)
                fh.readline()  # discard the possibly-truncated first line
            data = fh.read()
        return data.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _scan_forward_lines(path, offset, max_bytes=_TAIL_BYTES):
    """Lines from `offset` to EOF. The pointer records EOF (a line boundary) as
    the cursor, so no partial first line arises. Capped at max_bytes so a single
    turn that appended an unbounded amount of trace still reads a bounded slice —
    the pointer is a cache, never a correctness anchor. Any OS error → []."""
    try:
        size = path.stat().st_size
        if offset >= size:
            return []
        start = offset
        if size - offset > max_bytes:
            start = size - max_bytes  # bounded even on a huge forward delta
        with path.open("rb") as fh:
            fh.seek(start)
            if start != offset:
                fh.readline()  # drop the possibly-truncated first line after a re-seek
            data = fh.read()
        return data.decode("utf-8", errors="replace").splitlines()
    except OSError:
        return []


def _scan_session(lines, wanted, session_id):
    """The newest (last, append-only) record in `lines` matching an event in
    `wanted` for `session_id`, or None.

    A line that parses to something other than an OBJECT is skipped like a line
    that does not parse at all. It used to reach `rec.get(...)` and raise
    AttributeError, which escaped `_resolve` (unlike `latest_observation`, that
    path has no catch) and killed the whole inject over one malformed line — the
    opposite of this hook's telemetry-class fail-open contract. Keep this guard: it
    is also what lets the one-pass sweep below share the same blast radius as the
    per-family path it replaced."""
    best = None
    for line in lines:
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError:
            continue
        if not isinstance(rec, dict):
            continue
        if rec.get("event") in wanted and rec.get("session") == session_id:
            best = rec  # later line = newer (append-only)
    return best


def _latest_with_source(session_id, wanted, files_local, since_offset, since_file):
    """Scan `files_local` (newest-first) and return (best_record, source_path).

    R1: the `since_offset` byte cursor is applied ONLY to the file whose name
    matches `since_file` — wherever it sorts — NOT blindly to files_local[0].
    After sharding the newest-by-name file may be another session's shard, so a
    stale offset applied to the wrong file would read a garbage byte slice. Every
    other file is bounded-tail scanned. Back-compat: `since_file=None` with a
    `since_offset` keeps the legacy single-newest semantics (offset on the first
    file) for callers that pass only an offset."""
    for i, f in enumerate(files_local):
        if since_offset is not None and since_file is not None and f.name == since_file:
            lines = _scan_forward_lines(f, since_offset)
        elif since_offset is not None and since_file is None and i == 0:
            lines = _scan_forward_lines(f, since_offset)
        else:
            lines = _tail_lines(f)
        best = _scan_session(lines, wanted, session_id)
        if best is not None:
            return best, f
    return None, None


def _sweep_families(session_id, fams, files_local, pointer):
    """Resolve EVERY family in ONE pass over `files_local` (newest-first).

    `fams` is a sequence of `(family_key, wanted_events)`; `pointer` is the map
    `_read_pointer` returns. Returns `{family_key: (best_record, source_path)}`,
    the same pair `_latest_with_source` yields — for all families at once.

    ── WHY THIS EXISTS (do not "simplify" back to a call per family) ─────────────
    `core()` used to call `_latest_with_source` once per family, and each call
    re-read and re-parsed EVERY trace file. Cost was `families x files`, and both
    factors grow: families with nudge-channels.yaml, files with every new session
    (trace_log never rotates, it shards per session, and there is deliberately no
    shard manifest to consult). Measured on this repo's real 287-file store,
    returning nothing: 1.933 s per prompt at 15 families (ship config), 2.484 s at
    21 (dev override). Roughly 0.12 s per family either way — the family count IS
    the multiplier, which is what this removes.

    ── THE SELECTION RULE, PRESERVED EXACTLY ────────────────────────────────────
    Walk files newest-first; the FIRST file holding a match wins the family; inside
    that file the LAST matching line wins (append-only, so positionally last, NOT
    max-ts — they differ when a writer backdates). A family stays pending until it
    hits a file that yields something, so a cursor that consumes the newest file
    genuinely hands the win to an older one.

    ── WHY THE CURSOR PATH REPLAYS THE ORIGINAL CALL ────────────────────────────
    Each family carries its own `{file, offset}` cursor, so on one file different
    families may need different byte ranges. `_scan_forward_lines(f, off)` is
    ALMOST always a suffix of `_tail_lines(f)` — both cap at `_TAIL_BYTES` — but not
    when `off` lands exactly on the tail window's own seek point: the tail discards
    its first line as possibly-truncated, while a cursor sitting on that exact line
    boundary keeps it. Rather than reason about that boundary, a family whose cursor
    names this file is answered by calling the original pair verbatim. At most one
    file per family takes that path (a cursor names one file), and in the common
    steady state `off == EOF`, so it costs a stat and returns nothing.
    """
    wanted_by_fam = {}
    fams_by_event = {}
    order = []
    for fam, wanted in fams:
        w = tuple(wanted)
        wanted_by_fam[fam] = w
        order.append(fam)
        for ev in w:
            # Non-str event names can never match `rec.get("event") in wanted` for
            # a JSON-decoded record, so they are dropped from the index rather than
            # made hashable — keeps the dict lookup below exception-free.
            if isinstance(ev, str):
                fams_by_event.setdefault(ev, []).append(fam)

    pending = set(wanted_by_fam)
    result = {}
    for i, f in enumerate(files_local):
        if not pending:
            break  # every family answered; older files cannot change any verdict
        lines = _tail_lines(f)
        cand = {}
        for line in lines:
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or rec.get("session") != session_id:
                continue
            ev = rec.get("event")
            if not isinstance(ev, str):
                continue
            for fam in fams_by_event.get(ev, ()):
                if fam in pending:
                    cand[fam] = rec  # later line = newer, so plain overwrite
        for fam in order:
            if fam not in pending:
                continue
            cached = pointer.get(fam) or {}
            off, ptr_file = cached.get("offset"), cached.get("file")
            if off is not None and (ptr_file == f.name or (ptr_file is None and i == 0)):
                # `ptr_file is None` with an offset = a pointer written before the
                # file key existed; `_latest_with_source` puts it on files[0].
                rec = _scan_session(_scan_forward_lines(f, off),
                                    wanted_by_fam[fam], session_id)
            else:
                rec = cand.get(fam)
            if rec is None:
                continue  # stays pending: an older file may still win this family
            result[fam] = (rec, f)
            pending.discard(fam)
    for fam in pending:
        result[fam] = (None, None)
    return result


def latest_observation(session_id, trace_dir=None, events=None, since_offset=None,
                       files=None, since_file=None):
    """The newest observation in `events` for `session_id`, or None.

    `events` defaults to the decision-capture event (back-compat: existing callers
    pass only session_id / trace_dir positionally). Scans trace files newest-first
    (date-named, so filename order is chronological); within a file the last matching
    line wins (append-only). Filters by session so a prior run never leaks in.

    `since_offset` (a byte offset into the NEWEST file, from the per-session pointer)
    scans only the bytes appended since — the cheap steady-state path. Without it the
    newest file is read via its bounded tail. Either way NO full-file read happens.

    `files` (a pre-sorted newest-first list of trace paths) skips this call's own
    directory glob — core() globs the trace dir ONCE and threads the list through
    every family, instead of re-globbing per family per prompt.

    Deliberate fail-open trade-off (accepted at plan time): once an observation has been
    seen it is cached in the pointer and survives falling out of the tail window; but on
    the FIRST core() run of a session against an already-busy (or rolled-over) newest file
    — where no pointer exists yet — an observation older than the bounded tail is simply
    missed (a re-surface not shown), never recovered by a full read. The pointer is a
    cache, the trace is the SSOT, and a missed advisory degrades to "no reminder", which
    is preferable to a 4.7MB read every prompt. Never raises (fail-open)."""
    if not session_id:
        return None
    wanted = (_EVENT,) if events is None else tuple(events)
    try:
        if files is None:
            d = Path(trace_dir) if trace_dir is not None else _trace_dir()
            if not d.is_dir():
                return None
            files_local = sorted(d.glob("trace-*.jsonl"), reverse=True)
        else:
            files_local = files
        best, _ = _latest_with_source(session_id, wanted, files_local,
                                      since_offset, since_file)
        return best
    except Exception:  # noqa: BLE001 — inject must never break the prompt
        return None


# ── Read window ────────────────────────────────────────────────────────────────
# The sweep reads a tail from EVERY trace file, so its cost tracks the size of the
# archive rather than the size of the session — measured at 0.25 s per prompt over
# 319 shards / 86 MB, and the archive only grows. Both bounds below cut that link.
#
# `_SCAN_MARK_KEY` holds the wall-clock of the previous sweep. A file untouched
# since then cannot hold anything this session has not already been shown, because
# an observation is matched on `session` (see _scan_session) and therefore can only
# ever come from THIS session's own writes. That makes the mark exact, not a
# heuristic: it is the tightest correct bound available, and it holds for a session
# that runs for a week just as well as for one that runs for a minute.
#
# `_READ_WINDOW_DAYS` is the safety net for the FIRST sweep of a session, or one
# whose mark was lost. Derived, not picked: measured over 802 real sessions the p95
# session runs 12.2 h, so two days is roughly fourfold headroom, and it sits on the
# knee — widening to 7 or 14 days raises full coverage from 98.25% to 98.75% while
# reading 7x the files. Do not round it up "to be safe"; that trade was measured
# and it is a bad one.
#
# `_MTIME_SLACK_S` exists because mtime has one-second resolution: a write landing
# in the same second as the sweep would otherwise sit on the wrong side of the mark
# and be skipped forever.
_READ_WINDOW_DAYS = 2
_SCAN_MARK_KEY = "_scan_mark"
_MTIME_SLACK_S = 2


def _within_read_window(files, pointer):
    """The subset of `files` that can still hold something unseen.

    Never returns empty while `files` is non-empty: the callers below index
    `[0]` for the pointer fallback, and keeping the newest file costs about one
    millisecond while removing a whole class of empty-list edge cases. A file
    that cannot be stat'd is KEPT — a bound that drops what it cannot measure
    would silently lose observations."""
    cutoff = time.time() - _READ_WINDOW_DAYS * 86400
    mark = pointer.get(_SCAN_MARK_KEY) if isinstance(pointer, dict) else None
    if isinstance(mark, (int, float)) and not isinstance(mark, bool):
        cutoff = max(cutoff, float(mark) - _MTIME_SLACK_S)
    kept = []
    for f in files:
        try:
            if f.stat().st_mtime >= cutoff:
                kept.append(f)
        except OSError:
            kept.append(f)
    return kept or files[:1]


def _obs_pointer_path(session_id) -> Path:
    """Per-session observation-pointer cache (offset + newest record per family)."""
    return hook_runtime._state_dir() / _STATE_SUBDIR / ("%s.obs.json" % _safe_id(session_id))


def _read_pointer(session_id) -> dict:
    """The pointer map `{family: {file, offset, ts, obs}}`, or {} (fail-open:
    absent/corrupt/unreadable → empty, treated as a cache miss, never a raise)."""
    try:
        p = _obs_pointer_path(session_id)
        if not p.is_file():
            return {}
        d = json.loads(p.read_text(encoding="utf-8"))
        return d if isinstance(d, dict) else {}
    except (OSError, ValueError):
        return {}


def _write_pointer(session_id, pointer) -> None:
    """Persist the pointer map. Best-effort; a write error just means the next
    prompt pays a bounded tail scan instead of a since-offset scan."""
    try:
        p = _obs_pointer_path(session_id)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(json.dumps(pointer), encoding="utf-8")
    except OSError:
        pass


def _newer(a, b):
    """Whichever observation has the larger (ISO-8601, lexicographic) ts; the
    non-None one if only one exists; None if both are None."""
    if a is None:
        return b
    if b is None:
        return a
    return a if (a.get("ts") or "") >= (b.get("ts") or "") else b


def _safe_id(session_id) -> str:
    return hook_runtime.safe_session_id(session_id)


def _marker_path(session_id, suffix="") -> Path:
    """Per-session, per-kind marker. suffix="" keeps the original decision-capture
    filename (<sid>.txt) for on-disk back-compat; a kind suffix isolates the rest."""
    tag = (".%s" % suffix) if suffix else ""
    return hook_runtime._state_dir() / _STATE_SUBDIR / ("%s%s.txt" % (_safe_id(session_id), tag))


def _already_surfaced(session_id, ts, suffix="") -> bool:
    """True if an observation at-or-before `ts` was already surfaced this session for
    this kind (single-shot). Fail-open: no marker / a read error yields False (surface
    rather than suppress). ISO-8601 ts strings compare lexicographically in order."""
    if not ts:
        return False
    try:
        p = _marker_path(session_id, suffix)
        if not p.is_file():
            return False
        return p.read_text(encoding="utf-8").strip() >= ts
    except OSError:
        return False


def _mark_surfaced(session_id, ts, suffix="") -> None:
    """Record `ts` as the last surfaced observation for this kind. Best-effort; a
    write error never breaks the prompt (worst case: the next prompt re-surfaces)."""
    try:
        p = _marker_path(session_id, suffix)
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(ts or "", encoding="utf-8")
    except OSError:
        pass


def _subjects(note: str) -> str:
    """The subject portion of an observation note ("unrecorded_decision×N — a, b"
    -> "a, b"); the whole note if it carries no separator."""
    if not note:
        return ""
    if "—" in note:
        return note.split("—", 1)[1].strip()
    return note.strip()


def build_context(observation) -> str:
    """One-line additionalContext for a decision-capture observation."""
    subjects = _subjects((observation or {}).get("note", ""))
    detail = (": %s" % subjects) if subjects else ""
    return ("[decision-capture] An earlier turn this session shipped "
            "decision-shaped change(s) not yet in the ledger%s. Run /hs:remember "
            "to draft a DEC/memory, or record it by hand. Advisory; interactive "
            "sessions only." % detail)


def build_drift_context(observation) -> str:
    """One-line additionalContext for a standards-drift observation."""
    subjects = _subjects((observation or {}).get("note", ""))
    detail = (": %s" % subjects) if subjects else ""
    return ("[standards-drift] An earlier turn this session changed architecture/"
            "standards code without updating the auto-loaded docs "
            "(docs/system-architecture.md / docs/code-standards.md)%s. Run /hs:docs "
            "to resync if it changed the architecture or a standard. Advisory; "
            "interactive sessions only." % detail)


def build_memory_gap_context(observation) -> str:
    """One-line additionalContext for a memory-gap observation (H2-resolved,
    the model-aimed "memory_gap thường" leg — a fresh fence_breach signal ALSO
    gets an immediate systemMessage from memory_gap_hook; this is the next-turn
    follow-up regardless of signal type)."""
    note = (observation or {}).get("note", "")
    detail = (": %s" % note) if note else ""
    return ("[memory-gap] An earlier turn this session left a memory/ownership "
            "gap%s. Confirm it was intended, or close it. Advisory; interactive "
            "sessions only." % detail)


def build_backlog_context(observation) -> str:
    """One-line additionalContext for a backlog-capture observation
    (H2-resolved MEDIUM: propose-then-confirm, never auto-adds)."""
    return ("[backlog-capture] An earlier turn this session may have deferred "
            "work worth recording. Run `python3 harness/scripts/"
            "backlog_register.py add --text \"<what>\" --type <bug|chore|"
            "feature|debt> --priority <P0|P1|P2|P3>` if it is real. Advisory; "
            "interactive sessions only.")


def build_goal_cycle_context(observation) -> str:
    """One-line additionalContext for a goal-cycle observation (H2-resolved
    MEDIUM: the /goal loop is memory-blind between ticks)."""
    return ("[goal-cycle] An earlier tick ended without a cycle_N.md breadcrumb "
            "(## Done / ## Next / ## Blocker / ## Decisions — see "
            "hs:goal/references/cycle-convention.md). Drop one now if the run is "
            "still live. Advisory; interactive sessions only.")


# Names whose relay is served by a bespoke builder above — the generic pass skips
# them so a user who also lists one in nudge-channels.yaml never double-injects.
_BESPOKE_RELAY_NAMES = frozenset({
    "decision_capture", "decision_capture_nudge",
    "standards_drift", "standards_drift_nudge",
    "memory_gap", "memory_gap_hook",
    "backlog_capture", "backlog_capture_nudge",
    "goal_cycle", "goal_cycle_nudge",
})


def _bespoke_families():
    """The five hard-coded families as `(wanted_events, marker_suffix, builder)`.

    One source for both the sweep's family list and the emit loop, so a sixth family
    cannot be added to one and forgotten in the other. Declared as a function rather
    than a module constant because the builders are defined above it."""
    return (
        ((_EVENT,), "", build_context),
        (_DRIFT_EVENTS, _DRIFT_MARKER, build_drift_context),
        (_MEMORY_GAP_EVENTS, _MEMORY_GAP_MARKER, build_memory_gap_context),
        (_BACKLOG_EVENTS, _BACKLOG_MARKER, build_backlog_context),
        (_GOAL_CYCLE_EVENTS, _GOAL_CYCLE_MARKER, build_goal_cycle_context),
    )


def build_generic_relay_context(name, observation) -> str:
    """One-line additionalContext for a hook a user routed to `relay` via
    nudge-channels.yaml. The observation note already carries the hook's own
    advisory text, so surface it verbatim behind a small tag."""
    note = (observation or {}).get("note", "") or ("advisory from %s" % name)
    return "[nudge:%s] %s" % (name, note.strip())


def core(data):
    """The additionalContext to inject, or None. Surfaces each kind's newest
    observation at most once per session (newer observations supersede); when both a
    decision-capture and a standards-drift observation are fresh, both lines emit.

    Beyond the five bespoke families, ANY hook a user routes to the relay sink in
    nudge-channels.yaml is surfaced generically from its `<name>_observation`."""
    session_id = (data or {}).get("session_id") or ""
    if not session_id:
        return None
    # Glob the trace dir ONCE up front (newest-first), threaded through every family
    # so a busy prompt globs once, not 5+N times. EARLY-EXIT: no trace file means no
    # observation can exist for any family — skip the whole family + generic scan.
    try:
        d = _trace_dir()
        all_files = sorted(d.glob("trace-*.jsonl"), reverse=True) if d.is_dir() else []
    except OSError:
        all_files = []
    if not all_files:
        return None
    # Stamped BEFORE the sweep, never after: a write that lands while the sweep is
    # running must fall on the READ side of the next mark, not be skipped as older
    # than a mark taken at the end.
    scan_started = time.time()
    trace_files = _within_read_window(all_files, _read_pointer(session_id))
    newest = trace_files[0]
    newest_name = newest.name
    try:
        newest_size = newest.stat().st_size
    except OSError:
        newest_size = 0
    # One pointer read up front, one write at the end — shared across all 5 bespoke
    # families plus every relayed name, so a busy prompt costs at most a bounded tail
    # (or a since-offset delta) per family, never a full 4.7MB read.
    pointer = _read_pointer(session_id)
    new_pointer = dict(pointer)

    # Every family is resolved in ONE pass over the files (see _sweep_families).
    # The relay config is therefore read BEFORE the scan, not during it: the family
    # list has to be complete before the single pass starts. A config read that
    # fails still leaves the bespoke five to be swept — the same degradation the
    # old per-family generic loop had, just moved a few lines earlier.
    bespoke = _bespoke_families()
    fams = [(suffix or "decision", events) for events, suffix, _ in bespoke]
    generic_names = []
    try:
        for name in hook_runtime.nudge_observation_names():
            if name in _BESPOKE_RELAY_NAMES:
                continue
            generic_names.append(name)
            fams.append(("relay_%s" % name, ("%s_observation" % name,)))
    except Exception:  # noqa: BLE001 — a relay config miss must not lose the five
        pass
    swept = _sweep_families(session_id, fams, trace_files, pointer)

    def _fold(fam):
        """Merge one family's sweep result with its cached observation and advance
        its pointer. Byte-identical bookkeeping to the per-family version this
        replaced — only the source of `(fresh, src)` changed.

        R1: the offset is keyed to the FILE the observation lives in (the session's
        shard), not the newest-by-name file, which after sharding may belong to
        another session. No fresh hit → advance past the newest file's bytes
        (nothing matched there anyway) to preserve the cheap steady state."""
        fresh, src = swept.get(fam, (None, None))
        best = _newer(fresh, (pointer.get(fam) or {}).get("obs"))
        if src is not None:
            try:
                ptr_file, ptr_off = src.name, src.stat().st_size
            except OSError:
                ptr_file, ptr_off = newest_name, newest_size
        else:
            ptr_file, ptr_off = newest_name, newest_size
        new_pointer[fam] = {"file": ptr_file, "offset": ptr_off,
                            "ts": (best or {}).get("ts"), "obs": best}
        return best

    parts = []
    for events, suffix, builder in bespoke:
        obs = _fold(suffix or "decision")
        if obs is None:
            continue
        ts = obs.get("ts") or ""
        if _already_surfaced(session_id, ts, suffix):
            continue
        _mark_surfaced(session_id, ts, suffix)
        parts.append(builder(obs))
    # Generic pass: config hooks that record a model-bus observation (relay OR
    # systemMessage per-name entries), one-shot per session.
    try:
        for name in generic_names:
            suffix = "relay_%s" % name
            obs = _fold(suffix)
            if obs is None:
                continue
            ts = obs.get("ts") or ""
            if _already_surfaced(session_id, ts, suffix):
                continue
            _mark_surfaced(session_id, ts, suffix)
            parts.append(build_generic_relay_context(name, obs))
    except Exception:  # noqa: BLE001 — a relay miss must never break the prompt
        pass
    # Bookkeeping, not a family: `_fold` only ever writes keys it was handed, so this
    # reserved key rides along untouched and bounds the NEXT sweep.
    new_pointer[_SCAN_MARK_KEY] = scan_started
    _write_pointer(session_id, new_pointer)
    return "\n".join(parts) if parts else None


def _emit_context(text: str) -> None:
    sys.stdout.write(json.dumps({
        "hookSpecificOutput": {
            "hookEventName": "UserPromptSubmit",
            "additionalContext": text,
        }
    }))
    sys.stdout.flush()


def run(raw=None) -> None:
    """Telemetry-class, fail-open. Enabled + a fresh observation exists -> inject;
    disabled / no observation / any error -> plain continue. Never exits 2."""
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(NAME, HOOK_CLASS):
            text = core(data)
            if text:
                _emit_context(text)
                return
    except Exception as e:  # noqa: BLE001 — injection must never break the session
        hook_runtime.log_hook_error(NAME, e)
    hook_runtime.emit_continue()


def main(raw=None) -> None:
    run(raw=raw)


if __name__ == "__main__":
    main()
