"""AI2 submit/poll: tolerate transient errors, enforce the per-run deadline."""

from __future__ import annotations

from typing import Any
from unittest.mock import AsyncMock

import pytest

from contract_intelligence.config.settings import get_settings
from contract_intelligence.infrastructure import ai_adapters
from contract_intelligence.infrastructure.ai_adapters import (
    AiAdapterDeadlineExceeded,
    AiAdapterHTTPError,
    AiAdapterTimeoutError,
)

pytestmark = pytest.mark.asyncio

_SUBMIT_PAYLOAD: dict[str, Any] = dict.fromkeys(
    (
        "schema_version",
        "request_id",
        "idempotency_key",
        "attempt",
        "task_id",
        "dossier_id",
        "snapshots",
        "snapshot_identities",
        "dossier_members",
        "role_relation_map",
        "policy_flags",
    ),
    "x",
)


@pytest.fixture(autouse=True)
def _fast(monkeypatch: pytest.MonkeyPatch) -> None:
    settings = get_settings()
    monkeypatch.setattr(settings, "ai_dispatcher_poll_interval_seconds", 0.1)
    monkeypatch.setattr(settings, "ai2_max_consecutive_errors", 3)
    monkeypatch.setattr(ai_adapters, "_service_envelope", lambda *_a, **_k: {})
    monkeypatch.setattr(ai_adapters.asyncio, "sleep", AsyncMock())


async def _poll(timeout_seconds: float = 60.0) -> dict[str, Any]:
    return await ai_adapters.poll_ai2_processing(
        "job_1", tenant_id="t", dossier_id="d", timeout_seconds=timeout_seconds
    )


async def test_poll_rides_out_transient_errors(monkeypatch: pytest.MonkeyPatch) -> None:
    get_json = AsyncMock(
        side_effect=[
            AiAdapterTimeoutError("slow"),
            AiAdapterHTTPError(503, "busy"),
            {"status": "RUNNING"},
            AiAdapterHTTPError(429, "rate"),
            {"status": "SUCCEEDED", "job_id": "job_1"},
        ]
    )
    monkeypatch.setattr(ai_adapters, "_get_json", get_json)

    report = await _poll()

    assert report["status"] == "SUCCEEDED"
    assert get_json.await_count == 5


async def test_poll_gives_up_after_too_many_errors_in_a_row(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_json = AsyncMock(side_effect=AiAdapterHTTPError(502, "down"))
    monkeypatch.setattr(ai_adapters, "_get_json", get_json)

    with pytest.raises(AiAdapterHTTPError):
        await _poll()
    assert get_json.await_count == 3


async def test_poll_does_not_retry_a_client_error(monkeypatch: pytest.MonkeyPatch) -> None:
    get_json = AsyncMock(side_effect=AiAdapterHTTPError(403, "owner mismatch"))
    monkeypatch.setattr(ai_adapters, "_get_json", get_json)

    with pytest.raises(AiAdapterHTTPError):
        await _poll()
    assert get_json.await_count == 1


async def test_poll_raises_deadline_exceeded_while_job_still_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(ai_adapters, "_get_json", AsyncMock(return_value={"status": "RUNNING"}))
    clock = iter(float(n) for n in range(0, 1000, 10))
    monkeypatch.setattr(ai_adapters.time, "monotonic", lambda: next(clock))

    with pytest.raises(AiAdapterDeadlineExceeded):
        await _poll(timeout_seconds=25)
    assert not ai_adapters.is_transient(AiAdapterDeadlineExceeded("x"))


async def test_submit_retries_transient_errors_then_succeeds(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    post_json = AsyncMock(side_effect=[AiAdapterHTTPError(500, "boom"), {"job_id": "job_1"}])
    monkeypatch.setattr(ai_adapters, "_post_json", post_json)

    result = await ai_adapters.submit_ai2_processing(
        dict(_SUBMIT_PAYLOAD), tenant_id="t", dossier_id="d"
    )

    assert result == {"job_id": "job_1"}
    assert post_json.await_count == 2


async def test_submit_does_not_retry_a_rejected_payload(monkeypatch: pytest.MonkeyPatch) -> None:
    post_json = AsyncMock(side_effect=AiAdapterHTTPError(422, "bad snapshot"))
    monkeypatch.setattr(ai_adapters, "_post_json", post_json)

    with pytest.raises(AiAdapterHTTPError):
        await ai_adapters.submit_ai2_processing(
            dict(_SUBMIT_PAYLOAD), tenant_id="t", dossier_id="d"
        )
    assert post_json.await_count == 1
