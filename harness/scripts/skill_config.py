#!/usr/bin/env python3
"""skill_config.py — resolver for harness/data/skill-config.yaml (human-edited plan + skill knobs).

Three namespaces:
  plan.validation.{mode,minQuestions,maxQuestions,focusAreas} — how hs:plan runs its validation
      interview (mode enum, question bounds, which areas to probe).
  plan.grid.autoPreregister — freeze an N/A ruleset at plan Step 6 (before the fill).
  plan.resolution.branchPattern — a regex that extracts a plan slug from a branch name.
  skills.<name>.* — an open per-skill option bag (e.g. skills.research.useGemini).

Dual posture, mirroring output_config:
  load()        — fails OPEN: a missing/malformed file or a single bad field degrades to the
                  default and records the reason under `_diag`, so a fail-open hook/skill is
                  never killed by a corrupt config.
  load_strict() — fails CLOSED: raises SkillConfigError on a missing/malformed file or any bad
                  value, for a gate that must not proceed on a broken config.

Test/ephemeral seam: pass an explicit `path`, or set HARNESS_SKILL_CONFIG (load() only; the
strict gate path reads tracked config unless a path is passed).

ReDoS guard: `plan.resolution.branchPattern` is a regex supplied by human-edited config,
then matched against a real git branch name in `extract_slug()` — both the pattern and
(in a multi-contributor repo) the input are outside this module's control. Measured: a
catastrophic-backtracking pattern (`(a|a)+b`) against a 28-30 char input already hangs
stdlib `re` past 15s and keeps growing exponentially with input length, while a
legitimate branchPattern match takes well under a microsecond. Compiled + matched via
`regex` (a drop-in `re` superset with a `timeout=` kwarg `re` lacks) with a 1.0s bound —
generously above real usage, far below where a hang becomes noticeable.
"""
import os
from pathlib import Path

import regex

_DEFAULT_PATH = Path(__file__).resolve().parent.parent / "data" / "skill-config.yaml"
_ENV = "HARNESS_SKILL_CONFIG"

_MODES = ("prompt", "auto", "strict", "none")
_FOCUS = ("assumptions", "risks", "tradeoffs", "architecture",
          "security", "performance", "testing", "dependencies")
_DEFAULT_BRANCH_PATTERN = r"(?:feat|fix|chore|refactor|docs)/(?:[^/]+/)?(.+)"

# Generously above legitimate match latency (measured: sub-microsecond for the default
# branchPattern against a typical branch name), far below where a catastrophic pattern's
# hang becomes a problem (measured: already >15s at a 28-30 char adversarial input) —
# see the module docstring's ReDoS guard note.
_MATCH_TIMEOUT_SECONDS = 1.0


def defaults() -> dict:
    """A fresh copy of the fully-defaulted config (never mutate the module state)."""
    return {
        "plan": {
            "validation": {
                "mode": "prompt",
                "minQuestions": 3,
                "maxQuestions": 8,
                "focusAreas": ["assumptions", "risks", "tradeoffs", "architecture"],
            },
            "resolution": {"branchPattern": _DEFAULT_BRANCH_PATTERN},
            # Freeze an N/A ruleset automatically at hs:plan Step 6. ON by
            # default; the reasoning + what would justify flipping it lives
            # beside the key in skill-config.yaml.
            "grid": {"autoPreregister": True},
        },
        "skills": {},
    }


class SkillConfigError(Exception):
    """Raised by load_strict on a missing/malformed config or a bad value (gate path)."""


def _validate_validation(v, strict, diag) -> dict:
    """Validate + coerce a plan.validation mapping onto the defaults. `strict` raises;
    non-strict records to `diag` and keeps the default for a bad field."""
    out = defaults()["plan"]["validation"]
    if not isinstance(v, dict):
        if v is not None:
            _fail("plan.validation must be a mapping", strict, diag)
        return out
    mode = v.get("mode", out["mode"])
    if mode in _MODES:
        out["mode"] = mode
    else:
        _fail("plan.validation.mode must be one of %s (got %r)" % (list(_MODES), mode), strict, diag)
    for key, lo, hi in (("minQuestions", 0, 20), ("maxQuestions", 1, 20)):
        val = v.get(key, out[key])
        if isinstance(val, int) and not isinstance(val, bool) and lo <= val <= hi:
            out[key] = val
        else:
            _fail("plan.validation.%s must be an int in [%d,%d] (got %r)" % (key, lo, hi, val), strict, diag)
    areas = v.get("focusAreas", out["focusAreas"])
    if isinstance(areas, list) and all(a in _FOCUS for a in areas):
        out["focusAreas"] = list(areas)
    else:
        _fail("plan.validation.focusAreas must be a subset of %s (got %r)" % (list(_FOCUS), areas), strict, diag)
    return out


def _fail(msg, strict, diag):
    if strict:
        raise SkillConfigError(msg)
    diag.append(msg)


def _merge(raw, strict):
    cfg = defaults()
    diag = []
    if not isinstance(raw, dict):
        if raw is not None:
            _fail("skill-config root must be a mapping", strict, diag)
        if diag:
            cfg["_diag"] = diag
        return cfg
    plan = raw.get("plan")
    if isinstance(plan, dict):
        cfg["plan"]["validation"] = _validate_validation(plan.get("validation"), strict, diag)
        grid = plan.get("grid")
        if isinstance(grid, dict):
            auto = grid.get("autoPreregister", True)
            if isinstance(auto, bool):
                cfg["plan"]["grid"]["autoPreregister"] = auto
            else:
                _fail("plan.grid.autoPreregister must be a boolean (got %r)" % (auto,),
                      strict, diag)
        elif grid is not None:
            _fail("plan.grid must be a mapping", strict, diag)
        res = plan.get("resolution")
        if isinstance(res, dict):
            bp = res.get("branchPattern", _DEFAULT_BRANCH_PATTERN)
            if isinstance(bp, str) and bp.strip():
                # Test-compile via `regex` (the module extract_slug() actually
                # matches with, see its docstring / the ReDoS guard note) so a
                # pattern accepted here is guaranteed to also compile there.
                try:
                    regex.compile(bp)
                    cfg["plan"]["resolution"]["branchPattern"] = bp
                except regex.error as e:
                    _fail("plan.resolution.branchPattern is not a valid regex: %s" % e, strict, diag)
            else:
                _fail("plan.resolution.branchPattern must be a non-empty regex string", strict, diag)
    elif plan is not None:
        _fail("plan must be a mapping", strict, diag)
    skills = raw.get("skills")
    if isinstance(skills, dict):
        cfg["skills"] = {k: v for k, v in skills.items() if isinstance(v, dict)}
    elif skills is not None:
        _fail("skills must be a mapping of <name> -> options", strict, diag)
    if diag:
        cfg["_diag"] = diag
    return cfg


def _read(path, env_ok):
    p = Path(path) if path else (Path(os.environ[_ENV]) if env_ok and os.environ.get(_ENV) else _DEFAULT_PATH)
    import yaml_io  # lazy
    return p, yaml_io.safe_load(p.read_text(encoding="utf-8"))


def load(path=None) -> dict:
    """Fail-OPEN resolve: missing/malformed file or a bad field → default + `_diag`."""
    diag = []
    try:
        _, raw = _read(path, env_ok=True)
    except FileNotFoundError:
        cfg = defaults(); cfg["_diag"] = ["skill-config missing — using defaults"]; return cfg
    except Exception as e:  # noqa: BLE001 — unreadable YAML degrades, never raises
        cfg = defaults(); cfg["_diag"] = ["skill-config unreadable: %s" % e]; return cfg
    return _merge(raw, strict=False)


def load_strict(path=None) -> dict:
    """Fail-CLOSED resolve for a gate: raises SkillConfigError on any problem."""
    try:
        _, raw = _read(path, env_ok=False)
    except FileNotFoundError as e:
        raise SkillConfigError("skill-config not found: %s" % e)
    except Exception as e:
        raise SkillConfigError("skill-config unreadable: %s" % e)
    return _merge(raw, strict=True)


def skill_options(name, path=None) -> dict:
    """The option bag for one skill (skills.<name>), or {} when absent."""
    return dict(load(path).get("skills", {}).get(name, {}))


def extract_slug(branch, path=None):
    """Apply plan.resolution.branchPattern to a branch name; return the first capture group
    (the plan slug) or None when the branch does not match (or a catastrophic-backtracking
    pattern would time out matching it — see the module docstring's ReDoS guard note;
    treated the same as "no match", never a hang or a raised exception on this path)."""
    pattern = load(path)["plan"]["resolution"]["branchPattern"]
    try:
        m = regex.match(pattern, str(branch or ""), timeout=_MATCH_TIMEOUT_SECONDS)
    except TimeoutError:
        return None
    return m.group(1) if m and m.groups() else None


if __name__ == "__main__":
    import json
    import sys
    if "--resolved" in sys.argv:
        cfg = load()
        cfg.pop("_diag", None)
        json.dump(cfg, sys.stdout, ensure_ascii=False, indent=2)
        sys.stdout.write("\n")
