#!/usr/bin/env python3
"""test_policy.py — two-tier Definition-of-Done policy loader/merger.

Tier-1 (`harness/data/test-policy.yaml`, env override HARNESS_TEST_POLICY) is
the shipped default — the SPINE: a missing/malformed tier-1 raises (a gate with
no policy must never default-to-pass). Tier-2 (`<repo-root>/test-policy.yaml`,
which lives OUTSIDE harness/** by construction) is the repo override.

Merge contract (KISS — union + strictness-aware override, no deep inheritance):
  - a change-class present ONLY in tier-2 is ADDED (union).
  - for a class in BOTH, tier-2 wins WHEN it STRENGTHENS or matches the gate
    (raising enforcement, adding required types) — applied directly.
  - WEAKENING the gate (enforcement hard→soft, dropping a tier-1 required type,
    lowering a numeric coverage line) is refused unless the tier-2 class carries
    `grace: { reason: <non-empty> }`. An honored grace is applied AND emits a
    `policy_grace` audit trace — the backdoor is git-visible, never silent.
  - a MAJOR schema_version mismatch between the tiers raises (fail-loud, mirrors
    artifact_check.load_policy).
  - tier-2 absent → a clean copy of tier-1, no raise.

Posture: this is a DECLARATIVE policy reader, not an authenticator. It says what
the gate must demand; WHO ran the tests is attribution elsewhere.
"""

import copy
import os
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

_POLICY_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "test-policy.yaml"

# enforcement strictness rank — higher blocks harder. An unset enforcement
# defaults to `hard` (hard-default posture), so a weakening check treats a
# missing key as the strictest baseline.
_ENFORCE_RANK = {"hard": 2, "soft": 1, "advisory": 0, "off": 0}
_DEFAULT_ENFORCEMENT = "hard"


class TestPolicyError(Exception):
    """Raised when a test-policy file is malformed, the tiers disagree on the
    schema major, or a tier-2 override weakens the gate without a graced reason.
    The message names the file/class and the fix so it is a config edit, not a
    debug session."""


def _tier1_path(tier1_path=None) -> Path:
    if tier1_path is not None:
        return Path(tier1_path)
    raw = os.environ.get("HARNESS_TEST_POLICY")
    return Path(raw) if raw else _POLICY_DEFAULT


def _load_yaml(path: Path):
    import yaml_io  # lazy: keep importable without PyYAML until actually used
    return yaml_io.safe_load(path.read_text(encoding="utf-8"))


def _major(schema_version) -> str:
    return str(schema_version or "1.0").split(".")[0]


def _enforcement(cls_spec: dict) -> str:
    return str((cls_spec or {}).get("enforcement", _DEFAULT_ENFORCEMENT))


def _weakens(base: dict, override: dict) -> bool:
    """True when applying `override` onto tier-1 `base` for one change-class
    LOWERS the gate: enforcement downgrade, a dropped required type, or a
    lowered numeric coverage line. Only keys the override actually SETS are
    compared (an unspecified key is not a weakening)."""
    if "enforcement" in override:
        if _ENFORCE_RANK.get(_enforcement(override), 2) < _ENFORCE_RANK.get(_enforcement(base), 2):
            return True
    if "required" in override:
        base_req = set(base.get("required") or [])
        ov_req = set(override.get("required") or [])
        if not base_req.issubset(ov_req):  # a tier-1 required type was dropped
            return True
    base_line = (base.get("coverage") or {}).get("line")
    ov_cov = override.get("coverage") or {}
    if "line" in ov_cov and isinstance(base_line, (int, float)) \
            and isinstance(ov_cov.get("line"), (int, float)):
        if ov_cov["line"] < base_line:
            return True
    return False


def _merge_class(base: dict, override: dict) -> dict:
    """tier-2 keys overlay tier-1 for one change-class. `grace` (if present) is
    kept on the merged class so the gate + the expiry layer can read it."""
    merged = copy.deepcopy(base)
    for k, v in override.items():
        merged[k] = copy.deepcopy(v)
    return merged


def _emit_grace_trace(cls: str, reason: str) -> None:
    try:
        hooks = str(Path(__file__).resolve().parent.parent / "hooks")
        if hooks not in sys.path:
            sys.path.append(hooks)
        import trace_log
        trace_log.append_event("test_policy", "policy_grace",
                               target=cls, note=reason)
    except Exception:  # noqa: BLE001 — tracing never breaks policy loading
        pass


def _merge(tier1: dict, tier2: dict, *, trace: bool) -> dict:
    if _major(tier1.get("schema_version")) != _major(tier2.get("schema_version")):
        raise TestPolicyError(
            "test-policy schema_version major mismatch: tier-1 is %r but tier-2 "
            "is %r — bump both tiers together or pin the override to the tier-1 "
            "major" % (tier1.get("schema_version"), tier2.get("schema_version")))

    merged = copy.deepcopy(tier1)
    # preset + test_types: tier-2 wins / unions per key (additive, no weakening risk).
    if "preset" in tier2:
        merged["preset"] = tier2["preset"]
    merged.setdefault("test_types", {})
    for tt, spec in (tier2.get("test_types") or {}).items():
        merged["test_types"][tt] = copy.deepcopy(spec)
    # components: tier-2 entries appended (longest-match resolution at read time).
    if tier2.get("components"):
        merged.setdefault("components", [])
        merged["components"] = merged["components"] + copy.deepcopy(tier2["components"])

    merged.setdefault("change_classes", {})
    for cls, override in (tier2.get("change_classes") or {}).items():
        if not isinstance(override, dict):
            raise TestPolicyError(
                "tier-2 change_classes.%s must be a mapping (got %s)"
                % (cls, type(override).__name__))
        base = merged["change_classes"].get(cls)
        if base is None:  # union: a brand-new class is added wholesale
            merged["change_classes"][cls] = copy.deepcopy(override)
            continue
        weakening = _weakens(base, override)
        if weakening:
            grace = override.get("grace")
            reason = (grace or {}).get("reason") if isinstance(grace, dict) else None
            if not (isinstance(reason, str) and reason.strip()):
                raise TestPolicyError(
                    "tier-2 override for change-class %r WEAKENS the gate "
                    "(lower enforcement / fewer required types / lower coverage) "
                    "but carries no `grace: { reason: ... }` — strengthening "
                    "overrides apply directly; a weakening one needs a graced, "
                    "git-visible reason" % cls)
            # A grace has TEETH: it must carry an `expires` (ISO date). Past it
            # the gate stops honoring the grace and re-arms the FULL hard gate
            # — so a graced class records what to RESTORE on expiry.
            expires = (grace or {}).get("expires")
            if not (isinstance(expires, str) and expires.strip()):
                raise TestPolicyError(
                    "tier-2 grace for change-class %r is missing `expires` "
                    "(an ISO date). A grace with no expiry is a permanent "
                    "backdoor; past `expires` the gate re-blocks hard" % cls)
            if trace:
                _emit_grace_trace(cls, reason)
        merged_cls = _merge_class(base, override)
        if weakening and isinstance(merged_cls.get("grace"), dict):
            # stash the pre-grace (tier-1) spec so an expired grace restores the
            # full hard gate, not just a flag.
            merged_cls["grace"]["restores"] = {
                "required": list(base.get("required") or []),
                "enforcement": base.get("enforcement", _DEFAULT_ENFORCEMENT),
                "coverage": copy.deepcopy(base.get("coverage")),
            }
        merged["change_classes"][cls] = merged_cls
    return merged


def _assert_class_shapes(policy: dict) -> None:
    """Fail LOUD at load on the change-class config typos that would otherwise
    reach the gate as an opaque TypeError/AttributeError (a config typo must
    never silently disable or crash the gate):
      - `grace.expires` MUST be a quoted ISO date STRING. PyYAML parses an
        unquoted `expires: 2026-12-31` into a `datetime.date`, which the gate
        compares against a string `now` and crashes.
      - `coverage`, when present, MUST be a mapping (e.g. `{line: 80}`). A scalar
        `coverage: 80` crashes `(spec.get("coverage") or {}).get("line")`."""
    for cls, spec in (policy.get("change_classes") or {}).items():
        if not isinstance(spec, dict):
            continue
        if "coverage" in spec and not isinstance(spec.get("coverage"), dict):
            raise TestPolicyError(
                "change-class %r coverage is %r, not a mapping — write it as "
                "`coverage: { line: <pct> }` in test-policy.yaml (a scalar would "
                "crash the gate)" % (cls, spec.get("coverage")))
        grace = spec.get("grace")
        if not isinstance(grace, dict) or "expires" not in grace:
            continue
        exp = grace.get("expires")
        if not (isinstance(exp, str) and exp.strip()):
            raise TestPolicyError(
                "change-class %r grace.expires is %r, not a quoted ISO date "
                "string — quote it as `expires: \"YYYY-MM-DD\"` in "
                "test-policy.yaml (an unquoted date parses as a date object and "
                "would crash the gate)" % (cls, exp))
        import datetime
        try:
            datetime.date.fromisoformat(exp.strip()[:10])
        except ValueError:
            raise TestPolicyError(
                "change-class %r grace.expires %r is not an ISO date "
                "(YYYY-MM-DD) — the gate compares it lexically, so a non-ISO "
                "string silently mis-judges the grace; fix it in test-policy.yaml"
                % (cls, exp))


def load_test_policy(root=None, *, tier1_path=None, tier2_path=None, trace=True) -> dict:
    """Return the merged two-tier policy dict.

    tier-1 resolves from `tier1_path` > HARNESS_TEST_POLICY > shipped default; a
    missing/malformed tier-1 raises TestPolicyError. tier-2 resolves from
    `tier2_path` > `<root>/test-policy.yaml` if it exists; absent tier-2 → a
    clean tier-1 copy. `root` defaults to harness_paths.root()."""
    t1p = _tier1_path(tier1_path)
    try:
        raw1 = _load_yaml(t1p)
    except FileNotFoundError:
        raise TestPolicyError(
            "tier-1 test policy missing at %s — restore it (the shipped default "
            "is harness/data/test-policy.yaml). A gate with no policy must not "
            "default-to-pass" % t1p)
    except Exception as e:  # noqa: BLE001 — malformed YAML is a loud config error
        raise TestPolicyError("tier-1 test policy %s is malformed: %s" % (t1p, e))
    if not isinstance(raw1, dict) or not raw1.get("change_classes"):
        raise TestPolicyError(
            "tier-1 test policy %s is malformed — expected a mapping with a "
            "`change_classes:` block" % t1p)
    _assert_class_shapes(raw1)

    if tier2_path is None:
        if root is None:
            import harness_paths
            root = harness_paths.root()
        cand = Path(root) / "test-policy.yaml"
        tier2_path = cand if cand.is_file() else None

    if tier2_path is None:
        return copy.deepcopy(raw1)

    try:
        raw2 = _load_yaml(Path(tier2_path))
    except Exception as e:  # noqa: BLE001 — a present-but-broken override is loud
        raise TestPolicyError(
            "tier-2 test policy %s is malformed: %s" % (tier2_path, e))
    if raw2 is None:
        return copy.deepcopy(raw1)
    if not isinstance(raw2, dict):
        raise TestPolicyError(
            "tier-2 test policy %s must be a YAML mapping" % tier2_path)
    _assert_class_shapes(raw2)  # validate override shapes BEFORE _merge reads them
    merged = _merge(raw1, raw2, trace=trace)
    _assert_class_shapes(merged)  # tier-2 may union a new class with a bad grace
    return merged


def resolve_for_class(policy: dict, change_class: str) -> dict:
    """The resolved DoD spec for one change-class: {required, coverage,
    enforcement, grace?}. An unknown class returns an empty-required, hard spec
    (nothing demanded but the posture stays hard so a typo never silently opens
    the gate). enforcement defaults to hard when unset."""
    spec = dict((policy.get("change_classes") or {}).get(change_class) or {})
    spec.setdefault("required", [])
    spec.setdefault("enforcement", _DEFAULT_ENFORCEMENT)
    return spec
