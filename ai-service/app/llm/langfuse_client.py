"""AI2's own Langfuse client: AI2's image ships ``app/`` only, never AI1's ``src/``.

Same switches as AI1 (``LANGFUSE_PUBLIC_KEY``/``LANGFUSE_SECRET_KEY``,
``LANGFUSE_BASE_URL`` or ``LANGFUSE_HOST``, ``LANGFUSE_TRACING_ENABLED``) and the
same last-line mask for credentials in span attributes. Tracing must never make
AI2 unavailable: any failure here means no client.
"""

from __future__ import annotations

import logging
import os
import re
from functools import lru_cache
from typing import Any

try:
    from langfuse import Langfuse
    from langfuse.types import MaskOtelSpansResult, OtelSpanPatch
except ImportError:  # pragma: no cover - langfuse is a core dependency
    Langfuse = None  # type: ignore[assignment,misc]
    MaskOtelSpansResult = OtelSpanPatch = None  # type: ignore[assignment,misc]

logger = logging.getLogger(__name__)

_FALSE_VALUES = {"0", "false", "no", "off"}
_SECRET_PATTERN = re.compile(
    r"(?i)(?:bearer\s+|(?:sk|pk)-[a-z0-9_-]{8,}|"
    r"(?:x-amz-signature|x-amz-credential)=[^&\s]+)"
)


def _enabled() -> bool:
    explicit = os.environ.get("LANGFUSE_TRACING_ENABLED", "true").strip().lower()
    return (
        Langfuse is not None
        and explicit not in _FALSE_VALUES
        and bool(os.environ.get("LANGFUSE_PUBLIC_KEY"))
        and bool(os.environ.get("LANGFUSE_SECRET_KEY"))
        and bool(os.environ.get("LANGFUSE_BASE_URL") or os.environ.get("LANGFUSE_HOST"))
    )


def redact(value: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", value)


def mask_otel_spans(*, params: Any) -> Any:
    """Last-line defense against credentials leaking through span attributes."""
    patches: dict[str, Any] = {}
    for identifier, span in params.spans.items():
        replacements: dict[str, str] = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = redact(value)
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches)


@lru_cache(maxsize=1)
def get_langfuse() -> Any | None:
    """Return the configured singleton, or ``None`` when tracing is disabled."""
    if not _enabled():
        return None
    try:
        return Langfuse(mask_otel_spans=mask_otel_spans)
    except Exception:
        logger.exception("ai2.langfuse.initialization_failed")
        return None


def flush_langfuse() -> None:
    client = get_langfuse()
    if client is not None:
        try:
            client.flush()
        except Exception:
            logger.exception("ai2.langfuse.flush_failed")


def reset_langfuse_for_tests() -> None:
    """Clear cached configuration after tests mutate environment variables."""
    get_langfuse.cache_clear()


__all__ = [
    "flush_langfuse",
    "get_langfuse",
    "mask_otel_spans",
    "redact",
    "reset_langfuse_for_tests",
]
