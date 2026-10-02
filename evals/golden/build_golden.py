"""Build, validate, and report the deterministic synthetic golden set."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from collections.abc import Sequence
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from evals.golden.catalog import CONTRACTS
from evals.golden.render_snapshot import render_contract

GENERATOR_VERSION = "1.0.0"
SPEC_COMMIT = "bdcb297e2522a589539c359b2f864d860754c660"
PACKAGE_ROOT = Path(__file__).resolve().parents[1]
REPOSITORY_ROOT = PACKAGE_ROOT.parent
DATA_DIR = PACKAGE_ROOT / "data" / "golden"
SNAPSHOT_SCHEMA = REPOSITORY_ROOT / "docs" / "contracts" / "ai1.snapshot.v1.schema.json"
_SPLITS = {
    "G01": "dev",
    "G02": "dev",
    "G03": "dev",
    "G04": "val",
    "G05": "dev",
    "G06": "holdout",
    "G07": "holdout",
    "G08": "dev",
}
_STATE_FLOORS = {
    "ANSWERED": 35,
    "NEEDS_REVIEW": 15,
    "INSUFFICIENT_EVIDENCE": 17,
    "NOT_COMPARABLE": 4,
}


def _json_bytes(value: Any) -> bytes:
    return (json.dumps(value, ensure_ascii=False, indent=2, sort_keys=True) + "\n").encode("utf-8")


def _sha256_lf(payload: bytes) -> str:
    return hashlib.sha256(payload.replace(b"\r\n", b"\n")).hexdigest()


def _outputs(variant_seed: int | None = None) -> dict[str, bytes]:
    snapshots: dict[str, dict[str, Any]] = {}
    questions: list[dict[str, Any]] = []
    for contract in CONTRACTS:
        snapshot, contract_questions = render_contract(contract, variant_seed=variant_seed)
        snapshots[f"snapshots/{contract.contract_id}.json"] = snapshot
        questions.extend(contract_questions)

    files = []
    for path, snapshot in snapshots.items():
        contract_id = path.rsplit("/", 1)[-1].removesuffix(".json")
        files.append(
            {
                "path": path,
                "sha256_lf": _sha256_lf(_json_bytes(snapshot)),
                "contract_id": contract_id,
                "pages": len(snapshot["pages"]),
                "split": _SPLITS[contract_id],
            }
        )

    counts: dict[str, int] = {}
    for question in questions:
        counts[question["expected_state"]] = counts.get(question["expected_state"], 0) + 1
    units = {
        "questions": len(questions),
        "comparisons": sum(question["comparison"] for question in questions),
        "required_spans": sum(len(question["required_spans"]) for question in questions),
        "gold_values": sum(len(question["gold_values"]) for question in questions),
        "non_answerable": sum(question["expected_state"] != "ANSWERED" for question in questions),
        "states": dict(sorted(counts.items())),
    }
    manifest = {
        "schema_version": "ai2.golden.synthetic.v1",
        "golden_version": "1.0.0",
        "generator_version": GENERATOR_VERSION,
        "synthetic": True,
        "anonymized": False,
        "files": files,
        "units": units,
        "spec_commit": SPEC_COMMIT,
        "approval": None,
    }
    outputs = {path: _json_bytes(snapshot) for path, snapshot in snapshots.items()}
    outputs["questions.json"] = _json_bytes(questions)
    outputs["manifest.json"] = _json_bytes(manifest)
    return outputs


def _content_sha256(outputs: dict[str, bytes]) -> str:
    digest = hashlib.sha256()
    for path, payload in sorted(outputs.items()):
        if path == "manifest.json":
            continue
        digest.update(path.encode("utf-8"))
        digest.update(b"\0")
        digest.update(_sha256_lf(payload).encode("ascii"))
        digest.update(b"\n")
    return digest.hexdigest()


def _existing_content_sha256(output_dir: Path, outputs: dict[str, bytes]) -> str | None:
    existing: dict[str, bytes] = {}
    try:
        for relative_path in outputs:
            if relative_path == "manifest.json":
                continue
            path = output_dir / relative_path
            if not path.is_file():
                return None
            existing[relative_path] = path.read_bytes()
    except OSError:
        return None
    return _content_sha256(existing)


def _read_manifest(path: Path) -> dict[str, Any] | None:
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except FileNotFoundError:
        return None
    except (OSError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read manifest {path}: {exc}") from exc
    if not isinstance(value, dict):
        raise TypeError(f"manifest must be an object: {path}")
    return value


def build_golden(
    output_dir: Path = DATA_DIR,
    *,
    variant_seed: int | None = None,
    reset_approval: bool = False,
) -> int:
    """Write golden outputs, preserving approval only when content is unchanged."""

    if variant_seed is not None and variant_seed < 0:
        print("variant seed must be a non-negative integer", file=sys.stderr)
        return 2
    try:
        outputs = _outputs(variant_seed)
        manifest_path = output_dir / "manifest.json"
        previous = _read_manifest(manifest_path)
    except (OSError, ValueError) as exc:
        print(str(exc), file=sys.stderr)
        return 2

    approval = previous.get("approval") if previous else None
    if approval is not None:
        if not isinstance(approval, dict) or not isinstance(approval.get("content_sha256"), str):
            print("existing approval is malformed; refusing to overwrite", file=sys.stderr)
            return 2
        content_changed = (
            approval["content_sha256"] != _content_sha256(outputs)
            or approval["content_sha256"] != _existing_content_sha256(output_dir, outputs)
        )
        if content_changed:
            if not reset_approval:
                print("golden content changed after approval; pass --reset-approval to clear it", file=sys.stderr)
                return 2
            approval = None
    if reset_approval:
        approval = None
    manifest = json.loads(outputs["manifest.json"].decode("utf-8"))
    manifest["approval"] = approval
    outputs["manifest.json"] = _json_bytes(manifest)

    try:
        for relative_path, payload in outputs.items():
            destination = output_dir / relative_path
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(payload)
    except OSError as exc:
        print(f"cannot write golden output: {exc}", file=sys.stderr)
        return 2
    print(f"built {len(manifest['files'])} snapshots and {manifest['units']['questions']} questions in {output_dir}")
    return 0


def check_golden(data_dir: Path = DATA_DIR, schema_path: Path = SNAPSHOT_SCHEMA) -> int:
    """Check only manifest file hashes and snapshot schema, deliberately ignoring approval."""

    try:
        manifest = _read_manifest(data_dir / "manifest.json")
        if manifest is None:
            raise ValueError("golden manifest is missing")
        schema = json.loads(schema_path.read_text(encoding="utf-8"))
        from jsonschema import Draft202012Validator

        validator = Draft202012Validator(schema)
    except (OSError, ValueError, ImportError, json.JSONDecodeError) as exc:
        print(f"golden check setup failed: {exc}", file=sys.stderr)
        return 2

    failures = []
    for entry in manifest.get("files", []):
        try:
            payload = (data_dir / entry["path"]).read_bytes()
            snapshot = json.loads(payload.decode("utf-8"))
        except (OSError, KeyError, UnicodeDecodeError, json.JSONDecodeError) as exc:
            failures.append(f"{entry.get('path', '<unknown>')}: {exc}")
            continue
        if _sha256_lf(payload) != entry.get("sha256_lf"):
            failures.append(f"{entry['path']}: sha256_lf mismatch")
        errors = sorted(validator.iter_errors(snapshot), key=lambda error: list(error.absolute_path))
        if errors:
            failures.append(f"{entry['path']}: schema invalid at {list(errors[0].absolute_path)}")
    if failures:
        print("\n".join(failures), file=sys.stderr)
        return 1
    print(f"checked {len(manifest.get('files', []))} snapshots")
    return 0


def stats(data_dir: Path = DATA_DIR) -> tuple[dict[str, Any], bool]:
    """Return generated-unit counts and whether the declared floors are met."""

    try:
        manifest = _read_manifest(data_dir / "manifest.json")
        questions = json.loads((data_dir / "questions.json").read_text(encoding="utf-8"))
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        raise ValueError(f"golden data unavailable: {exc}") from exc
    if manifest is None or not isinstance(questions, list):
        raise ValueError("golden manifest or questions file has invalid shape")
    units = dict(manifest.get("units", {}))
    units["largest_contract_pages"] = max(
        (entry.get("pages", 0) for entry in manifest.get("files", [])), default=0
    )
    enough = all(units.get(state, units.get("states", {}).get(state, 0)) >= floor for state, floor in _STATE_FLOORS.items())
    enough = enough and units.get("questions", 0) >= 84 and units.get("comparisons", 0) >= 15
    enough = enough and units.get("non_answerable", 0) / max(1, units.get("questions", 0)) >= 0.2
    enough = enough and units.get("required_spans", 0) >= 60 and units.get("gold_values", 0) >= 60
    enough = enough and units["largest_contract_pages"] >= 55
    return units, enough


def approve(*, approved_by: str, data_dir: Path = DATA_DIR) -> int:
    if os.environ.get("CI"):
        print("approval is disabled when CI is set", file=sys.stderr)
        return 2
    if not approved_by.strip():
        print("--by must name a reviewer", file=sys.stderr)
        return 2
    try:
        manifest_path = data_dir / "manifest.json"
        manifest = _read_manifest(manifest_path)
        if manifest is None:
            raise ValueError("golden manifest is missing")
        outputs = _outputs()
        content_hash = _content_sha256(outputs)
        if any(
            not (data_dir / relative).is_file()
            or _sha256_lf((data_dir / relative).read_bytes()) != _sha256_lf(payload)
            for relative, payload in outputs.items()
            if relative != "manifest.json"
        ):
            raise ValueError("current golden content does not match deterministic generator output")
        manifest["approval"] = {
            "approved_by": approved_by.strip(),
            "approved_at": datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z"),
            "content_sha256": content_hash,
        }
        manifest_path.write_bytes(_json_bytes(manifest))
    except (OSError, ValueError, KeyError) as exc:
        print(str(exc), file=sys.stderr)
        return 2
    print(f"approved golden content by {approved_by.strip()}")
    return 0


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", nargs="?", choices=("build", "check", "stats", "approve"), default="build")
    parser.add_argument("--check", dest="check_flag", action="store_true", help="validate hashes and schemas")
    parser.add_argument("--reset-approval", action="store_true")
    parser.add_argument("--by", dest="approved_by")
    parser.add_argument("--variant-seed", type=int)
    parser.add_argument("--out", type=Path)
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if args.check_flag or args.command == "check":
        if args.variant_seed is not None:
            return 2
        return check_golden(args.out or DATA_DIR)
    if args.command == "stats":
        try:
            result, enough = stats(args.out or DATA_DIR)
        except ValueError as exc:
            print(str(exc), file=sys.stderr)
            return 2
        print(json.dumps(result, ensure_ascii=False, sort_keys=True))
        return 0 if enough else 1
    if args.command == "approve":
        if args.variant_seed is not None or args.out is not None or args.reset_approval:
            return 2
        return approve(approved_by=args.approved_by or "")
    if args.command == "build":
        return build_golden(
            args.out or DATA_DIR,
            variant_seed=args.variant_seed,
            reset_approval=args.reset_approval,
        )
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
