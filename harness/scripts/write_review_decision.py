#!/usr/bin/env python3
"""write_review_decision.py — write the review-decision gate artifact.

The third gate producer (with write_verification + plan_approval). hs:code-review used
to write review-decision.yaml directly with the Write tool, so it was the one gate
artifact that could not carry a run_seq stamp. Routing it through artifact_io here gives
it the SAME treatment as the other two — atomic same-dir write + run_seq stamp (D1) —
so the orchestrator's watchdog can stale-reject all THREE gate artifacts, not just two.

Gate logic is unchanged: this only writes the record hs:code-review already produces
(verdict/reviewer/role/rationale + optional fields), conforming to
harness/schemas/artifact-review-decision.json. The verdict decision stays with the
reviewer; this is the write path, not the judgment.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

import yaml_io

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import artifact_io  # noqa: E402
import fs_guard  # noqa: E402
import harness_paths  # noqa: E402

_VERDICTS = ("PASS", "PASS_WITH_RISK", "BLOCKED")


def _resolve_reviewer(explicit):
    """Explicit --reviewer wins; else resolve_actor() (attribution, not auth)."""
    if explicit:
        return explicit
    try:
        sys.path.insert(0, str(_HERE.parent / "hooks"))
        import hook_runtime
        return hook_runtime.resolve_actor()
    except Exception:  # noqa: BLE001 — never block a write on attribution
        return "agent:code-reviewer"


def _build_record(args) -> dict:
    rec = {
        "verdict": args.verdict,
        "reviewer": _resolve_reviewer(args.reviewer),
        "role": args.role,
        "rationale": args.rationale,
    }
    # optional fields only when provided — keep the artifact minimal + schema-clean
    for key, val in (("plan_hash", args.plan_hash), ("ticket_id", args.ticket_id),
                     ("effort", args.effort), ("strategy", args.strategy),
                     ("reviewer_engine", args.reviewer_engine),
                     ("reviewer_model", args.reviewer_model)):
        if val is not None:
            rec[key] = val
    if args.rounds_run is not None:
        rec["rounds_run"] = args.rounds_run

    # The architecture block, which this writer could not produce at all until now.
    # `artifact_check._architecture_review_consistency` BLOCKS a hard stage when a
    # structural diff carries no `architecture_review.checked == true`, and the
    # schema has held the field since it was written — but the only sanctioned
    # writer had no flag for it, so the one path that clears the gate was to
    # hand-edit the artifact this script exists to stop people hand-editing.
    #
    # `doc_sha` and `drift` ride along only when given: the gate is presence-gated
    # on `checked`, and the schema requires nothing else, so an empty `drift` means
    # "judged, found none" rather than "not recorded".
    if args.architecture_checked:
        block: dict = {"checked": True}
        if args.architecture_doc_sha:
            block["doc_sha"] = args.architecture_doc_sha
        if args.architecture_drift:
            block["drift"] = list(args.architecture_drift)
        rec["architecture_review"] = block
    return rec


def _canonical_target(plan_dir: Path) -> Path:
    """.yaml preferred (SSOT), .json legacy. Default to .yaml when neither exists."""
    art = plan_dir / "artifacts"
    yaml_p, json_p = art / "review-decision.yaml", art / "review-decision.json"
    return json_p if json_p.exists() and not yaml_p.exists() else yaml_p


def _usable_round(rounds_run) -> bool:
    """A round id the snapshot can be named after. `bool` is excluded explicitly —
    it is an int in Python, and `--rounds-run` reaching here as True would file every
    round as r1 and then first-wins would keep only the first."""
    return (not isinstance(rounds_run, bool)
            and isinstance(rounds_run, int) and rounds_run >= 0)


def _snapshot_round(plan_dir: Path, target: Path, rounds_run) -> None:
    """Copy the canonical record to review-decision-r<N>.json — first-wins.

    Same shape as write_verification's verification-<phase>.json, with one
    deliberate difference: this keeps EVERY verdict, not just PASS. A BLOCKED that
    a later round clears is precisely the record worth auditing, and by then the
    canonical file has already been overwritten.

    Degrades silently on any snapshot problem AFTER this point: the round id is
    validated up front in main(), so what remains here is I/O, and losing history to
    a transient read error must not fail the gate write itself.
    """
    snap = plan_dir / "artifacts" / ("review-decision-r%d.json" % rounds_run)
    if snap.exists():
        return  # first-wins: a round's verdict is not rewritable
    try:
        text = target.read_text(encoding="utf-8")
        rec = json.loads(text) if target.suffix == ".json" else yaml_io.safe_load(text)
    except Exception:  # noqa: BLE001 — snapshot is best-effort, the gate write is not
        return
    if isinstance(rec, dict):
        artifact_io.atomic_write_text(snap, json.dumps(rec, ensure_ascii=False, indent=2))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("plan_dir", help="active plan dir (path)")
    ap.add_argument("--verdict", required=True, choices=_VERDICTS)
    ap.add_argument("--rationale", required=True, help="WHY — the verdict's justification")
    ap.add_argument("--reviewer", default=None, help="reviewer identity (default: resolve_actor)")
    ap.add_argument("--role", default="reviewer")
    ap.add_argument("--plan-hash", dest="plan_hash", default=None)
    ap.add_argument("--ticket-id", dest="ticket_id", default=None)
    ap.add_argument("--effort", default=None, choices=("low", "medium", "high", "xhigh", "max"))
    # Not argparse-`required`: the refusal below returns 2 like the other preconditions
    # instead of argparse's own SystemExit, so every rejection this writer makes has the
    # same shape and the message can explain WHY the flag matters.
    ap.add_argument("--rounds-run", dest="rounds_run", type=int, default=None,
                    help="REQUIRED — the review round this verdict belongs to "
                         "(the first round is 1); names the per-round snapshot")
    ap.add_argument("--strategy", default=None)
    ap.add_argument("--reviewer-engine", dest="reviewer_engine", default=None)
    ap.add_argument("--reviewer-model", dest="reviewer_model", default=None)
    ap.add_argument("--architecture-checked", dest="architecture_checked",
                    action="store_true",
                    help="record architecture_review.checked=true — REQUIRED before a "
                         "hard stage when the diff touched standards.yaml "
                         "drift.structural_globs")
    ap.add_argument("--architecture-doc-sha", dest="architecture_doc_sha", default=None,
                    help="sha of docs/system-architecture.md at review time (audit "
                         "only; never sha-matched at ship)")
    ap.add_argument("--architecture-drift", dest="architecture_drift", action="append",
                    default=None,
                    help="one drift finding; repeat for several. Absent = none found")
    args = ap.parse_args(argv)

    plan_dir = Path(args.plan_dir).resolve()
    # The other two gate producers both refuse an implausible plan_dir
    # (write_verification._check_phase_is_node, plan_approval's plan.md check) —
    # this was the one with none, so a stale/typo'd plan_dir silently created a
    # stray plans/-shaped directory and wrote the verdict where nothing reads it.
    if not (plan_dir / "plan.md").is_file():
        sys.stderr.write(
            "write_review_decision: no plan.md in %s — pass a plan dir under "
            "plans/\n" % plan_dir)
        return 2
    target = _canonical_target(plan_dir)
    try:
        # project_root(), NOT root(): the hint names the tree the plans/ zone resolves
        # against, and root() is the BIN root (its legacy HARNESS_ROOT alias is a bin
        # alias too). Only bites with NO global bin — fs_guard._zone_base honours an
        # explicit root only then, and discards it under HARNESS_BIN_ROOT — so this site
        # is invisible in the layout most tests arm. Same class and same reasoning as
        # plan_approval.py's two sites; do not revert one without the others.
        fs_guard.assert_under(target, "plans", root=harness_paths.project_root())
    except fs_guard.FenceError as e:
        sys.stderr.write("write_review_decision: %s\n" % e)
        return 2
    # Last precondition, and the one that decides whether this verdict survives the NEXT
    # round. Without a round id there is nothing to name the snapshot after, so the
    # canonical file is the only copy and the next round erases it. That used to degrade
    # to a stderr advisory — the wrong instrument twice over: the caller is an agent
    # following a prose brief, and stderr gates nothing, so the failure mode was history
    # disappearing quietly. Refusing keeps the gate unpassed and makes the omission loud.
    # Ordered after the plan-dir and fence checks so a stale plan dir still reports the
    # more specific cause it always did.
    if not _usable_round(args.rounds_run):
        sys.stderr.write(
            "write_review_decision: --rounds-run <N> is required — it names the "
            "review-decision-r<N>.json snapshot, which is what keeps this verdict "
            "readable after a later round overwrites the canonical file. Pass the "
            "round you just ran (the first is 1). Nothing was written.\n")
        return 2
    art = plan_dir / "artifacts"
    art.mkdir(parents=True, exist_ok=True)
    rec = _build_record(args)
    artifact_io.stamp_and_write(target, rec)
    _snapshot_round(plan_dir, target, args.rounds_run)
    print(str(target))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
