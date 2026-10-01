from __future__ import annotations

import asyncio
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

import pytest

import app.transport.kafka_idp_worker as worker


def _adapted_request(*roles: str):
    request = SimpleNamespace(
        dossier_members=[SimpleNamespace(role=role) for role in roles],
        policy_flags=SimpleNamespace(
            egress_allowed=False,
            use_vector=False,
            budget_limits=SimpleNamespace(
                max_processing_seconds=30,
                max_llm_calls=0,
                max_embedding_tokens=0,
            ),
        ),
    )
    adapted = SimpleNamespace(record=object(), envelope=object())
    return request, adapted


def _command(event_id: str = "evt-1", *, roles: tuple[str, ...] = ("body",)):
    return {
        "schema_version": "ci.kafka.v1",
        "event_id": event_id,
        "event_type": worker.EVENT_COMMAND,
        "trace_id": "trace-1",
        "tenant_id": "tenant-1",
        "correlation": {"dossier_id": "dos-1", "run_id": "run-1"},
        "payload": {"dossier_id": "dos-1", "snapshot_identities": []},
        "_roles": roles,
    }


@pytest.fixture(autouse=True)
def clear_processed_events():
    worker._processed.clear()
    yield
    worker._processed.clear()


def test_handle_command_publishes_completed_wire_result():
    command = _command()
    request, adapted = _adapted_request("body")
    wire = {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "req-1",
        "idempotency_key": "idem-1",
        "attempt": 1,
        "job_id": "job-placeholder",
        "status": "SUCCEEDED",
    }

    with (
        patch.object(worker, "adapt_be_ai2_processing_request", return_value=(request, adapted)),
        patch.object(worker, "run_idp", return_value=object()),
        patch.object(worker, "job_result_to_wire", return_value=wire),
    ):
        result = worker._handle_command(command)

    assert result["event_type"] == worker.EVENT_COMPLETED
    assert result["trace_id"] == "trace-1"
    assert result["correlation"] == command["correlation"]
    assert result["payload"]["status"] == "SUCCEEDED"
    assert result["payload"]["job_id"].startswith("job_")


def test_handle_command_rejects_annex_in_body_only_mvp():
    command = _command(roles=("body", "annex"))
    request, adapted = _adapted_request("body", "annex")

    with patch.object(
        worker, "adapt_be_ai2_processing_request", return_value=(request, adapted)
    ):
        result = worker._handle_command(command)

    assert result["event_type"] == worker.EVENT_FAILED
    assert result["payload"]["status"] == "FAILED"
    assert result["payload"]["errors"][0]["code"] == "MVP_BODY_ONLY_VIOLATION"
    assert result["payload"]["errors"][0]["retryable"] is False


def test_duplicate_event_id_returns_original_result_without_reprocessing():
    command = _command()
    request, adapted = _adapted_request("body")
    run_idp = Mock(return_value=object())
    wire = {
        "schema_version": "ai2.be.processing.result.v1",
        "request_id": "req-1",
        "idempotency_key": "idem-1",
        "attempt": 1,
        "job_id": "job-placeholder",
        "status": "SUCCEEDED",
    }

    with (
        patch.object(worker, "adapt_be_ai2_processing_request", return_value=(request, adapted)),
        patch.object(worker, "run_idp", run_idp),
        patch.object(worker, "job_result_to_wire", return_value=wire),
    ):
        first = worker._handle_command(command)
        second = worker._handle_command(command)

    assert second == first
    run_idp.assert_called_once()


def test_transient_processing_failure_is_redeliverable():
    command = _command()
    request, adapted = _adapted_request("body")

    with (
        patch.object(worker, "adapt_be_ai2_processing_request", return_value=(request, adapted)),
        patch.object(worker, "run_idp", side_effect=TimeoutError("LLM timeout")),
    ):
        with pytest.raises(worker.RetryableAI2Error):
            worker._handle_command(command)


class _FakeConsumer:
    def __init__(self, message):
        self._messages = [SimpleNamespace(value=message)]
        self.commit_calls = 0
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    def __aiter__(self):
        return self

    async def __anext__(self):
        if self._messages:
            return self._messages.pop(0)
        raise StopAsyncIteration

    async def commit(self):
        self.commit_calls += 1


class _FakeProducer:
    def __init__(self, *, send_error: Exception | None = None):
        self.sent = []
        self.send_error = send_error
        self.started = False
        self.stopped = False

    async def start(self):
        self.started = True

    async def stop(self):
        self.stopped = True

    async def send_and_wait(self, topic, payload, *, key=None):
        if self.send_error is not None:
            raise self.send_error
        self.sent.append((topic, payload, key))


def test_worker_commits_only_after_result_publish():
    async def scenario():
        consumer = _FakeConsumer(_command())
        producer = _FakeProducer()
        result = {"event_type": worker.EVENT_COMPLETED, "payload": {"job_id": "job-1"}}

        with (
            patch.object(worker, "AIOKafkaConsumer", return_value=consumer),
            patch.object(worker, "AIOKafkaProducer", return_value=producer),
            patch.object(worker.asyncio, "to_thread", new=AsyncMock(return_value=result)),
        ):
            await worker.run_worker()

        return consumer, producer

    consumer, producer = asyncio.run(scenario())

    assert len(producer.sent) == 1
    assert consumer.commit_calls == 1
    assert consumer.started and consumer.stopped
    assert producer.started and producer.stopped


def test_worker_does_not_commit_or_publish_after_retryable_failure():
    async def scenario():
        consumer = _FakeConsumer(_command())
        producer = _FakeProducer()

        with (
            patch.object(worker, "AIOKafkaConsumer", return_value=consumer),
            patch.object(worker, "AIOKafkaProducer", return_value=producer),
            patch.object(
                worker.asyncio,
                "to_thread",
                new=AsyncMock(side_effect=worker.RetryableAI2Error("temporary")),
            ),
        ):
            await worker.run_worker()

        return consumer, producer

    consumer, producer = asyncio.run(scenario())

    assert producer.sent == []
    assert consumer.commit_calls == 0
    assert consumer.started and consumer.stopped
    assert producer.started and producer.stopped


def test_worker_does_not_commit_when_result_publish_is_retryable():
    async def scenario():
        consumer = _FakeConsumer(_command())
        producer = _FakeProducer(send_error=TimeoutError("Kafka unavailable"))
        result = {"event_type": worker.EVENT_COMPLETED, "payload": {"job_id": "job-1"}}

        with (
            patch.object(worker, "AIOKafkaConsumer", return_value=consumer),
            patch.object(worker, "AIOKafkaProducer", return_value=producer),
            patch.object(worker.asyncio, "to_thread", new=AsyncMock(return_value=result)),
        ):
            await worker.run_worker()

        return consumer, producer

    consumer, producer = asyncio.run(scenario())

    assert producer.sent == []
    assert consumer.commit_calls == 0
