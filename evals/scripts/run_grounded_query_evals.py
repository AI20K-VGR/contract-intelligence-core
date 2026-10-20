"""Deterministic production-eval CLI for the AI2 grounded-query domain."""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL_DIR = os.path.join(os.path.dirname(_HERE), "eval_types", "ai2_grounded_query")
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

from config_integrity import ConfigDriftError, load_verified_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Production eval runner for ai2_grounded_query")
    parser.add_argument("--sample-dir")
    parser.add_argument("--ground-truth")
    parser.add_argument("--questions", type=Path)
    parser.add_argument("--report", type=Path)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--judge-model", default=None)
    args = parser.parse_args()

    if args.questions:
        repo_root = str(Path(__file__).resolve().parents[2])
        if repo_root not in sys.path:
            sys.path.insert(0, repo_root)
        from evals.eval_types.ai2_grounded_query.questions import (
            load_questions,
            report_questions,
        )
        report = report_questions(load_questions(args.questions))
        rendered = json.dumps(report, ensure_ascii=False, indent=2)
        if args.report:
            args.report.parent.mkdir(parents=True, exist_ok=True)
            args.report.write_text(rendered + "\n", encoding="utf-8")
        print(rendered)
        sys.exit(0 if report["status"] == "complete" else 1)
    if not args.sample_dir or not args.ground_truth:
        parser.error("--sample-dir/--ground-truth hoặc --questions là bắt buộc")

    try:
        load_verified_config()
    except ConfigDriftError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)

    from runner import NormalizerNotRegistered, print_report, run_eval

    if not os.path.isdir(args.sample_dir):
        print(f"ERROR: Cannot find sample directory: {args.sample_dir}", file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.ground_truth):
        print(f"ERROR: Cannot find ground truth file: {args.ground_truth}", file=sys.stderr)
        sys.exit(2)

    try:
        results, scored = run_eval(args.sample_dir, args.ground_truth)
    except NormalizerNotRegistered as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        sys.exit(2)
    print_report(results, scored)

    if args.judge:
        try:
            from judge_runner import DEFAULT_JUDGE_MODEL, run_eval_with_judge
            run_eval_with_judge(
                args.sample_dir,
                args.ground_truth,
                skip_judge=False,
                judge_model=args.judge_model or DEFAULT_JUDGE_MODEL,
                precomputed=(results, scored),
            )
        except Exception as exc:  # noqa: BLE001 - advisory judge never gates
            print(f"[JUDGE] Advisory unavailable: {exc}", file=sys.stderr)

    if not results:
        print("ERROR: No scorable cases found.", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if scored.get("passed", False) else 1)


if __name__ == "__main__":
    main()
