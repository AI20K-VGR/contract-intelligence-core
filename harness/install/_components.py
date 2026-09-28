#!/usr/bin/env python3
"""_components.py — component selection + plugin wiring + policy (extracted from
install.py). Resolves the optional-component selection, projects it into the
target, and wires the plugin marketplace + enabledPlugins. install.py re-exports
these names, so callers and tests that reach them through the `install` module
see no change.
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_SCRIPTS = _HERE.parent / "scripts"
if str(_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_SCRIPTS))
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

from _errors import InstallError  # noqa: E402
from _settings import (  # noqa: E402
    _settings_path, _load_settings, _write_settings)

# The local plugin marketplace: name CC keys plugins under, the core plugin that
# is never disabled, and the directory CC loads plugins from (relative to the
# target repo root, the form CC expects in extraKnownMarketplaces).
MARKETPLACE = "hs-local"
SPINE_PLUGIN = "hs"
_PLUGINS_REL = "./harness/plugins"


def _chosen_components(components, components_arg) -> set:
    """Resolve `--components=all|csv` to the set of ENABLED component names.
    `all` (the default, or a missing/None arg) selects every declared component;
    a CSV selects only the named ones; an EMPTY string selects NONE (the "disable
    every optional component" choice — distinct from absent, which means all). An
    unknown name is a hard InstallError (a typo must not silently disable a
    component). Shared by the hook projector and the plugin wirer."""
    arg = "all" if components_arg is None else components_arg.strip()
    if arg == "all":
        return set(components)
    chosen = {c.strip() for c in arg.split(",") if c.strip()}
    unknown = chosen - set(components)
    if unknown:
        raise InstallError(
            "unknown component(s) %s — known: %s"
            % (", ".join(sorted(unknown)), ", ".join(sorted(components))))
    return chosen


def _apply_components(target_root, components_arg, result, dry_run):
    """Project the component selection into the TARGET (ship-all-but-off).
    The tree is already copied and every hook already wired; this only flips
    the `enabled` flag for DESELECTED components (off = runtime-disabled, never
    unwired or deleted) and records install-state. `--components=all` enables
    everything; a CSV (e.g. `rbac,decision-capture`) enables only those."""
    arg = "all" if components_arg is None else components_arg.strip()
    if dry_run:  # the target tree is not copied on a dry run — plan, don't read
        result["actions"].append(
            "components: project selection %r (dry-run)" % (arg or "(none)"))
        return
    scripts_dir = target_root / "harness" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import component_config as cc
    except Exception as e:  # noqa: BLE001 — no projector → leave defaults on
        result["warnings"].append("component projector unavailable: %s" % e)
        return
    comp_file = target_root / "harness" / "data" / "components.yaml"
    try:
        components = cc.load_components(comp_file)
    except cc.ComponentConfigError as e:
        result["warnings"].append("components.yaml unreadable: %s" % e)
        return

    chosen = _chosen_components(components, arg)
    selection = {name: (name in chosen) for name in components}
    off = sorted(n for n, on in selection.items() if not on)

    try:
        # Hooks/policy/state only — enabledPlugins is wired separately by
        # _wire_plugins (it owns the full marketplace list + core plugin).
        cc.apply_selection(
            selection, components_path=comp_file,
            policy_path=target_root / "harness" / "data" / "component-policy.yaml",
            hooks_path=target_root / "harness" / "data" / "harness-hooks.yaml",
            state_path=target_root / "harness" / "state" / "install-state.json")
    except cc.ComponentConfigError as e:
        raise InstallError("component selection invalid: %s" % e)
    result["actions"].append(
        "components: %d enabled, disabled=%s" % (len(chosen), off or "none"))


def _marketplace_plugins(target_root) -> list:
    """Plugin names declared in the local marketplace — the source of truth for
    which plugins exist. [] when the marketplace file is absent or unreadable."""
    mp = (target_root / "harness" / "plugins" / ".claude-plugin"
          / "marketplace.json")
    if not mp.is_file():
        return []
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — a broken marketplace wires no plugins
        return []
    return [p.get("name") for p in data.get("plugins", []) if p.get("name")]


def _wire_plugins(target_root, components_arg, local, result, dry_run,
                  source_root=None, bin_root=None):
    """Wire EVERY plugin the marketplace declares into the SAME settings file
    the hooks go to (one file, never split): write extraKnownMarketplaces.hs-local
    + enabledPlugins. Ship-all-but-off — every plugin defaults ENABLED; a
    component that maps to a plugin (components.yaml `plugin:`) and is deselected
    turns that plugin enabledPlugins:false while its DIR still ships. Core plugin
    `hs` is always enabled. Idempotent merge; user-authored keys are preserved.

    On a dry run the target tree is never copied, so the marketplace + component
    map are sourced from `source_root` instead — the preview lists what WOULD be
    wired (otherwise it reads an empty target and shows nothing).

    Under a GLOBAL install (`bin_root` set): the project has NO per-project
    harness/ tree, so the marketplace + component map are read from the shared
    BIN and the marketplace `path` is written as the bin's ABSOLUTE plugins dir.
    A relative `_PLUGINS_REL` would dangle (there is no `<project>/harness/plugins`),
    which is exactly the bug that left a global install with hooks but zero skills."""
    if bin_root is not None:
        read_root = Path(bin_root)
        plugins_path = str(Path(bin_root) / "harness" / "plugins")
    else:
        read_root = source_root if (dry_run and source_root is not None) else target_root
        plugins_path = _PLUGINS_REL
    plugins = _marketplace_plugins(read_root)
    if not plugins:
        return  # no marketplace → nothing to wire

    states = {name: True for name in plugins}  # ship-all default: every plugin on
    scripts_dir = read_root / "harness" / "scripts"
    if str(scripts_dir) not in sys.path:
        sys.path.insert(0, str(scripts_dir))
    try:
        import component_config as cc
        comp_file = read_root / "harness" / "data" / "components.yaml"
        components = cc.load_components(comp_file)
        chosen = _chosen_components(components, components_arg)
        selection = {n: (n in chosen) for n in components}
        for plugin, enabled in cc.plugin_states(components, selection).items():
            if plugin in states:
                states[plugin] = enabled
    except InstallError:
        raise
    except Exception as e:  # noqa: BLE001 — no components map → leave all on
        result["warnings"].append("plugin component-map unavailable: %s" % e)
    if SPINE_PLUGIN in states:
        states[SPINE_PLUGIN] = True  # core is never disabled, whatever a component
        # says — but only if the marketplace actually declares it (don't inject a
        # phantom enable key for a core that isn't there).

    if dry_run:
        result["actions"].append(
            "plugins: wire %d (%s) (dry-run)"
            % (len(states), ", ".join(sorted(states))))
        return
    path = _settings_path(target_root, local)
    settings = _load_settings(path)
    mk = dict(settings.get("extraKnownMarketplaces") or {})
    mk[MARKETPLACE] = {"source": {"source": "directory", "path": plugins_path}}
    settings["extraKnownMarketplaces"] = mk
    ep = dict(settings.get("enabledPlugins") or {})
    for plugin, enabled in states.items():
        ep["%s@%s" % (plugin, MARKETPLACE)] = bool(enabled)
    settings["enabledPlugins"] = ep
    _write_settings(path, settings, dry_run)
    off = sorted(p for p, on in states.items() if not on)
    result["actions"].append(
        "plugins: %d wired into %s, disabled=%s"
        % (len(states), path.name, off or "none"))


def _resolve_policy_components(source_root) -> str:
    """The default --components value when none was given: honor the shipped
    component-policy (default-only-hs). Returns "all" only when the policy has no
    deviations, else a CSV of the policy-enabled components; "all" on any error
    (fail-safe to the historical behavior rather than silently disabling)."""
    try:
        sys.path.insert(0, str(Path(source_root) / "harness" / "scripts"))
        import component_config as cc
        comps = cc.load_components(
            Path(source_root) / "harness" / "data" / "components.yaml")
        defaults = cc.resolved_selection(
            comps,
            cc.load_policy(Path(source_root) / "harness" / "data" / "component-policy.yaml"))
        enabled = sorted(c for c, on in defaults.items() if on)
        if len(enabled) == len(defaults):
            return "all"
        return ",".join(enabled)
    except Exception:  # noqa: BLE001 — no policy/map -> historical ship-all
        return "all"
