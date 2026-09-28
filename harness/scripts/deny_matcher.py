#!/usr/bin/env python3
"""deny_matcher.py — the PURE deny-list matcher (one matcher, N observers).

evaluate(target, policy, protected_roots) classifies a write target into a tier,
in strict order so a carve-out can never reopen the floor:

  1. Containment (security boundary FIRST): resolve the target's realpath (symlinks
     followed, `..` collapsed) relative to a protected root. Outside every root ->
     TIER_UNRESOLVED (the caller decides: a real path outside the protected zones
     is safe to allow; a dynamic Bash token that cannot be pinned is the caller's
     fail-closed problem, not ours).
  2. core-immune short-circuit: a match returns TIER_CORE immediately, BEFORE any
     ordered soft match — no `allow` rule ever reaches the core set.
  3. hard-binary: harness/** minus the harness/tests/** carve. The carve is a code
     constant, decided on the RESOLVED realpath (step 1), so a symlink through the
     tests dir into hooks/ resolves to a core path and is caught by step 2, never
     laundered through the carve.
  4. soft: one ordered rule list, last-match-wins (.gitignore style). A trailing
     deny -> TIER_SOFT (detective, still allowed); a trailing allow / no match ->
     TIER_ALLOW.

PURE: no file/env reads — every input is a parameter (the caller resolves roots
and loads the policy). Symlink-safe via write_guard._rel_target (reused, not
re-rolled)."""
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Optional, Sequence

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))
_HOOKS = _HERE.parent / "hooks"
if str(_HOOKS) not in sys.path:
    sys.path.append(str(_HOOKS))

import path_glob  # noqa: E402 — single-glob any-match, shared semantics
import write_guard  # noqa: E402 — reuse _rel_target (resolve-then-relative_to)
from write_deny_policy import (  # noqa: E402 — one tier/polarity vocab
    POLARITY_DENY,
    TIER_ALLOW,
    TIER_CORE,
    TIER_HARD_BINARY,
    TIER_SOFT,
)

# Matcher-local outcome: the target does not resolve into any protected root.
# Distinct from TIER_ALLOW so a caller can tell "provably outside protected"
# (safe) from "matched nothing inside" (also allowed, but observed differently).
TIER_UNRESOLVED = "unresolved"

_HARD_TIERS = (TIER_CORE, TIER_HARD_BINARY)


@dataclass(frozen=True)
class DenyDecision:
    tier: str
    matched_rule: Optional[str] = None

    @property
    def is_hard(self) -> bool:
        """True for the preventive floor tiers the caller must block."""
        return self.tier in _HARD_TIERS


def _resolve_rels(target, protected_roots: Sequence):
    """EVERY root-relative POSIX path the target has, one per protected root that
    contains it (resolved, order preserved, de-duplicated). Empty when it lies
    outside every root.

    Deliberately every root, not the first: roots nest, and a nested pair yields
    two different relative paths for one file. The globs are root-anchored, so a
    rule with no outer prefix (`docs/decisions.yaml`) only ever matches the INNER
    reading, while `harness/**` only matches the OUTER one. Keeping one reading
    discards the other, and which one survives then depends on argument order —
    the caller silently decides policy by how it builds a list."""
    rels = []
    for root in protected_roots or ():
        try:
            rel = write_guard._rel_target(target, Path(root))
        except Exception:  # noqa: BLE001 — a bad root never breaks classification
            rel = None
        if rel is not None and rel not in rels:
            rels.append(rel)
    return rels


def _first_match(rel: str, globs) -> Optional[str]:
    for g in globs or ():
        if path_glob.match_path_glob(rel, [g]):
            return g
    return None


def _soft_eval(rel: str, soft_rules) -> DenyDecision:
    tier, matched = TIER_ALLOW, None
    for polarity, glob in soft_rules or ():
        if path_glob.match_path_glob(rel, [glob]):
            if polarity == POLARITY_DENY:
                tier, matched = TIER_SOFT, glob
            else:
                tier, matched = TIER_ALLOW, None
    return DenyDecision(tier, matched)


# Most restrictive first. `evaluate` keeps the strictest verdict across roots, so
# this order IS the policy: moving a tier up here makes it win more often.
_STRICTNESS = (TIER_CORE, TIER_HARD_BINARY, TIER_SOFT, TIER_ALLOW)


def _classify_one(rel: str, policy) -> DenyDecision:
    """Classify ONE root-relative reading of the target.

    The deny tiers match case-INSENSITIVELY; the carve-out does NOT. That
    asymmetry is the whole point and is not a leftover:

      * folding the deny side closes a case-variant spelling (`HARNESS/hooks/x.py`
        is the same file as `harness/hooks/x.py` on a case-insensitive volume, so
        an unfolded deny lets the spelling launder a write past the floor);
      * folding the carve side would let ANY case-variant of the carve directory
        reopen the entire binary tree — `harness/Tests/**` and `harness/TESTS/**`
        would go BLOCK -> allow, which is exactly the regression this asymmetry
        exists to prevent.

    Soft rules are left case-SENSITIVE on purpose: that list is user-authored and
    carries `allow` polarity too, so folding it could loosen rather than tighten.
    """
    folded = rel.lower()

    core = _first_match(folded, policy.core_immune)
    if core is not None:
        return DenyDecision(TIER_CORE, core)

    hard = _first_match(folded, policy.hard_binary_deny)
    # carve on the ORIGINAL spelling — see the asymmetry note above
    if hard is not None and not path_glob.match_path_glob(rel, list(policy.hard_binary_carve)):
        return DenyDecision(TIER_HARD_BINARY, hard)

    return _soft_eval(rel, policy.soft_rules)


def evaluate(target, policy, protected_roots: Sequence) -> DenyDecision:
    """Classify `target` against `policy`. See module docstring for the order.

    With several protected roots the STRICTEST verdict wins — not the verdict of
    the first root that happens to contain the target. Monotone by construction:
    an extra root can only add a way to match, never remove one, so widening the
    root list can never turn a block into an allow. `TestAddingARootNeverLoosens`
    pins that mechanically; do not 'simplify' this back to first-root-wins."""
    rels = _resolve_rels(target, protected_roots)
    if not rels:
        return DenyDecision(TIER_UNRESOLVED, None)

    best = None
    for rel in rels:
        decision = _classify_one(rel, policy)
        if best is None or _STRICTNESS.index(decision.tier) < _STRICTNESS.index(best.tier):
            best = decision
    return best
