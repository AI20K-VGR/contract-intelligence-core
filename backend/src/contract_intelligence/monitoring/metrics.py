"""Backend HTTP metrics for Prometheus.

Labels are bounded and carry no request data: the route *template*
(``/api/v1/dossiers/{dossier_id}``, never the id), the method and the status
class. Unmatched paths share one label so a scanner cannot blow up cardinality.

Metrics are served by ``prometheus_client``'s own HTTP server on
``METRICS_PORT`` — a port that is not published and not routed by Caddy — so
``/metrics`` never becomes part of the public API.
"""

from __future__ import annotations

import time
from typing import Any

from prometheus_client import Counter, Histogram, start_http_server
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from contract_intelligence.config.logging import get_logger

logger = get_logger(__name__)

HTTP_REQUESTS = Counter(
    "ci_backend_http_requests_total",
    "HTTP requests handled by the backend API.",
    ["method", "route", "status_class"],
)
HTTP_DURATION = Histogram(
    "ci_backend_http_request_duration_seconds",
    "Backend API request latency.",
    ["method", "route"],
    buckets=(0.01, 0.025, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60),
)

_METHODS = frozenset({"GET", "HEAD", "POST", "PUT", "PATCH", "DELETE", "OPTIONS"})
_UNMATCHED = "unmatched"

_server: Any = None


def _route_label(scope: Scope) -> str:
    route = scope.get("route")
    path = getattr(route, "path", None)
    return path if isinstance(path, str) else _UNMATCHED


class HttpMetricsMiddleware:
    """Pure ASGI middleware: no buffering, so SSE and the Grafana stream pass through."""

    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        status_code = 500
        started = time.perf_counter()

        async def send_with_status(message: Message) -> None:
            nonlocal status_code
            if message["type"] == "http.response.start":
                status_code = int(message["status"])
            await send(message)

        try:
            await self.app(scope, receive, send_with_status)
        finally:
            method = scope.get("method", "")
            method = method if method in _METHODS else "OTHER"
            route = _route_label(scope)
            HTTP_REQUESTS.labels(method, route, f"{status_code // 100}xx").inc()
            HTTP_DURATION.labels(method, route).observe(time.perf_counter() - started)


def start_metrics_server(port: int) -> None:
    """Expose /metrics on ``port``; a second call in the same process is a no-op."""
    global _server  # noqa: PLW0603
    if _server is not None:
        return
    try:
        _server, _thread = start_http_server(port)
    except OSError as exc:
        # Metrics must never stop the API from serving.
        logger.warning("metrics.server_failed", port=port, error=str(exc))
        return
    logger.info("metrics.server_started", port=port)


def stop_metrics_server() -> None:
    global _server  # noqa: PLW0603
    if _server is not None:
        _server.shutdown()
        _server.server_close()
        _server = None
