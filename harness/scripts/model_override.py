#!/usr/bin/env python3
"""model_override.py — reasoned escape marker for the model-bound gate.

Named for what it bounds, not for the one agent-type it started with. `model_guard`
enforces a bound on ANY subagent-type; a marker module still called `explore_override`
described the gate as it was two renames ago and read as Explore-only.

The (c) escape path (spike P1 ruled out an inline reason key — the Agent tool schema is
additionalProperties:false, so a stray model_reason never reaches the payload). A user or
skill that genuinely needs to cross an agent's model bound writes a session-scoped,
count-bounded, TTL'd marker with a reason; model_guard consumes it and allows the
spawn + logs. Marker mechanics are self-contained (atomic write, consume-decrement,
empty-session refusal) rather than shared with another hook.

Attribution, not authorization — the marker is a spoofable local file; it tunes the escape,
it does not authenticate anyone. Empty session => never written (an empty key would be a
single file shared across all sessions), which is exactly why a session-less AFK spawn
cannot escape via a marker (red-team F5) — that path lowers `mode` instead.

A grant is bounded on TWO axes and BOTH are reported, because whichever is hit first ends
it: a use COUNT (default 1) and an EXPIRY (default 600s, `HARNESS_MODEL_OVERRIDE_TTL`).
Measured on the live tree: 3 of 3 historical markers expired still holding 11, 7 and 9
unused counts, because a fan-out of long-running subagents outlives ten minutes. Reporting
the count alone reads as N usable spawns and is a half-truth; the caller re-grants instead
of wondering why the escape stopped working.

CLI (--session is OPTIONAL — omitted, it auto-resolves the CURRENT session from the newest
transcript, so a caller never has to hand-hunt the session id):
  model_override.py --grant  --reason "..." [--count N] [--session S]  # write marker
  model_override.py --check  [--session S]                             # allow|deny peek
  model_override.py --clear  [--session S]                             # remove marker
  model_override.py --current                                          # print resolved session id

Auto-resolve does NOT weaken the F5 refusal: F5 is enforced on the CONSUME path (the guard reads
session_id from the spawn payload; an empty payload session never matches a marker). Auto-resolve
only spares a DELIBERATE grant from hunting the id; it still yields '' (and the grant no-ops) when
no transcript is found.
"""
import argparse
import json
import os
import sys
import time
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_HOOKS = _HERE.parent / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.insert(0, str(_HOOKS))

# Renamed with the module: one spelling for one thing. Both names had exactly one
# reader (this file), and the marker directory is runtime state under the gitignored
# `harness/state/`, so nothing outside carries the old spelling. Leaving half of a
# rename behind is worse than not renaming — a stale name reads as deliberate and the
# next sweep skips it.
_ENV_TTL = "HARNESS_MODEL_OVERRIDE_TTL"
_DEFAULT_TTL = 600
_MARKER_SUBDIR = "model-override"


def _state_dir(env) -> Path:
    raw = env.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw)
    try:
        import hook_runtime
        return hook_runtime._state_dir()
    except Exception:  # noqa: BLE001 — never hard-depend on the hook module importing
        return _HERE.parent / "state"


def _safe_session(session: str) -> str:
    try:
        import hook_runtime
        return hook_runtime.safe_session_id(session)
    except Exception:  # noqa: BLE001
        return "".join(c if (c.isalnum() or c in "-_") else "_" for c in (session or "_"))


def _marker_path(session, env):
    if not session:
        return None
    return _state_dir(env) / _MARKER_SUBDIR / ("%s.json" % _safe_session(session))


_SESSION_ENV_KEYS = ("CLAUDE_CODE_SESSION_ID", "CLAUDE_SESSION_ID")


def resolve_current_session(env=None) -> str:
    """Resolve the CURRENT session id for a standalone CLI grant, so the caller never hand-hunts
    the transcript. OFFICIAL source first: the `CLAUDE_CODE_SESSION_ID` env Claude Code sets in
    the tool subprocess (exact, survives multiple concurrent sessions). FALLBACK only when that is
    absent: the stem of the newest transcript `*.jsonl` under `~/.claude/projects/<slug>/` (the
    slug maps every non-alphanumeric char of the absolute project path to '-'). The fallback is
    a best-effort heuristic — with two concurrent sessions in one project it can pick the wrong
    file, which is exactly why the env key is preferred. '' keeps the F5 refusal intact."""
    env = os.environ if env is None else env
    for k in _SESSION_ENV_KEYS:
        v = (env.get(k) or "").strip()
        if v:
            return v
    proj = env.get("CLAUDE_PROJECT_DIR") or os.getcwd()
    try:
        # ASCII-only: the real Claude Code encoder is `[^a-zA-Z0-9]` -> '-'.
        # str.isalnum() is Unicode-aware and would keep a non-ASCII letter this
        # slug dashes, diverging from the directory Claude Code actually uses.
        slug = "".join(
            c if ("a" <= c <= "z" or "A" <= c <= "Z" or "0" <= c <= "9") else "-"
            for c in os.path.abspath(proj))
        tdir = Path.home() / ".claude" / "projects" / slug
        if not tdir.is_dir():
            return ""
        newest, newest_mt = "", -1.0
        for f in tdir.glob("*.jsonl"):
            try:
                mt = f.stat().st_mtime
            except OSError:
                continue
            if mt > newest_mt:
                newest_mt, newest = mt, f.stem
        return newest
    except Exception:  # noqa: BLE001 — resolver is best-effort; '' => explicit --session needed
        return ""


def _session_or_resolve(session: str, env=None) -> str:
    """The explicit --session wins; otherwise auto-resolve the current session."""
    return session.strip() if (session or "").strip() else resolve_current_session(env)


def _ttl(env) -> int:
    raw = env.get(_ENV_TTL)
    if raw is not None:
        try:
            return max(0, int(raw))
        except (TypeError, ValueError):
            pass
    return _DEFAULT_TTL


def _atomic_write(path: Path, obj: dict) -> None:
    # Durable write: fsync'd .tmp before os.replace so a crash never leaves an empty
    # override marker (the session gate would then read no override).
    path.parent.mkdir(parents=True, exist_ok=True)
    import artifact_io
    artifact_io.atomic_write_text(path, json.dumps(obj, ensure_ascii=False))


def write_marker(session, reason, count=1, env=None, ttl=None) -> bool:
    """Write a session-scoped override marker. Returns False (writes nothing) for an empty
    session or a non-positive count."""
    env = os.environ if env is None else env
    p = _marker_path(session, env)
    if p is None:
        return False
    try:
        n = int(count)
    except (TypeError, ValueError):
        n = 0
    if n <= 0:
        return False
    life = _ttl(env) if ttl is None else max(0, int(ttl))
    _atomic_write(p, {
        "reason": str(reason or "")[:500],
        "count": n,
        "expires_ts": time.time() + life,
    })
    return True


def _read_raw(session, env):
    p = _marker_path(session, env)
    if p is None or not p.is_file():
        return None, None
    try:
        data = json.loads(p.read_text(encoding="utf-8"))
        if not isinstance(data, dict):
            p.unlink(missing_ok=True)
            return None, None
        return data, p
    except Exception:  # noqa: BLE001 — corrupt marker treated as absent
        p.unlink(missing_ok=True)
        return None, None


def _expired(data) -> bool:
    try:
        return time.time() > float(data.get("expires_ts", 0))
    except (TypeError, ValueError):
        return True


def read_marker(session, env=None):
    """Non-consuming peek. Unlinks + returns None if expired/corrupt."""
    env = os.environ if env is None else env
    data, p = _read_raw(session, env)
    if data is None:
        return None
    if _expired(data):
        p.unlink(missing_ok=True)
        return None
    return data


def consume_marker(session, env=None) -> bool:
    """True iff a valid, unexpired, count>0 marker exists for `session`; decrements count
    (atomic) and unlinks at 0. Empty/expired session => False (never allows a session-less
    or stale spawn)."""
    env = os.environ if env is None else env
    p = _marker_path(session, env)
    if p is None:
        return False
    lock_path = p.parent / (".%s.lock" % _safe_session(session))
    try:
        from register_store import register_lock
    except Exception:  # noqa: BLE001 — no lock primitive: still apply the read-modify-write
        return _consume_marker_locked(session, env)
    with register_lock(lock_path):
        return _consume_marker_locked(session, env)


def _consume_marker_locked(session, env) -> bool:
    """The read-modify-write body of consume_marker — MUST only run inside the
    per-session lock consume_marker takes: two concurrent Explore spawns for
    the SAME session each calling this unlocked would both read count=1, both
    decrement to 0, and both return True — over-granting a bounded budget."""
    data, p = _read_raw(session, env)
    if data is None:
        return False
    if _expired(data):
        p.unlink(missing_ok=True)
        return False
    try:
        count = int(data.get("count", 0))
    except (TypeError, ValueError):
        count = 0
    if count <= 0:
        return False
    count -= 1
    if count <= 0:
        p.unlink(missing_ok=True)
    else:
        data["count"] = count
        _atomic_write(p, data)
    return True


def clear_marker(session, env=None) -> None:
    env = os.environ if env is None else env
    p = _marker_path(session, env)
    if p is not None:
        try:
            p.unlink(missing_ok=True)
        except OSError:
            pass


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(
        description="Reasoned escape marker for the model-bound gate (any subagent-type). "
                    "A grant is bounded BOTH by a use count and by an expiry; whichever "
                    "runs out first ends it.",
        epilog="EXPIRY: a marker dies %d seconds after it is written (override with "
               "$%s), no matter how much count is left — so a grant covering a long "
               "fan-out may need re-granting rather than a bigger --count."
               % (_DEFAULT_TTL, _ENV_TTL))
    g = ap.add_mutually_exclusive_group(required=True)
    g.add_argument("--grant", action="store_true", help="write an override marker")
    g.add_argument("--check", action="store_true", help="print allow|deny (non-consuming)")
    g.add_argument("--clear", action="store_true", help="remove the marker")
    g.add_argument("--current", action="store_true",
                   help="print the auto-resolved current session id (or empty line)")
    ap.add_argument("--session", default="",
                    help="explicit session id; omit to auto-resolve the current session")
    ap.add_argument("--reason", default="",
                    help="why this spawn genuinely needs to cross the bound; required for "
                         "--grant, recorded in the marker (attribution, not authorization)")
    ap.add_argument("--count", type=int, default=1,
                    help="how many spawns this grant covers (default: 1 — a fan-out of N "
                         "subagents needs --count N, or the second spawn is blocked again)")
    args = ap.parse_args(argv)

    if args.current:
        sys.stdout.write("%s\n" % resolve_current_session())
        return 0

    session = _session_or_resolve(args.session)

    if args.grant:
        if not args.reason.strip():
            sys.stderr.write("--grant requires a non-empty --reason\n")
            return 1
        if not session:
            sys.stderr.write("could not resolve current session; pass --session <id> explicitly\n")
            return 1
        ok = write_marker(session, args.reason, args.count)
        # BOTH bounds, always. Reporting the count alone reads as N usable spawns, and
        # the clock is what actually ended 3 of 3 historical grants (11, 7 and 9 counts
        # left unspent). A caller who knows the deadline re-grants; one who does not
        # reads the next block as the escape being broken.
        ttl = _ttl(os.environ)
        sys.stdout.write(
            ("granted (session %s, count %d, expires in %ds — whichever runs out "
             "first ends it)\n" % (session, args.count, ttl))
            if ok else "no-op (empty session or count<=0)\n")
        return 0 if ok else 1

    if args.clear:
        clear_marker(session)
        sys.stdout.write("cleared\n")
        return 0

    data = read_marker(session)
    try:
        count = int(data.get("count", 0)) if data else 0
    except (TypeError, ValueError):
        count = 0
    if data and count > 0:
        # `allow` on its own answers "is there a grant" and hides "for how much longer",
        # which is the half a caller mid-fan-out actually needs. The first token stays
        # `allow` so anything parsing this keeps working.
        try:
            left = max(0, int(float(data.get("expires_ts", 0)) - time.time()))
        except (TypeError, ValueError):
            left = 0
        sys.stdout.write("allow (count %d, expires in %ds)\n" % (count, left))
    else:
        sys.stdout.write("deny\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
