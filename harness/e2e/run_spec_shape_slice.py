#!/usr/bin/env python3
"""run_spec_shape_slice.py — end-to-end dogfood: PO(hs:spec) -> BA(hs:shape) ->
roadmap -> experiment -> POC gate -> plan-intake, all driven by REAL scripts run
as REAL subprocesses (argv flags, real stdout/stderr, real files on disk) --
no import cheating anywhere in this file.

Every script under test already takes `--root <workspace>` as a CLI argument,
so this slice runs the scripts straight from their real repo location (no
copytree of harness/plugins/hs/skills/ needed the way run_vertical_slice.py
copies harness/hooks/ -- those are stdin-JSON transport hooks with no --root
flag). All writes land under a tempfile.mkdtemp() workspace; nothing here
touches the real repo's docs/product/ or plans/.

Scenario:
  1. spec init (generate_templates.py) builds a minimal valid graph, EXCEPT
     the first story is authored with no acceptance_criteria (the CLI's own
     default-empty-list behavior -- not a hand-crafted defect). strict_gate.py
     BLOCKS (exit 2, missing_ac). Regenerate the same story --force with
     acceptance_criteria -> strict_gate.py PASSES (exit 0).
  2. shape: task_model.py authors dev tasks whose `serves` field covers all
     three PO<->BA cardinalities (1-1, 1-n, n-1); serves_resolver.py resolves
     each correctly.
  3. roadmap_rollup.py rolls the authored tasks into one milestone; its
     effort_rollup is the sum of each task's estimate.
  4. experiment_spec.py authors a market-experiment spec; experiment_verdict.py
     applies its own decision_rule to a PO-supplied actual, deterministically.
  5. poc_gate.py reads a review-decision (+ verification) artifact and closes a
     technical-POC sidecar; loop_handoff.py renders a plan-intake brief
     (markdown) from the committed BA tasks -- never a plan-graph.yaml.
  6. dec_ledger.py allocates two DECs in the per-workspace ledger; both unique.
  7. Regression: every PO story file's bytes are unchanged after every BA
     (shape) write in steps 2-6 -- the BA sidecar never mutates PO source.

Appends a run summary to harness/e2e/RUN-LOG.md (gitignored).

Usage: python3 harness/e2e/run_spec_shape_slice.py
"""

import json
import shutil
import subprocess
import sys
import tempfile
from datetime import datetime, timezone
from pathlib import Path

_E2E = Path(__file__).resolve().parent
_HARNESS = _E2E.parent
_SPEC_SCRIPTS = _HARNESS / "plugins" / "hs" / "skills" / "spec" / "scripts"
_SHAPE_SCRIPTS = _HARNESS / "plugins" / "hs" / "skills" / "shape" / "scripts"

_PASSED = []
_FAILED = []


def _check(name: str, ok: bool, detail: str = "") -> None:
    (_PASSED if ok else _FAILED).append((name, detail))
    print("  %s %s%s" % ("✓" if ok else "✗", name,
                         (" — " + detail) if (detail and not ok) else ""))


def _run(script: Path, *args) -> subprocess.CompletedProcess:
    return subprocess.run([sys.executable, str(script), *args],
                          capture_output=True, text=True)


def _write_values(vals_dir: Path, name: str, payload: dict) -> Path:
    p = vals_dir / (name + ".json")
    p.write_text(json.dumps(payload), encoding="utf-8")
    return p


def _generate(spec_root: Path, vals_dir: Path, name: str, artifact_type: str,
             payload: dict, extra_args=(), force=False):
    values_path = _write_values(vals_dir, name, payload)
    args = ["--root", str(spec_root), "--type", artifact_type, "--write",
            "--values", str(values_path), *extra_args]
    if force:
        args.append("--force")
    proc = _run(_SPEC_SCRIPTS / "generate_templates.py", *args)
    try:
        response = json.loads(proc.stdout)
    except json.JSONDecodeError:
        response = {}
    return proc, response


def _snapshot_story_bytes(spec_root: Path) -> dict:
    stories_dir = spec_root / "docs" / "product" / "stories"
    return {p.name: p.read_bytes() for p in sorted(stories_dir.glob("*.md"))}


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="harness-spec-shape-e2e-"))
    print("spec+shape e2e slice in %s (real subprocess CLIs, no import "
          "cheating)" % tmp)
    try:
        ws = tmp / "ws"
        vals = tmp / "values"
        vals.mkdir(parents=True)
        strict_gate = _SPEC_SCRIPTS / "strict_gate.py"

        # ------------------------------------------------------------------
        # 1. spec init + strict_gate block-then-pass
        # ------------------------------------------------------------------
        proc, resp = _generate(ws, vals, "product", "product", {
            "name": "Acme Shop",
            "one_line_description": "A web storefront for boutique fashion brands.",
            "current_implementation": "early prototype",
            "deployment": "Vercel + Supabase",
            "roadmap_one_liner": "Launch checkout flow this quarter.",
            "core_value": "Help boutique brands sell directly to fans without middlemen.",
            "personas": ["shopper", "store-admin"],
        })
        _check("generate_templates writes PRODUCT.md",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        proc, resp = _generate(ws, vals, "vision", "vision", {
            "personas": ["shopper", "store-admin"], "name": "Acme Shop"})
        _check("generate_templates writes vision.md",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        proc, resp = _generate(ws, vals, "brd", "brd", {
            "goals": [{"id": "BRD-G1", "title": "Reach $1M ARR in 12 months",
                       "metrics": ["arr"], "status": "draft", "owner": "Jane Doe"}]})
        _check("generate_templates writes brd.md",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        proc, resp = _generate(ws, vals, "prd", "prd", {
            "brd_goals": ["BRD-G1"], "personas": ["shopper"], "scope": "in",
            "moscow": "must", "horizon": "now", "metrics": ["signup-conversion"],
            "risks": [], "competitive_parity": {}}, extra_args=["--slug", "auth"])
        _check("generate_templates writes prds/auth.md (PRD-AUTH)",
               proc.returncode == 0 and resp.get("id") == "PRD-AUTH"
               and resp.get("written") is True, proc.stderr[:200])

        proc, resp = _generate(ws, vals, "epic", "epic", {
            "brd_goals": ["BRD-G1"], "personas": ["shopper"], "scope": "in",
            "moscow": "must", "horizon": "now", "metrics": [], "risks": []},
            extra_args=["--parent", "PRD-AUTH"])
        _check("generate_templates writes epics/PRD-AUTH-E1.md",
               proc.returncode == 0 and resp.get("id") == "PRD-AUTH-E1"
               and resp.get("written") is True, proc.stderr[:200])

        # The first story is authored with NO acceptance_criteria -- the CLI's
        # own default-empty-list behavior (LIST_FIELDS defaults to []), not a
        # hand-injected defect.
        proc, resp = _generate(ws, vals, "story_s1_no_ac", "story", {
            "personas": ["shopper"], "scope": "in", "moscow": "must", "size": "S",
            "horizon": "now", "metrics": [], "title": "Sign-In"},
            extra_args=["--parent", "PRD-AUTH-E1"])
        story1_id = resp.get("id")
        _check("generate_templates writes story with no acceptance_criteria (ADVISORY input)",
               proc.returncode == 0 and story1_id == "PRD-AUTH-E1-S1"
               and resp.get("written") is True, proc.stderr[:200])

        gate_proc = _run(strict_gate, "--root", str(ws))
        _check("strict_gate BLOCKS on missing_ac (exit 2)",
               gate_proc.returncode == 2 and "missing_ac" in gate_proc.stderr,
               "rc=%s stderr=%s" % (gate_proc.returncode, gate_proc.stderr[:300]))

        proc, resp = _generate(ws, vals, "story_s1_with_ac", "story", {
            "personas": ["shopper"], "scope": "in", "moscow": "must", "size": "S",
            "horizon": "now", "metrics": [], "title": "Sign-In",
            "acceptance_criteria": [
                "Given a registered user, when they enter correct credentials, "
                "then they reach the home page."]},
            extra_args=["--id", story1_id], force=True)
        _check("generate_templates rewrites S1 with acceptance_criteria (--force --id)",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        gate_proc2 = _run(strict_gate, "--root", str(ws))
        _check("strict_gate PASSES after adding acceptance_criteria (exit 0)",
               gate_proc2.returncode == 0, gate_proc2.stderr[:300])

        # Two more stories under the same epic -- fodder for the n-1 serves
        # cardinality below (a task serving two distinct stories).
        proc, resp = _generate(ws, vals, "story_s2", "story", {
            "personas": ["shopper"], "scope": "in", "moscow": "must", "size": "S",
            "horizon": "now", "metrics": [], "title": "Sign-Up",
            "acceptance_criteria": [
                "Given a new user, when they submit valid details, then an "
                "account is created."]}, extra_args=["--parent", "PRD-AUTH-E1"])
        story2_id = resp.get("id")
        _check("generate_templates writes story S2",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        proc, resp = _generate(ws, vals, "story_s3", "story", {
            "personas": ["shopper"], "scope": "in", "moscow": "must", "size": "S",
            "horizon": "now", "metrics": [], "title": "Cart Sync",
            "acceptance_criteria": [
                "Given items in a cart, when a user logs in, then the cart merges."]},
            extra_args=["--parent", "PRD-AUTH-E1"])
        story3_id = resp.get("id")
        _check("generate_templates writes story S3",
               proc.returncode == 0 and resp.get("written") is True, proc.stderr[:200])

        story_bytes_before = _snapshot_story_bytes(ws)
        _check("3 PO stories exist before any BA (shape) write",
               len(story_bytes_before) == 3, str(sorted(story_bytes_before)))

        # ------------------------------------------------------------------
        # 2. shape: serves 1-1 / 1-n / n-1
        # ------------------------------------------------------------------
        task_model = _SHAPE_SCRIPTS / "task_model.py"

        def _add_task(serves: str, title: str,
                      estimate: str) -> "tuple[str, subprocess.CompletedProcess]":
            proc = _run(task_model, "--root", str(ws), "--add",
                       "--serves", serves, "--title", title, "--estimate", estimate)
            return proc.stdout.strip(), proc

        # 1-1: story3 served by exactly one task.
        t1_id, proc = _add_task(story3_id, "Cart-sync 1-1 task", "2d")
        _check("task_model authors TASK (1-1 serves)", proc.returncode == 0 and t1_id == "TASK-1",
               proc.stderr[:200])
        # 1-n: story1 served by two tasks.
        t2_id, proc = _add_task(story1_id, "Sign-in FE task", "1d")
        _check("task_model authors TASK (1-n serves, first of two)",
               proc.returncode == 0 and t2_id == "TASK-2", proc.stderr[:200])
        t3_id, proc = _add_task(story1_id, "Sign-in BE task", "1d")
        _check("task_model authors TASK (1-n serves, second of two)",
               proc.returncode == 0 and t3_id == "TASK-3", proc.stderr[:200])
        # n-1: one task serving two distinct stories.
        t4_id, proc = _add_task("%s,%s" % (story1_id, story2_id),
                                "Shared auth migration task", "3d")
        _check("task_model authors TASK (n-1 serves, two stories)",
               proc.returncode == 0 and t4_id == "TASK-4", proc.stderr[:200])

        resolve_proc = _run(_SHAPE_SCRIPTS / "serves_resolver.py", "--root", str(ws))
        try:
            resolved = json.loads(resolve_proc.stdout)
        except json.JSONDecodeError:
            resolved = {}
        _check("serves_resolver runs clean (exit 0, no dangling ids)",
               resolve_proc.returncode == 0 and resolved.get("dangling") == {},
               resolve_proc.stderr[:200])
        _check("serves 1-1 resolves",
               resolved.get("story_to_tasks", {}).get(story3_id) == [t1_id]
               and resolved.get("task_to_stories", {}).get(t1_id) == [story3_id],
               json.dumps(resolved.get("story_to_tasks", {})))
        _check("serves 1-n resolves",
               resolved.get("story_to_tasks", {}).get(story1_id) == [t2_id, t3_id, t4_id],
               json.dumps(resolved.get("story_to_tasks", {})))
        _check("serves n-1 resolves",
               resolved.get("task_to_stories", {}).get(t4_id) == [story1_id, story2_id],
               json.dumps(resolved.get("task_to_stories", {})))

        # ------------------------------------------------------------------
        # 3. roadmap rollup
        # ------------------------------------------------------------------
        roadmap_rollup = _SHAPE_SCRIPTS / "roadmap_rollup.py"
        rr_proc = _run(roadmap_rollup, "--root", str(ws), "--add-milestone",
                       "--id", "MS-1", "--title", "Sign-in launch",
                       "--task-ids", ",".join([t1_id, t2_id, t3_id, t4_id]))
        # estimates: 2d + 1d + 1d + 3d = 7d
        _check("roadmap_rollup writes MS-1 (exit 0)", rr_proc.returncode == 0, rr_proc.stderr[:200])
        _check("roadmap effort_rollup == sum",
               rr_proc.stdout.strip() == "MS-1\t7d\tadvisory", rr_proc.stdout.strip())
        roadmap_path = ws / "docs" / "product" / "shape" / "roadmap.md"
        _check("roadmap.md written under shape/", roadmap_path.is_file())

        # ------------------------------------------------------------------
        # 4. experiment author + verdict
        # ------------------------------------------------------------------
        experiment_spec = _SHAPE_SCRIPTS / "experiment_spec.py"
        experiment_verdict = _SHAPE_SCRIPTS / "experiment_verdict.py"
        es_proc = _run(experiment_spec, "--root", str(ws), "--add",
                       "--hypothesis", "A shorter signup form increases conversion.",
                       "--linked-to", "BRD-G1", "--method", "A/B",
                       "--control", "long form", "--variant", "short form",
                       "--metric", "signup-conversion", "--direction", "higher",
                       "--target", "10", "--hit-floor", "0.9", "--partial-floor", "0.5",
                       "--title", "Signup form length")
        exp_id = es_proc.stdout.strip()
        _check("experiment_spec authors EXP-1", es_proc.returncode == 0 and exp_id == "EXP-1",
               es_proc.stderr[:200])

        ev_proc = _run(experiment_verdict, "--root", str(ws), "--id", exp_id, "--actual", "9.5")
        # direction=higher, target=10, actual=9.5 -> ratio 0.95 >= hit_floor(0.9) -> hit
        _check("experiment verdict is deterministic",
               ev_proc.returncode == 0 and ev_proc.stdout.strip() == "EXP-1\thit\tconcluded",
               "rc=%s out=%r err=%s" % (ev_proc.returncode, ev_proc.stdout, ev_proc.stderr[:200]))

        # ------------------------------------------------------------------
        # 5. POC gate + plan-intake handoff
        # ------------------------------------------------------------------
        poc_gate = _SHAPE_SCRIPTS / "poc_gate.py"
        loop_handoff = _SHAPE_SCRIPTS / "loop_handoff.py"
        poc_add_proc = _run(poc_gate, "--root", str(ws), "--add",
                            "--subject", "Checkout latency feasibility",
                            "--title", "Checkout POC")
        poc_id = poc_add_proc.stdout.strip()
        _check("poc_gate authors POC-1", poc_add_proc.returncode == 0 and poc_id == "POC-1",
               poc_add_proc.stderr[:200])

        review_path = ws / "artifacts" / "review-decision.json"
        verification_path = ws / "artifacts" / "verification.json"
        review_path.parent.mkdir(parents=True, exist_ok=True)
        review_path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")
        verification_path.write_text(json.dumps({"verdict": "PASS"}), encoding="utf-8")

        poc_gate_proc = _run(poc_gate, "--root", str(ws), "--gate", "--id", poc_id,
                             "--review-decision", str(review_path),
                             "--verification", str(verification_path))
        _check("POC gate closes on PASS+PASS",
               poc_gate_proc.returncode == 0
               and poc_gate_proc.stdout.strip() == "POC-1\tPASS\tclosed",
               "rc=%s out=%r err=%s" % (poc_gate_proc.returncode, poc_gate_proc.stdout,
                                        poc_gate_proc.stderr[:200]))

        handoff_proc = _run(loop_handoff, "--root", str(ws), "--poc", poc_id)
        brief_path_str = handoff_proc.stdout.strip()
        brief_path = Path(brief_path_str) if brief_path_str else None
        _check("loop_handoff renders a plan-intake brief (exit 0)",
               handoff_proc.returncode == 0 and brief_path is not None and brief_path.is_file(),
               handoff_proc.stderr[:200])
        brief_text = brief_path.read_text(encoding="utf-8") if brief_path and brief_path.is_file() else ""
        _check("plan-intake brief is markdown, not plan-graph.yaml",
               brief_path is not None
               and brief_path.name != "plan-graph.yaml"
               and brief_path.suffix == ".md"
               and "# Plan intake brief" in brief_text
               and "poc: POC-1" in brief_text,
               "path=%s" % brief_path_str)

        # ------------------------------------------------------------------
        # 6. dec_ledger allocates 2 unique DECs
        # ------------------------------------------------------------------
        dec_ledger = _SPEC_SCRIPTS / "dec_ledger.py"
        dec1_proc = _run(dec_ledger, "--root", str(ws), "--add",
                         "--title", "Adopt A/B testing for the signup form")
        dec2_proc = _run(dec_ledger, "--root", str(ws), "--add",
                         "--title", "Gate roadmap milestones on POC closure")
        dec1 = dec1_proc.stdout.strip()
        dec2 = dec2_proc.stdout.strip()
        _check("dec_ledger allocates 2 unique DECs",
               dec1_proc.returncode == 0 and dec2_proc.returncode == 0
               and dec1 and dec2 and dec1 != dec2,
               "dec1=%r dec2=%r" % (dec1, dec2))

        # ------------------------------------------------------------------
        # 7. PO story immutability: bytes unchanged after every BA write above
        # ------------------------------------------------------------------
        story_bytes_after = _snapshot_story_bytes(ws)
        _check("PO stories byte-unchanged after every shape op",
               story_bytes_after == story_bytes_before,
               "before=%s after=%s" % (sorted(story_bytes_before), sorted(story_bytes_after)))

    finally:
        shutil.rmtree(tmp, ignore_errors=True)

    ok = not _FAILED
    summary = "%s | %d passed, %d failed | transport=real-subprocess-cli" % (
        datetime.now(timezone.utc).isoformat(), len(_PASSED), len(_FAILED))
    print("\nspec+shape e2e:", summary)
    try:
        with open(_E2E / "RUN-LOG.md", "a", encoding="utf-8") as fh:
            fh.write("- %s\n" % summary)
            for name, detail in _FAILED:
                fh.write("  - FAILED: %s — %s\n" % (name, detail))
    except OSError:
        pass
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
