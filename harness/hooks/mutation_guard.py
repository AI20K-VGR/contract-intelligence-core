#!/usr/bin/env python3
"""mutation_guard.py — SubagentStart/Stop DETECTION hook (nudge class, fail-open).

DETECTION layer — INDEPENDENT of write_guard (PREVENTION layer on Write/Edit).
This hook catches advisory agents that mutate or delete a git-tracked source file
through ANY channel (Write, Bash-redirect, etc.) by comparing content-hashes taken
at spawn vs. stop. Scope is the set of files tracked AT spawn: a brand-new untracked
file created during the run is NOT in the snapshot, so creation-only mutations are
out of scope here (the write_guard prevention layer is what bounds writes).

Two modes:
  --start  (SubagentStart):  if agent_type is in advisory list, snapshot content
           hashes of git-tracked files under harness/ into state/mutation-guard/<key>.json.
  --stop   (SubagentStop):   if snapshot exists for this (session_id, agent_id) key,
           re-hash scope and report any changed non-allowlisted paths as advisory.

HOOK_CLASS = nudge: fail-open, never blocks, default OFF in harness-hooks.yaml.
Requires MUTATION_GUARD_REPO_ROOT env (or auto-detect via git rev-parse) to locate
the tracked file scope.
"""

import fnmatch
import hashlib
import json
import os
import subprocess
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_DATA = os.path.join(os.path.dirname(_HERE), "data")

for _p in (_HERE, os.path.join(os.path.dirname(_HERE), "scripts")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

HOOK_CLASS = "nudge"
_HOOK = "mutation_guard"
_CONFIG_FILE = os.path.join(_DATA, "mutation-guard.yaml")


def _load_config() -> dict:
    try:
        import hook_runtime  # for yaml_load (C loader + mandatory fallback)
        with open(_CONFIG_FILE, encoding="utf-8") as f:
            raw = hook_runtime.yaml_load(f)
        if isinstance(raw, dict):
            return raw
    except Exception:
        pass
    return {}


def _state_dir() -> Path:
    raw = os.environ.get("HARNESS_STATE_DIR")
    if raw:
        return Path(raw) / "mutation-guard"
    import hook_runtime
    return hook_runtime._state_dir() / "mutation-guard"


def _snapshot_key(payload: dict) -> "str | None":
    session = payload.get("session_id") or ""
    agent = payload.get("agent_id") or ""
    if not (session or agent):
        return None
    return hashlib.sha256(("%s|%s" % (session, agent)).encode()).hexdigest()[:32]


def _repo_root() -> "Path | None":
    override = os.environ.get("MUTATION_GUARD_REPO_ROOT")
    if override:
        return Path(override)
    try:
        out = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, timeout=5,
        )
        if out.returncode == 0:
            return Path(out.stdout.strip())
    except Exception:
        pass
    return None


def _git_tracked_files(repo_root: Path) -> list:
    """Return paths of git-tracked files under harness/ relative to repo_root."""
    try:
        out = subprocess.run(
            ["git", "-C", str(repo_root), "ls-files", "harness/"],
            capture_output=True, text=True, timeout=30,
        )
        if out.returncode != 0:
            return []
        return [line.strip() for line in out.stdout.splitlines() if line.strip()]
    except Exception:
        return []


def _file_hash(path: Path) -> "str | None":
    try:
        return hashlib.sha256(path.read_bytes()).hexdigest()
    except Exception:
        return None


def _is_allowlisted(rel_path: str, allow_patterns: list) -> bool:
    for pat in allow_patterns:
        if fnmatch.fnmatch(rel_path, pat):
            return True
        # Also match against the basename
        if fnmatch.fnmatch(os.path.basename(rel_path), pat.lstrip("*/")):
            return True
    return False


def _is_advisory(agent_type: str, cfg: dict) -> bool:
    advisory = cfg.get("advisory_agents") or []
    # de-namespace: hs:red-teamer → red-teamer
    bare = agent_type.split(":", 1)[1] if ":" in agent_type else agent_type
    return bare in advisory or agent_type in advisory


def do_start(payload: dict) -> None:
    """Snapshot tracked file hashes for advisory agents."""
    agent_type = str(payload.get("agent_type") or "").strip()
    cfg = _load_config()

    if not agent_type or not _is_advisory(agent_type, cfg):
        return  # not advisory — skip silently

    key = _snapshot_key(payload)
    if key is None:
        return

    repo_root = _repo_root()
    if repo_root is None:
        return

    tracked = _git_tracked_files(repo_root)
    snap = {}
    for rel in tracked:
        p = repo_root / rel
        h = _file_hash(p)
        if h is not None:
            snap[rel] = h

    snap_dir = _state_dir()
    snap_dir.mkdir(parents=True, exist_ok=True)
    snap_file = snap_dir / ("%s.json" % key)
    # Write-once per session: refuse to overwrite an existing snapshot so an
    # advisory agent cannot re-snapshot after mutating to erase the diff.
    if snap_file.exists():
        return
    snap_file.write_text(json.dumps({
        "key": key,
        "session_id": payload.get("session_id"),
        "agent_id": payload.get("agent_id"),
        "agent_type": agent_type,
        "files": snap,
    }, ensure_ascii=False), encoding="utf-8")


def do_stop(payload: dict) -> None:
    """Diff snapshot against current state; report mutations as advisory."""
    key = _snapshot_key(payload)
    if key is None:
        return

    snap_dir = _state_dir()
    snap_file = snap_dir / ("%s.json" % key)
    if not snap_file.exists():
        return  # no snapshot for this key (builder or missed start) — no-op

    try:
        snap_data = json.loads(snap_file.read_text(encoding="utf-8"))
    except Exception:
        snap_file.unlink(missing_ok=True)
        return

    try:
        cfg = _load_config()
        allow_patterns = cfg.get("allow_paths") or []

        repo_root = _repo_root()
        if repo_root is None:
            return

        before = snap_data.get("files") or {}
        agent_type = snap_data.get("agent_type") or "unknown"

        # Re-hash current state
        after = {}
        for rel in before:
            p = repo_root / rel
            h = _file_hash(p)
            if h is not None:
                after[rel] = h

        changed = []
        for rel, old_hash in before.items():
            if _is_allowlisted(rel, allow_patterns):
                continue
            new_hash = after.get(rel)
            if new_hash != old_hash:
                changed.append(rel)

        if changed:
            import trace_log
            import hook_runtime
            session = payload.get("session_id")
            trace_log.append_event(
                hook=_HOOK,
                event="mutation_detected",
                session=session,
                actor=hook_runtime.resolve_actor(session_id=session),
                status="advisory",
                note="agent_type=%s changed %d file(s): %s" % (
                    agent_type, len(changed), ", ".join(sorted(changed)[:5])
                ),
            )
            # Default sink systemMessage (person-aimed: an advisory agent mutated
            # tracked files); reroutable via nudge-channels.yaml. Route to the SHARED
            # queue (no terminal write here) so both the standalone main() and the
            # dispatcher own the single stdout blob (in-process callable, no double write).
            hook_runtime.emit_nudge(
                _HOOK,
                "[advisory] mutation_guard: advisory agent '%s' modified %d "
                "tracked file(s): %s"
                % (agent_type, len(changed), ", ".join(sorted(changed)[:5])),
                session=session, default_channel="systemMessage")
    finally:
        snap_file.unlink(missing_ok=True)


def main() -> None:
    if len(sys.argv) < 2 or sys.argv[1] not in ("--start", "--stop"):
        sys.stderr.write("Usage: mutation_guard.py --start | --stop\n")
        sys.exit(0)  # fail-open: bad args → continue

    try:
        import hook_runtime
        enabled = hook_runtime.hook_enabled(_HOOK, HOOK_CLASS)
    except Exception:
        enabled = True  # default ON if config unavailable

    try:
        raw = sys.stdin.read()
        payload = json.loads(raw) if raw and raw.strip() else {}
        if not isinstance(payload, dict):
            payload = {}
    except Exception:
        payload = {}

    if not enabled:
        sys.exit(0)

    try:
        if sys.argv[1] == "--start":
            do_start(payload)
        else:
            do_stop(payload)
    except Exception:
        pass  # fail-open: any error → swallow, exit 0

    # Drain a queued advisory (mutation detected) into the single terminal blob,
    # else a plain continue — do_stop no longer owns the stdout write directly.
    hook_runtime.drain_or_continue()
    sys.exit(0)


if __name__ == "__main__":
    main()
