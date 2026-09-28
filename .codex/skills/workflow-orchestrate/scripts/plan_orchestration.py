#!/usr/bin/env python3
"""Structural lead for hs:workflow-orchestrate: emit a deterministic spawn strategy.

Judgment stays in the LLM layer; this script only turns a few declared task
knobs into a machine-checkable proposal the skill prints for user approval:
mode (subagents vs workflow), group->sub-count map, batch size, which base
workflow template to reuse, and the early-write report dir.

Deterministic by design — same flags in, same JSON out — so the skill's
"present the plan before you spawn" directive has real backing, not prose.
"""
import argparse
import json
import re
import sys

# --- assessment predicates (content-derived, deterministic) ------------------
# The confidence score is derived from the CONTENT of the reflected fields, not
# their mere presence: a hollow "all"/"stuff" set never reaches the
# light bypass. Every predicate is pure + stdlib so the script stays importable by
# file path with no cross-tree dependency.

_CITE_RE = re.compile(r"hs:\w+|\b(?:low|medium|high|xhigh|max)\b|\d")
_MODE_RE = re.compile(r"\b(?:subagents?|workflow|team|inline)\b|\bmode [ABC]\b", re.I)
_TEMPLATE_RE = re.compile(r"base-[\w-]+|inline|pipeline|fanout", re.I)
_UNBOUNDED = ("all", "everything", "*", "any", "whole")
_WRITE_LANE_RE = re.compile(r"\b(?:worktree|isolation|--fix|write|edit|patch)\b", re.I)


def _has_cite(reason: str) -> bool:
    return bool(reason.strip()) and bool(_CITE_RE.search(reason))


def _names_mode_and_template(strategy: str) -> bool:
    return bool(_MODE_RE.search(strategy)) and bool(_TEMPLATE_RE.search(strategy))


def _scope_bounded(scope: str) -> bool:
    s = scope.strip().lower()
    if not s or s in _UNBOUNDED:
        return False
    if any(w == s or s.startswith(w + " ") or (" " + w + " ") in (" " + s + " ")
           for w in _UNBOUNDED):
        return False
    return bool(re.search(r"\d|/", scope))


def _has_write_lane(strategy: str) -> bool:
    return bool(_WRITE_LANE_RE.search(strategy))


def parse_groups(spec: str) -> list[dict]:
    groups = []
    for chunk in (spec or "").split(","):
        chunk = chunk.strip()
        if not chunk:
            continue
        if ":" not in chunk:
            print(f"bad group '{chunk}': want key:count", file=sys.stderr)
            raise SystemExit(2)
        key, _, cnt = chunk.partition(":")
        key = key.strip()
        try:
            n = int(cnt)
        except ValueError:
            print(f"bad count in '{chunk}'", file=sys.stderr)
            raise SystemExit(2)
        if not key or n < 1:
            print(f"bad group '{chunk}'", file=sys.stderr)
            raise SystemExit(2)
        groups.append({"key": key, "subs": n})
    if not groups:
        print("no groups given (--groups key:count,...)", file=sys.stderr)
        raise SystemExit(2)
    return groups


# Agent Teams is CLI-only and EXPERIMENTAL in Claude Code (research preview,
# gated by CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS + a server statsig). TeamCreate/
# TeamDelete were removed in v2.1.178 — the live model is one implicit team plus
# Agent(name=...) to spawn a named teammate and SendMessage to coordinate.
TEAM_FLAG = "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS=1 (or --agent-teams)"
TEAM_API = "Agent(name=...) + SendMessage (one implicit team; TeamCreate/TeamDelete removed CC v2.1.178)"

# Matches the Workflow tool's own budget heuristic (~1 agent per 100k output tokens).
DEFAULT_PER_SUB_TOKENS = 100_000


def token_budget_plan(groups: list[dict], sub_count: int, budget: int, per_sub: int) -> dict:
    """Cap the fan-out to what a TOKEN/cost budget affords. This is the
    output-token cost ceiling (~100k/sub), NOT the Layer-1b spawn-COUNT budget
    the provenance guard enforces — two distinct axes; do not conflate them.

    Advisory + non-destructive: the emitted `groups`/`sub_count` keep the human's
    original ask; this block only reports whether it fits and, if not, a concrete
    trimmed map that does. The skill presents both and lets the user confirm the
    cut — trimming is never applied silently (same contract as the exec gate).
    """
    capacity = budget // per_sub
    block = {
        "total": budget,
        "per_sub": per_sub,
        "capacity": capacity,
        "sub_count": sub_count,
        "within_budget": sub_count <= capacity,
        "trim_advice": None,
    }
    if sub_count <= capacity:
        return block

    # Budget affords zero subs: nothing to seat, name every dropped group.
    if capacity < 1:
        block["trim_advice"] = {
            "groups": [],
            "total_subs": 0,
            "dropped_subs": sub_count,
            "dropped_groups": [g["key"] for g in groups],
            "note": "token budget affords zero subs — raise --token-budget or drop the fan-out",
        }
        return block

    # Can't seat one sub per group: keep the leading `capacity` groups at 1 each,
    # drop the tail (order-preserved) rather than starve every group below 1.
    if capacity < len(groups):
        kept, dropped = groups[:capacity], groups[capacity:]
        block["trim_advice"] = {
            "groups": [{"key": g["key"], "subs": 1} for g in kept],
            "total_subs": capacity,
            "dropped_subs": sub_count - capacity,
            "dropped_groups": [g["key"] for g in dropped],
            "note": f"budget seats {capacity} subs < {len(groups)} groups — tail groups dropped",
        }
        return block

    # capacity >= #groups: floor 1 each, then hand the remainder out
    # widest-original-first so wide groups stay wide. Each group is capped at its
    # original ask, so we never inflate past what was requested.
    trimmed = [{"key": g["key"], "subs": 1} for g in groups]
    remaining = capacity - len(groups)
    order = sorted(range(len(groups)), key=lambda i: groups[i]["subs"], reverse=True)
    # Hand out the remainder widest-original-first, looping until it is fully
    # placed or every group has hit its original cap. A full pass that seats
    # nothing means no group can take more — stop, never under-allocate or spin.
    while remaining > 0:
        progressed = False
        for idx in order:
            if remaining <= 0:
                break
            if trimmed[idx]["subs"] < groups[idx]["subs"]:
                trimmed[idx]["subs"] += 1
                remaining -= 1
                progressed = True
        if not progressed:
            break
    total = sum(g["subs"] for g in trimmed)
    block["trim_advice"] = {
        "groups": trimmed,
        "total_subs": total,
        "dropped_subs": sub_count - total,
        "dropped_groups": [],
        "note": f"trimmed {sub_count}->{total} subs to fit {capacity}-sub budget",
    }
    return block


def choose_mode(
    stages: int,
    sub_count: int,
    barrier: bool,
    determinism: bool,
    coordinate: bool,
    long_lived: bool,
    override: str | None,
) -> tuple[str, str]:
    if override:
        return override, f"explicit --mode {override}"
    # Mode C (agent teams) is the NARROW case: long-lived work whose units must
    # message/challenge each other mid-flight — not a one-shot advisory fan-out.
    # Both signals are required so an ordinary wide fan-out does not misroute to
    # the experimental, high-cost team path.
    if coordinate and long_lived:
        return "team", "team: long-lived + mid-flight coordination (agent teams, experimental)"
    # Workflow earns its cost when the run is multi-stage, needs a barrier or
    # deterministic control flow, or is wide enough that hand-driven inline
    # batches get unwieldy. Otherwise a plain Task fan-out is cheaper.
    if stages > 1 or barrier or determinism or sub_count >= 6:
        why = []
        if stages > 1:
            why.append(f"{stages} stages")
        if barrier:
            why.append("barrier")
        if determinism:
            why.append("deterministic control flow")
        if sub_count >= 6:
            why.append(f"{sub_count} subs")
        return "workflow", "workflow: " + ", ".join(why)
    return "subagents", f"subagents: single-stage, {sub_count} subs, no barrier"


def choose_template(mode: str, stages: int, fanout: bool, find_verify: bool) -> str:
    if mode == "team":
        return "agent-teams"
    if mode == "subagents":
        return "inline-task"
    if find_verify:
        return "hs:base-pipeline-verify"
    if fanout and stages <= 2:
        return "hs:base-fanout-consolidate"
    return "inline-workflow"


def exec_gate(mode: str, ultracode: bool) -> dict:
    """Resolve the execution-gate policy.

    ultracode ON + workflow -> run the Workflow automatically.
    ultracode OFF + workflow -> MANDATORY user confirmation before running; the
      caller must never silently downgrade to inline subagents to dodge the ask.
    team -> always confirm (experimental + high cost), ultracode notwithstanding.
    subagents -> auto (cheap default, no opt-in needed).
    """
    if mode == "team":
        return {
            "gate": "confirm_required",
            "reason": "agent teams are experimental + high-cost — always confirm before spawning",
            "no_silent_downgrade": True,
        }
    if mode == "workflow":
        if ultracode:
            return {
                "gate": "auto",
                "reason": "ultracode on -> run the Workflow",
                "no_silent_downgrade": True,
            }
        return {
            "gate": "confirm_required",
            "reason": "workflow is the right mode but ultracode is off -> ask the user before "
                      "running; never silently fall back to inline subagents",
            "no_silent_downgrade": True,
        }
    return {
        "gate": "auto",
        "reason": "inline Task fan-out — cheap default, no opt-in needed",
        "no_silent_downgrade": True,
    }


def assess(groups, sub_count, stages, barrier, reason, strategy, scope, cap):
    """Turn declared knobs + reflected fields into an advisory score.

    Emits complexity (0..6 count), confidence (0..4 count), route_depth, and the
    red-flags that block a light bypass. Purely reflective: it never blocks — the
    skip-vs-escalate decision stays with the model. `cap` is a PRE-RESOLVED
    int (or None); the formula that produced it lives in orchestration_config.py,
    never here, so this script imports nothing cross-tree.
    """
    reason = reason or ""
    strategy = strategy or ""
    scope = scope or ""
    fields_present = bool(reason.strip()) and bool(strategy.strip()) and bool(scope.strip())

    over_cap = cap is not None and sub_count > cap
    variable_scope = not _scope_bounded(scope)
    write_lane = _has_write_lane(strategy)
    one_sub_per_finding = sub_count >= 6 and len(groups) == sub_count

    flags = []
    if not fields_present:
        flags.append("missing-fields")
    if over_cap:
        flags.append("over-cap")
    if one_sub_per_finding:
        flags.append("one-sub-per-finding")
    if scope.strip() and not _scope_bounded(scope):
        flags.append("unbounded-scope")
    if reason.strip() and not _has_cite(reason):
        flags.append("no-evidence")

    complexity = sum((
        stages > 1, bool(barrier), sub_count >= 6, over_cap,
        variable_scope, write_lane,
    ))

    confidence = sum((
        _has_cite(reason),
        _names_mode_and_template(strategy),
        _scope_bounded(scope),
        not flags,  # a clean red-flag set is itself a confidence signal
    ))

    light = complexity <= 2 and confidence >= 3 and fields_present
    return {
        "complexity": int(complexity),
        "confidence": int(confidence),
        "route_depth": "light" if light else "agent",
        "flags": flags,
        "cap": cap,
        "over_cap": bool(over_cap),
    }


def _sibling_dir():
    import os
    return os.path.dirname(os.path.abspath(__file__))


def _state_path(run_id) -> str:
    """Per-run state.json under the harness state dir (via run_state). Falls back to a state-
    relative hint if the sibling resolver cannot load."""
    try:
        if _sibling_dir() not in sys.path:
            sys.path.insert(0, _sibling_dir())
        import run_state  # noqa: E402 — sibling
        return run_state.run_state_path(run_id)
    except Exception:  # noqa: BLE001 — proposal must still emit even if the resolver is absent
        return "harness/state/orchestrate/%s/state.json" % run_id


def _history_path() -> str:
    """The cross-run metrics corpus under the harness state dir (via orchestrate_metrics)."""
    try:
        if _sibling_dir() not in sys.path:
            sys.path.insert(0, _sibling_dir())
        import orchestrate_metrics  # noqa: E402 — sibling
        return orchestrate_metrics.history_path()
    except Exception:  # noqa: BLE001
        return "harness/state/orchestrate-history.jsonl"


ULTRA_DEFAULT = 5
# Three, not five. Two positions is a disagreement with nothing to break the tie except
# the reader's prior; three is the smallest count where the synthesis has something to
# weigh. The best-of-N default is higher because there the extra draft costs a draft,
# while here every extra position also lengthens the argument being reconciled.
DEBATE_DEFAULT = 3
ULTRA_VERIFIER = "hs:escalation-consultant"


def panel_shape(members: int, *, debate: bool = False) -> dict:
    """A panel: N independent producers, one separate reader at the strongest tier.

    Two SHAPES of one thing, which is why they share this block instead of getting a
    code path each. `best-of-n` produces N attempts and keeps the best; `debate`
    produces N positions and keeps what survives the argument. Everything else is
    identical — the topology, the barrier, the independence contract, the approval
    gate — and two copies of that contract drift the moment one is edited.

    Named `panel` rather than after either shape. The block used to be keyed `ultra`,
    which meant a debate run reported itself under the name of the shape it is not;
    a reader checking `shape` would have been reading a field the key contradicted.

    Lives here rather than in each caller's body because the shape has exactly two
    load-bearing properties and both are easy to lose in a re-telling. The candidates
    must not see each other — N attempts that read each other's work converge, and the
    N becomes a cost with no spread behind it. And the chooser must be a different
    reader at the strongest tier, because a candidate grading its own attempt reports
    the confidence it already had rather than a comparison.

    The verifier is the agent this repo already escalates to, so the counsel flag and
    this shape cannot disagree about who the strongest reader is.
    """
    unit = "position" if debate else "candidate"
    candidates = members
    task = (
        "reconcile the %d positions into ONE answer: say where they agree, name each "
        "real disagreement, and resolve it on evidence rather than on majority" % candidates
        if debate else
        "compare the %d candidates against the stated goal, pick one, and say what the "
        "others got right that the winner should absorb" % candidates)
    return {
        "shape": "debate" if debate else "best-of-n",
        "candidates": candidates,
        "independent": True,
        "independence_rule": "%ss run with no sight of each other's output; shared "
                             "context collapses the spread the count pays for" % unit,
        "verifier": {
            "agent": ULTRA_VERIFIER,
            "separate_from_candidates": True,
            "task": task,
        },
    }


def build(args) -> dict:
    if args.debate and args.ultra is None:
        args.ultra = DEBATE_DEFAULT
    if args.ultra is not None:
        if args.groups:
            print("--ultra sizes the fan-out itself; passing --groups too leaves two "
                  "sources for one number", file=sys.stderr)
            raise SystemExit(2)
        if args.ultra < 2:
            print("--ultra needs at least 2 candidates — best-of-one is one attempt "
                  "with a second reader billed on top", file=sys.stderr)
            raise SystemExit(2)
        args.groups = ("position:%d,synthesis:1" if args.debate
                       else "candidate:%d,verify:1") % args.ultra
        args.barrier = True
        args.fanout = True
    elif not args.groups:
        print("--groups is required (or --ultra to size it)", file=sys.stderr)
        raise SystemExit(2)
    groups = parse_groups(args.groups)
    sub_count = sum(g["subs"] for g in groups)
    stages = args.stages if args.stages is not None else len(groups)

    mode, reason = choose_mode(
        stages, sub_count, args.barrier, args.determinism,
        args.coordinate, args.long_lived, args.mode,
    )
    template = choose_template(mode, stages, args.fanout, args.find_verify)

    base = "docs/product/_refs" if args.product else args.refs_base.rstrip("/")
    report_dir = f"{base}/{args.run_id}/"

    out = {
        "run_id": args.run_id,
        "status": "planned",
        "mode": mode,
        "reason": reason,
        "stages": stages,
        "sub_count": sub_count,
        "groups": groups,
        "batch_size": args.batch,
        "consolidate": "per-group",
        "template": template,
        "report_dir": report_dir,
        # Machine-written run-state + the metrics corpus live under the harness STATE dir
        # (gitignored), not the human-facing report dir. state.json is per-run; the skill
        # writes it for a real fan-out and reads it on --resume. history.jsonl is the
        # cross-run advisory metrics corpus.
        "state_path": _state_path(args.run_id),
        "history_path": _history_path(),
        "early_write": True,
        "exec": exec_gate(mode, args.ultracode),
        "inputs": {
            "reason": args.reason or "",
            "strategy": args.strategy or "",
            "scope": args.scope or "",
        },
        "assessment": assess(
            groups, sub_count, stages, args.barrier,
            args.reason, args.strategy, args.scope, args.group_cap,
        ),
    }
    if args.token_budget is not None:
        if args.token_budget < 1:
            print("token-budget must be >= 1", file=sys.stderr)
            raise SystemExit(2)
        if args.per_sub_cost < 1:
            print("per-sub-cost must be >= 1", file=sys.stderr)
            raise SystemExit(2)
        out["token_budget"] = token_budget_plan(groups, sub_count, args.token_budget, args.per_sub_cost)
    if args.ultra is not None:
        out["panel"] = panel_shape(args.ultra, debate=args.debate)
    if mode == "team":
        out["experimental"] = True
        out["requires_flag"] = TEAM_FLAG
        out["api"] = TEAM_API
    return out


def main() -> None:
    ap = argparse.ArgumentParser(description="Emit a spawn-strategy proposal (JSON).")
    ap.add_argument("--run-id", required=True)
    ap.add_argument("--groups", default=None, help="key:count,key:count (e.g. research:4,critique:6)")
    ap.add_argument("--ultra", nargs="?", type=int, const=ULTRA_DEFAULT, default=None,
                    metavar="N",
                    help=f"best-of-N: size N independent candidates plus one "
                         f"strongest-tier verifier (default {ULTRA_DEFAULT}); "
                         f"replaces --groups rather than adding to it")
    ap.add_argument("--debate", action="store_true",
                    help=f"argue instead of compete: N independent POSITIONS plus one "
                         f"synthesis that reconciles them (default {DEBATE_DEFAULT}); "
                         f"--ultra picks a winner, this one resolves disagreements")
    ap.add_argument("--stages", type=int, default=None, help="override stage count (default = #groups)")
    ap.add_argument("--barrier", action="store_true", help="a stage needs all prior results")
    ap.add_argument("--determinism", action="store_true", help="control flow must be deterministic")
    ap.add_argument("--fanout", action="store_true", help="single fan-out -> dedup shape")
    ap.add_argument("--find-verify", action="store_true", help="find -> verify shape")
    ap.add_argument("--mode", choices=["subagents", "workflow", "team"], default=None,
                    help="explicit mode override (else derived from knobs)")
    ap.add_argument("--coordinate", action="store_true",
                    help="teammates must message/challenge each other mid-flight (team signal)")
    ap.add_argument("--long-lived", dest="long_lived", action="store_true",
                    help="work spans a long build/research, not a one-shot fan-out (team signal)")
    ap.add_argument("--ultracode", action="store_true",
                    help="ultracode is on -> workflow runs auto; else workflow needs user confirm")
    ap.add_argument("--token-budget", dest="token_budget", type=int, default=None,
                    help="token/cost-budget target (output tokens, NOT the spawn-count budget); "
                         "caps the fan-out + emits a trim proposal when over")
    ap.add_argument("--per-sub-cost", dest="per_sub_cost", type=int, default=DEFAULT_PER_SUB_TOKENS,
                    help=f"est. output tokens per sub (default {DEFAULT_PER_SUB_TOKENS})")
    ap.add_argument("--reason", default=None,
                    help="why this fan-out (concrete, citable trigger) — reflected verbatim")
    ap.add_argument("--strategy", default=None,
                    help="mode + base template + group->count — reflected verbatim")
    ap.add_argument("--scope", default=None,
                    help="file-surface/SCALE + variable-vs-fixed count — reflected verbatim")
    ap.add_argument("--group-cap", dest="group_cap", type=int, default=None,
                    help="pre-resolved group cap (from orchestration_config.py --group-cap); "
                         "absent -> over_cap scoring off (back-compat)")
    ap.add_argument("--batch", type=int, default=2, help="inline fan-out batch size (default 2)")
    ap.add_argument("--refs-base", default="plans/reports", help="early-write base dir")
    ap.add_argument("--product", action="store_true", help="route report dir under docs/product/_refs")
    args = ap.parse_args()
    json.dump(build(args), sys.stdout, ensure_ascii=False, indent=2)
    sys.stdout.write("\n")


if __name__ == "__main__":
    main()
