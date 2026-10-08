from __future__ import annotations

import hashlib
import json
import math
import subprocess
from pathlib import Path

import pytest
from conftest import REPO_ROOT
from test_cg_pairs_corpus import contract_text, service_text, source

from evals.contract_graph.pairs import corpus, manifest, pool, run

PAIRS_DIR = REPO_ROOT / "evals" / "contract_graph" / "pairs"
COMMITTED_MANIFEST = PAIRS_DIR / "manifest.json"
TEXT_KEYS = {"text", "span_a", "span_b", "heading", "heading_a", "heading_b", "text_a", "text_b"}


def _sha(url: str) -> str:
    return hashlib.sha256(url.encode("utf-8")).hexdigest()


def test_split_by_cluster_two_thirds_heldout():
    urls = {f"pd-{i}": f"https://site{i}.test/x" for i in range(7)}
    clusters = [
        {"cluster_id": "c-a", "doc_ids": ["pd-0", "pd-1"]},
        {"cluster_id": "c-b", "doc_ids": ["pd-2"]},
        {"cluster_id": "c-c", "doc_ids": ["pd-3", "pd-4"]},
        {"cluster_id": "c-d", "doc_ids": ["pd-5"]},
        {"cluster_id": "c-e", "doc_ids": ["pd-6"]},
    ]
    splits, stats = manifest.assign_splits(clusters, set(), urls)

    for cluster in clusters:
        assert len({splits[d] for d in cluster["doc_ids"]}) == 1
    ranked = sorted(clusters, key=lambda c: min(_sha(urls[d]) for d in c["doc_ids"]))
    n_heldout = math.ceil(2 * len(clusters) / 3)
    assert [splits[c["doc_ids"][0]] for c in ranked] == (
        ["heldout"] * n_heldout + ["dev"] * (len(clusters) - n_heldout)
    )
    assert stats["forced_dev_contaminated"] == 0
    assert manifest.assign_splits(list(reversed(clusters)), set(), urls)[0] == splits


def test_contaminated_cluster_forced_to_dev():
    spike_clause = "Bên Mua chậm thanh toán chịu lãi chậm trả theo lãi suất ngân hàng công bố."
    spike = corpus.Spike.from_texts(urls=["https://spike.test/a"], texts=[spike_clause])
    by_url = corpus.build_doc(source("https://spike.test/a"), service_text())
    by_repo = corpus.build_doc(source("repo:ai-service/fixtures/contracts/X.md"), service_text())
    by_content = corpus.build_doc(source("https://new.test/c"), contract_text())
    sibling = corpus.build_doc(source("https://new.test/d"), service_text())
    clean = [corpus.build_doc(source(f"https://clean{i}.test/"), service_text()) for i in range(4)]
    docs = [by_url, by_repo, by_content, sibling, *clean]
    dirty = {d["doc_id"] for d in docs if corpus.contaminated(d, spike)}
    assert dirty == {by_url["doc_id"], by_repo["doc_id"], by_content["doc_id"]}
    clusters = [
        {"cluster_id": "c-1", "doc_ids": [by_url["doc_id"], sibling["doc_id"]]},
        {"cluster_id": "c-2", "doc_ids": [by_repo["doc_id"]]},
        {"cluster_id": "c-3", "doc_ids": [by_content["doc_id"]]},
        *({"cluster_id": f"c-clean{i}", "doc_ids": [d["doc_id"]]} for i, d in enumerate(clean)),
    ]
    splits, stats = manifest.assign_splits(clusters, dirty, {d["doc_id"]: d["url"] for d in docs})

    for doc in (by_url, sibling, by_repo, by_content):
        assert splits[doc["doc_id"]] == "dev"
    assert stats["forced_dev_contaminated"] == 4
    assert stats["forced_dev_clusters"] == 3
    assert sum(1 for d in clean if splits[d["doc_id"]] == "heldout") == math.ceil(2 * 4 / 3)


def _stage(data_dir: Path) -> list[dict]:
    """Two synthetic docs through build → pool → (fake) labels, staged under ``work/``."""

    docs = [
        corpus.build_doc(source("https://a.test/1"), contract_text()),
        corpus.build_doc(source("https://b.test/2", "SUPPLY_SERVICE"), service_text()),
    ]
    stats = {}
    for doc in docs:
        doc["contaminated"] = False
        manifest.write_json(manifest.work(data_dir, "docs", f"{doc['doc_id']}.json"), doc)
        records, stats[doc["doc_id"]] = pool.build_pool(doc)
        manifest.write_jsonl(manifest.work(data_dir, "pools", f"{doc['doc_id']}.jsonl"), records)
        labels = [
            {"pair_id": r["pair_id"], "label": "UNRELATED", "general": None, "referrer": None,
             "span_a": None, "span_b": None, "grounded": True, "label_invalid": False,
             "invalid_reason": None, "requested_model": "gpt-4o-mini",
             "served_model": "gpt-4o-mini-2024-07-18", "prompt_version": "pairs-labeler-v1",
             "request_digest": "0" * 64}
            for r in records
        ]
        manifest.write_jsonl(manifest.work(data_dir, "labels", f"{doc['doc_id']}.jsonl"), labels)
    manifest.write_json(manifest.work(data_dir, "pool_stats.json"), stats)
    manifest.write_json(
        manifest.work(data_dir, "clusters.json"),
        corpus.near_duplicate_clusters(docs),
    )
    return docs


def test_verify_detects_tamper(tmp_path: Path):
    data_dir, repo_manifest = tmp_path / "data", tmp_path / "manifest.json"
    docs = _stage(data_dir)
    frozen = manifest.freeze(data_dir, repo_manifest)

    assert manifest.verify(data_dir, repo_manifest) == []
    assert {d["doc_id"] for d in frozen["docs"]} == {d["doc_id"] for d in docs}
    assert frozen["labeler"]["family"] == "openai"
    entry = frozen["docs"][0]
    doc_dir = data_dir / entry["split"] / entry["doc_id"]
    assert sorted(p.name for p in doc_dir.iterdir()) == ["doc.json", "labels.gpt.jsonl",
                                                          "pool.jsonl"]

    labels = doc_dir / "labels.gpt.jsonl"
    labels.write_text(labels.read_text("utf-8").replace("UNRELATED", "CONFLICT", 1), "utf-8")
    (data_dir / "heldout" / "pd-stray").mkdir(parents=True)
    problems = manifest.verify(data_dir, repo_manifest)
    assert any("labels.gpt.jsonl" in p and "sha256" in p for p in problems)
    assert any("pd-stray" in p for p in problems)

    other = frozen["docs"][1]
    for f in (data_dir / other["split"] / other["doc_id"]).iterdir():
        f.unlink()
    (data_dir / other["split"] / other["doc_id"]).rmdir()
    assert any(other["doc_id"] in p and "missing" in p for p in manifest.verify(data_dir,
                                                                                repo_manifest))


def _strings(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _strings(v)
    elif isinstance(value, list):
        for v in value:
            yield from _strings(v)
    elif isinstance(value, str):
        yield value


def _keys(value):
    if isinstance(value, dict):
        for k, v in value.items():
            yield k
            yield from _keys(v)
    elif isinstance(value, list):
        for v in value:
            yield from _keys(v)


def _assert_no_text(data: dict) -> None:
    assert not TEXT_KEYS & set(_keys(data))
    assert all(len(s) <= 300 for s in _strings(data))


def test_frozen_manifest_shape_has_no_text(tmp_path: Path):
    _stage(tmp_path / "data")
    frozen = manifest.freeze(tmp_path / "data", tmp_path / "manifest.json")

    _assert_no_text(json.loads((tmp_path / "manifest.json").read_text("utf-8")))
    assert frozen["schema"] == "contract-graph-pairs-dataset/1"
    for key in ("extension_s4", "review_selection", "heldout_review"):
        assert frozen[key] is None
    assert frozen["pool_seed"] == pool.POOL_SEED
    assert (tmp_path / "manifest.json").read_bytes().count(b"\r\n") == 0


def test_committed_manifest_has_no_text():
    data = json.loads(COMMITTED_MANIFEST.read_text(encoding="utf-8"))

    _assert_no_text(data)
    assert data["schema"] == "contract-graph-pairs-dataset/1"
    assert data["labeler"]["family"] == "openai"


def test_cli_verify_exit_codes(tmp_path: Path):
    data_dir, repo_manifest = tmp_path / "data", tmp_path / "manifest.json"
    _stage(data_dir)
    frozen = manifest.freeze(data_dir, repo_manifest)
    args = ["verify", "--data-dir", str(data_dir), "--manifest", str(repo_manifest)]

    assert run.main(args) == 0
    entry = frozen["docs"][0]
    (data_dir / entry["split"] / entry["doc_id"] / "pool.jsonl").write_text("", "utf-8")
    assert run.main(args) == 2
    assert run.main(["verify", "--data-dir", str(data_dir),
                     "--manifest", str(tmp_path / "absent.json")]) == 2


def test_sources_schema():
    data = json.loads((PAIRS_DIR / "sources.json").read_text(encoding="utf-8"))
    sources = data["sources"]

    assert len(sources) >= 15
    assert len({s["url"] for s in sources}) == len(sources)
    for s in sources:
        assert set(s) == {"url", "profile", "title", "has_annex_section", "note"}, s
        assert s["profile"] in ("SALES", "SUPPLY_SERVICE")
        assert s["url"].startswith("https://")
        assert s["has_annex_section"] in (True, False, None)
        assert s["title"]
    for profile in ("SALES", "SUPPLY_SERVICE"):
        assert sum(1 for s in sources if s["profile"] == profile) >= 6
    spike = corpus.load_spike()
    assert not {corpus.normalize_url(s["url"]) for s in sources} & spike.urls


def _git_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init", "-q", str(repo)], check=True)
    (repo / ".gitignore").write_text("/ignored/\n/evals/cache/\n", encoding="utf-8")
    return repo


def test_ensure_outside_repo(tmp_path: Path):
    repo = _git_repo(tmp_path)

    manifest.ensure_outside_repo(repo / "ignored" / "pairs", repo_root=repo)
    for bad in (repo / "tracked" / "pairs", repo / "evals" / "cache" / "pairs"):
        with pytest.raises(SystemExit) as excinfo:
            manifest.ensure_outside_repo(bad, repo_root=repo)
        assert excinfo.value.code == 2
