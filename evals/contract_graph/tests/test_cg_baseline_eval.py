from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

from conftest import COMMITTED_DATA, REPO_ROOT

from evals.contract_graph import run_eval
from evals.contract_graph.baseline_predictor import predict


def _score(data: Path, out: Path) -> dict:
    assert (
        run_eval.main(["score", "--data", str(data), "--predictor", "baseline", "--out", str(out)])
        == 0
    )
    return json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))


def test_baseline_predictions_carry_the_contract_fields(mini_dataset: Path):
    preds = predict(mini_dataset / "mini")

    assert [p["src_address"] for p in preds] == [
        "khoan 1 dieu 1",
        "khoan 2 dieu 1",
        "diem a khoan 2 dieu 1",
        "diem b khoan 2 dieu 1",
        "khoan 3 dieu 1",
        "khoan 4 dieu 1",
    ]
    for pred in preds:
        assert set(pred) >= {
            "src_address",
            "op",
            "target_text",
            "target_address",
            "head",
            "marker_hit",
        }
        assert pred["marker_hit"] is True


def test_baseline_lists_targets_of_an_enumerated_item():
    from evals.contract_graph.baseline_predictor import parse

    text = (
        "Điều 1. Sửa đổi, bổ sung một số điều như sau:\n"
        "2. Sửa đổi, bổ sung một số điểm của khoản 1 và khoản 2 Điều 3 như sau:\n"
        "e) Bổ sung điểm d1, d2 vào sau điểm d khoản 2 như sau:\n"
        "“d1) Hợp đồng theo chi phí cộng phí;\n"
        "3. Bãi bỏ khoản 3 và khoản 4 Điều 7.\n"
        "Điều 2. Hiệu lực"
    )

    preds = {p["src_address"]: p for p in parse(text)}

    # spike target "điểm d1 điều 3" is kept as-is (no khoản level), only the list is expanded
    assert preds["diem e khoan 2 dieu 1"]["target_addresses"] == [
        "diem d1 dieu 3",
        "diem d2 dieu 3",
    ]
    assert preds["diem e khoan 2 dieu 1"]["target_address"] == "diem d1 dieu 3"
    # "khoản 1 và khoản 2" is two addresses, not a value list of one level: no expansion
    assert preds["khoan 2 dieu 1"]["target_addresses"] == ["khoan 2 dieu 3"]
    # spike regex keeps its own pick ("khoản 4 Điều 7", the one next to "Điều"); no list expansion
    assert preds["khoan 3 dieu 1"]["target_addresses"] == ["khoan 4 dieu 7"]


def test_baseline_end_to_end_on_mini_fixture(mini_dataset: Path, tmp_path: Path):
    report = _score(mini_dataset, tmp_path / "out" / "mini")

    overall = report["overall"]["all"]
    assert overall["n_gold"] == 5
    assert (overall["src_found"]["passed"], overall["src_found"]["denominator"]) == (5, 5)
    assert (
        overall["op_lexical_agreement"]["passed"],
        overall["op_lexical_agreement"]["denominator"],
    ) == (5, 5)
    assert (overall["target_accuracy"]["passed"], overall["target_accuracy"]["denominator"]) == (
        2,
        5,
    )
    assert [(u["src_address"], u["op"]) for u in report["unmatched_predictions"]] == [
        ("khoan 2 dieu 1", "SUBSTITUTION")
    ]
    wrong = {m["src_address"]: m["pred_target_address"] for m in report["target_mismatches"]}
    assert wrong == {
        "diem a khoan 2 dieu 1": "diem c dieu 4",
        "diem b khoan 2 dieu 1": "diem đ dieu 4",
        "khoan 3 dieu 1": "khoan 4 dieu 6",
    }
    assert report["by_pair"]["mini"]["all"]["target_accuracy"]["passed"] == 2
    assert report["overall"]["marker_hit"] == {
        "passed": 6,
        "denominator": 6,
        "rate": 1.0,
        "wilson95": [0.6097, 1.0],
    }
    md = (tmp_path / "out" / "mini.md").read_text(encoding="utf-8")
    assert "| SUBSTITUTION |" in md and "| mini |" in md


def test_report_bytes_independent_of_hash_seed(mini_dataset: Path, tmp_path: Path):
    outputs = []
    for seed in ("1", "2"):
        out = tmp_path / f"seed{seed}" / "report"
        env = {**os.environ, "PYTHONHASHSEED": seed, "PYTHONIOENCODING": "utf-8"}
        proc = subprocess.run(
            [
                sys.executable,
                "-m",
                "evals.contract_graph.run_eval",
                "score",
                "--data",
                str(mini_dataset),
                "--predictor",
                "baseline",
                "--out",
                str(out),
            ],
            cwd=REPO_ROOT,
            env=env,
            capture_output=True,
            text=True,
            timeout=120,
        )
        assert proc.returncode == 0, proc.stderr
        outputs.append((out.with_suffix(".json").read_bytes(), out.with_suffix(".md").read_bytes()))

    assert outputs[0] == outputs[1]


# ---- Tests After: committed dataset -------------------------------------------------------------


def test_baseline_reproduces_spike_on_nd50(tmp_path: Path):
    report = _score(COMMITTED_DATA, tmp_path / "all")

    nd50 = report["by_pair"]["nd50-2021"]["all"]
    assert nd50["n_gold"] == 26
    assert nd50["src_found"]["passed"] == 26
    assert nd50["op_lexical_agreement"]["passed"] == 26
