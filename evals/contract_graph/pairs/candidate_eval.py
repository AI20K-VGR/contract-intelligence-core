"""P2 of luồng 2: structural pair candidates measured on dev, the held-out S4 stratum, and the
locked HG-1 review sample.

``measure_dev`` scores ``generate_pair_candidates`` (the runtime code, uncapped) against the
GPT-labelled dev pool: recall by source (and the part only that source finds), by P1 stratum,
by label, and recall@K over ``K_GRID``; ``choose_top_k`` takes the smallest K reaching 95% of
the uncapped recall. ``extend_heldout`` is the only P2 reader of held-out: after ``verify`` and
a version check against the dev report it builds S4 = (B ∪ C) − pool per doc, has GPT label it
and records the file digests in the manifest. ``review_select`` locks the D18 sample in the
manifest before ``review_export`` may write the sheet.
"""

from __future__ import annotations

import sys
from collections import Counter
from collections.abc import Callable, Iterable, Mapping
from pathlib import Path

from evals.contract_graph.dataset import file_digest
from evals.contract_graph.pairs import labeler, manifest, pool, review
from evals.contract_graph.pairs.corpus import AI_SERVICE
from evals.contract_graph.score import rate

if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

from app.contracts.models import StructuralNode  # noqa: E402
from app.pipeline.contract_graph.pair_candidates import (  # noqa: E402
    ALL_SOURCES,
    CANDIDATES_VERSION,
    PAIRS_TOP_K,
    PairCandidateSet,
    PairSource,
    generate_pair_candidates,
)
from app.pipeline.contract_graph.resolver import StructureIndex  # noqa: E402

K_GRID = (10, 20, 30, 40, 60, 80)
UNCAPPED = 10**6
RECALL_SHARE = 0.95
VARIANT_B = frozenset({PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF})
GROUND_TRUTH = "gpt-labels (approved=false), dev"
S4 = "S4"
S4_FILES = ("s4.jsonl", "labels.s4.gpt.jsonl")
REVIEW_DIR = "review"
SELECTION = "selection.jsonl"
SHEET = "heldout_review.csv"
_NODE_FIELDS = ("node_id", "type", "raw_label", "parent_id", "order", "text", "source_file_id",
                "page_range")

LabelFn = Callable[[dict, dict, dict], dict]


def doc_record(doc: dict) -> tuple[list[StructuralNode], StructureIndex, frozenset]:
    """Nodes, index (the doc file in role ``body``) and luồng-1 pairs of one segmented doc."""

    nodes = [StructuralNode(**{k: n[k] for k in _NODE_FIELDS if k in n}) for n in doc["nodes"]]
    index = StructureIndex.build(nodes, {doc["doc_id"]: "body"})
    return nodes, index, frozenset(pool.luong1_pairs(doc))


def doc_candidates(
    doc: dict, *, top_k: int, sources: frozenset[PairSource] = ALL_SOURCES
) -> PairCandidateSet:
    nodes, index, excluded = doc_record(doc)
    return generate_pair_candidates(index, nodes, excluded_pairs=excluded, top_k=top_k,
                                    sources=sources)


def _key(a: str, b: str) -> frozenset[str]:
    return frozenset((a, b))


def _gold(entry: Mapping) -> dict[frozenset[str], dict]:
    """GPT-positive pool pairs of one doc: pair → ``{stratum, label}``."""

    pooled = {r["pair_id"]: r for r in entry["pool"]}
    gold = {}
    for record in entry["labels"]:
        pair = pooled.get(record["pair_id"])
        if pair is None or record.get("label_invalid") or record.get("label") not in review.LABELS:
            continue
        if record["label"] == labeler.UNRELATED:
            continue
        gold[_key(pair["a"], pair["b"])] = {"stratum": pair["stratum"], "label": record["label"]}
    return gold


def measure_dev(entries: Iterable[Mapping], *, k_grid: tuple[int, ...] = K_GRID) -> dict:
    """Recall of uncapped candidates on the dev GPT positives; no clause text in the result."""

    covered = Counter()
    by_source: Counter[str] = Counter()
    only_source: Counter[str] = Counter()
    at_k: Counter[int] = Counter()
    cells: dict[str, Counter] = {"stratum": Counter(), "label": Counter()}
    cell_hits: dict[str, Counter] = {"stratum": Counter(), "label": Counter()}
    per_doc, totals = [], Counter()
    n_gold = 0
    for entry in entries:
        doc = entry["doc"]
        gold = _gold(entry)
        result = doc_candidates(doc, top_k=UNCAPPED)
        ranked = [(_key(c.node_a, c.node_b), c.sources) for c in result.candidates]
        sources_of = dict(ranked)
        rank_of = {pair: i for i, (pair, _) in enumerate(ranked)}
        hits = 0
        for pair, cell in gold.items():
            cells["stratum"][cell["stratum"]] += 1
            cells["label"][cell["label"]] += 1
            found = sources_of.get(pair)
            if found is None:
                continue
            hits += 1
            cell_hits["stratum"][cell["stratum"]] += 1
            cell_hits["label"][cell["label"]] += 1
            for source in found:
                by_source[source.value] += 1
            if len(found) == 1:
                only_source[next(iter(found)).value] += 1
            for k in k_grid:
                at_k[k] += rank_of[pair] < k
        n_gold += len(gold)
        covered["passed"] += hits
        for key, value in result.stats.items():
            if isinstance(value, int):
                totals[key] += value
        per_doc.append({"doc_id": doc["doc_id"], "gold": len(gold), "covered": hits,
                        "candidates": result.stats["candidates_total"]})
    counts = sorted(d["candidates"] for d in per_doc)
    return {
        "schema": "contract-graph-pairs-candidates/1",
        "ground_truth": GROUND_TRUTH,
        "split": "dev",
        "n_docs": len(per_doc),
        "recall_full": rate(covered["passed"], n_gold),
        "by_source": {s.value: rate(by_source[s.value], n_gold) for s in PairSource},
        "by_source_marginal": {s.value: rate(only_source[s.value], n_gold) for s in PairSource},
        "by_stratum": {s: rate(cell_hits["stratum"][s], n) for s, n in sorted(cells["stratum"].items())},
        "by_label": {lab: rate(cell_hits["label"][lab], n) for lab, n in sorted(cells["label"].items())},
        "recall_at_k": {str(k): rate(at_k[k], n_gold) for k in k_grid},
        "candidates_per_doc": {
            "min": counts[0] if counts else 0,
            "median": counts[len(counts) // 2] if counts else 0,
            "max": counts[-1] if counts else 0,
            "total": sum(counts),
        },
        "stats_total": dict(sorted(totals.items())),
        "per_doc": per_doc,
    }


def choose_top_k(passed_at_k: Mapping[int, int], passed_full: int) -> tuple[int, str]:
    """Smallest K of the grid whose recall reaches ``RECALL_SHARE`` of the uncapped recall."""

    for k in sorted(passed_at_k):
        if passed_full and passed_at_k[k] >= RECALL_SHARE * passed_full:
            return k, f"K nhỏ nhất có recall@K ≥ {RECALL_SHARE} × recall không cắt"
    return PAIRS_TOP_K, f"không K ≤ {max(passed_at_k)} nào đạt {RECALL_SHARE} × recall không cắt; giữ {PAIRS_TOP_K}"


# -- held-out S4 ---------------------------------------------------------------------------------


def s4_records(entry: Mapping, *, top_k: int = PAIRS_TOP_K) -> list[dict]:
    """(B ∪ C) − pool of one held-out doc, in document order, stratum ``S4``."""

    doc = entry["doc"]
    order = {n["node_id"]: n["order"] for n in doc["nodes"]}
    pooled = {_key(r["a"], r["b"]) for r in entry["pool"]}
    variants: dict[frozenset[str], set[str]] = {}
    for name, sources in (("B", VARIANT_B), ("C", ALL_SOURCES)):
        for c in doc_candidates(doc, top_k=top_k, sources=sources).candidates:
            variants.setdefault(_key(c.node_a, c.node_b), set()).add(name)
    out = []
    for pair, names in variants.items():
        if pair in pooled:
            continue
        a, b = sorted(pair, key=lambda nid: (order[nid], nid))
        out.append({"pair_id": pool.pair_id_for(doc["doc_id"], a, b), "doc_id": doc["doc_id"],
                    "a": a, "b": b, "stratum": S4, "variants": sorted(names)})
    return sorted(out, key=lambda r: (order[r["a"]], order[r["b"]]))


def _check_versions(report_path: Path) -> None:
    report = manifest.read_json(report_path)
    found = (report.get("candidates_version"), report.get("pairs_top_k"))
    if found != (CANDIDATES_VERSION, PAIRS_TOP_K):
        print(f"{report_path}: candidates {found} != code ({CANDIDATES_VERSION}, {PAIRS_TOP_K}); "
              "candidate code changed after the dev freeze", file=sys.stderr)
        raise SystemExit(2)


def extend_heldout(
    data_dir: Path, repo_manifest: Path, report_path: Path, *, label_fn: LabelFn
) -> dict:
    """Build and label S4 for every held-out doc; record it in ``extension_s4``."""

    entries = manifest.read_split(data_dir, "heldout", repo_manifest)  # verify first, exit 2
    _check_versions(report_path)
    files, labels_by_label, all_labels, n_pairs = {}, Counter(), [], 0
    for entry in entries:
        doc = entry["doc"]
        nodes = {n["node_id"]: n for n in doc["nodes"]}
        records = s4_records(entry)
        labels = sorted((label_fn(r, nodes[r["a"]], nodes[r["b"]]) for r in records),
                        key=lambda r: r["pair_id"])
        out = Path(data_dir) / "heldout" / doc["doc_id"]
        manifest.write_jsonl(out / S4_FILES[0], records)
        manifest.write_jsonl(out / S4_FILES[1], labels)
        files[doc["doc_id"]] = {name: file_digest(out / name) for name in S4_FILES}
        labels_by_label.update(r["label"] if not r.get("label_invalid") else "INVALID"
                               for r in labels)
        all_labels.extend(labels)
        n_pairs += len(records)
    block = {
        "candidates_version": CANDIDATES_VERSION,
        "top_k": PAIRS_TOP_K,
        "variants": {"B": sorted(s.value for s in VARIANT_B),
                     "C": sorted(s.value for s in ALL_SOURCES)},
        "files": dict(sorted(files.items())),
        "n_pairs": n_pairs,
        "labels_by_label": dict(sorted(labels_by_label.items())),
        "labeler": manifest.labeler_block(all_labels),
    }
    data = manifest.read_json(repo_manifest)
    data["extension_s4"] = block
    data["review_selection"] = None  # any earlier sample predates this S4
    manifest.write_json(repo_manifest, data)
    return block


def production_label_fn(data_dir: Path, env_file: Path | None = None) -> LabelFn:
    config = labeler.load_config(env_file)
    client = labeler.OpenAICompatClient(config)
    cache_dir = Path(data_dir) / "cache" / "labeler"

    def label(pair: dict, node_a: dict, node_b: dict) -> dict:
        return labeler.label_pair(pair, node_a, node_b, client=client, model=config.model,
                                  cache_dir=cache_dir)

    return label


# -- HG-1 sample ---------------------------------------------------------------------------------


def _heldout_rows(data_dir: Path, repo_manifest: Path) -> tuple[list[dict], dict, dict]:
    """Held-out labelled pairs S1–S4 (pair fields merged in), labels by pair, nodes by id."""

    entries = manifest.read_split(data_dir, "heldout", repo_manifest)
    if not manifest.read_json(repo_manifest).get("extension_s4"):
        print("no extension_s4 in the manifest: run extend-heldout first", file=sys.stderr)
        raise SystemExit(2)
    rows, labels_by_pair, nodes_by_id = [], {}, {}
    for entry in entries:
        doc = entry["doc"]
        doc_dir = Path(data_dir) / "heldout" / doc["doc_id"]
        pairs = {r["pair_id"]: r for r in entry["pool"]}
        pairs.update({r["pair_id"]: r for r in manifest.read_jsonl(doc_dir / S4_FILES[0])})
        labels = [*entry["labels"], *manifest.read_jsonl(doc_dir / S4_FILES[1])]
        for record in labels:
            pair = pairs.get(record["pair_id"])
            if pair is None:
                continue
            rows.append({**pair, **record})
            labels_by_pair[record["pair_id"]] = record
        nodes_by_id.update({n["node_id"]: n for n in doc["nodes"]})
    return rows, labels_by_pair, nodes_by_id


def review_select(data_dir: Path, repo_manifest: Path) -> dict:
    rows, _, _ = _heldout_rows(data_dir, repo_manifest)
    by_stratum: dict[str, list[dict]] = {}
    for row in sorted(rows, key=lambda r: r["pair_id"]):
        by_stratum.setdefault(row["stratum"], []).append(row)
    try:
        selection = review.select_for_review(by_stratum, pool.POOL_SEED)
    except review.ReviewCapExceeded as exc:
        print(f"{exc}; ask the user before changing the sample", file=sys.stderr)
        raise SystemExit(2) from exc
    path = Path(data_dir) / REVIEW_DIR / SELECTION
    manifest.write_jsonl(path, selection)
    pi_table = {f"{r['gpt_label']}/{r['stratum']}": r["pi"] for r in selection}
    block = {
        "sha256": file_digest(path),
        "n_rows": len(selection),
        "seed": pool.POOL_SEED,
        "by_stratum": dict(sorted(Counter(r["stratum"] for r in selection).items())),
        "by_label": dict(sorted(Counter(r["gpt_label"] for r in selection).items())),
        "pi_table": dict(sorted(pi_table.items())),
    }
    data = manifest.read_json(repo_manifest)
    data["review_selection"] = block
    manifest.write_json(repo_manifest, data)
    return block


def review_export(data_dir: Path, repo_manifest: Path) -> int:
    """Write the HG-1 sheet; only from the selection whose digest the manifest locked."""

    locked = manifest.read_json(repo_manifest).get("review_selection")
    path = Path(data_dir) / REVIEW_DIR / SELECTION
    if not locked or not path.is_file() or file_digest(path) != locked.get("sha256"):
        print("review selection is not locked in the manifest (or changed since): run "
              "review-select and commit the manifest first", file=sys.stderr)
        raise SystemExit(2)
    _, labels_by_pair, nodes_by_id = _heldout_rows(data_dir, repo_manifest)
    selection = manifest.read_jsonl(path)
    return review.export_sheet(Path(data_dir) / REVIEW_DIR / SHEET, selection, labels_by_pair,
                               nodes_by_id)
