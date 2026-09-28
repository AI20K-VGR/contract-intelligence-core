#!/usr/bin/env python3
"""spawn_provenance.py — shared reader/counter for Agent|Task spawn provenance.

Backs BOTH Layer-1a (`spawn_provenance_nudge`, advisory, ships default-off)
and Layer-1b (`spawn_provenance_guard`, the BLOCK form, opt-in via
`block_enabled()`): a per-session_id, windowed, append-only counter of
subagent spawns, plus a reader for the orchestrate strategy token
`run_state.write_token` mints at the workflow-orchestrate APPROVAL step.
Layer-1a nudges toward `hs:workflow-orchestrate` on an un-planned wide
fan-out; Layer-1b enforces a resolved spawn BUDGET (`window_start()` +
`budget()` — the token-lifecycle decision in
plans/reports/spawn-provenance-token-lifecycle-sequential-thinking-260716.md):
BLOCK iff `count_in_window(session, since_ts=window_start(session)) >=
budget(session)`.

Store: `<state_dir>/spawn-provenance/spawns.jsonl` — one line per recorded
spawn, `{session, tool_use_id, actor, ts}` (`ts` an epoch float). Append-only;
the ONE exception is the bounded truncation in `record_spawn` (a maintenance
rewrite of the whole file when the cap is crossed, NOT a per-record
read-modify-write of a count). An empty or missing `session_id` is bucketed
under the literal `""` key — a distinct "unknown" bucket, NEVER merged into a
real session's count (mirrors `model_guard`'s `session_id or ""`
empty-string bucketing). `tool_use_id`, when carried, dedups the SAME spawn
recorded by both the nudge and the guard (both hang off the same
`PreToolUse:Agent|Task` group) into one counted event.

Counter order (M6): a hook calls `count_in_window()` BEFORE `record_spawn()`
— the returned count is the PRIOR count, so the spawn currently in flight is
never counted against itself (a hook firing for the 6th spawn sees prior=5,
not 6).

Fail-open throughout: every reader degrades to its safe default (0 / False /
0.0 / the default threshold) on any error — a broken counter must never wedge
a spawn, whether backing a nudge or (via the caller's own fail-open wrapper,
see `spawn_provenance_guard`'s F4 skeleton) a gate.
"""
import json
import os
import re
import sys
import time
from pathlib import Path


def _yaml_load(text):
    """The one shared YAML read (yaml_io.py, ruamel.yaml, C-accelerated) — see
    that module's docstring for why ruamel replaced PyYAML and hook_runtime.py
    for the parse-cost measurements.

    This module sits on a per-EVENT path, so its parse cost is paid per tool
    call / prompt, not once per CLI run. `import yaml_io` stays lazy and is a
    same-directory sibling import (harness/scripts/), so this file stays
    runnable as a standalone CLI without the hooks dir on sys.path.
    """
    import yaml_io
    return yaml_io.yaml_load(text)

_HERE = os.path.dirname(os.path.abspath(__file__))
if _HERE not in sys.path:  # scripts dir already contains this file; harness_paths is a sibling
    sys.path.insert(0, _HERE)
_HOOKS = os.path.join(os.path.dirname(_HERE), "hooks")
if _HOOKS not in sys.path:
    sys.path.insert(0, _HOOKS)

_REL_YAML = ("data", "spawn-provenance.yaml")
_ENV_CONFIG_OVERRIDE = "HARNESS_SPAWN_PROVENANCE"
_DEFAULT_THRESHOLD = 8
_DEFAULT_SUB_COUNT_CAP = 32
_DEFAULT_TOKEN_TTL_SECONDS = 1800
_DEFAULT_UNTICKETED_WINDOW_SECONDS = 60
_STORE_REL = ("spawn-provenance", "spawns.jsonl")
_TOKEN_REL = ("orchestrate",)
_TOKEN_FILE = "token.json"
# Bounded scan cap (M6): a PreToolUse hook runs on EVERY delegation, so the
# per-spawn scan of the store must stay O(cap), never O(all spawns ever).
_MAX_LINES = 500
# How far past the cap the store may drift before a trim runs. Without it the
# trim fires on EVERY append once the cap is reached — measured: at 500 lines,
# every record rewrote all 500, and two threads recording 100 spawns across that
# boundary lost 16 of them. The docstring below called that rewrite "bounded
# maintenance, NOT a per-record read-modify-write"; hysteresis is what makes the
# sentence true instead of aspirational.
_MAX_SLACK = 100


def _config_path(env=None) -> Path:
    env = os.environ if env is None else env
    raw = env.get(_ENV_CONFIG_OVERRIDE)
    if raw:
        return Path(raw)
    return Path(__file__).resolve().parent.parent.joinpath(*_REL_YAML)


def _load_config(env=None) -> dict:
    """Parse spawn-provenance.yaml. Missing/malformed/no-PyYAML => {} (every
    caller goes permissive). Never raises."""
    try:
        p = _config_path(env)
        if p.is_file():
            raw = _yaml_load(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001 — malformed config degrades to permissive
        pass
    return {}


def _state_dir(env=None) -> Path:
    """The state root. `HARNESS_STATE_DIR` wins (mirrors
    `harness_paths.state_dir()`'s own precedence — this is the same seam, not
    a competing one); else delegate to `harness_paths.state_dir()`."""
    env = os.environ if env is None else env
    raw = env.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    try:
        import harness_paths
        return harness_paths.state_dir()
    except Exception:  # noqa: BLE001 — never let a path helper wedge a spawn
        return Path("harness") / "state"


def _store_path(env=None) -> Path:
    return _state_dir(env).joinpath(*_STORE_REL)


def _bucket(session) -> str:
    """Empty/missing/non-str session -> the literal "" bucket (a distinct
    "unknown" bucket, never merged into a real session's count)."""
    return session if isinstance(session, str) else ""


def threshold(env=None) -> int:
    """spawn-provenance.yaml `threshold:` (default 8 == shipped). Fail-open on
    a missing/malformed config — mirrors `model_policy`'s fail-open reader.
    The default matches the shipped value on purpose: this gate fails toward
    OVER-block, so degrading to a stricter code default would resurrect the
    over-count misfire. `HARNESS_SPAWN_PROVENANCE` (whole-file override) is the
    test seam."""
    cfg = _load_config(env)
    v = cfg.get("threshold")
    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
        return v
    return _DEFAULT_THRESHOLD


def block_enabled(env=None) -> bool:
    """spawn-provenance.yaml `block_enabled:` — the Layer-1b flip switch.
    Fail-open -> False (stays False until Layer-1b resolves EP0 + the token
    lifecycle; no guard/token-producer exists yet regardless of this value)."""
    cfg = _load_config(env)
    return cfg.get("block_enabled") is True


def record_spawn(session, tool_use_id=None, env=None, run_id=None,
                 subagent_type=None) -> None:
    """Append one `{session, tool_use_id, run_id, subagent_type, actor, ts}` line for `session`
    (bucketed via `_bucket`). `ts` is an epoch float (Layer-1b needs a
    numeric timestamp to compare against a token's `ts`/`expires_at`).
    `tool_use_id`, when a non-empty string, lets `count_in_window` dedup the
    SAME spawn recorded by both the Layer-1a nudge and the Layer-1b guard
    (both hang off the same `PreToolUse:Agent|Task` group) into one count; a
    missing/empty id (older callers, or a payload with none) always counts
    on its own — backward-compatible with every pre-Layer-1b caller.
    Best-effort/fail-open: never raises. When the append would push the
    store past `_MAX_LINES`, rewrite the file once keeping only the most
    recent `_MAX_LINES` lines (a bounded maintenance rewrite, NOT a
    per-record read-modify-write of a count — see module docstring).

    `run_id` + `subagent_type` are what let a later reader ask "did a spawn
    attributable to THIS `hs-run <domain> prompt <role>` call actually happen,
    and was it the role that call asked for?" — turning `hs_run_cook.py`'s own
    "session-transcript fact, not a disk fact" admission into a disk fact. Both
    are recorded as an explicit `null` when absent rather than omitted: an
    ABSENT key is ambiguous between a record written before these fields existed
    and a spawn nobody could attribute, and the reader downstream must keep
    "not provable" apart from "no spawn happened".

    `subagent_type` is not optional decoration. Without it the ledger proves only
    that SOMETHING was spawned after the call, so a model that spawns an
    unrelated agent and then calls `record` still passes — the laundering the
    check exists to catch, surviving the check.

    Non-string values coerce to `None` rather than raising: this is the telemetry
    class, it WRITES and does not judge. A recorder that could refuse a spawn
    because a field looked wrong would have become a gate."""
    try:
        import hook_runtime
        bucketed = _bucket(session)
        rec = {
            "session": bucketed,
            "tool_use_id": tool_use_id if isinstance(tool_use_id, str) and tool_use_id else None,
            "run_id": run_id if isinstance(run_id, str) and run_id else None,
            "subagent_type": (subagent_type
                              if isinstance(subagent_type, str) and subagent_type else None),
            "actor": hook_runtime.resolve_actor(bucketed or None),
            "ts": time.time(),
        }
        line = json.dumps(rec, ensure_ascii=False)
        p = _store_path(env)
        import harness_paths  # local: this module never lets a path helper wedge a spawn
        if harness_paths.data_root_unresolved(p.parent.parent):
            return  # unresolved root: never materialise the marker at /
        p.parent.mkdir(parents=True, exist_ok=True)
        # Append and trim share ONE exclusive lock. Locking only the trim would
        # leave the window this store lost records through: the trim writes back
        # text it read before a concurrent append landed.
        import register_store
        with register_store.register_lock(p.with_suffix(p.suffix + ".lock")):
            with open(p, "a", encoding="utf-8") as fh:
                fh.write(line + "\n")
            _trim_store(p)
    except Exception:  # noqa: BLE001 — fail-open: a broken counter never wedges a spawn
        pass


def _trim_store(p) -> None:
    """Bound the store WITHOUT a per-append rewrite of the whole file.

    Hysteresis: the file may run past `_MAX_LINES` up to `_MAX_SLACK` before a
    rewrite happens, so the "occasional maintenance" the caller's docstring
    promises is one rewrite per `_MAX_SLACK` records rather than one per record.
    The NEWEST lines are kept — this store answers "did a spawn JUST happen", so
    trimming the new end would delete precisely the evidence anyone asks for.

    Callers hold the append lock; this never takes one of its own."""
    try:
        lines = Path(p).read_text(encoding="utf-8", errors="replace").splitlines()
    except OSError:
        return
    if len(lines) <= _MAX_LINES + _MAX_SLACK:
        return
    import register_store
    register_store.atomic_write(Path(p), "\n".join(lines[-_MAX_LINES:]) + "\n")


def has_spawn(*, session, run_id, subagent_type, env=None):
    """Did a Task spawn of `subagent_type` happen for this session, attributable
    to `run_id`?

    TRI-STATE, and the third state is the load-bearing one:
      True  — a matching record is on disk.
      False — the store was READ and holds no match (includes "store absent",
              which is a real read: nothing was ever recorded).
      None  — the store could not be read at all (a directory at the path, a
              permission error). "I could not look" is NOT "it did not happen",
              and a caller that conflates them turns a strict gate into a wrong
              one. This distinction was in the consumer's hand-rolled loop and
              had to be carried over deliberately — collapsing it to False was
              the first thing this refactor broke.

    The query belongs HERE, beside the writer that decides what a record looks
    like. `hs_run_cook` used to reach past this module into `_store_path()` and
    walk the lines itself — a fourth hand-written parser of a format this module
    owns, agreeing with the writer only by coincidence.

    Never raises: the caller's whole contract is that absence of evidence is not
    evidence of absence, and an exception would turn a soft answer hard."""
    try:
        p = _store_path(env)
        if p.exists() and not p.is_file():
            return None       # something is AT the path but is not a readable file
        if not p.is_file():
            return False
        try:
            text = p.read_text(encoding="utf-8", errors="replace")
        except OSError:
            return None       # exists, is a file, and still cannot be read
        for line in text.splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                rec = json.loads(line)
            except Exception:  # noqa: BLE001 — a torn line must not drop its neighbours
                continue
            if (isinstance(rec, dict)
                    and rec.get("run_id") == run_id
                    and rec.get("session") == _bucket(session)
                    and rec.get("subagent_type") == subagent_type):
                return True
        return False
    except Exception:  # noqa: BLE001 — an unexpected fault is "could not look"
        return None


def count_in_window(session, since_ts=None, exclude_tool_use_id=None, env=None) -> int:
    """Scan-derived PRIOR count of spawns recorded for `session` (the empty
    bucket counts only against itself — never merged with a real session).

    `since_ts`, when given (Layer-1b's `window_start()`), excludes any
    record whose `ts` is older than it — a stale pre-epoch burst never trips
    today's budget. Omitted (the P7-1a nudge's no-arg call) => no filter,
    unchanged behavior.

    `exclude_tool_use_id`, when given a non-empty string, drops EVERY record
    carrying that `tool_use_id` from the count outright (not just dedup —
    excluded). This is what restores the M6 invariant ("the in-flight spawn
    is never counted against itself") for `spawn_provenance_guard.core()`
    regardless of intra-dispatch ordering: the dispatcher runs the
    Layer-1a nudge (nudge class) BEFORE this guard (compliance class,
    hook_dispatch.py's non-compliance-first ordering), so by the time the
    guard reads the count the nudge has ALREADY recorded the in-flight
    spawn under the same `tool_use_id` — without this exclusion that record
    counts as "prior", turning budget N into N-1 (F1). The guard passes its
    own `tool_use_id` here; the nudge's own no-arg call never does, so this
    is a no-op for every caller that omits it (backward-compatible).

    Dedup: records sharing the same non-empty `tool_use_id` (and not
    excluded) count ONCE (the P7-1a nudge and the P7-1b guard both record
    the same spawn off the same `PreToolUse:Agent|Task` group) — a record
    with no `tool_use_id` (older callers) always counts on its own.

    Fail-open -> 0 on any error (missing/corrupt store, bad line…)."""
    try:
        p = _store_path(env)
        if not p.is_file():
            return 0
        want = _bucket(session)
        exclude = exclude_tool_use_id if isinstance(exclude_tool_use_id, str) and exclude_tool_use_id else None
        seen_ids = set()
        count = 0
        for raw_line in p.read_text(encoding="utf-8").splitlines():
            raw_line = raw_line.strip()
            if not raw_line:
                continue
            try:
                rec = json.loads(raw_line)
            except ValueError:
                continue
            if not isinstance(rec, dict) or _bucket(rec.get("session")) != want:
                continue
            if since_ts is not None:
                ts = rec.get("ts")
                if not isinstance(ts, (int, float)) or ts < since_ts:
                    continue  # older than the window, or an unparseable ts -> excluded
            tid = rec.get("tool_use_id")
            if exclude is not None and isinstance(tid, str) and tid == exclude:
                continue  # the in-flight spawn (recorded by the nudge under this id) — never counts against itself
            if isinstance(tid, str) and tid:
                if tid in seen_ids:
                    continue  # already counted this spawn (nudge + guard dedup)
                seen_ids.add(tid)
            count += 1
        return count
    except Exception:  # noqa: BLE001 — fail-open
        return 0


def _find_active_token(session, env=None):
    """Scan `<state_dir>/orchestrate/*/token.json` for the ACTIVE (session
    match, not expired) token with the LARGEST numeric `ts` — the
    most-recent active token. Shared by `has_orchestrate_token` (bool),
    `load_active_token` (dict), `budget()`, and `window_start()`'s
    active-token branch, so every reader walks the SAME token dir + expiry
    rule and selects the SAME token when a session has 2+ active tokens
    (N1 — `window_start` and `budget` used to read from different
    selectors, a session with 2+ active tokens could pair one token's
    epoch with a DIFFERENT token's sub_count). A token with a non-numeric
    `ts` cannot be ordered and falls back to "first active match in
    iterdir order" only when NO candidate has a comparable `ts` (preserves
    the original single-token behavior when `ts` is missing/malformed).
    Returns the parsed token dict, or None. Fail-open -> None on any
    error."""
    try:
        root = _state_dir(env).joinpath(*_TOKEN_REL)
        if not root.is_dir():
            return None
        want = _bucket(session)
        now = time.time()
        best = None
        best_ts = None
        fallback = None  # first active match with no comparable ts
        for run_dir in sorted(root.iterdir()):
            token_path = run_dir / _TOKEN_FILE
            if not token_path.is_file():
                continue
            try:
                tok = json.loads(token_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — a corrupt token is not a valid token
                continue
            if not isinstance(tok, dict) or _bucket(tok.get("session")) != want:
                continue
            expires = tok.get("expires_at")
            if isinstance(expires, (int, float)) and expires < now:
                continue  # expired token — not active
            ts = tok.get("ts")
            if isinstance(ts, (int, float)):
                if best_ts is None or ts > best_ts:
                    best_ts, best = ts, tok
            elif fallback is None:
                fallback = tok
        return best if best is not None else fallback
    except Exception:  # noqa: BLE001 — fail-open
        return None


def has_orchestrate_token(session, env=None) -> bool:
    """Reader-only seam for Layer-1b: True iff an active (non-expired)
    orchestrate strategy token is on record for `session`. No producer writes
    a token yet — Layer-1b (gated on EP0 + a resolved token lifecycle) lands
    the writer at `<state_dir>/orchestrate/<run_id>/token.json`; this reader
    exists NOW so 1b only has to add the write side. Returns False in
    practice today (no token dir is ever created). Fail-open -> False."""
    return _find_active_token(session, env) is not None


def load_active_token(session, env=None):
    """P9 seam: the active (non-expired) orchestrate strategy token dict for
    `session`, or None. Same scan + expiry rule as `has_orchestrate_token`
    (via `_find_active_token`) — this is what the P9 Stop-hook audit reads to
    get at the VL-3 `groups`/`report_dir` fields the boolean reader discards.
    Fail-open -> None on any error; inert today (no token producer exists
    yet, same as `has_orchestrate_token`)."""
    return _find_active_token(session, env)


def _most_recent_token(session, env=None):
    """Scan `<state_dir>/orchestrate/*/token.json` for the token whose
    `session` matches `session` with the LARGEST numeric `ts` — active OR
    expired (unlike `_find_active_token`, which drops an expired match). This
    is what `window_start()` needs to resolve the expired-token epoch case
    (`T_epoch = token.expires_at`). A token with a non-numeric `ts` is
    skipped (it cannot be ordered). Fail-open -> None on any error."""
    try:
        root = _state_dir(env).joinpath(*_TOKEN_REL)
        if not root.is_dir():
            return None
        want = _bucket(session)
        best = None
        best_ts = None
        for run_dir in sorted(root.iterdir()):
            token_path = run_dir / _TOKEN_FILE
            if not token_path.is_file():
                continue
            try:
                tok = json.loads(token_path.read_text(encoding="utf-8"))
            except Exception:  # noqa: BLE001 — a corrupt token is not a valid token
                continue
            if not isinstance(tok, dict) or _bucket(tok.get("session")) != want:
                continue
            ts = tok.get("ts")
            if not isinstance(ts, (int, float)):
                continue
            if best_ts is None or ts > best_ts:
                best_ts, best = ts, tok
        return best
    except Exception:  # noqa: BLE001 — fail-open
        return None


def window_start(session, env=None) -> float:
    """Layer-1b `T_epoch`: the point in time a spawn budget starts counting
    from, per the resolved token lifecycle:

      - active token (session match, now < expires_at) -> token.ts
      - expired token on record for the session         -> token.expires_at
      - no token ever for the session -> `now - unticketed_window_seconds()`
        (a sliding wall-clock window — the un-ticketed budget counts spawns in
        the last W seconds, NOT cumulatively since session start; a record
        older than W ages out of `count_in_window`'s `since_ts` filter)

    The active-token branch reads via `_find_active_token` — the SAME
    most-recent-active selector `budget()` reads — so the two can never
    pair a mismatched token when a session has 2+ active tokens (N1). Only
    when NO active token exists does this fall back to `_most_recent_token`
    (active-or-expired, by ts) to resolve the expired-token epoch case.

    A record's `ts >= window_start(...)` is what `count_in_window`'s
    `since_ts` filters on. Fail-open -> 0.0 (the widest, safest window) on
    any error or an unusable token shape."""
    try:
        tok = _find_active_token(session, env)
        if isinstance(tok, dict):
            ts = tok.get("ts")
            return float(ts) if isinstance(ts, (int, float)) else 0.0
        tok = _most_recent_token(session, env)
        if not isinstance(tok, dict):
            # No token ever for this session: the un-ticketed lane windows by
            # wall-clock time. Only spawns in the last W seconds count, so a
            # legitimate sequential SDLC flow (cook -> test -> review -> ...)
            # never accumulates a session-lifetime count that wedges the 6th
            # child (the bug this replaces: a fixed 0.0 epoch counted EVERY
            # spawn ever recorded this session).
            return time.time() - unticketed_window_seconds(env)
        expires = tok.get("expires_at")
        if not isinstance(expires, (int, float)):
            return 0.0
        return float(expires)
    except Exception:  # noqa: BLE001 — fail-open
        return 0.0


def budget(session, env=None) -> int:
    """Layer-1b `B`: the spawn budget for `session` — `min(active
    token.sub_count, sub_count_cap())` when an active (non-expired) token is
    on record, else the un-ticketed `threshold()`. Clamped to the cap even
    when the token itself claims more (defense in depth against a forged or
    stale-large `sub_count`). Fail-open -> `threshold()` on any error."""
    try:
        tok = _find_active_token(session, env)
        if isinstance(tok, dict):
            sc = tok.get("sub_count")
            if isinstance(sc, int) and not isinstance(sc, bool) and sc > 0:
                return min(sc, sub_count_cap(env))
        return threshold(env)
    except Exception:  # noqa: BLE001 — fail-open
        return threshold(env)


def sub_count_cap(env=None) -> int:
    """spawn-provenance.yaml `sub_count_cap:` (default 32) — the hard width
    ceiling an orchestrate token's `sub_count` is clamped to, so a forged or
    stale-huge token can never bless an unbounded fan-out. Fail-open on a
    missing/malformed config (mirrors `threshold()`)."""
    cfg = _load_config(env)
    v = cfg.get("sub_count_cap")
    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
        return v
    return _DEFAULT_SUB_COUNT_CAP


def token_ttl_seconds(env=None) -> int:
    """spawn-provenance.yaml `token_ttl_seconds:` (default 1800 = 30min) —
    how long a minted orchestrate token stays active before it expires and
    the budget reverts to the un-ticketed `threshold()`. Fail-open on a
    missing/malformed config (mirrors `threshold()`)."""
    cfg = _load_config(env)
    v = cfg.get("token_ttl_seconds")
    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
        return v
    return _DEFAULT_TOKEN_TTL_SECONDS


def unticketed_window_seconds(env=None) -> int:
    """spawn-provenance.yaml `unticketed_window_seconds:` (default 60) — the
    sliding wall-clock window, in SECONDS, for the un-ticketed (no-token)
    spawn lane. `window_start()`'s no-token branch returns `now - W`, so the
    budget becomes "N spawns in the last W seconds" instead of a cumulative
    count since session start (the misfire this replaces: a fixed 0.0 epoch
    let a legitimate sequential flow accumulate to the budget and hard-block).
    Fail-open on a missing/malformed config (mirrors `token_ttl_seconds()`)."""
    cfg = _load_config(env)
    v = cfg.get("unticketed_window_seconds")
    if isinstance(v, int) and not isinstance(v, bool) and v > 0:
        return v
    return _DEFAULT_UNTICKETED_WINDOW_SECONDS


_AGENT_CALL_RE = re.compile(r'\bagent\s*\(')
_ARRAY_CALL_RE = re.compile(r'\b(?:parallel|pipeline)\s*\(\s*\[')
# Two spellings that state the width as an integer in the source. Neither is the
# runtime-computed fan-out the honest ceiling below is about — the number is right
# there to be read, and both used to come back as width 1, so a call declaring
# twenty agents was indistinguishable from one declaring a single agent.
# Anchored on the spawn, not on the number. An unanchored `length:\s*(\d+)` scan read
# `const cfg = {length: 42}` as a 42-wide fan-out and blocked a call that spawns one —
# a false positive that costs more than the miss it closed, because it refuses work
# that was never wide. Both patterns now require an `agent(`/`parallel(`/`pipeline(`
# within the same construct: `Array.from({length: N}, ...)` must reach a spawn inside
# its own mapper, and a counted `for` must contain one in its body.
_LENGTH_LITERAL_RE = re.compile(
    r'\blength\s*:\s*(\d+)\s*\}[^;\n]{0,200}?(?:agent|parallel|pipeline)\s*\(', re.S)
_COUNTED_LOOP_RE = re.compile(
    r'\bfor\s*\([^;]*;\s*[A-Za-z_$][\w$]*\s*<=?\s*(\d+)\s*;[^{]*\{'
    r'[^}]*?(?:agent|parallel|pipeline)\s*\(', re.S)


def _split_top_level(body: str) -> list:
    """Best-effort array-literal item splitter for `workflow_width`: split
    `body` on depth-0 commas, treating `(`/`[`/`{` as one shared nesting
    level (this is a bracket-balance scan, NOT a real JS/TS parser — string
    literals containing a bare comma or bracket can still mislead it, which
    is why the caller treats the result as an estimate, not ground truth).
    An empty/whitespace-only body returns []."""
    items = []
    depth = 0
    current = []
    for c in body:
        if c in "([{":
            depth += 1
            current.append(c)
        elif c in ")]}":
            depth -= 1
            current.append(c)
        elif c == "," and depth == 0:
            items.append("".join(current))
            current = []
        else:
            current.append(c)
    tail = "".join(current)
    if tail.strip():
        items.append(tail)
    return [it for it in items if it.strip()]


def workflow_width(script) -> int:
    """Ask-3 Layer-2 (P8): a STATIC-PARSE estimate of a `Workflow` tool
    call's declared fan-out width, read from the FULL `tool_input.script`
    text — WP1-verified (plans/260715-0021-subagent-spawn-guards-and-
    reinject/probes/WP1-workflow-pretooluse.md): CC delivers the whole
    script string, not a structured width arg, so this is a text scan, not
    a field read.

    Two heuristics, the caller gets the larger (the "best static estimate"):
      - count `agent(` call occurrences — covers `parallel([()=>agent(),
        ()=>agent()])`, where every fan-out unit IS its own agent() call;
      - for a `parallel([...])` / `pipeline([...], ...)` call whose FIRST
        argument is an array LITERAL, count its top-level comma-separated
        items — covers the one-mapper-fn-many-items shape (e.g.
        `pipeline(['a','b','c'], (item) => agent(item))`) that the raw
        agent(-count regex cannot see (only 1 literal `agent(` there, but 3
        agents actually spawn).

    HONEST CEILING (documented, not hidden): this NEVER executes the
    script — a dynamic fan-out (`for (const x of items) agent(x)` over a
    runtime-computed `items`) cannot be counted exactly by a static parse,
    and this function does not try; it returns the best static estimate
    only. Fail-open -> 0 on any error, non-string, or empty/whitespace-only
    input — a 0 width never blocks a caller that guards on
    `width > budget`."""
    try:
        if not isinstance(script, str) or not script.strip():
            return 0
        agent_count = len(_AGENT_CALL_RE.findall(script))
        array_count = 0
        for m in _ARRAY_CALL_RE.finditer(script):
            start = m.end() - 1  # index of the opening '['
            depth = 0
            end = None
            i = start
            while i < len(script):
                c = script[i]
                if c == '[':
                    depth += 1
                elif c == ']':
                    depth -= 1
                    if depth == 0:
                        end = i
                        break
                i += 1
            if end is None:
                continue  # unbalanced brackets — skip this call, not fatal
            items = _split_top_level(script[start + 1:end])
            if items:
                array_count = max(array_count, len(items))
        # A stated integer beats the call count: `Array.from({length: 20}, ...)`
        # holds ONE literal `agent(`, and the twenty is the number that matters.
        # Capped at a sane ceiling so a `length: 999999` typo reports a width the
        # gate can act on rather than an overflow-shaped number in a block reason.
        declared = [int(m) for m in _LENGTH_LITERAL_RE.findall(script)]
        declared += [int(m) for m in _COUNTED_LOOP_RE.findall(script)]
        stated = min(max(declared), 10000) if declared else 0
        return max(agent_count, array_count, stated)
    except Exception:  # noqa: BLE001 — fail-open: a parse error never blocks a caller
        return 0


def groups_missing_early_write(token) -> list:
    """P9: for a VL-3-shaped orchestrate token
    (`{mode, sub_count, groups:[{key,...}], report_dir, session, ts, run_id}`),
    return the declared `groups[*].key` values with NO early-written finding
    file under `report_dir` — a file whose name CONTAINS the key
    (case-insensitive) counts as that group's early-write. This is a
    file-PRESENCE heuristic only; it approximates "grouping happened", it
    does not judge whether the grouping was the right semantic cut.

    Fail-open -> [] (nothing to flag) on a malformed token, a missing
    `report_dir`/`groups`, or an unreadable `report_dir` — this backs a
    Stop-hook OBSERVATION audit, never a gate, so an ambiguous token must
    never manufacture a false "missing" flag. Never raises."""
    try:
        if not isinstance(token, dict):
            return []
        groups = token.get("groups")
        report_dir = token.get("report_dir")
        if not isinstance(groups, list) or not groups or not report_dir:
            return []
        keys = [g["key"] for g in groups
                if isinstance(g, dict) and isinstance(g.get("key"), str) and g["key"]]
        if not keys:
            return []
        rdir = Path(report_dir)
        if not rdir.is_dir():
            return []
        try:
            names = [p.name.lower() for p in rdir.iterdir() if p.is_file()]
        except OSError:  # noqa: BLE001 — an unreadable dir listing degrades to "nothing to flag"
            return []
        return [k for k in keys if not any(k.lower() in n for n in names)]
    except Exception:  # noqa: BLE001 — fail-open; this backs an observation, not a gate
        return []
