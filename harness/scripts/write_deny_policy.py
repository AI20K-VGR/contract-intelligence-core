#!/usr/bin/env python3
"""write_deny_policy.py — deny-list policy SSOT (floor constants + soft loader).

The write-RBAC floor is a deny-list in two tiers. The HARD floor is a code
constant — author-maintained, never user-editable, because a user-editable
carve-out is a floor that widens itself:

  CORE_IMMUNE      absolute; no carve-out ever reopens it. Reuses
                   write_guard.GUARD_LIST (imported, NOT copied, so the two can
                   never drift) plus .git, a narrow secrets set, and the cage
                   self-disarm surface (.claude/settings*.json + the hooks slot).
  HARD_BINARY_DENY the installed harness binary (harness/**), carve-out only for
                   harness/tests/**. harness/state/** is deliberately NOT carved:
                   it is the audit store, and a shell/tool write there would let
                   an actor rewrite its own keyless chain_hash trail.

The SOFT tier is human-edited YAML, default EMPTY (= allow everything) — the
detective lane end users touch. Absent/empty config is inert, never a brick, the
opposite of the permission table whose absence fails closed.
"""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Tuple

_HOOKS_DIR = Path(__file__).resolve().parent.parent / "hooks"
if str(_HOOKS_DIR) not in sys.path:
    sys.path.append(str(_HOOKS_DIR))
import write_guard  # noqa: E402 — reuse GUARD_LIST (one guarded set, N observers)


def _yaml_load(text):
    """The one shared YAML read (yaml_io.py, ruamel.yaml, C-accelerated) — see
    that module's docstring for why ruamel replaced PyYAML and hook_runtime.py
    for the parse-cost measurements.

    This module sits on a per-EVENT path, so its parse cost is paid per tool
    call / prompt, not once per CLI run. `import yaml_io` stays lazy and is a
    same-directory sibling import (harness/scripts/), so this file stays
    runnable as a standalone CLI without the hooks dir on sys.path.
    """
    import yaml_io
    return yaml_io.yaml_load(text)

# Narrow secrets set: literal names + suffix globs that only match real dotenvs,
# never a template. Blanket `.env.*` would over-block `.env.example`/`.env.sample`.
_SECRETS: Tuple[str, ...] = (".env", ".env.local", ".env.prod", ".env.*.local")

# learn: the cage self-disarm surface — .claude/settings*.json is the guard
# on/off switch (write_guard.py header), and the installed hooks slot holds the
# hook registration; a default-allow floor must re-close what the old whitelist
# blocked via default_deny. The hooks-slot glob is assembled from parts so this
# source never carries the ".claude/" + "hooks/" contiguous literal the CI
# self-rule bans in harness/** (HC-1).
_CLAUDE = ".claude/"
_CAGE_DISARM: Tuple[str, ...] = (
    _CLAUDE + "settings.json",
    _CLAUDE + "settings.local.json",
    _CLAUDE + "hooks/**",
)

CORE_IMMUNE: Tuple[str, ...] = (
    # Both git entries are load-bearing; do not collapse them.
    #
    # `**/.git/**` — a git INTERNAL file at ANY depth. Depth matters because a glob
    # containing `/` is root-anchored in this matcher (one without a slash matches
    # any basename), so the earlier `.git/**` left `plans/x/.git/config` writeable —
    # and that is a full remote-code hole: set `core.hooksPath` there and the next
    # git command in that tree runs an arbitrary script. Nested `.git` directories
    # are ordinary (submodules, worktrees, vendored repos), so it is reachable.
    # Cost measured over 16,763 tracked+untracked files here: ZERO newly-denied
    # paths, and `.gitignore`/`.gitkeep` are untouched because the glob keys on the
    # `.git/` DIRECTORY.
    #
    # `.git` (bare) — a worktree's `.git` POINTER FILE, which `**/.git/**` misses
    # because it is a file, not a directory. Being slash-free, it is already
    # depth-agnostic.
    tuple(write_guard.GUARD_LIST) + ("**/.git/**", ".git") + _SECRETS + _CAGE_DISARM
)

# Author-maintained binary-deny (NOT config-driven — a user carve-out here would
# reopen the shipped binary to overwrite).
HARD_BINARY_DENY: Tuple[str, ...] = ("harness/**",)
HARD_BINARY_CARVE: Tuple[str, ...] = ("harness/tests/**",)

# Tier vocabulary (one set, imported by the matcher + observers — no drift).
TIER_CORE = "core_immune"
TIER_HARD_BINARY = "hard_binary"
TIER_SOFT = "soft"
TIER_ALLOW = "allow"

# Audit event names (the guards emit these — one vocab, not scattered strings).
EVENT_HARD_BLOCK = "deny_hard_block"
EVENT_SOFT_HIT = "deny_soft_hit"
EVENT_WIDEN = "widen_request"


# Soft-rule polarity. The soft tier is ONE ordered last-match-wins list (not two
# arrays): two independent arrays lose the cross-order that decides whether a
# broad allow or a more-specific deny wins for a path both would match.
POLARITY_DENY = "deny"
POLARITY_ALLOW = "allow"
_POLARITIES = (POLARITY_DENY, POLARITY_ALLOW)


class DenyPolicyError(ValueError):
    """A present-but-malformed soft rule list — fail-closed at the loader."""


@dataclass(frozen=True)
class Policy:
    """Immutable assembled policy the matcher consumes. Floor consts + soft rules."""
    core_immune: Tuple[str, ...]
    hard_binary_deny: Tuple[str, ...]
    hard_binary_carve: Tuple[str, ...]
    soft_rules: Tuple[Tuple[str, str], ...]  # ordered ((polarity, glob), ...)


def _parse_rule(item, idx: int) -> Tuple[str, str]:
    if not isinstance(item, dict) or len(item) != 1:
        raise DenyPolicyError(
            "write-deny-policy soft_rules[%d] must be a single {deny|allow: glob}" % idx)
    (polarity, glob), = item.items()
    if polarity not in _POLARITIES or not isinstance(glob, str) or not glob:
        raise DenyPolicyError(
            "write-deny-policy soft_rules[%d] must key on 'deny' or 'allow' with a "
            "non-empty glob string" % idx)
    return (polarity, glob)


def load_soft_rules(path) -> List[Tuple[str, str]]:
    """Parse the SOFT deny-list YAML -> ordered [(polarity, glob), ...].

    Absent/empty -> [] (inert: the soft tier allows everything by default).
    Present-but-malformed -> DenyPolicyError (fail-closed) — a broken detective
    config surfaces loudly, it never silently disables the tier.
    """
    p = Path(path)
    if not p.is_file():
        return []
    try:
        raw = _yaml_load(p.read_text(encoding="utf-8"))
    except Exception as e:  # noqa: BLE001
        raise DenyPolicyError("write-deny-policy is not valid YAML: %s" % e)
    if raw is None:
        return []
    if not isinstance(raw, dict):
        raise DenyPolicyError("write-deny-policy must be a mapping")
    rules = raw.get("soft_rules")
    if rules is None:
        return []
    if not isinstance(rules, list):
        raise DenyPolicyError("write-deny-policy 'soft_rules' must be a list")
    return [_parse_rule(item, i) for i, item in enumerate(rules)]


def assemble_policy(soft_rules) -> Policy:
    """Combine the code floor constants with parsed soft rules into one immutable
    Policy. PURE — no IO (the loader owns the file read)."""
    return Policy(
        core_immune=CORE_IMMUNE,
        hard_binary_deny=HARD_BINARY_DENY,
        hard_binary_carve=HARD_BINARY_CARVE,
        soft_rules=tuple((pol, glob) for pol, glob in (soft_rules or ())),
    )
