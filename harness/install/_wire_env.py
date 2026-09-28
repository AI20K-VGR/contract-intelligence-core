#!/usr/bin/env python3
"""_wire_env.py — emit the global-install root env into settings.json.

A global install resolves its shared binary through $HARNESS_BIN_ROOT and its
per-project data home through $HARNESS_DATA_ROOT. The installer now passes an
explicit data_root for a global install: a hook subprocess gets CLAUDE_PROJECT_DIR
from Claude Code and could derive `.harness` from it, but a Bash-tool subprocess
does not carry CLAUDE_PROJECT_DIR at all — so the explicit env write is the only
tier that subprocess can read. `data_root` stays an optional parameter (the
`else` branch below still applies) for a caller that passes None explicitly —
today that is the direct `wire_env()` tests and per-project installs, which never
call this function. Those values are MACHINE-SPECIFIC absolute paths; they land in
settings.json, which the harness gitignores (so a machine path is never committed —
verify_install.tracked_settings_problems also warns if either settings file is
tracked). NOT settings.local.json: Claude Code rewrites it from a stale in-memory
snapshot on every permission approval (a full-file read-modify-write; upstream CC
bugs #17017/#64699), which would wipe the bin-root env and brick the global install
(hooks resolve $HARNESS_BIN_ROOT to nothing). The portable hook wiring keeps its
$HARNESS_BIN_ROOT PLACEHOLDER in settings.json; the resolved value now lives in the
same file.

Idempotent (mirrors merge_hooks): re-running overwrites the two keys and leaves
every other env entry untouched, and strips any stale copy from settings.local.json
(CC merges local OVER main, so a leftover there would shadow the durable value).
Env is bound at session start, so a fresh wire needs a session RESTART to take
effect — the caller surfaces that note.
"""
from pathlib import Path

from _settings import _load_settings, _settings_path, _write_settings

RESTART_NOTE = (
    "HARNESS_BIN_ROOT/HARNESS_DATA_ROOT are env-bound — restart the Claude Code "
    "session for the global layout to take effect."
)


def wire_env(target_root, *, bin_root: str, data_root=None, dry_run: bool = False) -> dict:
    """Write HARNESS_BIN_ROOT (+ optional HARNESS_DATA_ROOT) into the target's
    settings.json `env` block. Returns the env block that was written (for dry-run
    preview). Preserves any existing env keys. Also strips any stale copy of these
    keys from settings.local.json (see _strip_local_root_env)."""
    path = _settings_path(Path(target_root), local=False)
    settings = _load_settings(path)
    env = dict(settings.get("env") or {})
    env["HARNESS_BIN_ROOT"] = str(bin_root)
    if data_root:
        env["HARNESS_DATA_ROOT"] = str(data_root)
    else:
        # caller passed None explicitly (a direct wire_env() test, or a
        # per-project caller — per-project never calls this function today):
        # drop any stale key rather than leave a prior run's value behind.
        env.pop("HARNESS_DATA_ROOT", None)
    settings["env"] = env
    _write_settings(path, settings, dry_run)
    _strip_local_root_env(Path(target_root), dry_run)
    return env


def _strip_local_root_env(target_root: Path, dry_run: bool) -> None:
    """Remove HARNESS_BIN_ROOT/HARNESS_DATA_ROOT from settings.local.json — they
    live in settings.json now, and Claude Code merges settings.local.json OVER
    settings.json, so a stale local copy (from an install made before this pinning)
    would shadow the durable value after a re-install to a different bin. Other env
    keys and every other setting are preserved; a no-op is silent."""
    lpath = _settings_path(Path(target_root), local=True)
    if not lpath.is_file():
        return
    settings = _load_settings(lpath)
    env = settings.get("env")
    if not isinstance(env, dict):
        return
    removed = False
    for k in ("HARNESS_BIN_ROOT", "HARNESS_DATA_ROOT"):
        if k in env:
            del env[k]
            removed = True
    if not removed:
        return
    if env:
        settings["env"] = env
    else:
        settings.pop("env", None)
    _write_settings(lpath, settings, dry_run)
