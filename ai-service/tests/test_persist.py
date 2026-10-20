import pytest

from app.contracts.models import JobResult, JobStatus, ReviewState
from app.pipeline.ai1_ingest import ingest_files
from app.tools.persist import load_session, record_from_dict, record_to_dict, save_session
from app.tools.store import InMemorySnapshotStore


@pytest.mark.parametrize("consent", [True, False])
def test_record_roundtrip_preserves_explicit_content_sharing_consent(consent):
    from fixtures import mock_record

    record = mock_record()
    record.content_sharing_consent = consent
    payload = record_to_dict(record)
    assert payload["content_sharing_consent"] is consent
    assert record_from_dict(payload).content_sharing_consent is consent


@pytest.mark.parametrize("value", [None, "true", "false", 1, 0, {}])
def test_record_consent_restores_only_explicit_boolean_true(value):
    from fixtures import mock_record

    payload = record_to_dict(mock_record())
    payload["content_sharing_consent"] = value
    assert record_from_dict(payload).content_sharing_consent is False


def test_legacy_record_without_consent_fails_closed():
    from fixtures import mock_record

    payload = record_to_dict(mock_record())
    payload.pop("content_sharing_consent", None)
    assert record_from_dict(payload).content_sharing_consent is False


def test_record_roundtrip_keeps_nodes():
    rec, env, meta, blobs = ingest_files([("a.md", b"Dieu 1 MST 0312345678", "body")])
    d = record_to_dict(rec)
    rec2 = record_from_dict(d)
    assert rec2.dossier_id == rec.dossier_id
    assert len(rec2.nodes) == len(rec.nodes)
    assert rec2.pins.source_snapshot_digest == rec.pins.source_snapshot_digest


def test_empty_semantic_fields_do_not_change_legacy_record_shape():
    rec, _env, _meta, _blobs = ingest_files([("a.md", b"Dieu 1", "body")])

    payload = record_to_dict(rec)

    assert "semantic_profile" not in payload
    assert "semantic_extension" not in payload
    assert "semantic_snapshots" not in payload


def test_record_from_dict_defaults_missing_egress_approval_to_fail_closed():
    rec, _env, _meta, _blobs = ingest_files([("a.md", b"Dieu 1", "body")])
    payload = record_to_dict(rec)
    payload.pop("egress_approved", None)

    restored = record_from_dict(payload)

    assert restored.egress_approved is False


def test_save_load_session(tmp_path, monkeypatch):
    import app.tools.persist as persist

    monkeypatch.setattr(persist, "DATA", tmp_path)
    monkeypatch.setattr(persist, "DB", tmp_path / "runs.sqlite")
    rec, env, meta, blobs = ingest_files([("a.md", b"Dieu 1", "body")])
    store = InMemorySnapshotStore()
    s = {
        "record": rec,
        "envelope": env,
        "filename": "a.md",
        "source": "upload",
        "step": "reconstruct",
        "ai1": meta,
        "job": JobResult(
            job_id="j1", status=JobStatus.SUCCEEDED, review_state=ReviewState.NEEDS_REVIEW
        ),
        "used_llm": False,
        "blobs": blobs,
        "gold": False,
        "reviews": {"c1": {"action": "confirm", "reason": "", "revision": 1, "stale": False}},
        "reviews_stale": False,
        "published": False,
    }
    save_session("abc123", s, store)
    loaded = load_session("abc123", store)
    assert loaded is not None
    assert loaded["filename"] == "a.md"
    assert loaded["reviews"]["c1"]["action"] == "confirm"
    assert loaded["job"].job_id == "j1"
