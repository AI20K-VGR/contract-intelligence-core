#!/usr/bin/env python3
"""user_override.py — the per-repo (layer-b) operational-rule override layer.

A repo tunes the operational rules with override files: either a folder of
`*.yaml` (default `docs/standards/`, set by `harness/data/standards.yaml
user_rules_dir`) whose `overrides:` lists are merged, or the legacy single
`<repo>/standards.user.yaml` used as a fallback when the folder is empty. The
env var `HARNESS_USER_OVERRIDE` (a file OR a dir) overrides both. Every override
is LOUD (it surfaces a warning) and MUST carry a non-empty `reason:` — silent or
unexplained overrides are refused.

Precedence floor — a floor rule is an inviolable safety layer:
  - an override BY ID targeting a floor rule is refused (the rule is unchanged),
    whether that floor is in the base set or was declared by an earlier override
    in the same pass (the live by-id view is checked);
  - a NEW-id user rule whose scope overlaps a BASE (shipped) floor with a WEAKER
    posture (lower severity, or disabled) is refused too — you cannot dodge a
    shipped floor by adding a fresh id. This new-id-shadow refusal applies ONLY
    to base floors: a repo's own layer-b rules coexist with its own declared
    floor (same author, not a dodge), so a broad-scoped self-floor does not
    refuse the repo's other rules on overlapping scopes.
An override may itself declare `floor: true` to make a repo-local rule
inviolable. Floor is also enforced at the coverage gate — defense in depth.

Conflict-detect (advisory in 2.2): a user rule whose scope overlaps a non-floor
std rule with an opposite severity is flagged. Disjoint scopes never warn (uses
the P0 glob-intersection predicate, not a substring guess).

Format:
    overrides:
      - rule_id: STD-...     # an existing rule (modify) or a new id (add)
        reason: "..."        # REQUIRED, non-empty
        severity: info       # optional fields to set
        enabled: false
        scope: ["**/*.py"]

API:
    load(repo_root) -> [override dict, ...]
    apply(rules, overrides) -> (new_rules, warnings)
    detect_conflicts(user_rules, std_rules) -> [finding, ...]
"""

import os
import sys
from pathlib import Path
from typing import Any, Dict, List, Tuple

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

from scope_match import globs_overlap

# Severity posture ranking — a lower rank is a weaker posture. A floor-shadow is
# a new rule that drops below the floor rule's rank (or disables) on its scope.
# Keys must stay in sync with standards_graph's severity vocabulary (currently
# critical/info); an unranked value falls to the weakest rank (1).
_SEV_RANK = {"critical": 2, "info": 1}

# Fields an override may set on the target rule. `floor` lets a repo-local rule
# declare itself inviolable (a layer-b floor) — once set, a later override that
# weakens it is refused, the same as a shipped floor.
_OVERRIDE_FIELDS = ("severity", "enabled", "scope", "detector", "relates_to_std", "floor")


def _knob_user_rules_dir(repo_root) -> str:
    """The layer-b folder, from harness/data/standards.yaml (default docs/standards/)."""
    knob = Path(repo_root) / "harness" / "data" / "standards.yaml"
    try:
        import yaml_io
        data = yaml_io.safe_load(knob.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            v = data.get("user_rules_dir")
            if isinstance(v, str) and v.strip():
                return v.strip()
    except Exception:  # noqa: BLE001 — a missing/malformed knob uses the default
        pass
    return "docs/standards/"


def _dir_files(folder: Path) -> List[Path]:
    """Every override file in a folder, sorted. `*.yaml` already covers the
    `*.std.yaml` files the layer-b folder uses (they end in .yaml)."""
    return sorted(folder.glob("*.yaml")) if folder.is_dir() else []


def _override_sources(repo_root) -> List[Path]:
    """Ordered override files to read.

    Precedence: env HARNESS_USER_OVERRIDE (a file OR a dir) wins; else the knob
    folder `user_rules_dir` when it holds override files; else the legacy root
    standards.user.yaml as a fallback (kept until the folder is populated)."""
    raw = os.environ.get("HARNESS_USER_OVERRIDE")
    if raw:
        p = Path(raw)
        return _dir_files(p) if p.is_dir() else [p]
    folder = Path(repo_root) / _knob_user_rules_dir(repo_root)
    files = _dir_files(folder)
    if files:
        return files
    legacy = Path(repo_root) / "standards.user.yaml"
    return [legacy] if legacy.exists() else []


def _load_one(p: Path) -> List[Dict[str, Any]]:
    """Read one override file's `overrides:` list. A missing or malformed file
    yields no overrides (fail-soft, isolated — one bad file in a folder never
    breaks its neighbours)."""
    try:
        import yaml_io
        data = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except (FileNotFoundError, OSError):
        return []
    except Exception:  # noqa: BLE001 — a malformed YAML file applies no override
        return []
    if not isinstance(data, dict):
        return []
    ov = data.get("overrides")
    return [o for o in ov if isinstance(o, dict)] if isinstance(ov, list) else []


def load(repo_root) -> List[Dict[str, Any]]:
    """Read the merged override list from the layer-b folder (or the legacy
    single file). Each source is fail-soft; a missing layer yields no overrides
    (the std tree stands on its own)."""
    out: List[Dict[str, Any]] = []
    for p in _override_sources(repo_root):
        out.extend(_load_one(p))
    return out


def _scope_overlaps_any(a_globs, b_globs) -> bool:
    return any(globs_overlap(a, b)
               for a in (a_globs or []) if isinstance(a, str)
               for b in (b_globs or []) if isinstance(b, str))


def _weakens(ov: Dict[str, Any], floor_rule: Dict[str, Any]) -> bool:
    """True when an override/new rule weakens a floor rule's posture on the same
    scope: disabling it, or lowering severity below the floor's rank."""
    if ov.get("enabled") is False:
        return True
    ov_rank = _SEV_RANK.get(ov.get("severity", "info"), 1)
    fl_rank = _SEV_RANK.get(floor_rule.get("severity", "critical"), 2)
    return ov_rank < fl_rank


def apply(rules, overrides) -> Tuple[List[Dict[str, Any]], List[str]]:
    """Apply the overrides to a copy of `rules`, returning (rules, warnings).

    Refuses (with a loud warning, leaving the rule unchanged): an override with
    no reason; an override of a floor rule; a new-id rule that shadows a floor
    rule with a weaker posture. Otherwise applies the fields by id, or adds a new
    user rule."""
    out = [dict(r) for r in rules]
    by_id = {r.get("id"): r for r in out}
    floor_rules = [r for r in out if r.get("floor")]
    warnings: List[str] = []

    for ov in overrides:
        if not isinstance(ov, dict):
            warnings.append("layer-b override: skipped a malformed override entry")
            continue
        rid = ov.get("rule_id") or ov.get("id")
        if not isinstance(rid, str) or not rid:
            # a non-string rule_id (a list/dict) is unhashable and malformed —
            # skip it (never raise into the consumer)
            warnings.append(
                "layer-b override: skipped an override with a non-string rule_id")
            continue
        reason = ov.get("reason")
        if not (isinstance(reason, str) and reason.strip()):
            warnings.append(
                "layer-b override: override of %r REFUSED — a non-empty "
                "reason is required" % rid)
            continue

        target = by_id.get(rid)
        if target is not None:
            if target.get("floor"):
                warnings.append(
                    "layer-b override: override of floor rule %r REJECTED — "
                    "floor rules are non-overridable (safety invariant)" % rid)
                continue
            for f in _OVERRIDE_FIELDS:
                if f in ov:
                    target[f] = ov[f]
            target["_user_override_reason"] = reason
            warnings.append(
                "layer-b override: rule %r overridden (reason: %s)" % (rid, reason))
            continue

        # new id — refuse if it shadows a floor rule with a weaker posture
        shadowed = next(
            (fr for fr in floor_rules
             if _scope_overlaps_any(ov.get("scope"), fr.get("scope"))
             and _weakens(ov, fr)), None)
        if shadowed is not None:
            warnings.append(
                "layer-b override: new rule %r REJECTED — its scope shadows "
                "floor rule %r with a weaker posture (no floor-shadow)"
                % (rid, shadowed.get("id")))
            continue
        newrule = {
            "id": rid, "type": "rule",
            "scope": ov.get("scope") or [],
            "severity": ov.get("severity", "info"),
            "enabled": ov.get("enabled", True),
            "floor": bool(ov.get("floor", False)),
            "detector": ov.get("detector"),
            "relates_to_std": ov.get("relates_to_std") or [],
            "_user_override_reason": reason,
        }
        out.append(newrule)
        by_id[rid] = newrule
        warnings.append(
            "layer-b override: new rule %r added (reason: %s)" % (rid, reason))

    return out, warnings


def detect_conflicts(user_rules, std_rules) -> List[Dict[str, Any]]:
    """Flag a user rule that overlaps a non-floor std rule (scope intersection or
    a shared relates_to_std) with an OPPOSITE severity. Disjoint scopes never
    warn. Advisory — a finding is a signal, not a block."""
    findings: List[Dict[str, Any]] = []
    for u in user_rules:
        u_scope = u.get("scope") or []
        u_rel = set(u.get("relates_to_std") or [])
        for s in std_rules:
            if s.get("floor"):
                continue  # floor is handled by refuse, not advisory conflict
            related = bool(u_rel & {s.get("id")})
            overlap = _scope_overlaps_any(u_scope, s.get("scope"))
            if not (related or overlap):
                continue
            u_sev, s_sev = u.get("severity"), s.get("severity")
            # Compare only when BOTH severities are present — a malformed rule
            # missing `severity` is not an "opposite severity" conflict.
            if not (u_sev and s_sev) or u_sev == s_sev:
                continue
            via = "scope overlaps" if overlap else "shared relates_to_std"
            findings.append({
                "user_rule": u.get("id"),
                "std_rule": s.get("id"),
                "detail": "%s with opposite severity (%s vs %s)"
                          % (via, u_sev, s_sev),
            })
    return findings
