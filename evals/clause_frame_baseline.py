"""CLI dev-only cho readiness và calibration qua production run_idp.

Không cung cấp quality PASS khi chưa có strategy card và reviewer độc lập.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import subprocess
from collections.abc import Callable
from dataclasses import asdict
from pathlib import Path
from typing import Any

from evals.clause_frame_scoring import (
    compare_units,
    is_supported_metric,
    score_units,
    validate_policy,
)
from evals.real_pipeline import REPOSITORY_ROOT, run_processing
from evals.unit_metrics import MetricSpec, UnitRecord


def _digest(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def _head() -> str | None:
    try:
        result = subprocess.run(["git", "-C", str(REPOSITORY_ROOT), "rev-parse", "HEAD"],
                                capture_output=True, text=True, check=False)
    except OSError:
        return None
    return result.stdout.strip() if result.returncode == 0 else None


def _valid_path(path: Any) -> bool:
    return (isinstance(path, list) and bool(path)
            and all((isinstance(x, str) and bool(x))
                    or (type(x) is int and x >= 0) for x in path))


def _valid_sha256(value: Any) -> bool:
    return isinstance(value, str) and re.fullmatch(r"[0-9a-f]{64}", value) is not None


def _split_hash(gold: dict) -> str:
    entries = sorted(
        ({"id": dossier.get("id"), "split": dossier.get("split")}
         for dossier in gold.get("dossiers", [])
         if isinstance(dossier, dict)),
        key=lambda item: (str(item["id"]), str(item["split"])),
    )
    payload = {"split": gold.get("split"), "dossiers": entries}
    return hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def _historical_plan_a_hash() -> str | None:
    path = (REPOSITORY_ROOT.parents[1] / "plans" / "260929-2323-ai2-a-measure-baseline"
            / "plan.md")
    try:
        return _digest(path)
    except OSError:
        return None


def _json_equal(left: Any, right: Any) -> bool:
    if type(left) is not type(right):
        return False
    if isinstance(left, dict):
        return (left.keys() == right.keys()
                and all(_json_equal(left[key], right[key]) for key in left))
    if isinstance(left, list):
        return len(left) == len(right) and all(_json_equal(x, y) for x, y in zip(left, right))
    return left == right


def _identities(gold: dict) -> bool:
    if not isinstance(gold, dict):
        return False
    dossiers = gold.get("dossiers")
    return (gold.get("split") == "dev" and isinstance(dossiers, list) and bool(dossiers)
            and all(isinstance(d, dict) and d.get("split") == "dev" for d in dossiers))


def readiness(gold: dict) -> dict:
    # Không trả lại ID/path/nhãn từ mixed manifest cho người tune.
    if not _identities(gold):
        return {"status": "BLOCKED", "reasons": ["DEV_ONLY_MANIFEST_REQUIRED"]}
    reasons = []
    if gold.get("schema") != "ai2.clause-frame.gold.v1":
        reasons.append("GOLD_SCHEMA_REQUIRED")
    people = [gold.get(x) for x in ("producer", "reviewer", "adjudicator")]
    if not all(isinstance(x, str) and x.strip() for x in people) or len(set(people)) != 3:
        reasons.append("INDEPENDENT_REVIEW_REQUIRED")
    if gold.get("approved") is not True or not gold.get("approval_ref"):
        reasons.append("APPROVED_LABELS_REQUIRED")
    if not gold.get("consent_ref"):
        reasons.append("CONSENT_REQUIRED")
    receipt = gold.get("holdout_receipt", {})
    if not isinstance(receipt, dict) or not (
        receipt.get("approved") is True and receipt.get("evaluator")
        and receipt.get("isolation_ref") and receipt.get("split_hash")
    ):
        reasons.append("EVALUATOR_ISOLATION_EVIDENCE_REQUIRED")
    ids = set()
    dossier_profiles = {}
    has_amendment = False
    for dossier in gold["dossiers"]:
        identifier = dossier.get("id")
        if (not isinstance(identifier, str) or not identifier
                or identifier in ids):
            reasons.append("DOSSIER_ID_INVALID")
        else:
            ids.add(identifier)
            dossier_profiles[identifier] = dossier.get("profile")
        if not isinstance(dossier.get("profile"), str) or not dossier["profile"].strip():
            reasons.append("DOSSIER_PROFILE_REQUIRED")
        if dossier.get("source_kind") != "real":
            reasons.append("REAL_SOURCE_REQUIRED")
        if not _valid_sha256(dossier.get("sha256")):
            reasons.append("SOURCE_HASH_INVALID")
        else:
            try:
                if _digest(Path(dossier["path"])) != dossier["sha256"]:
                    reasons.append("SOURCE_HASH_DRIFT")
            except (OSError, KeyError, TypeError):
                reasons.append("SOURCE_UNAVAILABLE")
        try:
            source_path = Path(dossier["path"])
            if source_path.is_symlink() or not source_path.is_file():
                reasons.append("SOURCE_UNAVAILABLE")
        except (OSError, KeyError, TypeError):
            reasons.append("SOURCE_UNAVAILABLE")
        has_amendment |= dossier.get("amendment_chain_verified") is True
    if not has_amendment:
        reasons.append("REAL_AMENDMENT_CHAIN_REQUIRED")
    units = gold.get("units")
    if not isinstance(units, list) or not units:
        reasons.append("ELIGIBLE_UNITS_REQUIRED")
    else:
        try:
            records = []
            for unit in units:
                if (unit.get("dossier_id") not in ids or unit.get("predicate") != "exact"
                        or not unit.get("evidence_ref") or not _valid_path(unit.get("path"))
                        or not _valid_path(unit.get("identity_path"))
                        or "identity_expected" not in unit or "expected" not in unit):
                    raise ValueError("invalid gold unit")
                metric = unit.get("metric")
                if not is_supported_metric(metric):
                    reasons.append("UNSUPPORTED_METRIC")
                if not isinstance(unit.get("profile"), str) or not unit["profile"].strip():
                    reasons.append("GOLD_UNIT_PROFILE_REQUIRED")
                elif unit["profile"] != dossier_profiles.get(unit["dossier_id"]):
                    reasons.append("GOLD_UNIT_PROFILE_MISMATCH")
                records.append(UnitRecord(unit["metric"], unit["item_id"], unit["unit_id"],
                                          True, unit["dossier_id"], split="dev"))
            compare_units(records, records, [])
        except (ValueError, KeyError, TypeError, AttributeError):
            reasons.append("GOLD_UNIT_INVALID_OR_DUPLICATED")
    return {"status": "BLOCKED" if reasons else "READY_FOR_CALIBRATION",
            "reasons": sorted(set(reasons)), "quality_ready": False}


def _get(output: Any, path: list) -> tuple[bool, Any]:
    value = output
    try:
        for segment in path:
            if isinstance(value, list) and type(segment) is int:
                if segment < 0:
                    return False, None
                value = value[segment]
            elif isinstance(value, dict) and isinstance(segment, str):
                value = value[segment]
            else:
                return False, None
        return True, value
    except (KeyError, IndexError, TypeError):
        return False, None


def baseline(gold: dict, *, replay: Callable = run_processing) -> dict:
    ready = readiness(gold)
    if ready["status"] == "BLOCKED":
        return ready
    outputs = {}
    for dossier in gold["dossiers"]:
        result = replay(dossier["path"])
        if not isinstance(result, dict) or result.get("status") != "PASS":
            return {"status": "BLOCKED", "reasons": ["PRODUCTION_REPLAY_FAILED"]}
        outputs[dossier["id"]] = result.get("output")
    # Dù chỉ calibration, receipt không được pin source đã bị đổi lúc replay.
    for dossier in gold["dossiers"]:
        try:
            if _digest(Path(dossier["path"])) != dossier["sha256"]:
                return {"status": "BLOCKED", "reasons": ["SOURCE_CHANGED_DURING_REPLAY"]}
        except OSError:
            return {"status": "BLOCKED", "reasons": ["SOURCE_CHANGED_DURING_REPLAY"]}
    records = []
    missing = 0
    for unit in gold["units"]:
        found, actual = _get(outputs[unit["dossier_id"]], unit["path"])
        bound, identity = _get(outputs[unit["dossier_id"]], unit["identity_path"])
        bound = bound and _json_equal(identity, unit["identity_expected"])
        covered = found and bound
        missing += not covered
        # JSON bool và number không được coi là tương đương.
        passed = covered and _json_equal(actual, unit["expected"])
        records.append(UnitRecord(unit["metric"], unit["item_id"], unit["unit_id"],
                                  passed, unit["dossier_id"],
                                  detail=None if covered else "MISSING_OR_UNBOUND", split="dev"))
    return {"status": "CALIBRATION_ONLY", "split": "dev", "quality_ready": False,
            "production_entry": "app.pipeline.idp.run_idp", "provider_policy": "local_no_egress",
            "units": [asdict(x) for x in records],
            "coverage": {"eligible": len(records), "missing": missing,
                         "covered": len(records) - missing},
            "reasons": ["FULL_METRIC_POLICY_AND_HUMAN_FREEZE_REQUIRED"]}


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("readiness", "baseline"))
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--split", choices=("dev",), required=True)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--policy", type=Path,
                        help="Strategy card đã user freeze; không tự phát hành quality PASS")
    args = parser.parse_args(argv)
    # Exclusive create bên dưới cũng bảo vệ gold/source/policy và symlink/hardlink.
    if args.out.exists():
        print(json.dumps({"status": "BLOCKED", "reasons": ["OUTPUT_ALREADY_EXISTS"]}))
        return 2
    gold = {}
    start_head = _head()
    manifest_hash = None
    runtime_paths = {"scorer_sha256": Path(__file__).with_name("clause_frame_scoring.py"),
                     "runner_sha256": Path(__file__)}
    runtime_hashes = {}
    try:
        runtime_hashes = {name: _digest(path) for name, path in runtime_paths.items()}
        # Đọc policy trước replay; không dùng phiên bản xuất hiện sau khi chạy.
        policy = None
        if args.policy is not None:
            policy_bytes = args.policy.read_bytes()
            runtime_paths["policy_sha256"] = args.policy
            runtime_hashes["policy_sha256"] = hashlib.sha256(policy_bytes).hexdigest()
            policy = json.loads(policy_bytes.decode("utf-8-sig"))
        manifest_bytes = args.manifest.read_bytes()
        manifest_hash = hashlib.sha256(manifest_bytes).hexdigest()
        gold = json.loads(manifest_bytes.decode("utf-8-sig"))
        policy_validation = None
        if args.policy is not None:
            expected_pins = {
                "dev_gold_hash": manifest_hash,
                "scorer_hash": runtime_hashes.get("scorer_sha256"),
                "split_hash": _split_hash(gold),
            }
            plan_a_hash = _historical_plan_a_hash()
            if plan_a_hash is not None:
                expected_pins["historical_plan_a_card_hash"] = plan_a_hash
            policy_validation = validate_policy(
                policy, expected_pins=expected_pins
            )
        if start_head is None:
            result = {"status": "BLOCKED", "reasons": ["SOURCE_HEAD_UNAVAILABLE"]}
        elif policy_validation is not None and policy_validation["status"] == "BLOCKED":
            result = readiness(gold)
        else:
            result = readiness(gold) if args.command == "readiness" else baseline(gold)
        if policy_validation is not None:
            result["policy_validation"] = policy_validation
            if policy_validation["status"] == "BLOCKED":
                result["status"] = "BLOCKED"
                result["reasons"] = sorted(set(result.get("reasons", [])
                                                + policy_validation["reasons"]))
            elif result.get("status") == "CALIBRATION_ONLY":
                specs = [MetricSpec(
                    spec["metric"], spec["threshold"] if spec["direction"] == "min"
                    else 1 - spec["threshold"], spec["minimum_units"])
                    for spec in policy["metrics"]]
                result["diagnostic_metrics"] = score_units(
                    [UnitRecord(**unit) for unit in result["units"]], specs)
    except (OSError, ValueError, TypeError):
        result = {"status": "BLOCKED", "reasons": ["MANIFEST_UNAVAILABLE_OR_INVALID"]}
    if manifest_hash is not None:
        try:
            if _digest(args.manifest) != manifest_hash or _head() != start_head:
                result = {"status": "BLOCKED", "reasons": ["INPUT_OR_SOURCE_HEAD_DRIFT"]}
        except OSError:
            result = {"status": "BLOCKED", "reasons": ["INPUT_OR_SOURCE_HEAD_DRIFT"]}
    if runtime_hashes:
        try:
            if any(_digest(runtime_paths[name]) != value
                   for name, value in runtime_hashes.items()):
                result = {"status": "BLOCKED", "reasons": ["RUNTIME_INPUT_DRIFT"]}
        except OSError:
            result = {"status": "BLOCKED", "reasons": ["RUNTIME_INPUT_DRIFT"]}
    result["pins"] = {"source_head": start_head, **runtime_hashes}
    if args.manifest.is_file() and _identities(gold):
        result["pins"]["dev_manifest_sha256"] = manifest_hash
    args.out.parent.mkdir(parents=True, exist_ok=True)
    try:
        with args.out.open("x", encoding="utf-8") as stream:
            stream.write(json.dumps(result, ensure_ascii=False, indent=2) + "\n")
    except OSError:
        print(json.dumps({"status": "BLOCKED", "reasons": ["OUTPUT_WRITE_REFUSED"]}))
        return 2
    print(json.dumps({"status": result["status"], "reasons": result.get("reasons", [])}))
    return 2 if result["status"] == "BLOCKED" else 0


if __name__ == "__main__":
    raise SystemExit(main())
