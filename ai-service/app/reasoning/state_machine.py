"""Durable-domain reasoning lifecycle and HITL command validation.

This module is deliberately storage-agnostic.  It owns the invariants that a
future database/event-store adapter must preserve: serialized state versions,
generation fencing, tenant/role authorization, command idempotency and an
atomic compare-and-set boundary.  It does not execute pipeline work or infer a
reviewer's decision from model output.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from enum import Enum
from threading import RLock
from typing import Any, ClassVar, Mapping

from pydantic import BaseModel, ConfigDict, Field, field_validator


class ReasoningStateName(str, Enum):
    CREATED = "CREATED"
    RUNNING = "RUNNING"
    WAITING_FOR_HUMAN = "WAITING_FOR_HUMAN"
    RESUMING = "RESUMING"
    RECOMPUTING = "RECOMPUTING"
    COMPLETED = "COMPLETED"
    FAILED = "FAILED"
    CANCELLED = "CANCELLED"
    EXPIRED = "EXPIRED"


class CommandType(str, Enum):
    START = "START"
    REQUEST_CONTEXT = "REQUEST_CONTEXT"
    APPROVE = "APPROVE"
    REJECT = "REJECT"
    EDIT = "EDIT"
    CONFIRM_IMPACT = "CONFIRM_IMPACT"
    RESUME = "RESUME"
    RECOMPUTE = "RECOMPUTE"
    COMPLETE = "COMPLETE"
    FAIL = "FAIL"
    CANCEL = "CANCEL"
    TIMEOUT = "TIMEOUT"
    EXPIRE = "EXPIRE"


class ActorRole(str, Enum):
    OWNER = "owner"
    REVIEWER = "reviewer"
    APPROVER = "approver"
    OPERATOR = "operator"
    SYSTEM = "system"
    ADMIN = "admin"


class ReasoningState(BaseModel):
    """Serializable state snapshot used as the CAS value for one run."""

    model_config = ConfigDict(extra="forbid")

    run_id: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    generation_id: str = Field(min_length=1, max_length=160)
    state: ReasoningStateName = ReasoningStateName.CREATED
    state_version: int = Field(default=0, ge=0)
    created_at: datetime
    updated_at: datetime
    expires_at: datetime | None = None
    pending_context: dict[str, Any] | None = None
    last_command_id: str | None = None

    @field_validator("created_at", "updated_at", "expires_at")
    @classmethod
    def require_aware_datetime(cls, value: datetime | None) -> datetime | None:
        if value is not None and value.tzinfo is None:
            raise ValueError("timestamps must include a timezone")
        return value


class HITLCommand(BaseModel):
    """Validated command envelope crossing the HITL/domain boundary."""

    model_config = ConfigDict(extra="forbid")

    command_id: str = Field(min_length=1, max_length=160)
    command_type: CommandType
    run_id: str = Field(min_length=1, max_length=160)
    checkpoint_id: str | None = Field(default=None, max_length=160)
    generation_id: str = Field(min_length=1, max_length=160)
    tenant_id: str = Field(min_length=1, max_length=160)
    actor_id: str = Field(min_length=1, max_length=160)
    actor_role: ActorRole
    correlation_id: str = Field(min_length=1, max_length=160)
    causation_id: str | None = Field(default=None, max_length=160)
    idempotency_key: str = Field(min_length=1, max_length=200)
    expected_state_version: int = Field(ge=0)
    submitted_at: datetime
    reason: str | None = Field(default=None, max_length=4000)
    payload: dict[str, Any] = Field(default_factory=dict)

    @field_validator("command_type", mode="before")
    @classmethod
    def normalize_command_type(cls, value: CommandType | str) -> CommandType | str:
        return value.upper() if isinstance(value, str) else value

    @field_validator("actor_role", mode="before")
    @classmethod
    def normalize_actor_role(cls, value: ActorRole | str) -> ActorRole | str:
        return value.lower() if isinstance(value, str) else value

    @field_validator("submitted_at")
    @classmethod
    def require_aware_submitted_at(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("submitted_at must include a timezone")
        return value


class CommandResult(BaseModel):
    """Stable, audit-ready result returned for both first calls and retries."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    accepted: bool
    command_id: str
    command_type: CommandType
    run_id: str
    tenant_id: str
    generation_id: str
    actor_id: str
    actor_role: ActorRole
    correlation_id: str
    idempotency_key: str
    state: ReasoningStateName
    state_version: int
    submitted_at: datetime
    reason: str | None = None
    error_code: str | None = None
    audit: dict[str, Any] = Field(default_factory=dict)


class DurableReasoningStateMachine:
    """Atomic in-process reducer with durable-friendly command receipts.

    The lock and receipt map model the transaction boundary.  A later adapter
    can replace them with a database transaction and a unique
    ``(run_id, idempotency_key)`` constraint without changing the command
    contract or transition rules.
    """

    _TERMINAL: ClassVar[frozenset[ReasoningStateName]] = frozenset(
        {
            ReasoningStateName.COMPLETED,
            ReasoningStateName.FAILED,
            ReasoningStateName.CANCELLED,
            ReasoningStateName.EXPIRED,
        }
    )
    _TRANSITIONS: ClassVar[dict[ReasoningStateName, dict[CommandType, ReasoningStateName]]] = {
        ReasoningStateName.CREATED: {
            CommandType.START: ReasoningStateName.RUNNING,
            CommandType.CANCEL: ReasoningStateName.CANCELLED,
            CommandType.EXPIRE: ReasoningStateName.EXPIRED,
            CommandType.TIMEOUT: ReasoningStateName.EXPIRED,
        },
        ReasoningStateName.RUNNING: {
            CommandType.REQUEST_CONTEXT: ReasoningStateName.WAITING_FOR_HUMAN,
            CommandType.COMPLETE: ReasoningStateName.COMPLETED,
            CommandType.FAIL: ReasoningStateName.FAILED,
            CommandType.CANCEL: ReasoningStateName.CANCELLED,
            CommandType.EXPIRE: ReasoningStateName.EXPIRED,
            CommandType.TIMEOUT: ReasoningStateName.EXPIRED,
        },
        ReasoningStateName.WAITING_FOR_HUMAN: {
            CommandType.REQUEST_CONTEXT: ReasoningStateName.WAITING_FOR_HUMAN,
            CommandType.APPROVE: ReasoningStateName.RESUMING,
            CommandType.REJECT: ReasoningStateName.RESUMING,
            CommandType.EDIT: ReasoningStateName.RESUMING,
            CommandType.CONFIRM_IMPACT: ReasoningStateName.RESUMING,
            CommandType.RESUME: ReasoningStateName.RESUMING,
            CommandType.CANCEL: ReasoningStateName.CANCELLED,
            CommandType.EXPIRE: ReasoningStateName.EXPIRED,
            CommandType.TIMEOUT: ReasoningStateName.EXPIRED,
        },
        ReasoningStateName.RESUMING: {
            CommandType.RECOMPUTE: ReasoningStateName.RECOMPUTING,
            CommandType.FAIL: ReasoningStateName.FAILED,
            CommandType.CANCEL: ReasoningStateName.CANCELLED,
            CommandType.EXPIRE: ReasoningStateName.EXPIRED,
            CommandType.TIMEOUT: ReasoningStateName.EXPIRED,
        },
        ReasoningStateName.RECOMPUTING: {
            CommandType.START: ReasoningStateName.RUNNING,
            CommandType.REQUEST_CONTEXT: ReasoningStateName.WAITING_FOR_HUMAN,
            CommandType.COMPLETE: ReasoningStateName.COMPLETED,
            CommandType.FAIL: ReasoningStateName.FAILED,
            CommandType.CANCEL: ReasoningStateName.CANCELLED,
            CommandType.EXPIRE: ReasoningStateName.EXPIRED,
            CommandType.TIMEOUT: ReasoningStateName.EXPIRED,
        },
    }
    _ROLE_POLICY: ClassVar[dict[CommandType, frozenset[ActorRole]]] = {
        CommandType.START: frozenset({ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.REQUEST_CONTEXT: frozenset(
            {ActorRole.OWNER, ActorRole.REVIEWER, ActorRole.APPROVER, ActorRole.OPERATOR, ActorRole.ADMIN}
        ),
        CommandType.APPROVE: frozenset({ActorRole.APPROVER, ActorRole.ADMIN}),
        CommandType.REJECT: frozenset({ActorRole.REVIEWER, ActorRole.APPROVER, ActorRole.ADMIN}),
        CommandType.EDIT: frozenset({ActorRole.REVIEWER, ActorRole.APPROVER, ActorRole.ADMIN}),
        CommandType.CONFIRM_IMPACT: frozenset({ActorRole.APPROVER, ActorRole.ADMIN}),
        CommandType.RESUME: frozenset({ActorRole.REVIEWER, ActorRole.APPROVER, ActorRole.OPERATOR, ActorRole.ADMIN}),
        CommandType.RECOMPUTE: frozenset({ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.COMPLETE: frozenset({ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.FAIL: frozenset({ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.CANCEL: frozenset({ActorRole.OWNER, ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.TIMEOUT: frozenset({ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
        CommandType.EXPIRE: frozenset({ActorRole.OPERATOR, ActorRole.SYSTEM, ActorRole.ADMIN}),
    }

    def __init__(
        self,
        *,
        run_id: str,
        tenant_id: str,
        generation_id: str,
        now: datetime | None = None,
        expires_at: datetime | None = None,
    ) -> None:
        current = now or datetime.now(timezone.utc)
        if current.tzinfo is None:
            raise ValueError("now must include a timezone")
        if expires_at is not None and expires_at.tzinfo is None:
            raise ValueError("expires_at must include a timezone")
        self.state = ReasoningState(
            run_id=run_id,
            tenant_id=tenant_id,
            generation_id=generation_id,
            created_at=current,
            updated_at=current,
            expires_at=expires_at,
        )
        self._receipts: dict[str, tuple[str, CommandResult]] = {}
        self._audit: list[dict[str, Any]] = []
        self._lock = RLock()

    @property
    def audit_log(self) -> tuple[dict[str, Any], ...]:
        with self._lock:
            return tuple(dict(item) for item in self._audit)

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self.state.model_dump(mode="json")

    def expire(self, *, now: datetime) -> ReasoningState:
        """Apply a scheduler timeout atomically; never approves a run."""

        with self._lock:
            self._expire_if_due(now)
            return self.state.model_copy(deep=True)

    def dispatch(self, command: HITLCommand, *, now: datetime | None = None) -> CommandResult:
        """Validate and atomically apply one command or return a stable error."""

        with self._lock:
            fingerprint = self._fingerprint(command)
            prior = self._receipts.get(command.idempotency_key)
            if prior is not None:
                prior_fingerprint, prior_result = prior
                if prior_fingerprint == fingerprint:
                    return prior_result
                return self._result(command, accepted=False, error_code="IDEMPOTENCY_CONFLICT")

            event_time = now or command.submitted_at
            self._expire_if_due(event_time)
            error_code = self._validate(command)
            if error_code is not None:
                self._audit.append(self._audit_entry(command, accepted=False, error_code=error_code))
                result = self._result(command, accepted=False, error_code=error_code)
                self._receipts[command.idempotency_key] = (fingerprint, result)
                return result

            next_state = self._TRANSITIONS[self.state.state][command.command_type]
            self.state = self.state.model_copy(
                update={
                    "state": next_state,
                    "state_version": self.state.state_version + 1,
                    "updated_at": event_time,
                    "last_command_id": command.command_id,
                    "pending_context": (
                        dict(command.payload)
                        if command.command_type == CommandType.REQUEST_CONTEXT
                        else None
                    ),
                }
            )
            audit = self._audit_entry(command, accepted=True, error_code=None)
            self._audit.append(audit)
            result = self._result(command, accepted=True, error_code=None)
            self._receipts[command.idempotency_key] = (fingerprint, result)
            return result

    def _validate(self, command: HITLCommand) -> str | None:
        if command.run_id != self.state.run_id:
            return "RUN_MISMATCH"
        if command.tenant_id != self.state.tenant_id:
            return "UNAUTHORIZED_TENANT"
        if command.generation_id != self.state.generation_id:
            return "STALE_GENERATION"
        if self.state.state == ReasoningStateName.EXPIRED:
            return "EXPIRED"
        if command.actor_role not in self._ROLE_POLICY[command.command_type]:
            return "UNAUTHORIZED_ROLE"
        if command.expected_state_version != self.state.state_version:
            return "STALE_STATE_VERSION"
        if command.command_type not in self._TRANSITIONS.get(self.state.state, {}):
            return "INVALID_TRANSITION"
        return self._validate_payload(command)

    @staticmethod
    def _validate_payload(command: HITLCommand) -> str | None:
        payload = command.payload
        if command.command_type == CommandType.REQUEST_CONTEXT:
            question = payload.get("question")
            if not isinstance(question, str) or not question.strip():
                return "INVALID_CONTEXT"
        elif command.command_type == CommandType.EDIT:
            edits = payload.get("edits", payload.get("changes"))
            if not isinstance(edits, (dict, list)) or not edits:
                return "INVALID_CONTEXT"
        elif command.command_type == CommandType.CONFIRM_IMPACT:
            if payload.get("confirmed") is not True or not str(payload.get("impact_id", "")).strip():
                return "INVALID_CONTEXT"
        elif command.command_type in {CommandType.REJECT, CommandType.CANCEL}:
            if not command.reason or not command.reason.strip():
                return "INVALID_CONTEXT"
        return None

    def _expire_if_due(self, now: datetime) -> None:
        if now.tzinfo is None:
            raise ValueError("now must include a timezone")
        if (
            self.state.expires_at is not None
            and now >= self.state.expires_at
            and self.state.state not in self._TERMINAL
        ):
            self.state = self.state.model_copy(
                update={
                    "state": ReasoningStateName.EXPIRED,
                    "state_version": self.state.state_version + 1,
                    "updated_at": now,
                }
            )
            self._audit.append(
                {
                    "event": "EXPIRED",
                    "run_id": self.state.run_id,
                    "tenant_id": self.state.tenant_id,
                    "state_version": self.state.state_version,
                    "occurred_at": now.isoformat(),
                }
            )

    def _result(self, command: HITLCommand, *, accepted: bool, error_code: str | None) -> CommandResult:
        return CommandResult(
            accepted=accepted,
            command_id=command.command_id,
            command_type=command.command_type,
            run_id=command.run_id,
            tenant_id=command.tenant_id,
            generation_id=command.generation_id,
            actor_id=command.actor_id,
            actor_role=command.actor_role,
            correlation_id=command.correlation_id,
            idempotency_key=command.idempotency_key,
            state=self.state.state,
            state_version=self.state.state_version,
            submitted_at=command.submitted_at,
            reason=command.reason,
            error_code=error_code,
            audit=self._audit_entry(command, accepted=accepted, error_code=error_code),
        )

    def _audit_entry(self, command: HITLCommand, *, accepted: bool, error_code: str | None) -> dict[str, Any]:
        return {
            "command_id": command.command_id,
            "command_type": command.command_type.value,
            "run_id": command.run_id,
            "tenant_id": command.tenant_id,
            "generation_id": command.generation_id,
            "actor_id": command.actor_id,
            "actor_role": command.actor_role.value,
            "correlation_id": command.correlation_id,
            "causation_id": command.causation_id,
            "checkpoint_id": command.checkpoint_id,
            "idempotency_key": command.idempotency_key,
            "expected_state_version": command.expected_state_version,
            "submitted_at": command.submitted_at.isoformat(),
            "reason": command.reason,
            "accepted": accepted,
            "error_code": error_code,
            "state": self.state.state.value,
            "state_version": self.state.state_version,
        }

    @staticmethod
    def _fingerprint(command: HITLCommand) -> str:
        data = command.model_dump(mode="json", exclude={"command_id", "submitted_at"})
        return json.dumps(data, sort_keys=True, separators=(",", ":"))


# Compatibility-friendly names for callers that describe the same domain
# object as a reducer or a state/command module.
ReasoningStateMachine = DurableReasoningStateMachine
StateReducer = DurableReasoningStateMachine
Command = HITLCommand
HITLCommandType = CommandType


__all__ = [
    "ActorRole",
    "Command",
    "CommandResult",
    "CommandType",
    "DurableReasoningStateMachine",
    "HITLCommand",
    "HITLCommandType",
    "ReasoningState",
    "ReasoningStateMachine",
    "ReasoningStateName",
    "StateReducer",
]
