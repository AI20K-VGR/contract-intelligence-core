"""Run the AI2 product-flow evaluation against deterministic code and live NineRouter.

Examples:
  python scripts/live_eval.py --mode deterministic
  python scripts/live_eval.py --mode live --case HD-TONG-HOP
  python scripts/live_eval.py --mode live --vector-mode auto
  python scripts/live_eval.py --mode live --vector-mode on --repeat-hard 2 \
    --review-output --strict

The normal report contains metadata, scores and sanitized traces only. The
optional review output is intentionally local-only and contains the complete
fixture input and AI2 responses, but never API keys or prompts.
"""

from __future__ import annotations

import argparse
from copy import deepcopy
import json
import os
import re
import sys
import time
import xml.etree.ElementTree as ET
from collections import Counter
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


PINNED_CHAT = "gh/gpt-4o"
PINNED_EMBEDDING = "openrouter/openai/text-embedding-3-small"
PINNED_EMBEDDING_DIMENSIONS = 1536


def _configure_live(args: argparse.Namespace) -> None:
    os.environ["AI2_LLM_MODEL"] = args.chat_model
    os.environ["AI2_LLM_STRONG_MODEL"] = args.chat_model
    os.environ["AI2_EMBEDDING_MODEL"] = args.embedding_model
    os.environ["AI2_EMBEDDING_DIMENSIONS"] = str(args.embedding_dimensions)
    os.environ["AI2_EMBEDDING_DISCOVERY_ENABLED"] = "true"
    os.environ["AI2_VECTOR_RECALL_ENABLED"] = "false" if args.vector_mode == "off" else "true"


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser()
    parser.add_argument("--mode", choices=("deterministic", "live", "both"), default="both")
    parser.add_argument("--case", action="append", dest="case_ids")
    parser.add_argument("--repeat-hard", type=int, default=0)
    parser.add_argument("--output", default="artifacts/ai2-eval")
    parser.add_argument("--chat-model", default=PINNED_CHAT)
    parser.add_argument("--embedding-model", default=os.getenv("AI2_EMBEDDING_MODEL", PINNED_EMBEDDING))
    parser.add_argument("--embedding-dimensions", type=int, default=PINNED_EMBEDDING_DIMENSIONS)
    parser.add_argument("--vector-mode", choices=("auto", "on", "off"), default="auto")
    parser.add_argument(
        "--review-output",
        action="store_true",
        help="write full local input/output artifacts for manual review",
    )
    parser.add_argument(
        "--strict",
        action="store_true",
        help="return non-zero when machine acceptance checks fail",
    )
    parser.add_argument(
        "--retry-provider-errors",
        action="store_true",
        help="retry transient provider errors until the request succeeds",
    )
    parser.add_argument(
        "--resume",
        action="store_true",
        help="resume from the output directory checkpoint",
    )
    return parser.parse_args()


def _safe_status(value: Any) -> str | None:
    if value is None:
        return None
    return getattr(value, "value", str(value))


RETRYABLE_STATUS_CODES = {429, 500, 502, 503, 504}


def _status_code_from_error(error: BaseException) -> int | None:
    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None) or getattr(error, "status_code", None)
    if isinstance(status, int):
        return status
    match = re.search(r"\b(429|500|502|503|504)\b", str(error))
    return int(match.group(1)) if match else None


def _retry_after_seconds(error: BaseException, attempt: int) -> float:
    response = getattr(error, "response", None)
    headers = getattr(response, "headers", None) or {}
    raw = headers.get("retry-after") or headers.get("Retry-After") if hasattr(headers, "get") else None
    try:
        if raw is not None:
            return max(0.1, min(float(raw), 60.0))
    except (TypeError, ValueError):
        pass
    return float(min(2 ** min(attempt, 5), 60))


def _is_retryable_response(response: Any) -> bool:
    return int(getattr(response, "status_code", 0) or 0) in RETRYABLE_STATUS_CODES


def _is_retryable_error(error: BaseException) -> bool:
    status = _status_code_from_error(error)
    if status in RETRYABLE_STATUS_CODES:
        return True
    return isinstance(error, (TimeoutError, ConnectionError)) or any(
        token in str(error).casefold() for token in ("timeout", "timed out", "connection reset", "temporarily unavailable")
    )


def _post_with_retry(
    client: Any,
    url: str,
    *,
    retry_provider_errors: bool,
    retry_log: list[dict[str, Any]],
    **kwargs: Any,
) -> tuple[Any | None, BaseException | None]:
    """POST and wait through transient provider failures when requested."""

    attempt = 0
    while True:
        try:
            response = client.post(url, **kwargs)
            if retry_provider_errors and _is_retryable_response(response):
                error = RuntimeError(f"provider HTTP {response.status_code}")
                delay = _retry_after_seconds(error, attempt)
                attempt += 1
                retry_log.append({"status_code": response.status_code, "attempt": attempt, "delay_seconds": delay})
                print(f"[retry] {url} HTTP {response.status_code}; waiting {delay:.1f}s (attempt {attempt})", flush=True)
                time.sleep(delay)
                continue
            return response, None
        except Exception as error:  # provider SDK errors are not uniform across OpenAI-compatible routers
            if not retry_provider_errors or not _is_retryable_error(error):
                return None, error
            delay = _retry_after_seconds(error, attempt)
            attempt += 1
            retry_log.append(
                {
                    "error_type": type(error).__name__,
                    "status_code": _status_code_from_error(error),
                    "attempt": attempt,
                    "delay_seconds": delay,
                }
            )
            print(
                f"[retry] {type(error).__name__} status={_status_code_from_error(error)}; "
                f"waiting {delay:.1f}s (attempt {attempt})",
                flush=True,
            )
            time.sleep(delay)


def _state_matches(
    expected: str,
    actual: str | None,
    *,
    extract_ok: bool,
    job_status: str,
    query: str | None,
    ask_state: str | None,
) -> bool:
    """Match the catalog label to the state the pipeline actually emits.

    PASS is only PASS. REVIEW is only NEEDS_REVIEW. An HTTP failure is never
    evidence that a BLOCKED case was enforced. A no-query INSUFFICIENT case
    must stay uncertain; a PASS job does not count.
    """

    if not extract_ok:
        return False
    if expected == "BLOCKED":
        return actual == "BLOCKED"
    if expected == "INSUFFICIENT":
        if query:
            return ask_state == "INSUFFICIENT_EVIDENCE"
        return actual in {"NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE"}
    if expected == "REVIEW":
        return job_status == "SUCCEEDED" and actual == "NEEDS_REVIEW"
    if expected == "PASS":
        return job_status == "SUCCEEDED" and actual == "PASS"
    return False


def _contains_legal_winner(value: Any) -> bool:
    if isinstance(value, dict):
        if value.get("legal_winner") is True:
            return True
        for key in ("finding_type", "disposition", "model_disposition"):
            if str(value.get(key) or "").upper() in {"LEGAL_WINNER", "WINNER"}:
                return True
        return any(_contains_legal_winner(item) for item in value.values())
    if isinstance(value, list):
        return any(_contains_legal_winner(item) for item in value)
    return False


def _llm_calls_used(job: dict[str, Any]) -> int:
    coverage = ((job.get("contribution") or {}).get("coverage") or {})
    runtime = coverage.get("runtime") or {}
    try:
        return int(runtime.get("llm_calls_used") or 0)
    except (TypeError, ValueError):
        return 0


def _labels_match(labels: list[str], pattern: str) -> bool:
    return any(re.search(pattern, (label or "").strip(), re.IGNORECASE) for label in labels)


def _claim_violated(claim: str, observed: dict[str, Any]) -> bool | None:
    """True when the banned behavior is in the payload, False when it is absent.

    None means this token has no structural check yet. Callers must not treat
    None as a pass.
    """

    job = observed.get("job") or {}
    facts = observed.get("facts") or []
    before = list(observed.get("before_labels") or [])
    after = list(observed.get("after_labels") or [])
    if claim == "legal_winner":
        return _contains_legal_winner(observed.get("answer")) or _contains_legal_winner(job)
    if claim == "unbounded_embed":
        retrieval = observed.get("retrieval") or {}
        try:
            hits = int(retrieval.get("vector_hits") or 0)
        except (TypeError, ValueError):
            hits = 0
        return hits > 0
    if claim == "silent_external_fallback":
        if observed.get("egress_approved", True):
            return False
        return _llm_calls_used(job) > 0
    if claim in {"full_pdf_dump", "dump_all_rows_to_llm", "single_32k_clause"}:
        # No model call means the document was not sent to a model. A call
        # without the prompt text is not evidence either way.
        if _llm_calls_used(job) == 0:
            return False
        return None
    if claim == "existence_leak":
        allowed = {str(observed.get("tenant_id") or ""), str(observed.get("dossier_id") or "")}

        def foreign(value: Any) -> bool:
            if isinstance(value, dict):
                for key in ("tenant_id", "dossier_id"):
                    found = value.get(key)
                    if isinstance(found, str) and found not in allowed:
                        return True
                return any(foreign(item) for item in value.values())
            if isinstance(value, list):
                return any(foreign(item) for item in value)
            return False

        return foreign({"answer": observed.get("answer"), "facts": facts})
    if claim == "invented_clause_3":
        pattern = r"^Điều\s*3\b"
        return _labels_match(after, pattern) and not _labels_match(before, pattern)
    if claim == "invented_annex_7":
        pattern = r"^Phụ lục\s*7\b"
        return _labels_match(after, pattern) and not _labels_match(before, pattern)
    if claim == "missing_as_zero":
        sentinels = {"", "-", "—", "n/a", "na", "missing", "trống"}
        for fact in facts:
            raw = str(fact.get("raw_value") or "").strip().casefold()
            if raw in sentinels and str(fact.get("normalized_value")) in {"0", "0.0"}:
                return True
        return False
    if claim == "fx_convert":
        for fact in facts:
            raw = str(fact.get("raw_value") or "")
            currency = str(fact.get("currency") or "")
            has_usd = bool(re.search(r"\bUSD\b", raw, re.IGNORECASE))
            has_vnd = bool(re.search(r"VND|đồng", raw, re.IGNORECASE))
            if has_usd and not has_vnd and currency == "VND":
                return True
            if has_vnd and not has_usd and currency == "USD":
                return True
        return False
    if claim in {"complete_total", "complete_total_without_rows", "fake_total"}:
        page_digits = re.sub(r"\D", "", str(observed.get("page_text") or ""))
        for fact in facts:
            key = f"{fact.get('item_key') or ''} {fact.get('subject') or ''}"
            if not re.search(r"total|tổng|subtotal", key, re.IGNORECASE):
                continue
            digits = re.sub(r"\D", "", str(fact.get("normalized_value") or ""))
            if digits and digits not in page_digits:
                return True
        return False
    if claim == "merge_same_label":
        def clause_counts(labels: list[str]) -> Counter[str]:
            counts: Counter[str] = Counter()
            for label in labels:
                match = re.match(r"^Điều\s+\d+$", (label or "").strip(), re.IGNORECASE)
                if match:
                    counts[match.group(0).casefold()] += 1
            return counts

        before_counts = clause_counts(before)
        after_counts = clause_counts(after)
        return any(count >= 2 and after_counts.get(label, 0) < count for label, count in before_counts.items())
    if claim == "fake_dieu_number":
        pattern = r"^Điều\s+\d+"
        return _labels_match(after, pattern) and not _labels_match(before, pattern)
    if claim == "flatten_levels":
        before_parents = observed.get("before_parents") or {}
        after_parents = observed.get("after_parents") or {}
        return any(
            parent and node_id in after_parents and not after_parents[node_id]
            for node_id, parent in before_parents.items()
        )
    if claim == "overwrite_raw":
        for fact in facts:
            raw = str(fact.get("raw_value") or "")
            span = str((fact.get("citation") or {}).get("text_span") or "")
            if span and raw and raw != span and re.fullmatch(r"\d+", raw) and re.sub(r"\D", "", span) == raw:
                return True
        return False
    if claim == "flatten_tier":
        for fact in facts:
            if fact.get("condition"):
                continue
            norm = str(fact.get("normalized_value") or "")
            if "%" in norm or "/" in norm:
                return True
        return False
    if claim == "force_compare":
        for candidate in observed.get("candidates") or []:
            disposition = str(candidate.get("disposition") or candidate.get("finding_type") or "")
            reason = str(candidate.get("reason") or "")
            forced = disposition in {"COMPARABLE_MATCH", "COMPARABLE_DIFFERENCE"}
            if forced and re.search(r"không so|khác phạm vi|not comparable", reason, re.IGNORECASE):
                return True
        return False
    if claim in {"llm_first_classify", "one_shot_all_annex"}:
        if _llm_calls_used(job) == 0:
            return False
        return None
    if claim == "double_publish":
        seen: set[tuple[str, str]] = set()
        for fact in facts:
            key = (str(fact.get("item_key") or ""), str(fact.get("normalized_value") or ""))
            if not key[0]:
                continue
            if key in seen:
                return True
            seen.add(key)
        return False
    if claim == "mutate_old_result":
        prior = observed.get("prior_fact_values")
        if not prior:
            return False
        current = [str(fact.get("normalized_value") or "") for fact in facts]
        return list(prior) != current
    if claim == "unpinned_alias":
        allowed = {str(item) for item in (observed.get("aliases") or [])}
        page = str(observed.get("page_text") or "")
        for fact in facts:
            norm = str(fact.get("normalized_value") or "")
            if not norm:
                continue
            if norm not in page and norm not in allowed:
                return True
        return False
    return None


def _claim_report(claims: list[str], observed: dict[str, Any]) -> tuple[list[str], list[str]]:
    hits: list[str] = []
    unchecked: list[str] = []
    for claim in claims:
        violated = _claim_violated(claim, observed)
        if violated is None:
            unchecked.append(claim)
        elif violated:
            hits.append(claim)
    return hits, unchecked


def _citation_errors(answer: dict[str, Any], record: Any) -> list[str]:
    valid = {node.node_id: node for node in record.nodes}
    pages = {page.page_revision_id: page for page in record.pages}
    tables = {table.table_id: table for table in record.tables}
    errors: list[str] = []
    for citation in answer.get("citations") or []:
        node_id = citation.get("node_id") if isinstance(citation, dict) else None
        if node_id not in valid:
            errors.append(f"unknown_node:{node_id}")
            continue
        node = valid[node_id]
        page_revision = citation.get("page_revision_id") if isinstance(citation, dict) else None
        if page_revision and node.page_revision_id and page_revision != node.page_revision_id:
            errors.append(f"page_revision_mismatch:{node_id}")
        span = citation.get("text_span") if isinstance(citation, dict) else ""
        if not span:
            errors.append(f"empty_span:{node_id}")
            continue
        table_id = citation.get("table_id") if isinstance(citation, dict) else None
        cell_id = citation.get("cell_id") if isinstance(citation, dict) else None
        if table_id or cell_id:
            table = tables.get(table_id or "")
            cell = next((item for item in (table.cells if table else []) if item.cell_id == cell_id), None)
            if table is None or cell is None or cell.text != span:
                errors.append(f"span_not_in_table_cell:{node_id}")
            continue
        page = pages.get(page_revision or "")
        page_text = (page.text if page else "") or ("\n".join(page.line_texts.values()) if page else "")
        if page is None:
            errors.append(f"unknown_page:{node_id}")
        elif span not in page_text:
            errors.append(f"span_not_in_source:{node_id}")
    return errors


def _jsonable(value: Any) -> Any:
    """Convert Pydantic/dataclass values into JSON-safe review data."""

    if hasattr(value, "model_dump"):
        return value.model_dump(mode="json")
    if hasattr(value, "__dataclass_fields__"):
        from dataclasses import asdict

        return _jsonable(asdict(value))
    if isinstance(value, dict):
        return {str(key): _jsonable(item) for key, item in value.items()}
    if isinstance(value, (list, tuple)):
        return [_jsonable(item) for item in value]
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    return str(value)


def _review_input(pack: Any) -> dict[str, Any]:
    """Return the complete fixture input without runtime request metadata."""

    return {
        "case": pack.to_meta(),
        "record": _jsonable(pack.record),
        "envelope": _jsonable(pack.envelope),
    }


def _evaluate_case(
    client: Any,
    pack: Any,
    *,
    use_llm: bool,
    use_vector: bool,
    run_label: str,
    capture_review: bool = False,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    from app.api import main

    # The historical catalog uses a placeholder digest for many independent
    # fixtures. A live vector run must never share those indexes, so each
    # evaluation gets an immutable, case-scoped snapshot identity.
    pack = deepcopy(pack)
    before_labels = [node.raw_label or "" for node in pack.record.nodes]
    before_parents = {node.node_id: node.parent_id for node in pack.record.nodes}
    page_text = "\n".join(page.text or "" for page in pack.record.pages)
    digest = f"sha256:eval-{pack.case_id.lower()}"
    pack.record.pins.source_snapshot_digest = digest
    pack.envelope.pins.source_snapshot_digest = digest

    # Isolate the case while still exercising the public HTTP routes.
    main.SESSIONS.clear()
    main.JOBS.clear()
    main.STORE = main.InMemorySnapshotStore()
    started = time.perf_counter()
    view = main._open_session(pack.record, pack.envelope, f"{pack.case_id}.snapshot", "eval", {"case_id": pack.case_id})
    sid = view["session_id"]
    extract_response = client.post(f"/api/workspace/{sid}/extract", json={"use_llm": use_llm})
    extract_ok = extract_response.status_code == 200
    payload = extract_response.json() if extract_ok else {"error": extract_response.text[:300]}
    job = payload.get("job") or {}
    actual_state = _safe_status(job.get("review_state"))
    query = pack.query
    ask_payload: dict[str, Any] = {}
    ask_ok = True
    if query:
        ask_response = client.post(
            f"/api/workspace/{sid}/ask",
            json={"query": query, "use_llm": use_llm, "use_vector": use_vector},
        )
        ask_ok = ask_response.status_code == 200
        ask_payload = ask_response.json() if ask_ok else {"error": ask_response.text[:300]}
    record = main.SESSIONS[sid]["record"]
    citation_checked = bool(query)
    citation_errors = _citation_errors(ask_payload, record) if citation_checked and ask_ok else (["ask_http_error"] if citation_checked else [])
    expected = pack.expected_state
    job_status = str(job.get("status") or "")
    retrieval_trace = ask_payload.get("retrieval_trace") or {}
    forbidden_hits, unchecked_claims = _claim_report(
        list(pack.expected_no_claims),
        {
            "answer": ask_payload.get("answer"),
            "job": job,
            "retrieval": retrieval_trace,
            "egress_approved": bool(getattr(record, "egress_approved", True)),
            "before_labels": before_labels,
            "after_labels": [node.raw_label or "" for node in record.evidence_nodes()],
            "before_parents": before_parents,
            "after_parents": {node.node_id: node.parent_id for node in record.evidence_nodes()},
            "candidates": ((job.get("contribution") or {}).get("candidates") or []),
            "aliases": [
                name
                for canonical, names in ((getattr(record.profile, "aliases", None) or {}).items())
                for name in [canonical, *list(names)]
            ],
            "page_text": page_text,
            "facts": [fact.model_dump() for fact in (record.facts or [])],
            "tenant_id": record.tenant_id,
            "dossier_id": record.dossier_id,
        },
    )
    state_match = _state_matches(
        expected,
        actual_state,
        extract_ok=extract_ok,
        job_status=job_status,
        query=query,
        ask_state=ask_payload.get("review_state"),
    )
    expected_match = state_match and not forbidden_hits and not unchecked_claims
    row = {
        "case_id": pack.case_id,
        "run": run_label,
        "expected_state": expected,
        "actual_extract_state": actual_state,
        "actual_ask_state": ask_payload.get("review_state"),
        "extract_http_ok": extract_ok,
        "ask_http_ok": ask_ok,
        "expected_match": expected_match,
        "state_match": state_match,
        "citation_checked": citation_checked,
        "citation_valid": not citation_errors,
        "citation_errors": citation_errors[:10],
        "forbidden_claims": forbidden_hits,
        "unchecked_claims": unchecked_claims,
        "n_citations": len(ask_payload.get("citations") or []),
        "use_vector": use_vector,
        "vector_status": retrieval_trace.get("vector_status", "NOT_REQUESTED"),
        "embedding_model": retrieval_trace.get("embedding_model"),
        "embedding_dimensions": retrieval_trace.get("embedding_dimensions"),
        "vector_hits": retrieval_trace.get("vector_hits", 0),
        "n_pages": len(record.pages),
        "n_nodes": len(record.nodes),
        "elapsed_ms": round((time.perf_counter() - started) * 1000, 1),
    }
    review = None
    if capture_review:
        review = {
            "case_id": pack.case_id,
            "run": run_label,
            "input": _review_input(pack),
            "output": {
                "extract": {
                    "status_code": extract_response.status_code,
                    "body": payload,
                },
                "ask": {
                    "status_code": ask_response.status_code if query else None,
                    "body": ask_payload if query else None,
                },
            },
            "machine_checks": row,
            "manual_review": {
                "verdict": "PENDING",
                "severity": None,
                "reviewer_notes": "",
            },
        }
    return row, review


def _score(results: list[dict[str, Any]]) -> dict[str, Any]:
    total = len(results) or 1
    critical = [r for r in results if r["expected_state"] == "BLOCKED"]
    insufficient = [r for r in results if r["expected_state"] == "INSUFFICIENT"]
    answerable = [r for r in results if r["expected_state"] not in {"BLOCKED", "INSUFFICIENT"}]
    checked = [r for r in results if r.get("citation_checked")]
    return {
        "total": len(results),
        "expected_match_rate": round(sum(bool(r["expected_match"]) for r in results) / total, 4),
        "state_match_rate": round(sum(bool(r.get("state_match")) for r in results) / total, 4),
        "unchecked_claim_cases": sum(bool(r.get("unchecked_claims")) for r in results),
        "citation_checked": len(checked),
        "citation_valid_rate": round(sum(bool(r["citation_valid"]) for r in checked) / len(checked), 4) if checked else None,
        "forbidden_claim_violations": sum(len(r["forbidden_claims"]) for r in results),
        "critical_blocked_rate": round(sum(r["actual_extract_state"] == "BLOCKED" for r in critical) / (len(critical) or 1), 4),
        "insufficient_rate": round(sum(r["actual_ask_state"] == "INSUFFICIENT_EVIDENCE" for r in insufficient) / (len(insufficient) or 1), 4),
        "answerable_pass_rate": round(sum(bool(r["expected_match"]) for r in answerable) / (len(answerable) or 1), 4),
        "p95_elapsed_ms": sorted((r["elapsed_ms"] for r in results))[max(0, int(len(results) * 0.95) - 1)] if results else 0,
        "state_counts": dict(Counter(r["actual_extract_state"] for r in results)),
    }


def _machine_failures(report: dict[str, Any]) -> list[dict[str, Any]]:
    failures: list[dict[str, Any]] = []
    for run in report.get("runs", []):
        for row in run.get("results", []):
            reasons: list[str] = []
            if not row.get("extract_http_ok"):
                reasons.append("extract_http_error")
            if not row.get("ask_http_ok"):
                reasons.append("ask_http_error")
            if not row.get("state_match", row.get("expected_match")):
                reasons.append("expected_state_mismatch")
            if row.get("citation_checked") and not row.get("citation_valid"):
                reasons.append("invalid_citation")
            if row.get("forbidden_claims"):
                reasons.append("forbidden_claim")
            if row.get("unchecked_claims"):
                reasons.append("unchecked_claim")
            if reasons:
                failures.append({"run": run.get("mode"), "case_id": row.get("case_id"), "reasons": reasons})
    return failures


def _safe_filename(value: str) -> str:
    return "".join(char if char.isalnum() or char in {"-", "_", "."} else "_" for char in value)


def _write_review_artifacts(out_dir: Path, review_rows: list[dict[str, Any]], report: dict[str, Any]) -> None:
    review_dir = out_dir / "review"
    cases_dir = review_dir / "cases"
    cases_dir.mkdir(parents=True, exist_ok=True)
    manifest_lines: list[str] = []
    markdown: list[str] = [
        "# AI2 live output review",
        "",
        "This directory contains full local fixture inputs and AI2 responses. "
        "Do not commit it or share it outside the test workspace.",
        "",
        "## Review status",
        "",
        "Every case starts as `PENDING`. Reviewer must change it to `PASS`, `FAIL`, or `REVIEW`.",
        "",
    ]
    for item in review_rows:
        filename = f"{_safe_filename(item['case_id'])}__{_safe_filename(item['run'])}.json"
        case_path = cases_dir / filename
        case_path.write_text(json.dumps(item, ensure_ascii=False, indent=2), encoding="utf-8")
        manifest_lines.append(json.dumps({"case_id": item["case_id"], "run": item["run"], "file": f"cases/{filename}"}, ensure_ascii=False))
        machine = item["machine_checks"]
        case = item["input"]["case"]
        markdown.extend(
            [
                f"## {item['case_id']} — {case.get('title', '')} ({item['run']})",
                "",
                f"- Input: `{case.get('n_pages', 0)} pages`, `{case.get('n_nodes', 0)} nodes`, `{case.get('n_tables', 0)} tables`",
                f"- Query: {case.get('query') or '(no query)'}",
                f"- Expected state: `{case.get('expected_state')}`",
                f"- Actual extraction state: `{machine.get('actual_extract_state')}`",
                f"- Actual answer state: `{machine.get('actual_ask_state')}`",
                f"- Citations: `{machine.get('n_citations')}`, valid=`{machine.get('citation_valid')}`",
                f"- Vector: `{machine.get('vector_status')}`, hits=`{machine.get('vector_hits')}`",
                f"- Machine flags: `{', '.join(machine.get('citation_errors') or machine.get('forbidden_claims') or ['none'])}`",
                f"- Full input/output: [{filename}](cases/{filename})",
                "- Manual verdict: `PENDING`",
                "- Reviewer notes:",
                "",
            ]
        )
    (review_dir / "manifest.jsonl").write_text("\n".join(manifest_lines) + ("\n" if manifest_lines else ""), encoding="utf-8")
    (review_dir / "review.md").write_text("\n".join(markdown), encoding="utf-8")
    failures = _machine_failures(report)
    triage = [
        "# AI2 machine failure triage",
        "",
        "Severity is a starting point: P0/P1 requires remediation before acceptance; P2 is non-blocking only after manual review.",
        "",
    ]
    if not failures:
        triage.append("No machine failures detected.")
    else:
        for failure in failures:
            triage.extend(
                [
                    f"- `{failure['run']}/{failure['case_id']}` — `{', '.join(failure['reasons'])}` — severity: `PENDING`",
                    "  - Reproduction: `python scripts/live_eval.py --mode live --vector-mode on --case <case-id> --review-output`",
                    "  - Resolution:",
                ]
            )
    (review_dir / "bug-triage.md").write_text("\n".join(triage) + "\n", encoding="utf-8")


def main() -> int:
    args = _parse_args()
    if args.mode in {"live", "both"} or args.vector_mode == "on":
        _configure_live(args)
    from fastapi.testclient import TestClient
    from fixtures.eval_suite import all_eval_cases
    from app.api.main import app
    from app.llm.client import NineRouterClient

    cases = all_eval_cases()
    if args.case_ids:
        missing = sorted(set(args.case_ids) - set(cases))
        if missing:
            print(f"unknown cases: {', '.join(missing)}", file=sys.stderr)
            return 2
        cases = {key: cases[key] for key in args.case_ids}
    client = TestClient(app)
    modes = [args.mode] if args.mode != "both" else ["deterministic", "live"]
    vector_enabled = args.vector_mode == "on"
    report: dict[str, Any] = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "config": {
            "chat_model": args.chat_model,
            "embedding_model": args.embedding_model or None,
            "embedding_dimensions": args.embedding_dimensions,
            "vector_mode": args.vector_mode,
        },
        "cases": [pack.to_meta() for pack in cases.values()],
        "runs": [],
    }
    review_rows: list[dict[str, Any]] = []
    if "live" in modes:
        health = client.get("/health")
        report["preflight"] = {"http_status": health.status_code, "health": health.json() if health.status_code == 200 else {"error": health.text[:300]}}
        health_body = health.json() if health.status_code == 200 else {}
        if health.status_code != 200 or health_body.get("llm") != "ready" or health_body.get("model") != args.chat_model:
            print(json.dumps(report["preflight"], ensure_ascii=False))
            return 3
        embedding = health_body.get("embedding") or {}
        if args.vector_mode == "auto":
            vector_enabled = embedding.get("status") == "READY"
        if vector_enabled and (
            embedding.get("status") != "READY"
            or embedding.get("selected_model") != args.embedding_model
            or embedding.get("dimensions") != args.embedding_dimensions
        ):
            report["preflight"]["error"] = "pinned embedding capability mismatch"
            print(json.dumps(report["preflight"], ensure_ascii=False))
            return 3
        report["config"].update(
            {
                "embedding_model": embedding.get("selected_model") or report["config"]["embedding_model"],
                "embedding_dimensions": embedding.get("dimensions") or report["config"]["embedding_dimensions"],
                "vector_enabled": vector_enabled,
                "embedding_status": embedding.get("status", "NOT_RUN"),
            }
        )
    else:
        vector_enabled = args.vector_mode == "on"
        report["config"]["vector_enabled"] = vector_enabled
    for mode in modes:
        rows = []
        for index, pack in enumerate(cases.values(), start=1):
            print(f"[{mode}] case {index}/{len(cases)} {pack.case_id}", flush=True)
            row, review = _evaluate_case(
                    client,
                    pack,
                    use_llm=mode == "live",
                    use_vector=vector_enabled,
                    run_label=mode,
                    capture_review=args.review_output,
                )
            rows.append(row)
            if review:
                review_rows.append(review)
        report["runs"].append({"mode": mode, "score": _score(rows), "results": rows})
    if args.repeat_hard:
        hard = [pack for pack in cases.values() if "edge" in pack.tags or "synthetic" in pack.tags]
        for index in range(args.repeat_hard):
            repeated_rows = []
            for pack in hard:
                row, review = _evaluate_case(
                    client,
                    pack,
                    use_llm=True,
                    use_vector=vector_enabled,
                    run_label=f"live-repeat-{index + 1}",
                    capture_review=args.review_output,
                )
                repeated_rows.append(row)
                if review:
                    review_rows.append(review)
            rows = repeated_rows
            report["runs"].append({"mode": f"live-repeat-{index + 1}", "score": _score(rows), "results": rows})
    traces = list(NineRouterClient.all_traces)
    report["llm_trace_summary"] = {
        "count": len(traces),
        "models": sorted({str(item.get("model")) for item in traces if item.get("model")}),
        "errors": dict(Counter(str(item.get("error_type")) for item in traces if item.get("error_type"))),
        "fallback_count": sum(bool(item.get("fallback_without_json_format")) for item in traces),
        "latency_ms": {
            "count": len([item for item in traces if item.get("latency_ms") is not None]),
            "p95": sorted(float(item["latency_ms"]) for item in traces if item.get("latency_ms") is not None)[max(0, int(len([item for item in traces if item.get("latency_ms") is not None]) * 0.95) - 1)] if any(item.get("latency_ms") is not None for item in traces) else 0,
        },
    }
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "summary.json").write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    (out_dir / "summary.md").write_text(_markdown_report(report), encoding="utf-8")
    jsonl_rows = [row | {"mode": run["mode"]} for run in report["runs"] for row in run["results"]]
    (out_dir / "cases.jsonl").write_text(
        "".join(json.dumps(row, ensure_ascii=False) + "\n" for row in jsonl_rows), encoding="utf-8"
    )
    suite = ET.Element("testsuites")
    for run in report["runs"]:
        results = run["results"]
        ts = ET.SubElement(suite, "testsuite", name=f"ai2-{run['mode']}", tests=str(len(results)))
        for row in results:
            case = ET.SubElement(ts, "testcase", name=row["case_id"], time=str(row["elapsed_ms"] / 1000))
            if not row["expected_match"] or not row["citation_valid"] or row["forbidden_claims"]:
                ET.SubElement(case, "failure", message="evaluation contract mismatch")
    ET.ElementTree(suite).write(out_dir / "junit.xml", encoding="utf-8", xml_declaration=True)
    if args.review_output:
        _write_review_artifacts(out_dir, review_rows, report)
    failures = _machine_failures(report)
    print(json.dumps({
        "output": str(out_dir),
        "review_output": bool(args.review_output),
        "machine_failures": len(failures),
        "runs": [{"mode": r["mode"], "score": r["score"]} for r in report["runs"]],
    }, ensure_ascii=False, indent=2))
    if args.strict and failures:
        return 4
    return 0


def _markdown_report(report: dict[str, Any]) -> str:
    lines = ["# AI2 full-flow evaluation", "", f"Generated: {report['generated_at']}", "", "## Configuration", "", f"- Chat: `{report['config']['chat_model']}`", f"- Embedding: `{report['config']['embedding_model']}` ({report['config']['embedding_dimensions']} dims)", f"- Vector mode: `{report['config'].get('vector_mode')}` / enabled=`{report['config'].get('vector_enabled')}`", f"- Embedding status: `{report['config'].get('embedding_status', 'NOT_RUN')}`", ""]
    for run in report["runs"]:
        score = run["score"]
        citation_rate = score["citation_valid_rate"]
        citation_text = "n/a" if citation_rate is None else f"{citation_rate:.1%}"
        lines.extend([
            f"## {run['mode']}",
            "",
            f"- Cases: {score['total']}",
            f"- Expected match: {score['expected_match_rate']:.1%}",
            f"- State match: {score.get('state_match_rate', 0):.1%}",
            f"- Unchecked claim cases: {score.get('unchecked_claim_cases', 0)}",
            f"- Citation valid: {citation_text} ({score.get('citation_checked', 0)} checked)",
            f"- Forbidden claim violations: {score['forbidden_claim_violations']}",
            f"- Critical blocked: {score['critical_blocked_rate']:.1%}",
            f"- Insufficient evidence: {score['insufficient_rate']:.1%}",
            f"- p95 elapsed: {score['p95_elapsed_ms']} ms",
            "",
        ])
    return "\n".join(lines)


if __name__ == "__main__":
    raise SystemExit(main())
