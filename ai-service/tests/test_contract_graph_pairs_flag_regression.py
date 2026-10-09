from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from scripts.capture_idp_golden import shas, strip_pairs

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts/capture_idp_golden.py"
GOLDEN = ROOT / "fixtures/contract_graph/idp_graph_on_golden.json"


def emit(*args, pairs=None, graph="1", seed="0"):
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI2_CONTRACT_GRAPH")}
    env.update(PYTHONHASHSEED=seed, AI2_CONTRACT_GRAPH_ENABLED=graph)
    if pairs is not None:
        env["AI2_CONTRACT_GRAPH_PAIRS_ENABLED"] = pairs
    proc = subprocess.run([sys.executable, str(SCRIPT), *args], cwd=ROOT, env=env,
                          capture_output=True, timeout=600)
    assert proc.returncode == 0, proc.stderr.decode("utf8", "replace")
    return json.loads(proc.stdout)


def test_flag_off_capture_reproduces_committed_file(tmp_path):
    out = tmp_path / "capture.json"
    env = {**os.environ, "PYTHONHASHSEED": "0"}
    proc = subprocess.run([sys.executable, str(SCRIPT), "--out", str(out)], cwd=ROOT,
                          env=env, capture_output=True, timeout=600)
    assert proc.returncode == 0
    assert out.read_bytes() == GOLDEN.with_name("idp_flag_off_golden.json").read_bytes()


def test_pairs_flag_alone_matches_flag_off_golden():
    want = json.loads(GOLDEN.with_name("idp_flag_off_golden.json").read_text("utf8"))["cases"]
    assert emit("--emit-shas", pairs="1", graph="0") == want


def test_graph_on_pairs_unset_matches_graph_on_golden():
    assert emit("--emit-shas", "--profile", "graph_on") == json.loads(GOLDEN.read_text("utf8"))["cases"]


@pytest.mark.parametrize("value", ["", "0", "false", "off"])
def test_graph_on_pairs_false_values_match_graph_on_golden(value):
    assert emit("--emit-shas", "--profile", "graph_on", pairs=value) == json.loads(GOLDEN.read_text("utf8"))["cases"]


def test_graph_on_golden_records_seed_python_and_cases():
    golden = json.loads(GOLDEN.read_text("utf8"))
    assert golden["hashseed"] == "0" and golden["python"] == f"{sys.version_info.major}.{sys.version_info.minor}"
    assert {"contract_graph.graph_record", "contract_graph.pair_record_embedded"} <= golden["cases"].keys()
    for seed in ("1", "2"):
        got = emit("--emit-shas", "--profile", "graph_on", seed=seed)
        assert {k for k in got if got[k] != golden["cases"][k]} <= {"SERVICE-BRD-08"}


def test_pairs_rule_only_differs_only_by_stripped_fields():
    golden = json.loads(GOLDEN.read_text("utf8"))
    want = {case: shas(strip_pairs(full)) for case, full in golden["full"].items()}
    assert emit("--emit-shas", "--profile", "graph_on", "--strip-pairs", pairs="1") == want
    for case, full in golden["full"].items():
        got = emit("--emit-full", case, "--profile", "graph_on", pairs="1")
        assert got["job_result"]["review_state"] in {full["job_result"]["review_state"], "NEEDS_REVIEW"}
    got = emit("--emit-full", "contract_graph.pair_record_embedded", "--profile", "graph_on", pairs="1")
    cov = got["job_result"]["contribution"]["coverage"]["contract_graph"]
    assert cov["graph_mode"] == "operation_first+pairs_rule_only"
    assert cov["pairs"]["rule_only_reason"] == "NO_CONSENT"


def test_pairs_off_does_not_import_pair_modules():
    env = {k: v for k, v in os.environ.items() if not k.startswith("AI2_CONTRACT_GRAPH")}
    env.update(PYTHONHASHSEED="0", AI2_CONTRACT_GRAPH_ENABLED="1")
    code = "import sys; from scripts import capture_idp_golden as c; c.run_case(dict(c.cases())[c.MOCK_CASE]); print(any(n.startswith('app.pipeline.contract_graph.pair_') for n in sys.modules))"
    proc = subprocess.run([sys.executable, "-c", code], cwd=ROOT, env=env, capture_output=True, timeout=120)
    assert proc.returncode == 0 and proc.stdout.strip() == b"False"
