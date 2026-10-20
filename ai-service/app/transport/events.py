"""Fail-closed event, AG-UI, SSE, and A2UI boundary primitives."""

from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import Enum
from typing import Any, Mapping

from app.security.policy import AuthorizationError, Principal, ROLE_ACTIONS, is_trusted_principal


@dataclass(frozen=True, slots=True)
class EventEnvelope:
    event_id: str
    run_id: str
    tenant_id: str
    sequence: int
    state_version: int
    state_hash: str
    event_type: str
    schema_version: str
    correlation_id: str
    payload: Mapping[str, Any]
    replayable: bool


class DeliveryClassification(str, Enum):
    ACCEPTED = "ACCEPTED"
    DUPLICATE = "DUPLICATE"
    OUT_OF_ORDER = "OUT_OF_ORDER"
    GAP = "GAP"


# Explicit aliases keep the small public API readable at call sites.
DeliveryDecision = DeliveryClassification
DeliveryStatus = DeliveryClassification


_SENSITIVE_KEY_PARTS = tuple(
    "".join(character for character in part.casefold() if character.isalnum())
    for part in ("raw_contract", "hidden_reasoning", "secret", "token", "prompt")
)
_CANONICAL_EVENT_KEYS = frozenset(
    {
        "event_id", "run_id", "tenant_id", "sequence", "state_version", "state_hash",
        "event_type", "schema_version", "correlation_id", "payload", "replayable",
    }
)


def _is_sensitive_key(key: Any) -> bool:
    if type(key) is not str:
        return False
    normalised = "".join(character for character in str.casefold(key) if character.isalnum())
    return any(part in normalised for part in _SENSITIVE_KEY_PARTS)


def _value(event: EventEnvelope | Mapping[str, Any], name: str, default: Any = None) -> Any:
    if isinstance(event, EventEnvelope):
        return getattr(event, name, default)
    if isinstance(event, Mapping):
        try:
            for key, value in event.items():
                if type(key) is str and key == name:
                    return value
        except Exception:
            return default
    return default


def _valid_sequence(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _valid_state_version(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value >= 1


def _valid_nonempty_string(value: Any) -> bool:
    return _canonical_string(value) is not None


def _canonical_string(value: Any) -> str | None:
    """Return a plain string so caller-defined equality cannot affect scope checks."""

    if not isinstance(value, str):
        return None
    canonical = str.strip(value)
    return canonical if canonical else None


def _normalise_optional_scope(value: Any, field_name: str) -> str | None:
    if value is None:
        return None
    normalised = _canonical_string(value)
    if normalised is None:
        raise ValueError(f"{field_name} must be a non-empty string")
    return normalised


def validate_scope(
    event: EventEnvelope | Mapping[str, Any],
    tenant_id: str,
    run_id: str,
    *,
    resource_id: str | None = None,
) -> bool:
    """Return true only when a well-formed event belongs to the requested scope."""

    try:
        expected_tenant = _canonical_string(tenant_id)
        expected_run = _canonical_string(run_id)
        expected_resource = _canonical_string(resource_id) if resource_id is not None else None
        event_tenant = _canonical_string(_value(event, "tenant_id"))
        event_run = _canonical_string(_value(event, "run_id"))
        event_id = _canonical_string(_value(event, "event_id"))
        event_type = _canonical_string(_value(event, "event_type"))
        schema_version = _canonical_string(_value(event, "schema_version"))
        state_hash = _canonical_string(_value(event, "state_hash"))
        correlation_id = _canonical_string(_value(event, "correlation_id"))
        event_resource = _canonical_string(_value(event, "resource_id")) if resource_id is not None else None
        if expected_tenant is None or expected_run is None or event_tenant is None or event_run is None:
            return False
        if isinstance(event, EventEnvelope):
            if resource_id is not None:
                return False
        elif isinstance(event, Mapping):
            expected_keys = _CANONICAL_EVENT_KEYS if resource_id is None else _CANONICAL_EVENT_KEYS | {"resource_id"}
            event = _canonical_raw_event(event, expected_keys)
            if event is None:
                return False
        else:
            return False
        return (
            event_tenant == expected_tenant
            and event_run == expected_run
            and event_id is not None
            and event_type is not None
            and schema_version is not None
            and _valid_sequence(_value(event, "sequence"))
            and _valid_state_version(_value(event, "state_version"))
            and state_hash is not None
            and correlation_id is not None
            and isinstance(_value(event, "payload"), Mapping)
            and isinstance(_value(event, "replayable"), bool)
            and (
                resource_id is None
                or (
                    expected_resource is not None
                    and event_resource is not None
                    and event_resource == expected_resource
                )
            )
        )
    except Exception:
        return False


def classify_delivery(
    last_sequence: int, event: EventEnvelope | Mapping[str, Any]
) -> DeliveryClassification:
    """Classify an event against the highest contiguous sequence already seen."""

    if (
        not isinstance(last_sequence, int)
        or isinstance(last_sequence, bool)
        or last_sequence < 0
        or not isinstance(event, (EventEnvelope, Mapping))
    ):
        return DeliveryClassification.OUT_OF_ORDER

    sequence = _value(event, "sequence")
    if not _valid_sequence(sequence):
        return DeliveryClassification.OUT_OF_ORDER
    if sequence == last_sequence:
        return DeliveryClassification.DUPLICATE
    if sequence < last_sequence:
        return DeliveryClassification.OUT_OF_ORDER
    if sequence > last_sequence + 1:
        return DeliveryClassification.GAP
    return DeliveryClassification.ACCEPTED


def _sanitize(value: Any) -> Any:
    if isinstance(value, Mapping):
        safe: dict[str, Any] = {}
        try:
            for key, item in value.items():
                if type(key) is not str or _is_sensitive_key(key):
                    continue
                safe[key] = _sanitize(item)
        except Exception:
            return safe
        return safe
    if isinstance(value, list):
        return [_sanitize(item) for item in value]
    if isinstance(value, tuple):
        return [_sanitize(item) for item in value]
    return value


def _event_mapping(event: EventEnvelope | Mapping[str, Any]) -> dict[str, Any] | None:
    if isinstance(event, EventEnvelope):
        return asdict(event)
    if isinstance(event, Mapping):
        return _canonical_raw_event(event, _CANONICAL_EVENT_KEYS | {"resource_id"}, require_exact=False)
    return None


def _canonical_raw_event(
    event: Mapping[Any, Any],
    allowed_keys: frozenset[str] | set[str],
    *,
    require_exact: bool = True,
) -> dict[str, Any] | None:
    """Copy raw event keys only after exact plain-key validation."""

    safe: dict[str, Any] = {}
    try:
        for key, value in event.items():
            if type(key) is not str or key not in allowed_keys:
                return None
            safe[key] = value
    except Exception:
        return None
    if require_exact and (len(safe) != len(allowed_keys) or any(key not in safe for key in allowed_keys)):
        return None
    return safe


def map_to_agui(
    event: EventEnvelope | Mapping[str, Any],
    allowed_event_types: set[str] | frozenset[str],
    *,
    expected_tenant_id: str,
    expected_run_id: str,
    expected_resource_id: str | None = None,
) -> dict[str, Any] | None:
    """Map a canonical event to a public AG-UI-shaped event, or reject it."""

    if not isinstance(allowed_event_types, (set, frozenset)):
        return None
    canonical_allowed_types = {
        canonical
        for item in allowed_event_types
        if (canonical := _canonical_string(item)) is not None
    }
    if len(canonical_allowed_types) != len(allowed_event_types) or not validate_scope(
            event,
            expected_tenant_id,
            expected_run_id,
            resource_id=expected_resource_id,
        ):
        return None
    event_type = _canonical_string(_value(event, "event_type"))
    if event_type is None or event_type not in canonical_allowed_types:
        return None

    mapped = _event_mapping(event)
    if mapped is None or not isinstance(mapped.get("payload"), Mapping):
        return None
    for field_name in (
        "event_id", "run_id", "tenant_id", "state_hash", "event_type", "schema_version", "correlation_id"
    ):
        canonical = _canonical_string(mapped.get(field_name))
        if canonical is None:
            return None
        mapped[field_name] = canonical
    if "resource_id" in mapped:
        canonical_resource = _canonical_string(mapped.get("resource_id"))
        if canonical_resource is None:
            return None
        mapped["resource_id"] = canonical_resource
    mapped = _sanitize(mapped)
    mapped["type"] = event_type
    return mapped


@dataclass(frozen=True, slots=True, init=False)
class SseSession:
    """Read-only SSE session state; commands must be sent through HTTP."""

    tenant_id: str
    run_id: str
    last_sequence: int = 0
    state_hash: str = ""
    principal_id: str | None = None
    resource_id: str | None = None
    _authorized: bool = False

    def __init__(
        self,
        tenant_id: str,
        run_id: str,
        last_sequence: int = 0,
        state_hash: str = "",
        authorized: bool = False,
        principal_id: str | None = None,
        resource_id: str | None = None,
    ) -> None:
        if authorized is not False:
            raise AuthorizationError("UNTRUSTED_SSE_SESSION", "authorized state cannot be supplied by the caller")
        normalised_tenant_id = _normalise_optional_scope(tenant_id, "tenant_id")
        normalised_run_id = _normalise_optional_scope(run_id, "run_id")
        if normalised_tenant_id is None or normalised_run_id is None:
            raise ValueError("tenant_id and run_id are required")
        if not isinstance(last_sequence, int) or isinstance(last_sequence, bool) or last_sequence < 0:
            raise ValueError("last_sequence must be a non-negative integer")
        if (principal_id is None) != (resource_id is None):
            raise ValueError("principal_id and resource_id must be supplied together")
        normalised_principal_id = _normalise_optional_scope(principal_id, "principal_id")
        normalised_resource_id = _normalise_optional_scope(resource_id, "resource_id")
        object.__setattr__(self, "tenant_id", normalised_tenant_id)
        object.__setattr__(self, "run_id", normalised_run_id)
        object.__setattr__(self, "last_sequence", last_sequence)
        object.__setattr__(self, "state_hash", state_hash)
        object.__setattr__(self, "principal_id", normalised_principal_id)
        object.__setattr__(self, "resource_id", normalised_resource_id)
        object.__setattr__(self, "_authorized", False)

    @property
    def authorized(self) -> bool:
        return self._authorized

    @property
    def cursor(self) -> int:
        return self.last_sequence

    def authorize(
        self,
        principal: Principal | None,
        *,
        run_id: str | None = None,
        resource_id: str | None = None,
    ) -> bool:
        try:
            requested_run_id = _canonical_string(run_id)
            requested_resource_id = _canonical_string(resource_id)
            valid = (
                is_trusted_principal(principal)
                and requested_run_id is not None
                and requested_resource_id is not None
                and principal.tenant_id == self.tenant_id
                and principal.actor_id == self.principal_id
                and requested_run_id == self.run_id
                and requested_resource_id == self.resource_id
                and "stream.read" in ROLE_ACTIONS.get(principal.role.lower(), frozenset())
            )
        except (AttributeError, TypeError):
            valid = False
        object.__setattr__(self, "_authorized", bool(valid))
        return self._authorized

    def heartbeat(self) -> dict[str, Any]:
        if not self.authorized:
            return {"code": "SSE_AUTHORIZATION_REQUIRED"}
        return {
            "event_type": "HEARTBEAT",
            "run_id": self.run_id,
            "tenant_id": self.tenant_id,
            "sequence": self.last_sequence,
            "state_hash": self.state_hash,
            "replayable": False,
        }

    def reconnect_cursor(self) -> dict[str, Any]:
        if not self.authorized:
            return {"code": "SSE_AUTHORIZATION_REQUIRED"}
        return {"last_sequence": self.last_sequence, "state_hash": self.state_hash}

    def reject_command(self, command: Any = None) -> dict[str, Any]:
        if not self.authorized:
            return {"code": "SSE_AUTHORIZATION_REQUIRED"}
        return {
            "accepted": False,
            "code": "SSE_COMMAND_NOT_ALLOWED",
            "reason": "SSE is read-only; submit commands through the authorized HTTP endpoint",
            "command": "[REDACTED]",
        }


def _catalog_components(catalog: Any) -> list[Any] | None:
    if isinstance(catalog, Mapping):
        components = catalog.get("components")
    else:
        components = catalog
    return components if isinstance(components, list) else None


def validate_a2ui_catalog(
    catalog: Any, allowlist: set[str] | frozenset[str], enabled: bool = False
) -> bool:
    """Validate only explicitly enabled catalogs against a fixed component allowlist."""

    if not enabled or not isinstance(allowlist, (set, frozenset)):
        return False
    if not all(isinstance(item, str) and bool(item) for item in allowlist):
        return False

    components = _catalog_components(catalog)
    if components is None:
        return False
    for component in components:
        if isinstance(component, str):
            component_type = component
        elif isinstance(component, Mapping):
            component_type = component.get("type", component.get("component_type"))
        else:
            return False
        if not isinstance(component_type, str) or component_type not in allowlist:
            return False
    return True


__all__ = [
    "DeliveryClassification",
    "DeliveryDecision",
    "DeliveryStatus",
    "EventEnvelope",
    "SseSession",
    "classify_delivery",
    "map_to_agui",
    "validate_a2ui_catalog",
    "validate_scope",
]
