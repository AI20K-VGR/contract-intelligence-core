"""CLI for the pair-label dataset (P1). Run from the repo root:

  python -m evals.contract_graph.pairs.run fetch      # sources → raw cache
  python -m evals.contract_graph.pairs.run build      # cache → segmented docs (offline)
  python -m evals.contract_graph.pairs.run cluster    # near-duplicate clusters
  python -m evals.contract_graph.pairs.run pool       # S1–S3 pools, prints the pool sha256
  python -m evals.contract_graph.pairs.run label [--env-file F]   # GPT labels (cached)
  python -m evals.contract_graph.pairs.run summary    # reports/l2-p1-dataset.{json,md}
  python -m evals.contract_graph.pairs.run freeze     # split dirs + pairs/manifest.json
  python -m evals.contract_graph.pairs.run verify     # exit 0 ok, 2 on any mismatch

``--data-dir`` defaults to ``$AI2_CG_PAIRS_DATA_DIR`` then ``.harness/state/contract-graph-pairs``;
every writing command checks first that it is git-ignored and outside tracked trees (exit 2).
"""

from __future__ import annotations

import argparse
import os
import shutil
import sys
from collections import Counter
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

from evals.contract_graph.dataset import CacheMiss, fetch_cached
from evals.contract_graph.pairs import corpus, labeler, manifest, pool
from evals.contract_graph.score import rate

PAIRS_DIR = Path(__file__).resolve().parent
DEFAULT_SOURCES = PAIRS_DIR / "sources.json"
DEFAULT_REPORT = PAIRS_DIR.parent / "reports" / "l2-p1-dataset"
USABLE_MIN, PROFILE_MIN, HELDOUT_MIN, DEV_MIN = 15, 6, 10, 5
NL = "\n"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.contract_graph.pairs.run")
    sub = parser.add_subparsers(dest="command", required=True)
    for name in ("fetch", "build", "cluster", "pool", "label", "summary", "freeze", "verify"):
        cmd = sub.add_parser(name)
        cmd.add_argument("--data-dir", type=Path, default=None)
        if name in ("fetch", "build", "summary"):
            cmd.add_argument("--sources", type=Path, default=DEFAULT_SOURCES)
        if name in ("freeze", "verify"):
            cmd.add_argument("--manifest", type=Path, default=manifest.REPO_MANIFEST)
        if name == "label":
            cmd.add_argument("--env-file", type=Path, default=None)
            cmd.add_argument("--workers", type=int, default=8)
        if name == "summary":
            cmd.add_argument("--report-prefix", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args(argv)
    args.data_dir = args.data_dir or Path(
        os.environ.get(manifest.DATA_DIR_ENV) or manifest.DEFAULT_DATA_DIR
    )
    if args.command == "verify":
        return _verify(args)
    manifest.ensure_outside_repo(args.data_dir)
    return {
        "fetch": _fetch, "build": _build, "cluster": _cluster, "pool": _pool,
        "label": _label, "summary": _summary, "freeze": _freeze,
    }[args.command](args)


def _sources(path: Path) -> list[dict]:
    return manifest.read_json(path)["sources"]


def _raw_cache(data_dir: Path) -> Path:
    return Path(data_dir) / "cache" / "raw"


def _fetch(args: argparse.Namespace) -> int:
    sources = _sources(args.sources)
    failed = []
    for source in sources:
        try:
            fetch_cached(source["url"], _raw_cache(args.data_dir))
        except (OSError, ValueError) as exc:
            failed.append(source["url"])
            print(f"fetch failed: {source['url']}: {type(exc).__name__}: {exc}", file=sys.stderr)
    print(f"cached {len(sources) - len(failed)}/{len(sources)} sources")
    return 1 if failed else 0


def _build(args: argparse.Namespace) -> int:
    docs_dir = manifest.work(args.data_dir, "docs")
    if docs_dir.exists():
        shutil.rmtree(docs_dir)
    usable, rejected, failed = [], [], []
    for source in _sources(args.sources):
        try:
            text, tail = corpus.fetch(source, _raw_cache(args.data_dir), offline=True)
            doc = corpus.build_doc(source, text)
        except corpus.RejectedDocument as exc:
            rejected.append({"url": source["url"], "profile": source["profile"],
                             "n_articles": exc.n_articles})
            continue
        except (CacheMiss, OSError, ValueError) as exc:
            failed.append({"url": source["url"], "profile": source["profile"],
                           "error": type(exc).__name__})
            continue
        doc["contaminated"] = corpus.contaminated(doc)
        manifest.write_json(docs_dir / f"{doc['doc_id']}.json", doc)
        usable.append({"doc_id": doc["doc_id"], "url": doc["url"], "profile": doc["profile"],
                       "n_articles": doc["n_articles"], "n_nodes": len(doc["nodes"]),
                       "has_annex": doc["has_annex"], "contaminated": doc["contaminated"],
                       "tail_boundary": tail.boundary, "tail_trimmed_chars": tail.trimmed_chars})
    manifest.write_json(manifest.work(args.data_dir, "build.json"),
                        {"usable": usable, "rejected_segmentation": rejected, "failed": failed})
    by_profile = Counter(d["profile"] for d in usable)
    tails = _tail_counts(usable)
    print(f"usable {len(usable)} {dict(sorted(by_profile.items()))}; "
          f"rejected_segmentation {len(rejected)}; failed {len(failed)}; "
          f"tail_trimmed {tails['tail_trimmed']} ({tails['tail_trimmed_chars']} chars); "
          f"tail_untrimmed {tails['tail_untrimmed']}")
    return 0


def _tail_counts(usable: list[dict]) -> dict:
    """Web sources cut (``tail_trimmed``) and web sources with no reliable boundary, kept whole
    (``tail_untrimmed``); docx sources are in neither."""

    return {
        "tail_trimmed": sum(1 for u in usable if u["tail_trimmed_chars"] > 0),
        "tail_untrimmed": sum(1 for u in usable if u["tail_boundary"] is None),
        "tail_trimmed_chars": sum(u["tail_trimmed_chars"] for u in usable),
        "tail_by_boundary": _count(str(u["tail_boundary"]) for u in usable),
    }


def _docs(data_dir: Path) -> list[dict]:
    return [manifest.read_json(p) for p in sorted(manifest.work(data_dir, "docs").glob("*.json"))]


def _cluster(args: argparse.Namespace) -> int:
    clusters = corpus.near_duplicate_clusters(_docs(args.data_dir))
    manifest.write_json(manifest.work(args.data_dir, "clusters.json"), clusters)
    multi = [c for c in clusters if len(c["doc_ids"]) > 1]
    print(f"{len(clusters)} clusters; near-duplicate clusters {len(multi)} "
          f"({sum(len(c['doc_ids']) for c in multi)} docs)")
    return 0


def _pool(args: argparse.Namespace) -> int:
    pools_dir = manifest.work(args.data_dir, "pools")
    if pools_dir.exists():
        shutil.rmtree(pools_dir)
    stats, everything = {}, []
    for doc in _docs(args.data_dir):
        records, stats[doc["doc_id"]] = pool.build_pool(doc)
        manifest.write_jsonl(pools_dir / f"{doc['doc_id']}.jsonl", records)
        everything.extend(records)
    manifest.write_json(manifest.work(args.data_dir, "pool_stats.json"), stats)
    by_stratum = Counter(r["stratum"] for r in everything)
    print(f"pairs {len(everything)} {dict(sorted(by_stratum.items()))}; excluded_luong1 "
          f"{sum(s['excluded_luong1'] for s in stats.values())}")
    print(f"pool_sha256 {pool.pool_digest(everything)}")
    return 0


def _label(args: argparse.Namespace) -> int:
    config = labeler.load_config(args.env_file)
    client = labeler.OpenAICompatClient(config)
    cache_dir = Path(args.data_dir) / "cache" / "labeler"
    errors = labeled = 0
    for doc in _docs(args.data_dir):
        records = manifest.read_jsonl(manifest.work(args.data_dir, "pools",
                                                    f"{doc['doc_id']}.jsonl"))
        nodes = {n["node_id"]: n for n in doc["nodes"]}

        def one(pair: dict) -> dict | None:
            try:
                return labeler.label_pair(pair, nodes[pair["a"]], nodes[pair["b"]],
                                          client=client, model=config.model, cache_dir=cache_dir)
            except labeler.LabelerCallError as exc:
                print(f"label failed: {pair['pair_id']}: {exc}", file=sys.stderr)
                return None

        with ThreadPoolExecutor(max_workers=max(1, args.workers)) as executor:
            results = list(executor.map(one, records))
        out = sorted((r for r in results if r is not None), key=lambda r: r["pair_id"])
        errors += len(records) - len(out)
        labeled += len(out)
        manifest.write_jsonl(manifest.work(args.data_dir, "labels", f"{doc['doc_id']}.jsonl"), out)
        print(f"{doc['doc_id']}: {len(out)}/{len(records)} labeled")
    print(f"labeled {labeled}; call errors {errors}")
    return 1 if errors else 0


def _summary(args: argparse.Namespace) -> int:
    report = build_summary(args.data_dir, args.sources)
    prefix = Path(args.report_prefix)
    manifest.write_json(prefix.with_suffix(".json"), report)
    prefix.with_suffix(".md").parent.mkdir(parents=True, exist_ok=True)
    with open(prefix.with_suffix(".md"), "w", encoding="utf-8", newline=NL) as fh:
        fh.write(render_summary(report))
    est = report["hg1_estimate"]
    print(f"HG-1 rows (before S4): {est['total_rows']} / cap {est['row_cap']}; "
          f"floors met: {report['floors']['met']}")
    if est["over_cap"]:
        print("HG-1 estimate over the 380-row cap: stop before freeze and ask the user",
              file=sys.stderr)
        return 1
    return 0


def build_summary(data_dir: Path, sources_path: Path) -> dict:
    stage = manifest.load_stage(data_dir)
    docs, pools, labels = stage["docs"], stage["pools"], stage["labels"]
    build = manifest.read_json(manifest.work(data_dir, "build.json"))
    stats = manifest.read_json(manifest.work(data_dir, "pool_stats.json"))
    sources = _sources(sources_path)
    built = {u["doc_id"]: u for u in build["usable"]}
    contaminated = {d for d, doc in docs.items() if doc.get("contaminated")}
    splits, split_stats = manifest.assign_splits(
        stage["clusters"], contaminated, {d: doc["url"] for d, doc in docs.items()}
    )
    cluster_of = {d: c["cluster_id"] for c in stage["clusters"] for d in c["doc_ids"]}
    multi = [c for c in stage["clusters"] if len(c["doc_ids"]) > 1]
    all_pool = [r for d in sorted(pools) for r in pools[d]]
    all_labels = [r for d in sorted(labels) for r in labels[d]]
    stratum_of = {r["pair_id"]: r["stratum"] for r in all_pool}
    split_of = {r["pair_id"]: splits[r["doc_id"]] for r in all_pool}
    valid = [r for r in all_labels if not r.get("label_invalid")]
    needs_span = [r for r in valid if r["label"] != labeler.UNRELATED]
    by_profile = Counter(doc["profile"] for doc in docs.values())
    by_split = Counter(splits.values())
    floors_met = (
        len(docs) >= USABLE_MIN
        and all(by_profile[p] >= PROFILE_MIN for p in corpus.PROFILES)
        and by_split["heldout"] >= HELDOUT_MIN
        and by_split["dev"] >= DEV_MIN
        and not any(splits[d] == "heldout" for d in contaminated)
    )
    return {
        "schema": "contract-graph-pairs-summary/1",
        "ground_truth": manifest.GROUND_TRUTH,
        "sources": {
            "listed": len(sources),
            "listed_by_profile": _count(s["profile"] for s in sources),
            "usable": len(docs),
            "rejected_segmentation": len(build["rejected_segmentation"]),
            "rejected_segmentation_detail": [
                {"url": r["url"], "n_articles": r["n_articles"]}
                for r in build["rejected_segmentation"]
            ],
            "failed": len(build["failed"]),
            **_tail_counts(build["usable"]),
        },
        "floors": {"usable_min": USABLE_MIN, "per_profile_min": PROFILE_MIN,
                   "heldout_min": HELDOUT_MIN, "dev_min": DEV_MIN, "met": floors_met},
        "docs": {
            "by_profile": _count(doc["profile"] for doc in docs.values()),
            "by_split": _count(splits.values()),
            "by_profile_split": _count(f"{doc['profile']}/{splits[d]}" for d, doc in docs.items()),
            "with_annex": sum(1 for doc in docs.values() if doc["has_annex"]),
        },
        "clusters": {
            "n": len(stage["clusters"]),
            "near_duplicate_clusters": len(multi),
            "docs_in_near_duplicate_clusters": sum(len(c["doc_ids"]) for c in multi),
            "by_split": _count(splits[c["doc_ids"][0]] for c in stage["clusters"]),
        },
        "split_stats": split_stats,
        "contaminated_docs": len(contaminated),
        "forced_dev_contaminated": split_stats["forced_dev_contaminated"],
        "contaminated_in_heldout": sum(1 for d in contaminated if splits[d] == "heldout"),
        "pairs": {
            "total": len(all_pool),
            "by_stratum": _count(r["stratum"] for r in all_pool),
            "by_split_stratum": _count(f"{split_of[r['pair_id']]}/{r['stratum']}"
                                       for r in all_pool),
            "universe_by_stratum": {
                s: sum(v[f"{s}_universe"] for v in stats.values()) for s in pool.STRATA
            },
        },
        "excluded_luong1": sum(v["excluded_luong1"] for v in stats.values()),
        "pool_sha256": pool.pool_digest(all_pool),
        "labels": {
            "labeled": len(all_labels),
            "unlabeled": len(all_pool) - len(all_labels),
            "by_split_label": _count(f"{split_of[r['pair_id']]}/{r['label']}" for r in valid),
            "by_stratum_label": _count(f"{stratum_of[r['pair_id']]}/{r['label']}"
                                       for r in valid),
            "label_invalid": rate(len(all_labels) - len(valid), len(all_labels)),
            "label_invalid_by_reason": _count(r["invalid_reason"] for r in all_labels
                                              if r.get("label_invalid")),
            "grounded_false": rate(sum(1 for r in needs_span if not r["grounded"]),
                                   len(needs_span)),
            "grounded_false_scope": "nhãn hợp lệ ≠ UNRELATED (span bắt buộc)",
        },
        "labeler": manifest.labeler_block(all_labels),
        "hg1_estimate": pool.estimate_review_rows(all_pool, all_labels),
        "per_doc": [
            {
                "doc_id": d,
                "profile": doc["profile"],
                "split": splits[d],
                "cluster_id": cluster_of[d],
                "n_articles": doc["n_articles"],
                "n_nodes": len(doc["nodes"]),
                "has_annex": doc["has_annex"],
                "tail_trimmed_chars": built[d]["tail_trimmed_chars"],
                "contaminated": d in contaminated,
                "pairs_by_stratum": _count(r["stratum"] for r in pools[d]),
                "labels_by_label": _count(r["label"] for r in labels[d]
                                          if not r.get("label_invalid")),
            }
            for d, doc in sorted(docs.items())
        ],
    }


def _count(values) -> dict:
    return dict(sorted(Counter(values).items()))


def render_summary(report: dict) -> str:
    src, docs, cl, pairs, lab = (report["sources"], report["docs"], report["clusters"],
                                 report["pairs"], report["labels"])
    est, model = report["hg1_estimate"], report["labeler"]
    lines = [
        "# Contract graph luồng 2 — P1 bộ nhãn cặp",
        "",
        f"- Ground truth: `{report['ground_truth']}` — nhãn GPT chưa duyệt, không phải độ chính "
        "xác nghiệp vụ.",
        f"- Người gán nhãn: yêu cầu `{model['requested_model']}`, phục vụ "
        f"`{model['served_model']}`, họ `{model['family']}`, prompt `{model['prompt_version']}`.",
        f"- Pool sha256: `{report['pool_sha256']}`",
        "",
        "## Nguồn và văn bản",
        "",
        f"- Nguồn liệt kê {src['listed']} {src['listed_by_profile']}; dùng được {src['usable']}; "
        f"loại do tách < 5 Điều {src['rejected_segmentation']}; lỗi tải/đọc {src['failed']}.",
        f"- Cắt đuôi trang web: `tail_trimmed` {src['tail_trimmed']} "
        f"({src['tail_trimmed_chars']} ký tự), `tail_untrimmed` {src['tail_untrimmed']} "
        f"(không có ranh giới tin cậy, giữ nguyên); theo ranh giới {src['tail_by_boundary']}.",
        f"- Theo profile: {docs['by_profile']}; theo split: {docs['by_split']}; "
        f"profile/split: {docs['by_profile_split']}; có Phụ lục: {docs['with_annex']}.",
        f"- Ngưỡng (≥{report['floors']['usable_min']} dùng được, ≥"
        f"{report['floors']['per_profile_min']}/profile, held-out ≥"
        f"{report['floors']['heldout_min']}, dev ≥{report['floors']['dev_min']}, không nhiễm bẩn "
        f"trong held-out): **{'đạt' if report['floors']['met'] else 'KHÔNG đạt'}**.",
        "",
        "## Cụm và nhiễm bẩn (RT-13)",
        "",
        f"- Cụm: {cl['n']} (held-out/dev: {cl['by_split']}); cụm gần trùng "
        f"{cl['near_duplicate_clusters']} gồm {cl['docs_in_near_duplicate_clusters']} văn bản.",
        f"- Văn bản nhiễm bẩn: {report['contaminated_docs']}; ép dev "
        f"(`forced_dev_contaminated`): {report['forced_dev_contaminated']}; nhiễm bẩn trong "
        f"held-out: {report['contaminated_in_heldout']}.",
        "",
        "## Pool (D17)",
        "",
        f"- Cặp: {pairs['total']} — theo tầng {pairs['by_stratum']}; split/tầng "
        f"{pairs['by_split_stratum']}; vũ trụ trước trần/mẫu {pairs['universe_by_stratum']}.",
        f"- `excluded_luong1`: {report['excluded_luong1']}.",
        "",
        "## Nhãn GPT",
        "",
        f"- Đã gán {lab['labeled']}, chưa gán (lỗi gọi) {lab['unlabeled']}.",
        f"- Split/nhãn: {lab['by_split_label']}",
        f"- Tầng/nhãn: {lab['by_stratum_label']}",
        f"- `label_invalid`: {_fmt(lab['label_invalid'])} {lab['label_invalid_by_reason']}",
        f"- `grounded=false` ({lab['grounded_false_scope']}): {_fmt(lab['grounded_false'])}",
        "",
        "## Ước số dòng HG-1 (D18, chưa gồm S4 — P2 cập nhật)",
        "",
        "| nhãn | GPT | chọn |",
        "| --- | --- | --- |",
    ]
    for label, row in est["by_label"].items():
        lines.append(f"| {label} | {row['gpt_positive']} | {row['selected']} |")
    lines += [
        f"| UNRELATED | {est['unrelated']['gpt_unrelated']} | {est['unrelated']['selected']} "
        f"{est['unrelated']['by_stratum']} |",
        "",
        f"- Tổng: **{est['total_rows']}** / trần {est['row_cap']}.",
        "",
        "## Theo văn bản",
        "",
        "| doc_id | profile | split | cluster | Điều | node | phụ lục | cắt đuôi | cặp theo tầng "
        "| nhãn |",
        "| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |",
    ]
    for d in report["per_doc"]:
        lines.append(
            f"| {d['doc_id']} | {d['profile']} | {d['split']} | {d['cluster_id']} | "
            f"{d['n_articles']} | {d['n_nodes']} | {'có' if d['has_annex'] else '—'} | "
            f"{d['tail_trimmed_chars']} | "
            f"{d['pairs_by_stratum']} | {d['labels_by_label']} |"
        )
    return NL.join(lines) + NL


def _fmt(r: dict) -> str:
    if not r["denominator"]:
        return "0/0"
    lo, hi = r["wilson95"]
    return f"{r['passed']}/{r['denominator']} ({r['rate']:.3f}; Wilson95 {lo:.3f}–{hi:.3f})"


def _freeze(args: argparse.Namespace) -> int:
    frozen = manifest.freeze(args.data_dir, args.manifest)
    print(f"froze {len(frozen['docs'])} docs ({_count(d['split'] for d in frozen['docs'])}) "
          f"-> {args.manifest}")
    return 0


def _verify(args: argparse.Namespace) -> int:
    problems = manifest.verify(args.data_dir, args.manifest)
    for problem in problems:
        print(problem, file=sys.stderr)
    if problems:
        return 2
    print(f"verify ok: {args.manifest}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
