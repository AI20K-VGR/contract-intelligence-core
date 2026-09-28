#!/usr/bin/env python3
"""engine_skew_nudge.py — SessionStart courier health advisory (nudge, fail-open).

Under the courier / global layout, three things can silently rot a session:
  1. UNRESOLVED — the engine home was deleted or the env lost, so the guards have
     no engine to resolve. Checked on the env-value path's .exists()+marker, NOT on
     bin_root() truthiness (it always returns a path when the env is set — F7).
  2. INTEGRITY  — the engine home is corrupt at the SAME version (a flipped byte),
     which a version compare is blind to (F8). Checked via the manifest hash.
  3. SKEW       — a newer plugin cache has not been applied to the engine home yet.

All three are ADVISORY (DEC handshake downgrade): a one-line nudge pointing at
`harness upgrade` / `harness doctor`, never a block. Fires ONCE per session.

Self-host (HARNESS_BIN_ROOT UNSET): silent, zero new behavior.

Dispatched via the SessionStart group. The once-per-session gate lives in core()
because the dispatcher calls the registered entry DIRECTLY, bypassing any main/run
gating (a known dispatcher trap). Visibility {model,user,stderr} is config-driven
via nudge-channels.yaml.
"""
import glob
import json
import os
import sys
import tempfile
from pathlib import Path

from packaging.version import InvalidVersion, Version

sys.path.append(os.path.dirname(os.path.abspath(__file__)))
sys.path.append(str(Path(__file__).resolve().parent.parent / "scripts"))
import hook_runtime  # noqa: E402

HOOK_CLASS = "nudge"
_NAME = "engine_skew_nudge"
_MARKERS = ("harness/manifest.json", "harness/hooks")


def _temp_dir() -> Path:
    return Path(os.environ.get("TMPDIR") or tempfile.gettempdir())


def _flag_path(session_id: str) -> Path:
    return _temp_dir() / ("harness-engine-skew-%s" % hook_runtime.safe_session_id(session_id))


def _already_nudged(session_id: str) -> bool:
    return _flag_path(session_id).exists()


def _mark_nudged(session_id: str) -> None:
    try:
        _flag_path(session_id).write_text("1", encoding="utf-8")
    except Exception:  # noqa: BLE001 — best-effort once-per-session guard
        pass


def _read_version(release_json: Path):
    try:
        return json.loads(release_json.read_text(encoding="utf-8")).get("harness_version")
    except Exception:  # noqa: BLE001
        return None


def _home_root_and_version():
    raw = os.environ.get("HARNESS_BIN_ROOT")
    if not raw:
        return None, None
    root = Path(raw)
    return root, _read_version(root / "harness" / "release.json")


def _root_unresolved(root: Path) -> bool:
    try:
        if not root.exists():
            return True
        return not any((root / m).exists() for m in _MARKERS)
    except Exception:  # noqa: BLE001
        return True


def _integrity_drift(root: Path) -> int:
    """Count of hard manifest drifts in the engine home (0 = clean). Fail-open: any
    error returns 0 (the nudge stays silent rather than crying wolf)."""
    try:
        import verify_install
        problems = verify_install.verify(Path(root).resolve())
        hard, _localized = verify_install.split_localized(problems)
        return len(hard)
    except Exception:  # noqa: BLE001
        return 0


def _newest_cache_version():
    """Max harness_version across courier plugin caches, or None. Bounded glob."""
    home = os.environ.get("HOME") or str(Path.home())
    pattern = os.path.join(
        home, ".claude", "plugins", "cache", "*", "*", "*",
        "engine", "harness", "release.json")
    best = None
    try:
        for p in glob.glob(pattern):
            v = _read_version(Path(p))
            if v and (best is None or _semver_key(v) > _semver_key(best)):
                best = v
    except Exception:  # noqa: BLE001
        return None
    return best


def _installed_floor():
    """Newest version installed in the engine home (max across version dirs), or
    None. The skew decision keys off THIS — the same reference `harness upgrade` and
    `harness doctor` use — so the nudge never advises an upgrade that `upgrade` would
    refuse on a pinned-newer home. Mirrors harness_lifecycle._home_floor_version
    (a parity test pins the two)."""
    try:
        import harness_paths
        eh = harness_paths.engine_home()
        if not eh.is_dir():
            return None
        vers = []
        for p in sorted(eh.iterdir()):
            if p.name == "current" or p.name.startswith("."):
                continue
            v = _read_version(p / "harness" / "release.json")
            if v:
                vers.append(v)
        return max(vers, key=_semver_key) if vers else None
    except Exception:  # noqa: BLE001
        return None


def _semver_key(v: str):
    """Sort key for a harness_version string, via `packaging.version.Version` so
    rc1 < rc2 < rc10 < final compare NUMERICALLY — a hand-rolled comparator that
    dot-split the pre-release missed this: this repo writes the single identifier
    "rc10" (not "rc.10"), which is not `.isdigit()` and fell into a lexical-string
    branch where "rc10" < "rc2". Build metadata (+...) is stripped BEFORE handing the
    string to Version — semver ignores it, but PEP 440 gives a local version (+build)
    meaning (it sorts ABOVE the base), which would silently change ordering behaviour.

    MUST stay total: `harness_version` is repo-controlled, but this nudge must never
    crash a session's SessionStart hook on one that is not PEP-440-shaped (e.g. a test
    fixture's "9.9.9-cache"). A string `Version` rejects is coerced into the closest
    numeric base and treated as a pre-release of it (sorts below that base's final) —
    never raises. Must MATCH harness_lifecycle._semver_key so `harness upgrade`'s
    direction guard and the skew nudge agree (a test pins the two together)."""
    s = str(v).split("+")[0]
    try:
        return Version(s)
    except InvalidVersion:
        base = s.split("-", 1)[0]
        parts = []
        for chunk in base.split("."):
            num = "".join(ch for ch in chunk if ch.isdigit())
            parts.append(num if num else "0")
        while len(parts) < 3:
            parts.append("0")
        try:
            return Version(".".join(parts[:3]) + ".dev0")
        except InvalidVersion:
            return Version("0.0.0.dev0")


def _build_advisory(root, home_version) -> str:
    if _root_unresolved(root):
        return ("[nudge] engine root %s is unresolved (the engine home was deleted or "
                "the env was lost) — the guards have no engine. Run `harness setup` (or "
                "`harness doctor`) to restore it." % root)
    drift = _integrity_drift(root)
    if drift:
        return ("[nudge] engine home integrity: %d file(s) drifted from the manifest "
                "(same version, tampered/partial) — run `harness doctor`, then "
                "`harness upgrade` to re-lay a clean engine." % drift)
    cache_version = _newest_cache_version()
    # Skew keys off the NEWEST installed version (the reference upgrade/doctor use),
    # NOT the resolved-env home_version — else on a pinned-newer home this nudge would
    # advise `harness upgrade` for a version upgrade() then refuses, contradicting doctor.
    floor = _installed_floor() or home_version
    if cache_version and floor and _semver_key(cache_version) > _semver_key(floor):
        return ("[nudge] a newer harness plugin cache (%s) has not been applied to the "
                "engine home (%s) — run `harness upgrade`." % (cache_version, floor))
    return ""


def core(data: dict):
    if not os.environ.get("HARNESS_BIN_ROOT"):
        return None  # self-host — silent
    session_id = str((data or {}).get("session_id") or "")
    # Anonymous sessions (no session_id) do NOT share a flag — the collapsed "_"
    # key would degrade "once per session" to "once ever". They skip the gate and
    # re-check each time (rare on real SessionStart, which always carries an id).
    if session_id and _already_nudged(session_id):
        return None
    root, home_version = _home_root_and_version()
    advisory = _build_advisory(root, home_version)
    # Mark AFTER the (expensive full-tree integrity) check runs — healthy or not —
    # so a healthy engine does not re-hash the whole tree on every SessionStart
    # (compact/resume/clear). Guard the CHECK, not just the emit.
    if session_id:
        _mark_nudged(session_id)
    if not advisory:
        return None
    _emit_trace(session_id)
    # Human visibility MUST come from this hook's own systemMessage queue, NOT from
    # the SessionStart additionalContext→systemMessage mirror: the SHIPPED
    # context-surface.yaml has session_start.system_message=false (model-only), so a
    # courier install would otherwise show the operator NOTHING when their engine is
    # broken. queue_system_message honors nudge-channels {user:true} independently of
    # that knob. (A dev override with system_message=true can double-render this, but
    # engine_skew_nudge is self-host-silent in dev, so that combo never fires in
    # practice.) Return the advisory as additionalContext for the model channel.
    ax = hook_runtime.nudge_axes(_NAME, "systemMessage")
    if ax.get("user"):
        hook_runtime.queue_system_message("\n" + advisory)
    return advisory if ax.get("model") else None


def _emit_trace(session_id: str) -> None:
    try:
        import trace_log
        actor = hook_runtime.resolve_actor(session_id)
        trace_log.append_event(hook=_NAME, event="engine_skew", actor=actor,
                               session=session_id, status="observed")
    except Exception:  # noqa: BLE001 — trace is telemetry, never fatal
        pass


def run(raw=None) -> None:
    data = hook_runtime.read_stdin_json() if raw is None else hook_runtime._parse(raw)
    try:
        if hook_runtime.hook_enabled(_NAME, "nudge"):
            text = core(data if isinstance(data, dict) else {})
            if text:
                blob = {
                    "hookSpecificOutput": {
                        "hookEventName": "SessionStart",
                        "additionalContext": text,
                    },
                    "continue": True,
                }
                # fold the human-facing systemMessage the core queued (user axis)
                # into the SAME blob instead of dropping it.
                queued = hook_runtime._drain_system_messages()
                if queued:
                    blob["systemMessage"] = queued
                sys.stdout.write(json.dumps(blob))
                sys.stdout.flush()
                return
    except Exception as e:  # noqa: BLE001 — a nudge must never break the session
        hook_runtime.log_hook_error(_NAME, e)
    hook_runtime.drain_or_continue()


if __name__ == "__main__":
    run()
