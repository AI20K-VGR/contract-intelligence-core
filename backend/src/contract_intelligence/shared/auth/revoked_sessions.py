"""Keycloak sessions that ended, so their access tokens stop working at once.

An access token is checked offline (signature, ``exp``), so without this it
keeps working until it expires, up to 15 minutes after the user logged out or
an administrator disabled them. Keycloak tells the backend when a session ends
(OIDC back-channel logout); the session id (``sid``) lands here and every
access token carrying it is refused.

The registry lives in this process's memory and is checked on every request.
``shared/session_revocation.py`` keeps the durable copy in PostgreSQL and loads
it at startup. The API runs as one uvicorn process; with several processes a
revocation received by one would not reach the others.
"""

from __future__ import annotations

import threading
import time


class RevokedSessions:
    """``sid`` → until when (epoch seconds) its tokens are refused."""

    __slots__ = ("_lock", "_until")

    def __init__(self) -> None:
        self._until: dict[str, float] = {}
        self._lock = threading.Lock()

    def add(self, sid: str, until: float) -> None:
        with self._lock:
            self._until[sid] = max(until, self._until.get(sid, 0.0))
            self._drop_expired(time.time())

    def replace(self, entries: dict[str, float]) -> None:
        """Take the persisted set (startup); later ``add`` calls go on top."""
        now = time.time()
        with self._lock:
            self._until = {sid: until for sid, until in entries.items() if until > now}

    def is_revoked(self, sid: str | None) -> bool:
        if not sid:
            return False
        until = self._until.get(sid)
        return until is not None and until > time.time()

    def clear(self) -> None:
        with self._lock:
            self._until.clear()

    def __len__(self) -> int:
        return len(self._until)

    def _drop_expired(self, now: float) -> None:
        for sid in [s for s, until in self._until.items() if until <= now]:
            del self._until[sid]


revoked_sessions = RevokedSessions()

__all__ = ["RevokedSessions", "revoked_sessions"]
