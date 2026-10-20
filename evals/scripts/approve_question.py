"""Explicit human approval of one question, bound to question and source hashes."""

from __future__ import annotations

import argparse
import copy
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path


def content_hash(question: dict) -> str:
    content = {key: value for key, value in question.items() if key != "approval"}
    return hashlib.sha256(json.dumps(content, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()).hexdigest()


def approve_question(question: dict, *, reviewer: str, basis: str) -> dict:
    if os.environ.get("CI"):
        raise ValueError("question approval is disabled in CI")
    if not reviewer.strip() or not basis.strip():
        raise ValueError("human reviewer and source review basis are required")
    approved = copy.deepcopy(question)
    approved["approval"] = {"decision": "APPROVE", "reviewer_id": reviewer.strip(),
                            "basis": basis.strip(), "reviewed_at": datetime.now(timezone.utc).isoformat(),
                            "content_sha256": content_hash(question)}
    return approved


def is_approved(question: dict) -> bool:
    approval = question.get("approval")
    return bool(isinstance(approval, dict) and approval.get("decision") == "APPROVE"
                and approval.get("reviewer_id") and approval.get("basis") and approval.get("reviewed_at")
                and approval.get("content_sha256") == content_hash(question))


def main():
    parser = argparse.ArgumentParser(description="Duyệt từng câu sau khi người duyệt kiểm nguồn và nhãn")
    parser.add_argument("--questions", type=Path, default=Path(__file__).resolve().parents[1] / "golden/questions_v1.jsonl")
    parser.add_argument("--question-id", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument("--basis", required=True)
    parser.add_argument("--content-sha256", required=True, help="Hash của phiên bản người duyệt đã xem")
    args = parser.parse_args()
    questions = [json.loads(line) for line in args.questions.read_text(encoding="utf-8").splitlines() if line.strip()]
    matches = [question for question in questions if question["question_id"] == args.question_id]
    if len(matches) != 1 or content_hash(matches[0]) != args.content_sha256:
        parser.error("ID hoặc hash không khớp phiên bản đã xem")
    try:
        approved = approve_question(matches[0], reviewer=args.reviewer, basis=args.basis)
    except ValueError as exc:
        parser.error(str(exc))
    updated = [approved if question["question_id"] == args.question_id else question for question in questions]
    temporary = args.questions.with_suffix(".jsonl.tmp")
    temporary.write_text("".join(json.dumps(question, ensure_ascii=False, sort_keys=True) + "\n" for question in updated), encoding="utf-8")
    os.replace(temporary, args.questions)
    print(json.dumps({"question_id": args.question_id, "approval": approved["approval"]}, ensure_ascii=False))


if __name__ == "__main__":
    main()
