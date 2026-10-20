"""Release-verification primitives for the AI2 offline gate.

This module deliberately keeps candidate data, reviewed golden data, and
production replay separate.  It is stdlib-only so the release report can be
validated without importing an LLM client or a mirror implementation.
"""

from __future__ import annotations

import dataclasses
import hashlib
import importlib
import json
import math
import os
import statistics
import sys
import time
from pathlib import Path
from typing import Any, Callable, Iterable, Mapping


STATUSES = frozenset({"PASS", "FAIL", "BLOCKED", "NOT_RUN", "UNVERIFIED", "SKIPPED"})


class VerificationError(ValueError):
    """The release input is malformed or violates a safety invariant."""


class MutationMappingError(VerificationError):
    """A P0 rule cannot be tied to a real control and negative fixture."""


def canonical_json(value: Any) -> str:
    """Return the byte-stable JSON representation used by evidence files."""

    return json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))


def write_json(path: str | Path, value: Any) -> None:
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(canonical_json(value) + "\n", encoding="utf-8", newline="\n")


def sha256_file(path: str | Path) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _require_status(value: str) -> str:
    if value not in STATUSES:
        raise VerificationError(f"unknown verification status: {value!r}")
    return value


def validate_corpus_separation(candidate: Mapping[str, Any], golden: Mapping[str, Any]) -> dict[str, Any]:
    """Validate active candidate/golden manifests and return release metadata.

    Candidate entries are never eligible for accuracy.  A golden entry must
    carry human reviewer evidence and active candidate and golden IDs must be
    disjoint; promotion history is retained as provenance only.
    """

    candidate_cases = candidate.get("cases")
    golden_cases = golden.get("cases")
    if not isinstance(candidate_cases, list) or not isinstance(golden_cases, list):
        raise VerificationError("candidate and golden manifests must contain case lists")

    def ids(items: list[dict[str, Any]], label: str) -> set[str]:
        seen: set[str] = set()
        for item in items:
            if not isinstance(item, dict) or not isinstance(item.get("case_id"), str) or not item["case_id"].strip():
                raise VerificationError(f"{label} contains a case without case_id")
            case_id = item["case_id"]
            if case_id in seen:
                raise VerificationError(f"duplicate {label} case_id: {case_id}")
            seen.add(case_id)
        return seen

    candidate_ids = ids(candidate_cases, "candidate")
    golden_ids = ids(golden_cases, "golden")
    overlap = sorted(candidate_ids & golden_ids)
    if overlap:
        raise VerificationError(f"candidate/golden active overlap: {overlap}")

    for item in candidate_cases:
        if item.get("validation_status") != "UNVERIFIED":
            raise VerificationError(f"candidate {item['case_id']} must remain UNVERIFIED")
        if item.get("reviewer_id") or item.get("reviewed_at"):
            raise VerificationError(f"candidate {item['case_id']} carries human-review metadata")

    for item in golden_cases:
        if item.get("validation_status") != "GOLDEN":
            raise VerificationError(f"golden {item['case_id']} must be GOLDEN")
        if not item.get("reviewer_id") or not item.get("reviewed_at"):
            raise VerificationError(f"golden {item['case_id']} lacks reviewer evidence")
        if not item.get("source_sha256"):
            raise VerificationError(f"golden {item['case_id']} lacks source_sha256")

    return {
        "candidate_count": len(candidate_cases),
        "candidate_status": "UNVERIFIED" if candidate_cases else "NOT_RUN",
        "golden_count": len(golden_cases),
        "golden_status": "PASS" if golden_cases else "UNVERIFIED",
        "accuracy_claim_eligible": bool(golden_cases),
        "active_overlap": overlap,
    }


def _citation_records(value: Any) -> list[Mapping[str, Any]]:
    if not isinstance(value, list):
        return []
    return [item for item in value if isinstance(item, Mapping)]


def score_citations(actual: Any, *, required: bool = True) -> dict[str, Any]:
    """Score machine-checkable citation identity and source scope."""

    if actual in (None, ""):
        return {"status": "MISS" if required else "SKIPPED", "valid": 0, "total": 0, "issues": ["citations missing"]}
    if isinstance(actual, str):
        if actual in {"valid", "required"}:
            return {"status": "UNVERIFIED", "valid": 0, "total": 0, "issues": ["citation marker has no source identity"]}
        return {"status": "FAIL", "valid": 0, "total": 0, "issues": ["citation value is not a citation record"]}
    records = _citation_records(actual)
    issues: list[str] = []
    valid = 0
    for index, citation in enumerate(records):
        missing = [key for key in ("citation_id", "node_id", "page_revision_id") if not citation.get(key)]
        if not citation.get("quote_hash") and not citation.get("text_span"):
            missing.append("quote_hash|text_span")
        if missing:
            issues.append(f"citation[{index}] missing {','.join(missing)}")
        else:
            valid += 1
    status = "PASS" if records and not issues else ("FAIL" if records else "MISS")
    return {"status": status, "valid": valid, "total": len(records), "issues": issues}


def compare_ground_truth(expected: Mapping[str, Any], actual: Mapping[str, Any]) -> dict[str, Any]:
    """Compare a non-empty expected schema without counting empty fields."""

    if not isinstance(expected, Mapping) or not expected:
        return {"status": "BLOCKED", "fields": [], "reason": "ground truth is empty or not an object"}
    if not isinstance(actual, Mapping):
        return {"status": "FAIL", "fields": [], "reason": "production output is not an object"}

    fields: list[dict[str, Any]] = []
    for name, want in sorted(expected.items()):
        if name in {"citations", "citation"} and want in {"valid", "required"}:
            citation = score_citations(actual.get(name), required=True)
            fields.append({"field": name, **citation})
            continue
        if name not in actual:
            fields.append({"field": name, "status": "MISS", "expected": want})
            continue
        got = actual[name]
        fields.append({"field": name, "status": "PASS" if got == want else "FAIL", "expected": want, "actual": got})
    statuses = {field["status"] for field in fields}
    status = "PASS" if statuses <= {"PASS"} else ("FAIL" if "FAIL" in statuses or "MISS" in statuses else "BLOCKED")
    return {"status": status, "fields": fields}


def score_ground_truth(cases: Iterable[Mapping[str, Any]], outputs: Mapping[str, Mapping[str, Any]], *, golden_count: int) -> dict[str, Any]:
    """Score schema/citation behavior while refusing an accuracy claim without gold."""

    results: list[dict[str, Any]] = []
    for case in cases:
        case_id = str(case.get("case_id") or "")
        expected = case.get("expected")
        if case.get("status") == "SKIPPED":
            results.append({"case_id": case_id, "status": "SKIPPED", "reason": case.get("reason", "explicit skip")})
            continue
        result = compare_ground_truth(expected, outputs.get(case_id, {}))
        results.append({"case_id": case_id, **result})
    counted = [item for item in results if item["status"] in {"PASS", "FAIL"}]
    accuracy_status = "PASS" if golden_count and counted and all(item["status"] == "PASS" for item in counted) else "UNVERIFIED"
    return {
        "status": "PASS" if results and all(item["status"] == "PASS" for item in results) else "FAIL",
        "accuracy_status": accuracy_status,
        "denominator": len(counted) if golden_count else 0,
        "skipped": sum(item["status"] == "SKIPPED" for item in results),
        "results": results,
    }


def _jsonable(value: Any) -> Any:
    if hasattr(value, "model_dump"):
        try:
            return value.model_dump(mode="json")
        except TypeError:
            return value.model_dump()
    if dataclasses.is_dataclass(value):
        return dataclasses.asdict(value)
    if isinstance(value, Mapping):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    return value


_VOLATILE_OUTPUT_KEYS = frozenset({"job_id", "context_id", "review_item_id"})


def _stable_projection(value: Any) -> Any:
    """Remove run-generated identifiers before persisting release evidence."""

    if isinstance(value, Mapping):
        return {key: _stable_projection(item) for key, item in sorted(value.items()) if key not in _VOLATILE_OUTPUT_KEYS}
    if isinstance(value, list):
        return [_stable_projection(item) for item in value]
    return value


def _production_entry() -> Callable[[list[dict[str, Any]]], Any]:
    repo = Path(__file__).resolve().parents[1]
    service = repo / "ai-service"
    if str(service) not in sys.path:
        sys.path.insert(0, str(service))
    return importlib.import_module("app.ai2.v1").process_payloads_full


def replay_production(path: str | Path, *, entry: Callable[[list[dict[str, Any]]], Any] | None = None) -> dict[str, Any]:
    """Run the real AI2 entry on a tracked handoff; mirror code is never fallback."""

    source = Path(path)
    if not source.is_file():
        return {"status": "NOT_RUN", "reason": f"handoff fixture missing: {source}", "parity_executed": False}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
    except (OSError, UnicodeDecodeError, json.JSONDecodeError) as exc:
        return {"status": "BLOCKED", "reason": f"handoff fixture unreadable: {type(exc).__name__}: {exc}", "parity_executed": False}
    if not isinstance(payload, dict) or not payload.get("snapshot_id"):
        return {"status": "BLOCKED", "reason": "production parity requires a handoff object with snapshot_id", "parity_executed": False}
    try:
        output = (entry or _production_entry())([payload])
        wire = _stable_projection(_jsonable(output))
        documents = wire.get("documents", []) if isinstance(wire, Mapping) else []
        returned = documents[0].get("snapshot_id") if documents else None
        if returned != payload["snapshot_id"]:
            return {"status": "FAIL", "reason": "production replay lost snapshot_id lineage", "parity_executed": True, "snapshot_id": payload["snapshot_id"], "output": wire}
        if wire.get("cross_document_findings") != []:
            return {"status": "FAIL", "reason": "production replay emitted cross-document findings", "parity_executed": True, "snapshot_id": payload["snapshot_id"], "output": wire}
        return {"status": "PASS", "parity_executed": True, "production_entry": "app.ai2.v1.process_payloads_full", "snapshot_id": payload["snapshot_id"], "output": wire}
    except Exception as exc:  # production failure is evidence, not a skip
        return {"status": "BLOCKED", "reason": f"production replay failed: {type(exc).__name__}: {exc}", "parity_executed": True, "snapshot_id": payload["snapshot_id"]}


def replay_grounded_query(path: str | Path, *, query: str = "Điều 5 nói gì?") -> dict[str, Any]:
    """Replay the real FourLayerReasoner on an adapted AI1 snapshot."""

    source = Path(path)
    if not source.is_file():
        return {"status": "NOT_RUN", "reason": f"query handoff fixture missing: {source}", "parity_executed": False}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("snapshot_id"):
            raise VerificationError("query parity requires snapshot_id")
        repo = Path(__file__).resolve().parents[1]
        service = repo / "ai-service"
        if str(service) not in sys.path:
            sys.path.insert(0, str(service))
        from app.pipeline.ai1_snapshot_adapter import adapt_ai1_input
        from app.reasoning.stack import FourLayerReasoner
        from app.tools.gateway import ToolGateway
        from app.tools.store import InMemorySnapshotStore

        adapted = adapt_ai1_input(payload, tenant_id="tenant_a", actor_id="user_001", scope_id=f"{payload['dossier_id']}:{payload['document_id']}")
        store = InMemorySnapshotStore()
        store.put(adapted.record)
        output = FourLayerReasoner(ToolGateway(store)).run(adapted.envelope, {"type": "lookup_term", "query": query})
        if not isinstance(output, Mapping):
            return {"status": "FAIL", "reason": "production query entry returned a non-object", "parity_executed": True}
        return {
            "status": "PASS",
            "parity_executed": True,
            "production_entry": "app.reasoning.stack.FourLayerReasoner.run",
            "snapshot_id": payload["snapshot_id"],
            "output": _stable_projection(_jsonable(output)),
        }
    except Exception as exc:  # production failure is evidence, not a skip
        return {"status": "BLOCKED", "reason": f"production query replay failed: {type(exc).__name__}: {exc}", "parity_executed": True}


def _contains_key(value: Any, key: str) -> bool:
    if isinstance(value, Mapping):
        return key in value or any(_contains_key(item, key) for item in value.values())
    if isinstance(value, list):
        return any(_contains_key(item, key) for item in value)
    return False


def validate_mutation_mapping(card: Mapping[str, Any], mapping: Mapping[str, Any]) -> dict[str, Any]:
    """Require explicit rule -> control -> fixture -> mutation mappings."""

    rules = card.get("p0_rules")
    entries = mapping.get("rules")
    if not isinstance(rules, list) or not rules or not isinstance(entries, list):
        raise MutationMappingError("P0 rules and mutation mapping must both be non-empty lists")
    if len(rules) != len(entries):
        raise MutationMappingError(f"P0 rule count {len(rules)} != mutation mapping count {len(entries)}")
    expected_fields = [case.get("expect", {}) for case in card.get("case_matrix", []) if isinstance(case, Mapping)]
    flattened = set().union(*(fields.keys() for fields in expected_fields if isinstance(fields, Mapping)))
    flattened.update({"blocked", "no_leakage", "no_cross_tenant_data", "no_legal_winner", "relation_edges", "relations"})
    seen: set[str] = set()
    for index, (rule, entry) in enumerate(zip(rules, entries)):
        if not isinstance(rule, Mapping) or not isinstance(entry, Mapping):
            raise MutationMappingError(f"P0 mapping {index} is not an object")
        rule_id = entry.get("rule_id")
        control = entry.get("control_field")
        fixture = entry.get("negative_fixture")
        mutation = entry.get("mutation")
        if not all(isinstance(value, str) and value.strip() for value in (rule_id, control, fixture, mutation)):
            raise MutationMappingError(f"P0 mapping {index} requires rule_id/control_field/negative_fixture/mutation")
        if rule_id in seen:
            raise MutationMappingError(f"duplicate mutation rule_id: {rule_id}")
        if control not in flattened:
            raise MutationMappingError(f"P0 rule {rule_id} targets absent case-matrix control field: {control}")
        seen.add(rule_id)
    return {"status": "PASS", "mapped": len(entries), "rule_ids": sorted(seen)}


def run_mutation_matrix(
    card: Mapping[str, Any],
    mapping: Mapping[str, Any],
    gate: Callable[[list[dict[str, Any]]], tuple[bool, list[dict[str, Any]]]],
    *,
    fixture_factory: Callable[[Mapping[str, Any]], Mapping[str, Any]] | None = None,
    mutation_applier: Callable[[Mapping[str, Any], Mapping[str, Any]], Mapping[str, Any]] | None = None,
    result_scorer: Callable[[Mapping[str, Any]], list[dict[str, Any]]] | None = None,
    production_entry_executed: bool = False,
) -> dict[str, Any]:
    """Exercise declared mutations; refuse synthetic self-authored mismatches."""

    validate_mutation_mapping(card, mapping)
    required = (fixture_factory, mutation_applier, result_scorer)
    if any(item is None for item in required):
        return {"status": "BLOCKED", "reason": "mutation execution requires a production/scorer executor"}
    observations: list[dict[str, Any]] = []
    for index, entry in enumerate(mapping["rules"]):
        baseline = fixture_factory(entry)
        mutated = mutation_applier(entry, baseline)
        changed = mutated != baseline
        result = result_scorer(mutated)
        passed, failures = gate(result)
        observations.append({
            "rule_id": entry["rule_id"],
            "rule_index": index,
            "mutation": entry["mutation"],
            "changed": changed,
            "scorer_killed": changed and not passed,
            "failures": failures,
        })
    if not all(item["scorer_killed"] for item in observations):
        return {"status": "BLOCKED", "reason": "one or more declared mutations were no-op or survived scorer", "scorer_fixture_observations": observations}
    if not production_entry_executed:
        return {"status": "BLOCKED", "reason": "scorer fixture was exercised but production entry mutation was not executed", "scorer_fixture_observations": observations}
    return {"status": "PASS", "mapped": len(observations), "scorer_fixture_observations": observations}


def _percentile(values: list[float], percentile: float) -> float:
    if not values:
        return 0.0
    ordered = sorted(values)
    rank = max(1, math.ceil(percentile * len(ordered)))
    return ordered[rank - 1]


def run_large_dossier_benchmark(path: str | Path, *, runs: int = 3, limits: Mapping[str, float] | None = None) -> dict[str, Any]:
    """Measure deterministic AI2 replay budgets, including quota metrics."""

    source = Path(path)
    if not source.is_file():
        return {"status": "NOT_RUN", "reason": f"large-dossier fixture missing: {source}"}
    try:
        payload = json.loads(source.read_text(encoding="utf-8"))
        if not isinstance(payload, dict) or not payload.get("snapshot_id"):
            raise VerificationError("large-dossier fixture requires snapshot_id")
        fn = _production_entry()
        import psutil

        process = psutil.Process(os.getpid())
        samples: list[dict[str, float]] = []
        for _ in range(max(1, runs)):
            before = process.memory_info().rss / (1024 * 1024)
            started = time.perf_counter()
            output = _jsonable(fn([payload]))
            elapsed = (time.perf_counter() - started) * 1000
            after = process.memory_info().rss / (1024 * 1024)
            document = (output.get("documents") or [{}])[0]
            coverage = ((document.get("job") or {}).get("contribution") or {}).get("coverage") or {}
            runtime = coverage.get("runtime") or {}
            samples.append({
                "seconds": elapsed / 1000,
                "rss_mb": max(before, after),
                "tokens": float(runtime.get("embedding_tokens_used", 0)),
                "provider_calls": float(runtime.get("llm_calls_used", 0)),
                "quota": float(runtime.get("max_embedding_tokens", 0)),
                "pages": float(len(payload.get("pages") or [])),
                "members": float(len(payload.get("nodes") or [])),
                "chunks": float(coverage.get("n_units", 0)),
                "edges": float(coverage.get("n_findings", 0)),
                "citations": float(coverage.get("n_facts", 0)),
            })
        metrics = {name: {"p95": _percentile([item[name] for item in samples], 0.95), "p99": _percentile([item[name] for item in samples], 0.99)} for name in ("seconds", "rss_mb", "tokens", "provider_calls", "pages", "members", "chunks", "edges", "citations")}
        metrics["quota"] = {"used": samples[-1]["tokens"], "limit": samples[-1]["quota"], "exceeded": bool(samples[-1]["quota"] and samples[-1]["tokens"] > samples[-1]["quota"])}
        limits = dict(limits or {})
        exceeded = [key for key, bound in limits.items() if key in metrics and isinstance(metrics[key], Mapping) and metrics[key].get("p99", 0) > bound]
        workload_status = "UNVERIFIED" if samples[-1]["pages"] < 50 else ("FAIL" if exceeded else "PASS")
        result = {"status": workload_status, "runs": len(samples), "metrics": metrics, "limits": limits, "exceeded": exceeded}
        if samples[-1]["pages"] < 50:
            result["reason"] = "fixture has fewer than 50 pages; measurements are smoke-only, not large-dossier evidence"
        return result
    except ImportError as exc:
        return {"status": "BLOCKED", "reason": f"benchmark dependency unavailable: {exc}"}
    except Exception as exc:  # a real replay error is not a skip
        return {"status": "BLOCKED", "reason": f"large-dossier replay failed: {type(exc).__name__}: {exc}"}


def build_release_evidence(*, corpus: Mapping[str, Any], scoring: Mapping[str, Any], replays: list[Mapping[str, Any]], mutation: Mapping[str, Any], performance: Mapping[str, Any], registry: Mapping[str, Any], live: Mapping[str, Any]) -> dict[str, Any]:
    """Build a sorted, status-explicit release evidence document."""

    statuses = [str(item.get("status")) for item in [scoring, mutation, performance, registry, live, *replays]]
    for status in statuses:
        if status not in STATUSES:
            raise VerificationError(f"invalid evidence status: {status}")
    hard_failure = any(status in {"FAIL", "BLOCKED"} for status in statuses)
    incomplete = any(status in {"NOT_RUN", "SKIPPED", "UNVERIFIED"} for status in statuses)
    release_verdict = "BLOCKED" if hard_failure else ("UNVERIFIED" if incomplete else "PASS")
    return {
        "schema_version": "ai2.release.evidence.v1",
        "release_verdict": release_verdict,
        "accuracy_claim": "PASS" if corpus.get("accuracy_claim_eligible") and scoring.get("accuracy_status") == "PASS" else "UNVERIFIED",
        "corpus": dict(corpus),
        "ground_truth_and_citation_scoring": dict(scoring),
        "production_replays": list(replays),
        "mutation": dict(mutation),
        "large_dossier": dict(performance),
        "registry": dict(registry),
        "live": dict(live),
        "status_counts": {status: statuses.count(status) for status in sorted(STATUSES) if status in statuses},
        "deterministic": True,
    }
