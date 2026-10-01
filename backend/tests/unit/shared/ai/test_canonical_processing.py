"""Tests for the Backend -> AI2 canonical processing mapper."""

from __future__ import annotations

from types import SimpleNamespace

from contract_intelligence.shared.ai.canonical_processing import (
    build_processing_request,
    strip_internal_fields,
)

STORED_AT = "2026-09-30T08:00:00+00:00"


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

    request = build_processing_request(  # defaults: attempt 1, 300s budget
        dossier_id="dos-1",
        run_id="run-1",
        snapshots={"doc-1": snapshot},
        documents=[document],
        members=[member],
        relations=[],
        snapshot_created_at={"doc-1": STORED_AT},
    )

    assert request is not None
    assert request["snapshots"][0]["source_digest"] == digest
    assert request["snapshot_identities"][0]["source_digest"] == digest
    assert request["dossier_members"][0]["source_digest"] == digest


def _compact_request(**overrides: object) -> dict[str, object] | None:
    snapshot = {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": "snap-1",
        "source_digest": "b" * 64,
        "dossier_id": "dos-1",
        "document_id": "doc-1",
        "pages": [],
    }
    member = SimpleNamespace(
        id="member-1", included=True, document_id="doc-1", order_index=0, doc_type="contract"
    )
    kwargs: dict[str, object] = {
        "dossier_id": "dos-1",
        "run_id": "run-1",
        "snapshots": {"doc-1": snapshot},
        "documents": [SimpleNamespace(id="doc-1")],
        "members": [member],
        "relations": [],
        "snapshot_created_at": {"doc-1": STORED_AT},
    }
    kwargs.update(overrides)
    return build_processing_request(**kwargs)  # type: ignore[arg-type]


def test_rebuilding_the_same_run_sends_an_identical_payload() -> None:
    """DEC-BE-AI2-01 B1: a resend after a restart must not trip AI2's 409."""
    first = _compact_request()
    second = _compact_request()

    assert first is not None and second is not None
    assert strip_internal_fields(first) == strip_internal_fields(second)
    assert first["snapshots"][0]["created_at"] == STORED_AT  # type: ignore[index]


def test_relation_order_does_not_change_the_payload() -> None:
    snapshots = {
        doc: {
            "schema_version": "ai1.snapshot.v1",
            "snapshot_id": f"snap-{doc}",
            "source_digest": "b" * 64,
            "dossier_id": "dos-1",
            "document_id": doc,
            "pages": [],
        }
        for doc in ("doc-1", "doc-2", "doc-3")
    }
    members = [
        SimpleNamespace(
            id=f"member-{doc}",
            included=True,
            document_id=doc,
            order_index=index,
            doc_type="contract" if doc == "doc-1" else "annex",
        )
        for index, doc in enumerate(snapshots)
    ]
    relations = [
        SimpleNamespace(
            id=f"rel-{doc}",
            source_document_id=doc,
            target_document_id="doc-1",
            relation_type="annex_of",
        )
        for doc in ("doc-2", "doc-3")
    ]
    common: dict[str, object] = {
        "snapshots": snapshots,
        "documents": [SimpleNamespace(id=doc) for doc in snapshots],
        "members": members,
        "snapshot_created_at": dict.fromkeys(snapshots, STORED_AT),
    }

    forward = _compact_request(**common, relations=relations)
    backward = _compact_request(**common, relations=list(reversed(relations)))

    assert forward is not None and backward is not None
    assert strip_internal_fields(forward) == strip_internal_fields(backward)


def test_compact_snapshot_without_a_stored_time_is_not_sent() -> None:
    assert _compact_request(snapshot_created_at={}) is None
