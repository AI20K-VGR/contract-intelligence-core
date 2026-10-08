"""CLI for the contract-graph eval.

  python -m evals.contract_graph.run_eval score --data evals/contract_graph/data \
      --predictor baseline --out evals/contract_graph/reports/p1-baseline
  python -m evals.contract_graph.run_eval fetch --sources evals/contract_graph/sources.json

``--predictor`` is ``baseline`` or ``module:function`` with ``predict(pair_dir: Path) -> list[dict]``
(each dict: ``src_address``, ``op``, ``target_address``; extra keys are kept but not scored).
``score`` checks the manifest first and refuses to score a dataset that does not match it.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import sys
from collections.abc import Callable
from pathlib import Path

from evals.contract_graph.dataset import (
    DEFAULT_CACHE,
    DEFAULT_DATA,
    MANIFEST,
    build_pair,
    freeze,
    load_gold,
    verify_manifest,
)
from evals.contract_graph.score import render_markdown, score

Predictor = Callable[[Path], list]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m evals.contract_graph.run_eval")
    sub = parser.add_subparsers(dest="command", required=True)
    fetch = sub.add_parser(
        "fetch", help="fetch (cached) + normalize + freeze the pairs of a sources file"
    )
    fetch.add_argument("--sources", type=Path, required=True)
    fetch.add_argument("--cache", type=Path, default=DEFAULT_CACHE)
    fetch.add_argument("--out", type=Path, default=DEFAULT_DATA)
    fetch.add_argument(
        "--offline", action="store_true", help="use the cache only; a missing page is an error"
    )
    run = sub.add_parser("score", help="score a predictor against the frozen dataset")
    run.add_argument("--data", type=Path, required=True)
    run.add_argument("--predictor", default="baseline")
    run.add_argument(
        "--out", type=Path, required=True, help="report path prefix; writes <out>.json and <out>.md"
    )
    args = parser.parse_args(argv)
    if args.command == "fetch":
        return _fetch(args)
    return _score(args, _load_predictor(args.predictor, parser))


def _fetch(args: argparse.Namespace) -> int:
    sources = json.loads(args.sources.read_text(encoding="utf-8"))["pairs"]
    pairs, failed = [], []
    for source in sources:
        try:
            pairs.append(build_pair(source, args.cache, offline=args.offline))
        except (OSError, ValueError, LookupError) as exc:
            failed.append(source.get("pair_id"))
            print(f"fetch failed: {source.get('pair_id')}: {exc}", file=sys.stderr)
    manifest = freeze(pairs, args.out)
    print(f"froze {len(manifest['pairs'])} pairs, {manifest['total_bytes']} bytes -> {args.out}")
    if failed:
        print(
            f"{len(failed)}/{len(sources)} pairs failed and were not frozen: {failed}",
            file=sys.stderr,
        )
        return 1
    return 0


def _score(args: argparse.Namespace, predictor: Predictor) -> int:
    problems = verify_manifest(args.data)
    if problems:
        print("manifest check failed, refusing to score:", file=sys.stderr)
        for problem in problems:
            print(f"  {problem}", file=sys.stderr)
        return 2
    manifest_bytes = (args.data / MANIFEST).read_bytes().replace(b"\r\n", b"\n")
    pairs = json.loads(manifest_bytes)["pairs"]
    gold, preds = [], []
    for entry in sorted(pairs, key=lambda e: e["pair_id"]):
        pair_dir = args.data / entry["pair_id"]
        gold.extend(load_gold(pair_dir))
        preds.extend({**pred, "pair_id": entry["pair_id"]} for pred in predictor(pair_dir))
    report = score(gold, preds)
    report["predictor"] = args.predictor
    report["dataset"] = {
        "pairs": len(pairs),
        "manifest_sha256": hashlib.sha256(manifest_bytes).hexdigest(),
    }
    args.out.parent.mkdir(parents=True, exist_ok=True)
    _write(
        args.out.parent / f"{args.out.name}.json",
        json.dumps(report, ensure_ascii=False, indent=1, sort_keys=True) + "\n",
    )
    _write(args.out.parent / f"{args.out.name}.md", render_markdown(report))
    overall = report["overall"]["all"]
    print(
        f"{len(pairs)} pairs, gold {overall['n_gold']}: src_found {overall['src_found']['passed']}, "
        f"op_lexical_agreement {overall['op_lexical_agreement']['passed']}, "
        f"target {overall['target_accuracy']['passed']}/{overall['target_accuracy']['denominator']}"
    )
    return 0


def _load_predictor(spec: str, parser: argparse.ArgumentParser) -> Predictor:
    if spec == "baseline":
        from evals.contract_graph.baseline_predictor import predict

        return predict
    module_name, _, func_name = spec.partition(":")
    if not module_name or not func_name:
        parser.error(f"--predictor must be 'baseline' or 'module:function', got {spec!r}")
    try:
        func = getattr(importlib.import_module(module_name), func_name)
    except (ImportError, AttributeError) as exc:
        parser.error(f"cannot load predictor {spec!r}: {exc}")
    if not callable(func):
        parser.error(f"predictor {spec!r} is not callable")
    return func


def _write(path: Path, text: str) -> None:
    with open(path, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(text)


if __name__ == "__main__":
    sys.exit(main())
