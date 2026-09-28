#!/usr/bin/env python3
"""review_recall.py — the deterministic half of hs:code-review recall-mode.

Recall-mode scales Stage-2 finding production by an effort level
(low|medium|high|xhigh|max). This module owns only the reproducible decisions; the
LLM judgment (fan-out, adversarial verify, sweep) layers on top in
references/recall-mode.md.

Four pure-ish resolvers:

1. `resolve_effort(flag, env, config)` — deterministic effort resolution, mirroring
   cook_parallel_plan.is_parallel_enabled: explicit arg > HARNESS_REVIEW_EFFORT env >
   code-review.yaml config > default `low`. An unknown value falls back to `low`
   (never crash, never silently escalate).
2. `breadth_for(level, config)` — the effort→breadth lookup (lenses/verify/sweep/
   fan_out). Numbers live in code-review.yaml, not here.
3. `resolve_diff_source(target, root)` — the git diff-range fallback chain
   (@{u}...HEAD → <main>...HEAD → HEAD~1) plus a working-tree-dirty flag. Pure git.
4. `assess_scope(changed_files, root)` — file count + risk_rubric signals → a
   deterministic {scope, signals, suggested_effort}. The skill layers LLM judgment on
   top, but this suggestion is reproducible.

The recall engine never touches the gate: verdict-truth-table + dismissals lookup +
review-decision.json are unchanged. This module has no gate authority.

Config: harness/data/code-review.yaml (env HARNESS_REVIEW_EFFORT for the level only).
"""

import os
import subprocess
import sys
from pathlib import Path

sys.path.append(os.path.dirname(os.path.abspath(__file__)))

ENV_VAR = "HARNESS_REVIEW_EFFORT"
LEVELS = ("low", "medium", "high", "xhigh", "max")
DEFAULT_LEVEL = "low"

_CONFIG_DEFAULT = Path(__file__).resolve().parent.parent / "data" / "code-review.yaml"

# Gate-signal flags that justify a high-effort suggestion regardless of file count.
_HIGH_SIGNALS = ("auth", "migration", "secret", "api_contract")


def load_config(path=None) -> dict:
    """Load code-review.yaml. Best-effort: a missing/unreadable config falls back to
    the built-in defaults so recall never hard-fails the review (it is not a gate)."""
    p = Path(path) if path is not None else _CONFIG_DEFAULT
    try:
        import yaml_io
        data = yaml_io.safe_load(p.read_text(encoding="utf-8")) or {}
    except Exception:
        # Advisory loader, not a gate: a missing file, an unreadable one, OR a
        # malformed YAML (yaml_io.YAMLError is NOT a ValueError) must all fall back to
        # the built-in defaults so recall never hard-fails the review.
        data = {}
    if not isinstance(data, dict):
        data = {}
    # setdefault alone only covers a MISSING key — a PRESENT key of the wrong
    # type (e.g. `levels: [low, high]`, a list) survives it and later crashes
    # breadth_for's dict-only access. The docstring promises recall never
    # hard-fails on a config typo; fold a wrong-typed value back to the
    # built-in default the same way an absent one already degrades.
    if not isinstance(data.get("default"), str):
        data["default"] = DEFAULT_LEVEL
    if not isinstance(data.get("levels"), dict):
        data["levels"] = dict(_BUILTIN_LEVELS)
    return data


# Built-in fallback mirrors code-review.yaml — the config is the source of truth, this
# only keeps the resolver working if the file is missing.
_BUILTIN_LEVELS = {
    "low":    {"fan_out": False, "lenses": 1, "verify": "self",                    "sweep": False},
    "medium": {"fan_out": True,  "lenses": 3, "verify": "consolidate",             "sweep": False},
    "high":   {"fan_out": True,  "lenses": 5, "verify": "consolidate_verify",      "sweep": True},
    "xhigh":  {"fan_out": True,  "lenses": 6, "verify": "independent",             "sweep": True},
    "max":    {"fan_out": True,  "lenses": 8, "verify": "independent_per_finding", "sweep": True},
}


def _norm_level(value):
    """A valid level string (lowercased) or None."""
    if value is None:
        return None
    v = str(value).strip().lower()
    return v if v in LEVELS else None


def resolve_effort(flag=None, env=None, config=None) -> str:
    """Resolve the effort level. flag/env/config are each a level string or None.
    Precedence flag > env > config > default low; an unknown value at any layer is
    ignored (falls through), and an all-unknown stack lands on `low`."""
    for candidate in (flag, env, config):
        lv = _norm_level(candidate)
        if lv is not None:
            return lv
    return DEFAULT_LEVEL


def breadth_for(level, config=None) -> dict:
    """The breadth knob for a level: {fan_out, lenses, verify, sweep}. Unknown level
    → low's breadth (matches resolve_effort's fallback). Recall is advisory, not a
    gate: a `config` whose `levels` is present but the wrong shape (a list instead
    of a mapping) fails OPEN to the built-in table instead of raising — the module
    docstring's "never hard-fails the review" promise, honored even when `config`
    is handed in directly rather than routed through load_config()."""
    cfg = config if config is not None else load_config()
    levels = cfg.get("levels") or _BUILTIN_LEVELS
    if not isinstance(levels, dict):
        levels = _BUILTIN_LEVELS
    lv = _norm_level(level) or DEFAULT_LEVEL
    breadth = levels.get(lv) or _BUILTIN_LEVELS[lv]
    # Defensive copy + fill any missing key from the built-in so callers see all four.
    out = dict(_BUILTIN_LEVELS[lv])
    out.update({k: breadth[k] for k in breadth if k in out})
    return out


# --- multi-round profiles -----------------------------------------------------
# A review-policy profile (resolved by review_policy_config.resolve_profile) names
# an effort level, a round count, and the four tactical axes. These helpers are the
# deterministic glue between a profile and a recall run — pure given their inputs;
# the LLM judgment (how the axes shape each round) lives in references/multi-round.md.

_AXES = ("compounding", "per_aspect", "blind_main_sub", "refute")
_CAP_DEFAULTS = {"max_rounds": 5, "max_lenses_per_round": 8}


def resolve_profile_breadth(profile, config=None) -> dict:
    """Map a review-policy profile onto a recall breadth: the effort→breadth knob
    (fan_out/lenses/verify/sweep from code-review.yaml) plus the profile's round
    count, the four axes, aspects rotation, and scope. rounds<1 floors to 1."""
    profile = profile or {}
    out = breadth_for(profile.get("effort", DEFAULT_LEVEL), config)
    rounds = profile.get("rounds", 1)
    try:
        rounds = int(rounds)
    except (TypeError, ValueError):
        rounds = 1
    out["rounds"] = rounds if rounds >= 1 else 1
    for axis in _AXES:
        out[axis] = bool(profile.get(axis, False))
    out["aspects"] = list(profile.get("aspects", []))
    out["scope"] = profile.get("scope", "diff")
    return out


def round_budget(rounds, lenses, caps=None) -> dict:
    """Clamp rounds x lenses to the policy caps. Returns {rounds, lenses, capped},
    capped True iff either value was reduced. Missing caps → built-in ceiling."""
    caps = caps or _CAP_DEFAULTS
    max_rounds = int(caps.get("max_rounds", _CAP_DEFAULTS["max_rounds"]))
    max_lenses = int(caps.get("max_lenses_per_round", _CAP_DEFAULTS["max_lenses_per_round"]))
    r_in, l_in = int(rounds), int(lenses)
    r_out, l_out = min(r_in, max_rounds), min(l_in, max_lenses)
    return {"rounds": r_out, "lenses": l_out,
            "capped": (r_out != r_in or l_out != l_in)}


def blind_payload(scope, artifact_path) -> dict:
    """The sub-agent payload for blind_main_sub: scope + artifact path ONLY, never
    the main's findings (mirrors independent-revalidator's sealed-room input). The
    absence of a findings key is the blind guarantee."""
    return {"scope": scope, "artifact_path": artifact_path}


def _git(root, *args):
    return subprocess.run(["git", "-C", str(root), *args],
                          capture_output=True, text=True)


def _has_upstream(root) -> bool:
    return _git(root, "rev-parse", "--abbrev-ref",
                "--symbolic-full-name", "@{u}").returncode == 0


def _main_branch(root):
    """The repo's integration branch by convention: origin/HEAD target, then a local
    main/master. None when the repo has no such branch (brand-new feature branch)."""
    head = _git(root, "symbolic-ref", "-q", "refs/remotes/origin/HEAD")
    if head.returncode == 0:
        name = head.stdout.strip().rsplit("/", 1)[-1]
        if name:
            return name
    for b in ("main", "master"):
        if _git(root, "rev-parse", "--verify", "-q", b).returncode == 0:
            return b
    return None


def _is_dirty(root) -> bool:
    r = _git(root, "status", "--porcelain")
    return bool(r.stdout.strip())


def _rev_exists(root, rev) -> bool:
    """True if `rev` resolves to a commit in this repo (a branch, tag, or sha)."""
    return _git(root, "rev-parse", "--verify", "-q",
                "%s^{commit}" % rev).returncode == 0


def resolve_diff_source(target=None, root=".") -> dict:
    """Resolve the diff range deterministically. Returns
    {"range": <git range>, "include_worktree": bool}.

    When `target` names an explicit revision (branch/tag/sha), the range is
    `<target>...HEAD`. The non-revision modes (--pending / codebase / recent / a PR
    ref) do not resolve here and fall through to the chain: an upstream @{u}...HEAD,
    else <main>...HEAD, else HEAD~1. A dirty working tree sets include_worktree so the
    skill also reviews unstaged work."""
    include_worktree = _is_dirty(root)
    if target and _rev_exists(root, str(target)):
        rng = "%s...HEAD" % target
    elif _has_upstream(root):
        rng = "@{u}...HEAD"
    else:
        main = _main_branch(root)
        rng = "%s...HEAD" % main if main else "HEAD~1"
    return {"range": rng, "include_worktree": include_worktree}


def assess_scope(changed_files, root=".", config=None) -> dict:
    """Deterministic scope read: file count + risk_rubric signals → a suggested
    effort. Returns {"scope", "signals", "suggested_effort"}. Pure given the inputs
    + the risk-rubric config (same inputs → same suggestion)."""
    cfg = config if config is not None else load_config()
    files = list(changed_files or [])
    sc = cfg.get("scope") or {}
    small_max = sc.get("small_max", 2)
    moderate_max = sc.get("moderate_max", 9)

    n = len(files)
    if n <= small_max:
        scope = "small"
    elif n <= moderate_max:
        scope = "moderate"
    else:
        scope = "large"

    signals = _risk_signals(files, root)
    high_signal = any(s in _HIGH_SIGNALS for s in signals)

    if high_signal or scope == "large":
        suggested = "high"
    elif scope == "moderate" or signals:
        suggested = "medium"
    else:
        suggested = "low"

    return {"scope": scope, "signals": signals, "suggested_effort": suggested}


def _risk_signals(files, root):
    """Risk-gate + flag names for the changed files, via risk_rubric (reuse, not
    re-derive). risk_rubric being absent (ImportError) yields no signals — it is an
    optional reuse. A PRESENT-but-broken rubric raises RiskRubricError and is allowed
    to propagate: a misconfigured risk gate must be loud, not silently downgrade the
    suggested effort to low on exactly the auth/migration diffs it exists to escalate
    ("không im lặng")."""
    try:
        import risk_rubric
    except ImportError:
        return []
    r = risk_rubric.derive_risk(root, files)
    return sorted(set(list(r.gates_hit) + list(r.flags)))


def main(argv=None) -> int:
    import argparse
    import json
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--effort", help="explicit effort level (overrides env/config)")
    ap.add_argument("--in-place", "--inline", action="store_true", dest="in_place",
                    help="allow the main agent to review inline (default: use subagents)")
    ap.add_argument("--root", default=".", help="repo root (default cwd)")
    ap.add_argument("--diff-source", action="store_true",
                    help="print the resolved diff range + worktree flag")
    ap.add_argument("--scope", nargs="*", metavar="FILE",
                    help="assess scope for the given changed files")
    args = ap.parse_args(argv)
    root = Path(args.root).resolve()

    cfg = load_config()
    level = resolve_effort(flag=args.effort, env=os.environ.get(ENV_VAR),
                           config=cfg.get("default"))
    out = {"effort": level, "breadth": breadth_for(level, cfg), "in_place": bool(args.in_place)}
    if args.diff_source:
        out["diff_source"] = resolve_diff_source(root=str(root))
    if args.scope is not None:
        out["scope_assessment"] = assess_scope(args.scope, root=str(root), config=cfg)
    print(json.dumps(out, indent=2, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
