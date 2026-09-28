#!/usr/bin/env python3
"""Run the eval + improve loop until all pass or max iterations reached.

Combines trigger_eval.run_eval and improve_description in a loop, tracking
history and returning the best description found. Supports a train/test split to
prevent overfitting. Adapted from the upstream run_loop: the HTML/live-report and
the anthropic client are dropped — output is JSON only (the harness keeps reports
in markdown, not HTML), and improvement goes through claude -p.
"""

import argparse
import json
import random
import sys
import time
from pathlib import Path

from improve_description import improve_description
from trigger_eval import find_project_root, parse_skill_md, run_eval


def split_eval_set(eval_set: list, holdout: float, seed: int = 42):
    """Split an eval set into train/test, stratified by should_trigger."""
    random.seed(seed)
    trigger = [e for e in eval_set if e["should_trigger"]]
    no_trigger = [e for e in eval_set if not e["should_trigger"]]
    random.shuffle(trigger)
    random.shuffle(no_trigger)

    n_trigger_test = max(1, int(len(trigger) * holdout))
    n_no_trigger_test = max(1, int(len(no_trigger) * holdout))

    test_set = trigger[:n_trigger_test] + no_trigger[:n_no_trigger_test]
    train_set = trigger[n_trigger_test:] + no_trigger[n_no_trigger_test:]
    return train_set, test_set


def run_loop(
    eval_set: list,
    skill_path: Path,
    description_override,
    num_workers: int,
    timeout: int,
    max_iterations: int,
    runs_per_query: int,
    trigger_threshold: float,
    holdout: float,
    model: str,
    verbose: bool,
    log_dir: Path = None,
) -> dict:
    """Run the eval + improvement loop and return the best description found."""
    project_root = find_project_root()
    name, original_description, content = parse_skill_md(skill_path)
    current_description = description_override or original_description

    if holdout > 0:
        train_set, test_set = split_eval_set(eval_set, holdout)
        if not train_set:
            # A tiny eval-set under a high holdout can send every query to test,
            # leaving train empty — which would read as a false "all_passed"
            # convergence on iteration 1. Refuse instead of reporting a phantom pass.
            raise ValueError(
                f"holdout={holdout} leaves an empty train set for {len(eval_set)} "
                "queries; add more eval queries or pass --holdout 0")
        if verbose:
            print(f"Split: {len(train_set)} train, {len(test_set)} test (holdout={holdout})", file=sys.stderr)
    else:
        train_set = eval_set
        test_set = []

    history = []
    exit_reason = "unknown"

    for iteration in range(1, max_iterations + 1):
        if verbose:
            print(f"\n{'='*60}\nIteration {iteration}/{max_iterations}\n"
                  f"Description: {current_description}\n{'='*60}", file=sys.stderr)

        all_queries = train_set + test_set
        t0 = time.time()
        all_results = run_eval(
            all_queries, name, current_description,
            num_workers=num_workers, timeout=timeout, project_root=project_root,
            runs_per_query=runs_per_query, trigger_threshold=trigger_threshold, model=model,
        )
        eval_elapsed = time.time() - t0

        train_queries_set = {q["query"] for q in train_set}
        train_result_list = [r for r in all_results["results"] if r["query"] in train_queries_set]
        test_result_list = [r for r in all_results["results"] if r["query"] not in train_queries_set]

        train_passed = sum(1 for r in train_result_list if r["pass"])
        train_total = len(train_result_list)
        train_summary = {"passed": train_passed, "failed": train_total - train_passed, "total": train_total}
        train_results = {"results": train_result_list, "summary": train_summary}

        if test_set:
            test_passed = sum(1 for r in test_result_list if r["pass"])
            test_total = len(test_result_list)
            test_summary = {"passed": test_passed, "failed": test_total - test_passed, "total": test_total}
            test_results = {"results": test_result_list, "summary": test_summary}
        else:
            test_results = None
            test_summary = None

        history.append({
            "iteration": iteration,
            "description": current_description,
            "train_passed": train_summary["passed"],
            "train_failed": train_summary["failed"],
            "train_total": train_summary["total"],
            "train_results": train_results["results"],
            "test_passed": test_summary["passed"] if test_summary else None,
            "test_failed": test_summary["failed"] if test_summary else None,
            "test_total": test_summary["total"] if test_summary else None,
            "test_results": test_results["results"] if test_results else None,
            "passed": train_summary["passed"],
            "failed": train_summary["failed"],
            "total": train_summary["total"],
            "results": train_results["results"],
        })

        if verbose:
            print(f"Train: {train_summary['passed']}/{train_summary['total']} "
                  f"({eval_elapsed:.1f}s)", file=sys.stderr)

        if train_summary["failed"] == 0:
            exit_reason = f"all_passed (iteration {iteration})"
            break

        if iteration == max_iterations:
            exit_reason = f"max_iterations ({max_iterations})"
            break

        # Strip test scores so the improvement model can't peek at the holdout.
        blinded_history = [
            {k: v for k, v in h.items() if not k.startswith("test_")}
            for h in history
        ]
        try:
            current_description = improve_description(
                skill_name=name,
                skill_content=content,
                current_description=current_description,
                eval_results=train_results,
                history=blinded_history,
                model=model,
                log_dir=log_dir,
                iteration=iteration,
            )
        except RuntimeError as exc:
            # A claude -p failure mid-loop must not discard the progress already
            # recorded in history — stop and return the best candidate so far.
            exit_reason = f"improve_error (iteration {iteration}): {exc}"
            if verbose:
                print(f"Improvement failed: {exc}", file=sys.stderr)
            break

    if test_set:
        best = max(history, key=lambda h: h["test_passed"] or 0)
        best_score = f"{best['test_passed']}/{best['test_total']}"
    else:
        best = max(history, key=lambda h: h["train_passed"])
        best_score = f"{best['train_passed']}/{best['train_total']}"

    if verbose:
        print(f"\nExit reason: {exit_reason}\nBest score: {best_score} "
              f"(iteration {best['iteration']})", file=sys.stderr)

    return {
        "exit_reason": exit_reason,
        "original_description": original_description,
        "best_description": best["description"],
        "best_score": best_score,
        "best_train_score": f"{best['train_passed']}/{best['train_total']}",
        "best_test_score": f"{best['test_passed']}/{best['test_total']}" if test_set else None,
        "final_description": current_description,
        "iterations_run": len(history),
        "holdout": holdout,
        "train_size": len(train_set),
        "test_size": len(test_set),
        "history": history,
    }


def main(argv=None):
    parser = argparse.ArgumentParser(description="Run the eval + improve loop")
    parser.add_argument("--eval-set", required=True, help="Path to eval-set JSON")
    parser.add_argument("--skill-path", required=True, help="Path to skill directory")
    parser.add_argument("--description", default=None, help="Override starting description")
    parser.add_argument("--num-workers", type=int, default=1, help="Parallel workers")
    parser.add_argument("--timeout", type=int, default=30, help="Timeout per query (seconds)")
    parser.add_argument("--max-iterations", type=int, default=5, help="Max improvement iterations")
    parser.add_argument("--runs-per-query", type=int, default=3, help="Runs per query")
    parser.add_argument("--trigger-threshold", type=float, default=0.5, help="Trigger-rate threshold")
    parser.add_argument("--holdout", type=float, default=0.4, help="Test holdout fraction (0 disables)")
    parser.add_argument("--model", required=True, help="Model for improvement")
    parser.add_argument("--verbose", action="store_true", help="Print progress to stderr")
    parser.add_argument("--results-dir", default=None, help="Save results.json + improve logs here")
    args = parser.parse_args(argv)

    eval_set = json.loads(Path(args.eval_set).read_text())
    skill_path = Path(args.skill_path)
    if not (skill_path / "SKILL.md").exists():
        print(f"Error: No SKILL.md found at {skill_path}", file=sys.stderr)
        return 1

    results_dir = None
    log_dir = None
    if args.results_dir:
        results_dir = Path(args.results_dir)
        results_dir.mkdir(parents=True, exist_ok=True)
        log_dir = results_dir / "logs"

    # Visible cost estimate before the loop spawns real, paid claude -p processes.
    est_eval = args.max_iterations * len(eval_set) * args.runs_per_query
    est_improve = args.max_iterations * 2  # one improve + a possible shorten per round
    print(f"[plan] up to ~{est_eval} eval + ~{est_improve} improve `claude -p` calls "
          f"(max-iter={args.max_iterations} x queries={len(eval_set)} x runs={args.runs_per_query}). "
          "Real model calls — opt-in, not free.", file=sys.stderr)

    output = run_loop(
        eval_set=eval_set,
        skill_path=skill_path,
        description_override=args.description,
        num_workers=args.num_workers,
        timeout=args.timeout,
        max_iterations=args.max_iterations,
        runs_per_query=args.runs_per_query,
        trigger_threshold=args.trigger_threshold,
        holdout=args.holdout,
        model=args.model,
        verbose=args.verbose,
        log_dir=log_dir,
    )

    json_output = json.dumps(output, indent=2)
    print(json_output)
    if results_dir:
        (results_dir / "results.json").write_text(json_output)
        print(f"Results saved to: {results_dir}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
