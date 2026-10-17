"""``Server-Timing`` header: how long the API spent on a request, and in SQL.

The browser shows it in DevTools (Network → Timing) and in the Resource Timing
API, so a slow request can be split into server time and network time without
access to the server:

    Server-Timing: app;dur=412.3, db;dur=35.1;desc="7 queries"

``app`` runs from the request reaching this middleware to the response headers
(for a streamed body, the time to first byte). ``db`` sums every SQL statement
the request ran, on any engine, and counts them (a high count points to N+1).

``Timing-Allow-Origin`` lists the CORS origins so the frontend, on another
origin, can read the values from ``performance.getEntriesByType('resource')``.
"""

from __future__ import annotations

import time
from contextvars import ContextVar
from dataclasses import dataclass
from typing import Any

from sqlalchemy import Engine, event
from starlette.datastructures import MutableHeaders
from starlette.types import ASGIApp, Message, Receive, Scope, Send


@dataclass
class _Stats:
    db_seconds: float = 0.0
    db_queries: int = 0


# Mutable stats object per request. SQLAlchemy's async engines run statements
# in a greenlet that carries this context, so the listeners below see it.
_current: ContextVar[_Stats | None] = ContextVar("server_timing", default=None)
_STARTED = "_server_timing_started"
_listening = False


def _before(
    conn: Any, _cursor: Any, _statement: Any, _params: Any, _context: Any, _many: Any
) -> None:
    if _current.get() is not None:
        conn.info.setdefault(_STARTED, []).append(time.perf_counter())


def _after(
    conn: Any, _cursor: Any, _statement: Any, _params: Any, _context: Any, _many: Any
) -> None:
    stats = _current.get()
    started = conn.info.get(_STARTED)
    if stats is None or not started:
        return
    stats.db_seconds += time.perf_counter() - started.pop()
    stats.db_queries += 1


def listen_for_queries() -> None:
    """Time SQL on every engine; idempotent."""
    global _listening  # noqa: PLW0603
    if _listening:
        return
    event.listen(Engine, "before_cursor_execute", _before)
    event.listen(Engine, "after_cursor_execute", _after)
    _listening = True


class ServerTimingMiddleware:
    """Pure ASGI middleware: no buffering, so SSE streams pass through."""

    def __init__(self, app: ASGIApp, *, allow_origins: list[str] | None = None) -> None:
        self.app = app
        origins = [o for o in (allow_origins or []) if o]
        self._allow_origin = "*" if "*" in origins else ", ".join(origins)
        listen_for_queries()

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        stats = _Stats()
        token = _current.set(stats)
        started = time.perf_counter()

        async def send_with_timing(message: Message) -> None:
            if message["type"] == "http.response.start":
                app_ms = (time.perf_counter() - started) * 1000
                headers = MutableHeaders(scope=message)
                headers.append(
                    "Server-Timing",
                    f"app;dur={app_ms:.1f}, "
                    f'db;dur={stats.db_seconds * 1000:.1f};desc="{stats.db_queries} queries"',
                )
                if self._allow_origin:
                    headers["Timing-Allow-Origin"] = self._allow_origin
            await send(message)

        try:
            await self.app(scope, receive, send_with_timing)
        finally:
            _current.reset(token)


__all__ = ["ServerTimingMiddleware", "listen_for_queries"]
