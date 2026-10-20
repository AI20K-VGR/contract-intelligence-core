"""Move a reviewed v2 card proposal into the approved-card location."""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Approve and install an AI2 v2 card proposal")
    parser.add_argument("--proposal", required=True, type=Path)
    parser.add_argument("--approved-by")
    args = parser.parse_args(argv)

    if "CI" in os.environ:
        print("ERROR: card approval is disabled in CI", file=sys.stderr)
        return 2
    if not args.approved_by or not args.approved_by.strip():
        print("ERROR: --approved-by is required", file=sys.stderr)
        return 2
    proposal = args.proposal
    try:
        payload = json.loads(proposal.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"ERROR: cannot read proposal: {exc}", file=sys.stderr)
        return 2
    if not isinstance(payload, dict) or payload.get("schema_version") != "ai2.eval.strategy.v2":
        print("ERROR: proposal must be an ai2.eval.strategy.v2 object", file=sys.stderr)
        return 2

    approved = dict(payload)
    approved["approved_by"] = args.approved_by.strip()
    approved["approved_ts"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    body = (json.dumps(approved, ensure_ascii=False, sort_keys=True, indent=2) + "\n").encode("utf-8")
    digest = hashlib.sha256(body.replace(b"\r\n", b"\n")).hexdigest()
    try:
        card_path = _approved_path(proposal)
    except ValueError as exc:
        print(f"ERROR: {exc}", file=sys.stderr)
        return 2
    sidecar_path = card_path.with_suffix(".sha256")
    if proposal.resolve() in {card_path.resolve(), sidecar_path.resolve()}:
        print("ERROR: proposal path must differ from approved destination", file=sys.stderr)
        return 2
    if not _confirm(proposal, card_path, approved):
        print("Approval cancelled", file=sys.stderr)
        return 2

    card_path.parent.mkdir(parents=True, exist_ok=True)
    staged_card = card_path.with_name(card_path.name + ".tmp")
    staged_hash = sidecar_path.with_name(sidecar_path.name + ".tmp")
    try:
        staged_card.write_bytes(body)
        staged_hash.write_text(digest + "\n", encoding="ascii", newline="\n")
        os.replace(staged_card, card_path)
        os.replace(staged_hash, sidecar_path)
        proposal.unlink()
    except OSError as exc:
        print(f"ERROR: could not install approved card: {exc}", file=sys.stderr)
        return 2
    finally:
        staged_card.unlink(missing_ok=True)
        staged_hash.unlink(missing_ok=True)
    print(f"Approved card: {card_path}")
    print(f"Threshold changes: {_threshold_summary(payload)}")
    return 0


def _approved_path(proposal: Path) -> Path:
    name = proposal.name
    if name.endswith(".v2.json"):
        name = name[:-len(".v2.json")] + ".json"
    elif name.endswith(".json"):
        name = name[:-len(".json")] + ".json"
    else:
        raise ValueError("proposal filename must end in .json")
    parent = proposal.parent.parent / "cards" if proposal.parent.name == "proposed" else proposal.parent / "cards"
    return parent / name


def _confirm(proposal: Path, card_path: Path, payload: dict[str, Any]) -> bool:
    try:
        answer = input(
            f"Approve {proposal.name} -> {card_path.name}; metrics/thresholds: {_threshold_summary(payload)}? [y/N] "
        )
    except (EOFError, OSError):
        return False
    return answer.strip().casefold() in {"y", "yes"}


def _threshold_summary(payload: dict[str, Any]) -> str:
    metrics = payload.get("metrics")
    if isinstance(metrics, dict):
        return ", ".join(f"{name}={value.get('threshold')}" for name, value in sorted(metrics.items()) if isinstance(value, dict)) or "no metric thresholds"
    return "no metric thresholds"


if __name__ == "__main__":
    raise SystemExit(main())
