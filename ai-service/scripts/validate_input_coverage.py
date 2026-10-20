"""Validate the versioned AI2 input coverage manifest without network calls."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.pipeline.ai1_snapshot_adapter import SnapshotContractError, adapt_ai1_input  # noqa: E402
from fixtures.eval_suite import all_eval_cases  # noqa: E402


MANIFEST = ROOT / "fixtures" / "eval_inputs" / "manifest.json"
VALID_MODES = {"deterministic", "live_llm", "hybrid_vector_recall"}


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _validate_input_file(item: dict[str, Any]) -> dict[str, Any]:
    path = ROOT / str(item["path"])
    if not path.is_file():
        raise AssertionError(f"missing input file: {item['id']} -> {path}")
    if item.get("valid"):
        payload = _load_json(path)
        result = adapt_ai1_input(payload)
        return {
            "id": item["id"],
            "status": "VALID",
            "source": result.meta.get("source"),
            "n_pages": result.meta.get("n_pages"),
            "n_handoff_issues": result.meta.get("n_handoff_issues"),
        }

    expected = str(item.get("expected_error") or "")
    try:
        payload = _load_json(path)
        adapt_ai1_input(payload)
    except json.JSONDecodeError as exc:
        actual = type(exc).__name__
    except SnapshotContractError as exc:
        actual = exc.code
    else:
        raise AssertionError(f"invalid input unexpectedly accepted: {item['id']}")
    if actual != expected:
        raise AssertionError(f"{item['id']}: expected {expected}, got {actual}")
    return {"id": item["id"], "status": "REJECTED", "error": actual}


def validate_manifest(path: Path = MANIFEST) -> dict[str, Any]:
    manifest = _load_json(path)
    if manifest.get("schema_version") != "ai2.eval_inputs.v2":
        raise AssertionError("manifest schema_version must be ai2.eval_inputs.v2")

    input_files = manifest.get("input_files") or []
    input_ids = [str(item.get("id")) for item in input_files]
    if len(input_ids) != len(set(input_ids)):
        raise AssertionError("input file ids must be unique")
    input_id_set = set(input_ids)
    input_results = [_validate_input_file(item) for item in input_files]

    cases = all_eval_cases()
    expected_count = int(manifest.get("catalog", {}).get("total_cases", 0))
    if len(cases) != expected_count:
        raise AssertionError(f"catalog count mismatch: manifest={expected_count}, runtime={len(cases)}")

    groups = manifest.get("coverage_matrix") or []
    group_ids: set[str] = set()
    explicitly_covered: set[str] = set()
    for group in groups:
        group_id = str(group.get("id") or "")
        if not group_id or group_id in group_ids:
            raise AssertionError(f"duplicate/empty coverage group: {group_id}")
        group_ids.add(group_id)
        missing_inputs = set(group.get("input_ids") or []) - input_id_set
        if missing_inputs:
            raise AssertionError(f"{group_id}: unknown input ids {sorted(missing_inputs)}")
        modes = set(group.get("modes") or [])
        if not modes or not modes <= VALID_MODES:
            raise AssertionError(f"{group_id}: invalid modes {sorted(modes)}")
        case_ids = set(group.get("case_ids") or [])
        unknown_cases = case_ids - set(cases)
        if unknown_cases:
            raise AssertionError(f"{group_id}: unknown case ids {sorted(unknown_cases)}")
        explicitly_covered.update(case_ids)

    catalog_coverage = manifest.get("catalog_coverage") or {}
    if catalog_coverage.get("selector") != "all_eval_cases":
        raise AssertionError("catalog_coverage.selector must be all_eval_cases")
    catalog_inputs = set(catalog_coverage.get("input_ids") or [])
    if not catalog_inputs <= input_id_set:
        raise AssertionError(f"catalog coverage references unknown inputs: {sorted(catalog_inputs - input_id_set)}")
    if not catalog_coverage.get("require_all_case_ids"):
        raise AssertionError("catalog coverage must require all case ids")

    return {
        "manifest": str(path.relative_to(ROOT)),
        "input_files": len(input_files),
        "valid_inputs": sum(item["status"] == "VALID" for item in input_results),
        "rejected_inputs": sum(item["status"] == "REJECTED" for item in input_results),
        "coverage_groups": len(groups),
        "catalog_cases": len(cases),
        "explicit_case_references": len(explicitly_covered),
        "input_results": input_results,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--manifest", type=Path, default=MANIFEST)
    args = parser.parse_args()
    try:
        result = validate_manifest(args.manifest.resolve())
    except (AssertionError, OSError, json.JSONDecodeError) as exc:
        print(f"INPUT_COVERAGE_FAIL: {exc}", file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
