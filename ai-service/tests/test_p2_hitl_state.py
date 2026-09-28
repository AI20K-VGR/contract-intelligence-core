from __future__ import annotations

from datetime import datetime, timedelta, timezone
from threading import Barrier, Thread

import pytest
from pydantic import ValidationError

from app.reasoning.state_machine import (
    ActorRole,
    CommandType,
    DurableReasoningStateMachine,
    HITLCommand,
    ReasoningState,
    ReasoningStateName,
)


NOW = datetime(2026, 9, 23, 12, 0, tzinfo=timezone.utc)


def make_machine(*, expires_at: datetime | None = None) -> DurableReasoningStateMachine:
    return DurableReasoningStateMachine(
        run_id="run-1",
        tenant_id="tenant-a",
        generation_id="generation-1",
        now=NOW,
        expires_at=expires_at or NOW + timedelta(hours=1),
    )


def command(
    command_type: CommandType,
    *,
    version: int = 0,
    actor_id: str = "reviewer-1",
    actor_role: ActorRole = ActorRole.REVIEWER,
    key: str | None = None,
    generation_id: str = "generation-1",
    tenant_id: str = "tenant-a",
    reason: str | None = None,
    payload: dict | None = None,
) -> HITLCommand:
    return HITLCommand(
        command_id=f"cmd-{key or command_type.value.lower()}-{version}",
        command_type=command_type,
        run_id="run-1",
        generation_id=generation_id,
        tenant_id=tenant_id,
        actor_id=actor_id,
        actor_role=actor_role,
        correlation_id="corr-1",
        idempotency_key=key or f"idem-{command_type.value.lower()}-{version}",
        expected_state_version=version,
        submitted_at=NOW,
        reason=reason,
        payload=payload or {},
    )


def test_transition_matrix_and_no_auto_approve() -> None:
    machine = make_machine()

    assert machine.state.state == ReasoningStateName.CREATED
    assert machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR)).accepted
    assert machine.state.state == ReasoningStateName.RUNNING
    assert machine.dispatch(command(CommandType.REQUEST_CONTEXT, version=1, payload={"question": "missing clause"})).accepted
    assert machine.state.state == ReasoningStateName.WAITING_FOR_HUMAN

    # A waiting run stays waiting until an explicit, authorized approval.
    assert machine.state.state != ReasoningStateName.COMPLETED
    resumed = machine.dispatch(command(CommandType.RESUME, version=2))
    assert resumed.accepted
    assert machine.state.state == ReasoningStateName.RESUMING

    # Approval is also explicit and cannot be inferred from the prior context
    # request; it is no longer legal after an explicit resume command.
    rejected = machine.dispatch(
        command(CommandType.APPROVE, version=3, actor_role=ActorRole.APPROVER, reason="reviewed evidence")
    )
    assert not rejected.accepted
    assert rejected.error_code == "INVALID_TRANSITION"

    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))
    machine.dispatch(command(CommandType.REQUEST_CONTEXT, version=1, payload={"question": "missing clause"}))
    approved = machine.dispatch(
        command(
            CommandType.APPROVE,
            version=2,
            actor_role=ActorRole.APPROVER,
            reason="reviewed evidence",
        )
    )
    assert approved.accepted
    assert machine.state.state == ReasoningStateName.RESUMING
    assert machine.dispatch(command(CommandType.RECOMPUTE, version=3, actor_role=ActorRole.SYSTEM)).accepted
    assert machine.state.state == ReasoningStateName.RECOMPUTING
    assert machine.dispatch(command(CommandType.COMPLETE, version=4, actor_role=ActorRole.SYSTEM)).accepted
    assert machine.state.state == ReasoningStateName.COMPLETED


def test_context_and_edit_commands_require_complete_payload() -> None:
    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))

    incomplete_context = machine.dispatch(command(CommandType.REQUEST_CONTEXT, version=1))
    assert not incomplete_context.accepted
    assert incomplete_context.error_code == "INVALID_CONTEXT"

    machine.dispatch(
        command(
            CommandType.REQUEST_CONTEXT,
            version=1,
            key="context-complete",
            payload={"question": "provide page reference", "context_key": "page_ref"},
        )
    )
    incomplete_edit = machine.dispatch(command(CommandType.EDIT, version=2, payload={}))
    assert not incomplete_edit.accepted
    assert incomplete_edit.error_code == "INVALID_CONTEXT"


def test_stale_version_generation_and_expired_commands_are_deterministic() -> None:
    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))

    stale = machine.dispatch(command(CommandType.REQUEST_CONTEXT, version=0, payload={"question": "q"}))
    assert not stale.accepted
    assert stale.error_code == "STALE_STATE_VERSION"

    stale_generation = machine.dispatch(
        command(CommandType.REQUEST_CONTEXT, version=1, generation_id="generation-old", payload={"question": "q"})
    )
    assert stale_generation.error_code == "STALE_GENERATION"

    expired = make_machine(expires_at=NOW)
    result = expired.dispatch(command(CommandType.START))
    assert not result.accepted
    assert result.error_code == "EXPIRED"
    assert expired.state.state == ReasoningStateName.EXPIRED


def test_idempotent_retry_returns_same_result_and_conflict_is_rejected() -> None:
    machine = make_machine()
    first = machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR, key="same-key"))
    retry = machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR, key="same-key"))

    assert first == retry
    assert machine.state.state_version == 1

    conflict = machine.dispatch(command(CommandType.CANCEL, version=1, key="same-key", reason="different command"))
    assert not conflict.accepted
    assert conflict.error_code == "IDEMPOTENCY_CONFLICT"
    assert machine.state.state == ReasoningStateName.RUNNING


def test_authorization_tenant_and_role_are_enforced() -> None:
    machine = make_machine()
    wrong_tenant = machine.dispatch(command(CommandType.START, tenant_id="tenant-b"))
    assert wrong_tenant.error_code == "UNAUTHORIZED_TENANT"

    wrong_role = machine.dispatch(
        command(CommandType.START, actor_role=ActorRole.REVIEWER, key="start-authority")
    )
    assert wrong_role.error_code == "UNAUTHORIZED_ROLE"

    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR, key="start-ok"))
    machine.dispatch(
        command(
            CommandType.REQUEST_CONTEXT,
            version=1,
            actor_role=ActorRole.REVIEWER,
            payload={"question": "q"},
        )
    )
    not_approver = machine.dispatch(command(CommandType.APPROVE, version=2, actor_role=ActorRole.REVIEWER))
    assert not_approver.error_code == "UNAUTHORIZED_ROLE"


def test_cancel_expire_race_has_one_winner() -> None:
    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))
    barrier = Barrier(3)
    results: list = []

    def submit(item: HITLCommand) -> None:
        barrier.wait()
        results.append(machine.dispatch(item))

    threads = [
        Thread(target=submit, args=(command(CommandType.CANCEL, version=1, actor_role=ActorRole.OPERATOR, key="cancel-race", reason="stop"),)),
        Thread(target=submit, args=(command(CommandType.EXPIRE, version=1, actor_role=ActorRole.SYSTEM, key="expire-race"),)),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sum(result.accepted for result in results) == 1
    assert machine.state.state in {ReasoningStateName.CANCELLED, ReasoningStateName.EXPIRED}
    assert machine.state.state_version == 2


def test_concurrent_approvals_have_one_cas_winner() -> None:
    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))
    machine.dispatch(
        command(
            CommandType.REQUEST_CONTEXT,
            version=1,
            payload={"question": "confirm governing law"},
        )
    )
    barrier = Barrier(3)
    results: list = []

    def submit(item: HITLCommand) -> None:
        barrier.wait()
        results.append(machine.dispatch(item))

    threads = [
        Thread(
            target=submit,
            args=(
                command(
                    CommandType.APPROVE,
                    version=2,
                    actor_id="approver-a",
                    actor_role=ActorRole.APPROVER,
                    key="approval-a",
                    reason="evidence reviewed",
                ),
            ),
        ),
        Thread(
            target=submit,
            args=(
                command(
                    CommandType.APPROVE,
                    version=2,
                    actor_id="approver-b",
                    actor_role=ActorRole.APPROVER,
                    key="approval-b",
                    reason="evidence reviewed independently",
                ),
            ),
        ),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sum(result.accepted for result in results) == 1
    assert sum(result.error_code == "STALE_STATE_VERSION" for result in results) == 1
    assert machine.state.state == ReasoningStateName.RESUMING
    assert machine.state.state_version == 3


def test_timeout_cancel_race_has_one_winner() -> None:
    machine = make_machine()
    machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR))
    barrier = Barrier(3)
    results: list = []

    def submit(item: HITLCommand) -> None:
        barrier.wait()
        results.append(machine.dispatch(item))

    threads = [
        Thread(
            target=submit,
            args=(
                command(
                    CommandType.TIMEOUT,
                    version=1,
                    actor_role=ActorRole.SYSTEM,
                    key="timeout-race",
                ),
            ),
        ),
        Thread(
            target=submit,
            args=(
                command(
                    CommandType.CANCEL,
                    version=1,
                    actor_role=ActorRole.OPERATOR,
                    key="cancel-timeout-race",
                    reason="stop run",
                ),
            ),
        ),
    ]
    for thread in threads:
        thread.start()
    barrier.wait()
    for thread in threads:
        thread.join()

    assert sum(result.accepted for result in results) == 1
    assert machine.state.state in {ReasoningStateName.EXPIRED, ReasoningStateName.CANCELLED}
    assert machine.state.state_version == 2


def test_rejected_command_and_accepted_command_have_audit_contract() -> None:
    machine = make_machine()
    unauthorized = machine.dispatch(
        command(
            CommandType.START,
            actor_id="reviewer-1",
            actor_role=ActorRole.REVIEWER,
            key="unauthorized-start",
        )
    )
    assert not unauthorized.accepted
    assert unauthorized.error_code == "UNAUTHORIZED_ROLE"
    assert set(
        [
            "command_id",
            "command_type",
            "run_id",
            "tenant_id",
            "generation_id",
            "actor_id",
            "actor_role",
            "correlation_id",
            "causation_id",
            "checkpoint_id",
            "idempotency_key",
            "expected_state_version",
            "submitted_at",
            "accepted",
            "error_code",
            "state",
            "state_version",
        ]
    ).issubset(unauthorized.audit)
    assert machine.audit_log[-1]["command_id"] == unauthorized.command_id

    accepted = machine.dispatch(command(CommandType.START, actor_role=ActorRole.OPERATOR, key="audited-start"))
    assert accepted.accepted
    assert accepted.audit["state"] == ReasoningStateName.RUNNING.value
    assert accepted.audit["state_version"] == accepted.state_version
    assert machine.audit_log[-1]["command_id"] == accepted.command_id


def test_command_schema_rejects_missing_contract_fields() -> None:
    with pytest.raises(ValidationError):
        HITLCommand(
            command_id="cmd-1",
            command_type=CommandType.APPROVE,
            run_id="run-1",
            generation_id="generation-1",
            tenant_id="tenant-a",
            actor_id="reviewer-1",
            actor_role=ActorRole.REVIEWER,
            correlation_id="corr-1",
            idempotency_key="idem-1",
            expected_state_version=-1,
            submitted_at=NOW,
        )


def test_state_is_serializable_without_raw_user_context() -> None:
    machine = make_machine()
    snapshot = machine.snapshot()
    assert snapshot["state"] == "CREATED"
    assert snapshot["state_version"] == 0
    assert "user_context" not in snapshot
    assert ReasoningState.model_validate(snapshot).run_id == "run-1"
