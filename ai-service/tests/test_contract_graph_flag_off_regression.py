"""K2: with ``AI2_CONTRACT_GRAPH_ENABLED`` off, ``run_idp`` output stays byte-identical.

Every golden comparison runs ``scripts/capture_idp_golden.py --emit-shas`` in a subprocess with
``PYTHONHASHSEED`` pinned (D16/RT-01): the old path orders a ``set`` of strings at
``app/pipeline/compare.py:67-71``, so a sha taken under another seed is not comparable.
"""

from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "capture_idp_golden.py"
GOLDEN = ROOT / "fixtures" / "contract_graph" / "idp_flag_off_golden.json"
FLAG = "AI2_CONTRACT_GRAPH_ENABLED"
# Only cases whose seed dependence has a cause in OLD code (not P3/P4) and a reviewer's sign-off.
HASHSEED_SENSITIVE = {"SERVICE-BRD-08": "compare.py:67-71 set order"}


def _env(seed: str, **flag: str) -> dict[str, str]:
    env = {k: v for k, v in os.environ.items() if k != FLAG}
    env.update(PYTHONHASHSEED=seed, PYTHONIOENCODING="utf-8", **flag)
    return env


def _emit(seed: str, **flag: str) -> dict[str, dict]:
    proc = subprocess.run(
        [sys.executable, str(SCRIPT), "--emit-shas"],
        cwd=ROOT,
        env=_env(seed, **flag),
        capture_output=True,
        timeout=600,
    )
    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    return json.loads(proc.stdout.decode("utf-8"))


def _golden() -> dict:
    return json.loads(GOLDEN.read_text(encoding="utf-8"))


def _mismatches(got: dict[str, dict], want: dict[str, dict]) -> list[str]:
    assert set(got) == set(want), sorted(set(got) ^ set(want))
    return sorted(case for case in want if got[case] != want[case])


def _full_diff_hint(cases: list[str]) -> str:
    golden = _golden()["full"]
    hints = []
    for case in cases:
        if case not in golden:
            continue
        proc = subprocess.run(
            [sys.executable, str(SCRIPT), "--emit-full", case],
            cwd=ROOT,
            env=_env("0"),
            capture_output=True,
            timeout=600,
        )
        got = json.loads(proc.stdout.decode("utf-8"))
        for part in ("job_result", "wire", "record"):
            if got[part] != golden[case][part]:
                hints.append(f"{case}/{part} differs from the stored full JSON")
    return "; ".join(hints)


@pytest.fixture(scope="module")
def seed0() -> dict[str, dict]:
    return _emit("0")


def test_golden_records_interpreter_and_seed():
    golden = _golden()
    running = f"{sys.version_info.major}.{sys.version_info.minor}"

    assert golden["hashseed"] == "0"
    if golden["python"] != running:
        pytest.fail(
            f"golden was captured on CPython {golden['python']}, this run is {running}: set "
            "iteration order is only stable within one minor version. Run the suite on "
            f"{golden['python']} (ai-service/.venv); do not recapture to make it pass."
        )


def test_run_idp_is_deterministic_under_patched_uuid():
    # Same process = same hash seed: this proves the uuid patch is enough, nothing about seeds.
    sys.path.insert(0, str(ROOT / "scripts"))
    try:
        import capture_idp_golden as capture
    finally:
        sys.path.remove(str(ROOT / "scripts"))

    for case_id, build in capture.cases():
        first = capture.shas(capture.run_case(build))
        second = capture.shas(capture.run_case(build))
        assert first == second, case_id


def test_flag_unset_matches_golden(seed0):
    bad = _mismatches(seed0, _golden()["cases"])

    assert bad == [], f"flag-off output changed for {bad}. {_full_diff_hint(bad)}"


@pytest.mark.parametrize("value", ["", "0", "false", "off"])
def test_flag_explicit_false_values_match_golden(value):
    bad = _mismatches(_emit("0", **{FLAG: value}), _golden()["cases"])

    assert bad == [], f"{FLAG}={value!r} changed flag-off output for {bad}"


def test_golden_equal_across_hash_seeds_except_declared(seed0):
    runs = {"0": seed0, "1": _emit("1"), "2": _emit("2")}
    golden = _golden()["cases"]

    for seed, run in runs.items():
        bad = [c for c in _mismatches(run, golden) if c not in HASHSEED_SENSITIVE]
        assert bad == [], f"seed {seed}: new hash-seed dependence in {bad} (find the set order)"
    varying = {case for case in golden if len({json.dumps(r[case]) for r in runs.values()}) > 1}
    assert varying == set(HASHSEED_SENSITIVE), (
        f"seed-dependent cases {sorted(varying)} != declared {sorted(HASHSEED_SENSITIVE)}"
    )


def test_flag_off_does_not_import_builder():
    code = (
        "import sys\n"
        "sys.path.insert(0, 'scripts')\n"
        "import capture_idp_golden as c\n"
        "c.run_case(dict(c.cases())[c.MOCK_CASE])\n"
        "print('app.pipeline.contract_graph.builder' in sys.modules,"
        " 'app.pipeline.contract_graph' in sys.modules)\n"
    )
    proc = subprocess.run(
        [sys.executable, "-c", code], cwd=ROOT, env=_env("0"), capture_output=True, timeout=300
    )

    assert proc.returncode == 0, proc.stderr.decode("utf-8", "replace")
    assert proc.stdout.decode().split() == ["False", "False"]
