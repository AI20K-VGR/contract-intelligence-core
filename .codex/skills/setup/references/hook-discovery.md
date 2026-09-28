# Hook / nudge discovery — read the live state, never trust a static list

The harness ships a LARGE, evolving set of hook/nudge/gate scripts (~40+, ~18 toggleable nudge/gate); a given repo's wiring can be stale. A hardcoded table here rots the moment a hook is added. So before surfacing nudges/gates in Full mode, DISCOVER the live state from source and present what actually exists and fires.

## The control model — three planes, one precedence

`hook_runtime.hook_enabled(name, class)` resolves on/off in this order:

1. **explicit `enabled` bool in `harness-hooks.yaml`** → wins (dev override: `HARNESS_HOOK_CONFIG`
   → `.harness-dev/harness-hooks.yaml`, scrubbed at push).
2. **guard-policy mode** (`off` / `warn` / `block`) — only for a hook registered as a guard/nudge in guard-policy; `off` ⇒ off, else on. Carries presets (strict/solo) + floors.
3. **class default** (`_CLASS_DEFAULTS`): `telemetry`=ON, `nudge`=OFF, `compliance`=ON+block. The fallback when no plane names the hook — i.e. an IMPLICIT state.

Plus the telemetry kill-switch: env `HARNESS_TELEMETRY_DISABLED` forces ALL telemetry-class hooks off at once (no effect on nudge/compliance).

Why the split: the class gives a safe per-category default; `harness-hooks.yaml` is the lightweight on/off for advisory nudges + opt-in gates; guard-policy is the security/enforcement plane (3-state + preset + floor). A hook on NO plane runs on its class default — surface those, they are the hidden ones.

## The five sources to read

| Source | What it tells you |
|---|---|
| `harness/install/hooks-registration.yaml` | every hook: name, `event`, `class`, command (the ship spec) |
| `"${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml` (or `$HARNESS_HOOK_CONFIG`) | explicit `enabled` flags |
| `guard_config.py show` | guard/nudge modes (off/warn/block) + preset + floors |
| `.claude/settings.json` (`hooks`) | what is ACTUALLY wired this session (CC only calls these) |
| `harness/hooks/*.py` | the hook bodies — `HOOK_CLASS` + the docstring's one-line purpose |

## Cross-reference: build the live table

Run this to produce `hook · class · event · wired? · in-config?` for every registration entry; then add guard-policy modes from `guard_config.py show`. Flag two drifts: **registration−settings** (shipped but not wired → never fires) and **no-plane** (runs on class default → implicit, make it explicit).

```bash
python3 - <<'PY'
import yaml, json, re
reg = yaml.safe_load(open("harness/install/hooks-registration.yaml")).get("hooks", [])
s = json.load(open(".claude/settings.json"))
wired = set()
for ev, groups in s.get("hooks", {}).items():
    for g in groups:
        for h in g.get("hooks", []):
            m = re.search(r'/hooks/([a-z0-9_]+)\.py', h.get("command","")); wired.add(m.group(1)) if m else None
cfg = set()
def walk(o):
    if isinstance(o, dict):
        for k, v in o.items():
            (cfg.add(k) if isinstance(v, dict) and "enabled" in v else walk(v))
    elif isinstance(o, list):
        [walk(i) for i in o]
walk(yaml.safe_load(open(""${HARNESS_BIN_ROOT:-.}"/harness/data/harness-hooks.yaml")))
for e in reg:
    nm = re.search(r'/hooks/([a-z0-9_]+)\.py', e.get("command","")); nm = nm.group(1) if nm else e.get("name","?")
    print(f"{nm:<28}{e.get('class','?'):<11}{e.get('event','?'):<16}"
          f"{'wired' if nm in wired else 'NOT-WIRED':<10}{'cfg' if nm in cfg else 'class-default'}")
PY
```

## How to guide the user from this

1. Present the live table (grouped by class), NOT a memorized list.
2. Call out NOT-WIRED hooks: shipped on disk but absent from `settings.json` → they do nothing until a re-projection (`install.py` materialize+merge) wires them. A stale `settings.json` is the usual cause.
3. Call out class-default (no-plane) hooks: their on/off is implicit — name the effective state and, if the user wants it visible, propose an explicit entry.
4. For each toggle the user wants to change, route to the RIGHT plane (harness-hooks.yaml `enabled`, or guard-policy mode) and remind: dev-only → `.harness-dev` + `HARNESS_HOOK_CONFIG` (no leak, restart to bind); shipped-default change → the tracked file (cp-bypass if GUARD_LIST-ed).

## Flipping a nudge (not a `--set` knob)

Nudges in `harness-hooks.yaml` are NOT `--set` knobs — flip `<nudge>: {enabled: true|false}` by hand (git-visible). Dev-only enablement uses `.harness-dev/harness-hooks.yaml` + `HARNESS_HOOK_CONFIG` (gitignored, scrubbed at push, restart to bind). The goal-cycle nudge pairs with the cycle-memory convention at `harness/plugins/hs/skills/goal/references/cycle-convention.md`.
