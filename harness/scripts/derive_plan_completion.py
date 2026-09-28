#!/usr/bin/env python3
"""derive_plan_completion.py — derive "this plan finished all its phases" from
per-phase evidence snapshots, deterministically and fail-SAFE.

The canonical verification.json is overwritten every phase, so it cannot answer
"are all N phases done?". phase_progress_writer keeps a per-phase copy
(verification-<phase>.json on a PASS). This module counts the DISTINCT phases
with a PASS snapshot whose id is a real plan-graph node, and calls the plan
complete only when that count reaches N (N = number of plan-graph nodes).

Why this shape is safe by construction:
  * complete needs N distinct node-phases — a single phase can never reach N, so
    closing after phase 1 of N is structurally impossible.
  * a missing sidecar, missing snapshots, or a corrupt file all reduce the count
    -> incomplete. Every degradation is an UNDER-count: it can delay a close, it
    can never cause an early one.
  * pure read: no writes, no network. Snapshots are an on-disk derived cache; the
    source of truth stays the committed frontmatter status + canonical verification.

Contract:
    is_complete(plan_dir, root=None) -> bool
    completion_state(plan_dir, root=None) -> dict
        {n_total, passed_phases:set, complete:bool, reason:str}
"""
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
import plan_graph  # noqa: E402
import artifact_check  # noqa: E402

_PASS_VERDICTS = {"PASS", "PASS_WITH_RISK"}
_PREFIX = "verification-"
_SUFFIX = ".json"


def _resolve_plan_dir(plan_dir, root):
    pd = Path(plan_dir)
    if root is not None and not pd.is_absolute():
        pd = Path(root) / pd
    return pd


def _missing_gate_fields(rec) -> list:
    """The gate-required verification fields this record lacks.

    Counting a phase here is what CLOSES the plan, and a closed plan is the
    state the ship gate cannot resolve — so what counts must be what the gate
    would ADMIT, not merely a file carrying verdict PASS. It was the latter,
    and the gap is reachable by the ordinary path: the canonical writer stamps
    stage/actor, an agent hand-writing the JSON omits them, the snapshot hook
    copies it anyway, and the plan reports completed on evidence artifact_check
    rejects as malformed. The field list is imported, never re-typed, so the
    two cannot drift back apart.
    """
    required = artifact_check._REQUIRED_FIELDS.get("verification", ())
    return [k for k in required if rec.get(k) in (None, "", [], {})]


def _is_verification_post(name: str) -> bool:
    """True for a post artifact named like a verification snapshot
    (verification-<id>.json) — those keep the verdict gate. Any other declared
    artifact (e.g. review-decision.json) is checked for presence only."""
    return name.startswith(_PREFIX) and name.endswith(_SUFFIX) and len(name) > len(_PREFIX) + len(_SUFFIX)


def _latest_verdict_regressed(art: Path, node: str):
    """None when there is no reason to doubt the node's PASS snapshot, else why.

    verification_snapshot.snapshot() is deliberately immutable/first-wins by
    ratified policy: once a phase earns a PASS snapshot it is never
    rewritten, even by a later regression on the SAME phase. That is correct
    evidence policy, but it means the snapshot alone cannot answer "is this
    STILL true" — a phase that regressed PASS -> BLOCKED keeps its stale PASS
    snapshot, and once a LATER phase's write overwrites the plan's single
    canonical verification.json, even that regression stops being visible
    anywhere. write_verification.py additionally maintains an always-current,
    mutable marker per phase (phase-latest-<node>.json, written on every run
    regardless of verdict) specifically so this counter has a "what did the
    last write for THIS phase actually say" signal that survives later writes
    to OTHER phases. Consulting it here can only ever REMOVE a node from
    `passed` (never add one absent from the snapshot check), so it stays
    inside the module's own invariant: every degradation is an under-count.
    A marker written by an older harness (or via the PostToolUse Write-tool
    path, which does not yet maintain this file) simply does not exist —
    degrade to the pre-existing snapshot-only behaviour, silently."""
    marker = art / ("phase-latest-%s.json" % node)
    if not marker.is_file():
        return None
    try:
        latest = json.loads(marker.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return "phase-latest-%s.json is unreadable" % node
    if isinstance(latest, dict) and latest.get("verdict") not in _PASS_VERDICTS:
        return ("the latest write for phase %r was verdict %r, superseding an "
                "earlier PASS snapshot — re-run write_verification.py with a "
                "passing verdict to re-close this phase" % (node, latest.get("verdict")))
    return None


def _node_post_satisfied(art: Path, post_list, node: str):
    """None when the node is satisfied, else why it is not (the caller folds
    those into completion_state's reason, so an unclosed plan says which phase
    is holding it and what that phase lacks).

    A node is satisfied when EVERY artifact it declares in `post` is present
    under artifacts/. A verification-*.json post additionally requires verdict
    in {PASS, PASS_WITH_RISK}, the gate's own required fields (see
    _missing_gate_fields), AND every check green by the gate's own rule
    (artifact_check.failing_checks_reason — the same function the gate calls, not
    a second copy of it). A corrupt/unreadable verification file fails its node —
    an under-count is the safe direction.

    The checks rule is here because reading only `verdict` made this counter
    disagree with the gate: a phase carrying PASS_WITH_RISK over FAILing checks
    counted as done while the gate blocked on it, so a plan could report N/N
    complete with work still red underneath."""
    for name in post_list:
        f = art / name
        if not f.is_file():
            return "missing %s" % name
        if _is_verification_post(name):
            try:
                rec = json.loads(f.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                return "%s is unreadable" % name
            if not isinstance(rec, dict) or rec.get("verdict") not in _PASS_VERDICTS:
                return "%s does not carry a PASS verdict" % name
            missing = _missing_gate_fields(rec)
            if missing:
                return ("%s is missing the field(s) the gate requires: %s — "
                        "write it via write_verification.py, which stamps them"
                        % (name, ", ".join(missing)))
            red = artifact_check.failing_checks_reason(rec)
            if red:
                return "%s: %s" % (name, red)
    return _latest_verdict_regressed(art, node)


def completion_state(plan_dir, root=None) -> dict:
    pd = _resolve_plan_dir(plan_dir, root)

    graph = plan_graph.parse_phase_graph(pd)
    if "error" in graph:
        # Sidecar is a MANDATORY plan artifact; its absence is anomalous, not a
        # reason to guess "done". Fail safe -> incomplete.
        return {"n_total": 0, "passed_phases": set(), "complete": False,
                "reason": "no plan-graph (%s)" % graph["error"]}
    all_nodes = plan_graph._all_nodes(graph)
    # A paused phase leaves the denominator: holding a plan open for work its author
    # deliberately deferred means the plan can never reach done. It stays VISIBLE in
    # the reason string, because a count that got smaller with no explanation is a
    # number the reader cannot check.
    paused = plan_graph.paused_phases(graph)
    nodes = all_nodes - paused
    n_total = len(nodes)
    pause_notes = [plan_graph.pause_note(graph, p) for p in sorted(paused)]

    # ONE counter, declarative source: each node satisfied iff its declared `post`
    # artifacts are all present (with the verdict gate on verification-*.json).
    # Default post = [verification-<node>.json] so a sidecar that never authored
    # `post` is identical to the old prefix logic.
    art = pd / "artifacts"
    passed = set()
    blockers = []
    for node in nodes:
        post = plan_graph.node_artifacts(graph, node)["post"]
        why = _node_post_satisfied(art, post, node)
        if why is None:
            passed.add(node)
        else:
            blockers.append("%s: %s" % (node, why))

    # n_total > 0 also covers the all-paused plan: pausing every phase is not a way
    # to reach done, it is a plan with nothing left to count.
    complete = n_total > 0 and len(passed) >= n_total
    reason = ("complete (%d/%d)" % (len(passed), n_total) if complete
              else "incomplete (%d/%d phases PASS) — %s"
              % (len(passed), n_total, "; ".join(blockers) or "no phases left to count"))
    if pause_notes:
        reason += " [not counted: %s]" % "; ".join(pause_notes)
    return {"n_total": n_total, "passed_phases": passed, "paused_phases": paused,
            "complete": complete, "reason": reason}


def is_complete(plan_dir, root=None) -> bool:
    return completion_state(plan_dir, root=root)["complete"]


def main(argv=None) -> int:
    argv = list(sys.argv[1:] if argv is None else argv)
    if len(argv) != 1:
        sys.stderr.write("usage: derive_plan_completion.py <plan_dir>\n")
        return 2
    st = completion_state(argv[0])
    st = {**st, "passed_phases": sorted(st["passed_phases"])}
    sys.stdout.write(json.dumps(st) + "\n")
    return 0 if st["complete"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
