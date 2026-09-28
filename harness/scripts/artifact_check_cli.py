#!/usr/bin/env python3
"""artifact_check_cli.py — the remote receipts-gate's CLI wrapper around check_stage.

Judges ONE plan dir at one stage grade. `--plan-dir` feeds check_stage's plan_dir seam
directly (bypasses the global newest-in_progress resolver — PR-agnostic, red-team H3;
HARNESS_ACTIVE_PLAN is scrubbed on CI anyway). Presence + verdict only — DoD
(_evaluate_dod) is NOT run here (advisory-only on CI in v1; hard-DoD is a BACKLOG item).

Exit 2 + an actionable reason on stderr when a receipt is missing/invalid; exit 0 + a
`{"stage","plan","result":"PASS"}` JSON line on stdout otherwise. Runs on a runner with
NO harness install — checkout + pyyaml is enough (it reads files directly)."""
from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description="Judge one plan dir's receipts at a stage")
    ap.add_argument("--stage", required=True,
                    help="grade to judge at (pr | merge | ship | deploy)")
    ap.add_argument("--plan-dir", required=True,
                    help="the plan dir to judge (bypasses the active-plan resolver)")
    ap.add_argument("--root", default=None, help="repo root (default: resolved)")
    a = ap.parse_args(argv)

    import artifact_check
    import harness_paths

    root = a.root or str(harness_paths.root())
    plan_dir = Path(a.plan_dir)
    if not (plan_dir / "plan.md").is_file():
        sys.stderr.write(
            "receipts-gate: no plan.md in %s — pass a plan dir under plans/\n" % plan_dir)
        return 2

    # check_stage returns None for BOTH "hard stage, judged, clean" and "stage is
    # soft/unrecognized, never judged" (its documented contract, artifact_check.py:
    # 1125 — the gate is behaving to spec). Collapsing those two into one
    # affirmative `result: PASS` is the CLI's own bug: an unrecognized --stage
    # token (a typo, a renamed stage, an unset CI variable landing as "") must
    # never render a clean receipt. Distinguish the three outcomes up front.
    try:
        stages = artifact_check.load_policy().get("stages") or {}
    except Exception as e:  # noqa: BLE001 — a crashed policy load must name itself
        sys.stderr.write("receipts-gate: cannot load stage policy: %s\n" % e)
        return 2
    stage_cfg = stages.get(a.stage)
    if not isinstance(stage_cfg, dict):
        sys.stderr.write(
            "receipts-gate: unknown stage %r — known stages: %s\n"
            % (a.stage, ", ".join(sorted(stages))))
        return 2

    try:
        reason = artifact_check.check_stage(a.stage, root, plan_dir=plan_dir)
    except Exception as e:  # noqa: BLE001 — a CLI crash must name itself, not hang the job
        sys.stderr.write("receipts-gate: check crashed for %s: %s\n" % (plan_dir.name, e))
        return 2
    if reason:
        sys.stderr.write(
            "receipts-gate BLOCK [stage=%s plan=%s]: %s\n" % (a.stage, plan_dir.name, reason))
        return 2
    if not stage_cfg.get("hard"):
        # A real, known stage — but not hard here, so nothing was actually
        # judged. Never render that as PASS (the judgment a caller would read
        # as "receipts verified").
        print(json.dumps({"stage": a.stage, "plan": plan_dir.name, "result": "SKIP"},
                         ensure_ascii=False))
        return 0
    print(json.dumps({"stage": a.stage, "plan": plan_dir.name, "result": "PASS"},
                     ensure_ascii=False))
    return 0


if __name__ == "__main__":
    sys.exit(main())
