"""Cross-cutting HTTP middleware — X-Backend-Version + X-Request-Id."""

from __future__ import annotations

import re
import uuid
from collections.abc import Awaitable, Callable

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import Response

from contract_intelligence.config.logging import get_logger
from contract_intelligence.config.settings import get_settings
from contract_intelligence.shared.versioning import __api_contract__, full_version

logger = get_logger(__name__)

# A client-sent id is echoed in a header and written to logs: keep it plain.
_REQUEST_ID = re.compile(r"[A-Za-z0-9._:-]{1,128}")


class BackendHeadersMiddleware(BaseHTTPMiddleware):
    """Inject headers chuẩn vào MỌI response:

        X-Backend-Version  : ``1.0.0+sprint3-full-api`` — chỉ ở dev/test; staging/prod
                            không cho người ngoài biết phiên bản để dò CVE
        X-Request-Id       : UUIDv4 sinh bởi server (echo ``X-Request-Id`` header
                            từ client nếu có, để truy vết đầu cuối)
        X-API-Contract     : ``__api_contract__`` — DOC-05b version hiện tại

    Lý do:
        - Client verify compatibility trước khi parse response.
        - Server log mọi request với request_id để truy vết.
        - Hỗ trợ idempotent retries: client gửi cùng X-Request-Id → server log
          cùng correlation id.
    """

    async def dispatch(
        self,
        request: Request,
        call_next: Callable[[Request], Awaitable[Response]],
    ) -> Response:
        # Honor client-provided X-Request-Id nếu hợp lệ; nếu không sinh mới
        sent = request.headers.get("X-Request-Id") or ""
        request_id = sent if _REQUEST_ID.fullmatch(sent) else str(uuid.uuid4())
        # Stash trong request.state để router/exception handler truy cập
        request.state.request_id = request_id

        response = await call_next(request)
        if not get_settings().exposed:
            response.headers["X-Backend-Version"] = full_version()
        response.headers["X-API-Contract"] = __api_contract__
        response.headers["X-Request-Id"] = request_id
        return response


__all__ = ["BackendHeadersMiddleware"]
