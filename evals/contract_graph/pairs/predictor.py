"""Production pair builder on verified public docs; family checks fail closed per call."""

from __future__ import annotations

import hashlib
import importlib.util
import json
import math
import os
import sys
import time
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from evals.contract_graph.dataset import file_digest
from evals.contract_graph.pairs import manifest, review
from evals.contract_graph.pairs.corpus import AI_SERVICE
from evals.contract_graph.pairs.models import (
    OPENAI,
    classifier_family_ok,
    classifier_model_differs_from_labeler,
    family,
)
from evals.contract_graph.pairs.pool import pair_id_for
from evals.contract_graph.pairs.score import score_relations

if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

from app.contracts.models import (
    LifecycleState,
    PageSnapshot,
    SourceFile,
    StructuralNode,
    TenantProfile,
    VersionPins,
)
from app.pipeline.contract_graph.builder import build_contract_graph
from app.pipeline.contract_graph.pair_builder import build_pair_relations
from app.pipeline.contract_graph.pair_candidates import (
    ALL_SOURCES,
    PAIRS_TOP_K,
    PairCandidate,
    PairCandidateSet,
    PairSource,
    generate_pair_candidates,
)
from app.pipeline.contract_graph.pair_classifier import (
    PAIRS_MAX_CALLS,
    PAIRS_PER_CALL,
    PROMPT_VERSION,
)
from app.pipeline.contract_graph.resolver import StructureIndex
from app.pipeline.runtime import ProcessingRuntime
from app.tools.store import DossierRecord

_MANIFEST_LABELER = object()
REPORT_SCHEMA = "contract-graph-pairs-predictor/2"
SCORING_SCHEMA = "contract-graph-pairs-score/1"
P3_GATE_SCHEMA = "contract-graph-p3-classifier-gate/1"
DEV_REVIEW_SCHEMA = "contract-graph-dev-review/1"


def code_fingerprints() -> dict[str, str]:
    paths = [AI_SERVICE / "app/pipeline/contract_graph" / name
             for name in ("pair_candidates.py", "pair_classifier.py", "pair_builder.py")]
    paths += [Path(__file__), Path(__file__).with_name("bakeoff.py"), Path(__file__).with_name("score.py"),
              AI_SERVICE / "app/llm/client.py"]
    return {path.name: file_digest(path) for path in paths}


def report_digest(report: dict) -> str:
    """Return the canonical digest of a report, excluding its self digest."""
    payload = {key: value for key, value in report.items() if key != "report_sha256"}
    canonical = json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(canonical.encode("utf-8")).hexdigest()


def _classifier_gate(scored: dict, evaluation_gate: str) -> dict:
    required_labels = {}
    reasons = []
    for label in ("CONFLICT", "DUPLICATE"):
        recall = scored["by_label"][label]["recall_observed"]
        required_labels[label] = {"gold_positive": recall["denominator"], "correct": recall["passed"]}
        if recall["denominator"] <= 0:
            reasons.append(f"missing_{label.lower()}_gold")
        elif recall["passed"] <= 0:
            reasons.append(f"zero_{label.lower()}_recall")
    false_duplicate = scored["false_duplicate"]["observed"]
    if false_duplicate:
        reasons.append("false_duplicate_observed")
    if evaluation_gate != "PASS":
        reasons.append("evaluation_gate_not_pass")
    return {"schema": P3_GATE_SCHEMA, "status": "PASS" if not reasons else "BLOCKED",
            "required_labels": required_labels, "false_duplicate_observed": false_duplicate,
            "reason_codes": reasons}


def _family_error() -> None:
    # Fixed diagnostic: never expose a provider error, response or key.
    print("K-a: classifier served_model must be recognised and differ from labeler; labeler must be openai", file=sys.stderr)
    raise SystemExit(2)


class _EvalRuntime(ProcessingRuntime):
    def __init__(self, *, labeler_served_model: str | None = None, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self._labeler_served_model = labeler_served_model

    def complete_json(self, client: Any, system: str, user: str, *, strong: bool = False) -> dict | None:
        start = len(getattr(client, "traces", []))
        response = super().complete_json(client, system, user, strong=strong)
        if response is not None:
            traces = getattr(client, "traces", [])[start:]
            served = traces[-1].get("served_model") if traces else None
            if (not isinstance(served, str) or not classifier_family_ok(served)
                    or not classifier_model_differs_from_labeler(served, self._labeler_served_model)):
                _family_error()
        return response


def eval_runtime(max_calls: int, labeler_served_model: str | None = None) -> ProcessingRuntime:
    return _EvalRuntime(labeler_served_model=labeler_served_model, egress_allowed=True, max_llm_calls=max_calls * 6,
                        max_processing_seconds=max(1000, max_calls * 200))


def record_from_doc(doc: dict) -> DossierRecord:
    """Synthetic page provenance of the public segmented JSON, not a claim about original PDFs."""
    doc_id = doc["doc_id"]
    nodes: list[StructuralNode] = []
    pages: list[PageSnapshot] = []
    sources: list[SourceFile] = []
    groups: dict[str, list[dict]] = {}
    for raw in doc["nodes"]:
        groups.setdefault(raw.get("source_file_id") or doc_id, []).append(raw)
    for page_number, (file_id, members) in enumerate(sorted(groups.items()), 1):
        revision = f"{doc_id}:{file_id}:synthetic-p1"
        lines = {}
        for raw in sorted(members, key=lambda n: (n["order"], n["node_id"])):
            text = raw.get("text") or ""
            ids = []
            for n, line in enumerate(text.split("\n")):
                lid = f"{raw['node_id']}:l{n}"
                lines[lid] = line
                ids.append(lid)
            fields = {k: raw[k] for k in ("node_id", "type", "raw_label", "parent_id", "order") if k in raw}
            nodes.append(StructuralNode(**fields, text=text, page_range=[page_number],
                                        source_file_id=file_id, page_revision_id=revision,
                                        page_in_file=1, source_line_ids=ids))
        page_text = "\n".join(lines.values())
        pages.append(PageSnapshot(page_revision_id=revision, page_number=page_number, text=page_text,
                                  source_file_id=file_id, page_in_file=1, line_texts=lines,
                                  source_hash="sha256:" + hashlib.sha256(page_text.encode()).hexdigest()))
        sources.append(SourceFile(file_id=file_id, filename=f"{file_id}.json", role="body", n_pages=1))
    digest = hashlib.sha256(json.dumps(doc, ensure_ascii=False, sort_keys=True).encode()).hexdigest()
    pins = VersionPins(manifest_version=1, source_snapshot_digest=f"sha256:{digest}",
                       tenant_profile_version=1, policy_version=1, ocr_run_version=1,
                       reconstruction_version=1, extraction_version=1, index_version="public-pairs-eval")
    record = DossierRecord(tenant_id="public-pairs-eval", dossier_id=doc_id, lifecycle=LifecycleState.ACTIVE,
                           pins=pins, pages=pages, nodes=nodes, tables=[],
                           profile=TenantProfile(version=1, aliases={}, field_keys=[]),
                           acl_revision=1, permissions_by_actor={}, source_files=sources)
    record.content_sharing_consent = True
    return record


def candidate_set(doc: dict, *, variant: str, pool: list[dict] | None = None) -> PairCandidateSet:
    if variant not in {"B", "C", "E"}:
        raise ValueError("variant must be B, C or E")
    record = record_from_doc(doc)
    nodes = record.evidence_nodes()
    index = StructureIndex.build(nodes, {s.file_id: s.role for s in record.source_files})
    graph = build_contract_graph(record, [], auto_pass=False)
    excluded = frozenset(frozenset((e.source_node_id, e.target_node_id)) for e in graph.edges)
    if variant == "E":
        if pool is None:
            raise ValueError("variant E requires the frozen P1 pool (plus S4 for heldout)")
        unique = {}
        for row in pool:
            a, b = sorted((row["a"], row["b"]), key=lambda n: (index.position(n), n))
            unique[(a, b)] = PairCandidate(a, b, frozenset(), 0, None)
        candidates = tuple(unique.values())
        return PairCandidateSet(candidates, {"candidates_total": len(candidates), "candidates_kept": len(candidates),
                                            "candidates_capped": 0, "candidates_by_source": {},
                                            "excluded_luong1": 0, "excluded_ancestor": 0,
                                            "excluded_short": 0, "excluded_external_ref": 0})
    sources = ALL_SOURCES if variant == "C" else frozenset({PairSource.SAME_ARTICLE, PairSource.EXPLICIT_REF})
    return generate_pair_candidates(index, nodes, excluded_pairs=excluded, sources=sources, top_k=PAIRS_TOP_K)


def predict_doc(
    doc: dict, *, llm: Any, model: str, variant: str, pool: list[dict] | None = None,
    labeler_served_model: str | None | object = _MANIFEST_LABELER,
    cluster_id: str | None = None,
) -> dict:
    if labeler_served_model is _MANIFEST_LABELER:
        labeler_served_model = manifest.read_json(manifest.REPO_MANIFEST).get("labeler", {}).get("served_model")
    if not isinstance(labeler_served_model, str) or family(labeler_served_model) != OPENAI:
        _family_error()
    record = record_from_doc(doc)
    graph = build_contract_graph(record, [], auto_pass=False)
    candidates = candidate_set(doc, variant=variant, pool=pool)
    max_calls = max(1, math.ceil(len(candidates.candidates) / PAIRS_PER_CALL)) if variant == "E" else PAIRS_MAX_CALLS
    started = time.perf_counter()
    result = build_pair_relations(record, graph.edges, llm=llm, model=model,
                                  runtime=eval_runtime(max_calls, labeler_served_model),
                                  candidates=candidates, max_calls=max_calls)
    order = {node.node_id: (node.order, node.node_id) for node in record.evidence_nodes()}
    pool_by = {(p["a"], p["b"]): p for p in pool or []}
    predictions = []
    for relation in result.relations:
        a, b = sorted((relation.node_a_id, relation.node_b_id), key=order.__getitem__)
        row = {"pair_id": pair_id_for(doc["doc_id"], a, b), "doc_id": doc["doc_id"],
               "label": relation.label.value, "direction": None,
               "stratum": pool_by.get((a, b), {}).get("stratum")}
        if relation.directed:
            row["direction"] = "A" if relation.node_a_id == a else "B"
        predictions.append(row)
    return {"doc_id": doc["doc_id"], "cluster_id": cluster_id or doc["doc_id"],
            "predictions": predictions, "stats": result.stats, "mode": result.mode,
            "rule_only_reason": result.rule_only_reason, "batches_completed": result.batches_completed,
            "latency_ms": round((time.perf_counter() - started) * 1000, 2),
            "prompt_version": result.prompt_version}


def _percentile(values: list[float], quantile: float) -> float | None:
    if not values:
        return None
    ordered = sorted(values)
    pos = (len(ordered) - 1) * quantile
    lo = int(pos)
    hi = min(lo + 1, len(ordered) - 1)
    return round(ordered[lo] + (ordered[hi] - ordered[lo]) * (pos - lo), 2)


@lru_cache(maxsize=1)
def _cluster_method():
    root = Path(os.getenv("HARNESS_BIN_ROOT") or manifest.REPO_ROOT)
    path = root / "harness" / "scripts" / "wilson.py"
    spec = importlib.util.spec_from_file_location("_pairs_wilson", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("harness wilson module unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module.cluster_adjusted


def cluster_intervals(by_cluster: dict) -> dict:
    """Aggregate observed k/n by source cluster using the shared, K-routed Wilson method."""
    labels = sorted({label for blocks in by_cluster.values() for label in blocks})
    out = {}
    for label in labels:
        out[label] = {}
        for metric in ("precision_conservative", "precision_observed", "recall_observed", "direction_accuracy"):
            counts = []
            for blocks in by_cluster.values():
                rate = blocks.get(label, {}).get(metric)
                if rate is not None and rate["denominator"] > 0:
                    counts.append((rate["passed"], rate["denominator"]))
            out[label][metric] = ({"method": "harness.scripts.wilson.cluster_adjusted", "conf": .95,
                                   **_cluster_method()(counts)} if counts else None)
    return out


def build_report(
    results: list[dict], gold: list[dict], *, split: str, variant: str, prompt_rounds: int,
    review_provenance: dict | None = None,
) -> dict:
    if not 0 <= prompt_rounds <= 3:
        raise ValueError("prompt_rounds must be 0..3")
    predictions = [p for result in results for p in result["predictions"]]
    # GPT labels remain calibration suggestions until a human records an approval.  The
    # production metric always uses reviewed gold; dev keeps a weak-label diagnostic below,
    # but it can never close a recall gate.
    reviewed = [row.get("source") == "user-review" and isinstance(row.get("approved"), bool)
                for row in gold]
    approved_gold = sum(is_reviewed and row.get("approved") is True
                        for row, is_reviewed in zip(gold, reviewed))
    # A reviewed rejection is a deliberate negative decision, not unreviewed GPT
    # gold.  Only rows outside the user-review provenance can block the dev gate.
    unapproved_gold = sum(not is_reviewed and isinstance(row.get("approved"), bool)
                          for row, is_reviewed in zip(gold, reviewed))
    invalid_approval = sum(not isinstance(row.get("approved"), bool) for row in gold)
    scored_gold = [{**row, "approved": row.get("approved") is True and is_reviewed}
                   for row, is_reviewed in zip(gold, reviewed)]
    scored = score_relations(scored_gold, predictions, approved_only=True)
    weak_scored = score_relations(gold, predictions, approved_only=False) if (unapproved_gold or invalid_approval) else None
    if split == "dev" and invalid_approval:
        evaluation_gate = "BLOCKED_INVALID_GOLD_APPROVAL"
    elif split == "dev" and unapproved_gold:
        evaluation_gate = "BLOCKED_UNREVIEWED_DEV_GOLD"
    elif split == "dev" and not approved_gold:
        evaluation_gate = "BLOCKED_MISSING_DEV_GOLD"
    else:
        evaluation_gate = "PASS"
    rejected: Counter = Counter()
    for result in results:
        rejected.update(result["stats"].get("rejected", {}))
    rejection_reason_versions = sorted({
        version for result in results
        if isinstance((version := result["stats"].get("rejection_reason_version")), str)
    })
    clusters = {r["cluster_id"] for r in results}
    by_cluster = {}
    for cluster in sorted(clusters):
        ids = {r["doc_id"] for r in results if r["cluster_id"] == cluster}
        by_cluster[cluster] = score_relations([g for g in scored_gold if g.get("doc_id") in ids],
                                             [p for p in predictions if p["doc_id"] in ids],
                                             approved_only=True)["by_label"]
    served = sorted({r["stats"]["served_model"] for r in results if r["stats"].get("served_model")})
    p3_classifier_gate = (_classifier_gate(scored, evaluation_gate) if split == "dev" else
                          {"schema": P3_GATE_SCHEMA, "status": "NOT_APPLICABLE", "required_labels": {},
                           "false_duplicate_observed": scored["false_duplicate"]["observed"], "reason_codes": []})
    report = {**scored, "schema": REPORT_SCHEMA, "scoring_schema": SCORING_SCHEMA,
            "code_sha256": code_fingerprints(),
            "status": ("BLOCKED" if evaluation_gate != "PASS"
                       or (split == "dev" and p3_classifier_gate["status"] != "PASS") else "OBSERVED"),
            "split": split, "variant": variant,
            "ground_truth": ("unreviewed GPT suggestions (calibration only), dev"
                              if split == "dev" and (unapproved_gold or invalid_approval)
                              else "no reviewed gold, dev" if split == "dev" and not approved_gold
                              else "reviewed gold (approved=true), dev" if split == "dev"
                              else "reviewed gold (approved=true), heldout"),
            "evaluation_gate": evaluation_gate,
            "gold_provenance": {"approved": approved_gold, "unapproved": unapproved_gold,
                                "invalid_approval": invalid_approval, "scoring": "approved_only"},
            "p3_classifier_gate": p3_classifier_gate,
            "by_cluster": by_cluster, "cluster_intervals": cluster_intervals(by_cluster),
            "direction_accuracy": {label: block["direction_accuracy"]
                                                              for label, block in scored["by_label"].items()
                                                              if block["direction_accuracy"] is not None},
            "rejected": dict(sorted(rejected.items())),
            "rejection_reason_versions": rejection_reason_versions,
            "injection_signals": sum(r["stats"].get("injection_signals", 0) for r in results),
            "tokens_per_doc": {r["doc_id"]: {"prompt": r["stats"]["prompt_tokens"],
                                             "completion": r["stats"]["completion_tokens"]} for r in results},
            "calls_per_doc": {r["doc_id"]: r["stats"]["llm_calls"] for r in results},
            "latency_ms": {"p50": _percentile([r["latency_ms"] for r in results], .5),
                           "p95": _percentile([r["latency_ms"] for r in results], .95)},
            "served_model": served, "prompt_version": PROMPT_VERSION, "prompt_rounds": prompt_rounds,
            "token_estimate_D13": {"total_per_doc_range": [10000, 16000],
                                   "note": "Ước tính [ASSUMED] 10–16k token/hồ sơ; token thực ghi riêng."},
            "documents": [{k: r[k] for k in ("doc_id", "cluster_id", "mode", "rule_only_reason", "batches_completed")}
                          for r in results]}
    if review_provenance is not None:
        report["dev_review"] = review_provenance
    if weak_scored is not None:
        report["unreviewed_diagnostic"] = {
            "n_gold": weak_scored["n_gold"],
            "by_label": weak_scored["by_label"],
            "false_duplicate": weak_scored["false_duplicate"],
            "note": "Chá»‰ dÃ¹ng Ä‘á»ƒ cháº©n Ä‘oÃ¡n; khÃ´ng dÃ¹ng lÃ  gold hay gate.",
        }
    report["report_sha256"] = report_digest(report)
    return report


def render_report(report: dict) -> str:
    lines = ["# P3 — bộ phân loại cặp dev", "", f"Trạng thái: `{report['status']}`.", "",
             f"Ground truth: {report['ground_truth']}.",
             (f"Evaluation gate: `{report.get('evaluation_gate', 'UNKNOWN')}`; gold provenance: "
              f"approved={report.get('gold_provenance', {}).get('approved', 0)}, "
              f"unapproved={report.get('gold_provenance', {}).get('unapproved', 0)}."),
             f"P3 classifier gate: `{report.get('p3_classifier_gate', {}).get('status', 'UNKNOWN')}`.",
             f"Prompt: `{report['prompt_version']}`; vòng chỉnh: {report['prompt_rounds']}.",
             f"Model phục vụ: {', '.join(report['served_model']) or 'chưa quan sát'}.",
             f"Rejection reason: {', '.join(report.get('rejection_reason_versions', [])) or 'chưa quan sát'}.", ""]
    if report.get("blocked_reasons"):
        lines.extend(f"- {reason}" for reason in report["blocked_reasons"])
    lines += ["", "Số đo (k/n, Wilson95, cụm, token, latency):", "", "```json",
              json.dumps({k: report[k] for k in ("by_label", "by_cluster", "cluster_intervals", "false_duplicate", "direction_accuracy",
                                                "rejected", "injection_signals", "tokens_per_doc", "calls_per_doc",
                                                "latency_ms")}, ensure_ascii=False, indent=2), "```", ""]
    if report.get("unreviewed_diagnostic"):
        lines += ["", "Weak-label diagnostic (khÃ´ng dÃ¹ng Ä‘á»ƒ Ä‘Ã³ng gate):", "", "```json",
                  json.dumps(report["unreviewed_diagnostic"], ensure_ascii=False, indent=2), "```", ""]
    return "\n".join(lines)


def _parse_dev_review(path: Path, docs: list[dict]) -> tuple[list[dict], str, dict[str, int]]:
    """Read an explicit user-reviewed dev decision file.

    Dev GPT labels are deliberately never promoted implicitly.  The optional JSONL
    file is the only path that can make the dev evaluation gate observable.  It
    contains one decision per audited pair and is fingerprinted into the report;
    callers must provide ``source=user-review`` and a real boolean ``approved``.
    """
    path = Path(path)
    if not path.is_file():
        print("dev BLOCKED: reviewed decision file is missing", file=sys.stderr)
        raise SystemExit(2)
    try:
        rows = manifest.read_jsonl(path)
    except (OSError, ValueError, TypeError):
        print("dev BLOCKED: reviewed decision file is invalid", file=sys.stderr)
        raise SystemExit(2) from None
    pool_by: dict[str, tuple[str, str]] = {}
    for item in docs:
        doc_id = item["doc"]["doc_id"]
        for pair in item["pool"]:
            pair_id = pair.get("pair_id")
            if not isinstance(pair_id, str) or pair_id in pool_by:
                print("dev BLOCKED: dev pool has duplicate or invalid pair_id", file=sys.stderr)
                raise SystemExit(2)
            pool_by[pair_id] = (doc_id, pair["stratum"])
    decisions: list[dict] = []
    seen: set[str] = set()
    for row in rows:
        if not isinstance(row, dict):
            print("dev BLOCKED: every reviewed decision must be a JSON object", file=sys.stderr)
            raise SystemExit(2)
        pair_id = row.get("pair_id")
        if not isinstance(pair_id, str) or not pair_id or pair_id in seen or pair_id not in pool_by:
            print("dev BLOCKED: reviewed decision IDs do not match the dev pool", file=sys.stderr)
            raise SystemExit(2)
        seen.add(pair_id)
        approved = row.get("approved")
        label = row.get("gold_label")
        direction = row.get("gold_direction")
        if (not isinstance(approved, bool) or row.get("source") != "user-review"
                or (approved and label not in review.LABELS)
                or (approved and label in review.DIRECTED and direction not in review.DIRECTIONS)
                or (approved and label not in review.DIRECTED and direction is not None)
                or (not approved and (label is not None or direction is not None))):
            print("dev BLOCKED: reviewed decisions have invalid label, direction or approval", file=sys.stderr)
            raise SystemExit(2)
        doc_id, stratum = pool_by[pair_id]
        decisions.append({"pair_id": pair_id, "doc_id": doc_id, "stratum": stratum,
                          "gold_label": label, "gold_direction": direction,
                          "approved": approved, "source": "user-review"})
    if not decisions:
        print("dev BLOCKED: reviewed decision file is empty", file=sys.stderr)
        raise SystemExit(2)
    approved_by_label = Counter(row["gold_label"] for row in decisions if row["approved"])
    if any(approved_by_label[label] < 1 for label in ("CONFLICT", "DUPLICATE")):
        print("dev BLOCKED: reviewed dev gold needs an approved CONFLICT and DUPLICATE", file=sys.stderr)
        raise SystemExit(2)
    return decisions, file_digest(path), dict(sorted(approved_by_label.items()))


def _read_reviewed_dev_gold(path: Path, docs: list[dict], frozen: dict) -> tuple[list[dict], dict]:
    decisions, digest, approved_by_label = _parse_dev_review(path, docs)
    locked = frozen.get("dev_review")
    if (not isinstance(locked, dict) or locked.get("schema") != DEV_REVIEW_SCHEMA
            or locked.get("sha256") != digest or locked.get("n_rows") != len(decisions)
            or locked.get("approved_by_label") != approved_by_label):
        print("dev BLOCKED: reviewed dev gold is not locked in the manifest", file=sys.stderr)
        raise SystemExit(2)
    return decisions, {"schema": DEV_REVIEW_SCHEMA, "sha256": digest, "n_rows": len(decisions),
                       "approved_by_label": approved_by_label, "source": "user-review",
                       "manifest_locked": True}


def predict_split(
    data_dir: Path, *, split: str, variant: str, llm: Any, model: str,
    repo_manifest: Path = manifest.REPO_MANIFEST, allow_heldout: bool = False, prompt_rounds: int = 0,
    dev_review: Path | None = None,
) -> dict:
    if split == "heldout" and not allow_heldout:
        print("heldout predictions require --allow-heldout (P5)", file=sys.stderr)
        raise SystemExit(2)
    if split not in {"dev", "heldout"}:
        raise ValueError("split must be dev or heldout")
    if dev_review is not None and split != "dev":
        raise ValueError("--dev-review is valid only for the dev split")
    docs = manifest.read_split(data_dir, split, repo_manifest)
    frozen = manifest.read_json(repo_manifest)
    labeler_model = frozen.get("labeler", {}).get("served_model")
    if not isinstance(labeler_model, str) or family(labeler_model) != OPENAI:
        _family_error()
    reviewed = _read_reviewed_gold(data_dir, frozen) if split == "heldout" else None
    reviewed_dev, dev_review_provenance = ((None, None) if dev_review is None
                                           else _read_reviewed_dev_gold(dev_review, docs, frozen))
    clusters = {doc_id: c["cluster_id"] for c in frozen.get("clusters", []) for doc_id in c["doc_ids"]}
    results, gold = [], []
    extension = frozen.get("extension_s4", {}).get("files", {})
    for item in docs:
        doc, pool = item["doc"], list(item["pool"])
        if split == "heldout" and doc["doc_id"] in extension:
            pool += manifest.read_jsonl(data_dir / split / doc["doc_id"] / "s4.jsonl")
        results.append(predict_doc(doc, llm=llm, model=model, variant=variant, pool=pool,
                                   labeler_served_model=labeler_model, cluster_id=clusters.get(doc["doc_id"])))
        pooled = {p["pair_id"]: p for p in pool}
        labels = list(item["labels"])
        if split == "heldout" and doc["doc_id"] in extension:
            labels += manifest.read_jsonl(data_dir / split / doc["doc_id"] / "labels.s4.gpt.jsonl")
        for label in labels:
            row = pooled.get(label["pair_id"])
            if row is None or label.get("label_invalid") or label.get("label") not in {"GENERAL_SPECIFIC", "CONFLICT", "DUPLICATE", "REFERENCE", "UNRELATED"}:
                continue
            gold.append({"pair_id": label["pair_id"], "doc_id": doc["doc_id"], "stratum": row["stratum"],
                         "gold_label": label["label"], "gold_direction": label.get("general") or label.get("referrer"),
                         "approved": False, "source": "gpt"})
    report_gold = reviewed if reviewed is not None else reviewed_dev if reviewed_dev is not None else gold
    return build_report(results, report_gold, split=split, variant=variant,
                        prompt_rounds=prompt_rounds, review_provenance=dev_review_provenance)


def _read_reviewed_gold(data_dir: Path, frozen: dict) -> list[dict]:
    blocks = [("HG-1", frozen.get("review_selection"), frozen.get("heldout_review"),
               Path(data_dir) / "review" / "selection.jsonl",
               Path(data_dir) / "review" / "heldout_review.decisions.jsonl")]
    hg2 = frozen.get("hg2")
    if isinstance(hg2, dict) and hg2.get("selection_path"):
        for key in ("selection_path", "decisions_path"):
            value = hg2.get(key)
            if (not isinstance(value, str) or Path(value).is_absolute()
                    or ".." in Path(value).parts):
                print("heldout BLOCKED: HG-2 review path is invalid", file=sys.stderr)
                raise SystemExit(2)
        blocks.append(("HG-2", {"sha256": hg2.get("selection_sha256"),
                                 "n_rows": hg2.get("selection_n_rows")}, hg2,
                       Path(data_dir) / hg2["selection_path"],
                       Path(data_dir) / hg2["decisions_path"]))
    gold: list[dict] = []
    seen: set[str] = set()
    for name, locked, reviewed, selection_path, decisions_path in blocks:
        if (not isinstance(locked, dict) or not isinstance(reviewed, dict)
                or not selection_path.is_file() or not decisions_path.is_file()
                or file_digest(selection_path) != locked.get("sha256")
                or file_digest(decisions_path) != reviewed.get("decisions_sha256")):
            print(f"heldout BLOCKED: locked {name} review missing or modified", file=sys.stderr)
            raise SystemExit(2)
        try:
            decisions = manifest.read_jsonl(decisions_path)
            rows = manifest.read_jsonl(selection_path)
        except (OSError, ValueError):
            print(f"heldout BLOCKED: {name} review incomplete or invalid", file=sys.stderr)
            raise SystemExit(2) from None
        if (any(not isinstance(row, dict) for row in rows)
                or any(not isinstance(row.get("pair_id"), str) or not row["pair_id"]
                       or not isinstance(row.get("doc_id"), str) or not row["doc_id"]
                       or not isinstance(row.get("stratum"), str) or not row["stratum"]
                       or not isinstance(row.get("pi"), (int, float)) or isinstance(row["pi"], bool)
                       or not 0 < row["pi"] <= 1 for row in rows)):
            print(f"heldout BLOCKED: {name} selection rows invalid", file=sys.stderr)
            raise SystemExit(2)
        if any(not isinstance(decision, dict)
               or not isinstance(decision.get("pair_id"), str) or not decision["pair_id"]
               for decision in decisions):
            print(f"heldout BLOCKED: {name} decision rows invalid", file=sys.stderr)
            raise SystemExit(2)
        by_id = {r["pair_id"]: r for r in rows}
        decision_ids = [d["pair_id"] for d in decisions]
        if (len(rows) != len(by_id) or len(by_id) != locked.get("n_rows")
                or len(decisions) != reviewed.get("n_selected")
                or len(decision_ids) != len(set(decision_ids)) or set(decision_ids) != set(by_id)
                or seen & set(by_id)):
            print(f"heldout BLOCKED: {name} decisions do not match locked selection", file=sys.stderr)
            raise SystemExit(2)
        for decision in decisions:
            label, direction = decision.get("gold_label"), decision.get("gold_direction")
            if (not isinstance(decision.get("approved"), bool)
                    or decision.get("source") != "user-review"
                    or (decision["approved"] and label not in review.LABELS)
                    or (decision["approved"] and label in review.DIRECTED and direction not in {"A", "B"})
                    or (decision["approved"] and label not in review.DIRECTED and direction is not None)
                    or (not decision["approved"] and (label is not None or direction is not None))):
                print(f"heldout BLOCKED: {name} decisions invalid", file=sys.stderr)
                raise SystemExit(2)
        seen.update(by_id)
        gold.extend([{**d, "doc_id": by_id[d["pair_id"]]["doc_id"],
                      "stratum": by_id[d["pair_id"]]["stratum"]} for d in decisions])
    return gold
