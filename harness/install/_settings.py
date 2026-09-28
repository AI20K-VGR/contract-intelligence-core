#!/usr/bin/env python3
"""_settings.py — read/merge/write .claude settings JSON (extracted from
install.py). Leaf IO over the target settings file; a syntax error becomes a
deployer-actionable InstallError."""
import json
from pathlib import Path

from _errors import InstallError


def _settings_path(target_root: Path, local: bool) -> Path:
    name = "settings.local.json" if local else "settings.json"
    return target_root / ".claude" / name

def _read_json(path: Path) -> dict:
    """Read a JSON settings file, turning a syntax error, a bad encoding, or a
    wrong-shape file into an actionable InstallError (a team may hand-edit
    .claude/settings.json and leave it invalid). Missing file -> empty settings,
    the install-from-scratch case."""
    if not path.is_file():
        return {}
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (ValueError, OSError) as e:
        # ValueError covers json.JSONDecodeError AND a non-UTF-8 hand-edit's
        # UnicodeDecodeError; OSError covers a read failure. All become one
        # deployer-actionable InstallError instead of a raw traceback out of setup.
        raise InstallError(
            "%s is not readable as valid JSON (%s) — fix or move it, then re-run "
            "the installer." % (path, e)) from e
    if not isinstance(data, dict):
        # valid JSON but a top-level list/scalar — settings must be a mapping, or a
        # later `.get()` in the wiring path would raise a raw AttributeError.
        raise InstallError(
            "%s is not a JSON object (settings must be a mapping) — fix or move it, "
            "then re-run the installer." % path)
    _validate_settings_shape(data, path)
    return data


def _validate_settings_shape(data: dict, path: Path) -> None:
    """Validate the two nested keys the wiring path consumes (`env`, `hooks`) so a
    hand-edit slip becomes an actionable InstallError instead of a raw AttributeError/
    ValueError out of setup OR uninstall. `env` must be a mapping (it is `dict()`-ed);
    `hooks` must be event->list-of-group-mappings, each group's `hooks` a list of
    mappings (strip_harness_hooks iterates them). Missing keys are fine."""
    # `null` is treated as "missing" (every consumer reads `dict(env or {})` /
    # `hooks or {}`), so validator and consumers agree in both directions — reject only
    # a present, non-null, wrong-typed value.
    if data.get("env") is not None and not isinstance(data["env"], dict):
        raise InstallError(
            "%s: `env` must be a JSON object (got %s) — fix or move it, then re-run."
            % (path, type(data["env"]).__name__))
    hooks = data.get("hooks")
    if hooks is None:
        return
    if not isinstance(hooks, dict):
        raise InstallError(
            "%s: `hooks` must be a JSON object of event->groups (got %s) — fix or "
            "move it, then re-run." % (path, type(hooks).__name__))
    for event, groups in hooks.items():
        if not isinstance(groups, list):
            raise InstallError(
                "%s: hooks[%r] must be a list of groups (got %s) — fix or move it, "
                "then re-run." % (path, event, type(groups).__name__))
        for g in groups:
            if not isinstance(g, dict):
                raise InstallError(
                    "%s: a group under hooks[%r] must be a JSON object (got %s) — "
                    "fix or move it, then re-run." % (path, event, type(g).__name__))
            inner = g.get("hooks", [])
            if not isinstance(inner, list) or any(not isinstance(h, dict) for h in inner):
                raise InstallError(
                    "%s: hooks[%r] group `hooks` must be a list of objects — fix or "
                    "move it, then re-run." % (path, event))

def _load_settings(path: Path) -> dict:
    return _read_json(path)

def _write_settings(path: Path, settings: dict, dry_run: bool):
    if dry_run:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(settings, indent=2) + "\n", encoding="utf-8")
