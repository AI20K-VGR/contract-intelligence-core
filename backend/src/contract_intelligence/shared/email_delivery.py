"""Addresses that can never receive mail, so the backend does not send to them.

Reserved names (RFC 2606, RFC 6761, RFC 6762) have no public mail exchanger: a message
sent there bounces back into the sender's mailbox. The demo accounts in
``keycloak/realm-export.json`` use ``@ci.local``.

A mailbox that does not exist on a real domain (``wrong-name@gmail.com``) cannot be
detected before sending; only a bounce or a provider webhook reports it.
"""

from __future__ import annotations

import structlog

logger = structlog.get_logger(__name__)

_RESERVED_TLDS = frozenset({"local", "test", "example", "invalid", "localhost"})
_RESERVED_DOMAINS = frozenset({"example.com", "example.net", "example.org"})

UNDELIVERABLE_MESSAGE = "Tên miền email không nhận được thư, vui lòng kiểm tra lại."


def email_domain(address: str) -> str:
    """Lower-case domain of ``address`` without a trailing dot; empty when there is none."""
    _, sep, domain = (address or "").strip().rpartition("@")
    return domain.strip().rstrip(".").lower() if sep else ""


def is_undeliverable_email(address: str) -> bool:
    """True when ``address`` has no domain or a domain reserved for local or test use."""
    domain = email_domain(address)
    if not domain:
        return True
    labels = domain.split(".")
    return labels[-1] in _RESERVED_TLDS or ".".join(labels[-2:]) in _RESERVED_DOMAINS


def skip_undeliverable(address: str, *, purpose: str, **context: object) -> bool:
    """Log ``email.skipped_undeliverable`` and return True when ``address`` cannot get mail."""
    if not is_undeliverable_email(address):
        return False
    logger.info(
        "email.skipped_undeliverable",
        purpose=purpose,
        domain=email_domain(address) or None,
        **context,
    )
    return True


__all__ = [
    "UNDELIVERABLE_MESSAGE",
    "email_domain",
    "is_undeliverable_email",
    "skip_undeliverable",
]
