"""Blind review utilities for the 95 unverified fixture candidates."""

from __future__ import annotations

import argparse
import hashlib
import importlib
import json
import os
import re
import sys
from collections import Counter
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

REPOSITORY_ROOT = Path(__file__).resolve().parents[2]
AI_SERVICE_ROOT = REPOSITORY_ROOT / "ai-service"
CORPUS_DIR = REPOSITORY_ROOT / "evals" / "corpus"
WORKSHEET_PATH = CORPUS_DIR / "candidate_review_worksheet.md"
DECISIONS_PATH = CORPUS_DIR / "candidate_decisions.json"
CANDIDATE_MANIFEST = CORPUS_DIR / "candidate_manifest.json"
GOLDEN_MANIFEST = CORPUS_DIR / "golden_manifest.json"
_ALLOWED_LABELS = frozenset({"PASS", "NEEDS_REVIEW", "INSUFFICIENT_EVIDENCE", "BLOCKED"})
_DECISIONS = frozenset({"PENDING", "APPROVE", "REJECT"})
_OLD_LABEL_MAP = {
    "PASS": "PASS",
    "REVIEW": "NEEDS_REVIEW",
    "NEEDS_REVIEW": "NEEDS_REVIEW",
    "INSUFFICIENT": "INSUFFICIENT_EVIDENCE",
    "INSUFFICIENT_EVIDENCE": "INSUFFICIENT_EVIDENCE",
    "BLOCKED": "BLOCKED",
}


def _sha256_lf(path: Path) -> str:
    return hashlib.sha256(path.read_bytes().replace(b"\r\n", b"\n")).hexdigest()


def _load_cases(repo_root: Path = REPOSITORY_ROOT) -> dict[str, Any]:
    fixture_root = repo_root / "ai-service"
    fixture_path = str(fixture_root)
    if fixture_path not in sys.path:
        sys.path.insert(0, fixture_path)
    module = importlib.import_module("fixtures.eval_suite")
    cases = module.all_eval_cases()
    if not isinstance(cases, dict) or len(cases) != 95:
        raise ValueError(f"expected 95 fixture cases, found {len(cases) if isinstance(cases, dict) else 'invalid'}")
    return cases


def _blind_text(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return re.sub(
        r"\b(?:PASS|REVIEW|INSUFFICIENT(?:_EVIDENCE)?|NEEDS_REVIEW|BLOCKED)\b",
        "[đã ẩn nhãn]",
        text,
        flags=re.IGNORECASE,
    )


def _worksheet_rows(repo_root: Path) -> list[dict[str, Any]]:
    cases = _load_cases(repo_root)
    source_paths = {
        "catalog": repo_root / "ai-service" / "fixtures" / "catalog.py",
        "synthetic": repo_root / "ai-service" / "fixtures" / "eval_suite.py",
    }
    source_hashes = {kind: _sha256_lf(path) for kind, path in source_paths.items()}
    rows = []
    for case_id, case in sorted(cases.items()):
        source_kind = "synthetic" if case_id.startswith("SYN-") else "catalog"
        source_path = source_paths[source_kind].relative_to(repo_root).as_posix()
        rows.append(
            {
                "case_id": case_id,
                "source": source_path,
                "source_sha256": source_hashes[source_kind],
                "title": _blind_text(case.title),
                "scenario_notes": _blind_text(case.notes),
                "pages": len(case.record.pages),
                "nodes": len(case.record.nodes),
                "tags": list(case.tags),
            }
        )
    return rows


def _escape_cell(value: Any) -> str:
    text = " ".join(str(value or "").split())
    return text.replace("|", "\\|")


def write_worksheet(
    output_path: Path = WORKSHEET_PATH,
    *,
    repo_root: Path = REPOSITORY_ROOT,
) -> list[dict[str, Any]]:
    """Write the blind worksheet without loading expected states or reasoner output."""

    rows = _worksheet_rows(repo_root)
    lines = [
        "# Candidate review worksheet",
        "",
        "Review the cited fixture source independently. This worksheet intentionally omits previous labels and system output.",
        "",
        "| ID | Source | Source SHA-256 | Title | Scenario / notes | Pages / nodes | Tags |",
        "|---|---|---|---|---|---:|---|",
    ]
    for row in rows:
        lines.append(
            "| "
            + " | ".join(
                (
                    _escape_cell(row["case_id"]),
                    _escape_cell(row["source"]),
                    _escape_cell(row["source_sha256"]),
                    _escape_cell(row["title"]),
                    _escape_cell(row["scenario_notes"]),
                    f"{row['pages']} / {row['nodes']}",
                    _escape_cell(", ".join(row["tags"])),
                )
            )
            + " |"
        )
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text("\n".join(lines) + "\n", encoding="utf-8", newline="\n")
    return rows


def init_decisions(output_path: Path = DECISIONS_PATH, *, repo_root: Path = REPOSITORY_ROOT) -> list[dict[str, Any]]:
    cases = _load_cases(repo_root)
    decisions = [
        {"case_id": case_id, "decision": "PENDING", "final_label": None, "basis": None}
        for case_id in sorted(cases)
    ]
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(decisions, ensure_ascii=False, indent=2) + "\n", encoding="utf-8", newline="\n")
    return decisions


def _read_json(path: Path) -> Any:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read {path}: {exc}") from exc


def _write_json_atomic(path: Path, value: Any) -> None:
    payload = (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")
    temporary = path.with_name(path.name + ".tmp")
    temporary.write_bytes(payload)
    os.replace(temporary, path)


def promote(
    decisions_path: Path,
    candidate_manifest_path: Path,
    golden_manifest_path: Path,
    *,
    reviewer: str,
) -> int:
    """Move explicitly approved, evidenced decisions into the active golden corpus."""

    if os.environ.get("CI"):
        print("promotion is disabled when CI is set", file=sys.stderr)
        return 2
    try:
        decisions = _read_json(decisions_path)
        candidate = _read_json(candidate_manifest_path)
        golden = _read_json(golden_manifest_path)
        if not isinstance(decisions, list) or not isinstance(candidate, dict) or not isinstance(golden, dict):
            raise TypeError("decision and manifest files have invalid shape")
        by_id = {}
        for item in decisions:
            if not isinstance(item, dict) or not isinstance(item.get("case_id"), str):
                raise TypeError("decision entry requires case_id")
            if item["case_id"] in by_id:
                raise ValueError(f"duplicate decision id: {item['case_id']}")
            by_id[item["case_id"]] = item
        candidate_cases = candidate.get("cases")
        golden_cases = golden.get("cases")
        if not isinstance(candidate_cases, list) or not isinstance(golden_cases, list):
            raise TypeError("candidate and golden manifests must contain case lists")

        candidate_by_id = {item["case_id"]: item for item in candidate_cases}
        golden_by_id = {item["case_id"]: item for item in golden_cases}
        if len(candidate_by_id) != len(candidate_cases) or len(golden_by_id) != len(golden_cases):
            raise ValueError("manifest contains duplicate case ids")
        if set(candidate_by_id) & set(golden_by_id):
            raise ValueError("candidate and golden manifests already overlap")

        approved = []
        for case_id, item in by_id.items():
            decision = item.get("decision")
            if decision not in _DECISIONS:
                raise ValueError(f"unknown decision for {case_id}: {decision!r}")
            if decision != "APPROVE":
                continue
            if not reviewer.strip():
                raise ValueError("--reviewer is required to promote a case")
            label = item.get("final_label")
            basis = item.get("basis")
            if label not in _ALLOWED_LABELS:
                raise ValueError(f"invalid final_label for {case_id}")
            if not isinstance(basis, str) or not basis.strip():
                raise ValueError(f"review basis is required for {case_id}")
            if case_id not in candidate_by_id and case_id not in golden_by_id:
                raise ValueError(f"unknown candidate case: {case_id}")
            approved.append((case_id, label, basis.strip()))

        if approved and not reviewer.strip():
            raise ValueError("--reviewer is required to promote cases")
        reviewed_at = datetime.now(timezone.utc).isoformat(timespec="seconds")
        for case_id, label, basis in approved:
            candidate_item = candidate_by_id.get(case_id)
            if candidate_item is None:
                existing = golden_by_id[case_id]
                if (
                    existing.get("expected_state") != label
                    or existing.get("reviewer_id") != reviewer.strip()
                    or existing.get("review_basis") != basis
                ):
                    raise ValueError(f"conflicting repeated promotion for {case_id}")
                continue
            if candidate_item.get("validation_status") != "UNVERIFIED":
                raise ValueError(f"candidate {case_id} is not UNVERIFIED")
            source = candidate_item.get("source")
            source_sha256 = candidate_item.get("source_sha256")
            if not isinstance(source, str) or not isinstance(source_sha256, str) or not source_sha256:
                raise ValueError(f"candidate {case_id} lacks source provenance")
            promoted = {
                "case_id": case_id,
                "expected_state": label,
                "source": source,
                "source_sha256": source_sha256,
                "tags": candidate_item.get("tags", []),
                "validation_status": "GOLDEN",
                "reviewer_id": reviewer.strip(),
                "reviewed_at": reviewed_at,
                "review_basis": basis,
            }
            golden_cases.append(promoted)
            candidate_cases.remove(candidate_item)
        candidate["case_count"] = len(candidate_cases)
        golden["cases"] = sorted(golden_cases, key=lambda entry: entry["case_id"])
        _write_json_atomic(candidate_manifest_path, candidate)
        _write_json_atomic(golden_manifest_path, golden)
    except (OSError, ValueError, KeyError, TypeError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"promoted {len(approved)} reviewed candidate decision(s)")
    return 0


def agreement_for_labels(expected: Sequence[str], reviewed: Sequence[str]) -> dict[str, Any]:
    if len(expected) != len(reviewed):
        raise ValueError("label sequences must have equal length")
    if not expected:
        return {"denominator": 0, "agreement": None, "cohen_kappa": None}
    denominator = len(expected)
    matches = sum(left == right for left, right in zip(expected, reviewed, strict=True))
    categories = set(expected) | set(reviewed)
    expected_counts = Counter(expected)
    reviewed_counts = Counter(reviewed)
    observed = matches / denominator
    chance = sum(expected_counts[label] * reviewed_counts[label] for label in categories) / denominator**2
    kappa = (observed - chance) / (1 - chance) if chance < 1 else 1.0 if observed == 1 else 0.0
    return {"denominator": denominator, "agreement": observed, "cohen_kappa": kappa}


def agreement(decisions_path: Path = DECISIONS_PATH, *, repo_root: Path = REPOSITORY_ROOT) -> dict[str, Any]:
    decisions = _read_json(decisions_path)
    if not isinstance(decisions, list):
        raise TypeError("decision file must contain a list")
    cases = _load_cases(repo_root)
    expected_labels = []
    reviewed_labels = []
    for item in decisions:
        if not isinstance(item, dict) or item.get("final_label") is None:
            continue
        case_id = item.get("case_id")
        if case_id not in cases:
            raise ValueError(f"unknown decision case: {case_id}")
        reviewed = item["final_label"]
        if reviewed not in _ALLOWED_LABELS:
            raise ValueError(f"invalid final label for {case_id}")
        fixture_label = _OLD_LABEL_MAP.get(cases[case_id].expected_state)
        if fixture_label is None:
            raise ValueError(f"fixture label not supported for {case_id}")
        expected_labels.append(fixture_label)
        reviewed_labels.append(reviewed)
    result = agreement_for_labels(expected_labels, reviewed_labels)
    result["compared_sources"] = 2
    return result


def main(argv: Sequence[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    subparsers = parser.add_subparsers(dest="command", required=True)
    worksheet_parser = subparsers.add_parser("worksheet")
    worksheet_parser.add_argument("--out", type=Path, default=WORKSHEET_PATH)
    decisions_parser = subparsers.add_parser("init-decisions")
    decisions_parser.add_argument("--out", type=Path, default=DECISIONS_PATH)
    promote_parser = subparsers.add_parser("promote")
    promote_parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    promote_parser.add_argument("--candidate", type=Path, default=CANDIDATE_MANIFEST)
    promote_parser.add_argument("--golden", type=Path, default=GOLDEN_MANIFEST)
    promote_parser.add_argument("--reviewer", required=True)
    agreement_parser = subparsers.add_parser("agreement")
    agreement_parser.add_argument("--decisions", type=Path, default=DECISIONS_PATH)
    args = parser.parse_args(argv)

    try:
        if args.command == "worksheet":
            rows = write_worksheet(args.out)
            print(f"wrote blind worksheet with {len(rows)} candidates")
            return 0
        if args.command == "init-decisions":
            decisions = init_decisions(args.out)
            print(f"wrote {len(decisions)} pending decisions")
            return 0
        if args.command == "promote":
            return promote(args.decisions, args.candidate, args.golden, reviewer=args.reviewer)
        if args.command == "agreement":
            print(json.dumps(agreement(args.decisions), ensure_ascii=False, sort_keys=True))
            return 0
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
