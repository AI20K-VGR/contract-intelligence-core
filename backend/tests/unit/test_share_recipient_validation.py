"""Sharing a dossier only with real, enabled members of the caller's tenant.

- PUT /dossiers/{id}/access checks every NEW recipient in Keycloak before it stores
  anything or sends any mail; existing grants are kept without a new check
- GET /users/lookup finds exactly one active tenant member by email
- GET /users/directory needs a query from an OPERATOR
- no mail goes to reserved domains (.local, .test, ...): share, invite, resend
"""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from keycloak.exceptions import KeycloakGetError

from contract_intelligence.contract.application.services.contract_service import (
    ContractService,
)
from contract_intelligence.contract.domain.entities.dossier import Dossier
from contract_intelligence.contract.interfaces.api.routers import contract_router
from contract_intelligence.infrastructure import keycloak_admin
from contract_intelligence.main import app
from contract_intelligence.shared.auth import get_current_user
from contract_intelligence.shared.auth.schemas import AuthenticatedUser
from contract_intelligence.shared.email_delivery import is_undeliverable_email

TENANT = "tenant_a"
REJECTED_MESSAGE = (
    "Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt "
    "tài khoản. Vui lòng kiểm tra lại."
)


def _kc_user(
    user_id: str,
    email: str,
    *,
    tenant: str | None = TENANT,
    enabled: bool = True,
    invited: bool = False,
    role: str = "REVIEWER",
) -> dict[str, Any]:
    return {
        "id": user_id,
        "username": email,
        "email": email,
        "firstName": email.split("@")[0].title(),
        "enabled": enabled,
        "requiredActions": ["UPDATE_PASSWORD"] if invited else [],
        "attributes": {"tenant_id": [tenant]} if tenant else {},
        "createdTimestamp": 1_760_000_000_000,
        "_role": role,
    }


class _FakeAdmin:
    def __init__(self) -> None:
        self.users = [
            _kc_user("u-rita", "rita@lexis.vn"),
            _kc_user("u-ivy", "ivy@lexis.vn", invited=True),
            _kc_user("u-dan", "dan@lexis.vn", enabled=False),
            _kc_user("u-zoe", "zoe@lexis.vn", tenant="tenant_b"),
            _kc_user("u-nora", "nora@lexis.vn", tenant=None),
            _kc_user("u-demo", "reviewer@ci.local"),
        ]
        self.queries: list[dict[str, Any]] = []
        self.sent: list[str] = []
        self.created: list[dict[str, Any]] = []
        self.user_reads: list[str] = []

    def get_user(self, user_id: str) -> dict[str, Any]:
        self.user_reads.append(user_id)
        for user in self.users:
            if user["id"] == user_id:
                return user
        raise KeycloakGetError(error_message="User not found", response_code=404)

    def get_users(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        self.queries.append(query)
        # Keycloak's own email filter is a substring match unless exact=true.
        needle = str(query.get("email") or query.get("search") or "").lower()
        return [u for u in self.users if needle in u["email"].lower()]

    def get_realm_roles_of_user(self, user_id: str) -> list[dict[str, Any]]:
        return [{"name": next(u["_role"] for u in self.users if u["id"] == user_id)}]

    def get_events(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def update_user(self, user_id: str, payload: dict[str, Any]) -> None:
        return None

    def send_update_account(self, user_id: str, **_: Any) -> None:
        self.sent.append(user_id)

    def create_user(self, payload: dict[str, Any]) -> str:
        self.created.append(payload)
        return "u-new"


def _principal(role: str = "OPERATOR", tenant: str = TENANT) -> AuthenticatedUser:
    return AuthenticatedUser(
        user_id="u-owner",
        tenant_id=tenant,
        email="owner@lexis.vn",
        display_name="Owner",
        role=role,
    )


@pytest.fixture
def kc(monkeypatch: pytest.MonkeyPatch) -> _FakeAdmin:
    fake = _FakeAdmin()
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: fake)
    return fake


@pytest.fixture
def mailer(monkeypatch: pytest.MonkeyPatch) -> MagicMock:
    send = MagicMock()
    monkeypatch.setattr(contract_router, "_send_share_emails", send)
    monkeypatch.setattr(contract_router, "_record", AsyncMock())
    return send


@pytest_asyncio.fixture
async def mock_svc() -> AsyncMock:
    svc = AsyncMock(spec=ContractService)
    svc.get_dossier.return_value = Dossier(
        id="dos_1",
        name="Hồ sơ A",
        batch_id=None,
        has_conflicts=False,
        metadata={"created_by": "u-owner"},
    )
    return svc


@pytest_asyncio.fixture
async def client(kc: _FakeAdmin, mock_svc: AsyncMock) -> AsyncGenerator[AsyncClient, None]:
    from contract_intelligence.contract.interfaces.api.dependencies import get_contract_service
    from contract_intelligence.shared.auth.tenant import get_tenant_id
    from contract_intelligence.shared.persistence import get_async_session

    async def no_db() -> AsyncGenerator[AsyncMock, None]:
        yield AsyncMock()

    app.dependency_overrides[get_contract_service] = lambda: mock_svc
    app.dependency_overrides[get_current_user] = lambda: _principal()
    app.dependency_overrides[get_tenant_id] = lambda: TENANT
    app.dependency_overrides[get_async_session] = no_db
    async with AsyncClient(transport=ASGITransport(app=app), base_url="http://test") as http:
        yield http
    app.dependency_overrides.clear()


def _share(*grants: dict[str, Any]) -> dict[str, Any]:
    return {"scope": "shared_out", "shared_with": list(grants)}


async def _put(client: AsyncClient, body: dict[str, Any]) -> Any:
    return await client.put("/api/v1/dossiers/dos_1/access", json=body)


# ──────────────────────────────────────────────────────────────────────────────
# PUT /dossiers/{id}/access
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_valid_recipient_is_stored_with_keycloak_identity(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock
) -> None:
    response = await _put(
        client,
        _share({"id": "u-rita", "email": "spoofed@evil.test", "display_name": "Fake"}),
    )

    assert response.status_code == 200, response.text
    stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"]
    assert stored == [
        {
            "id": "u-rita",
            "email": "rita@lexis.vn",
            "display_name": "Rita",
            "status": "active",
            "permission": "edit",
            "expires_at": None,
        }
    ]
    assert mailer.call_args.kwargs["recipients"][0]["email"] == "rita@lexis.vn"


@pytest.mark.asyncio
async def test_recipient_without_id_is_found_by_exact_email(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock, kc: _FakeAdmin
) -> None:
    response = await _put(client, _share({"id": "", "email": "RITA@lexis.vn"}))

    assert response.status_code == 200, response.text
    assert response.json()["data"]["shared_with"][0]["id"] == "u-rita"
    assert kc.queries[-1]["exact"] is True


@pytest.mark.asyncio
async def test_invited_member_may_be_shared_with(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock
) -> None:
    response = await _put(client, _share({"id": "u-ivy", "email": "ivy@lexis.vn"}))

    assert response.status_code == 200, response.text
    stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"][0]
    assert stored["status"] == "invited"


@pytest.mark.parametrize(
    ("grant", "rejected"),
    [
        ({"id": "u-zoe", "email": "zoe@lexis.vn"}, "zoe@lexis.vn"),
        ({"id": "u-dan", "email": "dan@lexis.vn"}, "dan@lexis.vn"),
        ({"id": "u-nora", "email": "nora@lexis.vn"}, "nora@lexis.vn"),
        ({"id": "u-ghost", "email": "ghost@lexis.vn"}, "ghost@lexis.vn"),
        ({"id": "", "email": "nobody@lexis.vn"}, "nobody@lexis.vn"),
        ({"id": "", "email": "lexis.vn"}, "lexis.vn"),
        ({"id": "../roles", "email": ""}, "../roles"),
    ],
    ids=[
        "other-tenant",
        "disabled",
        "no-tenant",
        "unknown-id",
        "unknown-email",
        "partial",
        "bad-id",
    ],
)
@pytest.mark.asyncio
async def test_invalid_recipient_is_rejected_and_nothing_is_saved_or_sent(
    client: AsyncClient,
    mock_svc: AsyncMock,
    mailer: MagicMock,
    grant: dict[str, Any],
    rejected: str,
) -> None:
    response = await _put(client, _share({"id": "u-rita", "email": "rita@lexis.vn"}, grant))

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "share_recipient_not_found"
    assert error["message"] == REJECTED_MESSAGE
    assert error["details"] == {"rejected_emails": [rejected]}
    mock_svc.patch_dossier.assert_not_awaited()
    mailer.assert_not_called()


@pytest.mark.asyncio
async def test_existing_grant_is_kept_without_a_new_check(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock, kc: _FakeAdmin
) -> None:
    """A grant shared before (even with a user since disabled) does not block the save."""
    mock_svc.get_dossier.return_value = Dossier(
        id="dos_1",
        name="Hồ sơ A",
        batch_id=None,
        has_conflicts=False,
        metadata={
            "created_by": "u-owner",
            "access_scope": "shared_out",
            "shared_with": [
                {
                    "id": "u-dan",
                    "email": "dan@lexis.vn",
                    "display_name": "Dan",
                    "status": "active",
                    "permission": "edit",
                },
            ],
        },
    )

    response = await _put(
        client,
        _share(
            {
                "id": "u-dan",
                "email": "changed@evil.test",
                "display_name": "X",
                "permission": "read",
            },
        ),
    )

    assert response.status_code == 200, response.text
    stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"]
    assert stored == [
        {
            "id": "u-dan",
            "email": "dan@lexis.vn",
            "display_name": "Dan",
            "status": "active",
            "permission": "read",
            "expires_at": None,
        },
    ]
    assert kc.queries == []
    mailer.assert_not_called()


@pytest.mark.asyncio
async def test_duplicate_recipients_are_stored_once(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock
) -> None:
    response = await _put(
        client,
        _share({"id": "u-rita", "email": ""}, {"id": "", "email": "rita@lexis.vn"}),
    )

    assert response.status_code == 200, response.text
    stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"]
    assert [grant["id"] for grant in stored] == ["u-rita"]


@pytest.mark.asyncio
async def test_a_repeated_recipient_is_looked_up_once(
    client: AsyncClient, kc: _FakeAdmin, mock_svc: AsyncMock, mailer: MagicMock
) -> None:
    same_id = [{"id": "u-rita", "permission": "edit" if i else "read"} for i in range(60)]
    same_email = [{"id": "", "email": e} for e in ("ivy@lexis.vn", " IVY@lexis.vn ")] * 20

    response = await _put(client, _share(*same_id, *same_email))

    assert response.status_code == 200, response.text
    assert kc.user_reads.count("u-rita") == 1
    assert [q for q in kc.queries if q.get("email")] == [
        {"email": "ivy@lexis.vn", "exact": True, "max": 10}
    ]
    stored = mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"]
    # The first copy wins, as before.
    assert [(g["id"], g["permission"]) for g in stored] == [("u-rita", "read"), ("u-ivy", "edit")]


@pytest.mark.asyncio
async def test_a_repeated_invalid_recipient_is_looked_up_once(
    client: AsyncClient, kc: _FakeAdmin, mock_svc: AsyncMock
) -> None:
    response = await _put(client, _share(*[{"id": "u-zoe", "email": "zoe@lexis.vn"}] * 3))

    assert response.status_code == 422
    assert kc.user_reads.count("u-zoe") == 1
    mock_svc.patch_dossier.assert_not_awaited()


@pytest.mark.asyncio
async def test_too_many_recipients_are_refused_before_any_lookup(
    client: AsyncClient, kc: _FakeAdmin, mock_svc: AsyncMock
) -> None:
    body = _share(
        *[{"id": f"u-{i}", "email": ""} for i in range(contract_router.MAX_SHARE_RECIPIENTS + 1)]
    )

    response = await _put(client, body)

    assert response.status_code == 422
    assert kc.user_reads == []
    mock_svc.patch_dossier.assert_not_awaited()


@pytest.mark.asyncio
async def test_keycloak_down_saves_nothing(
    client: AsyncClient,
    mock_svc: AsyncMock,
    mailer: MagicMock,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    async def down(**_: Any) -> Any:
        raise keycloak_admin.KeycloakUnavailableError()

    monkeypatch.setattr(keycloak_admin, "resolve_tenant_members", down)

    response = await _put(client, _share({"id": "u-rita", "email": "rita@lexis.vn"}))

    assert response.status_code == 503
    assert response.json()["error"]["code"] == "keycloak_unavailable"
    mock_svc.patch_dossier.assert_not_awaited()
    mailer.assert_not_called()


@pytest.mark.asyncio
async def test_private_scope_needs_no_lookup(
    client: AsyncClient, mock_svc: AsyncMock, mailer: MagicMock, kc: _FakeAdmin
) -> None:
    response = await _put(
        client, {"scope": "mine", "shared_with": [{"id": "u-ghost", "email": "x@y.vn"}]}
    )

    assert response.status_code == 200, response.text
    assert mock_svc.patch_dossier.await_args.kwargs["metadata"]["shared_with"] == []
    assert kc.queries == []


# ──────────────────────────────────────────────────────────────────────────────
# GET /users/lookup and /users/directory
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_lookup_returns_the_one_active_member(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/lookup", params={"email": " Rita@Lexis.vn"})

    assert response.status_code == 200, response.text
    assert response.json()["data"] == {
        "id": "u-rita",
        "email": "rita@lexis.vn",
        "display_name": "Rita",
        "role": "REVIEWER",
    }


@pytest.mark.parametrize(
    "email",
    [
        "zoe@lexis.vn",
        "dan@lexis.vn",
        "ivy@lexis.vn",
        "nora@lexis.vn",
        "nobody@lexis.vn",
        "lexis.vn",
    ],
)
@pytest.mark.asyncio
async def test_lookup_hides_everyone_else(client: AsyncClient, email: str) -> None:
    response = await client.get("/api/v1/users/lookup", params={"email": email})

    assert response.status_code == 404
    assert response.json()["error"]["code"] == "user_not_found"


@pytest.mark.asyncio
async def test_lookup_is_for_sharing_roles_only(client: AsyncClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _principal("REVIEWER")

    response = await client.get("/api/v1/users/lookup", params={"email": "rita@lexis.vn"})

    assert response.status_code == 403


@pytest.mark.parametrize("params", [{}, {"q": ""}, {"q": " ri "}])
@pytest.mark.asyncio
async def test_operator_must_search_the_directory(
    client: AsyncClient, params: dict[str, str]
) -> None:
    response = await client.get("/api/v1/users/directory", params=params)

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "directory_query_required"


@pytest.mark.asyncio
async def test_operator_directory_search_still_works(client: AsyncClient) -> None:
    response = await client.get("/api/v1/users/directory", params={"q": "rita@lexis.vn"})

    assert response.status_code == 200, response.text
    assert [item["id"] for item in response.json()["data"]] == ["u-rita"]


# ──────────────────────────────────────────────────────────────────────────────
# No mail to reserved domains
# ──────────────────────────────────────────────────────────────────────────────


@pytest.mark.parametrize(
    ("address", "undeliverable"),
    [
        ("admin@ci.local", True),
        ("a@b.LOCAL.", True),
        ("x@foo.test", True),
        ("x@example.com", True),
        ("x@mail.example.org", True),
        ("x@foo.invalid", True),
        ("x@localhost", True),
        ("x@host.example", True),
        ("no-at-sign", True),
        ("", True),
        ("rita@lexis.vn", False),
        ("someone@gmail.com", False),
        ("x@examples.com", False),
    ],
)
def test_reserved_domains(address: str, undeliverable: bool) -> None:
    assert is_undeliverable_email(address) is undeliverable


def test_share_mail_skips_reserved_domains_without_smtp(
    monkeypatch: pytest.MonkeyPatch, kc: _FakeAdmin
) -> None:
    smtp = MagicMock()
    monkeypatch.setattr("smtplib.SMTP", smtp)

    contract_router._send_share_emails(
        dossier_name="Hồ sơ A",
        dossier_id="dos_1",
        sender_name="Owner",
        recipients=[
            {"id": "u-demo", "email": "reviewer@ci.local", "status": "invited"},
            {"id": "", "email": "guest@foo.local", "status": "active"},
        ],
    )

    smtp.assert_not_called()
    assert kc.sent == []


def test_share_login_mail_skips_a_reserved_keycloak_address(kc: _FakeAdmin) -> None:
    sent = keycloak_admin.send_share_login_email_sync(
        user_id="u-demo", dossier_name="Hồ sơ A", sender_name="Owner", require_password=True
    )

    assert sent is True
    assert kc.sent == []


@pytest.mark.asyncio
async def test_create_user_on_reserved_domain_is_refused(
    client: AsyncClient, kc: _FakeAdmin
) -> None:
    app.dependency_overrides[get_current_user] = lambda: _principal("ADMINISTRATOR")

    response = await client.post(
        "/api/v1/users",
        json={"email": "new@ci.local", "display_name": "New", "role": "OPERATOR"},
    )

    assert response.status_code == 422
    error = response.json()["error"]
    assert error["code"] == "email_domain_undeliverable"
    assert error["message"] == "Tên miền email không nhận được thư, vui lòng kiểm tra lại."
    assert kc.created == []
    assert kc.sent == []


@pytest.mark.asyncio
async def test_resend_invite_to_reserved_domain_is_refused(
    client: AsyncClient, kc: _FakeAdmin
) -> None:
    kc.users.append(_kc_user("u-local", "invitee@ci.local", invited=True))
    app.dependency_overrides[get_current_user] = lambda: _principal("ADMINISTRATOR")

    response = await client.post("/api/v1/users/u-local/invite")

    assert response.status_code == 422
    assert response.json()["error"]["code"] == "email_domain_undeliverable"
    assert kc.sent == []
