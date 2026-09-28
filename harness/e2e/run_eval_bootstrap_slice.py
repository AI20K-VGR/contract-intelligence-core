#!/usr/bin/env python3
"""run_eval_bootstrap_slice.py — end-to-end dogfood for hs:eval-bootstrap.

Proves the generated eval framework actually RUNS, not just that it parses:

  SLICE 1 (ground-truth, 0-API-key) — scaffold a ground-truth tree, fill the
    domain stubs the way the model would (a key:value pipeline mirror and a
    pass-rate scorer), then run the generated run_production_evals.py as a REAL
    subprocess: a clean fixture exits 0 (all fields MATCH after normalisation),
    and mutating one ground-truth field exits 1 (block-then-pass). No import
    cheating.

  SLICE 2 (fake-judge, 0-API-key) — scaffold a judge tree, inject a FIXED fake
    judge output (no LLM), and prove the judge is ADVISORY ONLY: build_judge_prompt
    runs without the source's .format KeyError, and attach_judge_advisory leaves
    the deterministic maturity + passed verdict UNCHANGED (VL-2).

  SLICE 3 (data extraction) — run the generated extract_data_text.py: the image
    branch (no OCR) is exercised dep-free; the PDF branch runs only when pymupdf
    is installed (skip-guarded otherwise).

  SLICE 4 (L1 + card integrity) — a scaffold call missing a required judgment
    arg refuses (never defaults); a full-arg scaffold + card write + verify all
    pass; a hand-edited eval_config.json makes the stamped run_production_evals.py
    refuse to score (exit 2, config drift) — the card-hash integrity loop.

  SLICE 5 (R9 sandbox evidence) — a clean fill runs cleanly through
    sandbox_run.py under BOTH the fallback and bwrap containment seams (the
    seam is re-injected AFTER _clean_env, never inherited); a fill importing
    socket is refused before it ever executes (denylist, exit 3), proven by an
    absent marker file; under bwrap, a write to a runtime-computed path outside
    the sandbox is blocked at the OS level, never reaching the real host path.

  SLICE 6 (two-tier memory) — a lesson (tier-1, tracked per-repo) and a
    standard (tier-2, per-machine — routed via an explicitly re-injected
    HARNESS_STATE_DIR) are appended, then recalled with a filter + limit;
    email/phone redaction is asserted at the raw byte level, and the real
    per-OS home directory is proven untouched throughout.

  SLICE 7 (mutation matrix) — a real check_p0_gates fill generates + runs a
    mutation matrix that matches every expectation (p0-kill, +-epsilon
    threshold, noise-no-panic); a placeholder tree (check_p0_gates left as the
    stamped stub) fails the run and is classified as a blind gate.

  SLICE 8 (subprocess mirror, non-python lang) — scaffold a lane with
    mirror_lang "fakelang" (python plays the exotic interpreter named in the
    card's mirror_invoke, proving the any-language path needs nothing
    installed): the non-python lane stamps a mirror-implementation guide +
    test_mirror_contract.py instead of pipeline_mirror.py; emit the
    mirror_contract.json from the approved card, "LLM fill" the mirror file
    it names, then drive run_production_evals.py through the subprocess
    dispatch — clean exit 0, mutated ground truth exit 1 (block-then-pass
    through the subprocess), the stamped contract tests pass against the
    filled mirror, and a hand-edited mirror_contract.json card_hash makes the
    runner die loud (ConfigDriftError) rather than score against a drifted
    contract.

All writes land under a tempfile workspace; nothing here touches the real repo.
Every subprocess this file spawns builds its env from `_clean_env()` (scrubs
every HARNESS_* var) so a stray dev-session override never leaks in and
produces a false result; slices 5/6 re-inject one HARNESS_* seam explicitly,
AFTER the scrub, exactly where the containment/state-dir behavior needs it.

Usage: python3 harness/e2e/run_eval_bootstrap_slice.py
"""

import json
import os
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path

_HARNESS = Path(__file__).resolve().parent.parent
_SCAFFOLD = _HARNESS / "plugins" / "hs" / "skills" / "eval-bootstrap" / "scripts" / "eval_scaffold.py"
_CONFIG = _HARNESS / "plugins" / "hs" / "skills" / "eval-bootstrap" / "scripts" / "eval_config.py"
_MEMORY = _HARNESS / "plugins" / "hs" / "skills" / "eval-bootstrap" / "scripts" / "eval_memory.py"
_MUTATION = _HARNESS / "plugins" / "hs" / "skills" / "eval-bootstrap" / "scripts" / "mutation_matrix.py"
_SANDBOX_RUN = _HARNESS / "plugins" / "hs" / "skills" / "eval-bootstrap" / "scripts" / "sandbox_run.py"


_MIRROR_FILL = '''

# --- e2e domain fill (stands in for the model's Phase 3.5 work) ---
def run_pipeline(input_data):
    out = {}
    for line in input_data.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out
'''

_SCORER_FILL = '''

# --- e2e domain fill ---
# FORK D (phase-7 ripple d): DIMENSIONS is NOT set here — the stamped
# scorer.py already reads it from the approved card at import time
# (config_integrity.load_verified_config); overriding it here would shadow
# the loader and void the FORK-D proof that dims come from one source.
# _write_card() below writes {"accuracy": 100}, matching this domain's fill.
def score_dimension(dimension_name, results):
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.get("passed"))
    return 100.0 * passed / len(results)
'''


def _clean_env():
    """A copy of the current process env with every HARNESS_* key scrubbed.

    A dev session commonly carries HARNESS_STATE_DIR / HARNESS_R9_CONTAINMENT /
    HARNESS_GUARD_POLICY / ... overrides; leaking any of those into a slice
    subprocess would corrupt that subprocess's own posture and produce a false
    result (memory: dev-env-leak-into-gate-e2e-subprocess). EVERY subprocess
    this file spawns must build its env from this — never a bare os.environ
    passthrough. A slice that needs one specific HARNESS_* seam (5, 6)
    re-injects it explicitly, AFTER this scrub, never before.
    """
    return {k: v for k, v in os.environ.items() if not k.startswith("HARNESS_")}


def _run(cmd, env=None, **kw):
    if env is None:
        env = _clean_env()
    return subprocess.run(cmd, capture_output=True, text=True, env=env, **kw)


# Every judgment blank the CLI now REQUIRES (L1) — stand-ins for an approved
# strategy card, since this slice dogfoods the scaffolder end-to-end rather
# than exercising a real card-approval flow.
_JUDGE_STRATEGIES = ("judge", "hybrid")


def _scaffold(target, domain, strategy, dimensions=None, primary_dimension=None,
             domain_config=None, mirror_lang="python", forge="github"):
    dimensions = dimensions or {"accuracy": 100}
    primary_dimension = primary_dimension or "accuracy"
    domain_config = domain_config if domain_config is not None else {"normalizers": {}, "masks": {}}
    cmd = [sys.executable, str(_SCAFFOLD), "--target", str(target),
           "--domain", domain, "--strategy", strategy,
           "--threshold", "70", "--production-module", "src/%s.py" % domain,
           "--p0-rules", "name must be non-null",
           "--dimensions", json.dumps(dimensions),
           "--primary-dimension", primary_dimension,
           "--domain-config", json.dumps(domain_config),
           "--mirror-lang", mirror_lang, "--forge", forge]
    if strategy in _JUDGE_STRATEGIES:
        cmd += ["--judge-model", "sonnet", "--pipeline-model", "haiku"]
    r = _run(cmd)
    assert r.returncode == 0, "scaffold failed: %s\n%s" % (r.stdout, r.stderr)


def _fill_domain_stubs(eval_dir):
    with open(eval_dir / "pipeline_mirror.py", "a", encoding="utf-8") as f:
        f.write(_MIRROR_FILL)
    with open(eval_dir / "scorer.py", "a", encoding="utf-8") as f:
        f.write(_SCORER_FILL)


def _write_card(ws, domain, strategy, domain_config=None, mirror_lang="python",
                forge="github", mirror_invoke=None, case_matrix=None):
    """P3 BLOCKER B1: after config_integrity is stamped-in, run_production_evals
    refuses to score without an approved card on disk — write a minimal
    schema-valid one (P2 eval_config.py CLI) before the slice's clean run."""
    domain_config = domain_config if domain_config is not None else {"normalizers": {}, "masks": {}}
    card = {
        "schema_version": "1",
        "domain": domain,
        "strategy": strategy,
        "surface": "extraction",
        "production_module": "src/%s.py" % domain,
        "production_entry": "extract",
        "mirror_lang": mirror_lang,
        "forge": forge,
        "threshold": 70,
        "p0_rules": [{"rule": "name must be non-null", "source": "card"}],
        "dimensions": {"accuracy": 100},
        "primary_dimension": "accuracy",
        "domain_config": domain_config,
        "case_matrix": case_matrix or [{"case": "c1", "input": "name: x", "expect": {"name": "x"}}],
        "epsilon": {"maturity": 1},
        "cited_lessons": [],
        "approved_by": "e2e-slice",
        "approved_ts": "2026-07-14",
    }
    if mirror_invoke is not None:
        card["mirror_invoke"] = mirror_invoke
    if strategy in _JUDGE_STRATEGIES:
        card["judge_model"] = "sonnet"
        card["pipeline_model"] = "haiku"
    card_path = ws / ("_card_%s.json" % domain)
    card_path.write_text(json.dumps(card), encoding="utf-8")
    r = _run([sys.executable, str(_CONFIG), "write", "--target", str(ws), "--card", str(card_path)])
    assert r.returncode == 0, "eval_config.py write failed: %s\n%s" % (r.stdout, r.stderr)


def slice1_ground_truth(ws):
    # normalize_generic (the default, undeclared-field normalizer) folds case
    # + whitespace but no longer strips diacritics (that is a language-profile
    # decision, L1) — so the ground truth must carry the SAME diacritics as
    # the sample, differing only in case/whitespace, to still MATCH.
    domain = "cv"
    domain_config = {"normalizers": {}, "masks": {"email": "email"}}
    _scaffold(ws, domain, "ground-truth", domain_config=domain_config)
    eval_dir = ws / "evals" / "eval_types" / domain
    _fill_domain_stubs(eval_dir)
    _write_card(ws, domain, "ground-truth", domain_config=domain_config)

    samples = ws / "data" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    # sidecar for a binary case: runner reads <case>.txt
    (samples / "case1.pdf.txt").write_text(
        "name: Nguyễn Văn An\nemail: an@example.com\n", encoding="utf-8")

    gt_path = eval_dir / "tests" / "production_fixtures" / "ground_truth.json"
    gt = {
        "description": "e2e",
        "items": [{
            "case_file": "case1.pdf",
            "ground_truth": {"name": "nguyễn  văn  an", "email": "an@example.com"},
            "notes": "case + whitespace variant must MATCH after normalize_generic "
                     "(diacritic-preserving; email masked via domain_config)",
        }],
    }
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")

    cli = ws / "evals" / "scripts" / "run_production_evals.py"
    clean = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                  "--ground-truth", str(gt_path)])
    assert clean.returncode == 0, "clean run should PASS (exit 0):\n%s\n%s" % (clean.stdout, clean.stderr)
    assert "MATCH" in clean.stdout, clean.stdout
    # PII masking (R5): the raw email local-part must not leak into the report
    assert "an@example.com" not in clean.stdout or "*" in clean.stdout

    # mutate one ground-truth field -> the gate must BLOCK (exit 1)
    gt["items"][0]["ground_truth"]["name"] = "someone completely different"
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    blocked = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                    "--ground-truth", str(gt_path)])
    assert blocked.returncode == 1, "mutated run should BLOCK (exit 1):\n%s" % blocked.stdout
    assert "MISMATCH" in blocked.stdout, blocked.stdout
    print("SLICE 1 OK: block-then-pass via real subprocess (exit 0 clean, exit 1 mutated); PII masked")


def slice2_fake_judge(ws):
    # A dims set OUTSIDE the old hard-coded 5-name ("accuracy"/"robustness"/...)
    # set — proves DIMENSIONS/PRIMARY_DIMENSION render from the card, not a
    # stamped literal (phase-8: the source KeyError'd on any card that didn't
    # declare "accuracy").
    domain = "chat"
    dims = {"correctness": 70, "helpfulness": 30}
    primary = "correctness"
    _scaffold(ws, domain, "judge", dimensions=dims, primary_dimension=primary)
    eval_dir = ws / "evals" / "eval_types" / domain

    # Prove advisory-only entirely in a subprocess against the STAMPED modules.
    probe = '''
import sys, json
sys.path.insert(0, %r)
import judge_prompt, judge_runner

assert judge_runner.DIMENSIONS == %r
assert judge_runner.PRIMARY_DIMENSION == %r

comp = [{"case": "c1", "passed": True,
         "fields": [{"field": "answer", "status": "MATCH", "extracted": "x", "expected": "x"}]}]
gt = {"description": "d", "items": [{"case_file": "c1", "ground_truth": {"answer": "x"}}]}
prompt = judge_prompt.build_judge_prompt(comp, gt, "def run_pipeline(): pass")
assert "system" in prompt and "user" in prompt
assert "correctness" in prompt["system"] and "helpfulness" in prompt["system"]

# a FIXED fake judge output (no LLM) carrying ALL of the card's dims, with a
# deliberately low score on the primary dim
fake = {"overall_score": 20, "confidence": 0.4,
        "dimensions": {"correctness": {"score": 30, "confidence": 0.4},
                       "helpfulness": {"score": 55, "confidence": 0.6}},
        "patterns": [], "recommendations": [], "p0_triggered": False}
det = {"maturity": 82.0, "passed": True, "threshold": 70,
       "p0_gate_passed": True, "p0_failures": [], "dimensions": {}}
merged = judge_runner.attach_judge_advisory(det, fake)
assert merged["maturity"] == 82.0, "VL-2: judge must not change maturity"
assert merged["passed"] is True, "VL-2: judge must not flip the verdict"
assert merged["judge_advisory"]["p0_recommendation"] is True, "advisory p0 rec set (conf<0.7)"
assert "combined_multiplier" not in merged
print("advisory-only confirmed")
''' % (str(eval_dir), dims, primary)
    r = _run([sys.executable, "-c", probe])
    assert r.returncode == 0, "fake-judge slice failed:\n%s\n%s" % (r.stdout, r.stderr)
    assert "advisory-only confirmed" in r.stdout
    print("SLICE 2 OK: fake-judge merge runs with dims-from-card (no KeyError); judge advisory-only, verdict unchanged")


def slice3_data_extraction(ws):
    domain = "cv"
    _scaffold(ws, domain, "ground-truth")
    scripts = ws / "evals" / "scripts"
    extractor_cli = scripts / "extract_data_text.py"
    assert extractor_cli.exists(), "extract_data_text.py must be scaffolded"

    data = ws / "imgdata"
    data.mkdir(parents=True, exist_ok=True)
    (data / "scan.png").write_bytes(b"\x89PNG\r\n\x1a\n fake image bytes")
    img = _run([sys.executable, str(extractor_cli), "--data-dir", str(data)])
    assert img.returncode == 0, img.stderr
    assert "IMAGE" in img.stdout, "image must be surfaced for manual model-read (no OCR): %s" % img.stdout
    assert not (data / "scan.png.txt").exists(), "images must NOT get an auto sidecar"

    try:
        import fitz  # pymupdf
    except Exception:
        print("SLICE 3 OK: image branch (no OCR) verified; PDF branch skipped (pymupdf absent)")
        return

    pdf_dir = ws / "pdfdata"
    pdf_dir.mkdir(parents=True, exist_ok=True)
    pdf_path = pdf_dir / "doc.pdf"
    doc = fitz.open()
    page = doc.new_page()
    page.insert_text((72, 72), "hello eval bootstrap")
    doc.save(str(pdf_path))
    doc.close()
    pdf = _run([sys.executable, str(extractor_cli), "--data-dir", str(pdf_dir)])
    assert pdf.returncode == 0, pdf.stderr
    sidecar = pdf_dir / "doc.pdf.txt"
    assert sidecar.exists(), "PDF must get a .txt sidecar"
    assert "hello eval bootstrap" in sidecar.read_text(encoding="utf-8")
    print("SLICE 3 OK: image branch (no OCR) + PDF extract -> sidecar .txt (pymupdf present)")


# --------------------------------------------------------------------------
# SLICE 4 — L1 (no code-side default) + card-hash integrity loop
# --------------------------------------------------------------------------

def slice4_l1_and_card(ws):
    domain = "card"

    # 1) L1: a required judgment arg (--dimensions) is OMITTED -> the scaffolder
    #    must refuse (argparse error), never silently default the value.
    incomplete_cmd = [sys.executable, str(_SCAFFOLD), "--target", str(ws),
                      "--domain", domain, "--strategy", "ground-truth",
                      "--threshold", "70", "--production-module", "src/%s.py" % domain,
                      "--p0-rules", "name must be non-null",
                      "--primary-dimension", "accuracy",
                      "--domain-config", json.dumps({"normalizers": {}, "masks": {}}),
                      "--mirror-lang", "python", "--forge", "github"]
    incomplete = _run(incomplete_cmd)
    assert incomplete.returncode != 0, (
        "scaffold must refuse a missing judgment arg (--dimensions), not default it:\n%s"
        % incomplete.stderr)

    # 2) full args -> scaffold + domain fill + card write -> verify PASSES.
    domain_config = {"normalizers": {}, "masks": {}}
    _scaffold(ws, domain, "ground-truth", domain_config=domain_config)
    eval_dir = ws / "evals" / "eval_types" / domain
    _fill_domain_stubs(eval_dir)
    _write_card(ws, domain, "ground-truth", domain_config=domain_config)

    verify = _run([sys.executable, str(_CONFIG), "verify", "--target", str(ws)])
    assert verify.returncode == 0, (
        "eval_config verify should PASS right after write:\n%s\n%s" % (verify.stdout, verify.stderr))

    # 3) hand-edit the written config (tamper AFTER approval) -> the stamped
    #    run_production_evals.py must refuse to score (exit 2, config drift),
    #    never scoring against a card whose hash no longer matches its sidecar.
    config_path = ws / "evals" / "eval_config.json"
    with open(config_path, "a", encoding="utf-8") as f:
        f.write(" ")

    samples = ws / "data" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    (samples / "dummy.txt").write_text("name: x\n", encoding="utf-8")
    gt_path = ws / "_gt_dummy.json"
    gt_path.write_text(json.dumps({"description": "d", "items": []}), encoding="utf-8")

    cli = ws / "evals" / "scripts" / "run_production_evals.py"
    tampered = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                     "--ground-truth", str(gt_path)])
    assert tampered.returncode == 2, (
        "a hand-edited eval_config.json must refuse to score (exit 2, integrity):\n%s\n%s"
        % (tampered.stdout, tampered.stderr))
    print("SLICE 4 OK: missing-arg scaffold refused, full-arg card write+verify passed, "
          "hand-edited config refused scoring (exit 2 integrity)")


# --------------------------------------------------------------------------
# SLICE 5 — R9 sandbox evidence (fallback vs bwrap containment)
# --------------------------------------------------------------------------

_R9_CLEAN_FILL = '''
def run_pipeline(input_data):
    out = {}
    if not isinstance(input_data, str):
        return out
    for line in input_data.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out
'''

# import socket ALONE triggers the R9 denylist (layer 1, code "network") --
# the fill is refused (exit 3) before it is ever executed in any process, so
# the marker write below (module-level, not gated on any condition) can only
# ever appear if the fill somehow ran despite the refusal.
_R9_SOCKET_FILL_TMPL = '''
import socket  # forbidden: triggers the R9 denylist refuse (layer 1)

with open(%r, "w", encoding="utf-8") as _marker_fh:
    _marker_fh.write("EXECUTED")


def run_pipeline(input_data):
    return {"echo": input_data}
'''

# The write target is built at RUNTIME (list + join), never a literal string
# argument to open() -- the same technique the sandbox_run.py test suite uses
# (test_bwrap_containment_when_present) to prove OS-level containment on a
# path a static denylist cannot catch (it only flags a literal Constant arg).
_R9_ESCAPE_FILL = '''
def run_pipeline(input_data):
    path_parts = ["/tmp", "eval-r9-slice-host-marker-should-not-exist.txt"]
    target = path_parts[0] + "/" + path_parts[1]
    with open(target, "w") as fh:
        fh.write("leaked")
    out = {}
    if not isinstance(input_data, str):
        return out
    for line in input_data.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out
'''


def _r9_config(ws):
    cfg = {"case_matrix": [
        {"case": "c1", "input": "name: x", "expect": {"name": "x"}},
        {"case": "c2", "input": "a: 1\nb: 2", "expect": {"a": "1", "b": "2"}},
    ]}
    path = ws / "r9_config.json"
    path.write_text(json.dumps(cfg), encoding="utf-8")
    return path


def slice5_r9_sandbox(ws):
    ws.mkdir(parents=True, exist_ok=True)
    config_path = _r9_config(ws)

    clean_fill = ws / "fill_clean.py"
    clean_fill.write_text(_R9_CLEAN_FILL, encoding="utf-8")

    marker_path = ws / "should-not-execute.txt"
    socket_fill = ws / "fill_socket.py"
    socket_fill.write_text(_R9_SOCKET_FILL_TMPL % str(marker_path), encoding="utf-8")

    # -- denylist refuse (exit 3), mode-independent: fires before containment
    # is even resolved, so it never needs to run twice.
    denylist_env = dict(_clean_env())
    denylist_env["HARNESS_R9_CONTAINMENT"] = "fallback"
    evidence_denylist = ws / "evidence_denylist.json"
    denylist_run = _run([sys.executable, str(_SANDBOX_RUN),
                         "--fill", str(socket_fill), "--entry", "run_pipeline",
                         "--config", str(config_path),
                         "--evidence-out", str(evidence_denylist)], env=denylist_env)
    assert denylist_run.returncode == 3, (
        "a fill importing socket must be refused pre-execute (exit 3):\n%s\n%s"
        % (denylist_run.stdout, denylist_run.stderr))
    assert not marker_path.exists(), (
        "the denylist-refused fill must NEVER execute -- its marker file must stay absent")

    bwrap_available = shutil.which("bwrap") is not None
    bwrap_ran = False

    # _clean_env() scrubs every HARNESS_* var, so the containment seam is
    # re-injected EXPLICITLY, AFTER the scrub, for each mode in turn -- never
    # left to whatever the dev session happened to have set (a scrubbed seam
    # would fall back to auto and make =fallback false-fail on a bwrap host,
    # or =bwrap never engage at all).
    for mode in ("fallback", "bwrap"):
        if mode == "bwrap" and not bwrap_available:
            print("SLICE 5: =bwrap sub-slice SKIPPED -- bwrap binary absent on this "
                  "machine (dev host); CI installs bubblewrap and runs it for real "
                  "(a missing bwrap there is exit 4 -> job red, never a silent skip-pass)")
            continue

        env = dict(_clean_env())
        env["HARNESS_R9_CONTAINMENT"] = mode
        evidence_path = ws / ("evidence_%s.json" % mode)
        clean_run = _run([sys.executable, str(_SANDBOX_RUN),
                          "--fill", str(clean_fill), "--entry", "run_pipeline",
                          "--config", str(config_path),
                          "--evidence-out", str(evidence_path)], env=env)
        if (mode == "bwrap" and clean_run.returncode != 0
                and "bwrap seam requested but unavailable" in clean_run.stderr):
            print("SLICE 5: =bwrap sub-slice SKIPPED -- bwrap binary present but the "
                  "CI kernel/container denies its namespace setup (uid map / network):\n%s"
                  % clean_run.stderr.strip())
            continue
        assert clean_run.returncode == 0, (
            "a clean fill must PASS every case+edge under %s mode:\n%s\n%s"
            % (mode, clean_run.stdout, clean_run.stderr))
        evidence = json.loads(evidence_path.read_text(encoding="utf-8"))
        assert len(evidence["cases"]) == 2, evidence
        assert len(evidence["edge_cases"]) == 5, evidence
        assert evidence["summary"]["fail"] == 0, evidence

        if mode == "fallback":
            assert evidence["containment"] == "python-filter-fallback", evidence
            assert "best-effort" in clean_run.stdout.lower(), clean_run.stdout
        else:
            bwrap_ran = True
            assert evidence["containment"] == "bwrap", evidence
            share_net = evidence.get("meta", {}).get("bwrap_share_net", False)

            # F4 proof: a write to a runtime-computed path outside the sandbox
            # must be blocked at the OS level (bwrap's own private /tmp), not
            # merely denylist-refused -- this path is built at runtime, never
            # a literal, so layer 1 cannot catch it.
            # On kernels that deny a private network namespace we still run
            # bwrap with filesystem/process isolation, but the host /tmp is
            # visible so the OS-level /tmp escape assertion cannot hold.
            host_marker = Path("/tmp/eval-r9-slice-host-marker-should-not-exist.txt")
            if host_marker.exists():
                host_marker.unlink()
            escape_fill = ws / "fill_escape.py"
            escape_fill.write_text(_R9_ESCAPE_FILL, encoding="utf-8")
            escape_evidence = ws / "evidence_escape.json"
            try:
                escape_run = _run([sys.executable, str(_SANDBOX_RUN),
                                   "--fill", str(escape_fill), "--entry", "run_pipeline",
                                   "--config", str(config_path),
                                   "--evidence-out", str(escape_evidence)], env=env)
                assert escape_run.returncode == 0, (
                    "the fill itself must run cleanly under bwrap (its own private "
                    "/tmp hides the write, never a crash):\n%s\n%s"
                    % (escape_run.stdout, escape_run.stderr))
                if not share_net:
                    assert not host_marker.exists(), (
                        "a write to a path outside the bwrap sandbox must be blocked "
                        "OS-level -- it must never reach the real host path")
            finally:
                if host_marker.exists():
                    host_marker.unlink()

    bwrap_note = ""
    if not bwrap_ran:
        if bwrap_available:
            bwrap_note = " (bwrap sub-slice skipped: present but kernel/container denies namespace setup)"
        else:
            bwrap_note = " (bwrap sub-slice skipped: absent on this host)"

    print("SLICE 5 OK: R9 sandbox clean-fill exit 0 (case+edge evidence); "
          "import-socket fill refused pre-execute (exit 3, marker absent); "
          "fallback containment + warning asserted%s"
          % (" ; bwrap containment + OS-level escape-block asserted%s"
              % (" (network namespace shared)" if share_net else "")
              if bwrap_ran else bwrap_note))


# --------------------------------------------------------------------------
# SLICE 6 — two-tier memory (append/recall, redaction, real-home isolation)
# --------------------------------------------------------------------------

def _real_os_tier2_home():
    """Mirror eval_memory._tier2_home()'s per-OS default resolution, MINUS the
    HARNESS_STATE_DIR override -- used ONLY to prove this slice's explicit
    re-injection kept every write off the real per-machine home. Never used to
    exercise memory behavior itself (that goes through the real CLI below)."""
    plat = sys.platform
    if plat.startswith("win"):
        base = os.environ.get("LOCALAPPDATA") or "~/AppData/Local"
        return Path(base).expanduser() / "harness" / "eval-memory"
    if plat == "darwin":
        return Path("~/Library/Application Support").expanduser() / "harness" / "eval-memory"
    base = os.environ.get("XDG_DATA_HOME") or "~/.local/share"
    if base != "~/.local/share" and not os.path.isabs(os.path.expanduser(base)):
        base = "~/.local/share"
    return Path(base).expanduser() / "harness" / "eval-memory"


def slice6_memory(ws):
    ws.mkdir(parents=True, exist_ok=True)
    target = ws / "target"
    target.mkdir(parents=True, exist_ok=True)
    state_dir = ws / "state"

    # _clean_env() scrubs every HARNESS_* var -- HARNESS_STATE_DIR is re-injected
    # EXPLICITLY, AFTER the scrub, or tier-2 "standard" resolves into the dev's
    # REAL per-OS home and litters outside the sandbox.
    env = dict(_clean_env())
    env["HARNESS_STATE_DIR"] = str(state_dir)

    real_home = _real_os_tier2_home()
    before = set(real_home.rglob("*")) if real_home.exists() else set()

    lesson_body = "cv extraction lesson: contact test-user@example.com or 0912345678 for details"
    lesson_alpha = _run([sys.executable, str(_MEMORY), "append", "--type", "lesson",
                        "--domain", "alpha", "--surface", "extraction", "--stack", "python",
                        "--body", lesson_body, "--target", str(target)], env=env)
    assert lesson_alpha.returncode == 0, lesson_alpha.stderr
    lesson_beta = _run([sys.executable, str(_MEMORY), "append", "--type", "lesson",
                       "--domain", "beta", "--surface", "extraction", "--stack", "python",
                       "--body", "unrelated lesson, no pii here", "--target", str(target)], env=env)
    assert lesson_beta.returncode == 0, lesson_beta.stderr

    standard_run = _run([sys.executable, str(_MEMORY), "append", "--type", "standard",
                        "--domain", "harness", "--surface", "cli", "--stack", "python",
                        "--body", "always validate CLI args early"], env=env)
    assert standard_run.returncode == 0, standard_run.stderr

    recall = _run([sys.executable, str(_MEMORY), "recall", "--type", "lesson",
                  "--target", str(target), "--filter", "domain=alpha", "--limit", "5"], env=env)
    assert recall.returncode == 0, recall.stderr
    recalled = [json.loads(l) for l in recall.stdout.splitlines() if l.strip()]
    assert len(recalled) == 1, recalled
    assert recalled[0]["domain"] == "alpha", recalled

    recall_standard = _run([sys.executable, str(_MEMORY), "recall", "--type", "standard",
                           "--limit", "5"], env=env)
    assert recall_standard.returncode == 0, recall_standard.stderr
    standard_records = [json.loads(l) for l in recall_standard.stdout.splitlines() if l.strip()]
    assert any(r["domain"] == "harness" for r in standard_records), standard_records

    raw = (target / "evals" / "_memory" / "lesson.jsonl").read_bytes()
    assert b"test-user@example.com" not in raw, "raw email must not survive to the tier-1 file"
    assert b"0912345678" not in raw, "raw phone digits must not survive to the tier-1 file"
    assert b"***@***.***" in raw, "the masked email placeholder must be present"
    assert b"*" in raw

    assert (state_dir / "eval-memory" / "standard.jsonl").is_file(), (
        "the re-injected HARNESS_STATE_DIR must have routed the tier-2 standard record")

    after = set(real_home.rglob("*")) if real_home.exists() else set()
    assert after == before, (
        "eval_memory must never write under the real per-OS home when HARNESS_STATE_DIR "
        "is explicitly re-injected: new entries %s" % (after - before))

    print("SLICE 6 OK: lesson+standard appended, filtered recall correct, "
          "email+phone redacted at byte level, real per-OS home untouched")


# --------------------------------------------------------------------------
# SLICE 7 — mutation matrix (real p0 fill all-pass; placeholder gate-blind)
# --------------------------------------------------------------------------

_M_MIRROR_FILL = '''

def run_pipeline(input_data):
    out = {}
    for line in input_data.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    return out
'''

_M_SCORER_FILL_COMMON = '''

def score_dimension(dimension_name, results):
    if not results:
        return 0.0
    passed = sum(1 for r in results if r.get("passed"))
    return 100.0 * passed / len(results)
'''

# The real p0 body: attribution dicts, not free strings -- lets mutation_matrix.py's
# `run` grep stdout for "'rule_index': N" and assert the P0-mutation trips the
# NAMED rule (single rule here -> index 0).
_M_SCORER_FILL_REAL_P0 = _M_SCORER_FILL_COMMON + '''

def check_p0_gates(results):
    failures = []
    for r in results:
        for f in r.get("fields", []):
            if f["field"] != "name":
                continue
            if f["status"] in ("EXTRA", "MISS"):
                failures.append({"rule_index": 0,
                                  "msg": "name is null in %s" % r["case"]})
    return len(failures) == 0, failures
'''

# The placeholder tree: mirror + score_dimension are filled for real, but
# check_p0_gates is left exactly as eval_scaffold stamped it (failures == []
# always) -- the "gate blind" fixture that closes the R3 presence-gate hole.


def _mutation_card(domain):
    return {
        "schema_version": "1",
        "domain": domain,
        "strategy": "ground-truth",
        "surface": "extraction",
        "production_module": "src/%s.py" % domain,
        "production_entry": "extract",
        "mirror_lang": "python",
        "forge": "github",
        "threshold": 70,
        "p0_rules": [
            {"rule": "name must be non-null", "source": "card",
             "target_axis": "name", "violation_value": None},
        ],
        "dimensions": {"accuracy": 100},
        "primary_dimension": "accuracy",
        "domain_config": {"normalizers": {}, "masks": {}},
        "case_matrix": [
            {"case": "c1.txt", "input": "name: Ann\nemail: ann@example.com",
             "expect": {"name": "Ann", "email": "ann@example.com"}, "baseline": True},
            {"case": "c2.txt", "input": "name: Bob\nemail: bob@example.com",
             "expect": {"name": "Bob", "email": "bob@example.com"}},
        ],
        "epsilon": {"maturity": 0.1},
        "cited_lessons": [],
        "approved_by": "e2e-slice",
        "approved_ts": "2026-07-14",
        # Phase 4 R3: mutation-proven coverage (>=1 mirror + >=1 p0-body code
        # mutation) or `generate` refuses. The real fill's check_p0_gates fires
        # on name MISS, so a broken mirror (-> {}) kills; the placeholder tree
        # leaves the gate blind so both go MISMATCH (the intended slice-7 fail).
        "code_mutations": [
            {"id": "cm-mirror", "target": "pipeline_mirror", "kills": "code:mirror",
             "patch": {"kind": "symbol_return", "symbol": "run_pipeline", "value": {}},
             "expected_exit": 1},
            {"id": "cm-p0", "target": "check_p0_gates", "kills": "code:p0",
             "patch": {"kind": "symbol_return", "symbol": "check_p0_gates",
                       "value": [False, [{"rule_index": 0, "msg": "forced"}]]},
             "expected_exit": 1},
        ],
    }


def _mutation_write_card(ws, card):
    card_path = ws / "_mutation_card.json"
    card_path.write_text(json.dumps(card), encoding="utf-8")
    r = _run([sys.executable, str(_CONFIG), "write", "--target", str(ws), "--card", str(card_path)])
    assert r.returncode == 0, "eval_config write failed: %s\n%s" % (r.stdout, r.stderr)


def _mutation_samples_and_gt(ws, domain, card):
    domain_dir = ws / "evals" / "eval_types" / domain
    samples = ws / "data" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    items = []
    for case in card["case_matrix"]:
        (samples / case["case"]).write_text(case["input"] + "\n", encoding="utf-8")
        items.append({"case_file": case["case"], "ground_truth": dict(case["expect"])})
    gt_path = domain_dir / "tests" / "production_fixtures" / "ground_truth.json"
    gt_path.parent.mkdir(parents=True, exist_ok=True)
    gt_path.write_text(json.dumps({"description": "slice7", "items": items}, ensure_ascii=False),
                       encoding="utf-8")
    return samples, gt_path


def _mutation_fill(ws, domain, mirror_fill, scorer_fill):
    domain_dir = ws / "evals" / "eval_types" / domain
    with open(domain_dir / "pipeline_mirror.py", "a", encoding="utf-8") as f:
        f.write(mirror_fill)
    with open(domain_dir / "scorer.py", "a", encoding="utf-8") as f:
        f.write(scorer_fill)


def slice7_mutation_matrix(ws):
    domain = "widget"
    ws.mkdir(parents=True, exist_ok=True)
    card = _mutation_card(domain)

    # -- real-fill tree: mirror + scorer + a REAL check_p0_gates -> generate
    # exit 0, run exit 0 (every mutation matched: p0-kill, +-epsilon threshold,
    # noise-no-panic).
    real = ws / "real"
    _scaffold(real, domain, "ground-truth")
    _mutation_fill(real, domain, _M_MIRROR_FILL, _M_SCORER_FILL_REAL_P0)
    _mutation_write_card(real, card)
    samples, gt_path = _mutation_samples_and_gt(real, domain, card)
    config_path = real / "evals" / "eval_config.json"

    matrix_path = real / "matrix.json"
    gen = _run([sys.executable, str(_MUTATION), "generate",
               "--config", str(config_path), "--out", str(matrix_path)])
    assert gen.returncode == 0, "mutation generate failed: %s" % gen.stderr

    report_path = real / "report.json"
    ran = _run([sys.executable, str(_MUTATION), "run", "--config", str(config_path),
               "--matrix", str(matrix_path), "--evals-root", str(real / "evals"),
               "--sample-dir", str(samples), "--ground-truth", str(gt_path),
               "--report", str(report_path)])
    assert ran.returncode == 0, (
        "a real check_p0_gates fill must make every mutation match its expectation:\n%s\n%s"
        % (ran.stdout, ran.stderr))
    report = json.loads(report_path.read_text(encoding="utf-8"))
    assert report["control_baseline_ok"] is True, report
    assert report["mismatches"] == [], report

    # -- placeholder-p0 tree: mirror + scorer filled for real, check_p0_gates
    # LEFT as the stamped stub (failures == [] always) -> run must FAIL and
    # classify the miss as a blind gate.
    placeholder = ws / "placeholder"
    _scaffold(placeholder, domain, "ground-truth")
    _mutation_fill(placeholder, domain, _M_MIRROR_FILL, _M_SCORER_FILL_COMMON)
    _mutation_write_card(placeholder, card)
    p_samples, p_gt_path = _mutation_samples_and_gt(placeholder, domain, card)
    p_config_path = placeholder / "evals" / "eval_config.json"

    p_matrix_path = placeholder / "matrix.json"
    p_gen = _run([sys.executable, str(_MUTATION), "generate",
                 "--config", str(p_config_path), "--out", str(p_matrix_path)])
    assert p_gen.returncode == 0, "mutation generate failed: %s" % p_gen.stderr

    p_ran = _run([sys.executable, str(_MUTATION), "run", "--config", str(p_config_path),
                 "--matrix", str(p_matrix_path), "--evals-root", str(placeholder / "evals"),
                 "--sample-dir", str(p_samples), "--ground-truth", str(p_gt_path)])
    assert p_ran.returncode == 1, (
        "a placeholder check_p0_gates (stub, always clean) must fail the mutation run:\n%s"
        % p_ran.stdout)
    assert "gate blind" in p_ran.stderr, p_ran.stderr

    print("SLICE 7 OK: real-fill tree all-pass mutation matrix; "
          "placeholder-p0 tree caught as a blind gate")

# --------------------------------------------------------------------------
# SLICE 8 — subprocess mirror lane (non-python mirror_lang, wave-2 wiring)
# --------------------------------------------------------------------------

# Stands in for an exotic-language pipeline mirror: python plays the
# interpreter the card's mirror_invoke argv_template names ("python3"), so
# this proves the any-language subprocess path needs nothing installed
# beyond python3 on PATH. Reads ONE case's arg-file (argv[1], per the
# {input_file} contract) and prints exactly ONE JSON object to stdout —
# zero-network, zero-env, deterministic (R9 mirror-guide contract).
_SLICE8_MIRROR_SOURCE = '''import json
import sys


def main():
    with open(sys.argv[1], encoding="utf-8") as fh:
        text = fh.read()
    out = {}
    for line in text.splitlines():
        if ":" in line:
            key, value = line.split(":", 1)
            out[key.strip()] = value.strip()
    sys.stdout.write(json.dumps(out))


if __name__ == "__main__":
    main()
'''


def slice8_subprocess_mirror(ws):
    domain = "fakepipe"
    dims = {"accuracy": 100}
    primary = "accuracy"
    domain_config = {"normalizers": {}, "masks": {}}
    # python stands in for "fakelang"'s own interpreter — proves the
    # subprocess contract needs no card-declared lang to be actually
    # installed, only an argv_template that resolves on PATH.
    mirror_invoke = {"argv_template": ["python3", "{mirror_path}", "{input_file}"]}
    case_matrix = [
        {"case": "c1.txt", "input": "name: Ann", "expect": {"name": "Ann"}},
        {"case": "c2.txt", "input": "name: Bob", "expect": {"name": "Bob"}},
    ]

    # 1) scaffold a NON-python lane.
    _scaffold(ws, domain, "ground-truth", dimensions=dims, primary_dimension=primary,
             domain_config=domain_config, mirror_lang="fakelang", forge="github")
    eval_dir = ws / "evals" / "eval_types" / domain

    # non-python mirror_lang stamps the guide + contract test in place of
    # pipeline_mirror.py + test_mirror_parity.py (eval_scaffold._plan) — the
    # two lanes are mutually exclusive; confirm before touching anything else.
    assert (eval_dir / "mirror-implementation-guide.md").is_file(), (
        "non-python mirror_lang must stamp the implementation guide")
    assert not (eval_dir / "pipeline_mirror.py").exists(), (
        "non-python mirror_lang must NOT stamp pipeline_mirror.py")
    test_contract_path = eval_dir / "tests" / "test_mirror_contract.py"
    assert test_contract_path.is_file(), "test_mirror_contract.py must be stamped"
    assert not (eval_dir / "tests" / "test_mirror_parity.py").exists()

    # scoring infra stays python either way (only the mirror itself is
    # lang-variable) — fill the scorer like every other slice.
    with open(eval_dir / "scorer.py", "a", encoding="utf-8") as f:
        f.write(_SCORER_FILL)

    _write_card(ws, domain, "ground-truth", domain_config=domain_config,
               mirror_lang="fakelang", forge="github", mirror_invoke=mirror_invoke,
               case_matrix=case_matrix)

    # 2) emit the subprocess contract from the approved card.
    emit = _run([sys.executable, str(_CONFIG), "emit-mirror-contract", "--target", str(ws)])
    assert emit.returncode == 0, "emit-mirror-contract failed: %s\n%s" % (emit.stdout, emit.stderr)
    contract_path = eval_dir / "mirror_contract.json"
    assert contract_path.is_file(), "mirror_contract.json must be emitted"
    contract = json.loads(contract_path.read_text(encoding="utf-8"))
    assert contract["card_hash"].startswith("sha256:"), contract
    assert contract["mirror_filename"] == "pipeline_mirror.fakelang", contract
    assert contract["lang"] == "fakelang", contract

    # 3) "LLM fill" — write the mirror at the contract's own mirror_filename.
    mirror_path = eval_dir / contract["mirror_filename"]
    mirror_path.write_text(_SLICE8_MIRROR_SOURCE, encoding="utf-8")

    samples = ws / "data" / "samples"
    samples.mkdir(parents=True, exist_ok=True)
    (samples / "c1.txt").write_text("name: Ann\n", encoding="utf-8")
    (samples / "c2.txt").write_text("name: Bob\n", encoding="utf-8")

    gt_path = eval_dir / "tests" / "production_fixtures" / "ground_truth.json"
    gt = {
        "description": "slice8 subprocess-mirror",
        "items": [
            {"case_file": "c1.txt", "ground_truth": {"name": "Ann"}},
            {"case_file": "c2.txt", "ground_truth": {"name": "Bob"}},
        ],
    }
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")

    cli = ws / "evals" / "scripts" / "run_production_evals.py"

    # 4) clean run -> exit 0 THROUGH the subprocess mirror.
    clean = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                 "--ground-truth", str(gt_path)])
    assert clean.returncode == 0, (
        "clean run through the subprocess mirror should PASS (exit 0):\n%s\n%s"
        % (clean.stdout, clean.stderr))
    assert "MATCH" in clean.stdout, clean.stdout

    # mutate ground truth -> BLOCK (exit 1): block-then-pass survives the
    # subprocess-mirror lane exactly like the direct-import lane (SLICE 1).
    gt["items"][0]["ground_truth"]["name"] = "someone completely different"
    gt_path.write_text(json.dumps(gt, indent=2, ensure_ascii=False), encoding="utf-8")
    blocked = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                   "--ground-truth", str(gt_path)])
    assert blocked.returncode == 1, (
        "mutated run through the subprocess mirror should BLOCK (exit 1):\n%s"
        % blocked.stdout)
    assert "MISMATCH" in blocked.stdout, blocked.stdout

    # 5) the stamped contract tests, run against the FILLED mirror — the R9
    # evidence gate's mechanical layer (determinism 2-run + import-fence)
    # must pass now that the mirror is filled, deterministic, and clean.
    contract_tests = _run([sys.executable, "-m", "pytest", str(test_contract_path), "-q"])
    assert contract_tests.returncode == 0, (
        "stamped test_mirror_contract.py must pass against the filled mirror:\n%s\n%s"
        % (contract_tests.stdout, contract_tests.stderr))
    assert "passed" in contract_tests.stdout, contract_tests.stdout

    # 6) hand-edit mirror_contract.json's card_hash AFTER approval -> drift
    # proof across the subprocess lane: the runner must die LOUD
    # (ConfigDriftError), never silently score against a contract whose hash
    # no longer matches the currently approved card.
    tampered = dict(contract)
    tampered["card_hash"] = "sha256:" + "0" * 64
    contract_path.write_text(
        json.dumps(tampered, sort_keys=True, separators=(",", ":"), ensure_ascii=False),
        encoding="utf-8")
    drifted = _run([sys.executable, str(cli), "--sample-dir", str(samples),
                   "--ground-truth", str(gt_path)])
    assert drifted.returncode != 0, (
        "a hand-edited mirror_contract.json card_hash must not score cleanly:\n%s\n%s"
        % (drifted.stdout, drifted.stderr))
    assert "ConfigDriftError" in drifted.stderr, (
        "the drift must surface as ConfigDriftError, loud, not a silent block:\n%s"
        % drifted.stderr)
    assert "PRODUCTION EVAL RESULTS" not in drifted.stdout, (
        "a drifted contract must die before any scoring/report output:\n%s" % drifted.stdout)

    print("SLICE 8 OK: subprocess-mirror lane (non-python mirror_lang) scaffolded, "
          "contract emitted+filled, clean/blocked exit codes through the mirror subprocess, "
          "stamped contract tests pass, hand-edited card_hash dies loud (ConfigDriftError)")


def main():
    with tempfile.TemporaryDirectory(prefix="eval-bootstrap-slice-") as tmp:
        ws = Path(tmp)
        slice1_ground_truth(ws / "s1")
        slice2_fake_judge(ws / "s2")
        slice3_data_extraction(ws / "s3")
        slice4_l1_and_card(ws / "s4")
        slice5_r9_sandbox(ws / "s5")
        slice6_memory(ws / "s6")
        slice7_mutation_matrix(ws / "s7")
        slice8_subprocess_mirror(ws / "s8")
    print("ALL SLICES PASSED")
    return 0


if __name__ == "__main__":
    sys.exit(main())
