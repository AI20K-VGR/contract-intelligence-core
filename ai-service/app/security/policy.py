"""Fail-closed authorization and observability primitives for the P5 boundary.

The module intentionally has no application or third-party dependencies.  It
does not execute prompts, tools, or HITL commands; it only returns decisions
and safe-to-log metadata for a caller that owns execution.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import math
import re
import secrets
import time
from collections.abc import Callable, Mapping, Sequence
from dataclasses import dataclass, field
from threading import RLock
from typing import Any


ROLES = frozenset({"reviewer", "owner", "admin", "read_only"})
ACTIONS = frozenset({"snapshot.read", "replay.read", "stream.read", "hitl.command"})

ROLE_ACTIONS = {
    "reviewer": frozenset(ACTIONS),
    "owner": frozenset(ACTIONS),
    "admin": frozenset(ACTIONS),
    "read_only": frozenset({"snapshot.read", "replay.read", "stream.read"}),
}

_SENSITIVE_KEY_PARTS = (
    "raw_contract",
    "hidden_reasoning",
    "prompt",
    "secret",
    "token",
)
_INJECTION_PATTERNS = (
    ("instruction_override", re.compile(r"ignore\s+(all\s+)?previous|disregard\s+instructions", re.I)),
    ("role_impersonation", re.compile(r"system\s+message|developer\s+message", re.I)),
    ("secret_exfiltration", re.compile(r"reveal|print|dump|show\s+.*(secret|token|prompt)", re.I)),
)


_PRINCIPAL_SECRET = secrets.token_bytes(32)
_APPROVAL_SECRET = secrets.token_bytes(32)
_APPROVAL_CONSUMED: set[str] = set()
_APPROVAL_LOCK = RLock()


def _normalise(value: Any) -> str:
    canonical = _canonical_string(value, allow_empty=True)
    return canonical.lower() if canonical is not None else ""


def _nonempty_string(value: Any) -> bool:
    return _canonical_string(value) is not None


def _canonical_string(value: Any, *, allow_empty: bool = False) -> str | None:
    """Return a plain, caller-independent string for a boundary field."""

    if not isinstance(value, str):
        return None
    canonical = str.strip(value)
    if not allow_empty and not canonical:
        return None
    return canonical


def _is_sensitive_key(key: Any) -> bool:
    if type(key) is not str:
        return False
    normalised = _normalise(str.casefold(key)).replace("-", "_")
    return any(part in normalised for part in _SENSITIVE_KEY_PARTS)


def redact(value: Any, *, max_string_length: int = 256) -> Any:
    """Return a recursively redacted, bounded copy suitable for audit data."""

    if max_string_length < 0:
        raise ValueError("max_string_length must be non-negative")
    if isinstance(value, str):
        if len(value) <= max_string_length:
            return value
        if max_string_length <= 3:
            return value[:max_string_length]
        return value[: max_string_length - 3] + "..."
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        try:
            for key, item in value.items():
                if type(key) is not str:
                    continue
                safe[key] = "[REDACTED]" if _is_sensitive_key(key) else redact(
                    item, max_string_length=max_string_length
                )
        except Exception:
            return safe
        return safe
    if isinstance(value, Sequence) and not isinstance(value, (bytes, bytearray, str)):
        return [redact(item, max_string_length=max_string_length) for item in value]
    if isinstance(value, (bytes, bytearray)):
        return "[REDACTED_BYTES]"
    return value


redact_for_audit = redact


@dataclass(frozen=True)
class AuthzRequest:
    actor_id: str
    tenant_id: str
    dossier_id: str
    role: str
    action: str
    correlation_id: str
    idempotency_key: str
    payload: Mapping[str, Any] | None = None
    principal: "Principal | None" = None


class Principal:
    """Opaque principal issued by the trusted authentication boundary.

    Direct construction is intentionally denied.  ``issue_trusted_principal``
    is a prototype seam for the authenticated service boundary; production
    integration must replace it with the service's verified identity issuer.
    """

    __slots__ = ("_actor_id", "_tenant_id", "_role", "_proof")

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("Principal is immutable")

    def __new__(cls, *args: Any, **kwargs: Any) -> "Principal":
        raise AuthorizationError("UNTRUSTED_PRINCIPAL", "principal must be issued by the trusted boundary")

    @property
    def actor_id(self) -> str:
        return self._actor_id

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def role(self) -> str:
        return self._role

    def __repr__(self) -> str:
        return f"Principal(actor_id={self.actor_id!r}, tenant_id={self.tenant_id!r}, role={self.role!r})"


def _principal_proof(actor_id: str, tenant_id: str, role: str) -> str:
    payload = "\x1f".join((actor_id, tenant_id, role)).encode("utf-8")
    return hmac.new(_PRINCIPAL_SECRET, payload, hashlib.sha256).hexdigest()


def issue_trusted_principal(*, actor_id: Any, tenant_id: Any, role: Any) -> Principal:
    """Issue a validated principal at the prototype trust boundary."""

    canonical_actor = _canonical_string(actor_id)
    canonical_tenant = _canonical_string(tenant_id)
    canonical_role = _canonical_string(role)
    if canonical_actor is None or canonical_tenant is None or canonical_role is None:
        raise AuthorizationError("INVALID_PRINCIPAL", "principal identity fields must be non-empty strings")
    normalised_role = canonical_role.lower()
    if normalised_role not in ROLES:
        raise AuthorizationError("UNKNOWN_ROLE", "role is not recognized")
    principal = object.__new__(Principal)
    object.__setattr__(principal, "_actor_id", canonical_actor)
    object.__setattr__(principal, "_tenant_id", canonical_tenant)
    object.__setattr__(principal, "_role", normalised_role)
    object.__setattr__(principal, "_proof", _principal_proof(principal.actor_id, principal.tenant_id, principal.role))
    return principal


def _is_trusted_principal(value: Any) -> bool:
    try:
        return (
            isinstance(value, Principal)
            and type(value.actor_id) is str
            and type(value.tenant_id) is str
            and type(value.role) is str
            and _nonempty_string(value.actor_id)
            and _nonempty_string(value.tenant_id)
            and _normalise(value.role) in ROLES
            and hmac.compare_digest(value._proof, _principal_proof(value.actor_id, value.tenant_id, _normalise(value.role)))
        )
    except (AttributeError, TypeError):
        return False


is_trusted_principal = _is_trusted_principal


class ApprovalGrant:
    """Opaque one-time approval capability issued by a trusted store.

    The consumed registry is process-local and non-durable.  A production
    approval issuer must persist issuance, expiry, and consumption atomically.
    """

    __slots__ = (
        "_approval_id", "_tenant_id", "_dossier_id", "_actor_id", "_tool_name",
        "_command_digest", "_issuer", "_expires_at", "_nonce", "_proof",
    )

    def __setattr__(self, name: str, value: Any) -> None:
        raise AttributeError("ApprovalGrant is immutable")

    def __new__(cls, *args: Any, **kwargs: Any) -> "ApprovalGrant":
        raise AuthorizationError("UNTRUSTED_APPROVAL_GRANT", "approval must be issued by a trusted approval boundary")

    @property
    def approval_id(self) -> str:
        return self._approval_id

    @property
    def tenant_id(self) -> str:
        return self._tenant_id

    @property
    def dossier_id(self) -> str:
        return self._dossier_id

    @property
    def actor_id(self) -> str:
        return self._actor_id

    @property
    def tool_name(self) -> str:
        return self._tool_name

    @property
    def command_digest(self) -> str:
        return self._command_digest

    @property
    def issuer(self) -> str:
        return self._issuer

    @property
    def expires_at(self) -> float:
        return self._expires_at

    @property
    def nonce(self) -> str:
        return self._nonce

    @property
    def proof(self) -> str:
        return self._proof


def _canonical_command(tool_name: Any, command: Any) -> bytes | None:
    if not _nonempty_string(tool_name) or command is None:
        return None
    try:
        return json.dumps(
            {"tool_name": _normalise(tool_name), "command": command},
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError):
        return None


def _command_digest_for(tool_name: Any, command: Any) -> str | None:
    canonical = _canonical_command(tool_name, command)
    return hashlib.sha256(canonical).hexdigest() if canonical is not None else None


def _approval_proof(grant: Mapping[str, Any]) -> str:
    encoded = json.dumps(dict(grant), sort_keys=True, separators=(",", ":")).encode("utf-8")
    return hmac.new(_APPROVAL_SECRET, encoded, hashlib.sha256).hexdigest()


def issue_approval_grant(
    *,
    approval_id: Any,
    tenant_id: Any,
    dossier_id: Any,
    actor_id: Any,
    tool_name: Any,
    command: Any,
    issuer: Any,
    ttl_seconds: float = 300.0,
) -> ApprovalGrant:
    """Issue a signed, expiring capability for the exact command input."""

    canonical_fields = tuple(
        _canonical_string(value)
        for value in (approval_id, tenant_id, dossier_id, actor_id, tool_name, issuer)
    )
    if any(value is None for value in canonical_fields):
        raise AuthorizationError("INVALID_APPROVAL", "approval fields must be non-empty strings")
    if type(ttl_seconds) not in (int, float):
        raise AuthorizationError("INVALID_APPROVAL", "approval TTL must be a non-negative number")
    try:
        canonical_ttl = float(ttl_seconds)
    except (OverflowError, ValueError):
        canonical_ttl = math.inf
    if not math.isfinite(canonical_ttl) or canonical_ttl < 0:
        raise AuthorizationError("INVALID_APPROVAL", "approval TTL must be a non-negative number")
    digest = _command_digest_for(tool_name, command)
    if digest is None:
        raise AuthorizationError("INVALID_APPROVAL_COMMAND", "approval requires a JSON-serializable command")
    now = time.time()
    nonce = secrets.token_urlsafe(24)
    approval_id_value, tenant_value, dossier_value, actor_value, tool_value, issuer_value = canonical_fields
    fields = {
        "approval_id": approval_id_value,
        "tenant_id": tenant_value,
        "dossier_id": dossier_value,
        "actor_id": actor_value,
        "tool_name": tool_value.lower(),
        "command_digest": digest,
        "issuer": issuer_value,
        "expires_at": now + canonical_ttl,
        "nonce": nonce,
    }
    grant = object.__new__(ApprovalGrant)
    for name, value in fields.items():
        object.__setattr__(grant, f"_{name}", value)
    object.__setattr__(grant, "_proof", _approval_proof(fields))
    return grant


def _valid_approval_grant(grant: ApprovalGrant) -> bool:
    try:
        fields = {
            "approval_id": grant.approval_id,
            "tenant_id": grant.tenant_id,
            "dossier_id": grant.dossier_id,
            "actor_id": grant.actor_id,
            "tool_name": grant.tool_name,
            "command_digest": grant.command_digest,
            "issuer": grant.issuer,
            "expires_at": grant.expires_at,
            "nonce": grant.nonce,
        }
        if any(type(fields[name]) is not str for name in ("approval_id", "tenant_id", "dossier_id", "actor_id", "tool_name", "command_digest", "issuer", "nonce")):
            return False
        return hmac.compare_digest(grant.proof, _approval_proof(fields))
    except (AttributeError, TypeError):
        return False


def _consume_approval(grant: ApprovalGrant) -> str | None:
    with _APPROVAL_LOCK:
        if time.time() >= grant.expires_at:
            return "APPROVAL_EXPIRED"
        if grant.nonce in _APPROVAL_CONSUMED:
            return "APPROVAL_REPLAY"
        _APPROVAL_CONSUMED.add(grant.nonce)
        return None


@dataclass(frozen=True)
class ResourceScope:
    tenant_id: str
    dossier_id: str


@dataclass(frozen=True)
class RequestContext:
    principal: Principal
    resource: ResourceScope
    action: str
    correlation_id: str
    idempotency_key: str
    role: str | None = None

    def __post_init__(self) -> None:
        if self.role is None:
            object.__setattr__(self, "role", self.principal.role)


class AuthorizationError(ValueError):
    """Raised when a public security context or command contract is invalid."""

    def __init__(self, code: str, reason: str | None = None) -> None:
        self.code = code
        self.reason = reason or code
        super().__init__(self.reason)


def validate_request_context(
    context: RequestContext,
    *,
    expected_scope: ResourceScope | None = None,
) -> RequestContext:
    """Validate a request context and return the unchanged context when valid."""

    if not _is_trusted_principal(context.principal):
        raise AuthorizationError("UNTRUSTED_PRINCIPAL", "trusted principal binding is required")
    tenant = _canonical_string(context.resource.tenant_id)
    dossier = _canonical_string(context.resource.dossier_id)
    correlation = _canonical_string(context.correlation_id)
    action = _canonical_string(context.action, allow_empty=True)
    idempotency_key = _canonical_string(context.idempotency_key, allow_empty=True)
    role = _canonical_string(context.role, allow_empty=True) if context.role is not None else None
    if tenant is None or dossier is None:
        raise AuthorizationError("MISSING_SCOPE", "tenant and dossier are required")
    if correlation is None or action is None or idempotency_key is None:
        raise AuthorizationError("INVALID_CONTEXT", "actor and correlation are required")
    normalised_context = RequestContext(
        principal=context.principal,
        resource=ResourceScope(tenant_id=tenant, dossier_id=dossier),
        action=action,
        correlation_id=correlation,
        idempotency_key=idempotency_key,
        role=role,
    )
    expected_tenant = _canonical_string(expected_scope.tenant_id) if expected_scope is not None else None
    expected_dossier = _canonical_string(expected_scope.dossier_id) if expected_scope is not None else None
    if expected_scope is not None and (expected_tenant is None or expected_dossier is None):
        raise AuthorizationError("MISSING_SCOPE", "tenant and dossier are required")
    if context.principal.tenant_id != tenant:
        raise AuthorizationError("CROSS_TENANT", "principal and resource tenants differ")
    if expected_tenant is not None and tenant != expected_tenant:
        raise AuthorizationError("CROSS_TENANT", "request is outside the tenant scope")
    if expected_dossier is not None and dossier != expected_dossier:
        raise AuthorizationError("CROSS_DOSSIER", "request is outside the dossier scope")

    normalised_role = _normalise(normalised_context.role or "")
    normalised_action = _normalise(normalised_context.action)
    if normalised_role not in ROLES:
        raise AuthorizationError("UNKNOWN_ROLE", "role is not recognized")
    if normalised_role != _normalise(context.principal.role):
        raise AuthorizationError("ROLE_MISMATCH", "request role differs from principal role")
    if normalised_action not in ACTIONS:
        raise AuthorizationError("UNKNOWN_ACTION", "action is not recognized")
    if normalised_action not in ROLE_ACTIONS[normalised_role]:
        raise AuthorizationError("ROLE_NOT_ALLOWED", "role is not allowed for action")
    if normalised_action == "hitl.command" and not idempotency_key:
        raise AuthorizationError("IDEMPOTENCY_KEY_REQUIRED", "command key is required")
    return normalised_context


class CommandLedger:
    """Thread-safe idempotency ledger for command results."""

    def __init__(self) -> None:
        self._records: dict[tuple[str, str, str], tuple[str, Any]] = {}
        self._lock = RLock()

    def get_or_record(
        self,
        *,
        tenant_id: str,
        dossier_id: str,
        idempotency_key: str,
        command_digest: str,
        result_factory: Callable[[], Any],
    ) -> tuple[Any, bool]:
        canonical_key = tuple(_canonical_string(value) for value in (tenant_id, dossier_id, idempotency_key))
        if any(value is None for value in canonical_key):
            raise AuthorizationError("INVALID_CONTEXT", "ledger identity fields must be non-empty strings")
        key = (canonical_key[0], canonical_key[1], canonical_key[2])
        with self._lock:
            prior = self._records.get(key)
            if prior is not None:
                prior_digest, result = prior
                if prior_digest != command_digest:
                    raise AuthorizationError(
                        "IDEMPOTENCY_CONFLICT",
                        "idempotency key was reused for a different command",
                    )
                return result, True
            result = result_factory()
            self._records[key] = (command_digest, result)
            return result, False


class AuditLog:
    """In-memory sink for bounded, redacted audit events."""

    def __init__(self) -> None:
        self.events: list[dict[str, Any]] = []

    def append(self, event: Mapping[str, Any]) -> dict[str, Any]:
        safe_event = redact(event)
        self.events.append(safe_event)
        return safe_event


@dataclass(frozen=True)
class PromptInput:
    content: str


@dataclass(frozen=True)
class AuthorizationDecision:
    allowed: bool
    code: str
    reason: str
    actor_id: str
    tenant_id: str
    dossier_id: str
    correlation_id: str
    action: str
    outcome: str
    audit_event: Mapping[str, Any]
    cached: bool = False

    def __bool__(self) -> bool:
        return self.allowed

    @property
    def audit(self) -> Mapping[str, Any]:
        return self.audit_event


def build_audit_event(
    request: AuthzRequest,
    *,
    outcome: str,
    details: Mapping[str, Any] | None = None,
    code: str | None = None,
    max_string_length: int = 256,
) -> dict[str, Any]:
    """Build the minimum correlation fields plus recursively safe details."""

    event: dict[str, Any] = {
        "event_type": "security.authorization",
        "actor_id": _canonical_string(request.actor_id, allow_empty=True) or "",
        "tenant_id": _canonical_string(request.tenant_id, allow_empty=True) or "",
        "dossier_id": _canonical_string(request.dossier_id, allow_empty=True) or "",
        "correlation_id": _canonical_string(request.correlation_id, allow_empty=True) or "",
        "action": _canonical_string(request.action, allow_empty=True) or "",
        "outcome": outcome,
        "details": redact(details or {}, max_string_length=max_string_length),
    }
    if code is not None:
        event["code"] = code
    return event


def _command_digest(request: AuthzRequest) -> str:
    command = {
        "action": _normalise(request.action),
        "payload": request.payload or {},
    }
    encoded = json.dumps(command, ensure_ascii=False, sort_keys=True, separators=(",", ":"), default=repr)
    return hashlib.sha256(encoded.encode("utf-8")).hexdigest()


_AUTHZ_IDENTITY_FIELDS = (
    "actor_id",
    "tenant_id",
    "dossier_id",
    "role",
    "action",
    "correlation_id",
    "idempotency_key",
)


def _canonical_authz_request(value: Any) -> tuple[AuthzRequest, bool]:
    """Project public request fields to plain strings before any policy logic."""

    valid = isinstance(value, AuthzRequest)
    fields: dict[str, str] = {}
    for name in _AUTHZ_IDENTITY_FIELDS:
        try:
            canonical = _canonical_string(getattr(value, name), allow_empty=True)
        except Exception:
            canonical = None
        if canonical is None:
            valid = False
            canonical = ""
        fields[name] = canonical
    try:
        payload = value.payload if value.payload is None or isinstance(value.payload, Mapping) else None
        if value.payload is not None and not isinstance(value.payload, Mapping):
            valid = False
        principal = value.principal
    except Exception:
        payload = None
        principal = None
    return AuthzRequest(**fields, payload=payload, principal=principal), valid


class SecurityPolicy:
    """Deny-by-default policy for one optional tenant/dossier resource scope."""

    def __init__(
        self,
        *,
        tenant_id: str | None = None,
        dossier_id: str | None = None,
        approved_tools: Sequence[str] = (),
    ) -> None:
        if tenant_id is not None and _canonical_string(tenant_id) is None:
            raise AuthorizationError("INVALID_SCOPE", "tenant scope must be a non-empty string")
        if dossier_id is not None and _canonical_string(dossier_id) is None:
            raise AuthorizationError("INVALID_SCOPE", "dossier scope must be a non-empty string")
        self._tenant_id = _canonical_string(tenant_id) if tenant_id is not None else None
        self._dossier_id = _canonical_string(dossier_id) if dossier_id is not None else None
        self.tool_policy = ToolPolicy(approved_tools=approved_tools)
        self._idempotency: dict[tuple[str, str, str, str], tuple[str, AuthorizationDecision]] = {}
        self._lock = RLock()

    def authorize(
        self,
        request: AuthzRequest,
        *,
        tenant_id: str | None = None,
        dossier_id: str | None = None,
    ) -> AuthorizationDecision:
        """Authorize one request and return an audit-ready stable decision."""

        request, request_valid = _canonical_authz_request(request)
        expected_tenant = self._tenant_id
        expected_dossier = self._dossier_id
        role = _normalise(request.role)
        action = _normalise(request.action)

        with self._lock:
            if not request_valid:
                return self._decision(request, False, "INVALID_CONTEXT", "authorization identity fields are invalid")
            if not _nonempty_string(request.actor_id) or not _nonempty_string(request.correlation_id):
                return self._decision(request, False, "INVALID_CONTEXT", "actor and correlation are required")
            if not _nonempty_string(request.tenant_id) or not _nonempty_string(request.dossier_id):
                return self._decision(request, False, "MISSING_SCOPE", "tenant and dossier are required")
            if role not in ROLES:
                return self._decision(request, False, "UNKNOWN_ROLE", "role is not recognized")
            if action not in ACTIONS:
                return self._decision(request, False, "UNKNOWN_ACTION", "action is not recognized")
            if not _is_trusted_principal(request.principal):
                return self._decision(request, False, "UNTRUSTED_PRINCIPAL", "trusted principal binding is required")
            if request.actor_id != request.principal.actor_id:
                return self._decision(request, False, "ACTOR_MISMATCH", "request actor differs from principal")
            if request.tenant_id != request.principal.tenant_id:
                return self._decision(request, False, "CROSS_TENANT", "principal and request tenants differ")
            if role != _normalise(request.principal.role):
                return self._decision(request, False, "ROLE_MISMATCH", "request role differs from principal role")
            if expected_tenant is None or expected_dossier is None:
                return self._decision(request, False, "SCOPE_NOT_BOUND", "policy scope must be bound at construction")
            caller_tenant = _canonical_string(tenant_id) if tenant_id is not None else None
            caller_dossier = _canonical_string(dossier_id) if dossier_id is not None else None
            if (tenant_id is not None and caller_tenant is None) or (dossier_id is not None and caller_dossier is None):
                return self._decision(request, False, "INVALID_CONTEXT", "caller scope fields are invalid")
            if caller_tenant is not None and caller_tenant != expected_tenant:
                return self._decision(request, False, "CROSS_TENANT", "caller cannot override policy tenant scope")
            if caller_dossier is not None and caller_dossier != expected_dossier:
                return self._decision(request, False, "CROSS_DOSSIER", "caller cannot override policy dossier scope")
            if expected_tenant is not None and request.tenant_id != expected_tenant:
                return self._decision(request, False, "CROSS_TENANT", "request is outside the tenant scope")
            if expected_dossier is not None and request.dossier_id != expected_dossier:
                return self._decision(request, False, "CROSS_DOSSIER", "request is outside the dossier scope")
            if role not in ROLES:
                return self._decision(request, False, "UNKNOWN_ROLE", "role is not recognized")
            if action not in ACTIONS:
                return self._decision(request, False, "UNKNOWN_ACTION", "action is not recognized")
            if action not in ROLE_ACTIONS[role]:
                return self._decision(request, False, "ROLE_NOT_ALLOWED", "role is not allowed for action")
            if action == "hitl.command":
                if not _nonempty_string(request.idempotency_key):
                    return self._decision(request, False, "IDEMPOTENCY_KEY_REQUIRED", "command key is required")
                cache_key = (request.tenant_id, request.dossier_id, request.actor_id, request.idempotency_key)
                digest = _command_digest(request)
                prior = self._idempotency.get(cache_key)
                if prior is not None:
                    prior_digest, prior_decision = prior
                    if prior_digest != digest:
                        return self._decision(
                            request,
                            False,
                            "IDEMPOTENCY_CONFLICT",
                            "idempotency key was reused for a different command",
                        )
                    return AuthorizationDecision(**{**prior_decision.__dict__, "cached": True})
            else:
                digest = None
                cache_key = None

            decision = self._decision(request, True, "AUTHORIZED", "request is authorized")
            if cache_key is not None and digest is not None:
                self._idempotency[cache_key] = (digest, decision)
            return decision

    @property
    def tenant_id(self) -> str | None:
        return self._tenant_id

    @property
    def dossier_id(self) -> str | None:
        return self._dossier_id

    def authorize_tool(self, tool_name: str, **kwargs: Any) -> "ToolDecision":
        return self.tool_policy.authorize(tool_name, **kwargs)

    def _decision(self, request: AuthzRequest, allowed: bool, code: str, reason: str) -> AuthorizationDecision:
        outcome = "allowed" if allowed else "denied"
        details = {
            "code": code,
            "reason": reason,
            "payload": request.payload or {},
        }
        event = build_audit_event(request, outcome=outcome, details=details, code=code)
        return AuthorizationDecision(
            allowed=allowed,
            code=code,
            reason=reason,
            actor_id=request.actor_id,
            tenant_id=request.tenant_id,
            dossier_id=request.dossier_id,
            correlation_id=request.correlation_id,
            action=request.action,
            outcome=outcome,
            audit_event=event,
        )


@dataclass(frozen=True)
class ToolDecision:
    allowed: bool
    code: str
    tool_name: str

    def __bool__(self) -> bool:
        return self.allowed


class ToolPolicy:
    """Allow read-only tools; require explicit approval for mutations."""

    READ_TOOLS = frozenset(
        {
            "snapshot.read",
            "replay.read",
            "stream.read",
            "read_snapshot",
            "read_replay",
            "read_stream",
        }
    )
    SIDE_EFFECT_TOOLS = frozenset({"hitl.command", "command.dispatch", "snapshot.write", "replay.write", "stream.write"})

    def __init__(self, *, approved_tools: Sequence[str] = ()) -> None:
        self._approved_tools = frozenset(_normalise(item) for item in approved_tools)

    def authorize(
        self,
        tool_name: str,
        *,
        approved: bool = False,
        approval: ApprovalGrant | None = None,
        tenant_id: str | None = None,
        dossier_id: str | None = None,
        actor_id: str | None = None,
        command: Any = None,
        command_digest: str | None = None,
    ) -> ToolDecision:
        canonical_tool_name = _canonical_string(tool_name, allow_empty=True) or ""
        normalised = canonical_tool_name.lower()
        if normalised in self.READ_TOOLS:
            return ToolDecision(True, "READ_TOOL_ALLOWED", canonical_tool_name)
        if normalised in self.SIDE_EFFECT_TOOLS:
            if approved:
                return ToolDecision(False, "APPROVAL_RECORD_REQUIRED", canonical_tool_name)
            if not isinstance(approval, ApprovalGrant):
                return ToolDecision(False, "SIDE_EFFECT_APPROVAL_REQUIRED", canonical_tool_name)
            if command is None:
                return ToolDecision(False, "APPROVAL_COMMAND_REQUIRED", canonical_tool_name)
            actual_digest = _command_digest_for(tool_name, command)
            if actual_digest is None:
                return ToolDecision(False, "APPROVAL_COMMAND_INVALID", canonical_tool_name)
            canonical_context = tuple(_canonical_string(value) for value in (tenant_id, dossier_id, actor_id))
            if not all(
                value is not None for value in canonical_context
            ):
                return ToolDecision(False, "APPROVAL_CONTEXT_REQUIRED", canonical_tool_name)
            if not _valid_approval_grant(approval):
                return ToolDecision(False, "APPROVAL_INVALID", canonical_tool_name)
            canonical_tenant, canonical_dossier, canonical_actor = canonical_context
            if (
                approval.tenant_id != canonical_tenant
                or approval.dossier_id != canonical_dossier
                or approval.actor_id != canonical_actor
                or _normalise(approval.tool_name) != normalised
            ):
                return ToolDecision(False, "APPROVAL_SCOPE_MISMATCH", canonical_tool_name)
            if approval.command_digest != actual_digest:
                return ToolDecision(False, "APPROVAL_COMMAND_MISMATCH", canonical_tool_name)
            consumed_error = _consume_approval(approval)
            if consumed_error is not None:
                return ToolDecision(False, consumed_error, canonical_tool_name)
            return ToolDecision(True, "EXPLICIT_APPROVAL", canonical_tool_name)
        return ToolDecision(False, "UNKNOWN_TOOL", canonical_tool_name)

    def is_allowed(self, tool_name: str, **kwargs: Any) -> bool:
        return bool(self.authorize(tool_name, **kwargs))

    allow = is_allowed


def authorize_tool(tool_name: str, *, approved: bool = False, approved_tools: Sequence[str] = (), **kwargs: Any) -> ToolDecision:
    return ToolPolicy(approved_tools=approved_tools).authorize(tool_name, approved=approved, **kwargs)


@dataclass(frozen=True)
class PromptInjectionClassification:
    label: str
    is_untrusted: bool
    should_execute: bool
    signals: tuple[str, ...] = field(default_factory=tuple)

    def as_dict(self) -> dict[str, Any]:
        return {
            "label": self.label,
            "is_untrusted": self.is_untrusted,
            "should_execute": self.should_execute,
            "signals": list(self.signals),
        }


def classify_prompt_injection(value: Any) -> PromptInjectionClassification:
    """Label external content as untrusted; never interpret or execute it."""

    text = value.content if isinstance(value, PromptInput) else value if isinstance(value, str) else repr(value)
    signals = tuple(name for name, pattern in _INJECTION_PATTERNS if pattern.search(text))
    return PromptInjectionClassification(
        label="untrusted",
        is_untrusted=True,
        should_execute=False,
        signals=signals,
    )


label_prompt_injection = classify_prompt_injection


__all__ = [
    "ACTIONS",
    "AuditLog",
    "ApprovalGrant",
    "AuthzRequest",
    "AuthorizationError",
    "AuthorizationDecision",
    "CommandLedger",
    "Principal",
    "PromptInput",
    "PromptInjectionClassification",
    "RequestContext",
    "ResourceScope",
    "ROLE_ACTIONS",
    "ROLES",
    "SecurityPolicy",
    "ToolDecision",
    "ToolPolicy",
    "authorize_tool",
    "build_audit_event",
    "classify_prompt_injection",
    "label_prompt_injection",
    "issue_approval_grant",
    "issue_trusted_principal",
    "is_trusted_principal",
    "redact",
    "redact_for_audit",
    "validate_request_context",
]
