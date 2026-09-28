#!/usr/bin/env python3
"""gemini_partner_config.py — gate-grade loader for the gemini partner lane.

SSOT: harness/data/gemini-partner.yaml. Resolution order (env-bound, like
HARNESS_GUARD_POLICY — a change needs a restart, never a live in-session flip):

    explicit path arg  >  $HARNESS_GEMINI_PARTNER  >  shipped tracked file

The shipped file is the factory-safe corner; a dev points the env var at
`.harness-dev/gemini-partner.yaml` (dogfood `route_all_surface: all`) so the wide
surface never bakes into the ship (LESSONS: personal/dev config in a shipped file).

`resolve()` is fail-CLOSED: a forbidden combo (S1) or an override model outside the
model SSOT (S7) raises SystemExit with an actionable reason — the pattern lifted
from resolve_model._validate. S6 (master off ⇒ inert) is a *runtime* view, applied
by `effective()` not baked into the stored config, so the file still round-trips
what the human wrote. Consumers that must not die on a bad file (the fail-open
Stop hook) wrap resolve() themselves — this module never fabricates a default.
"""
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

# resolve_model lives in the plugin scripts dir; put it on the path off __file__
# (never CWD — hooks import this from an installed .claude/ tree). resolve_model
# owns the model taxonomy; this loader never re-implements resolution (RT-10).
_PLUGIN_SCRIPTS = Path(__file__).resolve().parent.parent / "plugins" / "hs" / "scripts"
if str(_PLUGIN_SCRIPTS) not in sys.path:
    sys.path.insert(0, str(_PLUGIN_SCRIPTS))

_ENV_OVERRIDE = "HARNESS_GEMINI_PARTNER"
_DATA = Path(__file__).resolve().parent.parent / "data" / "gemini-partner.yaml"

ADVISORY_PURPOSES = frozenset({"research", "scout", "review", "critique", "redteam"})
WRITE_PURPOSES = frozenset({"delegate", "fix"})

_REQUIRED_KEYS = ("master", "mode", "write", "stop_review_gate", "purposes",
                  "route_all_surface", "timeouts")

# Enum domains per axis. Bare off/on fold to bool under YAML 1.1, so master and
# stop_review_gate accept the folded bool and recover the token below.
_MODE = {"partner", "route-all"}
_WRITE = {"read_only", "sandbox_write"}
_STOP = {"off", "advisory", "enforce"}
# Claude-driven loop modes: converge/target are mechanical (hs:loop discipline),
# judge is a Claude-per-task criterion. The block is OPTIONAL — a missing loop
# defaults to a safe {max_rounds: 3, default_mode: converge}.
_LOOP_MODES = {"converge", "target", "judge"}
_LOOP_DEFAULT = {"max_rounds": 3, "default_mode": "converge"}

# engine axis (D3): the transport lane. `auto` resolves at call time from the
# available credential (D4). Pure enum — NO forbidden-state (D19); the only check
# is membership.
_ENGINE = {"gemini-print", "agy-print", "auto"}

# agy has no model SSOT like models.yaml — its reasoning tiers are display names.
# The static allowlist IS the taxonomy (D31): overrides_agy values must be one of
# these. Probed against the agy CLI.
_AGY_MODEL_ALLOWLIST = frozenset({
    "Gemini 3.5 Flash (Low)", "Gemini 3.5 Flash (Medium)", "Gemini 3.5 Flash (High)",
    "Gemini 3.1 Pro (Low)", "Gemini 3.1 Pro (High)",
})
# default tier → agy reasoning display name (D23: flash→Medium, pro→High).
_AGY_DEFAULT_MODELS = {
    "flash": "Gemini 3.5 Flash (Medium)",
    "pro": "Gemini 3.1 Pro (High)",
}


def _switch(value, true_word, false_word, field):
    """Recover a token that YAML may have folded to a bool. Accepts the folded
    bool, common synonyms, or the literal words; anything else is a config error."""
    if isinstance(value, bool):
        return true_word if value else false_word
    s = str(value).strip().lower()
    if s in (true_word, "true", "yes", "on", "1"):
        return true_word
    if s in (false_word, "false", "no", "off", "0"):
        return false_word
    raise SystemExit(
        "gemini-partner: `%s` must be %s|%s (got %r)"
        % (field, true_word, false_word, value))


def _available_models() -> set:
    import resolve_model
    return set(resolve_model._load()["available"])


def _coerce(cfg: Dict[str, Any], path: Path) -> Dict[str, Any]:
    """Normalize axis values to canonical tokens (bool-fold recovery + enum check).
    Returns a new dict; leaves the non-axis keys untouched."""
    out = dict(cfg)
    out["master"] = _switch(cfg["master"], "on", "off", "master")

    mode = str(cfg["mode"]).strip().lower().replace("_", "-")
    if mode not in _MODE:
        raise SystemExit("gemini-partner: `mode` must be one of %s (got %r)"
                         % (sorted(_MODE), cfg["mode"]))
    out["mode"] = mode

    write = str(cfg["write"]).strip().lower()
    if write not in _WRITE:
        raise SystemExit("gemini-partner: `write` must be one of %s (got %r)"
                         % (sorted(_WRITE), cfg["write"]))
    out["write"] = write

    # stop gate: bare `off` folds to bool False → recover to "off".
    stop = cfg["stop_review_gate"]
    if isinstance(stop, bool):
        stop = "advisory" if stop else "off"  # bare `on` is ambiguous → advisory
    stop = str(stop).strip().lower()
    if stop not in _STOP:
        raise SystemExit("gemini-partner: `stop_review_gate` must be one of %s (got %r)"
                         % (sorted(_STOP), cfg["stop_review_gate"]))
    out["stop_review_gate"] = stop

    # engine axis (OPTIONAL, default auto — an old config without it loads). Pure
    # enum like mode/write: normalize + membership-reject here, no S-state (D19).
    engine = str(cfg.get("engine", "auto")).strip().lower()
    if engine not in _ENGINE:
        raise SystemExit("gemini-partner: `engine` must be one of %s (got %r)"
                         % (sorted(_ENGINE), cfg.get("engine")))
    out["engine"] = engine

    # route_all_injection (OPTIONAL, default off): a separate axis from `mode`/
    # route_all — it gates ONLY the AUTO injection of skill methodology on the
    # route-all fan-out. Not in _REQUIRED_KEYS (F2): a shipped/dev file without it
    # must still load. Bare `on`/`off` fold to bool under YAML 1.1 → recover.
    out["route_all_injection"] = _switch(
        cfg.get("route_all_injection", "off"), "on", "off", "route_all_injection")

    # loop block (optional): normalize to always-present with safe defaults so
    # consumers never index a missing key. Value validation is in _validate.
    loop = cfg.get("loop") or {}
    if not isinstance(loop, dict):
        raise SystemExit("gemini-partner: `loop` must be a mapping (got %r)" % cfg.get("loop"))
    out["loop"] = {"max_rounds": loop.get("max_rounds", _LOOP_DEFAULT["max_rounds"]),
                   "default_mode": loop.get("default_mode", _LOOP_DEFAULT["default_mode"])}
    return out


def _validate(cfg: Dict[str, Any], path: Path) -> None:
    """Fail-closed structural + forbidden-state check. S6 is NOT here — it is a
    runtime view (effective()), not a rejectable config."""
    for key in _REQUIRED_KEYS:
        if key not in cfg:
            raise SystemExit("gemini-partner: `%s` missing in %s" % (key, path))

    # S8/S9 are checked BEFORE S1 so the injection-specific diagnostic wins: an
    # injection-on config that also has sandbox_write technically also trips S1
    # (injection-on ⟹ route-all, and route-all+sandbox_write = S1), but the more
    # precise S8 message is the useful one.

    # S8 — route_all_injection + sandbox_write: mass AUTO-injection of heavy skill
    # methodology PLUS mutating the tree is too wide a blast radius (S1 in spirit).
    if cfg.get("route_all_injection") == "on" and cfg["write"] == "sandbox_write":
        raise SystemExit(
            "gemini-partner: forbidden state S8 — route_all_injection=on with "
            "write=sandbox_write (mass auto-injection that also mutates the tree); "
            "pick one (fix %s)" % path)

    # S9 — route_all_injection only makes sense under route-all; on in partner mode
    # is a mistake that would leak methodology unintentionally. MANUAL injection
    # (Claude → relayer --skill) is unaffected — this axis gates only the AUTO path.
    if cfg.get("route_all_injection") == "on" and cfg["mode"] != "route-all":
        raise SystemExit(
            "gemini-partner: forbidden state S9 — route_all_injection=on requires "
            "mode=route-all (auto-injection is meaningless without route-all; manual "
            "--skill injection is unaffected) (fix %s)" % path)

    # S1 — route-all + sandbox_write is unrecoverable at the config layer.
    if cfg["mode"] == "route-all" and cfg["write"] == "sandbox_write":
        raise SystemExit(
            "gemini-partner: forbidden state S1 — mode=route-all with "
            "write=sandbox_write (mass fan-out that also mutates the tree); "
            "pick one (fix %s)" % path)

    # timeouts must be a mapping carrying `default` — timeout_for() reads
    # timeouts["default"] unguarded, so a missing/scalar value would escape as a
    # raw KeyError past partner_call's except (review finding).
    timeouts = cfg.get("timeouts")
    if not isinstance(timeouts, dict) or "default" not in timeouts:
        raise SystemExit(
            "gemini-partner: `timeouts` must be a mapping with a `default` key in %s"
            % path)

    # loop block: max_rounds must be a positive int (a runaway cap of 0/-1 is a
    # config error, not a silent no-op); default_mode must be a known mode.
    loop = cfg.get("loop") or {}
    mr = loop.get("max_rounds")
    if not isinstance(mr, int) or isinstance(mr, bool) or mr < 1:
        raise SystemExit(
            "gemini-partner: `loop.max_rounds` must be a positive int (got %r) (fix %s)"
            % (mr, path))
    dm = loop.get("default_mode")
    if dm not in _LOOP_MODES:
        raise SystemExit(
            "gemini-partner: `loop.default_mode` must be one of %s (got %r) (fix %s)"
            % (sorted(_LOOP_MODES), dm, path))

    # S7 — every override model must exist in the model SSOT.
    overrides = cfg.get("overrides") or {}
    if not isinstance(overrides, dict):
        raise SystemExit("gemini-partner: `overrides` must be a mapping in %s" % path)
    avail = _available_models()
    bad = ["%s=%s" % (k, v) for k, v in overrides.items() if v not in avail]
    if bad:
        raise SystemExit(
            "gemini-partner: forbidden state S7 — override model(s) not in "
            "models.yaml `available`: %s (choices: %s) (fix %s)"
            % (", ".join(bad), ", ".join(sorted(avail)), path))

    # engine_models (OPTIONAL): tier → agy reasoning display name. Must be a
    # mapping. A purpose tier with no mapping (explicit or default) WARNs at load
    # and falls back at runtime — a missing display label never crashes a run (F7).
    em = cfg.get("engine_models")
    if em is not None and not isinstance(em, dict):
        raise SystemExit("gemini-partner: `engine_models` must be a mapping in %s" % path)
    covered = set(_AGY_DEFAULT_MODELS) | set(em or {})
    uncovered = sorted({t for t in (cfg.get("purposes") or {}).values()
                        if t not in covered})
    if uncovered:
        sys.stderr.write(
            "gemini-partner: WARNING — no agy engine_model for tier(s) %s; agy-print "
            "falls back to the flash default for those purposes (fix engine_models "
            "in %s)\n" % (uncovered, path))

    # overrides_agy (OPTIONAL): per-purpose agy override, each ∈ the static
    # allowlist (D31 — agy has no models.yaml, so the allowlist is the check). The
    # flat `overrides` above stays the gemini branch untouched (additive, F1).
    oa = cfg.get("overrides_agy") or {}
    if not isinstance(oa, dict):
        raise SystemExit("gemini-partner: `overrides_agy` must be a mapping in %s" % path)
    bad_agy = ["%s=%s" % (k, v) for k, v in oa.items()
               if v not in _AGY_MODEL_ALLOWLIST]
    if bad_agy:
        raise SystemExit(
            "gemini-partner: agy override model(s) not in the allowlist: %s "
            "(choices: %s) (fix %s)"
            % (", ".join(bad_agy), ", ".join(sorted(_AGY_MODEL_ALLOWLIST)), path))


def _config_path(path: Optional[Path]) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get(_ENV_OVERRIDE)
    return Path(env) if env else _DATA


def resolve(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load + coerce + fail-closed-validate the lane config.

    `path` pins the file (tests); else $HARNESS_GEMINI_PARTNER, else the shipped
    tracked file. yaml/read errors surface, never swallowed into a default."""
    try:
        import yaml_io
    except ImportError as e:  # pragma: no cover - yaml is a harness dep
        raise SystemExit("gemini-partner: PyYAML required (%s)" % e)
    p = _config_path(path)
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("gemini-partner: config missing at %s" % p)
    except yaml_io.YAMLError as e:
        raise SystemExit("gemini-partner: bad YAML in %s: %s" % (p, e))
    if not isinstance(raw, dict):
        raise SystemExit("gemini-partner: config %s must be a YAML mapping" % p)
    # Presence check BEFORE _coerce: _coerce indexes the axis keys directly, so a
    # missing key would otherwise escape as a raw KeyError traceback instead of the
    # loader's actionable SystemExit (review finding).
    for key in _REQUIRED_KEYS:
        if key not in raw:
            raise SystemExit("gemini-partner: `%s` missing in %s" % (key, p))
    cfg = _coerce(raw, p)
    _validate(cfg, p)
    return cfg


def effective(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Runtime-effective view. S6: master off ⇒ the lane is inert regardless of
    what the other axes say (mode=inert, write=read_only, stop gate off). Returns
    a copy; the stored config is never mutated."""
    eff = dict(cfg)
    if cfg["master"] == "off":
        eff["mode"] = "inert"
        eff["write"] = "read_only"
        eff["stop_review_gate"] = "off"
        eff["route_all_injection"] = "off"  # S6': master off ⇒ no auto-injection
    return eff


def tier_for(cfg: Dict[str, Any], purpose: str) -> str:
    """Model id for a purpose: purposes[purpose] names a tier, resolved through
    the model SSOT (never a hardcoded id, RT-10)."""
    import resolve_model
    tier = (cfg.get("purposes") or {}).get(purpose)
    if tier is None:
        raise SystemExit("gemini-partner: no purpose mapping for %r" % purpose)
    return resolve_model.resolve_model(tier=tier)


def _resolve_engine(cfg: Dict[str, Any]) -> str:
    """Concretize the engine axis to gemini-print|agy-print. A pinned engine is
    returned as-is (no env sniff — the pin wins, D7). `auto` detects the available
    credential (D4): GEMINI_API_KEY present → gemini-print, else agy-print (OAuth),
    precedence gemini→agy."""
    engine = cfg.get("engine", "auto")
    if engine != "auto":
        return engine
    if os.environ.get("GEMINI_API_KEY"):
        return "gemini-print"
    return "agy-print"


def _agy_login_present() -> bool:
    """Heuristic: does an agy Google-OAuth session LIKELY exist? Checks the agy CLI
    home dir presence — NOT token validity (a stale/expired token still leaves the
    dir); the canary (D18) is the real reachability gate. HARNESS_AGY_CMD (a wired
    override/fake binary) counts as available; HARNESS_AGY_HOME overrides the dir for
    tests. Default: ~/.gemini/antigravity-cli (the agy CLI home, probed)."""
    if os.environ.get("HARNESS_AGY_CMD"):
        return True
    home = os.environ.get("HARNESS_AGY_HOME")
    if home:
        return Path(home).exists()
    return (Path.home() / ".gemini" / "antigravity-cli").exists()


def _auth_inert(cfg: Dict[str, Any]) -> bool:
    """True iff engine=auto but NEITHER credential is present — no GEMINI_API_KEY AND
    no agy login heuristic — so the lane cannot reach any engine (D25). A pinned
    engine is never inert-auth here (its own canary reports reachability). presence
    != validity, so this only short-circuits the obvious 'nothing configured' case;
    the caller must STILL print how to enable the lane (never a silent abort)."""
    if cfg.get("engine", "auto") != "auto":
        return False
    return not os.environ.get("GEMINI_API_KEY") and not _agy_login_present()


def _agy_model_for(cfg: Dict[str, Any], purpose: str) -> str:
    """agy reasoning display name for a purpose. overrides_agy wins (allowlist-
    validated at load), else engine_models[tier], else the tier default, else the
    flash default + a runtime WARN (F7 — a missing label never crashes a run). The
    gemini branch (_model_for/tier_for) is untouched: agy is a parallel reader."""
    override = (cfg.get("overrides_agy") or {}).get(purpose)
    if override:
        return override
    tier = (cfg.get("purposes") or {}).get(purpose)
    if tier is None:
        raise SystemExit("gemini-partner: no purpose mapping for %r" % purpose)
    name = (cfg.get("engine_models") or {}).get(tier) or _AGY_DEFAULT_MODELS.get(tier)
    if name is None:
        sys.stderr.write(
            "gemini-partner: WARNING — no agy engine_model for tier %r (purpose "
            "%r); using the flash default\n" % (tier, purpose))
        name = _AGY_DEFAULT_MODELS["flash"]
    return name


def is_advisory(purpose: str) -> bool:
    """True for read-only advisory roles; False for the write roles (delegate/fix)."""
    return purpose in ADVISORY_PURPOSES


def should_route(cfg: Dict[str, Any], skill: str) -> bool:
    """Route-all decision: True iff the (EFFECTIVE) config is in route-all mode AND
    `skill` is in the allowlist. `route_all_surface: all` (dogfood) routes every
    skill. Pass an `effective()` cfg — master=off makes mode `inert`, so a killed
    lane never routes."""
    if cfg.get("mode") != "route-all":
        return False
    surface = cfg.get("route_all_surface") or []
    if surface == "all":
        return True
    return skill in surface


def _skill_is_injectable(name: str) -> bool:
    """Resolve a skill NAME to its dir and consult its injectable frontmatter
    (fail-closed: absent field or unresolvable skill → False). Kept as a module
    seam so should_route_injection is unit-testable without a live skill tree."""
    try:
        import catalog
        import check_skill_structure as css
        cat = catalog.load_catalog()
        dir_name = (cat["slug_to_dir"].get(name)
                    or cat["slug_to_dir"].get(name.replace(":", "-")))
        if not dir_name:
            return False
        for src in catalog.skills_dirs():
            cand = src / dir_name
            if (cand / "SKILL.md").is_file():
                return css.is_injectable(str(cand))
    except Exception:
        return False
    return False


def should_route_injection(cfg: Dict[str, Any], skill: str) -> bool:
    """AUTO skill-injection gate: True iff (route-all mode AND skill in the
    route-all surface — should_route) AND route_all_injection is on AND the skill
    is injectable. Every condition ANDs — any one missing means no auto-injection.
    This gates ONLY the AUTO path; manual injection (Claude → relayer --skill) is
    never blocked by this axis. Pass an effective() cfg so a killed lane never
    auto-injects (S6')."""
    if cfg.get("route_all_injection") != "on":
        return False
    if not should_route(cfg, skill):
        return False
    return _skill_is_injectable(skill)


def timeout_for(cfg: Dict[str, Any], verb: str) -> int:
    """Per-verb timeout, falling back to timeouts.default (D10)."""
    timeouts = cfg.get("timeouts") or {}
    if verb in timeouts:
        return int(timeouts[verb])
    return int(timeouts["default"])


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="resolve the gemini partner lane config")
    ap.add_argument("--file", default=None, help="explicit config path")
    ap.add_argument("--effective", action="store_true",
                    help="print the runtime-effective view (S6 applied)")
    ap.add_argument("--should-route", metavar="SKILL", default=None,
                    help="print 'route' if this skill routes to gemini under the "
                         "effective config, else 'claude' (route-all gate)")
    args = ap.parse_args(argv)
    cfg = effective(resolve(args.file))
    if args.should_route is not None:
        print("route" if should_route(cfg, args.should_route) else "claude")
        return 0
    if not args.effective:
        cfg = resolve(args.file)
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
