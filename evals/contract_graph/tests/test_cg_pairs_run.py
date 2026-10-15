from __future__ import annotations

from types import SimpleNamespace

import pytest

from evals.contract_graph.dataset import file_digest
from evals.contract_graph.pairs import bakeoff, manifest, predictor, run
from evals.contract_graph.score import rate


def _quality_fixture(tmp_path, *, review_lock=False):
    data_dir = tmp_path / "quality-data"
    review_dir = data_dir / "review"
    review_dir.mkdir(parents=True)
    gold = [{"pair_id": "p1", "gold_label": "CONFLICT", "gold_direction": None,
             "approved": True, "source": "user-review"}]
    entries = {}
    for name, rows, role in (("recall_frame", [{"pair_id": "p1", "role": "both", "cluster_id": "cl-1"}], "both"),
                             ("precision_frame", [{"pair_id": "p1", "role": "both", "cluster_id": "cl-1"}], "both"),
                             ("reviewed_gold", gold, None)):
        path = review_dir / f"{name}.jsonl"
        manifest.write_jsonl(path, rows)
        entries[name] = {"path": f"review/{name}.jsonl", "sha256": file_digest(path), "n_rows": len(rows)}
    frozen = {"schema": predictor.QUALITY_DATASET_SCHEMA, "dataset_id": "quality-run-v1",
              "frame_version": predictor.score_quality_frame_version(), **entries}
    if review_lock:
        frozen["review_lock"] = {"schema": predictor.QUALITY_REVIEW_LOCK_SCHEMA,
                                  "dataset_id": frozen["dataset_id"],
                                  "reviewed_gold_sha256": entries["reviewed_gold"]["sha256"],
                                  "n_rows": 1, "approved_by_label": {"CONFLICT": 1},
                                  "source": "user-review", "human_approved": True}
    quality_manifest = tmp_path / "quality-manifest.json"
    manifest.write_json(quality_manifest, frozen)
    return data_dir, quality_manifest


def test_quality_dev_lock_is_report_independent(monkeypatch, tmp_path, capsys):
    data_dir, quality_manifest = _quality_fixture(tmp_path)
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(manifest, "ensure_outside_repo", lambda *_: None)
    args = SimpleNamespace(data_dir=data_dir, manifest=quality_manifest)

    assert run._review_quality_dev_lock(args) == 0
    locked = manifest.read_json(quality_manifest)
    assert locked["review_lock"]["human_approved"] is True
    assert locked["review_lock"]["approved_by_label"] == {"CONFLICT": 1}
    assert "dev_report_lock" not in locked
    assert '"review_lock"' in capsys.readouterr().out


def test_quality_report_lock_requires_matching_predecessor_and_pass_report(monkeypatch, tmp_path):
    data_dir, quality_manifest = _quality_fixture(tmp_path, review_lock=True)
    monkeypatch.setattr(manifest, "REPO_ROOT", tmp_path)
    monkeypatch.setattr(manifest, "ensure_outside_repo", lambda *_: None)
    args = SimpleNamespace(data_dir=data_dir, manifest=quality_manifest,
                           report=tmp_path / "missing-report.json", predecessor_sha256="0" * 64)

    assert run._review_quality_dev_report_lock(args) == 2
    assert "dev_report_lock" not in manifest.read_json(quality_manifest)


def test_quality_heldout_preflight_blocks_missing_locked_report_before_data_access(tmp_path):
    data_dir, quality_manifest = _quality_fixture(tmp_path, review_lock=True)

    with pytest.raises(SystemExit) as blocked:
        bakeoff.preconditions(data_dir, quality_manifest=quality_manifest)

    assert blocked.value.code == 2


def _write_passing_report(tmp_path, data_dir, quality_manifest):
    frozen = manifest.read_json(quality_manifest)
    gold, predictions, frame_ids = [], [], []
    for label in ("GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE"):
        for index in range(60):
            pair_id = f"{label}-{index}"
            cluster_id = f"cluster-{index % 30:02d}"
            direction = "A" if label in {"GENERAL_SPECIFIC", "REFERENCE"} else None
            gold.append({"pair_id": pair_id, "gold_label": label, "gold_direction": direction,
                         "cluster_id": cluster_id,
                         "approved": True, "source": "user-review"})
            predictions.append({"pair_id": pair_id, "label": label, "direction": direction,
                                "cluster_id": cluster_id})
            frame_ids.append({"pair_id": pair_id, "role": "both", "cluster_id": cluster_id})
    entries = {}
    for name, rows in (("recall_frame", frame_ids), ("precision_frame", frame_ids),
                       ("reviewed_gold", gold)):
        path = data_dir / frozen[name]["path"]
        manifest.write_jsonl(path, rows)
        entries[name] = {"path": frozen[name]["path"], "sha256": file_digest(path), "n_rows": len(rows)}
    frozen.update(entries)
    frozen["review_lock"] = {"schema": predictor.QUALITY_REVIEW_LOCK_SCHEMA,
                             "dataset_id": frozen["dataset_id"],
                             "reviewed_gold_sha256": entries["reviewed_gold"]["sha256"],
                             "n_rows": len(gold),
                             "approved_by_label": {label: 60 for label in
                                                   ("GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE")},
                             "source": "user-review", "human_approved": True}
    manifest.write_json(quality_manifest, frozen)
    reviewed = predictor.read_quality_dataset(data_dir, quality_manifest, require_review_lock=True)
    cluster_by_pair = {row["pair_id"]: row["cluster_id"] for row in frame_ids}
    cluster_intervals = predictor.quality_cluster_intervals(gold, predictions, cluster_by_pair)
    report = {"quality_report_schema": predictor.QUALITY_REPORT_SCHEMA, "quality_status": "PASS",
              "quality_dataset": {"dataset_id": frozen["dataset_id"],
                                  "manifest_sha256": reviewed["manifest_sha256"]},
              "quality_evidence": {"gold": gold, "predictions": predictions,
                                   "recall_frame": [row["pair_id"] for row in frame_ids],
                                   "precision_frame": [row["pair_id"] for row in frame_ids],
                                   "cluster_by_pair": cluster_by_pair},
              "quality_score": predictor.score_quality(gold, predictions,
                                                        recall_frame=[row["pair_id"] for row in frame_ids],
                                                        precision_frame=[row["pair_id"] for row in frame_ids]),
              "code_sha256": predictor.code_fingerprints()}
    report["quality_cluster_intervals"] = cluster_intervals
    report["quality_gate"] = predictor.quality_gate(report["quality_score"],
                                                   cluster_intervals=cluster_intervals)
    report["report_sha256"] = predictor.report_digest(report)
    report_path = tmp_path / "quality-dev-report.json"
    manifest.write_json(report_path, report)
    return report_path


def test_quality_report_lock_and_preflight_recompute_raw_metrics(tmp_path, capsys):
    data_dir, quality_manifest = _quality_fixture(tmp_path)
    run._review_quality_dev_lock(SimpleNamespace(data_dir=data_dir, manifest=quality_manifest))
    report_path = _write_passing_report(tmp_path, data_dir, quality_manifest)
    frozen = manifest.read_json(quality_manifest)
    args = SimpleNamespace(data_dir=data_dir, manifest=quality_manifest, report=report_path,
                           predecessor_sha256=predictor.quality_manifest_digest(frozen))

    assert run._review_quality_dev_report_lock(args) == 0
    with pytest.raises(SystemExit) as blocked:
        bakeoff.preconditions(data_dir, quality_manifest=quality_manifest,
                              dev_report_path=report_path)

    assert blocked.value.code == 2
    assert "held-out review/frame lock is missing" in capsys.readouterr().err


def test_quality_preflight_rejects_forged_aggregate_even_with_fresh_report_digest(tmp_path, capsys):
    data_dir, quality_manifest = _quality_fixture(tmp_path)
    run._review_quality_dev_lock(SimpleNamespace(data_dir=data_dir, manifest=quality_manifest))
    report_path = _write_passing_report(tmp_path, data_dir, quality_manifest)
    report = manifest.read_json(report_path)
    report["quality_score"]["by_label"]["CONFLICT"]["recall_exact"] = rate(59, 60)
    report["report_sha256"] = predictor.report_digest(report)
    manifest.write_json(report_path, report)
    frozen = manifest.read_json(quality_manifest)
    lock = frozen["dev_report_lock"] = {
        "schema": predictor.QUALITY_REPORT_LOCK_SCHEMA,
        "path": report_path.resolve().relative_to(manifest.REPO_ROOT.resolve()).as_posix(),
        "sha256": file_digest(report_path), "dataset_id": frozen["dataset_id"],
        "quality_manifest_sha256": predictor.quality_manifest_digest(frozen),
        "predecessor_sha256": predictor.quality_manifest_digest(frozen),
    }
    manifest.write_json(quality_manifest, frozen)

    with pytest.raises(SystemExit) as blocked:
        bakeoff.preconditions(data_dir, quality_manifest=quality_manifest,
                              dev_report_path=report_path)

    assert blocked.value.code == 2
    assert "quality dev metrics do not recompute" in capsys.readouterr().err


def test_preflight_cli_accepts_explicit_quality_manifest_and_dev_report(tmp_path, monkeypatch):
    captured = []

    def preconditions(*args, **kwargs):
        captured.append((args, kwargs))
        raise SystemExit(2)

    monkeypatch.setattr(bakeoff, "preconditions", preconditions)
    quality_manifest = tmp_path / "quality.json"
    dev_report = tmp_path / "dev-report.json"
    result = run.main(["bakeoff", "preflight-checks", "--quality-manifest", str(quality_manifest),
                       "--dev-report", str(dev_report)])

    assert result == 2
    assert captured[0][1]["quality_manifest"] == quality_manifest
    assert captured[0][1]["dev_report_path"] == dev_report
