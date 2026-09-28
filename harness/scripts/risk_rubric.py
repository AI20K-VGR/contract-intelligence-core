#!/usr/bin/env python3
"""risk_rubric.py — derive a change-risk tier from the files a diff touches.

Hard-gate globs (auth, migration, secret-handling, API-contract) force the
high_risk tier regardless of flag count; otherwise the count of risk flags picks
tiny / normal / high_risk. The tier maps to a ceremony — a set of extra demands
(plan, security scan, non-author review) the cook/review skills enforce.

Reuse, not re-derive: the dependency-manifest flag routes through
change_class_derivation._is_manifest so manifest detection stays consistent with
the test-policy change-class layer (no parallel grep).

Boundary (v1): this is a SKILL-ENFORCED advisory. derive_risk produces a
derivation; the cook/code-review skills read it and run the ceremony. It does
NOT patch stage-policy `requires:` — a high_risk change can still reach a stage
gate without a security-scan artifact (the same accepted AI-applied gap as the
review-rules layer). `enabled: false` collapses everything to tiny.

Config: harness/data/risk-rubric.yaml (env HARNESS_RISK_RUBRIC).
"""

import os
import sys
from collections import namedtuple
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import change_class_derivation as ccd
from scope_match import scope_matches as _canonical_scope_matches

_RUBRIC_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "risk-rubric.yaml"

Risk = namedtuple("Risk", ["tier", "gates_hit", "flags", "ceremony"])

_EMPTY_CEREMONY = {
    "require_plan": False,
    "require_security_scan": False,
    "require_non_author_review": False,
}


class RiskRubricError(Exception):
    """Raised when the risk-rubric config is unreadable/malformed."""


def _rubric_path():
    raw = os.environ.get("HARNESS_RISK_RUBRIC")
    return Path(raw) if raw else _RUBRIC_DEFAULT


def load_policy(path=None) -> dict:
    """Load the risk-rubric config. A missing file is an error (a risk gate with
    no config must not silently default-to-pass — but `enabled: false` inside it
    is the sanctioned off-switch)."""
    p = Path(path) if path is not None else _rubric_path()
    try:
        import yaml_io
        data = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError as e:
        raise RiskRubricError("risk-rubric config not found at %s" % p) from e
    except (OSError, ValueError) as e:
        raise RiskRubricError("risk-rubric config at %s is unreadable: %s" % (p, e)) from e
    if not isinstance(data, dict):
        raise RiskRubricError("risk-rubric config at %s is not a mapping" % p)
    return data


def _require_globs(globs, label: str) -> None:
    """Fail loud if `globs` is not a list of non-empty strings. A bare string
    would be iterated char-by-char by _any_match (silent fail-open); a non-string
    element would raise an uncaught TypeError deeper in _glob_to_re."""
    if not isinstance(globs, (list, tuple)):
        raise RiskRubricError(
            "%s globs must be a list of glob strings, got %s"
            % (label, type(globs).__name__))
    for g in globs:
        if not isinstance(g, str) or not g:
            raise RiskRubricError(
                "%s has a non-string/empty glob entry: %r" % (label, g))


def _any_match(globs, changed_files) -> bool:
    # Case-insensitive on purpose: risk-gate filenames are conventionally
    # capitalized in several stacks (AuthService.java, AuthGuard.tsx) — a
    # case-sensitive match would miss them and silently under-rate the risk.
    return _canonical_scope_matches(globs, changed_files, case_insensitive=True)


def derive_risk(root, changed_files, *, policy=None) -> Risk:
    """Derive the risk tier + ceremony for a set of changed files."""
    pol = policy if policy is not None else load_policy()
    changed_files = list(changed_files or [])

    if not pol.get("enabled", True):
        return Risk("tiny", [], [], dict(_EMPTY_CEREMONY))

    gates_hit = []
    for name, spec in (pol.get("hard_gates") or {}).items():
        globs = spec.get("globs") if isinstance(spec, dict) else spec
        # A bare string here would be iterated char-by-char by _any_match and
        # silently fail OPEN (a hard gate downgraded to tiny) — fail loud instead.
        _require_globs(globs, "hard_gate %r" % name)
        if _any_match(globs, changed_files):
            gates_hit.append(name)

    flags = []
    # Dependency-manifest flag: REUSE change_class_derivation's manifest test so
    # this stays consistent with the test-policy change-class signals.
    if any(ccd._is_manifest(f) for f in changed_files):
        flags.append("dependency_manifest")
    for fl in (pol.get("flags") or []):
        if not isinstance(fl, dict):
            raise RiskRubricError(
                "flags entry must be a mapping with 'name'+'globs', got %s"
                % type(fl).__name__)
        nm = fl.get("name")
        if not nm or nm == "dependency_manifest":  # manifest handled via ccd above
            continue
        globs = fl.get("globs")
        _require_globs(globs, "flag %r" % nm)
        if _any_match(globs, changed_files):
            flags.append(nm)

    gates_hit = sorted(set(gates_hit))
    flags = sorted(set(flags))

    th = pol.get("thresholds") or {}
    tiny_max = th.get("tiny_max", 1)
    normal_max = th.get("normal_max", 3)
    if gates_hit:
        tier = "high_risk"
    elif len(flags) <= tiny_max:
        tier = "tiny"
    elif len(flags) <= normal_max:
        tier = "normal"
    else:
        tier = "high_risk"

    ceremony = (pol.get("ceremony") or {}).get(tier) or _EMPTY_CEREMONY
    return Risk(tier, gates_hit, flags, dict(ceremony))


def main() -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description="Derive a risk tier from changed files.")
    ap.add_argument("--root", default=".")
    ap.add_argument("files", nargs="*")
    args = ap.parse_args()
    try:
        r = derive_risk(args.root, args.files)
    except RiskRubricError as e:
        print("risk-rubric error: %s" % e, file=sys.stderr)
        return 2
    print(json.dumps(r._asdict(), indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
