from __future__ import annotations

from copy import deepcopy

import pytest

from app.migration.boundary import (
    DuplicateSubmissionConflict,
    FeatureFlags,
    MigrationBoundary,
    MigrationRequest,
    Route,
)


def request(*, key: str = "idem-1", raw: dict | None = None) -> MigrationRequest:
    return MigrationRequest(
        tenant_id="tenant-a",
        legacy_session_id="session-1",
        idempotency_key=key,
        raw_ai1=raw or {"snapshot_id": "snap-1", "text": "body"},
    )


def test_old_new_parity_dual_read_keeps_legacy_result_and_does_not_mutate_raw_ai1() -> None:
    raw = {"snapshot_id": "snap-1", "documents": [{"id": "body"}], "text": "body"}
    before = deepcopy(raw)
    boundary = MigrationBoundary(
        FeatureFlags(canonical_enabled=True, dual_read=True, canary_tenants=frozenset({"tenant-a"}))
    )

    outcome = boundary.submit(
        request(raw=raw),
        legacy_reader=lambda payload: {"status": "ok", "documents": payload["documents"]},
        canonical_reader=lambda payload: {"documents": payload["documents"], "status": "ok"},
    )

    assert outcome.route is Route.DUAL_READ
    assert outcome.result == {"status": "ok", "documents": [{"id": "body"}]}
    assert outcome.parity is not None and outcome.parity.matched
    assert raw == before
    assert boundary.records[-1].action == "PARITY_CHECKED"


def test_one_and_multi_document_compatibility_is_explicit() -> None:
    boundary = MigrationBoundary()
    one = boundary.inspect_documents(request())
    many = boundary.inspect_documents(
        request(raw={"documents": [{"id": "body"}, {"id": "annex"}]})
    )

    assert one.document_count == 1
    assert one.mode == "one-document"
    assert many.document_count == 2
    assert many.mode == "multi-document"
    assert many.document_ids == ("body", "annex")


def test_feature_flags_route_canary_and_rollback() -> None:
    boundary = MigrationBoundary(
        FeatureFlags(canonical_enabled=True, canary_tenants=frozenset({"tenant-a"}))
    )

    assert boundary.route_for("tenant-a") is Route.CANONICAL
    assert boundary.route_for("tenant-b") is Route.LEGACY

    boundary.rollback(reason="canary regression")
    assert boundary.route_for("tenant-a") is Route.LEGACY
    assert boundary.flags.rollback_to_legacy
    assert boundary.records[-1].action == "ROLLBACK_ACTIVATED"


def test_duplicate_submit_is_idempotent_and_payload_conflict_is_rejected() -> None:
    calls: list[str] = []
    boundary = MigrationBoundary(FeatureFlags(canonical_enabled=True))
    run = boundary.submit(
        request(),
        canonical_reader=lambda payload: calls.append(payload["snapshot_id"]) or {"ok": True},
    )
    duplicate = boundary.submit(
        request(),
        canonical_reader=lambda payload: calls.append("unexpected") or {"ok": False},
    )

    assert duplicate.duplicate
    assert duplicate.run_id == run.run_id
    assert calls == ["snap-1"]
    with pytest.raises(DuplicateSubmissionConflict):
        boundary.submit(
            request(raw={"snapshot_id": "different"}),
            canonical_reader=lambda payload: {"ok": True},
        )


def test_legacy_session_maps_to_one_durable_run() -> None:
    boundary = MigrationBoundary(FeatureFlags(canonical_enabled=True))
    first = boundary.submit(request(), canonical_reader=lambda payload: {"ok": True})
    second = boundary.submit(
        request(key="idem-2"), canonical_reader=lambda payload: {"ok": True}
    )

    assert first.run_id == second.run_id
    assert boundary.run_for_session("session-1") == first.run_id


def test_stale_or_unverified_generation_cannot_publish() -> None:
    boundary = MigrationBoundary(FeatureFlags(canonical_enabled=True))
    outcome = boundary.submit(request(), canonical_reader=lambda payload: {"ok": True})

    stale = boundary.publish(
        outcome.run_id, generation_id="older-generation", result={"ok": "stale"}, verified=True
    )
    unverified = boundary.publish(
        outcome.run_id, generation_id=outcome.generation_id, result={"ok": "unchecked"}, verified=False
    )

    assert not stale.published and stale.reason == "STALE_GENERATION"
    assert not unverified.published and unverified.reason == "UNVERIFIED_GENERATION"
    assert boundary.published_result(outcome.run_id) is None


def test_rollback_mid_run_preserves_records_and_blocks_canonical_publish() -> None:
    boundary = MigrationBoundary(FeatureFlags(canonical_enabled=True))
    outcome = boundary.submit(request(), canonical_reader=lambda payload: {"ok": True})
    before = boundary.records

    boundary.rollback(reason="operator rollback")
    published = boundary.publish(
        outcome.run_id, generation_id=outcome.generation_id, result={"ok": "late"}, verified=True
    )

    assert not published.published and published.reason == "ROLLBACK_ACTIVE"
    assert boundary.published_result(outcome.run_id) is None
    assert boundary.records[: len(before)] == before
    assert boundary.records[-1].action == "PUBLISH_REJECTED"

