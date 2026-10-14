"""last_login_at of a user comes from Keycloak's LOGIN events.

One realm-wide call covers the newest events; when that window is full, users
of the page it does not cover are asked for one by one.
"""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

import pytest
from keycloak.exceptions import KeycloakError

from contract_intelligence.infrastructure import keycloak_admin

ALICE = "kc-alice"
BOB = "kc-bob"
CAROL = "kc-carol"


def _ms(day: int, hour: int = 0) -> int:
    return int(datetime(2026, 10, day, hour, tzinfo=UTC).timestamp() * 1000)


def _login(user_id: str, time_ms: int) -> dict[str, Any]:
    return {"type": "LOGIN", "userId": user_id, "time": time_ms}


class _FakeAdmin:
    def __init__(
        self,
        events: list[dict[str, Any]] | Exception,
        *,
        fail_for_user: str | None = None,
    ) -> None:
        self._events = events
        self._fail_for_user = fail_for_user
        self.event_queries: list[dict[str, Any]] = []
        self.users = [
            {"id": ALICE, "email": "alice@example.com", "enabled": True},
            {"id": BOB, "email": "bob@example.com", "enabled": True},
            {"id": CAROL, "email": "carol@example.com", "enabled": True},
        ]

    def get_users(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return self.users

    def get_user(self, user_id: str) -> dict[str, Any]:
        return next(user for user in self.users if user["id"] == user_id)

    def get_realm_roles_of_user(self, user_id: str) -> list[dict[str, Any]]:
        return [{"name": "OPERATOR"}]

    def get_realm_role_members(self, role: str, query: Any = None) -> list[dict[str, Any]]:
        return self.users

    def disable_user(self, user_id: str) -> None:
        return None

    def get_events(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        self.event_queries.append(query)
        if isinstance(self._events, Exception):
            raise self._events
        if "user" in query:
            if query["user"] == self._fail_for_user:
                raise KeycloakError(error_message="unavailable", response_code=503)
            own = [event for event in self._events if event["userId"] == query["user"]]
            return own[: query["max"]]
        # Like Keycloak: newest first, never more than `max`.
        return self._events[: query["max"]]


def _use(monkeypatch: pytest.MonkeyPatch, admin: _FakeAdmin) -> None:
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)


def _list(**overrides: Any) -> keycloak_admin.UserListResult:
    params: dict[str, Any] = {
        "q": None,
        "role": None,
        "status": None,
        "limit": 20,
        "offset": 0,
        "tenant_id": None,
    }
    params.update(overrides)
    return keycloak_admin._list_users_sync(**params)


def test_each_user_gets_their_newest_login(monkeypatch: pytest.MonkeyPatch) -> None:
    # Keycloak returns newest first; a foreign user's event sits in between.
    admin = _FakeAdmin(
        [
            _login(BOB, _ms(11, 9)),
            _login("kc-someone-else", _ms(11, 8)),
            _login(ALICE, _ms(10, 15)),
            _login(BOB, _ms(9)),
            _login(ALICE, _ms(8)),
        ]
    )
    _use(monkeypatch, admin)

    by_id = {user.id: user for user in _list().items}

    assert by_id[ALICE].last_login_at == datetime(2026, 10, 10, 15, tzinfo=UTC)
    assert by_id[BOB].last_login_at == datetime(2026, 10, 11, 9, tzinfo=UTC)
    assert admin.event_queries == [{"type": "LOGIN", "max": 1000}]


def test_newest_login_wins_whatever_order_the_events_come_in(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _use(monkeypatch, _FakeAdmin([_login(ALICE, _ms(3)), _login(ALICE, _ms(7))]))

    by_id = {user.id: user for user in _list().items}

    assert by_id[ALICE].last_login_at == datetime(2026, 10, 7, tzinfo=UTC)


def test_user_without_a_login_event_has_no_last_login(monkeypatch: pytest.MonkeyPatch) -> None:
    _use(monkeypatch, _FakeAdmin([_login(ALICE, _ms(10))]))

    by_id = {user.id: user for user in _list().items}

    assert by_id[CAROL].last_login_at is None
    assert by_id[ALICE].last_login_at is not None


@pytest.mark.parametrize(
    "failure",
    [
        KeycloakError(error_message="forbidden", response_code=403),
        TimeoutError("events timed out"),
    ],
)
def test_failed_events_call_still_lists_the_users(
    monkeypatch: pytest.MonkeyPatch, failure: Exception
) -> None:
    _use(monkeypatch, _FakeAdmin(failure))

    result = _list()

    assert result.total == 3
    assert [user.last_login_at for user in result.items] == [None, None, None]


def test_only_the_returned_page_is_looked_up_in_one_call(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _FakeAdmin([_login(ALICE, _ms(10)), _login(BOB, _ms(9)), _login(CAROL, _ms(8))])
    _use(monkeypatch, admin)

    result = _list(limit=2, offset=1)

    assert [user.id for user in result.items] == [BOB, CAROL]
    assert all(user.last_login_at is not None for user in result.items)
    assert len(admin.event_queries) == 1


def test_login_older_than_the_realm_window_is_still_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # The realm-wide window holds 2 events and is full: Alice's last login is
    # older than both, so she (and Carol) are asked for one by one.
    monkeypatch.setattr(keycloak_admin, "_LOGIN_EVENTS_MAX", 2)
    admin = _FakeAdmin(
        [
            _login(BOB, _ms(11, 9)),
            _login("kc-someone-else", _ms(11, 8)),
            _login(ALICE, _ms(5)),
        ]
    )
    _use(monkeypatch, admin)

    by_id = {user.id: user for user in _list().items}

    assert by_id[ALICE].last_login_at == datetime(2026, 10, 5, tzinfo=UTC)
    assert by_id[BOB].last_login_at == datetime(2026, 10, 11, 9, tzinfo=UTC)
    assert by_id[CAROL].last_login_at is None
    assert admin.event_queries == [
        {"type": "LOGIN", "max": 2},
        {"type": "LOGIN", "user": ALICE, "max": 1},
        {"type": "LOGIN", "user": CAROL, "max": 1},
    ]


def test_window_that_is_not_full_needs_no_per_user_call(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    # Fewer events than the window holds: that is every event the realm keeps,
    # so Carol has no login to find and is not asked for separately.
    admin = _FakeAdmin([_login(ALICE, _ms(10)), _login(BOB, _ms(9))])
    _use(monkeypatch, admin)

    by_id = {user.id: user for user in _list().items}

    assert by_id[CAROL].last_login_at is None
    assert admin.event_queries == [{"type": "LOGIN", "max": 1000}]


def test_failed_per_user_call_keeps_what_was_found(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(keycloak_admin, "_LOGIN_EVENTS_MAX", 1)
    admin = _FakeAdmin(
        [_login(BOB, _ms(11)), _login(ALICE, _ms(5)), _login(CAROL, _ms(4))],
        fail_for_user=ALICE,
    )
    _use(monkeypatch, admin)

    by_id = {user.id: user for user in _list().items}

    assert by_id[BOB].last_login_at == datetime(2026, 10, 11, tzinfo=UTC)
    assert by_id[ALICE].last_login_at is None
    # The failure stops the lookup: Carol is not asked for.
    assert by_id[CAROL].last_login_at is None
    assert admin.event_queries[-1] == {"type": "LOGIN", "user": ALICE, "max": 1}


def test_empty_page_does_not_call_events(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _FakeAdmin([_login(ALICE, _ms(10))])
    _use(monkeypatch, admin)

    assert _list(offset=10).items == []
    assert admin.event_queries == []


def test_single_user_response_carries_the_last_login(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _FakeAdmin([_login(BOB, _ms(11)), _login(ALICE, _ms(10)), _login(ALICE, _ms(2))])
    _use(monkeypatch, admin)

    user = keycloak_admin._set_enabled_sync(user_id=ALICE, enabled=False)

    assert user.last_login_at == datetime(2026, 10, 10, tzinfo=UTC)
    assert admin.event_queries == [{"type": "LOGIN", "user": ALICE, "max": 1}]


def test_stale_last_login_attribute_is_not_used(monkeypatch: pytest.MonkeyPatch) -> None:
    admin = _FakeAdmin([])
    admin.users[0]["attributes"] = {"last_login_at": ["2020-01-01T00:00:00Z"]}
    _use(monkeypatch, admin)

    by_id = {user.id: user for user in _list().items}

    assert by_id[ALICE].last_login_at is None
