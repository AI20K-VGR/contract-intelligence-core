#!/usr/bin/env python3
"""_integrations.py — opt-in host integrations for the installer (extracted from
install.py): the ccstatusline terminal status bar and the on-PATH hs-cli
launcher. install.py re-exports these names, so callers and tests that reach
them through the `install` module see no change.
"""
import os
import shutil
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _settings import (  # noqa: E402
    _settings_path, _load_settings, _write_settings)


def _statusline_config_home(override) -> Path:
    """Where ccstatusline keeps its config. The documented default is
    ~/.config/ccstatusline; the override is an explicit install() param so the
    home write is testable without touching the real ~/.config."""
    if override is not None:
        return Path(override)
    return Path.home() / ".config" / "ccstatusline"


def _wire_statusline(source_root, target_root, local, result, dry_run, home_override):
    """Opt-in ccstatusline onboarding. Two no-clobber writes:
    (1) a `statusLine` block in the target's settings.json (the npx command
    auto-installs ccstatusline on first run), and (2) a shipped default config
    copied into the user's config home. An existing statusLine or an existing
    config file is left exactly as the user had it."""
    path = _settings_path(target_root, local)
    settings = _load_settings(path)
    if "statusLine" in settings:
        result["actions"].append(
            "statusLine already set in %s — left as-is" % path.name)
    else:
        settings["statusLine"] = {
            "type": "command",
            "command": "npx -y ccstatusline@latest",
            "padding": 0,
        }
        _write_settings(path, settings, dry_run)
        result["actions"].append(
            "wire statusLine (ccstatusline) into %s" % path.name)

    cfg_dir = _statusline_config_home(home_override)
    cfg = cfg_dir / "settings.json"
    asset = source_root / "harness" / "data" / "ccstatusline-default.json"
    if cfg.is_file():
        result["actions"].append(
            "ccstatusline config exists at %s — left as-is" % cfg)
    elif not asset.is_file():
        result["warnings"].append(
            "ccstatusline default config asset missing: %s" % asset)
    elif dry_run:
        result["actions"].append("ccstatusline config -> %s (dry-run)" % cfg)
    else:
        cfg_dir.mkdir(parents=True, exist_ok=True)
        shutil.copy2(asset, cfg)
        result["actions"].append("copy default ccstatusline config -> %s" % cfg)


def _cli_bindir(override) -> Path:
    """Where the on-PATH `hs-cli` launcher is dropped. Default ~/.local/bin (the
    XDG user-bin convention, already on PATH in most shells); an explicit
    override keeps it testable."""
    if override:
        return Path(override)
    return Path.home() / ".local" / "bin"


def _wire_cli(source_root, target_root, result, dry_run, bindir_override):
    """Opt-in: put an `hs-cli` launcher on PATH. POSIX → a no-clobber symlink in
    ~/.local/bin pointing at the shipped harness/bin/hs-cli wrapper (which
    resolves the repo from its own location and delegates to hs_cli.py). Windows
    has no reliable user symlink → advise adding harness/bin to PATH. Never
    clobbers an existing hs-cli; no package manager involved (just a launcher)."""
    wrapper = target_root / "harness" / "bin" / "hs-cli"
    if not wrapper.is_file():
        result["warnings"].append("hs-cli wrapper missing: %s" % wrapper)
        return
    if not dry_run:
        try:  # tar can drop the exec bit — restore it so the launcher runs
            wrapper.chmod(0o755)
        except OSError:
            pass
    if os.name == "nt":
        result["actions"].append(
            "hs-cli: on Windows add %s to PATH (hs-cli.cmd launcher)"
            % wrapper.parent)
        return
    bindir = _cli_bindir(bindir_override)
    link = bindir / "hs-cli"
    if link.exists() or link.is_symlink():
        result["actions"].append("hs-cli already at %s — left as-is" % link)
        return
    if dry_run:
        result["actions"].append("hs-cli symlink -> %s (dry-run)" % link)
        return
    try:
        bindir.mkdir(parents=True, exist_ok=True)
        link.symlink_to(wrapper)
        result["actions"].append("link hs-cli -> %s" % wrapper)
        on_path = str(bindir) in (os.environ.get("PATH") or "").split(os.pathsep)
        if not on_path:
            result["warnings"].append(
                "%s is not on PATH — add it to call `hs-cli` directly" % bindir)
    except OSError as e:  # noqa: BLE001 — a launcher we could not link is a warning
        result["warnings"].append("could not link hs-cli (%s)" % e)
