"""Thư mời bị trả về, đọc từ hộp thư mà Keycloak dùng để gửi.

Gmail (và phần lớn máy chủ chuyển thư) nhận mọi người nhận lúc gửi SMTP, nên
``POST /users`` thành công cả khi ``sai-ten@gmail.com`` không tồn tại. Vài giây
tới vài phút sau, máy chủ thư gửi một thư báo lỗi (DSN, RFC 3464) về hộp thư
gửi: "Address not found". Module này đọc các thư đó qua IMAP (chỉ đọc, không
đánh dấu đã đọc) và trả về người nhận nào bị từ chối, lúc nào, vì sao.

Không cấu hình IMAP (``Settings.invite_bounce_imap``) thì không kiểm tra gì.
Một lần đọc được giữ ``_CACHE_SECONDS`` để trang người dùng hỏi lại liên tục
không mở một phiên IMAP mỗi lần; IMAP lỗi thì chờ ``_FAILURE_CACHE_SECONDS`` mới
thử lại, để ``GET /users`` không lần nào cũng chờ timeout. Thư đã đọc được nhớ
theo UID (thư báo lỗi không đổi), nên mỗi lần chỉ tải thư mới, gom trong một lệnh.
"""

from __future__ import annotations

import email
import imaplib
import re
import threading
import time
from dataclasses import dataclass
from datetime import UTC, date, datetime
from email.message import Message
from email.policy import default as default_policy
from email.utils import parsedate_to_datetime

import structlog

from contract_intelligence.config.settings import get_settings
from contract_intelligence.schemas.users import InviteBounceReason

logger = structlog.get_logger(__name__)

_CACHE_SECONDS = 20.0
_FAILURE_CACHE_SECONDS = 60.0
_IMAP_TIMEOUT_SECONDS = 10.0
# Thư báo lỗi mới nhất được đọc trong một lần; hộp thư gửi ít khi có nhiều hơn.
_MAX_MESSAGES = 200
# Chỉ tải phần đầu mỗi thư: phần delivery-status nằm trước thư gốc đính kèm.
_FETCH_BYTES = 65536
_UID_RE = re.compile(rb"\bUID (\d+)")
# IMAP SINCE cần tên tháng tiếng Anh, không phụ thuộc locale như strftime("%b").
_MONTHS = ("Jan", "Feb", "Mar", "Apr", "May", "Jun", "Jul", "Aug", "Sep", "Oct", "Nov", "Dec")
_NOT_FOUND_STATUSES = frozenset({"5.1.0", "5.1.1", "5.1.10"})
_NOT_FOUND_RE = re.compile(
    r"does not exist|doesn't exist|address not found|couldn't be found|could not be found"
    r"|no such user|user unknown|unknown user|recipient not found|mailbox unavailable",
    re.IGNORECASE,
)
_ADDRESS_RE = re.compile(r"[^\s<>;,]+@[^\s<>;,]+")


@dataclass(frozen=True, slots=True)
class Bounce:
    """Một người nhận bị máy chủ thư từ chối hẳn (không phải báo chậm 4.x.x)."""

    email: str
    at: datetime
    reason: InviteBounceReason


@dataclass(frozen=True, slots=True)
class MailboxRead:
    """Một lần đọc hộp thư gửi thành công: lúc đọc và thư trả về theo email."""

    at: datetime
    bounces: dict[str, Bounce]


_lock = threading.Lock()
# (lúc đọc theo time.monotonic, ngày SINCE đã dùng, kết quả; None khi lần đó lỗi)
_cache: tuple[float, date, MailboxRead | None] | None = None
# Thư đã parse, theo (UIDVALIDITY, UID).
_parsed: dict[tuple[bytes, bytes], list[Bounce]] = {}


def bounce_check_enabled() -> bool:
    return get_settings().invite_bounce_imap() is not None


def recent_bounces(since: datetime) -> MailboxRead | None:
    """Thư trả về từ ngày của ``since``; None khi không đọc được hộp thư.

    Mỗi email (casefold) giữ thư mới nhất. ``MailboxRead.at`` là lúc đọc hộp thư,
    có thể đã cách tới ``_CACHE_SECONDS``. None khi chưa cấu hình IMAP hoặc IMAP
    lỗi (đã ghi log).
    """
    global _cache
    conf = get_settings().invite_bounce_imap()
    if conf is None:
        return None
    day = since.astimezone(UTC).date()
    with _lock:
        if _cache is not None:
            read_at, cached_day, cached = _cache
            age = time.monotonic() - read_at
            if cached is None and age < _FAILURE_CACHE_SECONDS:
                return None
            if cached is not None and age < _CACHE_SECONDS and cached_day <= day:
                return cached
        try:
            found = _read_bounces(*conf, day=day)
        except (imaplib.IMAP4.error, OSError) as exc:
            logger.warning(
                "invite_bounces.imap_failed", host=conf[0], error_type=type(exc).__name__
            )
            _cache = (time.monotonic(), day, None)
            return None
        result = MailboxRead(at=datetime.now(UTC), bounces=found)
        _cache = (time.monotonic(), day, result)
        return result


def clear_cache() -> None:
    global _cache
    with _lock:
        _cache = None
        _parsed.clear()


def _read_bounces(
    host: str, port: int, user: str, password: str, *, day: date
) -> dict[str, Bounce]:
    since = f"{day.day:02d}-{_MONTHS[day.month - 1]}-{day.year}"
    with imaplib.IMAP4_SSL(host, port, timeout=_IMAP_TIMEOUT_SECONDS) as imap:
        imap.login(user, password)
        imap.select("INBOX", readonly=True)
        _, validity = imap.response("UIDVALIDITY")
        uid_validity = validity[0] if validity and isinstance(validity[0], bytes) else b""
        _, data = imap.uid(
            "SEARCH", "SINCE", since, "OR", "FROM", "mailer-daemon", "FROM", "postmaster"
        )
        uids: list[bytes] = (data[0] or b"").split()[-_MAX_MESSAGES:] if data else []
        new = [uid for uid in uids if (uid_validity, uid) not in _parsed]
        if new:
            # Một lệnh cho mọi thư mới, thay vì một vòng hỏi đáp mỗi thư.
            _, parts = imap.uid(
                "FETCH", b",".join(new).decode(), f"(BODY.PEEK[]<0.{_FETCH_BYTES}>)"
            )
            fetched: dict[bytes, list[Bounce]] = {}
            for part in parts or []:
                if not (isinstance(part, tuple) and len(part) > 1):
                    continue
                match = _UID_RE.search(part[0]) if isinstance(part[0], bytes) else None
                if match is not None and isinstance(part[1], bytes):
                    fetched[match.group(1)] = parse_bounce(part[1])
            for uid in new:
                # Thư bị xoá giữa SEARCH và FETCH thì không có gì để đọc.
                _parsed[(uid_validity, uid)] = fetched.get(uid, [])
    # Chỉ giữ thư còn trong lần SEARCH này, để bộ nhớ không lớn dần.
    keep = {(uid_validity, uid) for uid in uids}
    for key in [key for key in _parsed if key not in keep]:
        del _parsed[key]
    found: dict[str, Bounce] = {}
    for uid in uids:
        for bounce in _parsed.get((uid_validity, uid), []):
            kept = found.get(bounce.email)
            if kept is None or bounce.at > kept.at:
                found[bounce.email] = bounce
    return found


def parse_bounce(raw: bytes) -> list[Bounce]:
    """Người nhận bị từ chối hẳn trong một thư báo lỗi; [] khi không phải thư như vậy."""
    message = email.message_from_bytes(raw, policy=default_policy)
    at = _message_time(message)
    if at is None:
        return []
    failed = _delivery_status_failures(message)
    # Có phần delivery-status thì chỉ tin phần đó: "delayed" (4.x.x) không phải
    # bị trả về dù thư có X-Failed-Recipients. Không có thì chỉ tin header khi
    # thư đến từ người gửi rỗng (Return-Path <>), như mọi thư báo lỗi thật.
    if failed is None:
        if not _from_null_sender(message):
            return []
        header = str(message.get("X-Failed-Recipients") or "")
        reason = _reason("", _body_text(message))
        failed = [(address, reason) for address in _addresses(header)]
    return [Bounce(email=address, at=at, reason=reason) for address, reason in failed]


def _message_time(message: Message) -> datetime | None:
    raw = message.get("Date")
    if not raw:
        return None
    try:
        when = parsedate_to_datetime(str(raw))
    except (TypeError, ValueError):
        return None
    return when.replace(tzinfo=UTC) if when.tzinfo is None else when.astimezone(UTC)


def _from_null_sender(message: Message) -> bool:
    return str(message.get("Return-Path") or "").strip() == "<>"


def _delivery_status_failures(
    message: Message,
) -> list[tuple[str, InviteBounceReason]] | None:
    """Người nhận thất bại hẳn theo phần delivery-status; None khi thư không có phần đó."""
    failed: list[tuple[str, InviteBounceReason]] | None = None
    for part in message.walk():
        if part.get_content_type() != "message/delivery-status":
            continue
        if failed is None:
            failed = []
        blocks = part.get_payload()
        if not isinstance(blocks, list):
            continue
        for block in blocks:
            if not isinstance(block, Message):
                continue
            action = str(block.get("Action") or "").strip().lower()
            status = str(block.get("Status") or "").strip()
            if action != "failed" and not status.startswith("5"):
                continue
            recipient = str(block.get("Final-Recipient") or block.get("Original-Recipient") or "")
            for address in _addresses(recipient.rpartition(";")[2]):
                failed.append((address, _reason(status, str(block.get("Diagnostic-Code") or ""))))
    return failed


def _addresses(value: str) -> list[str]:
    return [match.casefold() for match in _ADDRESS_RE.findall(value or "")]


def _reason(status: str, text: str) -> InviteBounceReason:
    if status in _NOT_FOUND_STATUSES or _NOT_FOUND_RE.search(text):
        return "mailbox_not_found"
    return "rejected"


def _body_text(message: Message) -> str:
    chunks: list[str] = []
    for part in message.walk():
        if part.get_content_type() != "text/plain":
            continue
        payload = part.get_payload(decode=True)
        if isinstance(payload, bytes):
            charset = part.get_content_charset() or "utf-8"
            try:
                chunks.append(payload.decode(charset, errors="replace"))
            except LookupError:
                chunks.append(payload.decode("utf-8", errors="replace"))
    return "\n".join(chunks)


__all__ = [
    "Bounce",
    "MailboxRead",
    "bounce_check_enabled",
    "clear_cache",
    "parse_bounce",
    "recent_bounces",
]
