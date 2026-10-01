from __future__ import annotations

import pytest

from app.migration.canary import (
    DuplicateSubmissionConflict,
    MigrationConfig,
    MigrationMode,
    SubmitRecord,
    can_publish,
    compare_outputs,
    rollback_mode,
    submit_once,
)


def record(
    *,
    key: str = "idem-1",
    dossier_id: str = "dossier-1",
    generation_id: str = "generation-2",
    status: str = "VERIFIED",
    source: str = "canary",
) -> SubmitRecord:
    return SubmitRecord(
        run_id=f"run-{dossier_id}",
        tenant_id="tenant-a",
        dossier_id=dossier_id,
        generation_id=generation_id,
        idempotency_key=key,
        status=status,
        source=source,
    )


def test_flags_cover_legacy_canary_canonical_and_publish_policy() -> None:
    assert [mode.value for mode in MigrationMode] == ["legacy", "canary", "canonical"]
    config = MigrationConfig(MigrationMode.CANARY)

    assert config.publish_verified_only
    assert config.compare_enabled
    assert MigrationConfig(MigrationMode.CANONICAL, False, False) == MigrationConfig(
        MigrationMode.CANONICAL,
        publish_verified_only=False,
        compare_enabled=False,
    )


def test_one_and_multi_document_dossiers_use_the_same_dossier_id_boundary() -> None:
    records: dict[str, SubmitRecord] = {}
    one = submit_once(records, record(dossier_id="one-document"))
    many = submit_once(records, record(key="idem-2", dossier_id="multi-document"))

    assert one.dossier_id == "one-document"
    assert many.dossier_id == "multi-document"
    assert list(records) == ["idem-1", "idem-2"]


def test_duplicate_is_idempotent_and_conflicting_digest_is_rejected() -> None:
    records: dict[str, SubmitRecord] = {}
    first = record()

    assert submit_once(records, first) is first
    assert submit_once(records, record()) is first

    with pytest.raises(DuplicateSubmissionConflict):
        submit_once(records, record(source="legacy"))


def test_only_current_verified_generation_can_publish() -> None:
    verified = record(generation_id="generation-2", status="verified")
    stale = record(generation_id="generation-1")
    unverified = record(generation_id="generation-2", status="PENDING")

    assert can_publish(verified, "generation-2")
    assert not can_publish(stale, "generation-2")
    assert not can_publish(unverified, "generation-2")


def test_parity_is_equal_or_has_sorted_nested_difference_paths() -> None:
    legacy = {"status": "verified", "documents": [{"id": "body"}, {"id": "annex"}]}
    canonical = {"documents": [{"id": "body"}, {"id": "appendix"}], "status": "verified"}

    assert compare_outputs(legacy, legacy).equal
    result = compare_outputs(legacy, canonical)
    assert not result.equal
    assert result.differences == ("$.documents[1].id",)
    assert result.differences == compare_outputs(legacy, canonical).differences


def test_rollback_forces_legacy_and_preserves_compare_and_publish_flags() -> None:
    config = MigrationConfig(
        MigrationMode.CANONICAL,
        publish_verified_only=False,
        compare_enabled=False,
    )

    rolled_back = rollback_mode(config)

    assert rolled_back.mode is MigrationMode.LEGACY
    assert rolled_back.publish_verified_only is False
    assert rolled_back.compare_enabled is False
    assert config.mode is MigrationMode.CANONICAL
