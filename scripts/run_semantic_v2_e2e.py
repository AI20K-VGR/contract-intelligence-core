"""Run a reproducible semantic-v2 probe without hiding provider state.

The comparator is always deterministic.  ``vector-only``, ``llm-only`` and
``full`` only record the requested provider mode; they must not replace or
remove deterministic pairs when no provider is configured.  A live provider
replay is an explicit operation outside this hermetic probe.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
from dataclasses import asdict
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
AI_SERVICE = ROOT / "ai-service"
if str(AI_SERVICE) not in sys.path:
    sys.path.insert(0, str(AI_SERVICE))

from app.contracts.clause_frames import Evidence
from app.pipeline.clause_keys import build_candidates
from app.pipeline.frame_comparison import compare_frames
from app.pipeline.frame_extraction import extract_frames

MODES = frozenset({"local-only", "vector-only", "llm-only", "full"})


def _mode_flags(mode: str) -> tuple[bool, bool]:
    if mode not in MODES:
        raise ValueError(f"unsupported mode: {mode}")
    return mode in {"vector-only", "full"}, mode in {"llm-only", "full"}


def _evidence(document_id: str, text: str) -> Evidence:
    digest = hashlib.sha256(f"{document_id}\0{text}".encode()).hexdigest()[:16]
    return Evidence(document_id, f"snapshot-{document_id}", f"node-{digest}", text)


def _pair_json(pair) -> dict[str, Any]:
    return {
        "left_id": pair.left_id,
        "right_id": pair.right_id,
        "disposition": pair.disposition,
        "reason": pair.reason,
        "review_state": pair.review_state,
        "left_evidence": [asdict(item) for item in pair.left_evidence],
        "right_evidence": [asdict(item) for item in pair.right_evidence],
    }


def run_case(left_text: str, right_text: str, *, mode: str = "local-only") -> dict[str, Any]:
    """Process one two-source case through the real frame comparator."""

    vector_requested, llm_requested = _mode_flags(mode)
    dossier_id = "e2e-semantic-v2-probe"
    left = extract_frames(
        _evidence("body", left_text), profile="SALES", dossier_id=dossier_id
    )
    right = extract_frames(
        _evidence("annex", right_text), profile="SALES", dossier_id=dossier_id
    )
    frames = (*left, *right)
    candidates = build_candidates(frames)
    by_id = {frame.frame_id: frame for frame in frames}
    pairs = [
        compare_frames(by_id[item.left_id], by_id[item.right_id])
        for item in candidates
    ]
    provider_configured = bool(os.getenv("OPENAI_API_KEY") or os.getenv("AI2_LLM_API_KEY"))
    return {
        "schema": "ai2.semantic-v2.e2e-receipt.v1",
        "mode": mode,
        "provider": {
            "vector_requested": vector_requested,
            "llm_requested": llm_requested,
            "llm_configured": provider_configured,
            "calls": 0,
            "deterministic_comparator": True,
        },
        "frames": [
            {
                "frame_id": frame.frame_id,
                "document_id": frame.document_id,
                "family": frame.family,
                "slots": {
                    name: {
                        "value": str(slot.value) if slot.value is not None else None,
                        "state": slot.state,
                    }
                    for name, slot in frame.slots
                    if slot.state in {"GROUNDED", "ABSENT"}
                },
                "citations": [asdict(evidence) for evidence in frame.evidence],
            }
            for frame in frames
        ],
        "pairs": [_pair_json(pair) for pair in pairs],
        "timeline": [],
        "coverage": {
            "frames": len(frames),
            "candidates": len(candidates),
            "deterministic_pairs": len(pairs),
            "provider_calls": 0,
            "vector_status": "REQUESTED_BUT_NOT_USED" if vector_requested else "NOT_REQUESTED",
            "llm_status": "REQUESTED_BUT_NOT_USED" if llm_requested else "NOT_REQUESTED",
            "amendment_state": "NOT_REQUESTED",
        },
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--left", default="Bên A phải thanh toán 30% khi ký.")
    parser.add_argument("--right", default="Bên A không được thanh toán 30% khi ký.")
    parser.add_argument("--mode", choices=sorted(MODES), default="local-only")
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args(argv)
    result = run_case(args.left, args.right, mode=args.mode)
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({"output": str(args.output), "mode": args.mode, "pairs": len(result["pairs"])}))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
