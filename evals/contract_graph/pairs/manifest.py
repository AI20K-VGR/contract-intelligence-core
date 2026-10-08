"""Freeze the pair dataset outside the repo and lock it with an in-repo, text-free manifest.

Data (docs, pools, GPT labels, caches) lives under ``AI2_CG_PAIRS_DATA_DIR`` (D14):
``work/`` holds the staged CLI outputs, ``freeze`` copies them to ``<split>/<doc_id>/`` and
writes ``evals/contract_graph/pairs/manifest.json`` (URLs, sha256, counts, model, split, seed —
never clause text). ``verify`` re-derives every digest; a reader of a frozen split calls it
first (``read_split``) and stops with exit 2 on any problem. Digests are over LF-normalized
UTF-8 (``dataset.file_digest``).
"""

from __future__ import annotations

import datetime as dt
import hashlib
import json
import shutil
import subprocess
import sys
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path

from evals.contract_graph.dataset import _json_line, _write, file_digest
from evals.contract_graph.pairs.labeler import LABELER_PROMPT_VERSION
from evals.contract_graph.pairs.models import family
from evals.contract_graph.pairs.pool import POOL_PARAMS, POOL_SEED, STRATA

REPO_ROOT = Path(__file__).resolve().parents[3]
REPO_MANIFEST = Path(__file__).resolve().parent / "manifest.json"
DEFAULT_DATA_DIR = REPO_ROOT / ".harness" / "state" / "contract-graph-pairs"
DATA_DIR_ENV = "AI2_CG_PAIRS_DATA_DIR"
SCHEMA = "contract-graph-pairs-dataset/1"
GROUND_TRUTH = (
    f"GPT labeler {LABELER_PROMPT_VERSION} (approved=false; HG-1 human review pending, P2/P5)"
)
SPLITS = ("dev", "heldout")
WORK = "work"
DOC_FILES = ("doc.json", "labels.gpt.jsonl", "pool.jsonl")
FORBIDDEN_UNDER = ("evals", "ai-service", "docs")


def work(data_dir: Path, *parts: str) -> Path:
    return Path(data_dir, WORK, *parts)


def write_json(path: Path, obj: object) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _write(Path(path), json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=True) + "\n")


def write_jsonl(path: Path, records: Iterable[Mapping]) -> None:
    Path(path).parent.mkdir(parents=True, exist_ok=True)
    _write(Path(path), "".join(_json_line(dict(r)) for r in records))


def read_json(path: Path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def read_jsonl(path: Path) -> list[dict]:
    text = Path(path).read_text(encoding="utf-8")
    return [json.loads(line) for line in text.splitlines() if line.strip()]


def ensure_outside_repo(data_dir: Path, repo_root: Path = REPO_ROOT) -> None:
    """Exit 2 unless git ignores ``data_dir`` and it is not under ``evals/``, ``ai-service/`` or
    ``docs/`` (``.harness/`` is ignored only through ``.git/info/exclude``: checked, not assumed)."""

    data_dir, root = Path(data_dir).resolve(), Path(repo_root).resolve()
    try:
        rel = data_dir.relative_to(root)
    except ValueError:
        rel = None
    if rel is not None and rel.parts and rel.parts[0] in FORBIDDEN_UNDER:
        _fail(f"{data_dir} is under {rel.parts[0]}/; pair data must stay outside tracked trees")
    probe = f"{rel.as_posix()}/probe" if rel is not None else str(data_dir / "probe")
    result = subprocess.run(
        ["git", "-C", str(root), "check-ignore", "-q", probe], capture_output=True, text=True
    )
    if result.returncode != 0:
        _fail(f"{data_dir} is not git-ignored (git check-ignore exit {result.returncode})")


def _fail(message: str) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(2)


def assign_splits(
    clusters: Iterable[Mapping], contaminated: set[str], urls: Mapping[str, str]
) -> tuple[dict[str, str], dict]:
    """Whole clusters to one split. A cluster with a contaminated doc ⇒ ``dev``; the others ranked
    by ``min sha256(url)`` of their docs, the first ``ceil(2/3 · n)`` ⇒ ``heldout``."""

    clusters = sorted(clusters, key=lambda c: c["cluster_id"])
    forced = [c for c in clusters if any(d in contaminated for d in c["doc_ids"])]
    rest = sorted(
        (c for c in clusters if c not in forced),
        key=lambda c: (min(_sha(urls[d]) for d in c["doc_ids"]), c["cluster_id"]),
    )
    n_heldout = -(-2 * len(rest) // 3)
    splits: dict[str, str] = {}
    for i, cluster in enumerate(rest):
        for doc_id in cluster["doc_ids"]:
            splits[doc_id] = "heldout" if i < n_heldout else "dev"
    for cluster in forced:
        for doc_id in cluster["doc_ids"]:
            splits[doc_id] = "dev"
    stats = {
        "clusters": len(clusters),
        "heldout_clusters": n_heldout,
        "dev_clusters": len(clusters) - n_heldout,
        "forced_dev_clusters": len(forced),
        "forced_dev_contaminated": sum(len(c["doc_ids"]) for c in forced),
    }
    return splits, stats


def _sha(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def load_stage(data_dir: Path) -> dict:
    """Staged CLI outputs: docs, clusters, pools, labels (labels restricted to pool pairs)."""

    docs = {d["doc_id"]: d for d in (read_json(p) for p in sorted(work(data_dir, "docs").glob("*.json")))}
    clusters = read_json(work(data_dir, "clusters.json"))
    clustered = sorted(d for c in clusters for d in c["doc_ids"])
    if clustered != sorted(docs):
        raise ValueError("clusters.json does not cover exactly the built docs; rerun `cluster`")
    pools, labels = {}, {}
    for doc_id in docs:
        pool_path = work(data_dir, "pools", f"{doc_id}.jsonl")
        if not pool_path.is_file():
            raise ValueError(f"{doc_id}: no pool; rerun `pool`")
        pools[doc_id] = read_jsonl(pool_path)
        in_pool = {r["pair_id"] for r in pools[doc_id]}
        label_path = work(data_dir, "labels", f"{doc_id}.jsonl")
        found = read_jsonl(label_path) if label_path.is_file() else []
        labels[doc_id] = sorted((r for r in found if r["pair_id"] in in_pool),
                                key=lambda r: r["pair_id"])
    return {"docs": docs, "clusters": clusters, "pools": pools, "labels": labels}


def labeler_block(labels: Iterable[Mapping]) -> dict:
    labels = list(labels)
    served = sorted({r["served_model"] for r in labels if r.get("served_model")})
    families = sorted({family(m) for m in served})
    return {
        "requested_model": _one(sorted({r["requested_model"] for r in labels
                                        if r.get("requested_model")})),
        "served_model": _one(served),
        "family": _one(families) if families else "unknown",
        "prompt_version": _one(sorted({r["prompt_version"] for r in labels
                                       if r.get("prompt_version")})),
    }


def _one(values: list[str]):
    return values[0] if len(values) == 1 else (values or None)


def freeze(data_dir: Path, repo_manifest_path: Path = REPO_MANIFEST, *,
           frozen_at: str | None = None) -> dict:
    data_dir = Path(data_dir)
    stage = load_stage(data_dir)
    docs = stage["docs"]
    contaminated = {doc_id for doc_id, d in docs.items() if d.get("contaminated")}
    splits, split_stats = assign_splits(
        stage["clusters"], contaminated, {doc_id: d["url"] for doc_id, d in docs.items()}
    )
    cluster_of = {d: c["cluster_id"] for c in stage["clusters"] for d in c["doc_ids"]}
    for split in SPLITS:
        if (data_dir / split).exists():
            shutil.rmtree(data_dir / split)  # derived output; rebuilt from work/ below
    entries = []
    for doc_id in sorted(docs):
        doc, pool, labels = docs[doc_id], stage["pools"][doc_id], stage["labels"][doc_id]
        out = data_dir / splits[doc_id] / doc_id
        write_json(out / "doc.json", doc)
        write_jsonl(out / "pool.jsonl", pool)
        write_jsonl(out / "labels.gpt.jsonl", labels)
        entries.append(
            {
                "doc_id": doc_id,
                "url": doc["url"],
                "profile": doc["profile"],
                "split": splits[doc_id],
                "cluster_id": cluster_of[doc_id],
                "contaminated": doc_id in contaminated,
                "files": {name: file_digest(out / name) for name in DOC_FILES},
                "n_nodes": len(doc["nodes"]),
                "n_articles": doc["n_articles"],
                "n_pairs_by_stratum": {s: sum(1 for r in pool if r["stratum"] == s)
                                       for s in STRATA},
                "labels_by_label": dict(sorted(Counter(
                    r["label"] if not r.get("label_invalid") else "INVALID" for r in labels
                ).items())),
                "n_unlabeled": len(pool) - len(labels),
            }
        )
    manifest = {
        "schema": SCHEMA,
        "ground_truth": GROUND_TRUTH,
        "digest": "sha256 of UTF-8 text with LF line endings",
        "pool_seed": POOL_SEED,
        "pool_params": POOL_PARAMS,
        "labeler": labeler_block(r for rows in stage["labels"].values() for r in rows),
        "split_stats": split_stats,
        "clusters": [
            {"cluster_id": c["cluster_id"], "doc_ids": c["doc_ids"],
             "split": splits[c["doc_ids"][0]]}
            for c in stage["clusters"]
        ],
        "docs": entries,
        "extension_s4": None,
        "review_selection": None,
        "heldout_review": None,
        "frozen_at": frozen_at or dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
    }
    write_json(repo_manifest_path, manifest)
    return manifest


def verify(data_dir: Path, repo_manifest: Path = REPO_MANIFEST) -> list[str]:
    """Problems that make the frozen data untrustworthy; [] means it matches the manifest."""

    data_dir, path = Path(data_dir), Path(repo_manifest)
    if not path.is_file():
        return [f"{path}: manifest missing"]
    try:
        entries = read_json(path)["docs"]
    except (ValueError, KeyError, TypeError) as exc:
        return [f"{path}: unreadable manifest ({exc})"]
    problems: list[str] = []
    listed: set[tuple[str, str]] = set()
    for entry in entries:
        doc_id, split = entry.get("doc_id", "?"), entry.get("split", "?")
        if split not in SPLITS:
            problems.append(f"{doc_id}: split {split!r} ∉ {SPLITS}")
            continue
        listed.add((split, doc_id))
        files = entry.get("files", {})
        if sorted(files) != sorted(DOC_FILES):
            problems.append(f"{split}/{doc_id}: manifest lists {sorted(files)}")
        doc_dir = data_dir / split / doc_id
        if not doc_dir.is_dir():
            problems.append(f"{split}/{doc_id}: missing")
            continue
        for name, digest in sorted(files.items()):
            file = doc_dir / name
            if not file.is_file():
                problems.append(f"{split}/{doc_id}/{name}: missing")
            elif file_digest(file) != digest:
                problems.append(f"{split}/{doc_id}/{name}: sha256 mismatch")
        problems.extend(
            f"{split}/{doc_id}/{p.name}: file not in manifest"
            for p in sorted(doc_dir.iterdir()) if p.name not in files
        )
    for split in SPLITS:
        if (data_dir / split).is_dir():
            problems.extend(
                f"{split}/{child.name}: directory not in manifest"
                for child in sorted((data_dir / split).iterdir())
                if (split, child.name) not in listed
            )
    return problems


def read_split(data_dir: Path, split: str, repo_manifest: Path = REPO_MANIFEST) -> list[dict]:
    """Frozen docs of one split (``doc`` + ``pool`` + ``labels``), after ``verify``; any problem
    ⇒ exit 2."""

    problems = verify(data_dir, repo_manifest)
    if problems:
        for problem in problems:
            print(problem, file=sys.stderr)
        raise SystemExit(2)
    out = []
    for entry in read_json(repo_manifest)["docs"]:
        if entry["split"] != split:
            continue
        doc_dir = Path(data_dir) / split / entry["doc_id"]
        out.append({"doc": read_json(doc_dir / "doc.json"),
                    "pool": read_jsonl(doc_dir / "pool.jsonl"),
                    "labels": read_jsonl(doc_dir / "labels.gpt.jsonl")})
    return out
