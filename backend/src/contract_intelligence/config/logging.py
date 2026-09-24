"""Logging setup — structured logging với structlog.

Mặc định output JSON cho production, console cho dev. Tích hợp
OpenTelemetry trace_id/span_id nếu exporter đang chạy.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

from contract_intelligence.config.settings import get_settings


def configure_logging() -> None:
    """Cấu hình logging cho toàn bộ process — gọi 1 lần ở ``main.py``.

    Idempotent — gọi nhiều lần cũng không sao.
    """
    settings = get_settings()
    is_dev = settings.env in {"dev", "test"}

    # Standard logging — chuyển qua structlog renderer
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stdout,
        level=logging.DEBUG if settings.debug else logging.INFO,
    )

    processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.processors.add_log_level,
        structlog.processors.TimeStamper(fmt="iso", utc=True),
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    if is_dev:
        # structlog chỉ tô màu trên Windows khi đã cài colorama.
        use_colors = True
        if sys.platform == "win32":
            try:
                import colorama  # noqa: F401
            except ImportError:
                use_colors = False
        processors.append(structlog.dev.ConsoleRenderer(colors=use_colors))
    else:
        processors.append(structlog.processors.JSONRenderer())

    structlog.configure(
        processors=processors,
        wrapper_class=structlog.make_filtering_bound_logger(
            logging.DEBUG if settings.debug else logging.INFO,
        ),
        context_class=dict,
        logger_factory=structlog.PrintLoggerFactory(),
        cache_logger_on_first_use=True,
    )


def get_logger(name: str | None = None) -> Any:
    """Shorthand cho ``structlog.get_logger``."""
    return structlog.get_logger(name)
