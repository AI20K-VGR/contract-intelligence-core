"""Tests for the Backend -> AI2 canonical processing mapper."""

from __future__ import annotations

from types import SimpleNamespace

from contract_intelligence.shared.ai.canonical_processing import build_processing_request


def test_processing_request_normalizes_ai1_sha256_prefix_for_ai2_wire_contract() -> None:
    digest = "a" * 64
    snapshot = {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-1",
        "source_digest": f"sha256:{digest}",
        "dossier_id": "dos-1",
        "document_id": "doc-1",
        "pages": [],
    }
    member = SimpleNamespace(
        id="member-1",
        included=True,
        document_id="doc-1",
        order_index=0,
        doc_type="contract",
    )
    document = SimpleNamespace(id="doc-1")

    request = build_processing_request(
        dossier_id="dos-1",
        run_id="run-1",
        snapshots={"doc-1": snapshot},
        documents=[document],
        members=[member],
        relations=[],
    )

    assert request is not None
    assert request["snapshots"][0]["source_digest"] == digest
    assert request["snapshot_identities"][0]["source_digest"] == digest
    assert request["dossier_members"][0]["source_digest"] == digest
