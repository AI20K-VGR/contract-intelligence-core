#!/usr/bin/env python3
"""model_policy.py — reader + evaluator for model-policy.yaml (the model-bound posture).

Governs subagent-types that CANNOT be pinned via agent frontmatter (the built-in
Claude Code types: explore/plan/general-purpose/claude/…) AND documents the exact model of
the agents we ship. resolve(agent_type) returns the per-agent bound + mode (per-agent mode
read BEFORE the global mode so a per-agent override is genuinely wired, never an inert
advertised knob — red-team F3 + LESSONS a).

Bound kinds (at most one per agent; evaluate() applies them in this precedence):
  require_explicit: true   — must name a model explicitly OR record a reason; no bare inherit
  required_model: X        — exact: the effective tier must equal X
  max_model: X             — ceiling: the effective tier must be <= X
  min_model: X             — floor: the effective tier must be >= X
  self_pinned: true        — the agent's frontmatter sets its own model, so a bare inherit is
                             trusted (it runs the frontmatter model == required); only an
                             EXPLICIT spawn model is ever evaluated. Built-in types omit this.

Tier ladder: haiku < sonnet < opus < fable. Two ladders, not one, and the difference is
load-bearing: `fable` IS ranked when it is the model being EVALUATED (so a sonnet/opus
ceiling refuses it), and is NOT a valid DECLARED endpoint (`max_model: fable` /
`min_model: fable` stay inert, since a fable bound constrains nothing useful).

Tier classification maps THROUGH the environment (ANTHROPIC_DEFAULT_{HAIKU,SONNET,OPUS}_MODEL)
so a user's custom model mapping is honored — never a hardcoded family-substring that a
custom id would evade. When the env mapping collapses tiers (the same id for >1 tier) or an
id cannot be classified, tier comparison FAILS OPEN (passes) rather than false-blocking a
custom setup.

Fail-open by design: a missing or malformed config yields a PERMISSIVE posture
(mode='off', no bound) — a reader that raised, or defaulted to block on a broken file, would
brick every bounded spawn. The gate's own enforce decision fails closed (the guard); this
READER never does.

Not on write_guard's GUARD_LIST: a human/dev may lower `mode` by hand or via the
HARNESS_MODEL_POLICY whole-file override (restart-bound; HARNESS_* is scrubbed at push).

`agents:` is ALSO the effort SSOT: effort_for(agent_type) reads a per-agent `effort:` key
(haiku agents carry none — no effort dial) and effort_valid_for_model(effort, model) clamps
an effort value against a concrete model's capability (haiku → none; xhigh → not on the
older opus-4.6/sonnet-4.6 generation). Both are separate fail-open readers — resolve() and
evaluate() never look at `effort:` and stay untouched by it (author-time validation only;
no spawn-time enforcement here).
"""
import os
from pathlib import Path

_VALID_MODES = ("block", "advisory", "off")
_ENV_OVERRIDE = "HARNESS_MODEL_POLICY"
_REL = ("data", "model-policy.yaml")

# BOUND ladder — the ranks a DECLARED endpoint may take. `fable` is intentionally absent:
# `max_model: fable` / `min_model: fable` bound nothing useful, so they stay inert rather
# than let a config author believe otherwise.
_TIER_RANK = {"haiku": 1, "sonnet": 2, "opus": 3}

# EFFECTIVE ladder — the ranks the model BEING EVALUATED may take. fable sits above opus,
# so a sonnet/opus ceiling refuses it.
#
# These are two different questions and must stay two different tables. Collapsing them
# either way costs something real: drop fable from BOTH and it classifies as "unknown",
# which hits the custom-model fail-open and sails past every ceiling (measured: fable
# passed where opus was blocked, on 4 of 6 bounded agents); add fable to BOTH and a fable
# ceiling starts pretending to constrain a spawn. The fail-open itself is deliberate and
# stays — it exists so a user's CUSTOM model id is never false-blocked. fable simply is not
# a custom id: this harness names it, ships it, and pins an agent to it, so being treated as
# a stranger in its own house was the defect, not the fail-open.
_EFFECTIVE_RANK = dict(_TIER_RANK, fable=max(_TIER_RANK.values()) + 1)
# Logical tier -> the env var carrying the concrete model id the user mapped it to.
_TIER_ENV = {
    "haiku": "ANTHROPIC_DEFAULT_HAIKU_MODEL",
    "sonnet": "ANTHROPIC_DEFAULT_SONNET_MODEL",
    "opus": "ANTHROPIC_DEFAULT_OPUS_MODEL",
}
_AMBIGUOUS = "AMBIGUOUS"


def _config_path(env) -> Path:
    raw = env.get(_ENV_OVERRIDE)
    if raw:
        return Path(raw)
    # off __file__: harness/scripts/model_policy.py -> harness/data/model-policy.yaml
    return Path(__file__).resolve().parent.parent.joinpath(*_REL)


def _load_config(env) -> dict:
    """Parse model-policy.yaml. Missing/malformed/no-PyYAML => {} (caller goes permissive).
    Never raises — a broken config must not wedge a spawn."""
    try:
        p = _config_path(env)
        if p.is_file():
            import yaml_io
            raw = yaml_io.safe_load(p.read_text(encoding="utf-8"))
            if isinstance(raw, dict):
                return raw
    except Exception:  # noqa: BLE001 — malformed config degrades to permissive
        pass
    return {}


def _norm(agent_type) -> str:
    """De-namespace hs:explore -> explore and lowercase for a stable compare."""
    t = str(agent_type or "").strip().lower()
    return t.split(":", 1)[1] if ":" in t else t


def _valid_mode(v, default) -> str:
    # YAML 1.1 parses a bare `off` as the boolean False (and `on` as True); a user writing
    # `mode: off` means the string "off". Coerce that back before validating.
    if v is False:
        return "off"
    if isinstance(v, str):
        v = v.strip().lower()
    return v if v in _VALID_MODES else default


def _alias(v):
    """A logical model alias from config (haiku/sonnet/opus/fable) — lowercased str or None."""
    return str(v).strip().lower() if isinstance(v, str) and v.strip() else None


def resolve(agent_type, env=None) -> dict:
    """Return the bound + mode for an agent:
        {required_model, max_model, min_model, require_explicit, self_pinned, mode}

    Broken/missing config → permissive (off, no bound). A known agent's per-agent `mode`
    wins over the global `mode`; an unknown agent carries no bound so the gate has nothing to
    enforce."""
    env = os.environ if env is None else env
    empty = {
        "required_model": None, "max_model": None, "min_model": None,
        "require_explicit": False, "self_pinned": False, "mode": "off",
    }
    cfg = _load_config(env)
    if not cfg:
        return empty

    global_mode = _valid_mode(cfg.get("mode"), "block")
    agents = cfg.get("agents") if isinstance(cfg.get("agents"), dict) else {}
    entry = agents.get(_norm(agent_type))
    if not isinstance(entry, dict):
        return {**empty, "mode": global_mode}

    return {
        "required_model": _alias(entry.get("required_model")),
        "max_model": _alias(entry.get("max_model")),
        "min_model": _alias(entry.get("min_model")),
        "require_explicit": entry.get("require_explicit") is True,
        "self_pinned": entry.get("self_pinned") is True,
        "mode": _valid_mode(entry.get("mode"), global_mode),  # per-agent FIRST, fallback global
    }


def _norm_id(model) -> str:
    """Lowercase a concrete model id and drop a trailing `[..]` tag (e.g. the `[1m]`
    context-window marker) so a transcript id and an env id compare equal."""
    s = str(model or "").strip().lower()
    i = s.find("[")
    return s[:i].strip() if i != -1 else s


def classify_tier(model, env=None):
    """Classify a concrete model id into a logical tier.

    Returns 'haiku'|'sonnet'|'opus', or 'AMBIGUOUS' when the env mapping assigns the same id
    to more than one tier (a collapsed/custom mapping that cannot be ranked), or None when the
    id is empty or cannot be classified at all.

    Maps THROUGH ANTHROPIC_DEFAULT_*_MODEL first (honoring a custom mapping); only falls back
    to a canonical family-name substring when the env carries no matching id."""
    env = os.environ if env is None else env
    nid = _norm_id(model)
    if not nid:
        return None
    matched = [tier for tier, ev in _TIER_ENV.items() if _norm_id(env.get(ev)) == nid and _norm_id(env.get(ev))]
    if len(matched) == 1:
        return matched[0]
    if len(matched) > 1:
        return _AMBIGUOUS  # env collapses these tiers onto one id — not rankable
    # `fable` belongs here even though it has no ANTHROPIC_DEFAULT_*_MODEL var: leaving it
    # unclassified routes it into the custom-model fail-open, which is how it used to clear
    # every ceiling. It is a first-party family, not a custom id.
    for tier in ("haiku", "sonnet", "opus", "fable"):  # disjoint families; order irrelevant
        if tier in nid:
            return tier
    return None


# --- model FAMILY (a separate question from the ladder above) ----------------------------
#
# classify_tier answers "where does this sit on haiku<sonnet<opus<fable", so model_guard can
# enforce a ceiling; a model off that ladder returns None and evaluate() reads that as
# fail-open. Correct, and four call sites depend on it — nothing below touches that path.
#
# This answers "which family is driving", so prose can be pitched at it: a thin skill body
# leans on inference, and a second-tier model does better pointed at the step-by-step
# reference than asked to infer it. Families live in data/model-families.yaml as PATTERNS,
# never versions — a table of exact ids goes stale silently, since an unmatched id reads
# exactly like a frontier model and the fallback just stops applying.

_FAMILIES_CACHE = None


def _families():
    """The family table, read once. Fail-open to empty on any problem: an unreadable
    table must degrade to 'unknown family', never raise into a hook and never silently
    switch a session into either mode."""
    global _FAMILIES_CACHE
    if _FAMILIES_CACHE is not None:
        return _FAMILIES_CACHE
    path = os.environ.get("HARNESS_MODEL_FAMILIES")
    if not path:
        path = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                            "..", "data", "model-families.yaml")
    table = {"second_tier": [], "frontier": []}
    try:
        import yaml_io
        loaded = yaml_io.yaml_load(open(path, encoding="utf-8").read()) or {}
        for key in table:
            vals = loaded.get(key) or []
            table[key] = [str(v).strip().lower() for v in vals if str(v).strip()]
    except Exception:  # noqa: BLE001 - a broken table is 'unknown', never an exception
        pass
    _FAMILIES_CACHE = table
    return table


def model_family(model):
    """The family group this model belongs to — 'second_tier', 'frontier', or None.

    None means UNRECOGNISED, which is deliberately not the same as frontier: a typo or a
    new vendor opts into neither mode rather than silently picking one. Matching is a
    case-insensitive substring on the normalised id, so a later version of a listed family
    (`minimax-m9`, `glm-5`) still matches without a config edit.

    `HARNESS_MODEL_TIER` (`1` frontier / `2` second-tier) OVERRIDES the table in both
    directions. A pattern table cannot know every vendor, and an id is not always the
    truth: a proxy, an internal alias, or a gateway that rewrites the model name all
    leave the operator knowing something the string does not say. An unreadable value is
    IGNORED rather than honoured — a typo must not disable the recogniser for everything.
    """
    declared = str(os.environ.get("HARNESS_MODEL_TIER") or "").strip()
    if declared in ("1", "2"):
        return "frontier" if declared == "1" else "second_tier"
    nid = _norm_id(model)
    if not nid:
        return None
    table = _families()
    for group in ("second_tier", "frontier"):
        if any(pat in nid for pat in table.get(group) or []):
            return group
    return None


def is_second_tier(model) -> bool:
    """True only for a POSITIVELY recognised second-tier family. Unknown is False —
    absence of evidence is not evidence, and a false True would put every session into
    the verbose reading mode this trim exists to avoid."""
    return model_family(model) == "second_tier"


def _rank(tier):
    """Rank of a DECLARED BOUND endpoint, or None when the alias cannot bound anything
    (fable / AMBIGUOUS / unknown). Callers treat None as 'this bound enforces nothing'."""
    return _TIER_RANK.get(tier)


def _effective_rank(tier):
    """Rank of the model BEING EVALUATED, or None when it cannot be ranked. Differs from
    _rank by one entry (fable, above opus) — see the two tables for why that asymmetry is
    load-bearing rather than an oversight."""
    return _EFFECTIVE_RANK.get(tier)


def model_satisfies(model, required) -> bool:
    """Back-compat exact check: substring match so both a bare alias ('haiku') and a dated id
    ('claude-haiku-4-5-20251001') satisfy 'haiku'. No requirement => always satisfied."""
    if not required:
        return True
    return str(required).strip().lower() in str(model or "").strip().lower()


def _ok(kind, note=""):
    return {"ok": True, "kind": kind, "effective": None, "note": note}


def evaluate(spawn_model, session_model, resolved, env=None) -> dict:
    """Decide whether a spawn satisfies the resolved bound.

    Returns {ok, kind, effective, note}. `kind` is one of
    none|explicit|exact|ceiling|floor and drives the block message.

    Session-awareness: a bare inherit (empty spawn_model) resolves to `session_model` — the
    LIVE model — unless the agent is self_pinned (then the frontmatter model applies and the
    inherit is trusted). Tier comparisons FAIL OPEN when the effective model cannot be cleanly
    classified (custom/collapsed mapping) so a custom setup is never false-blocked."""
    env = os.environ if env is None else env
    spawn = str(spawn_model or "").strip()
    require_explicit = resolved.get("require_explicit")
    required = resolved.get("required_model")
    maxm = resolved.get("max_model")
    minm = resolved.get("min_model")
    self_pinned = resolved.get("self_pinned")

    if not (require_explicit or required or maxm or minm):
        return _ok("none")

    # require_explicit: a bare inherit is never enough — name a model or record a reason.
    if require_explicit:
        if spawn:
            return _ok("explicit")
        return {"ok": False, "kind": "explicit", "effective": "(inherit)", "note": ""}

    # Effective model: explicit wins; else a self_pinned agent runs its frontmatter model
    # (== the required tier) so the inherit is satisfied; else the live session model.
    if spawn:
        effective = spawn
    elif self_pinned:
        return _ok("exact" if required else ("ceiling" if maxm else "floor"),
                   note="self_pinned inherit trusts frontmatter")
    else:
        effective = str(session_model or "").strip()

    et = classify_tier(effective, env)
    # A blank effective (bare inherit with no live/session model to reason about) forces an
    # explicit choice — it is a violation, NOT a fail-open. A NON-blank id that merely cannot
    # be classified (a custom id absent from the env, or a collapsed/AMBIGUOUS mapping) fails
    # open, so a custom model setup is never false-blocked.
    blank = not effective

    # Exact.
    if required:
        if required == "fable":
            ok = "fable" in _norm_id(effective)  # unranked — id/substring match only
            return {"ok": ok, "kind": "exact", "effective": effective, "note": ""}
        if blank:
            return {"ok": False, "kind": "exact", "effective": "(inherit)", "note": ""}
        if et in (_AMBIGUOUS, None):
            return _ok("exact", note="unclassifiable custom model → fail-open")
        return {"ok": et == required, "kind": "exact", "effective": effective, "note": ""}

    # Ceiling (<=).
    if maxm:
        ct = _rank(maxm)
        if ct is None:  # a fable/unranked ceiling is not a valid bound — enforce nothing.
            return _ok("none", note="unrankable ceiling alias %r" % maxm)
        if blank:
            return {"ok": False, "kind": "ceiling", "effective": "(inherit)", "note": ""}
        if et in (_AMBIGUOUS, None):
            return _ok("ceiling", note="unclassifiable custom model → fail-open")
        return {"ok": _effective_rank(et) <= ct, "kind": "ceiling",
                "effective": effective, "note": ""}

    # Floor (>=).
    if minm:
        ft = _rank(minm)
        if ft is None:
            return _ok("none", note="unrankable floor alias %r" % minm)
        if blank:
            return {"ok": False, "kind": "floor", "effective": "(inherit)", "note": ""}
        if et in (_AMBIGUOUS, None):
            return _ok("floor", note="unclassifiable custom model → fail-open")
        return {"ok": _effective_rank(et) >= ft, "kind": "floor",
                "effective": effective, "note": ""}

    return _ok("none")


# ── Per-agent effort SSOT ───────────────────────────────────────────────────────────────
# model-policy.yaml's `agents:` map is also the effort SSOT: an `effort:` key per
# non-haiku agent (haiku has no effort dial — declares none). Reader is fail-open like
# resolve()/_load_config; it never treats `effort:` as a resolve() bound (resolve() only
# ever reads required_model/max_model/min_model/require_explicit/self_pinned/mode).

_EFFORT_LEVELS = ("low", "medium", "high", "xhigh", "max")
# model-id substring marking the older generation that lacks an xhigh dial (opus-4.6,
# sonnet-4.6); sonnet-5/opus-4.7/opus-4.8/fable all support xhigh.
_NO_XHIGH_ID_MARKERS = ("4-6", "4.6")


def effort_for(agent_type, env=None):
    """Return the policy `effort:` for agent_type (de-namespaced), or None when absent,
    haiku, unknown, or the config is broken. Never raises — mirrors _load_config's
    fail-open contract."""
    env = os.environ if env is None else env
    try:
        cfg = _load_config(env)
        if not cfg:
            return None
        agents = cfg.get("agents") if isinstance(cfg.get("agents"), dict) else {}
        entry = agents.get(_norm(agent_type))
        if not isinstance(entry, dict):
            return None
        eff = entry.get("effort")
        return eff.strip().lower() if isinstance(eff, str) and eff.strip() else None
    except Exception:  # noqa: BLE001 — a broken config must not wedge a caller
        return None


def effort_valid_for_model(effort, model, env=None) -> bool:
    """Capability clamp: is `effort` usable on the concrete `model` id?

    haiku has NO effort dial: any effort value is invalid, `None` is valid. `xhigh` is
    invalid on the older opus-4.6/sonnet-4.6 generation but valid on sonnet-5/opus-4.7/
    opus-4.8/fable; the other levels (low/medium/high/max) are valid on any sonnet/opus/
    fable generation. An unclassifiable model id fails OPEN (True) — never false-rejects a
    custom setup. Never raises."""
    env = os.environ if env is None else env
    try:
        eff = str(effort).strip().lower() if effort else None
        if eff is None:
            return True
        if eff not in _EFFORT_LEVELS:
            return True  # unrecognized effort string — fail open, nothing to clamp against

        nid = _norm_id(model)
        tier = classify_tier(model, env)

        if tier == "haiku":
            return False  # haiku carries no effort dial at all

        if "fable" in nid:
            return True  # fable supports every level

        if eff != "xhigh":
            return True  # low/medium/high/max valid on any sonnet/opus generation

        if any(marker in nid for marker in _NO_XHIGH_ID_MARKERS):
            return False  # the 4.6 generation has no xhigh dial

        return True  # sonnet-5/opus-4.7/opus-4.8/unclassifiable → fail open / valid
    except Exception:  # noqa: BLE001 — never brick a caller on a malformed input
        return True


if __name__ == "__main__":
    import json
    import sys

    ap_agent = sys.argv[1] if len(sys.argv) > 1 else "explore"
    sys.stdout.write(json.dumps(resolve(ap_agent)) + "\n")
