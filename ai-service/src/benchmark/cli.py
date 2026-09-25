from __future__ import annotations

import argparse
from pathlib import Path

from benchmark.pipeline import evaluate_benchmark, load_config, prepare_dataset, run_benchmark
from benchmark.reporting import generate_report


def parser() -> argparse.ArgumentParser:
    root = argparse.ArgumentParser(prog="python -m benchmark")
    root.add_argument("--config", default="ocr-benchmark/config.yaml")
    commands = root.add_subparsers(dest="command", required=True)
    prepare = commands.add_parser("prepare")
    prepare.add_argument("--input", default="ocr-benchmark/data/scans")
    commands.add_parser("run")
    commands.add_parser("evaluate")
    commands.add_parser("report")
    all_command = commands.add_parser("all")
    all_command.add_argument("--input", default="ocr-benchmark/data/scans")
    return root


def main(argv: list[str] | None = None) -> int:
    try:
        from dotenv import load_dotenv

        load_dotenv()
    except ImportError:
        pass
    args = parser().parse_args(argv)
    config_path = Path(args.config)
    config = load_config(config_path)
    base = config_path.parent
    data = base / config.get("paths", {}).get("data", "data")
    artifacts = base / config.get("paths", {}).get("artifacts", "artifacts")
    reports = base / config.get("paths", {}).get("reports", "reports")
    if args.command in {"prepare", "all"}:
        docs = prepare_dataset(Path(args.input), data, config)
        print(f"Prepared {len(docs)} documents / {sum(doc.page_count for doc in docs)} pages")
    if args.command in {"run", "all"}:
        statuses = run_benchmark(data, artifacts, config)
        print(f"Run attempts: {len(statuses)}")
    if args.command in {"evaluate", "all"}:
        result = evaluate_benchmark(data, artifacts, reports)
        print(f"Evaluated {len(result['by_document'])} Mistral experiment results")
    if args.command in {"report", "all"}:
        result = generate_report(data, artifacts, reports, config)
        print(f"Report generated from {len(result['paired_rows'])} paired rows")
    return 0
