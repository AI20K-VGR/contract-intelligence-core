#!/usr/bin/env python3
"""partner_config.py — gate-grade loader for the provider-agnostic partner lane
POLICY (twin of gemini_partner_config.py, deliberately NOT importing it — the
two lanes stay independent so one config bug can never couple both).

SSOT: harness/data/partner.yaml. Resolution order (env-bound, like
HARNESS_GUARD_POLICY — a change needs a restart, never a live in-session flip):

    explicit path arg  >  $HARNESS_PARTNER  >  shipped tracked file

This is POLICY only — no provider list, no engine/model axis. Provider
discovery (which CLI/CCS lane is actually reachable) is a separate concern
(partner_preflight.py); `purposes` here maps a call purpose to a
methodology-template KEY, never a model tier — this loader never calls
resolve_model.

`resolve()` is fail-CLOSED: bad YAML, a missing required key, or the
read_only+allow_live:on forbidden combo all raise SystemExit with an
actionable reason (path + fix). The master-off-implies-inert rule is a
*runtime* view applied by `effective()`, not baked into the stored config —
the file still round-trips what the human wrote.
"""
import math
import os
import sys
from pathlib import Path
from typing import Any, Dict, Optional

_ENV_OVERRIDE = "HARNESS_PARTNER"
_DATA = Path(__file__).resolve().parent.parent / "data" / "partner.yaml"

_WRITE = {"read_only", "worktree_staged"}

_REQUIRED_KEYS = ("master", "write", "allow_live", "secret_scrub", "purposes",
                  "timeouts", "retry", "cost_warn_usd")

# Advisory-only lane: every purpose this config maps is a read-only call
# (review/adversarial-review/research/critique) — no write/fix verb exists
# here, unlike the gemini lane's delegate/fix split.
ADVISORY_PURPOSES = frozenset({"review", "adversarial-review", "research", "critique"})


def _switch(value, field: str) -> str:
    """Recover an on/off token that YAML 1.1 may have folded to a bool. Accepts
    the folded bool, common synonyms, or the literal words; anything else is a
    config error."""
    if isinstance(value, bool):
        return "on" if value else "off"
    s = str(value).strip().lower()
    if s in ("on", "true", "yes", "1"):
        return "on"
    if s in ("off", "false", "no", "0"):
        return "off"
    raise SystemExit("partner: `%s` must be on|off (got %r)" % (field, value))


def _coerce(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Normalize axis values to canonical tokens (bool-fold recovery + enum
    check). Returns a new dict; leaves non-axis keys untouched."""
    out = dict(cfg)
    out["master"] = _switch(cfg["master"], "master")
    out["allow_live"] = _switch(cfg["allow_live"], "allow_live")

    write = str(cfg["write"]).strip().lower()
    if write not in _WRITE:
        raise SystemExit("partner: `write` must be one of %s (got %r)"
                         % (sorted(_WRITE), cfg["write"]))
    out["write"] = write
    return out


def _validate(cfg: Dict[str, Any], path: Path) -> None:
    """Fail-closed structural + forbidden-state check. The master-off-implies-
    inert rule is NOT here — it is a runtime view (effective()), not a
    rejectable config."""
    for key in _REQUIRED_KEYS:
        if key not in cfg:
            raise SystemExit("partner: `%s` missing in %s" % (key, path))

    # read_only + allow_live:on is a contradictory config: live-write is
    # meaningless when the lane cannot write at all. Reject rather than
    # silently normalize, so a human notices the mistake.
    if cfg["write"] == "read_only" and cfg["allow_live"] == "on":
        raise SystemExit(
            "partner: forbidden config — write=read_only with allow_live=on "
            "(live-write is meaningless under read_only); pick one (fix %s)" % path)

    # timeouts must be a mapping carrying `default` — timeout_for() reads
    # timeouts["default"] unguarded, so a missing/scalar value would otherwise
    # escape as a raw KeyError past a caller's except.
    timeouts = cfg.get("timeouts")
    if not isinstance(timeouts, dict) or "default" not in timeouts:
        raise SystemExit(
            "partner: `timeouts` must be a mapping with a `default` key in %s" % path)

    # cost_warn_usd must be a non-negative, non-NaN number — a bad value must
    # fail HERE, not crash later at a threshold compare. NaN is a float and
    # every `NaN < 0` comparison is False, so it would otherwise sail past
    # the `cost < 0` check and silently disable the cost-warn threshold.
    cost = cfg.get("cost_warn_usd")
    cost_is_number = isinstance(cost, (int, float)) and not isinstance(cost, bool)
    if not cost_is_number or cost < 0 or (isinstance(cost, float) and math.isnan(cost)):
        raise SystemExit(
            "partner: `cost_warn_usd` must be a number >= 0 (got %r) in %s"
            % (cost, path))


def _config_path(path: Optional[Path]) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get(_ENV_OVERRIDE)
    return Path(env) if env else _DATA


def resolve(path: Optional[Path] = None) -> Dict[str, Any]:
    """Load + coerce + fail-closed-validate the partner lane policy.

    `path` pins the file (tests); else $HARNESS_PARTNER, else the shipped
    tracked file. yaml/read errors surface, never swallowed into a default."""
    try:
        import yaml_io
    except ImportError as e:  # pragma: no cover - yaml is a harness dep
        raise SystemExit("partner: PyYAML required (%s)" % e)
    p = _config_path(path)
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        raise SystemExit("partner: config missing at %s" % p)
    except yaml_io.YAMLError as e:
        raise SystemExit("partner: bad YAML in %s: %s" % (p, e))
    if not isinstance(raw, dict):
        raise SystemExit("partner: config %s must be a YAML mapping" % p)
    # Presence check BEFORE _coerce: _coerce indexes the axis keys directly, so
    # a missing key would otherwise escape as a raw KeyError instead of the
    # loader's actionable SystemExit.
    for key in _REQUIRED_KEYS:
        if key not in raw:
            raise SystemExit("partner: `%s` missing in %s" % (key, p))
    cfg = _coerce(raw)
    _validate(cfg, p)
    return cfg


def effective(cfg: Dict[str, Any]) -> Dict[str, Any]:
    """Runtime-effective view: master off ⇒ the lane is inert regardless
    of what the other axes say (write forced read_only, allow_live forced
    off). Returns a copy; the stored config is never mutated."""
    eff = dict(cfg)
    if cfg["master"] == "off":
        eff["write"] = "read_only"
        eff["allow_live"] = "off"
    return eff


def timeout_for(cfg: Dict[str, Any], verb: str) -> int:
    """Per-verb timeout, falling back to timeouts.default."""
    timeouts = cfg.get("timeouts") or {}
    if verb in timeouts:
        return int(timeouts[verb])
    return int(timeouts["default"])


def is_advisory(purpose: str) -> bool:
    """True for every purpose this lane knows — the lane is advisory-only (no
    write/fix verb exists here, unlike the gemini lane)."""
    return purpose in ADVISORY_PURPOSES


def allow_live(cfg: Dict[str, Any]) -> bool:
    """Layer-1 gate for --live: True iff the EFFECTIVE (master-off-normalized)
    allow_live is on. Always re-derives effective() itself so a caller can
    never pass the raw stored config and bypass the master-off kill-switch."""
    return effective(cfg)["allow_live"] == "on"


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="resolve the partner lane policy config")
    ap.add_argument("--file", default=None, help="explicit config path")
    args = ap.parse_args(argv)
    cfg = resolve(args.file)
    print(json.dumps(cfg, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
