from __future__ import annotations

import hashlib
import json
import os
import sys
from pathlib import Path
from unittest.mock import patch

from evals.golden.spec import QUESTION_CATEGORIES
from evals.scripts.approve_question import is_approved

ROOT = Path(__file__).resolve().parents[3]


def load_questions(path: Path) -> list[dict]:
    questions = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len({question["question_id"] for question in questions}) != len(questions):
        raise ValueError("duplicate question ID")
    if any(question.get("category") not in QUESTION_CATEGORIES for question in questions):
        raise ValueError("unknown question category")
    return questions


def execute_question(question: dict, *, root: Path = ROOT) -> dict:
    source = (root / question["source"]).resolve()
    if not source.is_relative_to(root.resolve()):
        raise ValueError("question source escapes repository")
    body = source.read_bytes().replace(b"\r\n", b"\n")
    if question.get("source_sha256") and hashlib.sha256(body).hexdigest() != question["source_sha256"]:
        raise ValueError("question source changed since review")
    if question["category"] != "permission":
        from evals.real_pipeline import run_query
        replay = run_query(json.loads(body), question["text"])
        output = replay.get("output", {})
        state = output.get("state") or output.get("review_state")
        return {**output, "state": "ANSWERED" if state == "PASS" else state,
                "replay_status": replay["status"], "production_entry": replay.get("production_entry"),
                "http_status": None, "replay_error": replay.get("reason")}

    ai_root = str(root / "ai-service")
    if ai_root not in sys.path:
        sys.path.insert(0, ai_root)
    from fastapi.testclient import TestClient

    from evals.real_pipeline import adapt_snapshot
    with patch.dict(os.environ, {"AI2_SERVICE_HMAC_SECRET": "golden-dummy-local-test", "AI2_QUERY_REQUIRE_SIGNATURE": "true",
                                 "AI2_QUERY_EGRESS_ALLOWED": "false", "AI2_QUERY_USE_VECTOR": "false", "AI2_QUERY_USE_LLM": "false"}):
        from app.api import main
        from app.security.service_envelope import build_service_envelope
        from app.tools.store import InMemorySnapshotStore
        adapted = adapt_snapshot(json.loads(body))
        store = InMemorySnapshotStore()
        store.put(adapted.record)
        payload = {"query": question["text"], "dossier_id": adapted.record.dossier_id, "snapshot_version": "ai1.snapshot.v1"}
        signed_dossier = "outside-signed-dossier" if question["permission_case"] == "wrong_dossier" else adapted.record.dossier_id
        signed_tenant = "outside-tenant" if question["permission_case"] == "wrong_tenant" else adapted.record.tenant_id
        payload["service_envelope"] = build_service_envelope(
            payload, secret="golden-dummy-local-test", tenant_id=signed_tenant, dossier_id=signed_dossier,
            actor_id="eval_actor", scopes=["ai2.query"],
        )
        with patch.object(main, "STORE", store), patch.object(main, "load_query_snapshot", lambda *args, **kwargs: None):
            response = TestClient(main.app).post("/query", json=payload)
        output = response.json()
        return {**output, "http_status": response.status_code, "citations": output.get("citations", []),
                "production_entry": "POST /query"}


def _correct(question: dict, result: dict) -> bool:
    state = result.get("state")
    if question["category"] == "permission":
        return (result.get("http_status") == 401 or state == "BLOCKED") and not result.get("citations")
    if question["category"] == "not_in_document":
        return state == "INSUFFICIENT_EVIDENCE"
    if state not in {"ANSWERED", "PASS"} or not result.get("citations"):
        return False
    import re
    answer = re.sub(r"[.,\s]", "", str(result.get("answer", "")).casefold())
    for value in question.get("gold_values", []):
        expected = re.sub(r"[.,\s]", "", str(value.get("normalized", ""))).casefold()
        if expected and expected not in answer:
            return False
    required = {line_id for span in question.get("required_spans", []) for line_id in span.get("line_ids", [])}
    cited = {citation.get("node_id") for citation in result.get("citations", []) if isinstance(citation, dict)}
    return not required or required <= cited


def report_questions(questions: list[dict], *, execute=execute_question) -> dict:
    categories = {category: {"total": 0, "correct": 0, "incorrect": 0, "accuracy": None} for category in sorted(QUESTION_CATEGORIES)}
    results = []
    for question in questions:
        if not is_approved(question):
            continue
        try:
            output = execute(question)
            correct = _correct(question, output)
        except Exception as exc:  # noqa: BLE001 - replay errors are counted as failures, never skipped
            output, correct = {"error": f"{type(exc).__name__}: {exc}"}, False
        counts = categories[question["category"]]
        counts["total"] += 1
        counts["correct" if correct else "incorrect"] += 1
        results.append({"question_id": question["question_id"], "correct": correct, "output": output})
    for counts in categories.values():
        if counts["total"]:
            counts["accuracy"] = counts["correct"] / counts["total"]
    complete = all(counts["total"] >= 10 for counts in categories.values())
    return {"status": "complete" if complete else "pending_review", "approved_count": len(results),
            "candidate_count": len(questions), "categories": categories, "results": results}
