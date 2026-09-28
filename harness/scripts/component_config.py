#!/usr/bin/env python3
"""component_config.py — ship-all-but-off component projector.

A component is a named bundle of hooks/scripts/skills/data declared in
`components.yaml`. Every component SHIPS unconditionally; a component is turned
OFF only at RUNTIME, through whichever real mechanism its membership implies —
both REUSE an existing enable path rather than inventing a parallel flag:
  * HOOK-bearing components write `enabled: false` for each hook into
    `harness-hooks.yaml` (`hooks.<name>.enabled`, read live by
    `hook_runtime.hook_enabled`).
  * PLUGIN-bearing components are VESTIGIAL post-collapse: their sibling
    plugins were folded into the one `hs` plugin, so an `enabledPlugins["hs-<group>
    @hs-local"]` toggle would name a plugin that no longer exists. _write_enabled_
    plugins filters those phantoms against the live marketplace, and the real
    per-skill disable is now install-time dir-omission (skill_selection / hs-cli
    skills). The `plugin:` key is kept only as a group label.

Files:
  components.yaml         — static declaration (what each component contains)
  component-policy.yaml   — selection (which components are off); ship-all default
  harness-hooks.yaml      — projection target (enabled flags); core hooks untouched
  state/install-state.json — observed install/enable state (gitignored)

For HOOK-bearing components (rbac, decision-capture) the load-bearing effect is the
hook enable flag; SKILL/SCRIPT/DATA membership is otherwise informational. For the
former PLUGIN-bearing components the `skills:` list is the install-time selection
set (group label); their `enabledPlugins` toggle is inert post-collapse.

Validate BEFORE any write (an invalid toggle raises and
touches nothing), preserve the file's leading comment header on rewrite.
"""
import sys
import register_store
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

_DATA = _HERE.parent / "data"
_HOOKS_DEFAULT = _DATA / "harness-hooks.yaml"
_STATE_DEFAULT = _HERE.parent / "state" / "install-state.json"
_COMPONENTS_DEFAULT = _DATA / "components.yaml"
_POLICY_DEFAULT = _DATA / "component-policy.yaml"
_MARKETPLACE_DEFAULT = "hs-local"


class ComponentConfigError(Exception):
    """Raised when a component declaration / selection / toggle is invalid.
    The message names the offending component so the fix is a config edit."""


# ---- loaders --------------------------------------------------------------

def load_components(path=None) -> dict:
    """Parse components.yaml → {name: {hooks, scripts, skills, data, requires}}.
    Missing file / non-mapping / bad entry raises ComponentConfigError."""
    import yaml_io
    p = Path(path) if path else _COMPONENTS_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise ComponentConfigError("components manifest missing at %s" % p)
    if not isinstance(raw, dict):
        raise ComponentConfigError(
            "components %s malformed — expected a mapping with `components:`" % p)
    comps = raw.get("components", {})
    if not isinstance(comps, dict):
        raise ComponentConfigError(
            "`components` in %s must be a mapping of name -> spec" % p)
    out = {}
    for name, spec in comps.items():
        if not isinstance(spec, dict):
            raise ComponentConfigError(
                "component %r in %s must be a mapping" % (name, p))
        out[name] = {
            "hooks": list(spec.get("hooks") or []),
            "scripts": list(spec.get("scripts") or []),
            "skills": list(spec.get("skills") or []),
            "data": list(spec.get("data") or []),
            "requires": list(spec.get("requires") or []),
            # optional: the sibling plugin this component toggles. A
            # component with no plugin only affects hooks; a plugin-only
            # component (no hooks) only affects enabledPlugins.
            "plugin": spec.get("plugin"),
        }
    return out


def load_policy(path=None) -> dict:
    """Parse component-policy.yaml → {name: bool} selection. Missing/empty → {}
    (ship-all: every component enabled)."""
    import yaml_io
    p = Path(path) if path else _POLICY_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if raw is None:
        return {}
    if not isinstance(raw, dict):
        raise ComponentConfigError(
            "policy %s malformed — expected a mapping with `components:`" % p)
    sel = raw.get("components", {})
    if sel is None:
        return {}
    if not isinstance(sel, dict):
        raise ComponentConfigError(
            "`components` in %s must be a mapping of name -> bool" % p)
    for k, v in sel.items():
        if not isinstance(v, bool):
            raise ComponentConfigError(
                "component %r in %s must be true or false (got %r) — a quoted "
                "'false'/'off' string is truthy in Python and would silently "
                "leave the component ENABLED" % (k, p, v))
    return dict(sel)


# ---- resolution + validation ---------------------------------------------

def resolved_selection(components, selection) -> dict:
    """Every declared component → bool. A component absent from `selection` is
    ENABLED (ship-all default)."""
    return {name: bool(selection.get(name, True)) for name in components}


def validate_requires(components, selection) -> None:
    """Raise if an ENABLED component needs a dependency that is unknown or off.
    `selection` may be sparse (resolved internally)."""
    sel = resolved_selection(components, selection)
    for name, spec in components.items():
        if not sel.get(name):
            continue  # a disabled component's deps are irrelevant
        for dep in spec.get("requires", []):
            if dep not in components:
                raise ComponentConfigError(
                    "component %r requires unknown component %r" % (name, dep))
            if not sel.get(dep):
                raise ComponentConfigError(
                    "cannot enable %r: required component %r is disabled"
                    % (name, dep))


def plugin_states(components, selection) -> dict:
    """{plugin_name: enabled} for every component that declares `plugin:`.
    A component without a plugin contributes nothing; `selection` may be sparse
    (resolved via ship-all default). Last component wins if two map one plugin."""
    sel = resolved_selection(components, selection)
    out = {}
    for name, spec in components.items():
        plugin = spec.get("plugin")
        if plugin:
            out[plugin] = sel[name]
    return out


# ---- projector (pure) -----------------------------------------------------

def project(components, selection, current_hooks) -> dict:
    """Apply the components named in `selection` onto `current_hooks`, returning
    a NEW hooks map. TARGETED: only hooks of components present in `selection`
    are written (enabled: bool); every other entry — core hooks, manual
    mode/enabled overrides — is carried through untouched. An unknown component
    name is skipped (set_component is where a typo'd toggle raises loudly)."""
    out = dict(current_hooks or {})
    for name in selection:
        spec = components.get(name)
        if not spec:
            continue
        enabled = bool(selection[name])
        for hook in spec.get("hooks", []):
            entry = dict(out.get(hook) or {})
            entry["enabled"] = enabled
            out[hook] = entry
    return out


def cross_check(components, selection, hooks) -> list:
    """Tamper/drift detector: a hook of an OFF component whose harness-hooks
    entry is not `enabled: false`. Returns a list of human-readable problems
    (empty when consistent). After project() it is always empty."""
    sel = resolved_selection(components, selection)
    bad = []
    for name, spec in components.items():
        if sel.get(name):
            continue
        for hook in spec.get("hooks", []):
            if (hooks.get(hook) or {}).get("enabled") is not False:
                bad.append(
                    "hook %r is not disabled but its component %r is off"
                    % (hook, name))
    return bad


# ---- writers (header-preserving, validate-first) -------------------------

def _header(path, default: str) -> str:
    import config_io
    return config_io.leading_comment_block(path, default)


def _load_hooks_map(path=None) -> dict:
    import yaml_io
    p = Path(path) if path else _HOOKS_DEFAULT
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return {}
    if not isinstance(raw, dict):
        return {}
    hooks = raw.get("hooks", {})
    return hooks if isinstance(hooks, dict) else {}


def _write_hooks_file(path, hooks_map) -> None:
    import yaml_io
    p = Path(path) if path else _HOOKS_DEFAULT
    header = _header(p, "# harness-hooks.yaml — per-hook enabled/mode overrides.\n")
    # The file holds top-level knobs beside `hooks:` (inject_refresh_mode,
    # scope_hint_advisory, …), each with a live reader. Serialising only the hooks
    # map deleted them on every component toggle, and a hook falling back to its
    # default is invisible — carry the rest through.
    kept = {}
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
        if isinstance(raw, dict):
            kept = {k: v for k, v in raw.items() if k != "hooks"}
    except FileNotFoundError:
        pass
    kept["hooks"] = hooks_map or {}
    body = yaml_io.safe_dump(kept, sort_keys=True, default_flow_style=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    register_store.atomic_write(p, header + body)


def _write_policy_file(path, selection) -> None:
    import yaml_io
    p = Path(path) if path else _POLICY_DEFAULT
    header = _header(
        p, "# component-policy.yaml — component on/off selection.\n")
    body = yaml_io.safe_dump({"components": dict(selection or {})}, sort_keys=True,
                          default_flow_style=False)
    p.parent.mkdir(parents=True, exist_ok=True)
    register_store.atomic_write(p, header + body)


def _write_state(path, components, selection) -> None:
    import json
    p = Path(path) if path else _STATE_DEFAULT
    sel = resolved_selection(components, selection)
    prior = {}
    try:
        prior = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — fresh state file is fine
        prior = {}
    state = {
        "installed_at": prior.get("installed_at"),
        "components": {name: {"installed": True, "enabled": sel[name]}
                       for name in components},
        "hooks_wired": True,
        "last_verified": prior.get("last_verified"),
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    register_store.atomic_write(p, json.dumps(state, indent=2, ensure_ascii=False) + "\n")


def _marketplace_names(settings_path) -> set:
    """Plugin names the local marketplace actually declares, derived from the repo
    that owns settings_path (<root>/.claude/settings.json -> <root>/harness/plugins/
    .claude-plugin/marketplace.json). Empty set when it can't be found, which the
    caller treats as 'do not filter' (never silently drop everything)."""
    import json
    root = Path(settings_path).resolve().parent.parent
    mp = root / "harness" / "plugins" / ".claude-plugin" / "marketplace.json"
    try:
        data = json.loads(mp.read_text(encoding="utf-8"))
        return {p.get("name") for p in data.get("plugins", []) if p.get("name")}
    except Exception:  # noqa: BLE001 — no/unreadable marketplace -> no filter
        return set()


def _write_enabled_plugins(settings_path, states, *,
                           marketplace=_MARKETPLACE_DEFAULT) -> None:
    """Merge {plugin: enabled} into settings.json `enabledPlugins` as
    '<plugin>@<marketplace>': bool. Idempotent; preserves user-authored keys.
    No-op when `states` is empty. A plugin the local marketplace does NOT declare
    is SKIPPED: post-collapse the 13 former group `plugin:` keys point at plugins
    that no longer exist, so writing `hs-think@hs-local:false` etc. would pollute
    the user's settings with dead keys (the install path filters the same way)."""
    import json
    if not states:
        return
    p = Path(settings_path)
    try:
        settings = json.loads(p.read_text(encoding="utf-8"))
    except Exception:  # noqa: BLE001 — missing/invalid -> fresh settings
        settings = {}
    if not isinstance(settings, dict):
        settings = {}
    known = _marketplace_names(p)
    ep = dict(settings.get("enabledPlugins") or {})
    wrote = False
    for plugin, enabled in states.items():
        if known and plugin not in known:
            continue  # phantom plugin: not in the marketplace -> no dead key
        ep["%s@%s" % (plugin, marketplace)] = bool(enabled)
        wrote = True
    if not wrote:
        return
    settings["enabledPlugins"] = ep
    p.parent.mkdir(parents=True, exist_ok=True)
    register_store.atomic_write(p, json.dumps(settings, indent=2) + "\n")


def apply_selection(selection, *, components_path=None, policy_path=None,
                    hooks_path=None, state_path=None, settings_path=None,
                    marketplace=_MARKETPLACE_DEFAULT) -> dict:
    """Apply a full/partial component selection at once (the install path).
    `selection` is {name: bool}; names absent from it keep their current policy
    (or ship-all default). Validates BEFORE any write — an unknown name or a
    requires violation raises ComponentConfigError and touches no file — then
    writes policy, projects hooks, records install-state, and (when
    `settings_path` is given) projects component->plugin choices into
    `enabledPlugins`."""
    components = load_components(components_path)
    unknown = set(selection) - set(components)
    if unknown:
        raise ComponentConfigError(
            "unknown component(s): %s — known: %s"
            % (", ".join(sorted(unknown)), ", ".join(sorted(components)) or "(none)"))

    merged = dict(load_policy(policy_path))
    merged.update({k: bool(v) for k, v in selection.items()})

    validate_requires(components, merged)  # raises before any write

    current = _load_hooks_map(hooks_path)
    new_hooks = project(components, merged, current)
    problems = cross_check(components, merged, new_hooks)
    if problems:  # defensive: projection must be self-consistent
        raise ComponentConfigError(
            "projection inconsistent: %s" % "; ".join(problems))

    # Record ONLY deviations from ship-all (default = enabled): a default install
    # (every component on) leaves the policy empty, so the shipped `components: {}`
    # round-trips byte-stable instead of expanding to redundant `name: true`.
    # Self-healing: rewrites only when the deviation set actually changed (also
    # cleans a stale all-true map a prior write may have left).
    deviations = {k: v for k, v in merged.items() if not v}
    if deviations != dict(load_policy(policy_path)):
        _write_policy_file(policy_path, deviations)
    # Skip the hooks rewrite when projection changes nothing — a no-op ship-all
    # install must not reformat (and thus hash-drift) the shipped hooks file.
    if new_hooks != current:
        _write_hooks_file(hooks_path, new_hooks)
    _write_state(state_path, components, merged)
    if settings_path is not None:
        _write_enabled_plugins(settings_path, plugin_states(components, merged),
                               marketplace=marketplace)
    return resolved_selection(components, merged)


def set_component(name, enabled, *, components_path=None, policy_path=None,
                  hooks_path=None, state_path=None, settings_path=None,
                  marketplace=_MARKETPLACE_DEFAULT) -> dict:
    """Toggle ONE component on/off (the CLI path). Thin wrapper over
    apply_selection so the validate-then-write contract lives in one place."""
    return apply_selection({name: bool(enabled)},
                           components_path=components_path,
                           policy_path=policy_path, hooks_path=hooks_path,
                           state_path=state_path, settings_path=settings_path,
                           marketplace=marketplace)


# ---- CLI ------------------------------------------------------------------

def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(
        description="component on/off projector (ship-all-but-off)")
    ap.add_argument("action", nargs="?", default="show",
                    choices=["show", "list"],
                    help="show resolved state (default) or list components")
    ap.add_argument("--set", dest="sets", action="append",
                    metavar="NAME=enabled|disabled",
                    help="toggle a component (repeatable)")
    ap.add_argument("--components-file", default=None)
    ap.add_argument("--policy-file", default=None)
    ap.add_argument("--hooks-file", default=None)
    ap.add_argument("--state-file", default=None)
    ap.add_argument("--settings-file", default=None,
                    help="also project component->plugin choices into this "
                         "settings.json enabledPlugins (re-toggle path)")
    ap.add_argument("--marketplace", default=_MARKETPLACE_DEFAULT)
    args = ap.parse_args(argv)

    try:
        components = load_components(args.components_file)
    except ComponentConfigError as e:
        sys.stderr.write("error: %s\n" % e)
        return 2

    if args.sets:
        for pair in args.sets:
            if "=" not in pair:
                sys.stderr.write("--set expects NAME=enabled|disabled, got %r\n" % pair)
                return 2
            name, value = pair.split("=", 1)
            value = value.strip().lower()
            if value not in ("enabled", "disabled", "on", "off", "true", "false"):
                sys.stderr.write(
                    "--set value must be enabled|disabled (got %r)\n" % value)
                return 2
            enabled = value in ("enabled", "on", "true")
            try:
                set_component(name.strip(), enabled,
                              components_path=args.components_file,
                              policy_path=args.policy_file,
                              hooks_path=args.hooks_file,
                              state_path=args.state_file,
                              settings_path=args.settings_file,
                              marketplace=args.marketplace)
            except ComponentConfigError as e:
                sys.stderr.write("error: %s\n" % e)
                return 2
        return 0

    policy = load_policy(args.policy_file)
    sel = resolved_selection(components, policy)
    if args.action == "list":
        for name in sorted(components):
            print(name)
        return 0
    # show
    hooks = _load_hooks_map(args.hooks_file)
    problems = cross_check(components, policy, hooks)
    print(json.dumps({"components": {n: sel[n] for n in sorted(components)},
                      "plugins": plugin_states(components, policy),
                      "drift": problems}, indent=2, ensure_ascii=False))
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
