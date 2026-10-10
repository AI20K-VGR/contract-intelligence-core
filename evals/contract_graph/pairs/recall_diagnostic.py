"""Reconcile held-out pair recall by pipeline layer.

The bake-off deliberately stores only safe aggregate traces.  This module keeps that boundary:
it joins reviewed pair ids to deterministic candidate metadata and safe classifier counters, but
never copies clause text, prompts, spans, or provider payloads into a tracked artifact.
"""

from __future__ import annotations

import datetime as dt
import json
import subprocess
from collections import Counter
from collections.abc import Iterable, Mapping
from pathlib import Path
from typing import Any

from evals.contract_graph.dataset import file_digest
from evals.contract_graph.pairs import manifest, predictor
from evals.contract_graph.pairs.pool import pair_id_for

SCORED_LABELS = frozenset({"GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE"})
DIRECTED_LABELS = frozenset({"GENERAL_SPECIFIC", "REFERENCE"})
VALIDATION_REJECTION_CODES = frozenset(
    {
        "malformed",
        "unknown_pair",
        "duplicate_id",
        "invalid_label",
        "bad_span",
        "ungrounded_span",
        "missing_direction",
        "duplicate_value_mismatch",
        "conflict_same_span",
        "reference_explicit",
        "citation_invalid",
    }
)
DEFAULT_SNAPSHOT_DIR = manifest.DEFAULT_DATA_DIR / "bakeoff-gpt55-final-20261010"
DEFAULT_REPORT_PREFIX = manifest.REPO_ROOT / "evals/contract_graph/reports/l2-p6-recall-diagnostic"


def _safe_candidate(candidate: Any) -> dict[str, Any]:
    """Serialize candidate provenance without importing or exposing contract text."""

    if isinstance(candidate, Mapping):
        sources = candidate.get("sources", ())
        score = candidate.get("score")
    else:
        sources = getattr(candidate, "sources", ())
        score = getattr(candidate, "score", None)
    values = sorted(str(getattr(source, "value", source)) for source in (sources or ()))
    return {"sources": values, "score": float(score) if isinstance(score, (int, float)) else None}


def _candidate_ids(candidates: Mapping[str, Mapping[str, Any]]) -> dict[str, dict[str, Any]]:
    """Normalize either a test fixture or a production candidate inventory."""

    return {
        str(doc_id): {str(pair_id): _safe_candidate(candidate)
                      for pair_id, candidate in pairs.items()}
        for doc_id, pairs in candidates.items()
    }


def _safe_trace_summary(traces: Iterable[Mapping[str, Any]]) -> dict[str, Any]:
    traces = list(traces)
    errors = [trace.get("error_type") for trace in traces if trace.get("error_type")]
    failed = sum(bool(trace.get("classification_failed")) for trace in traces)
    served = sorted({trace.get("served_model") for trace in traces if trace.get("served_model")})
    return {
        "trace_count": len(traces),
        "provider_error_traces": len(errors),
        "classification_failed_traces": failed,
        "error_types": sorted({str(error) for error in errors}),
        "served_models": served,
    }


def _prediction_map(predictions: Iterable[Mapping[str, Any]]) -> tuple[dict[str, Mapping[str, Any]], int]:
    by_id: dict[str, Mapping[str, Any]] = {}
    duplicates = 0
    for prediction in predictions:
        pair_id = prediction.get("pair_id")
        if not isinstance(pair_id, str):
            continue
        if pair_id in by_id:
            duplicates += 1
            continue
        by_id[pair_id] = prediction
    return by_id, duplicates


def _same_direction(gold: Mapping[str, Any], prediction: Mapping[str, Any]) -> bool:
    label = gold.get("gold_label")
    if label not in DIRECTED_LABELS:
        return True
    if gold.get("gold_direction") is None:
        return True
    return (gold.get("gold_direction") or None) == (prediction.get("direction") or None)


def _failure_for_unpredicted(
    *,
    doc_id: str,
    provider_docs: set[str],
    over_budget: bool,
    rejected: Mapping[str, int],
) -> tuple[str, str]:
    if doc_id in provider_docs:
        return "unclassified_or_provider", "provider_or_budget"
    if rejected.get("unrelated", 0) > 0:
        return "classifier_unrelated", "aggregate_rejection"
    if sum(rejected.get(code, 0) for code in VALIDATION_REJECTION_CODES) > 0:
        return "validation_reject", "aggregate_rejection"
    if over_budget:
        return "unclassified_or_provider", "provider_or_budget"
    return "unclassified_or_provider", "unclassified"


def diagnose_trial(
    trial: Mapping[str, Any],
    *,
    gold: Iterable[Mapping[str, Any]],
    candidates: Mapping[str, Mapping[str, Any]],
) -> dict[str, Any]:
    """Diagnose one safe bake-off snapshot.

    ``classifier_unrelated`` and ``validation_reject`` are aggregate attributions when the
    snapshot has no pair-level rejection trace.  The evidence scope is recorded explicitly so a
    later instrumentation phase cannot mistake it for a pair-level fact.
    """

    inventory = _candidate_ids(candidates)
    candidate_by_pair = {
        pair_id: {"doc_id": doc_id, **metadata}
        for doc_id, pairs in inventory.items()
        for pair_id, metadata in pairs.items()
    }
    predictions, duplicate_predictions = _prediction_map(trial.get("predictions", ()))
    rejected = {
        str(code): int(value)
        for code, value in (trial.get("rejected") or {}).items()
        if isinstance(value, (int, float)) and not isinstance(value, bool) and value >= 0
    }
    trace_summary = _safe_trace_summary(trial.get("traces", ()))
    provider_docs = {
        str(trace.get("doc_id"))
        for trace in trial.get("traces", ())
        if (trace.get("error_type") or trace.get("classification_failed")) and trace.get("doc_id")
    }
    over_budget = bool(trial.get("over_budget"))
    gold_rows = [
        row for row in gold
        if row.get("gold_label") in SCORED_LABELS and isinstance(row.get("pair_id"), str)
    ]
    outcomes: list[dict[str, Any]] = []
    for row in sorted(gold_rows, key=lambda item: str(item["pair_id"])):
        pair_id = str(row["pair_id"])
        candidate = candidate_by_pair.get(pair_id)
        prediction = predictions.get(pair_id)
        outcome: dict[str, Any] = {
            "pair_id": pair_id,
            "doc_id": row.get("doc_id"),
            "gold_label": row.get("gold_label"),
            "candidate": candidate,
            "prediction_label": prediction.get("label") if prediction else None,
            "failure_class": None,
            "evidence_scope": "pair" if prediction or candidate is None else "aggregate",
        }
        if candidate is None:
            outcome["failure_class"] = "candidate_miss"
        elif prediction is None:
            failure, scope = _failure_for_unpredicted(
                doc_id=str(row.get("doc_id") or candidate.get("doc_id") or ""),
                provider_docs=provider_docs,
                over_budget=over_budget,
                rejected=rejected,
            )
            outcome["failure_class"] = failure
            outcome["evidence_scope"] = scope
        elif prediction.get("label") != row.get("gold_label"):
            outcome["failure_class"] = "classifier_wrong_label"
        elif not _same_direction(row, prediction):
            outcome["failure_class"] = "classifier_wrong_direction"
        else:
            outcome["failure_class"] = "correct"
        outcomes.append(outcome)

    candidate_total = sum(len(pairs) for pairs in inventory.values())
    predicted_in_candidates = sum(1 for pair_id in predictions if pair_id in candidate_by_pair)
    rejected_total = sum(rejected.values())
    residual = candidate_total - predicted_in_candidates - rejected_total
    unclassified = max(0, residual)
    validation_rejects = sum(rejected.get(code, 0) for code in VALIDATION_REJECTION_CODES)
    false_duplicate = {
        "observed": sum(
            1 for pair_id, prediction in predictions.items()
            if prediction.get("label") == "DUPLICATE"
            and pair_id in {row["pair_id"] for row in gold_rows}
            and next(row for row in gold_rows if row["pair_id"] == pair_id).get("gold_label") != "DUPLICATE"
        ),
        "unreviewed": sum(
            1 for pair_id, prediction in predictions.items()
            if prediction.get("label") == "DUPLICATE" and pair_id not in {row["pair_id"] for row in gold_rows}
        ),
    }
    hard_stops = []
    if false_duplicate["observed"] or false_duplicate["unreviewed"]:
        hard_stops.append("false_duplicate")
    if duplicate_predictions:
        hard_stops.append("duplicate_prediction_id")
    if residual < 0:
        hard_stops.append("candidate_accounting_mismatch")
    failure_counts = Counter(row["failure_class"] for row in outcomes)
    failure_counts["validation_reject"] = validation_rejects
    return {
        "variant": trial.get("variant"),
        "trial": trial.get("trial"),
        "gold_outcomes": outcomes,
        "failure_counts": dict(sorted(failure_counts.items())),
        "candidate_accounting": {
            "candidate_total": candidate_total,
            "predicted_in_candidates": predicted_in_candidates,
            "rejected_total": rejected_total,
            "unclassified": unclassified,
            "unaccounted": min(0, residual),
            "unknown_predictions": len(predictions) - predicted_in_candidates,
        },
        "rejection_counts": dict(sorted(rejected.items())),
        "provider_or_budget": {
            **trace_summary,
            "over_budget": over_budget,
            "elapsed_s": trial.get("elapsed_s"),
            "budget": trial.get("budget"),
        },
        "false_duplicate": false_duplicate,
        "hard_stops": hard_stops,
    }


def _coverage(
    candidates: Mapping[str, Mapping[str, Any]], gold: Iterable[Mapping[str, Any]]
) -> dict[str, Any]:
    positive = [row for row in gold if row.get("gold_label") in SCORED_LABELS]
    ids = {pair_id for pairs in candidates.values() for pair_id in pairs}
    covered = sum(1 for row in positive if row.get("pair_id") in ids)
    denominator = len(positive)
    return {
        "covered": covered,
        "denominator": denominator,
        "rate": round(covered / denominator, 4) if denominator else None,
    }


def diagnose_trials(
    trials: Iterable[Mapping[str, Any]],
    *,
    gold: Iterable[Mapping[str, Any]],
    candidates_by_variant: Mapping[str, Mapping[str, Mapping[str, Any]]],
) -> dict[str, Any]:
    gold = list(gold)
    results = []
    for trial in sorted(trials, key=lambda item: (str(item.get("variant")), int(item.get("trial", 0)))):
        variant = str(trial.get("variant"))
        if variant not in candidates_by_variant:
            raise ValueError(f"candidate inventory missing variant {variant}")
        results.append(diagnose_trial(trial, gold=gold, candidates=candidates_by_variant[variant]))
    return {
        "candidate_coverage": {
            variant: _coverage(candidates, gold)
            for variant, candidates in sorted(candidates_by_variant.items())
        },
        "trials": results,
        "hard_stops": sorted({stop for result in results for stop in result["hard_stops"]}),
    }


def _candidate_inventory(
    data_dir: Path, *, variant: str, repo_manifest: Path = manifest.REPO_MANIFEST
) -> dict[str, dict[str, dict[str, Any]]]:
    frozen = manifest.read_json(repo_manifest)
    extension = (frozen.get("extension_s4") or {}).get("files", {})
    inventory: dict[str, dict[str, dict[str, Any]]] = {}
    for item in manifest.read_split(data_dir, "heldout", repo_manifest):
        doc = item["doc"]
        doc_id = doc["doc_id"]
        pool = list(item["pool"])
        if doc_id in extension:
            pool += manifest.read_jsonl(data_dir / "heldout" / doc_id / "s4.jsonl")
        generated = predictor.candidate_set(doc, variant=variant, pool=pool)
        inventory[doc_id] = {
            pair_id_for(doc_id, candidate.node_a, candidate.node_b): _safe_candidate(candidate)
            for candidate in generated.candidates
        }
    return inventory


def _git_head() -> str | None:
    try:
        return subprocess.run(
            ["git", "rev-parse", "HEAD"], capture_output=True, text=True, check=True
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        return None


def _code_digests() -> dict[str, str]:
    files = (
        "evals/contract_graph/pairs/recall_diagnostic.py",
        "evals/contract_graph/pairs/predictor.py",
        "evals/contract_graph/pairs/bakeoff.py",
        "ai-service/app/pipeline/contract_graph/pair_candidates.py",
        "ai-service/app/pipeline/contract_graph/pair_classifier.py",
    )
    return {path: file_digest(manifest.REPO_ROOT / path) for path in files if (manifest.REPO_ROOT / path).is_file()}


def diagnose_snapshots(
    snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
    *,
    data_dir: Path = manifest.DEFAULT_DATA_DIR,
    repo_manifest: Path = manifest.REPO_MANIFEST,
    variants: Iterable[str] = ("B", "C", "E"),
    trials: Iterable[int] = (1, 2),
) -> dict[str, Any]:
    problems = manifest.verify(data_dir, repo_manifest)
    if problems:
        raise ValueError("frozen dataset verification failed")
    frozen = manifest.read_json(repo_manifest)
    gold = predictor._read_reviewed_gold(data_dir, frozen)
    candidates_by_variant = {
        variant: _candidate_inventory(data_dir, variant=variant, repo_manifest=repo_manifest)
        for variant in variants
    }
    snapshots = []
    for trial in trials:
        for variant in variants:
            path = Path(snapshot_dir) / f"t{trial}" / f"{variant}.json"
            if not path.is_file():
                raise ValueError(f"snapshot missing: {variant}{trial}")
            snapshots.append(manifest.read_json(path))
    report = diagnose_trials(snapshots, gold=gold, candidates_by_variant=candidates_by_variant)
    report.update(
        {
            "schema": "contract-graph-recall-diagnostic/1",
            "status": "OBSERVED",
            "generated_at": dt.datetime.now(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
            "gold": {
                "positive_count": sum(row.get("gold_label") in SCORED_LABELS for row in gold),
                "approved_count": sum(bool(row.get("approved")) for row in gold),
                "labels": dict(sorted(Counter(row["gold_label"] for row in gold).items())),
            },
            "provenance": {
                "git_head": _git_head(),
                "manifest_sha256": file_digest(repo_manifest),
                "review_selection_sha256": (frozen.get("review_selection") or {}).get("sha256"),
                "heldout_decisions_sha256": (frozen.get("heldout_review") or {}).get("decisions_sha256"),
                "code_sha256": _code_digests(),
                "requested_models": sorted({
                    str(snapshot.get("requested_model"))
                    for snapshot in snapshots
                    if snapshot.get("requested_model")
                }),
                "served_models": sorted({
                    str(model)
                    for snapshot in snapshots
                    for model in (snapshot.get("served_model") or [])
                }),
                "snapshot_dir": str(Path(snapshot_dir).resolve()),
            },
        }
    )
    return report


def render_report(report: Mapping[str, Any]) -> str:
    lines = [
        "# Contract graph P1 — recall diagnostic",
        "",
        f"- Trạng thái: `{report.get('status', 'UNKNOWN')}`.",
        f"- Gold positive: `{report.get('gold', {}).get('positive_count', 0)}`; approved: `{report.get('gold', {}).get('approved_count', 0)}`.",
        "- Báo cáo chỉ ghi pair id, metadata candidate và bộ đếm an toàn; không ghi clause text, span, prompt hay response.",
        "",
        "## Candidate coverage",
        "",
        "| Variant | Covered | Denominator | Rate |",
        "| --- | ---: | ---: | ---: |",
    ]
    for variant, block in sorted(report.get("candidate_coverage", {}).items()):
        rate = "—" if block.get("rate") is None else f"{block['rate']:.4f}"
        lines.append(f"| {variant} | {block['covered']} | {block['denominator']} | {rate} |")
    lines.extend(["", "## Trial failure taxonomy", ""])
    for trial in report.get("trials", []):
        lines.extend(
            [
                f"### {trial.get('variant')}{trial.get('trial')}",
                "",
                "```json",
                json.dumps(
                    {
                        "failure_counts": trial.get("failure_counts"),
                        "candidate_accounting": trial.get("candidate_accounting"),
                        "rejection_counts": trial.get("rejection_counts"),
                        "provider_or_budget": trial.get("provider_or_budget"),
                        "false_duplicate": trial.get("false_duplicate"),
                        "hard_stops": trial.get("hard_stops"),
                    },
                    ensure_ascii=False,
                    indent=2,
                    sort_keys=True,
                ),
                "```",
                "",
            ]
        )
    lines.extend(
        [
            "## Provenance",
            "",
            "```json",
            json.dumps(report.get("provenance", {}), ensure_ascii=False, indent=2, sort_keys=True),
            "```",
            "",
            f"Hard stops: `{', '.join(report.get('hard_stops', [])) or 'none'}`.",
        ]
    )
    return "\n".join(lines) + "\n"


def write_report(report: Mapping[str, Any], prefix: Path = DEFAULT_REPORT_PREFIX) -> tuple[Path, Path]:
    json_path = Path(prefix).with_suffix(".json")
    md_path = Path(prefix).with_suffix(".md")
    manifest.write_json(json_path, dict(report))
    md_path.write_text(render_report(report), encoding="utf-8")
    return json_path, md_path
