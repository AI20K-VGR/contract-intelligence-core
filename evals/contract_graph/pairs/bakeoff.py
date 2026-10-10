"""Held-out bake-off with locked human review and a pure recommendation gate."""

from __future__ import annotations

import csv
import ctypes
import datetime as dt
import hashlib
import importlib.util
import json
import math
import os
import re
import subprocess
import sys
import time
import uuid
from collections import Counter
from functools import lru_cache
from pathlib import Path
from typing import Any

from evals.contract_graph.dataset import _json_line, file_digest
from evals.contract_graph.pairs import manifest, predictor, review
from evals.contract_graph.pairs.models import (
    OPENAI,
    classifier_family_ok,
    classifier_model_differs_from_labeler,
    family,
)
from evals.contract_graph.pairs.pool import pair_id_for
from evals.contract_graph.pairs.score import SCORED, score_relations
from evals.contract_graph.score import rate, wilson

# predictor inserts the ai-service source root before importing the production contracts.
if str(predictor.AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(predictor.AI_SERVICE))

from app.pipeline.contract_graph.pair_candidates import CANDIDATES_VERSION, PAIRS_TOP_K
from app.pipeline.contract_graph.pair_classifier import PROMPT_VERSION
from app.pipeline.contract_graph.review_policy import (
    MIN_N,
    MIN_WILSON_LOWER,
    wilson_lower,
)

DEV_REPORT = manifest.REPO_ROOT / "evals/contract_graph/reports/l2-p3-classifier-dev.json"
E_MAX_PAIRS_PER_DOC = 300
TRIALS = (1, 2)
FINGERPRINT_FILES = ("pair_candidates.py", "pair_classifier.py", "pair_builder.py", "predictor.py", "bakeoff.py", "score.py", "client.py")
HG2_SCHEMA = "contract-graph-hg2/1"
DEV_REPORT_LOCK_SCHEMA = "contract-graph-dev-report-lock/1"
DEV_REPORT_PATH = Path("evals/contract_graph/reports/l2-p3-classifier-dev.json")
HG2_REVIEW_PATH = Path("plans/261010-1309-contract-graph-recall-remediation/reports/hg2-review.md")
HG2_SIZING_PATH = Path("plans/261010-1309-contract-graph-recall-remediation/reports/hg2-sizing.json")
HG2_SELECTION_REL = Path("review/hg2_selection.jsonl")
HG2_DECISIONS_REL = Path("review/hg2_review.decisions.jsonl")
_UNOBSERVED = object()


def _code_fingerprints() -> dict[str, str]:
    return predictor.code_fingerprints()


def _blocked(reason: str) -> None:
    print(f"P5 BLOCKED: {reason}", file=sys.stderr)
    raise SystemExit(2)


def _is_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _repo_artifact(relative: Any) -> Path | None:
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    root = manifest.REPO_ROOT.resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _git_blob_digest(relative: str) -> str | None:
    result = subprocess.run(["git", "-C", str(manifest.REPO_ROOT), "show", f"HEAD:{relative}"],
                            capture_output=True, check=False)
    if result.returncode:
        return None
    return hashlib.sha256(result.stdout.replace(b"\r\n", b"\n")).hexdigest()


def _selection(data_dir: Path, frozen: dict) -> list[dict]:
    path = data_dir / "review/selection.jsonl"
    locked = frozen.get("review_selection") or {}
    if not path.is_file() or file_digest(path) != locked.get("sha256"):
        _blocked("selection SHA mismatch")
    rows = manifest.read_jsonl(path)
    ids = [r["pair_id"] for r in rows]
    if len(ids) != len(set(ids)) or len(rows) != locked.get("n_rows"):
        _blocked("selection IDs/count mismatch")
    if any(not isinstance(r.get("pi"), (int, float)) or isinstance(r["pi"], bool)
           or not 0 < r["pi"] <= 1 for r in rows):
        _blocked("selection inclusion probability invalid")
    hg2 = frozen.get("hg2")
    if isinstance(hg2, dict) and hg2.get("selection_path"):
        path = _data_review_path(data_dir, hg2.get("selection_path"))
        if (path is None or not path.is_file()
                or file_digest(path) != hg2.get("selection_sha256")):
            _blocked("HG-2 selection SHA mismatch")
        extra = manifest.read_jsonl(path)
        _validate_selection_rows(extra, "HG-2")
        if len(extra) != hg2.get("selection_n_rows"):
            _blocked("HG-2 selection count mismatch")
        if {r["pair_id"] for r in rows} & {r["pair_id"] for r in extra}:
            _blocked("HG-2 selection overlaps locked HG-1")
        rows.extend(extra)
    return rows


def _data_review_path(data_dir: Path, relative: Any) -> Path | None:
    """Resolve a review artifact below the ignored data directory only."""
    if not isinstance(relative, str) or not relative or Path(relative).is_absolute():
        return None
    root = Path(data_dir).resolve()
    path = (root / relative).resolve()
    try:
        path.relative_to(root)
    except ValueError:
        return None
    return path


def _validate_selection_rows(rows: list[dict], name: str) -> None:
    ids = []
    for row in rows:
        if (not isinstance(row, dict)
                or not isinstance(row.get("pair_id"), str) or not row["pair_id"]
                or not isinstance(row.get("doc_id"), str) or not row["doc_id"]
                or not isinstance(row.get("stratum"), str) or not row["stratum"]
                or not isinstance(row.get("pi"), (int, float)) or isinstance(row["pi"], bool)
                or not 0 < row["pi"] <= 1):
            _blocked(f"{name} selection rows invalid")
        ids.append(row["pair_id"])
    if len(ids) != len(set(ids)):
        _blocked(f"{name} selection IDs/count mismatch")


def _review_locks(frozen: dict) -> list[dict]:
    locks = [frozen.get("heldout_review")]
    hg2 = frozen.get("hg2")
    if isinstance(hg2, dict) and hg2.get("decisions_path"):
        locks.append(hg2)
    return [lock for lock in locks if isinstance(lock, dict)]


def _combined_review_counts(frozen: dict) -> tuple[int, int]:
    """Return selected and approved totals across HG-1 and a locked HG-2 block."""
    locks = _review_locks(frozen)
    selected = sum(lock.get("n_selected", 0) for lock in locks)
    approved = sum(lock.get("n_approve", 0) + lock.get("n_relabel", 0) for lock in locks)
    return selected, approved


def _review_decisions_digest(gold: list[dict]) -> str:
    """Digest the complete reviewed gold universe used by a held-out run."""
    canonical = [{k: row[k] for k in ("pair_id", "gold_label", "gold_direction",
                                      "approved", "source", "decision") if k in row}
                 for row in sorted(gold, key=lambda row: row["pair_id"])]
    return hashlib.sha256("".join(_json_line(row) for row in canonical).encode("utf-8")).hexdigest()


def _review_selection_digest(selection: list[dict]) -> str:
    """Digest the exact combined HG-1/HG-2 sampling rows used by a run."""
    return hashlib.sha256("".join(_json_line(row) for row in selection).encode("utf-8")).hexdigest()


def import_review(data_dir: Path, csv_path: Path, *, repo_manifest: Path = manifest.REPO_MANIFEST) -> dict:
    """Validate the complete CSV, write canonical decisions, then change only heldout_review."""
    if manifest.verify(data_dir, repo_manifest):
        _blocked("frozen dataset verification failed")
    frozen = manifest.read_json(repo_manifest)
    selected = _selection(data_dir, frozen)
    decisions = review.import_sheet(csv_path)
    with csv_path.open(encoding="utf-8-sig", newline="") as fh:
        sheet = list(csv.DictReader(fh))
    by_id = {r["pair_id"]: r for r in selected}
    labels = {}
    for item in _heldout(data_dir, frozen, repo_manifest):
        rows = list(item["labels"])
        doc_id = item["doc"]["doc_id"]
        if doc_id in (frozen.get("extension_s4") or {}).get("files", {}):
            rows += manifest.read_jsonl(data_dir / "heldout" / doc_id / "labels.s4.gpt.jsonl")
        labels.update({r["pair_id"]: r for r in rows})
    ids = [d["pair_id"] for d in decisions]
    if len(ids) != len(set(ids)) or set(ids) != set(by_id) or len(ids) != len(selected):
        _blocked("review must contain exactly the unique selected IDs")
    for row in sheet:
        sel = by_id[(row.get("pair_id") or "").strip()]
        if row.get("doc_id") != sel["doc_id"] or row.get("gpt_label") != sel["gpt_label"]:
            _blocked("review metadata differs from locked selection")
        original = labels.get(sel["pair_id"])
        if original is None or original.get("label") != sel["gpt_label"] or (row.get("gpt_direction") or "").strip().upper() != review.gpt_direction(original):
            _blocked("review GPT label/direction differs from frozen labels")
    sheet_by = {(r["pair_id"] or "").strip(): r for r in sheet}
    canonical = sorted(({**d, "decision": sheet_by[d["pair_id"]]["decision"].strip().casefold()}
                        for d in decisions), key=lambda d: d["pair_id"])
    # Digest the same canonical LF JSONL representation as manifest.write_jsonl.
    digest = hashlib.sha256("".join(_json_line(d) for d in canonical).encode("utf-8")).hexdigest()
    counts = Counter(d["decision"] for d in canonical)
    locked = {"decisions_sha256": digest, "n_selected": len(canonical),
              **{f"n_{decision}": counts[decision] for decision in review.DECISIONS}}
    if frozen.get("heldout_review") and frozen["heldout_review"] != locked:
        _blocked("existing review lock differs; do not replace after trials")
    manifest.write_jsonl(data_dir / "review/heldout_review.decisions.jsonl", canonical)
    frozen["heldout_review"] = locked
    manifest.write_json(repo_manifest, frozen)
    return locked


def _hg2_selection(data_dir: Path, frozen: dict) -> tuple[Path, list[dict]]:
    """Read the pre-registered HG-2 selection and verify its proposal digest."""
    path = Path(data_dir) / HG2_SELECTION_REL
    if not path.is_file():
        _blocked("HG-2 selection is missing")
    try:
        rows = manifest.read_jsonl(path)
        sizing = manifest.read_json(manifest.REPO_ROOT / HG2_SIZING_PATH)
    except (OSError, ValueError, TypeError):
        _blocked("HG-2 selection or sizing receipt is invalid")
    proposal = sizing.get("proposal") if isinstance(sizing, dict) else None
    if (not isinstance(proposal, dict)
            or proposal.get("selection_sha256") != file_digest(path)
            or proposal.get("n_rows") != len(rows)):
        _blocked("HG-2 selection does not match the sizing receipt")
    _validate_selection_rows(rows, "HG-2")
    hg1 = _selection_hg1(data_dir, frozen)
    if {r["pair_id"] for r in rows} & {r["pair_id"] for r in hg1}:
        _blocked("HG-2 selection overlaps locked HG-1")
    return path, rows


def _selection_hg1(data_dir: Path, frozen: dict) -> list[dict]:
    path = Path(data_dir) / "review/selection.jsonl"
    locked = frozen.get("review_selection") or {}
    if not path.is_file() or file_digest(path) != locked.get("sha256"):
        _blocked("selection SHA mismatch")
    rows = manifest.read_jsonl(path)
    _validate_selection_rows(rows, "HG-1")
    if len(rows) != locked.get("n_rows"):
        _blocked("selection IDs/count mismatch")
    return rows


def _hg2_universe(data_dir: Path, frozen: dict) -> dict[str, dict]:
    universe = {}
    labels = {}
    extension = (frozen.get("extension_s4") or {}).get("files", {})
    for item in _heldout(data_dir, frozen, manifest.REPO_MANIFEST):
        for pair in item["pool"]:
            if pair["pair_id"] in universe:
                _blocked("heldout pool has duplicate pair_id")
            universe[pair["pair_id"]] = pair
        label_rows = list(item["labels"])
        doc_id = item["doc"]["doc_id"]
        if doc_id in extension:
            label_rows += manifest.read_jsonl(data_dir / "heldout" / doc_id / "labels.s4.gpt.jsonl")
        for label in label_rows:
            labels[label["pair_id"]] = label
    return {"pairs": universe, "labels": labels}


def _validate_hg2_sheet(data_dir: Path, csv_path: Path,
                        frozen: dict) -> tuple[list[dict], dict]:
    """Validate a filled HG-2 sheet without changing either lock."""
    selection_path, selection = _hg2_selection(data_dir, frozen)
    try:
        decisions = review.import_sheet(csv_path)
        with csv_path.open(encoding="utf-8-sig", newline="") as fh:
            sheet = list(csv.DictReader(fh))
    except (OSError, csv.Error, review.SheetError, ValueError):
        _blocked("HG-2 review sheet is invalid")
    selected_by_id = {row["pair_id"]: row for row in selection}
    decision_ids = [row["pair_id"] for row in decisions]
    if (len(sheet) != len(selection) or len(decisions) != len(selection)
            or len(decision_ids) != len(set(decision_ids))
            or set(decision_ids) != set(selected_by_id)):
        _blocked("HG-2 review must contain exactly the unique selected IDs")
    universe = _hg2_universe(data_dir, frozen)
    hg1_ids = {row["pair_id"] for row in _selection_hg1(data_dir, frozen)}
    if set(selected_by_id) & hg1_ids:
        _blocked("HG-2 review overlaps locked HG-1")
    by_sheet = {}
    for row in sheet:
        pair_id = (row.get("pair_id") or "").strip()
        if pair_id in by_sheet:
            _blocked("HG-2 review contains duplicate pair_id")
        by_sheet[pair_id] = row
        sel = selected_by_id.get(pair_id)
        pair = universe["pairs"].get(pair_id)
        label = universe["labels"].get(pair_id)
        if (sel is None or pair is None or label is None
                or row.get("doc_id") != sel["doc_id"]
                or row.get("gpt_label") != sel["gpt_label"]
                or row.get("gpt_direction", "").strip().upper() != review.gpt_direction(label)
                or pair.get("doc_id") != sel["doc_id"]
                or pair.get("stratum") != sel["stratum"]):
            _blocked("HG-2 review metadata differs from frozen selection")
    canonical = []
    for decision in sorted(decisions, key=lambda row: row["pair_id"]):
        sel = selected_by_id[decision["pair_id"]]
        canonical.append({**decision, "doc_id": sel["doc_id"], "stratum": sel["stratum"],
                          "decision": by_sheet[decision["pair_id"]]["decision"].strip().casefold()})
    digest = hashlib.sha256("".join(_json_line(row) for row in canonical).encode("utf-8")).hexdigest()
    counts = Counter(row["decision"] for row in canonical)
    lock = {"selection_path": HG2_SELECTION_REL.as_posix(),
            "selection_sha256": file_digest(selection_path), "selection_n_rows": len(selection),
            "decisions_path": HG2_DECISIONS_REL.as_posix(), "decisions_sha256": digest,
            "n_selected": len(canonical),
            **{f"n_{decision}": counts[decision] for decision in review.DECISIONS},
            "approved_by_label": dict(sorted(Counter(
                row["gold_label"] for row in canonical if row["approved"]
            ).items()))}
    return canonical, lock


def import_hg2_review(data_dir: Path, csv_path: Path,
                      *, repo_manifest: Path = manifest.REPO_MANIFEST) -> dict:
    """Validate a completed HG-2 sheet and write decisions outside Git.

    This deliberately does not set ``human_approved`` or mutate the manifest.  The
    separate lock command requires an explicit human approval and recall-floor choice.
    """
    if manifest.verify(data_dir, repo_manifest):
        _blocked("frozen dataset verification failed")
    frozen = manifest.read_json(repo_manifest)
    canonical, lock = _validate_hg2_sheet(data_dir, csv_path, frozen)
    manifest.write_jsonl(Path(data_dir) / HG2_DECISIONS_REL, canonical)
    return lock


def lock_hg2(data_dir: Path, *, repo_manifest: Path = manifest.REPO_MANIFEST,
             recall_floor: float = MIN_WILSON_LOWER, human_approved: bool = False,
             scope_consent: bool = False) -> dict:
    """Promote imported HG-2 decisions only after an explicit human gate."""
    if not human_approved or not scope_consent:
        _blocked("HG-2 lock requires explicit human approval and scope consent")
    if (not isinstance(recall_floor, (int, float)) or isinstance(recall_floor, bool)
            or not math.isfinite(float(recall_floor)) or float(recall_floor) < MIN_WILSON_LOWER
            or float(recall_floor) > 1):
        _blocked("HG-2 recall floor must be within [0,1] and at least the policy floor")
    if manifest.verify(data_dir, repo_manifest):
        _blocked("frozen dataset verification failed")
    frozen = manifest.read_json(repo_manifest)
    decisions_path = Path(data_dir) / HG2_DECISIONS_REL
    if not decisions_path.is_file():
        _blocked("HG-2 decisions are missing; import the reviewed sheet first")
    try:
        decisions = manifest.read_jsonl(decisions_path)
        selection_path, selection = _hg2_selection(data_dir, frozen)
    except (OSError, ValueError, TypeError):
        _blocked("HG-2 decisions or selection is invalid")
    if (len(decisions) != len(selection)
            or len({row.get("pair_id") for row in decisions}) != len(decisions)
            or {row.get("pair_id") for row in decisions} != {row.get("pair_id") for row in selection}):
        _blocked("HG-2 decisions do not match the locked selection")
    for row in decisions:
        if (not isinstance(row, dict) or row.get("source") != "user-review"
                or not isinstance(row.get("approved"), bool)):
            _blocked("HG-2 decisions lack user-review provenance")
    review_path = manifest.REPO_ROOT / HG2_REVIEW_PATH
    sizing_path = manifest.REPO_ROOT / HG2_SIZING_PATH
    if not review_path.is_file() or not sizing_path.is_file():
        _blocked("HG-2 receipt artifacts are missing")
    if frozen.get("hg2") is not None:
        _blocked("existing HG-2 lock differs; refusing replacement")
    counts = Counter(row.get("decision") for row in decisions)
    approved_by_label = dict(sorted(Counter(
        row.get("gold_label") for row in decisions if row.get("approved")
    ).items()))
    try:
        receipt = review_path.read_text(encoding="utf-8")
        sizing = manifest.read_json(sizing_path)
    except (OSError, ValueError, TypeError):
        _blocked("HG-2 receipt artifacts are invalid")
    receipt = receipt.replace("- Status: `PENDING_HUMAN_APPROVAL`", "- Status: `PASS`", 1)
    receipt = receipt.replace("- `human_approved`: `false`", "- `human_approved`: `true`", 1)
    receipt = receipt.replace("- `manifest_locked`: `false`", "- `manifest_locked`: `true`", 1)
    receipt = receipt.replace(
        "all 474 GPT suggestions are `UNRELATED`; no decision is prefilled.",
        "all 474 GPT suggestions are `UNRELATED`; the human-confirmed decisions are recorded below.",
        1,
    )
    receipt += (
        "\n## Human decision recorded\n\n"
        "- Status: `PASS`\n"
        "- `human_approved`: `true`\n"
        "- `scope_consent`: `true`\n"
        f"- Recall floor: Wilson lower `>={float(recall_floor):.2f}` for "
        f"{', '.join(SCORED)}.\n"
        f"- Reviewed rows: `{len(decisions)}`; "
        f"approve `{counts['approve']}`, relabel `{counts['relabel']}`, reject `{counts['reject']}`.\n"
        "- HG-1 rows remain unchanged; P5 is permitted only after this manifest is committed.\n"
    )
    review_path.write_text(receipt, encoding="utf-8", newline="\n")
    if not isinstance(sizing, dict):
        _blocked("HG-2 sizing receipt is not an object")
    sizing["status"] = "PASS"
    sizing["manifest_locked"] = True
    sizing["human_decision"] = {"recall_floor": {"method": "wilson_lower", "min": float(recall_floor),
                                                   "labels": list(SCORED)},
                                 "scope_consent": True, "n_selected": len(decisions),
                                 "approved_by_label": approved_by_label}
    proposal = sizing.get("proposal")
    if isinstance(proposal, dict):
        proposal["decisions_recorded"] = True
        proposal["human_action"] = "human-confirmed decisions recorded; HG-2 lock is PASS"
    sizing["note"] = "HG-2 PASS is locked with explicit human decisions; additional counts remain lower bounds."
    manifest.write_json(sizing_path, sizing)
    lock = {"schema": HG2_SCHEMA, "status": "PASS", "human_approved": True,
            "manifest_locked": True, "review_path": HG2_REVIEW_PATH.as_posix(),
            "sizing_path": HG2_SIZING_PATH.as_posix(),
            "review_sha256": file_digest(review_path), "sizing_sha256": file_digest(sizing_path),
            "selection_path": HG2_SELECTION_REL.as_posix(),
            "selection_sha256": file_digest(selection_path), "selection_n_rows": len(selection),
            "decisions_path": HG2_DECISIONS_REL.as_posix(),
            "decisions_sha256": file_digest(decisions_path), "n_selected": len(decisions),
            **{f"n_{decision}": counts[decision] for decision in review.DECISIONS},
            "approved_by_label": approved_by_label,
            "recall_floor": {"method": "wilson_lower", "min": float(recall_floor),
                             "labels": list(SCORED)}, "scope_consent": True}
    frozen["hg2"] = lock
    manifest.write_json(repo_manifest, frozen)
    return lock


def _heldout(data_dir: Path, frozen: dict, repo_manifest: Path) -> list[dict]:
    docs = manifest.read_split(data_dir, "heldout", repo_manifest)
    extension = (frozen.get("extension_s4") or {}).get("files", {})
    for item in docs:
        item["pool"] = list(item["pool"])
        doc_id = item["doc"]["doc_id"]
        if doc_id in extension:
            item["pool"] += manifest.read_jsonl(data_dir / "heldout" / doc_id / "s4.jsonl")
    return docs


def preconditions(
    data_dir: Path, *, repo_manifest: Path = manifest.REPO_MANIFEST,
    dev_report: dict | None = None, served_model: Any = _UNOBSERVED,
    require_commit_lock: bool = True,
) -> dict:
    """Offline checks; an actual served model can be supplied from the production probe."""
    data_dir = Path(data_dir)
    try:
        if manifest.verify(data_dir, repo_manifest):
            _blocked("frozen dataset verification failed")
        frozen = manifest.read_json(repo_manifest)
        locked_dev_report = frozen.get("dev_report")
        dev_path = (_repo_artifact(locked_dev_report.get("path"))
                    if isinstance(locked_dev_report, dict) else None)
        if (not isinstance(locked_dev_report, dict)
                or locked_dev_report.get("schema") != DEV_REPORT_LOCK_SCHEMA
                or locked_dev_report.get("path") != DEV_REPORT_PATH.as_posix()
                or dev_path is None
                or not _is_sha256(locked_dev_report.get("sha256"))
                or not dev_path.is_file()
                or file_digest(dev_path) != locked_dev_report.get("sha256")):
            _blocked("dev report artifact is missing or not manifest-locked")
        locked_dev = manifest.read_json(dev_path)
        dev = dev_report if dev_report is not None else locked_dev
        if dev != locked_dev:
            _blocked("dev report differs from manifest-locked artifact")
        if dev.get("status") != "OBSERVED":
            _blocked("dev report status is not OBSERVED")
        if dev.get("evaluation_gate") != "PASS":
            _blocked("dev evaluation gate is not PASS")
        if dev.get("schema") != predictor.REPORT_SCHEMA or dev.get("scoring_schema") != predictor.SCORING_SCHEMA:
            _blocked("dev report schema is stale")
        if dev.get("code_sha256") != _code_fingerprints():
            _blocked("dev report code fingerprint is stale")
        if (not _is_sha256(dev.get("report_sha256"))
                or dev.get("report_sha256") != predictor.report_digest(dev)):
            _blocked("dev report digest is missing or stale")
        provenance = dev.get("gold_provenance")
        if (not isinstance(provenance, dict)
                or any(type(provenance.get(key)) is not int for key in ("approved", "unapproved", "invalid_approval"))
                or provenance["approved"] <= 0
                or provenance["unapproved"] != 0
                or provenance["invalid_approval"] != 0):
            _blocked("dev report lacks exclusively reviewed gold")
        p3_gate = dev.get("p3_classifier_gate")
        required = p3_gate.get("required_labels") if isinstance(p3_gate, dict) else None
        if (not isinstance(p3_gate, dict) or p3_gate.get("schema") != predictor.P3_GATE_SCHEMA
                or p3_gate.get("status") != "PASS"
                or type(p3_gate.get("false_duplicate_observed")) is not int
                or p3_gate.get("false_duplicate_observed") != 0
                or not isinstance(required, dict)
                or any(not isinstance(required.get(label), dict)
                       or type(required[label].get("gold_positive")) is not int
                       or type(required[label].get("correct")) is not int
                       or required[label]["gold_positive"] < 1
                       or required[label]["correct"] < 1
                       for label in ("CONFLICT", "DUPLICATE"))):
            _blocked("P3 classifier gate is not satisfied")
        by_label = dev.get("by_label")
        false_duplicate = dev.get("false_duplicate")
        if (not isinstance(by_label, dict) or not isinstance(false_duplicate, dict)
                or type(false_duplicate.get("observed")) is not int
                or false_duplicate.get("observed") != p3_gate["false_duplicate_observed"]
                or any(not isinstance(by_label.get(label), dict)
                       or not isinstance(by_label[label].get("recall_observed"), dict)
                       or type(by_label[label]["recall_observed"].get("denominator")) is not int
                       or type(by_label[label]["recall_observed"].get("passed")) is not int
                       for label in ("CONFLICT", "DUPLICATE"))
                or any(required[label] != {
                    "gold_positive": by_label.get(label, {}).get("recall_observed", {}).get("denominator"),
                    "correct": by_label.get(label, {}).get("recall_observed", {}).get("passed"),
                } for label in ("CONFLICT", "DUPLICATE"))):
            _blocked("P3 classifier gate does not match dev metrics")
        dev_review = dev.get("dev_review")
        locked_dev_review = frozen.get("dev_review")
        if (not isinstance(dev_review, dict) or dev_review.get("schema") != predictor.DEV_REVIEW_SCHEMA
                or dev_review.get("source") != "user-review"
                or dev_review.get("manifest_locked") is not True
                or not isinstance(locked_dev_review, dict)
                or locked_dev_review.get("schema") != predictor.DEV_REVIEW_SCHEMA
                or not _is_sha256(dev_review.get("sha256"))
                or not _is_sha256(locked_dev_review.get("sha256"))
                or dev_review.get("sha256") != locked_dev_review.get("sha256")
                or type(dev_review.get("n_rows")) is not int
                or type(locked_dev_review.get("n_rows")) is not int
                or dev_review.get("n_rows") != locked_dev_review.get("n_rows")
                or dev_review.get("approved_by_label") != locked_dev_review.get("approved_by_label")):
            _blocked("dev review provenance is not manifest-locked")
        approved_by_label = dev_review.get("approved_by_label")
        if (not isinstance(approved_by_label, dict)
                or any(type(value) is not int or value < 0 for value in approved_by_label.values())
                or sum(approved_by_label.values()) != provenance["approved"]):
            _blocked("dev review counts do not match dev gold provenance")
        hg2 = frozen.get("hg2")
        floor = hg2.get("recall_floor") if isinstance(hg2, dict) else None
        floor_min = floor.get("min") if isinstance(floor, dict) else None
        floor_labels = floor.get("labels") if isinstance(floor, dict) else None
        hg2_review_path = (_repo_artifact(hg2.get("review_path"))
                          if isinstance(hg2, dict) else None)
        hg2_sizing_path = (_repo_artifact(hg2.get("sizing_path"))
                          if isinstance(hg2, dict) else None)
        if (not isinstance(hg2, dict)
                or hg2.get("schema") != HG2_SCHEMA
                or hg2.get("status") != "PASS"
                or hg2.get("human_approved") is not True
                or hg2.get("manifest_locked") is not True
                or hg2.get("review_path") != HG2_REVIEW_PATH.as_posix()
                or hg2.get("sizing_path") != HG2_SIZING_PATH.as_posix()
                or not _is_sha256(hg2.get("review_sha256"))
                or not _is_sha256(hg2.get("sizing_sha256"))
                or hg2_review_path is None
                or hg2_sizing_path is None
                or not hg2_review_path.is_file()
                or not hg2_sizing_path.is_file()
                or file_digest(hg2_review_path) != hg2.get("review_sha256")
                or file_digest(hg2_sizing_path) != hg2.get("sizing_sha256")
                or not isinstance(floor, dict)
                or floor.get("method") != "wilson_lower"
                or type(floor_min) not in (int, float)
                or isinstance(floor_min, bool)
                or not math.isfinite(float(floor_min))
                or not 0 <= float(floor_min) <= 1
                or float(floor_min) < MIN_WILSON_LOWER
                or not isinstance(floor_labels, list)
                or len(floor_labels) != len(SCORED)
                or set(floor_labels) != set(SCORED)):
            _blocked("HG-2/P4 manifest lock missing or invalid")
        if hg2.get("selection_path") or hg2.get("decisions_path"):
            selection_path = _data_review_path(data_dir, hg2.get("selection_path"))
            decisions_path = _data_review_path(data_dir, hg2.get("decisions_path"))
            if (selection_path is None or decisions_path is None
                    or not selection_path.is_file() or not decisions_path.is_file()
                    or not _is_sha256(hg2.get("selection_sha256"))
                    or not _is_sha256(hg2.get("decisions_sha256"))
                    or file_digest(selection_path) != hg2.get("selection_sha256")
                    or file_digest(decisions_path) != hg2.get("decisions_sha256")):
                _blocked("HG-2/P4 decision artifacts are missing or modified")
            try:
                hg2_selection = manifest.read_jsonl(selection_path)
                hg2_decisions = manifest.read_jsonl(decisions_path)
            except (OSError, ValueError, TypeError):
                _blocked("HG-2/P4 decision artifacts are invalid")
            _validate_selection_rows(hg2_selection, "HG-2")
            if (len(hg2_selection) != hg2.get("selection_n_rows")
                    or len(hg2_decisions) != hg2.get("n_selected")
                    or len(hg2_decisions) != sum(hg2.get(f"n_{d}", -1) for d in review.DECISIONS)
                    or any(not isinstance(row, dict) or row.get("source") != "user-review"
                           or not isinstance(row.get("approved"), bool) for row in hg2_decisions)):
                _blocked("HG-2/P4 decision counts or provenance are invalid")
        if require_commit_lock:
            _review_lock(repo_manifest, frozen)
        selected = _selection(data_dir, frozen)
        gold = predictor._read_reviewed_gold(data_dir, frozen)
        selected_count, approved_count = _combined_review_counts(frozen)
        if (selected_count != len(selected)
                or sum(g["approved"] is True for g in gold) != approved_count):
            _blocked("review decision counts mismatch")
        for block in (frozen.get("labeler") or {}, (frozen.get("extension_s4") or {}).get("labeler", frozen.get("labeler") or {})):
            model = block.get("served_model")
            if not isinstance(model, str) or family(model) != OPENAI:
                _blocked("labeler served_model must be openai")
        if served_model is not _UNOBSERVED:
            labeler_model = frozen.get("labeler", {}).get("served_model")
            if (not isinstance(served_model, str) or not classifier_family_ok(served_model)
                    or not classifier_model_differs_from_labeler(served_model, labeler_model)):
                _blocked("classifier served_model must be recognised and differ from labeler")
        if dev.get("prompt_version") != PROMPT_VERSION:
            _blocked("prompt version changed after dev freeze")
        extension = frozen.get("extension_s4") or {}
        if extension.get("candidates_version") != CANDIDATES_VERSION or extension.get("top_k") != PAIRS_TOP_K:
            _blocked("P2 candidates version/top_k changed")
        docs = _heldout(data_dir, frozen, repo_manifest)
        counts = {v: 0 for v in ("C", "B", "E")}
        max_e = 0
        universe = set()
        for item in docs:
            doc, pool = item["doc"], item["pool"]
            ids = {p["pair_id"] for p in pool}
            universe.update(ids)
            counts["E"] += len(ids)
            max_e = max(max_e, len(ids))
            for variant in ("C", "B"):
                candidates = predictor.candidate_set(doc, variant=variant, pool=pool).candidates
                found = {pair_id_for(doc["doc_id"], c.node_a, c.node_b) for c in candidates}
                if not found <= ids:
                    _blocked(f"{variant} candidates outside pool + S4")
                counts[variant] += len(found)
        if {s["pair_id"] for s in selected} - universe:
            _blocked("review selection outside gold universe")
        dev_candidates = dev.get("n_candidates")
        if dev_candidates is None:
            dev_candidates = sum(len(predictor.candidate_set(d["doc"], variant="C", pool=d["pool"]).candidates)
                                 for d in manifest.read_split(data_dir, "dev", repo_manifest))
        if not dev_candidates or not docs:
            _blocked("empty dev candidates or heldout docs")
        expected = {label: dev["by_label"][label]["denominator"] / dev_candidates * counts["C"] for label in SCORED}
        skip_e = all(n < MIN_N / 2 for n in expected.values())
        variants = ["C", "B"] if skip_e else ["C", "B", "E"]
        if "E" in variants and max_e > E_MAX_PAIRS_PER_DOC:
            _blocked("E exceeds frozen per-document cap; scope decision required")
        tokens = dev.get("tokens_per_doc") or {}
        if not tokens:
            _blocked("missing dev token measurements")
        multiplier = max(counts[v] for v in variants) / max(1, counts["C"])
        budgets = {"tokens": math.ceil(sum(sum(t.values()) for t in tokens.values()) / len(tokens) * len(docs) * 1.5 * multiplier),
                   "seconds": math.ceil(dev["latency_ms"]["p50"] / 1000 * len(docs) * 1.5 * multiplier)}
        return {"variants": variants, "candidate_counts": counts, "n_docs": len(docs), "budgets": budgets,
                "feasibility": {"expected_n": expected, "status": "KEEP_OFF_INSUFFICIENT_N expected" if skip_e else "E retained",
                                "skipped_variants": {"E": "every label expected_n < MIN_N/2"} if skip_e else {}},
                "decisions_sha256": _review_decisions_digest(gold),
                "selection_sha256": _review_selection_digest(selected), "selection_n_rows": len(selected),
                "prompt_version": PROMPT_VERSION,
                "code_sha256": _code_fingerprints(),
                "served_model_check": "OBSERVED" if served_model is not _UNOBSERVED else "pending production probe/per-call check"}
    except (OSError, ValueError, KeyError, TypeError, AttributeError):
        _blocked("invalid or incomplete frozen inputs")


def _clusters(frozen: dict) -> dict[str, str]:
    heldout = {d["doc_id"] for d in frozen["docs"] if d["split"] == "heldout"}
    return {doc_id: c["cluster_id"] for c in frozen.get("clusters", []) for doc_id in c["doc_ids"] if doc_id in heldout}


def _review_lock(repo_manifest: Path, frozen: dict) -> dict:
    """Anchor the complete dataset manifest and review chronology to the actual Git commit."""
    relative = Path(repo_manifest).resolve().relative_to(manifest.REPO_ROOT.resolve()).as_posix()
    result = subprocess.run(["git", "-C", str(manifest.REPO_ROOT), "show", f"HEAD:{relative}"],
                            capture_output=True, text=True, encoding="utf-8", check=False)
    if result.returncode or json.loads(result.stdout) != frozen:
        _blocked("review lock must be committed before heldout classification")
    dev_lock = frozen.get("dev_report")
    hg2_lock = frozen.get("hg2")
    committed_artifacts = (
        (DEV_REPORT_PATH.as_posix(), dev_lock.get("sha256") if isinstance(dev_lock, dict) else None),
        (HG2_REVIEW_PATH.as_posix(), hg2_lock.get("review_sha256") if isinstance(hg2_lock, dict) else None),
        (HG2_SIZING_PATH.as_posix(), hg2_lock.get("sizing_sha256") if isinstance(hg2_lock, dict) else None),
    )
    if any(not _is_sha256(expected) or _git_blob_digest(path) != expected
           for path, expected in committed_artifacts):
        _blocked("review lock artifacts must be present with matching content in HEAD")
    head = subprocess.run(["git", "-C", str(manifest.REPO_ROOT), "log", "-1", "--format=%H%n%cI", "--", relative],
                          capture_output=True, text=True, check=False)
    if head.returncode:
        _blocked("cannot establish review lock commit")
    commit, committed_at = head.stdout.strip().splitlines()
    return {"commit": commit, "committed_at": committed_at}


def _trace_buffer(llm: Any) -> list[dict]:
    from app.llm.client import NineRouterClient
    # classifier_client creates production clients; their traces share the class buffer.
    return NineRouterClient.all_traces if isinstance(llm, NineRouterClient) else getattr(llm, "traces", [])


def _pid_alive(pid: int) -> bool:
    if pid <= 0:
        return False
    if os.name == "nt":
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)
        if not handle:
            return False
        ctypes.windll.kernel32.CloseHandle(handle)
        return True
    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        return False
    except PermissionError:
        return True
    except OSError:
        return False
    return True


def _acquire_claim(target: Path) -> tuple[Path, str]:
    claim = target.with_suffix(target.suffix + ".claim")
    claim.parent.mkdir(parents=True, exist_ok=True)
    token = uuid.uuid4().hex
    payload = {"pid": os.getpid(), "token": token,
               "started_at": dt.datetime.now(dt.timezone.utc).isoformat()}
    for attempt in range(2):
        try:
            fd = os.open(claim, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
        except FileExistsError:
            try:
                owner = json.loads(claim.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _blocked("trial claim exists with unknown owner")
            pid = owner.get("pid") if isinstance(owner, dict) else None
            if not isinstance(pid, int) or _pid_alive(pid):
                _blocked("trial is already claimed")
            stale = claim.with_name(f"{claim.name}.{token}.stale")
            try:
                os.replace(claim, stale)
            except FileNotFoundError:
                continue
            try:
                moved = json.loads(stale.read_text(encoding="utf-8"))
            except (OSError, ValueError):
                _blocked("stale trial claim is unreadable")
            if moved != owner or (isinstance(moved, dict) and _pid_alive(moved.get("pid", 0))):
                _blocked("trial claim changed while recovering stale owner")
            try:
                stale.unlink()
            except FileNotFoundError:
                pass
            if attempt == 0:
                continue
            _blocked("trial claim changed while recovering stale owner")
        else:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as fh:
                json.dump(payload, fh, sort_keys=True)
                fh.write("\n")
            return claim, token
    _blocked("could not acquire trial claim")


def _release_claim(claim: Path, token: str) -> None:
    try:
        owner = json.loads(claim.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return
    if isinstance(owner, dict) and owner.get("token") == token:
        try:
            claim.unlink()
        except FileNotFoundError:
            pass


def _scored(gold: list[dict], predictions: list[dict], selection: list[dict], cluster_of: dict) -> dict:
    scored = score_relations(gold, predictions, approved_only=True, selection=selection)
    positives = [g for g in gold if g.get("approved") is True and g.get("gold_label") in SCORED]
    predicted = {p["pair_id"]: p["label"] for p in predictions}
    scored["recall_any"] = rate(sum(predicted.get(g["pair_id"]) == g["gold_label"] for g in positives), len(positives))
    by_cluster = {}
    for cluster in sorted(set(cluster_of.values())):
        ids = {d for d, c in cluster_of.items() if c == cluster}
        by_cluster[cluster] = score_relations([g for g in gold if g.get("doc_id") in ids],
                                              [p for p in predictions if p.get("doc_id") in ids],
                                              approved_only=True, selection=selection)["by_label"]
    return {**scored, "by_cluster": by_cluster, "cluster_intervals": predictor.cluster_intervals(by_cluster)}


def _validate_doc_trace_provenance(doc_stats: dict, traces: list[dict], predictions: list[dict]) -> None:
    actual: dict[str, list[dict]] = {}
    for trace in traces:
        actual.setdefault(trace["doc_id"], []).append(trace)
    expected_docs = set(doc_stats)
    covered_docs = {doc_id for doc_id, stats in doc_stats.items() if stats["llm_calls"] > 0}
    if set(actual) != covered_docs:
        raise ValueError("document trace coverage differs from expected calls")
    predicted_counts = Counter(p.get("doc_id") for p in predictions)
    for doc_id, stats in doc_stats.items():
        rows = actual.get(doc_id, [])
        if sum(row["llm_calls"] for row in rows) != stats["llm_calls"]:
            raise ValueError("document trace call totals differ from classifier stats")
        for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
            if sum(row[key] for row in rows) != stats[key]:
                raise ValueError("document trace token totals differ from classifier stats")
        if predicted_counts.get(doc_id, 0) != stats["n_predictions"]:
            raise ValueError("document prediction count differs from classifier result")
    if set(doc_stats) != expected_docs:
        raise ValueError("document provenance keys are inconsistent")


def run(
    variant: str, trial: int, *, out_dir: Path, model: str, data_dir: Path = manifest.DEFAULT_DATA_DIR,
    repo_manifest: Path = manifest.REPO_MANIFEST, llm: Any = None, allow_heldout: bool = False,
    dev_report: dict | None = None, budget_tokens: int = 500000, budget_seconds: float = 550,
) -> dict:
    if not allow_heldout:
        _blocked("heldout run requires --allow-heldout")
    if trial not in TRIALS:
        _blocked("only predeclared trials 1 and 2 are allowed")
    target = Path(out_dir) / f"t{trial}" / f"{variant}.json"
    if target.exists():
        _blocked("trial already exists; refusing overwrite")
    checked = preconditions(data_dir, repo_manifest=repo_manifest, dev_report=dev_report,
                            require_commit_lock=False)
    if variant not in checked["variants"]:
        _blocked("variant excluded by preflight")
    if not 0 < budget_tokens <= 2000000 or not math.isfinite(budget_seconds) or not 0 < budget_seconds <= 600:
        _blocked("invalid budget or budget above preflight limits")
    sequence = [(v, n) for n in TRIALS for v in checked["variants"]]
    preceding = sequence[:sequence.index((variant, trial))]
    if any(not (Path(out_dir) / f"t{n}" / f"{v}.json").is_file() for v, n in preceding):
        _blocked("trials must run in predeclared C1 B1 [E1] C2 B2 [E2] order")
    frozen = manifest.read_json(repo_manifest)
    labeler_model = frozen.get("labeler", {}).get("served_model")
    if not classifier_family_ok(model) or not classifier_model_differs_from_labeler(model, labeler_model):
        _blocked("requested classifier model must be recognised and differ from labeler")
    claim, claim_token = _acquire_claim(target)
    try:
        if llm is None:
            from app.llm.client import NineRouterClient
            llm = NineRouterClient()
        lock = _review_lock(repo_manifest, frozen)
        gold = predictor._read_reviewed_gold(data_dir, frozen)
        selected = _selection(Path(data_dir), frozen)
        cluster_of = _clusters(frozen)
        results, traces = [], []
        started_at = dt.datetime.now(dt.timezone.utc).isoformat()
        started = time.perf_counter()
        for item in _heldout(Path(data_dir), frozen, repo_manifest):
            doc_id = item["doc"]["doc_id"]
            buffer = _trace_buffer(llm)
            trace_start = len(buffer)
            result = predictor.predict_doc(item["doc"], llm=llm, model=model, variant=variant, pool=item["pool"],
                                           labeler_served_model=frozen["labeler"]["served_model"], cluster_id=cluster_of.get(doc_id))
            if result["prompt_version"] != PROMPT_VERSION:
                _blocked("trial prompt changed")
            fresh = buffer[trace_start:]
            for trace in fresh:
                error_type = trace.get("error_type")
                if error_type and error_type != "ResponseParseError":
                    _blocked("classifier trace contains provider error")
                served = trace.get("served_model")
                if (not isinstance(served, str) or not classifier_family_ok(served)
                        or not classifier_model_differs_from_labeler(served, labeler_model)):
                    _blocked("classifier actual served_model is not recognised or equals labeler")
                fallback = trace.get("fallback_without_json_format", False)
                if not isinstance(fallback, bool):
                    _blocked("classifier trace fallback marker invalid")
                usage = {}
                for key in ("prompt_tokens", "completion_tokens", "total_tokens"):
                    value = trace.get(key)
                    if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                        _blocked(f"classifier trace {key} missing or invalid")
                    usage[key] = value
                if usage["total_tokens"] != usage["prompt_tokens"] + usage["completion_tokens"]:
                    _blocked("classifier trace total tokens differ from components")
                traces.append({"doc_id": doc_id, **usage, "latency_ms": trace.get("latency_ms", 0),
                    **{k: trace[k] for k in ("served_model", "model", "request_digest", "fallback_without_json_format")
                       if k in trace},
                    "llm_calls": 2 if fallback else 1,
                    "error_type": error_type,
                    "classification_failed": error_type == "ResponseParseError"})
            if result["stats"].get("llm_calls", 0) and not fresh:
                _blocked("classifier calls have no trace provenance")
            results.append(result)
        doc_provenance = {}
        predictions = [p for r in results for p in r["predictions"]]
        for result in results:
            doc_id = result["doc_id"]
            if doc_id in doc_provenance:
                _blocked("duplicate classifier result document")
            stats = result["stats"]
            doc_provenance[doc_id] = {
                "llm_calls": stats.get("llm_calls", 0),
                "prompt_tokens": stats.get("prompt_tokens", 0),
                "completion_tokens": stats.get("completion_tokens", 0),
                "total_tokens": stats.get("prompt_tokens", 0) + stats.get("completion_tokens", 0),
                "n_predictions": len(result["predictions"]),
            }
        try:
            _validate_doc_trace_provenance(doc_provenance, traces, predictions)
        except ValueError as exc:
            _blocked(str(exc))
        report = predictor.build_report(results, gold, split="heldout", variant=variant, prompt_rounds=0)
        report.update(_scored(gold, predictions, selected, cluster_of))
        elapsed = time.perf_counter() - started
        prompt_tokens = sum(r["stats"].get("prompt_tokens", 0) for r in results)
        completion_tokens = sum(r["stats"].get("completion_tokens", 0) for r in results)
        report.update({"trial": trial, "requested_model": model, "predictions": predictions, "traces": traces,
                       "started_at": started_at, "finished_at": dt.datetime.now(dt.timezone.utc).isoformat(),
                       "elapsed_s": round(elapsed, 6), "n_docs": len(results),
                       "llm_calls": sum(r["stats"].get("llm_calls", 0) for r in results),
                       "prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                       "decisions_sha256": checked["decisions_sha256"], "feasibility": checked["feasibility"],
                       "doc_provenance": doc_provenance,
                       "review_lock_commit": lock["commit"],
                       "code_sha256": checked["code_sha256"],
                       "latency_ms_per_doc": {r["doc_id"]: r["latency_ms"] for r in results},
                       "budget": {"tokens": budget_tokens, "seconds": budget_seconds},
                       "over_budget": elapsed > budget_seconds or prompt_tokens + completion_tokens > budget_tokens})
        if not report["served_model"]:
            _blocked("no classifier served model observed")
        report["served_model"] = sorted({t["served_model"] for t in traces if t.get("served_model")})
        if len(report["served_model"]) != 1:
            _blocked("actual model changed between calls")
        target.parent.mkdir(parents=True, exist_ok=True)
        with target.open("x", encoding="utf-8", newline="\n") as fh:
            json.dump(report, fh, ensure_ascii=False, sort_keys=True, indent=1)
            fh.write("\n")
        return report
    finally:
        _release_claim(claim, claim_token)


def metric(variant: str, out_dir: Path, field: str = "recall_any", *, dry_run: bool = False) -> float:
    if dry_run:
        return 0.0  # Explicit CLI-contract probe; no measured trial or classifier call.
    files = sorted(Path(out_dir).glob(f"t*/{variant}.json"), key=lambda p: int(p.parent.name[1:]))
    if not files:
        raise ValueError("no trial available for metric")
    value = manifest.read_json(files[-1])[field]
    if isinstance(value, dict):
        value = value["rate"]
    if isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value):
        raise ValueError("metric must be a finite number with a positive denominator")
    return float(value)


@lru_cache(maxsize=1)
def _statistics():
    root = Path(os.getenv("HARNESS_BIN_ROOT") or manifest.REPO_ROOT)
    path = root / "harness/scripts/wilson.py"
    spec = importlib.util.spec_from_file_location("_pairs_bakeoff_wilson", path)
    if spec is None or spec.loader is None:
        raise RuntimeError("shared statistical engine unavailable")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def compare_items(gold: list[dict], a: list[dict], b: list[dict]) -> dict:
    positives = {g["pair_id"]: g["gold_label"] for g in gold
                 if g.get("approved") is True and g.get("gold_label") in SCORED}
    left = {p["pair_id"]: p["label"] for p in a}
    right = {p["pair_id"]: p["label"] for p in b}
    wins_a = sum(left.get(pid) == label and right.get(pid) != label for pid, label in positives.items())
    wins_b = sum(right.get(pid) == label and left.get(pid) != label for pid, label in positives.items())
    return {"b": wins_a, "c": wins_b, "n_items": len(positives), "method": "mcnemar-wilson",
            **_statistics().mcnemar_wilson(wins_a, wins_b)}


def minimum_sample(observed_rate: float | None) -> int | None:
    """Smallest conservative size at the measured rate; increasing n cannot fix a low rate."""
    if observed_rate is None or observed_rate <= MIN_WILSON_LOWER:
        return None
    # floor(p*n) has finite local sawteeth: search, do not binary-search a nonmonotone predicate.
    for n in range(MIN_N, 1000001):
        if wilson_lower(math.floor(observed_rate * n), n) >= MIN_WILSON_LOWER:
            return n
    return None


def _checked_trials(report: dict) -> list[dict]:
    expected = report["manifest"].get("decisions_sha256")
    if expected is None:
        # Backward-compatible path for pre-HG-2 unit fixtures. Real P5 reports
        # carry the combined reviewed-gold digest above.
        expected = report["manifest"]["heldout_review"]["decisions_sha256"]
    if not isinstance(expected, str) or len(expected) != 64 or report.get("decisions_sha256") != expected:
        raise ValueError("report decisions SHA differs from manifest lock")
    canonical = [{k: g[k] for k in ("pair_id", "gold_label", "gold_direction", "approved", "source", "decision") if k in g}
                 for g in sorted(report["gold"], key=lambda g: g["pair_id"])]
    actual = hashlib.sha256("".join(_json_line(d) for d in canonical).encode("utf-8")).hexdigest()
    if actual != expected:
        raise ValueError("report gold SHA differs from manifest review lock")
    selected = report["selection"]
    selection_lock = report["manifest"]["review_selection"]
    expected_selection_sha = report["manifest"].get("selection_sha256", selection_lock.get("sha256"))
    expected_selection_n = report["manifest"].get("selection_n_rows", selection_lock.get("n_rows"))
    selection_digest = hashlib.sha256("".join(_json_line(s) for s in selected).encode("utf-8")).hexdigest()
    selected_by = {s["pair_id"]: s for s in selected}
    if (selection_digest != expected_selection_sha or len(selected) != expected_selection_n
            or len(selected_by) != len(selected) or len(canonical) != len(selected)
            or {g["pair_id"] for g in canonical} != set(selected_by)):
        raise ValueError("selection SHA/IDs/count differ from manifest lock")
    docs = {d["doc_id"]: d for d in report["manifest"]["docs"] if d["split"] == "heldout"}
    clusters = {doc_id: doc["cluster_id"] for doc_id, doc in docs.items()}
    if report["cluster_of_doc"] != clusters:
        raise ValueError("cluster metadata differs from frozen manifest")
    candidate_rows = report.get("candidate_universe")
    if not isinstance(candidate_rows, list) or not candidate_rows:
        raise ValueError("candidate universe is required")
    candidate_by = {}
    for candidate in candidate_rows:
        if not isinstance(candidate, dict):
            raise ValueError("candidate universe row is invalid")
        pair_id = candidate.get("pair_id")
        if (not isinstance(pair_id, str) or not pair_id or pair_id in candidate_by
                or candidate.get("doc_id") not in docs or not isinstance(candidate.get("stratum"), str)):
            raise ValueError("candidate universe metadata is invalid")
        candidate_by[pair_id] = candidate
    for gold in report["gold"]:
        sel = selected_by[gold["pair_id"]]
        if (sel["doc_id"] not in docs or gold.get("doc_id") != sel["doc_id"] or gold.get("stratum") != sel["stratum"]
                or isinstance(sel.get("pi"), bool) or not isinstance(sel.get("pi"), (int, float)) or not 0 < sel["pi"] <= 1):
            raise ValueError("gold metadata/inclusion probability differs from locked selection")
        if gold["pair_id"] not in candidate_by:
            raise ValueError("gold pair outside frozen candidate universe")
    fingerprints_expected = report.get("code_sha256")
    if (not isinstance(fingerprints_expected, dict) or set(fingerprints_expected) != set(FINGERPRINT_FILES)
            or any(not isinstance(s, str) or not re.fullmatch(r"[0-9a-f]{64}", s) for s in fingerprints_expected.values())):
        raise ValueError("complete frozen code SHA map required")
    lock = report["review_lock"]
    if not isinstance(lock.get("commit"), str) or not re.fullmatch(r"[0-9a-f]{40}", lock["commit"]):
        raise ValueError("review commit SHA invalid")
    committed_at = _timestamp(lock["committed_at"])
    if (report.get("review_lock_commit") != lock["commit"]
            or report.get("review_lock_committed_at") != lock["committed_at"]):
        raise ValueError("review lock summary differs from recorded lock")
    variants = report["variants_run"]
    trials = report["trials"]
    if (len(variants) != len(set(variants)) or set(variants) not in ({"C", "B"}, {"C", "B", "E"})
            or Counter((t["variant"], t["trial"]) for t in trials) != Counter((v, n) for v in variants for n in TRIALS)):
        raise ValueError("exactly two trials required per selected variant")
    models = set()
    fingerprints = []
    for trial in trials:
        if trial.get("decisions_sha256") != expected:
            raise ValueError("trial decisions SHA differs from manifest lock")
        trial_requested_model = trial.get("requested_model")
        labeler_model = report.get("manifest", {}).get("labeler", {}).get("served_model")
        if (not isinstance(trial_requested_model, str) or not classifier_family_ok(trial_requested_model)
                or not classifier_model_differs_from_labeler(trial_requested_model, labeler_model)):
            raise ValueError("trial requested model must be recognised and differ from labeler")
        served = trial.get("served_model")
        if (not isinstance(served, list) or len(served) != 1 or not classifier_family_ok(served[0])
                or not classifier_model_differs_from_labeler(served[0], labeler_model)):
            raise ValueError("every trial must observe one recognised served model different from labeler")
        models.add(served[0])
        fingerprints.append(trial.get("code_sha256"))
        if trial.get("code_sha256") != fingerprints_expected:
            raise ValueError("trial code SHA differs from frozen code snapshot")
        if trial.get("review_lock_commit") != lock["commit"]:
            raise ValueError("trial review commit differs from actual locked commit")
        start, finish = _timestamp(trial["started_at"]), _timestamp(trial["finished_at"])
        if start < committed_at or finish < start:
            raise ValueError("trial ran before review lock or has invalid timestamps")
        budget = trial.get("budget")
        if not isinstance(budget, dict):
            raise ValueError("trial budget is required")
        budget_tokens, budget_seconds = budget.get("tokens"), budget.get("seconds")
        if (isinstance(budget_tokens, bool) or not isinstance(budget_tokens, int)
                or not 0 < budget_tokens <= 2000000
                or isinstance(budget_seconds, bool) or not isinstance(budget_seconds, (int, float))
                or not math.isfinite(budget_seconds) or not 0 < budget_seconds <= 600):
            raise ValueError("trial budget is invalid")
        elapsed = trial.get("elapsed_s")
        if isinstance(elapsed, bool) or not isinstance(elapsed, (int, float)) or not math.isfinite(elapsed) or elapsed < 0:
            raise ValueError("trial elapsed time is invalid")
        if not isinstance(trial.get("over_budget"), bool):
            raise ValueError("trial over_budget marker is invalid")
        doc_provenance = trial.get("doc_provenance")
        if not isinstance(doc_provenance, dict) or set(doc_provenance) != set(docs):
            raise ValueError("document provenance keys differ from frozen heldout")
        for doc_id, stats in doc_provenance.items():
            if not isinstance(stats, dict):
                raise ValueError("document provenance record is invalid")
            for key in ("llm_calls", "prompt_tokens", "completion_tokens", "total_tokens", "n_predictions"):
                value = stats.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError("document provenance count is invalid")
            if stats["total_tokens"] != stats["prompt_tokens"] + stats["completion_tokens"]:
                raise ValueError("document provenance token total differs from components")
        traces = trial.get("traces")
        if not isinstance(traces, list) or not traces:
            raise ValueError("actual call traces required")
        served_traces = set()
        trace_calls = 0
        for trace in traces:
            if not isinstance(trace, dict):
                raise ValueError("trace record is invalid")
            if trace.get("doc_id") not in docs:
                raise ValueError("trace document outside frozen heldout")
            error_type = trace.get("error_type")
            if error_type not in (None, "ResponseParseError"):
                raise ValueError("trace contains provider error")
            actual_model = trace.get("served_model")
            if (not isinstance(actual_model, str) or not classifier_family_ok(actual_model)
                    or not classifier_model_differs_from_labeler(actual_model, labeler_model)):
                raise ValueError("actual trace served model is not recognised or equals labeler")
            requested_model = trace.get("model")
            if (not isinstance(requested_model, str) or not classifier_family_ok(requested_model)
                    or not classifier_model_differs_from_labeler(requested_model, labeler_model)):
                raise ValueError("actual trace requested model is not recognised or equals labeler")
            if requested_model != trial_requested_model:
                raise ValueError("trace requested model differs from trial")
            served_traces.add(actual_model)
            fallback = trace.get("fallback_without_json_format")
            if not isinstance(fallback, bool):
                raise ValueError("trace fallback marker invalid")
            expected_calls = 2 if fallback else 1
            if trace.get("llm_calls") != expected_calls:
                raise ValueError("trace call count invalid")
            if trace.get("classification_failed") is not (error_type == "ResponseParseError"):
                raise ValueError("trace classification status invalid")
            trace_calls += expected_calls
            for key in ("prompt_tokens", "completion_tokens"):
                value = trace.get(key)
                if isinstance(value, bool) or not isinstance(value, int) or value < 0:
                    raise ValueError("trace token count invalid")
            total = trace.get("total_tokens")
            if isinstance(total, bool) or not isinstance(total, int) or total < 0:
                raise ValueError("trace total token count invalid")
            if total != trace["prompt_tokens"] + trace["completion_tokens"]:
                raise ValueError("trace total token count differs from components")
        if served_traces != set(served) or trial.get("llm_calls") != trace_calls:
            raise ValueError("trial model/call count differs from actual traces")
        if any(trial.get(key) != sum(t.get(key, 0) for t in traces) for key in ("prompt_tokens", "completion_tokens")):
            raise ValueError("trial token count differs from actual traces")
        try:
            _validate_doc_trace_provenance(doc_provenance, traces, trial["predictions"])
        except ValueError as exc:
            raise ValueError(f"document trace coverage: {exc}") from exc
        measured_over_budget = (elapsed > budget_seconds
                                or trial["prompt_tokens"] + trial["completion_tokens"] > budget_tokens)
        if trial["over_budget"] != measured_over_budget:
            raise ValueError("trial over_budget differs from measured values")
        if trial.get("n_docs") != len(docs):
            raise ValueError("trial document count differs from frozen split")
        for pred in trial["predictions"]:
            if pred.get("doc_id") not in docs or pred.get("label") not in SCORED:
                raise ValueError("prediction document/label outside frozen evaluation")
            direction = pred.get("direction")
            if pred["label"] in review.DIRECTED:
                if direction not in {"A", "B"}:
                    raise ValueError("directed prediction direction invalid")
            elif direction is not None:
                raise ValueError("undirected prediction direction invalid")
            candidate = candidate_by.get(pred.get("pair_id"))
            if candidate is None or any(pred.get(k) != candidate[k] for k in ("doc_id", "stratum")):
                raise ValueError("prediction outside frozen candidate universe")
            selected_meta = selected_by.get(pred["pair_id"])
            if selected_meta and any(pred.get(k) != selected_meta[k] for k in ("doc_id", "stratum")):
                raise ValueError("prediction metadata differs from locked selection")
        if trial.get("prompt_version") != report.get("prompt_version") or trial["prompt_version"] != PROMPT_VERSION:
            raise ValueError("prompt version mismatch")
    if len(models) != 1:
        raise ValueError("served model changed between trials")
    if any(f != fingerprints[0] for f in fingerprints):
        raise ValueError("classifier/candidate/scorer code changed between trials")
    return [{**t, **_scored(report["gold"], t["predictions"], report["selection"], report["cluster_of_doc"])} for t in trials]


def _timestamp(value: str) -> dt.datetime:
    timestamp = dt.datetime.fromisoformat(value)
    if timestamp.tzinfo is None:
        raise ValueError("timezone-aware timestamp required")
    return timestamp


def decide(report: dict) -> dict:
    """Pure recommendation: counts are rederived from every trial, never copied from metrics."""
    trials = _checked_trials(report)
    c_trials = [t for t in trials if t["variant"] == "C"]
    per_label = {}
    for label in SCORED:
        worst = min(c_trials, key=lambda t: (wilson_lower(t["by_label"][label]["passed"],
                                                        t["by_label"][label]["denominator"]), t["trial"]))
        block = worst["by_label"][label]
        k, n = block["passed"], block["denominator"]
        lo, hi = wilson(k, n)
        needed = minimum_sample(k / n if n else None)
        docs = worst["n_docs"]
        per_label[label] = {"trial": worst["trial"], "k": k, "n": n, "rate": k / n if n else None,
                            "wilson_lower": lo, "wilson_upper": hi, "method": "wilson", "conf": .95,
                            "cluster_lower": min((t["cluster_intervals"].get(label, {}).get("precision_conservative") or {}).get("lower", 0)
                                                 for t in c_trials),
                            "precision_observed": block["precision_observed"], "precision_weighted": block["precision_weighted"],
                            "recall_observed": block["recall_observed"], "recall_weighted": block["recall_weighted"],
                            "passed": all(t["by_label"][label]["denominator"] >= MIN_N and
                                          wilson_lower(t["by_label"][label]["passed"], t["by_label"][label]["denominator"]) >= MIN_WILSON_LOWER
                                          for t in c_trials),
                            "min_n_needed": needed, "min_n_all_pass": _statistics().min_n_all_pass(MIN_WILSON_LOWER),
                            "additional_docs_estimate": math.ceil(max(0, needed - n) / (n / docs)) if needed and n and docs else None,
                            "sizing_note": "Ước tính giữ tỷ lệ đo, dùng floor(p*n); null: chưa có cỡ hữu hạn được chứng minh. all-pass là trường hợp tốt nhất."}
    worst_by_variant = {v: min((t for t in trials if t["variant"] == v),
                               key=lambda t: (t["recall_any"]["rate"] or 0, t["trial"])) for v in report["variants_run"]}
    comparisons = {f"C_vs_{v}": compare_items(report["gold"], worst_by_variant["C"]["predictions"], worst_by_variant[v]["predictions"])
                   for v in report["variants_run"] if v != "C"}
    discrepancies = [label for label in SCORED if not per_label[label]["passed"] and any(
        t["by_label"][label]["precision_weighted"] is not None and
        t["by_label"][label]["precision_weighted"] >= MIN_WILSON_LOWER and
        t["by_label"][label]["precision_weighted"] > (t["by_label"][label]["precision_conservative"]["rate"] or 0)
        for t in c_trials)]
    budget_blocked_variants = sorted({t["variant"] for t in trials if t["over_budget"]})
    if any(sum(t["false_duplicate"].values()) > 0 for t in c_trials):
        verdict = "KEEP_OFF_FALSE_DUPLICATE"
    elif any(t["by_label"][label]["denominator"] < MIN_N for t in c_trials for label in SCORED):
        # A hard sample-size failure is deterministic and takes precedence over a
        # budget advisory on a non-gating variant.  HUMAN_DECISION is reserved for
        # a fully sampled run whose other evidence still needs a human ruling.
        verdict = "KEEP_OFF_INSUFFICIENT_N"
    elif budget_blocked_variants:
        verdict = "HUMAN_DECISION"
    elif discrepancies:
        verdict = "HUMAN_DECISION"
    elif any(not b["passed"] for b in per_label.values()):
        verdict = "KEEP_OFF_BELOW_THRESHOLD"
    elif any(b["cluster_lower"] < MIN_WILSON_LOWER for b in per_label.values()) or comparisons["C_vs_B"]["upper"] < .5:
        verdict = "HUMAN_DECISION"
    else:
        verdict = "ENABLE_CANDIDATE"
    return {"verdict": verdict, "recommendation_only": True, "thresholds_source": "review_policy.py",
            "thresholds": {"min_n": MIN_N, "min_wilson_lower": MIN_WILSON_LOWER},
            "decisions_sha256": report["decisions_sha256"], "per_label": per_label,
            "weighted_discrepancies": discrepancies, "mcnemar": comparisons,
            "feasibility": report["feasibility"], "variants_run": report["variants_run"],
            "budget_blocked_variants": budget_blocked_variants}


def assemble_report(out_dir: Path, data_dir: Path, *, repo_manifest: Path = manifest.REPO_MANIFEST) -> dict:
    checked = preconditions(data_dir, repo_manifest=repo_manifest)
    frozen = manifest.read_json(repo_manifest)
    gold = predictor._read_reviewed_gold(data_dir, frozen)
    selected = _selection(Path(data_dir), frozen)
    trials = [manifest.read_json(Path(out_dir) / f"t{n}" / f"{v}.json") for v in checked["variants"] for n in TRIALS]
    universe = {p["pair_id"]: p for item in _heldout(Path(data_dir), frozen, repo_manifest) for p in item["pool"]}
    for trial in trials:
        for pred in trial["predictions"]:
            pair = universe.get(pred["pair_id"])
            if pair is None or any(pred.get(k) != pair[k] for k in ("doc_id", "stratum")):
                raise ValueError("trial predictions differ from verified pool + S4 universe")
    lock = _review_lock(repo_manifest, frozen)
    report = {"schema": "contract-graph-pairs-bakeoff/1", "status": "OBSERVED",
              "manifest": {"heldout_review": frozen["heldout_review"], "review_selection": frozen["review_selection"],
                           "hg2": frozen.get("hg2"), "docs": frozen["docs"],
                           "decisions_sha256": checked["decisions_sha256"],
                           "selection_sha256": checked["selection_sha256"],
                           "selection_n_rows": checked["selection_n_rows"]},
              "decisions_sha256": checked["decisions_sha256"],
              "review_lock": lock, "review_lock_commit": lock["commit"],
              "review_lock_committed_at": lock["committed_at"],
              "code_sha256": checked["code_sha256"],
              "prompt_version": PROMPT_VERSION, "variants_run": checked["variants"], "feasibility": checked["feasibility"],
              "gold": gold, "selection": selected,
              "candidate_universe": sorted(universe.values(), key=lambda p: p["pair_id"]),
              "cluster_of_doc": _clusters(frozen), "trials": trials,
              "method": "wilson 95%; cluster-adjusted; mcnemar-wilson; newcombe difference",
              "heldout_trial_count": len(trials), "dev_tuning_rounds": {"prompt": manifest.read_json(DEV_REPORT)["prompt_rounds"],
                  "lexicon": manifest.read_json(DEV_REPORT.with_name("l2-p2-candidates.json"))["tuning_rounds"]},
              "run1_note": "Run1 C 10/11, B 8/11, E precision 11/32 chỉ định hướng; có thể dùng GPT và khác dữ liệu."}
    report["trials"] = _checked_trials(report)
    trials = report["trials"]
    report["decision"] = decide(report)
    report["scoreboard"] = {v: {"recall_any_trials": [t["recall_any"] for t in trials if t["variant"] == v],
                               "spread": max(t["recall_any"]["rate"] for t in trials if t["variant"] == v) - min(t["recall_any"]["rate"] for t in trials if t["variant"] == v),
                               "over_budget": any(t.get("over_budget") for t in trials if t["variant"] == v)} for v in checked["variants"]}
    confusion = review.labeler_confusion(selected, gold)
    screens = {}
    for label in SCORED:
        cells = confusion["overall"]
        tp = cells.get(label, {}).get(label, 0)
        fp = sum(count for human, count in cells.get(label, {}).items() if human != label)
        fn = sum(row.get(label, 0) for gpt, row in cells.items() if gpt != label)
        tn = sum(count for gpt, row in cells.items() for human, count in row.items() if gpt != label and human != label)
        screens[label] = {"TP": tp, "FN": fn, "TN": tn, "FP": fp, **_statistics().judge_screen(tp, fn, tn, fp)}
    report["labeler_calibration"] = {**confusion, "agreement": rate(confusion["agreement"]["passed"], confusion["agreement"]["denominator"]),
                                      "judge_screen": screens, "upper_bound_only": True}
    report["precision_difference"] = {f"C_vs_{v}": {label: _statistics().diff_newcombe(
        report["decision"]["per_label"][label]["k"], report["decision"]["per_label"][label]["n"],
        min((t for t in report["trials"] if t["variant"] == v), key=lambda t: t["by_label"][label]["precision_conservative"]["wilson95"][0])["by_label"][label]["passed"],
        min((t for t in report["trials"] if t["variant"] == v), key=lambda t: t["by_label"][label]["precision_conservative"]["wilson95"][0])["by_label"][label]["denominator"])
        for label in SCORED} for v in checked["variants"] if v != "C"}
    return report


def render_report(report: dict) -> str:
    decision = decide(report)
    trials = _checked_trials(report)
    # Allowlist the rendered fields; arbitrary input keys are never copied into Markdown.
    summary = {"decision": decision, "scoreboard": report.get("scoreboard"), "method": "wilson 95%",
               "labeler_calibration": report.get("labeler_calibration"), "precision_difference": report.get("precision_difference"),
               "dev_tuning_rounds": report.get("dev_tuning_rounds"), "heldout_trial_count": len(report["trials"]),
               "trials": [{k: t.get(k) for k in ("variant", "trial", "by_label", "by_stratum", "by_doc", "cluster_intervals", "recall_any",
                                               "llm_calls", "prompt_tokens", "completion_tokens", "elapsed_s", "latency_ms", "false_duplicate", "rejected", "injection_signals", "over_budget")}
                          for t in trials]}
    return ("# P5 — bake-off cặp hợp đồng\n\n"
            f"Khuyến nghị: `{decision['verdict']}`. Đo trên mẫu HĐ công khai.\n\n"
            "Precision bảo thủ dùng cho cổng; 1/π chỉ báo và không có khoảng tin cậy. "
            "Đồng thuận GPT↔người là cận trên vì người duyệt thấy nhãn GPT. "
            "Không có người gán mù thứ hai.\n\n"
            "Run1 C 10/11, B 8/11, E precision 11/32 chỉ định hướng; có thể dùng GPT và khác dữ liệu.\n\n"
            "```json\n" + json.dumps(summary, ensure_ascii=False, indent=2) + "\n```\n")
