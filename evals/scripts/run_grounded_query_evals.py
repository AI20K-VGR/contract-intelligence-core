"""Deterministic production-eval CLI for the AI2 grounded-query domain."""

from __future__ import annotations

import argparse
import os
import sys


_HERE = os.path.dirname(os.path.abspath(__file__))
_EVAL_DIR = os.path.join(os.path.dirname(_HERE), "eval_types", "ai2_grounded_query")
if _EVAL_DIR not in sys.path:
    sys.path.insert(0, _EVAL_DIR)

from config_integrity import ConfigDriftError, load_verified_config


def main() -> None:
    parser = argparse.ArgumentParser(description="Production eval runner for ai2_grounded_query")
    parser.add_argument("--sample-dir", required=True)
    parser.add_argument("--ground-truth", required=True)
    parser.add_argument("--judge", action="store_true")
    parser.add_argument("--judge-model", default=None)
    args = parser.parse_args()

    try:
        load_verified_config()
    except ConfigDriftError as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(2)

    from runner import NormalizerNotRegistered, run_eval, print_report

    if not os.path.isdir(args.sample_dir):
        print("ERROR: Cannot find sample directory: %s" % args.sample_dir, file=sys.stderr)
        sys.exit(2)
    if not os.path.isfile(args.ground_truth):
        print("ERROR: Cannot find ground truth file: %s" % args.ground_truth, file=sys.stderr)
        sys.exit(2)

    try:
        results, scored = run_eval(args.sample_dir, args.ground_truth)
    except NormalizerNotRegistered as exc:
        print("ERROR: %s" % exc, file=sys.stderr)
        sys.exit(2)
    print_report(results, scored)

    if args.judge:
        try:
            from judge_runner import run_eval_with_judge, DEFAULT_JUDGE_MODEL
            run_eval_with_judge(
                args.sample_dir,
                args.ground_truth,
                skip_judge=False,
                judge_model=args.judge_model or DEFAULT_JUDGE_MODEL,
                precomputed=(results, scored),
            )
        except Exception as exc:  # noqa: BLE001 - advisory judge never gates
            print("[JUDGE] Advisory unavailable: %s" % exc, file=sys.stderr)

    if not results:
        print("ERROR: No scorable cases found.", file=sys.stderr)
        sys.exit(1)
    sys.exit(0 if scored.get("passed", False) else 1)


if __name__ == "__main__":
    main()
