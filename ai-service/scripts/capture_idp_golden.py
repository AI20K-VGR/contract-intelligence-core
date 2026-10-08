"""Flag-off golden of ``run_idp`` (contract graph P3, K2): sha256 per case of the job result,
the BE wire payload (request case only) and the persisted record.

  PYTHONHASHSEED=0 python scripts/capture_idp_golden.py            # (re)write the golden
  python scripts/capture_idp_golden.py --emit-shas                 # {case: {...}} on stdout
  python scripts/capture_idp_golden.py --emit-full <case_id>       # full JSON of one case

Run from ``ai-service/``. Capture refuses to run unless ``PYTHONHASHSEED=0`` (D16/RT-01: the
old path iterates a ``set`` of strings at ``app/pipeline/compare.py:67-71``) and drops
``AI2_CONTRACT_GRAPH_ENABLED``; ``--emit-*`` keep the environment as given so the tests can
probe explicit flag values. uuid4 is patched with a counter reset per case.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import sys
import uuid
from collections.abc import Callable, Iterator
from contextlib import ExitStack, contextmanager
from pathlib import Path
from typing import Any
from unittest import mock

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

GOLDEN = ROOT / "fixtures" / "contract_graph" / "idp_flag_off_golden.json"
EXAMPLES = ROOT.parent / "docs" / "contracts" / "examples"
FLAG = "AI2_CONTRACT_GRAPH_ENABLED"
SCHEMA = "idp-flag-off-golden.v1"
JOB_ID = "job_golden"
REQUEST_CASE = "wire:ai1.snapshot.v1.body+annex"
MOCK_CASE = "fixtures.mock_record"
UUID_SOURCES = ("app.pipeline.idp.uuid4", "app.pipeline.clause.uuid4", "app.pipeline.compare.uuid4")
# fixed so the request (and its envelope) is byte-identical across runs
ENVELOPE_NOW = 1_790_000_000
ENVELOPE_NONCE = "0" * 32

Case = tuple[str, Callable[[], tuple[Any, Any, Any]]]


def sha256_json(value: Any) -> str:
    text = json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


@contextmanager
def deterministic_uuid4() -> Iterator[None]:
    counter = iter(range(1, 1 << 30))

    def fake() -> uuid.UUID:
        return uuid.UUID(int=next(counter))

    with ExitStack() as stack:
        for target in UUID_SOURCES:
            stack.enter_context(mock.patch(target, fake))
        yield


def cases() -> list[Case]:
    import fixtures
    from fixtures.catalog import all_cases

    out: list[Case] = [(MOCK_CASE, lambda: (fixtures.mock_record(), fixtures.envelope(), None))]
    for case_id in sorted(all_cases()):
        out.append((case_id, lambda case_id=case_id: _catalog_case(case_id)))
    out.append((REQUEST_CASE, _request_case))
    return out


def run_case(build: Callable[[], tuple[Any, Any, Any]]) -> dict[str, Any]:
    from app.contracts.wire import job_result_to_wire
    from app.pipeline.idp import run_idp
    from app.tools.persist import record_to_dict

    with deterministic_uuid4():
        record, envelope, request = build()
        result = run_idp(record, envelope, job_id=JOB_ID)
        wire = job_result_to_wire(result, request) if request is not None else None
    return {
        "job_result": result.model_dump(mode="json"),
        "wire": wire,
        "record": record_to_dict(record),
    }


def shas(full: dict[str, Any]) -> dict[str, str | None]:
    return {
        "job_result": sha256_json(full["job_result"]),
        "wire": sha256_json(full["wire"]) if full["wire"] is not None else None,
        "record": sha256_json(full["record"]),
    }


def emit_shas() -> dict[str, dict[str, str | None]]:
    return {case_id: shas(run_case(build)) for case_id, build in cases()}


def representative_cases(case_ids: list[str]) -> list[str]:
    catalog = [c for c in case_ids if c not in (MOCK_CASE, REQUEST_CASE)]
    return [MOCK_CASE, catalog[0], REQUEST_CASE]


def capture() -> dict[str, Any]:
    built = {case_id: run_case(build) for case_id, build in cases()}
    keep = representative_cases(list(built))
    return {
        "schema": SCHEMA,
        "hashseed": os.environ["PYTHONHASHSEED"],
        "python": f"{sys.version_info.major}.{sys.version_info.minor}",
        "flag": f"{FLAG} unset",
        "job_id": JOB_ID,
        "cases": {case_id: shas(full) for case_id, full in built.items()},
        "full": {case_id: built[case_id] for case_id in keep},
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python scripts/capture_idp_golden.py")
    mode = parser.add_mutually_exclusive_group()
    mode.add_argument("--emit-shas", action="store_true", help="print sha256 per case as JSON")
    mode.add_argument("--emit-full", metavar="CASE_ID", help="print the full JSON of one case")
    parser.add_argument("--out", type=Path, default=GOLDEN)
    args = parser.parse_args(argv)
    if args.emit_shas:
        _print(emit_shas())
        return 0
    if args.emit_full:
        found = dict(cases()).get(args.emit_full)
        if found is None:
            print(f"unknown case {args.emit_full!r}", file=sys.stderr)
            return 2
        _print(run_case(found))
        return 0
    if os.environ.get("PYTHONHASHSEED") != "0":
        print("refusing to capture: run with PYTHONHASHSEED=0 (RT-01)", file=sys.stderr)
        return 2
    os.environ.pop(FLAG, None)
    golden = capture()
    args.out.parent.mkdir(parents=True, exist_ok=True)
    with open(args.out, "w", encoding="utf-8", newline="\n") as fh:
        fh.write(json.dumps(golden, ensure_ascii=False, indent=1, sort_keys=True) + "\n")
    print(f"captured {len(golden['cases'])} cases -> {args.out}")
    return 0


def _catalog_case(case_id: str) -> tuple[Any, Any, Any]:
    from fixtures.catalog import load_case

    pack = load_case(case_id)
    return pack.record, pack.envelope, None


def _request_case() -> tuple[Any, Any, Any]:
    from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request

    request, adapted = adapt_be_ai2_processing_request(_request_payload())
    return adapted.record, adapted.envelope, request


def _request_payload() -> dict[str, Any]:
    """Same request as ``tests/test_processing_wire_contract.py::_request`` with a fixed envelope."""

    from app.security.service_envelope import build_service_envelope

    body = json.loads((EXAMPLES / "ai1.snapshot.v1.body.example.json").read_text(encoding="utf-8"))
    annex = json.loads(
        (EXAMPLES / "ai1.snapshot.v1.annex.example.json").read_text(encoding="utf-8")
    )

    def identity(snapshot: dict[str, Any]) -> dict[str, Any]:
        canonical = json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":"))
        return {
            "snapshot_id": snapshot["snapshot_id"],
            "snapshot_version": "ai1.snapshot.v1",
            "source_digest": snapshot["source_digest"],
            "snapshot_digest": hashlib.sha256(canonical.encode("utf-8")).hexdigest(),
        }

    def member(member_id: str, snapshot: dict[str, Any], role: str) -> dict[str, Any]:
        return {
            "member_id": member_id,
            "document_id": snapshot["document_id"],
            "snapshot_id": snapshot["snapshot_id"],
            "role": role,
            "source_digest": snapshot["source_digest"],
        }

    payload: dict[str, Any] = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": "req-wire-001",
        "idempotency_key": "dossier-example-001:attempt-1",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": "dossier-example-001",
        "snapshots": [body, annex],
        "snapshot_identities": [identity(body), identity(annex)],
        "dossier_members": [
            member("member-body-001", body, "body"),
            member("member-annex-001", annex, "annex"),
        ],
        "role_relation_map": [
            {
                "relation_id": "relation-annex-001",
                "relation_type": "ANNEX_OF",
                "member_id": "member-annex-001",
                "related_member_id": "member-body-001",
                "dossier_id": "dossier-example-001",
            }
        ],
        "policy_flags": {
            "egress_allowed": False,
            "use_vector": True,
            "budget_limits": {
                "max_processing_seconds": 300,
                "max_llm_calls": 20,
                "max_embedding_tokens": 50000,
            },
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload,
        secret="test-secret",
        tenant_id="tenant_a",
        dossier_id=payload["dossier_id"],
        actor_id="test-backend",
        now=ENVELOPE_NOW,
        nonce=ENVELOPE_NONCE,
    )
    return payload


def _print(value: Any) -> None:
    sys.stdout.buffer.write(
        (json.dumps(value, ensure_ascii=False, sort_keys=True) + "\n").encode("utf-8")
    )


if __name__ == "__main__":
    sys.exit(main())
