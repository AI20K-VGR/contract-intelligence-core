#!/usr/bin/env python3
"""branch_policy.py — which branches are protected.

A protected branch is one a push must not reach without the merge-grade
artifacts (the transport twin of the `pr` stage). The patterns live in
protected-branches.yaml; fnmatch `*` spans `/`, so `release/*` owns the family.

Resolution mirrors the other config loaders: an explicit path wins, then the
HARNESS_PROTECTED_BRANCHES env override (tests + the rare per-repo redirect),
then the shipped default under harness/data/. A missing file protects nothing
(additive — never invent a gate from absence); a malformed file is a typed
BranchPolicyError so a broken policy is loud, not silently permissive.
"""
import fnmatch
import os
from pathlib import Path


class BranchPolicyError(Exception):
    """protected-branches.yaml is present but malformed."""


_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "protected-branches.yaml"


def _path(path=None) -> Path:
    if path is not None:
        return Path(path)
    env = os.environ.get("HARNESS_PROTECTED_BRANCHES")
    return Path(env) if env and env.strip() else _DEFAULT


def load_protected(path=None) -> list:
    """Return the list of protected-branch glob patterns. Missing file → []."""
    import yaml_io  # lazy: importable without PyYAML until actually used

    p = _path(path)
    try:
        raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return []
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise BranchPolicyError(
            "protected-branches policy %s is malformed — expected a YAML "
            "mapping with a `protected` list" % p)
    pats = raw.get("protected")
    if pats is None:
        return []
    if not isinstance(pats, list) or not all(
            isinstance(x, str) for x in pats):
        raise BranchPolicyError(
            "key `protected` in %s must be a list of branch glob strings" % p)
    return [x.strip() for x in pats if x.strip()]


def is_protected(branch, path=None) -> bool:
    """True when the short branch name matches any protected pattern. `branch`
    is a short name (`main`, `release/1.2`), not a `refs/heads/...` ref."""
    if not branch:
        return False
    return any(fnmatch.fnmatch(branch, pat) for pat in load_protected(path))
