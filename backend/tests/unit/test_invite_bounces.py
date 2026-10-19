"""Thư mời bị trả về: đọc thư báo lỗi và gắn vào người dùng còn "invited".

Gmail nhận mọi người nhận lúc gửi SMTP; địa chỉ không tồn tại chỉ báo về sau
bằng thư "Address not found" trong hộp thư gửi. Backend đọc thư đó và trả
``invite_delivery = "bounced"`` cho trang quản lý người dùng.
"""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from typing import Any

import pytest

from contract_intelligence.config.settings import Settings
from contract_intelligence.infrastructure import invite_bounces, keycloak_admin
from contract_intelligence.infrastructure.invite_bounces import Bounce, parse_bounce

GMAIL_DSN = b"""\
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
To: lexis.sender@gmail.com
Subject: Delivery Status Notification (Failure)
Date: Mon, 19 Oct 2026 09:30:05 -0700
X-Failed-Recipients: Sai.Ten@gmail.com
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b1"

--b1
Content-Type: text/plain; charset="UTF-8"

Address not found
Your message wasn't delivered to sai.ten@gmail.com because the address couldn't be found.

--b1
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com

Final-Recipient: rfc822; Sai.Ten@gmail.com
Action: failed
Status: 5.1.1
Diagnostic-Code: smtp; 550-5.1.1 The email account that you tried to reach does not exist.

--b1--
"""

DELAYED_DSN = b"""\
From: Mail Delivery Subsystem <mailer-daemon@googlemail.com>
Subject: Delivery Status Notification (Delay)
Date: Mon, 19 Oct 2026 09:30:05 +0000
MIME-Version: 1.0
Content-Type: multipart/report; report-type=delivery-status; boundary="b2"

--b2
Content-Type: text/plain

Delivery incomplete

--b2
Content-Type: message/delivery-status

Reporting-MTA: dns; googlemail.com

Final-Recipient: rfc822; slow@example.org
Action: delayed
Status: 4.4.7

--b2--
"""

PLAIN_BOUNCE = b"""\
From: postmaster@mail.example.org
Subject: Undeliverable
Date: Mon, 19 Oct 2026 10:00:00 +0000
X-Failed-Recipients: gone@example.org
Content-Type: text/plain

Remote server said: 550 mailbox rejected for policy reasons
"""


def test_gmail_address_not_found_is_a_mailbox_not_found_bounce() -> None:
    [bounce] = parse_bounce(GMAIL_DSN)
    assert bounce.email == "sai.ten@gmail.com"
    assert bounce.reason == "mailbox_not_found"
    assert bounce.at == datetime(2026, 10, 19, 16, 30, 5, tzinfo=UTC)


def test_a_delayed_notice_is_not_a_bounce() -> None:
    assert parse_bounce(DELAYED_DSN) == []


def test_x_failed_recipients_without_a_status_report() -> None:
    [bounce] = parse_bounce(PLAIN_BOUNCE)
    assert bounce.email == "gone@example.org"
    assert bounce.reason == "rejected"


def test_imap_defaults_to_gmail_and_the_smtp_account(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "smtp.gmail.com")
    monkeypatch.setenv("SMTP_USER", "lexis.sender@gmail.com")
    monkeypatch.setenv("SMTP_PASSWORD", "app-password")
    assert Settings().invite_bounce_imap() == (
        "imap.gmail.com",
        993,
        "lexis.sender@gmail.com",
        "app-password",
    )


def test_no_imap_check_for_mailpit(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("SMTP_HOST", "mailpit")
    monkeypatch.delenv("INVITE_BOUNCE_IMAP_HOST", raising=False)
    assert Settings().invite_bounce_imap() is None


# -----------------------------------------------------------------------------
# invite_delivery trên UserDTO
# -----------------------------------------------------------------------------


def _ms(when: datetime) -> str:
    return str(int(when.timestamp() * 1000))


def _invited(
    user_id: str = "kc-new", email: str = "sai.ten@gmail.com", **attributes: str
) -> dict[str, Any]:
    return {
        "id": user_id,
        "username": email,
        "email": email,
        "firstName": "Người mới",
        "enabled": True,
        "requiredActions": ["UPDATE_PASSWORD"],
        "attributes": {"tenant_id": ["t1"], **{k: [v] for k, v in attributes.items()}},
    }


@pytest.fixture
def check_on(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invite_bounces, "bounce_check_enabled", lambda: True)


def test_just_sent_invite_is_pending(check_on: None) -> None:
    sent = datetime.now(UTC) - timedelta(seconds=30)
    dto = keycloak_admin._to_user_dto(_invited(invite_sent_at=_ms(sent)), "OPERATOR")
    assert (dto.invite_delivery, dto.invite_delivery_reason) == ("pending", None)


def test_invite_without_bounce_after_the_wait_is_sent(check_on: None) -> None:
    sent = datetime.now(UTC) - timedelta(hours=1)
    dto = keycloak_admin._to_user_dto(_invited(invite_sent_at=_ms(sent)), "OPERATOR")
    assert dto.invite_delivery == "sent"


def test_recorded_bounce_is_reported(check_on: None) -> None:
    sent = datetime.now(UTC) - timedelta(minutes=5)
    user = _invited(
        invite_sent_at=_ms(sent),
        invite_bounced_at=_ms(sent + timedelta(seconds=10)),
        invite_bounce_reason="mailbox_not_found",
    )
    dto = keycloak_admin._to_user_dto(user, "OPERATOR")
    assert (dto.invite_delivery, dto.invite_delivery_reason) == ("bounced", "mailbox_not_found")


def test_unknown_without_mailbox_access(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(invite_bounces, "bounce_check_enabled", lambda: False)
    sent = datetime.now(UTC) - timedelta(seconds=30)
    dto = keycloak_admin._to_user_dto(_invited(invite_sent_at=_ms(sent)), "OPERATOR")
    assert dto.invite_delivery is None


def test_active_user_has_no_invite_delivery(check_on: None) -> None:
    user = _invited(invite_sent_at=_ms(datetime.now(UTC)))
    user["requiredActions"] = []
    assert keycloak_admin._to_user_dto(user, "OPERATOR").invite_delivery is None


# -----------------------------------------------------------------------------
# GET /users đối chiếu hộp thư và ghi lại thư trả về
# -----------------------------------------------------------------------------


class _FakeAdmin:
    def __init__(self, users: list[dict[str, Any]]) -> None:
        self.users = users
        self.updates: list[tuple[str, dict[str, Any]]] = []
        self.sent_to: list[str] = []

    def get_users(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return self.users

    def get_user(self, user_id: str) -> dict[str, Any]:
        return next(user for user in self.users if user["id"] == user_id)

    def get_realm_roles_of_user(self, user_id: str) -> list[dict[str, Any]]:
        return [{"name": "OPERATOR"}]

    def get_events(self, query: dict[str, Any]) -> list[dict[str, Any]]:
        return []

    def update_user(self, user_id: str, payload: dict[str, Any]) -> None:
        self.updates.append((user_id, payload))
        user = self.get_user(user_id)
        user["attributes"] = payload.get("attributes", user.get("attributes"))

    def send_update_account(self, user_id: str, **kwargs: Any) -> None:
        self.sent_to.append(user_id)


def _use(monkeypatch: pytest.MonkeyPatch, admin: _FakeAdmin, bounces: dict[str, Bounce]) -> None:
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)
    monkeypatch.setattr(invite_bounces, "recent_bounces", lambda since: bounces)


def _list() -> list[Any]:
    return keycloak_admin._list_users_sync(
        q=None, role=None, status=None, limit=20, offset=0, tenant_id="t1"
    ).items


def test_list_marks_and_saves_a_bounce_after_the_invite(
    monkeypatch: pytest.MonkeyPatch, check_on: None
) -> None:
    sent = datetime.now(UTC) - timedelta(minutes=1)
    admin = _FakeAdmin([_invited(invite_sent_at=_ms(sent))])
    bounce_at = sent + timedelta(seconds=8)
    _use(
        monkeypatch,
        admin,
        {"sai.ten@gmail.com": Bounce("sai.ten@gmail.com", bounce_at, "mailbox_not_found")},
    )

    [dto] = _list()

    assert (dto.invite_delivery, dto.invite_delivery_reason) == ("bounced", "mailbox_not_found")
    [(user_id, payload)] = admin.updates
    assert user_id == "kc-new"
    assert payload["attributes"]["invite_bounced_at"] == [_ms(bounce_at)]
    assert payload["attributes"]["invite_bounce_reason"] == ["mailbox_not_found"]
    assert payload["attributes"]["tenant_id"] == ["t1"]
    assert payload["email"] == "sai.ten@gmail.com"


def test_bounce_of_an_earlier_invite_is_ignored(
    monkeypatch: pytest.MonkeyPatch, check_on: None
) -> None:
    sent = datetime.now(UTC) - timedelta(minutes=1)
    admin = _FakeAdmin([_invited(invite_sent_at=_ms(sent))])
    old = sent - timedelta(hours=2)
    _use(
        monkeypatch,
        admin,
        {"sai.ten@gmail.com": Bounce("sai.ten@gmail.com", old, "mailbox_not_found")},
    )

    [dto] = _list()

    assert dto.invite_delivery == "pending"
    assert admin.updates == []


def test_no_mailbox_read_without_a_waiting_invite(
    monkeypatch: pytest.MonkeyPatch, check_on: None
) -> None:
    admin = _FakeAdmin([_invited()])  # mời trước khi có invite_sent_at
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)

    def _fail(since: datetime) -> dict[str, Bounce]:
        raise AssertionError("mailbox must not be read")

    monkeypatch.setattr(invite_bounces, "recent_bounces", _fail)

    [dto] = _list()

    assert dto.invite_delivery is None


def test_resend_restarts_the_wait(monkeypatch: pytest.MonkeyPatch, check_on: None) -> None:
    sent = datetime.now(UTC) - timedelta(hours=1)
    admin = _FakeAdmin(
        [
            _invited(
                invite_sent_at=_ms(sent),
                invite_bounced_at=_ms(sent + timedelta(seconds=5)),
                invite_bounce_reason="mailbox_not_found",
            )
        ]
    )
    monkeypatch.setattr(keycloak_admin, "_build_keycloak_admin", lambda: admin)

    dto = keycloak_admin._resend_invite_sync(user_id="kc-new")

    assert admin.sent_to == ["kc-new"]
    assert (dto.invite_delivery, dto.invite_delivery_reason) == ("pending", None)
    attributes = admin.updates[-1][1]["attributes"]
    assert "invite_bounced_at" not in attributes
    assert "invite_bounce_reason" not in attributes
    assert int(attributes["invite_sent_at"][0]) > int(_ms(sent))
