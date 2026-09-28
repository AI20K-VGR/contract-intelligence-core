#!/usr/bin/env python3
"""Centralized model-id resolver for the LLM-CLI surface (gemini / agy).

Single source of truth: `harness/plugins/hs/data/models.yaml`. Skills (use-mcp,
scout, ai-multimodal) never hardcode a model id — they call this script so the
whole taxonomy lives in one file.

Resolution the skills document: default -> fallback -> `--list` (hand `available`
to the LLM to pick). The env var $GEMINI_MODEL overrides `default`.

CLI:
    resolve_model.py                 # print the default model (env override wins)
    resolve_model.py --fallback      # print the fallback model
    resolve_model.py --tier pro|flash|flash_lite
    resolve_model.py --list          # print every available model (one per line)
    resolve_model.py --json          # dump the whole config as JSON

Importable:
    from resolve_model import resolve_model
    resolve_model()            -> default (env $GEMINI_MODEL wins)
    resolve_model('fallback')  -> fallback
    resolve_model(tier='pro')  -> tier model

Fail-closed: a config whose default/fallback/tier value is not in `available`,
or an unknown --tier, exits non-zero with an actionable reason. yaml/read errors
are surfaced, never swallowed into a silent default.
"""
import argparse
import json
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_ENV_OVERRIDE = "GEMINI_MODEL"
_DATA = Path(__file__).resolve().parent.parent / "data" / "models.yaml"


def _load(path: Path = _DATA) -> Dict[str, Any]:
    # yaml_io (harness/scripts/) is not on sys.path by default from a skill's
    # scripts/ dir -- add it before importing (mirrors partner_companion.py /
    # gemini_companion.py's own module-level bootstrap, done lazily here since
    # this loader is only reached when a config read is actually needed).
    _harness_scripts = str(Path(__file__).resolve().parents[3] / "scripts")
    if _harness_scripts not in sys.path:
        sys.path.append(_harness_scripts)
    try:
        import yaml_io
    except ImportError as e:  # pragma: no cover - ruamel.yaml is a harness dep
        raise SystemExit(f"resolve_model: ruamel.yaml required ({e})")
    try:
        cfg = yaml_io.safe_load(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit(f"resolve_model: model config missing at {path}")
    except yaml_io.YAMLError as e:
        raise SystemExit(f"resolve_model: bad YAML in {path}: {e}")
    _validate(cfg, path)
    return cfg


def _validate(cfg: Dict[str, Any], path: Path) -> None:
    for key in ("available", "tiers", "default", "fallback"):
        if key not in cfg:
            raise SystemExit(f"resolve_model: '{key}' missing in {path}")
    available = cfg["available"]
    if not isinstance(available, list) or not available:
        raise SystemExit(f"resolve_model: 'available' must be a non-empty list in {path}")
    avail = set(available)
    bad = []
    if cfg["default"] not in avail:
        bad.append(f"default={cfg['default']}")
    if cfg["fallback"] not in avail:
        bad.append(f"fallback={cfg['fallback']}")
    for tier, model in (cfg["tiers"] or {}).items():
        if model not in avail:
            bad.append(f"tiers.{tier}={model}")
    if bad:
        raise SystemExit(
            "resolve_model: these config values are not in `available`: "
            + ", ".join(bad)
            + f" (fix {path})"
        )


def resolve_model(kind: str = "default", tier: Optional[str] = None,
                  env: bool = True, cfg: Optional[Dict[str, Any]] = None) -> str:
    """Return a model id. `kind`='default'|'fallback', or pass `tier`.

    With kind='default' and env=True, $GEMINI_MODEL (if set) wins verbatim —
    a runtime override is respected even if it is not in `available`.
    """
    cfg = cfg or _load()
    if tier is not None:
        try:
            return cfg["tiers"][tier]
        except KeyError:
            raise SystemExit(
                f"resolve_model: unknown tier '{tier}'; "
                f"choices: {', '.join(cfg['tiers'])}"
            )
    if kind == "fallback":
        return cfg["fallback"]
    if kind == "default":
        if env:
            override = os.environ.get(_ENV_OVERRIDE)
            if override:
                return override
        return cfg["default"]
    raise SystemExit(f"resolve_model: unknown kind '{kind}'")


def main(argv=None) -> int:
    p = argparse.ArgumentParser(description="Resolve the LLM-CLI model id.")
    g = p.add_mutually_exclusive_group()
    g.add_argument("--fallback", action="store_true", help="print the fallback model")
    g.add_argument("--tier", metavar="pro|flash|flash_lite", help="print a named tier model")
    g.add_argument("--list", action="store_true", help="print every available model")
    g.add_argument("--json", action="store_true", help="dump the whole config as JSON")
    p.add_argument("--no-env", action="store_true", help="ignore $GEMINI_MODEL override")
    args = p.parse_args(argv)

    cfg = _load()
    if args.list:
        print("\n".join(cfg["available"]))
        return 0
    if args.json:
        print(json.dumps(cfg, ensure_ascii=False))
        return 0
    if args.tier:
        print(resolve_model(tier=args.tier, cfg=cfg))
        return 0
    kind = "fallback" if args.fallback else "default"
    print(resolve_model(kind, env=not args.no_env, cfg=cfg))
    return 0


if __name__ == "__main__":
    sys.exit(main())
