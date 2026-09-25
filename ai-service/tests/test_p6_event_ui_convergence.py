import pytest

from app.security.policy import AuthorizationError, Principal, issue_trusted_principal
from app.transport.events import (
    DeliveryClassification,
    EventEnvelope,
    SseSession,
    classify_delivery,
    map_to_agui,
    validate_a2ui_catalog,
    validate_scope,
)


def event(sequence: int = 1, **payload) -> EventEnvelope:
    return EventEnvelope(
        event_id=f"evt-{sequence}",
        run_id="run-1",
        tenant_id="tenant-a",
        sequence=sequence,
        state_version=sequence,
        state_hash="hash-1",
        event_type="FACTS_READY",
        schema_version="run.event.v1",
        correlation_id="corr-1",
        payload=payload or {"safe": "ok"},
        replayable=True,
    )


def test_scope_delivery_and_agui_redaction() -> None:
    current = event(
        raw_contract="secret",
        rawContractText="private",
        nested={
            "hidden_reasoning": "private",
            "hiddenReasoningTrace": "private",
            "HIDDEN_REASONING_TRACE": "private",
            "secretToken": "private",
            "prompt_suffix": "private",
            "safe": 1,
        },
        items=[
            {
                "RAW_CONTRACT_COPY": "private",
                "SECRET_COPY": "private",
                "PROMPT_COPY": "private",
                "TOKEN-value": "private",
                "safe": 2,
            }
        ],
    )

    assert validate_scope(current, "tenant-a", "run-1")
    assert not validate_scope(current, "tenant-b", "run-1")
    assert classify_delivery(0, current) is DeliveryClassification.ACCEPTED
    assert classify_delivery(1, current) is DeliveryClassification.DUPLICATE
    assert classify_delivery(2, current) is DeliveryClassification.OUT_OF_ORDER
    assert classify_delivery(0, event(3)) is DeliveryClassification.GAP

    mapped = map_to_agui(
        current,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
    )
    assert mapped is not None
    assert mapped["type"] == "FACTS_READY"
    assert "raw_contract" not in mapped["payload"]
    assert "rawContractText" not in mapped["payload"]
    assert "hidden_reasoning" not in mapped["payload"]["nested"]
    assert "hiddenReasoningTrace" not in mapped["payload"]["nested"]
    assert "HIDDEN_REASONING_TRACE" not in mapped["payload"]["nested"]
    assert "secretToken" not in mapped["payload"]["nested"]
    assert "prompt_suffix" not in mapped["payload"]["nested"]
    assert "RAW_CONTRACT_COPY" not in mapped["payload"]["items"][0]
    assert "SECRET_COPY" not in mapped["payload"]["items"][0]
    assert "PROMPT_COPY" not in mapped["payload"]["items"][0]
    assert "TOKEN-value" not in mapped["payload"]["items"][0]
    assert mapped["payload"]["nested"]["safe"] == 1
    assert map_to_agui(
        current,
        {"RUN_COMPLETED"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
    ) is None


def test_scope_validation_and_mapper_require_canonical_envelope_and_expected_scope() -> None:
    current = event()
    raw = {
        "event_id": current.event_id,
        "run_id": current.run_id,
        "tenant_id": current.tenant_id,
        "sequence": current.sequence,
        "state_version": current.state_version,
        "state_hash": current.state_hash,
        "event_type": current.event_type,
        "schema_version": current.schema_version,
        "correlation_id": current.correlation_id,
        "payload": dict(current.payload),
        "replayable": current.replayable,
    }
    for missing in ("event_type", "schema_version", "state_version", "state_hash", "correlation_id", "payload"):
        malformed = dict(raw)
        malformed.pop(missing)
        assert not validate_scope(malformed, "tenant-a", "run-1")

    assert map_to_agui(
        current,
        {"FACTS_READY"},
        expected_tenant_id="tenant-b",
        expected_run_id="run-1",
    ) is None
    assert map_to_agui(
        current,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-other",
    ) is None

    leaked_top_level = {**raw, "hidden_reasoning": "LEAK"}
    assert not validate_scope(leaked_top_level, "tenant-a", "run-1")
    assert map_to_agui(
        leaked_top_level,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
    ) is None
    cross_scope_resource = {**raw, "resource_id": "dossier-b"}
    assert not validate_scope(cross_scope_resource, "tenant-a", "run-1")
    assert map_to_agui(
        cross_scope_resource,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
        expected_resource_id="dossier-a",
    ) is None
    matching_resource = {**raw, "resource_id": "dossier-a"}
    assert map_to_agui(
        matching_resource,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
        expected_resource_id="dossier-a",
    ) is not None


@pytest.mark.parametrize("spoofed_field", ["event_id", "tenant_id", "payload", "extra"])
def test_raw_agui_mapping_rejects_non_plain_keys_before_lookup_or_equality(spoofed_field: str) -> None:
    class EvilKey(str):
        __hash__ = str.__hash__

        def __eq__(self, other: object) -> bool:
            raise AssertionError("caller-controlled key equality must not run")

    current = event()
    raw = {
        "event_id": current.event_id,
        "run_id": current.run_id,
        "tenant_id": current.tenant_id,
        "sequence": current.sequence,
        "state_version": current.state_version,
        "state_hash": current.state_hash,
        "event_type": current.event_type,
        "schema_version": current.schema_version,
        "correlation_id": current.correlation_id,
        "payload": current.payload,
        "replayable": current.replayable,
    }
    if spoofed_field == "extra":
        raw["extra"] = "spoof"
        key_name = "extra"
    else:
        key_name = spoofed_field
    raw = {
        EvilKey(key_name) if key == key_name else key: value
        for key, value in raw.items()
    }

    assert validate_scope(raw, "tenant-a", "run-1") is False
    assert map_to_agui(
        raw,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
    ) is None


def test_agui_sanitizer_drops_nested_non_plain_sensitive_keys() -> None:
    class SneakyKey(str):
        __hash__ = str.__hash__

        def __str__(self) -> str:
            raise AssertionError("caller-controlled __str__ must not run")

    current = event(
        nested={SneakyKey("prompt"): "SECRET"},
        items=[{SneakyKey("token"): "TOKEN"}],
        tuple_items=({SneakyKey("secret"): "SECRET"},),
    )

    mapped = map_to_agui(
        current,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
    )

    assert mapped is not None
    assert mapped["payload"] == {"nested": {}, "items": [{}], "tuple_items": [{}]}


def test_sse_session_is_tenant_resource_and_principal_bound_read_only_and_cursored() -> None:
    session = SseSession(
        "tenant-a",
        "run-1",
        last_sequence=4,
        state_hash="hash-4",
        principal_id="reader-1",
        resource_id="dossier-a",
    )

    heartbeat_before_auth = session.heartbeat()
    cursor_before_auth = session.reconnect_cursor()
    rejected_before_auth = session.reject_command("approve secret command")

    assert heartbeat_before_auth["code"] == "SSE_AUTHORIZATION_REQUIRED"
    assert "tenant_id" not in heartbeat_before_auth
    assert "run_id" not in heartbeat_before_auth
    assert cursor_before_auth["code"] == "SSE_AUTHORIZATION_REQUIRED"
    assert "last_sequence" not in cursor_before_auth
    assert "state_hash" not in cursor_before_auth
    assert rejected_before_auth["code"] == "SSE_AUTHORIZATION_REQUIRED"
    assert "approve secret command" not in repr(rejected_before_auth)

    assert session.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only"),
        run_id="run-1",
        resource_id="dossier-a",
    )
    assert session.heartbeat()["event_type"] == "HEARTBEAT"
    assert session.reconnect_cursor() == {"last_sequence": 4, "state_hash": "hash-4"}
    rejected = session.reject_command("approve secret command")
    assert rejected["accepted"] is False
    assert rejected["command"] == "[REDACTED]"
    assert "approve secret command" not in repr(rejected)

    assert not session.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-b", role="read_only"),
        run_id="run-1",
        resource_id="dossier-a",
    )
    assert session.heartbeat()["code"] == "SSE_AUTHORIZATION_REQUIRED"


def test_sse_session_fails_closed_for_missing_or_cross_resource_scope() -> None:
    missing_scope = SseSession("tenant-a", "run-1")
    assert not missing_scope.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only"),
        run_id="run-1",
        resource_id="dossier-a",
    )

    session = SseSession(
        "tenant-a",
        "run-1",
        principal_id="reader-1",
        resource_id="dossier-a",
    )
    principal = issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only")
    assert not session.authorize(principal, run_id="run-other", resource_id="dossier-a")
    assert not session.authorize(principal, run_id="run-1", resource_id="dossier-b")


def test_sse_constructor_cannot_forge_authorization_or_retarget_bound_state() -> None:
    with pytest.raises(AuthorizationError):
        SseSession("tenant-a", "run-1", authorized=True, principal_id="reader-1", resource_id="dossier-a")

    session = SseSession("tenant-a", "run-1", principal_id="reader-1", resource_id="dossier-a")
    assert session.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only"),
        run_id="run-1",
        resource_id="dossier-a",
    )
    with pytest.raises((AttributeError, TypeError, ValueError)):
        session.tenant_id = "tenant-b"
    with pytest.raises((AttributeError, TypeError, ValueError)):
        session.run_id = "run-b"
    with pytest.raises((AttributeError, TypeError, ValueError)):
        session.resource_id = "dossier-b"
    heartbeat = session.heartbeat()
    assert heartbeat["tenant_id"] == "tenant-a"
    assert heartbeat["run_id"] == "run-1"


def test_sse_rejects_malformed_principal_without_raising() -> None:
    malformed = object.__new__(Principal)
    session = SseSession("tenant-a", "run-1", principal_id="reader-1", resource_id="dossier-a")

    assert not session.authorize(malformed, run_id="run-1", resource_id="dossier-a")
    assert session.heartbeat()["code"] == "SSE_AUTHORIZATION_REQUIRED"


def test_sse_constructor_normalizes_string_subclasses_before_scope_comparison() -> None:
    class AlwaysEqualString(str):
        def __eq__(self, other: object) -> bool:
            return True

    session = SseSession(
        "tenant-a",
        "run-1",
        principal_id=AlwaysEqualString("attacker"),
        resource_id=AlwaysEqualString("attacker-resource"),
    )

    assert type(session.principal_id) is str
    assert type(session.resource_id) is str
    assert not session.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only"),
        run_id="run-1",
        resource_id="dossier-a",
    )
    assert session.heartbeat()["code"] == "SSE_AUTHORIZATION_REQUIRED"


def test_event_scope_and_agui_mapping_canonicalize_identity_subclasses() -> None:
    class AlwaysEqualString(str):
        def __eq__(self, other: object) -> bool:
            return True

    current = event()
    cross_scope = {
        "event_id": current.event_id,
        "run_id": current.run_id,
        "tenant_id": current.tenant_id,
        "sequence": current.sequence,
        "state_version": current.state_version,
        "state_hash": current.state_hash,
        "event_type": current.event_type,
        "schema_version": current.schema_version,
        "correlation_id": current.correlation_id,
        "payload": current.payload,
        "replayable": current.replayable,
        "tenant_id": AlwaysEqualString("tenant-b"),
        "run_id": AlwaysEqualString("run-other"),
        "event_id": AlwaysEqualString("event-cross-scope"),
    }

    assert not validate_scope(cross_scope, "tenant-a", "run-1")
    assert map_to_agui(
        cross_scope,
        {"FACTS_READY"},
        expected_tenant_id=AlwaysEqualString("tenant-a"),
        expected_run_id=AlwaysEqualString("run-1"),
    ) is None

    canonicalized = {
        **cross_scope,
        "tenant_id": AlwaysEqualString("tenant-a"),
        "run_id": AlwaysEqualString("run-1"),
        "event_id": AlwaysEqualString("event-safe"),
        "event_type": AlwaysEqualString("FACTS_READY"),
    }
    mapped = map_to_agui(canonicalized, {"FACTS_READY"}, expected_tenant_id="tenant-a", expected_run_id="run-1")
    assert mapped is not None
    assert type(mapped["tenant_id"]) is str
    assert type(mapped["run_id"]) is str
    assert type(mapped["event_id"]) is str

    resource_cross_scope = {**cross_scope, "resource_id": AlwaysEqualString("dossier-b")}
    assert not validate_scope(resource_cross_scope, "tenant-a", "run-1", resource_id="dossier-a")
    assert map_to_agui(
        resource_cross_scope,
        {"FACTS_READY"},
        expected_tenant_id="tenant-a",
        expected_run_id="run-1",
        expected_resource_id=AlwaysEqualString("dossier-a"),
    ) is None


def test_sse_session_canonicalizes_tenant_and_run_bindings_before_storage() -> None:
    class AlwaysEqualString(str):
        def __eq__(self, other: object) -> bool:
            return True

    session = SseSession(
        AlwaysEqualString("tenant-b"),
        AlwaysEqualString("run-1"),
        principal_id="reader-1",
        resource_id="dossier-a",
    )

    assert type(session.tenant_id) is str
    assert type(session.run_id) is str
    assert not session.authorize(
        issue_trusted_principal(actor_id="reader-1", tenant_id="tenant-a", role="read_only"),
        run_id=AlwaysEqualString("run-1"),
        resource_id="dossier-a",
    )


@pytest.mark.parametrize("principal_id,resource_id", [(None, "dossier-a"), ("reader-1", None)])
def test_sse_constructor_rejects_partial_optional_scope(
    principal_id: str | None,
    resource_id: str | None,
) -> None:
    with pytest.raises(ValueError):
        SseSession("tenant-a", "run-1", principal_id=principal_id, resource_id=resource_id)


def test_a2ui_catalog_is_disabled_by_default_and_allowlisted_when_enabled() -> None:
    catalog = {"components": [{"type": "Card"}, {"type": "Text"}]}

    assert not validate_a2ui_catalog(catalog, {"Card", "Text"})
    assert validate_a2ui_catalog(catalog, {"Card", "Text"}, enabled=True)
    assert not validate_a2ui_catalog({"components": [{"type": "Button"}]}, {"Card"}, enabled=True)
    assert not validate_a2ui_catalog(None, {"Card"}, enabled=True)
