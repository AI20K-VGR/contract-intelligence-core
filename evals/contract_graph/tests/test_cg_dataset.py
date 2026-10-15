from __future__ import annotations

import hashlib
import json
import urllib.request
from pathlib import Path

import pytest
from conftest import COMMITTED_DATA, MINI_SOURCES, seed_cache

from evals.contract_graph import run_eval
from evals.contract_graph.dataset import (
    CacheMiss,
    build_pair,
    fetch_cached,
    verify_manifest,
)

MAX_COMMITTED_BYTES = 5 * 1024 * 1024


def _sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def test_freeze_writes_sha256_for_every_file(mini_dataset: Path):
    manifest = json.loads((mini_dataset / "manifest.json").read_text(encoding="utf-8"))

    assert [p["pair_id"] for p in manifest["pairs"]] == ["mini"]
    entry = manifest["pairs"][0]
    assert set(entry["files"]) == {"amending.txt", "vbhn.txt", "gold.jsonl"}
    for name, digest in entry["files"].items():
        assert digest == _sha(mini_dataset / "mini" / name)
    assert entry["gold_by_op"] == {"INSERTION": 2, "REPEAL": 1, "SUBSTITUTION": 2}
    assert entry["issuer"] == "Chính phủ"
    assert entry["amending_doc"] == "20/2021/NĐ-CP"
    assert set(entry["raw_sha256"]) == {"amending", "vbhn"}
    assert entry["operative_article"] == "1"
    assert manifest["total_bytes"] == sum(
        f.stat().st_size for f in (mini_dataset / "mini").iterdir()
    )
    assert verify_manifest(mini_dataset) == []


def test_verify_manifest_detects_tampered_file(mini_dataset: Path):
    gold = mini_dataset / "mini" / "gold.jsonl"
    gold.write_text(
        gold.read_text(encoding="utf-8").replace("REPEAL", "INSERTION"), encoding="utf-8"
    )
    (mini_dataset / "stray").mkdir()

    problems = verify_manifest(mini_dataset)

    assert any("mini/gold.jsonl" in p and "sha256" in p for p in problems)
    assert any("stray" in p for p in problems)
    assert verify_manifest(mini_dataset / "missing") != []


def test_offline_fetch_never_touches_network(tmp_path: Path):
    url = "https://example.test/mini_vbhn.html"
    seed_cache(tmp_path, url, "mini_vbhn.html")

    assert fetch_cached(url, tmp_path, offline=True).startswith(b"<!DOCTYPE html>")
    assert fetch_cached(url, tmp_path, offline=False).startswith(b"<!DOCTYPE html>")
    with pytest.raises(CacheMiss, match="not cached"):
        fetch_cached("https://example.test/absent.html", tmp_path, offline=True)
    with pytest.raises(RuntimeError, match="network access is blocked"):
        fetch_cached("https://example.test/absent.html", tmp_path, offline=False)
    assert urllib.request.urlopen.__name__ == "_blocked"


def test_build_pair_carries_source_metadata(tmp_path: Path):
    source = MINI_SOURCES[1]
    for key in ("amending_url", "vbhn_url"):
        seed_cache(tmp_path, source[key], source[key].rsplit("/", 1)[1])

    pair = build_pair(source, tmp_path, offline=True)

    assert pair["pair_id"] == "mini-suffix"
    assert [r["target_address"] for r in pair["gold"]] == [
        "diem d1 khoan 2 dieu 3",
        "diem d2 khoan 2 dieu 3",
        "khoan 5a dieu 18",
        "dieu 30a",
    ]
    assert "Điều 1. Sửa đổi, bổ sung" in pair["amending_text"]


def test_run_eval_refuses_when_manifest_mismatches(
    mini_dataset: Path, tmp_path: Path, capsys: pytest.CaptureFixture
):
    (mini_dataset / "mini" / "vbhn.txt").write_text("sửa tay", encoding="utf-8")
    out = tmp_path / "reports" / "r"

    code = run_eval.main(
        ["score", "--data", str(mini_dataset), "--predictor", "baseline", "--out", str(out)]
    )

    assert code != 0
    assert "manifest" in capsys.readouterr().err
    assert not out.with_suffix(".json").exists() and not out.with_suffix(".md").exists()


FAKE_PREDICTOR = """
from pathlib import Path

CALLS = []


def predict(pair_dir: Path) -> list[dict]:
    CALLS.append(pair_dir.name)
    return [{"src_address": "khoan 4 dieu 1", "op": "REPEAL", "target_address": "khoan 3 dieu 7"}]
"""


def test_run_eval_loads_predictor_from_dotted_path(
    mini_dataset: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
):
    pkg = tmp_path / "plugins"
    pkg.mkdir()
    (pkg / "cg_fake_predictor.py").write_text(FAKE_PREDICTOR, encoding="utf-8")
    monkeypatch.syspath_prepend(str(pkg))
    out = tmp_path / "reports" / "fake"

    code = run_eval.main(
        [
            "score",
            "--data",
            str(mini_dataset),
            "--predictor",
            "cg_fake_predictor:predict",
            "--out",
            str(out),
        ]
    )

    assert code == 0
    import cg_fake_predictor

    assert cg_fake_predictor.CALLS == ["mini"]
    report = json.loads(out.with_suffix(".json").read_text(encoding="utf-8"))
    assert report["predictor"] == "cg_fake_predictor:predict"
    assert report["overall"]["by_op"]["REPEAL"]["target_accuracy"]["passed"] == 1
    assert report["overall"]["all"]["src_found"] == {
        "passed": 1,
        "denominator": 5,
        "rate": 0.2,
        "wilson95": report["overall"]["all"]["src_found"]["wilson95"],
    }


def test_run_eval_rejects_bad_predictor_spec(mini_dataset: Path, tmp_path: Path):
    with pytest.raises(SystemExit):
        run_eval.main(
            [
                "score",
                "--data",
                str(mini_dataset),
                "--predictor",
                "no_colon_here",
                "--out",
                str(tmp_path / "x"),
            ]
        )


# ---- Tests After: committed dataset -------------------------------------------------------------


def test_committed_dataset_manifest_verifies():
    assert (COMMITTED_DATA / "manifest.json").exists(), "dataset not frozen yet"
    assert verify_manifest(COMMITTED_DATA) == []
    manifest = json.loads((COMMITTED_DATA / "manifest.json").read_text(encoding="utf-8"))
    assert manifest["total_bytes"] <= MAX_COMMITTED_BYTES


def test_committed_dataset_meets_coverage_contract():
    manifest = json.loads((COMMITTED_DATA / "manifest.json").read_text(encoding="utf-8"))
    pairs = manifest["pairs"]
    issuers = {p["issuer"] for p in pairs}
    repeal = sum(p["gold_by_op"].get("REPEAL", 0) for p in pairs)

    assert len(pairs) >= 10, f"{len(pairs)} pairs"
    assert len(issuers) >= 4, sorted(issuers)
    assert repeal >= 1
    assert "nd50-2021" in {p["pair_id"] for p in pairs}
