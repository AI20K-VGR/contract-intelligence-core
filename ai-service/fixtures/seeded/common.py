"""Build a signed Backend → AI2 processing request from fictional OCR lines (body + annex)."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path

from app.security.service_envelope import build_service_envelope

_ROOT = Path(__file__).resolve().parents[3]
_EXAMPLE = _ROOT / "docs" / "contracts" / "examples" / "ai1.snapshot.v1.body.example.json"
TENANT_ID = "tenant_seeded"

DISCLAIMER = [
    "BỘ TÀI LIỆU HƯ CẤU, chỉ dùng kiểm thử phần mềm. Tên doanh nghiệp, số hợp đồng, số tiền và điều khoản đều được tạo",
    "mới; không đại diện cho giao dịch thật.",
]


def _lines(doc: str, page_no: int, texts: list[str]) -> list[dict]:
    return [
        {
            "line_id": f"{doc}:s1:p{page_no:03d}:l{index:03d}",
            "raw_text": text,
            "bbox": [0.1, 0.05 + index * 0.02, 0.9, 0.065 + index * 0.02],
            "bbox_source": "native",
            "geometry_status": "measured",
            "words": [],
        }
        for index, text in enumerate(texts, start=1)
    ]


def _snapshot(dossier_id: str, doc: str, pages: list[list[str]], digest: str) -> dict:
    base = json.loads(_EXAMPLE.read_text(encoding="utf-8"))
    template = base["pages"][0]
    base.update(
        {
            "snapshot_id": f"snap-{doc}",
            "dossier_id": dossier_id,
            "document_id": doc,
            "source_digest": digest,
            "pages": [
                {
                    **template,
                    "page_no": number,
                    "page_revision_id": f"{doc}:p{number}",
                    "quality": {
                        "coverage_status": "COMPLETE",
                        "ocr_confidence": 0.97,
                        "signals": [],
                    },
                    "lines": _lines(doc, number, texts),
                    "tables": [],
                    "warnings": [],
                    "table_coverage": {"status": "NOT_PRESENT", "method": "test", "version": "1"},
                }
                for number, texts in enumerate(pages, start=1)
            ],
        }
    )
    return base


def _identity(snapshot: dict) -> dict:
    digest = hashlib.sha256(
        json.dumps(snapshot, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode(
            "utf-8"
        )
    ).hexdigest()
    return {
        "snapshot_id": snapshot["snapshot_id"],
        "snapshot_version": "ai1.snapshot.v1",
        "source_digest": snapshot["source_digest"],
        "snapshot_digest": digest,
    }


def semantic_profile() -> dict:
    payload = {
        "schema_version": "ai2.semantic-profile.v1",
        "capability": "ai2.semantic.v1",
        "tenant_id": TENANT_ID,
        "version": 1,
        "contract_type": "SALES",
        "alias_version": 0,
        "alias_digest": None,
        "aliases": [],
        "activation_state": "DRAFT_ONLY",
        "alias_proposal_minimum_length": None,
        # Production caps (docker-compose AI2_SEMANTIC_CONTEXT_CAPS).
        "context_bounds": {
            "max_hops": 2,
            "max_nodes": 256,
            "max_context_tokens": 32768,
            "max_output_tokens": 8192,
            "max_llm_calls": 20,
            "max_seconds": 300,
        },
    }
    payload["digest"] = hashlib.sha256(
        json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()
    return payload


def context_caps_env() -> str:
    return json.dumps(semantic_profile()["context_bounds"])


def build_request(
    *,
    dossier_id: str,
    body_pages: list[list[str]],
    annex_pages: list[list[str]],
    egress_allowed: bool = False,
) -> dict:
    body = _snapshot(dossier_id, "doc_body", body_pages, "1" * 64)
    annex = _snapshot(dossier_id, "doc_annex", annex_pages, "2" * 64)
    payload = {
        "schema_version": "be.ai2.processing.request.v1",
        "request_id": f"req-{dossier_id}",
        "idempotency_key": f"{dossier_id}:1",
        "attempt": 1,
        "task_id": "process-dossier",
        "dossier_id": dossier_id,
        "snapshots": [body, annex],
        "snapshot_identities": [_identity(body), _identity(annex)],
        "dossier_members": [
            {
                "member_id": "m-body",
                "document_id": "doc_body",
                "snapshot_id": body["snapshot_id"],
                "role": "body",
                "source_digest": body["source_digest"],
            },
            {
                "member_id": "m-annex",
                "document_id": "doc_annex",
                "snapshot_id": annex["snapshot_id"],
                "role": "annex",
                "source_digest": annex["source_digest"],
            },
        ],
        "role_relation_map": [
            {
                "relation_id": "rel-1",
                "relation_type": "ANNEX_OF",
                "member_id": "m-annex",
                "related_member_id": "m-body",
                "dossier_id": dossier_id,
            }
        ],
        "semantic_profile": semantic_profile(),
        "policy_flags": {
            "egress_allowed": egress_allowed,
            "use_vector": False,
            "budget_limits": {
                "max_processing_seconds": 310,
                "max_llm_calls": 20,
                "max_embedding_tokens": 50000,
            },
        },
    }
    payload["service_envelope"] = build_service_envelope(
        payload,
        secret="seeded-test-secret",
        tenant_id=TENANT_ID,
        dossier_id=dossier_id,
        actor_id="seeded",
    )
    return payload
