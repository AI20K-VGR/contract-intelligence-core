import json

from contract_intelligence.worker import (
    _durable_snapshots_from_run,
    _merge_snapshot_cache,
    _snapshot_digest,
)


def _snapshot(document_id: str = "doc-1") -> dict[str, object]:
    return {
        "schema_version": "ai1.snapshot.v1",
        "snapshot_id": f"snap-{document_id}",
        "document_id": document_id,
        "source_digest": "sha256:source-1",
        "pages": [{"page_number": 1, "text": "body"}],
    }


def test_durable_run_payload_hydrates_snapshot_after_cache_restart() -> None:
    snapshot = _snapshot()
    run = type("Run", (), {"config_snapshot": json.dumps({"ai1_snapshots": {"doc-1": snapshot}})})()

    hydrated = _durable_snapshots_from_run(run)

    assert hydrated == {"doc-1": snapshot}
    assert _snapshot_digest(snapshot)


def test_merge_hydrates_only_valid_scoped_snapshots() -> None:
    cache: dict[str, dict[str, object]] = {}
    _merge_snapshot_cache(cache, {"doc-1": _snapshot(), "doc-2": {"document_id": "doc-2"}})

    assert "doc-1" in cache
    assert "doc-2" not in cache


def test_durable_run_payload_rejects_malformed_data() -> None:
    run = type("Run", (), {"config_snapshot": "not-json"})()

    assert _durable_snapshots_from_run(run) == {}
