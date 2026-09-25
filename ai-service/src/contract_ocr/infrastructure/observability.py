"""Privacy-safe Langfuse tracing helpers for the OCR runtime.

The contract body and rendered page images are intentionally never attached to
observations.  Traces contain operational metadata and aggregate output counts
only; this keeps observability useful without copying customer contracts into a
second system.
"""

from __future__ import annotations

import logging
import os
import re
from contextlib import contextmanager
from functools import lru_cache
from typing import Any, Iterator

try:
    from langfuse import Langfuse, propagate_attributes
    from langfuse.types import MaskOtelSpansParams, MaskOtelSpansResult, OtelSpanPatch
except ImportError:  # pragma: no cover - exercised only when langfuse isn't installed
    Langfuse = None  # type: ignore[assignment,misc]
    propagate_attributes = None  # type: ignore[assignment]
    MaskOtelSpansParams = MaskOtelSpansResult = OtelSpanPatch = None  # type: ignore[assignment,misc]

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


def _redact(value: str) -> str:
    return _SECRET_PATTERN.sub("[REDACTED]", value)


def _mask_otel_spans(*, params: MaskOtelSpansParams) -> MaskOtelSpansResult:
    """Last-line defense against credentials leaking through span attributes."""
    patches: dict[str, OtelSpanPatch] = {}
    for identifier, span in params.spans.items():
        replacements: dict[str, str] = {}
        for key, value in span.attributes.items():
            if isinstance(value, str):
                masked = _redact(value)
                if masked != value:
                    replacements[key] = masked
        if replacements:
            patches[identifier] = OtelSpanPatch(set_attributes=replacements)
    return MaskOtelSpansResult(span_patches=patches)


@lru_cache(maxsize=1)
def get_langfuse() -> Langfuse | None:
    """Return the configured singleton, or ``None`` when tracing is disabled."""
    if not _enabled():
        return None
    try:
        return Langfuse(mask_otel_spans=_mask_otel_spans)
    except Exception:
        # Observability must never make OCR unavailable.
        logger.exception("langfuse.initialization_failed")
        return None


@contextmanager
def observation(
    name: str,
    *,
    as_type: str = "span",
    input: dict[str, Any] | None = None,
    metadata: dict[str, Any] | None = None,
    model: str | None = None,
    model_parameters: dict[str, Any] | None = None,
    trace_seed: str | None = None,
    session_id: str | None = None,
    tags: list[str] | None = None,
) -> Iterator[Any | None]:
    """Create a nested observation while degrading to a no-op when unconfigured.

    Callers must pass sanitized metadata only.  In particular, do not pass PDF
    bytes, page images, OCR text, prompts containing contract text, API keys, or
    presigned storage URLs.
    """
    client = get_langfuse()
    if client is None:
        yield None
        return

    trace_context = None
    if trace_seed:
        trace_context = {"trace_id": client.create_trace_id(seed=trace_seed)}

    with client.start_as_current_observation(
        name=name,
        as_type=as_type,
        input=input,
        metadata=metadata,
        model=model,
        model_parameters=model_parameters,
        trace_context=trace_context,
    ) as current:
        with propagate_attributes(
            trace_name=name if trace_seed else None,
            session_id=session_id,
            tags=tags,
            metadata=metadata,
        ):
            yield current


def response_usage(response: Any) -> dict[str, int] | None:
    """Normalize token/page counters exposed by supported provider SDKs."""
    source = (
        getattr(response, "usage", None)
        or getattr(response, "usage_metadata", None)
        or getattr(response, "usage_info", None)
    )
    if source is None:
        return None

    aliases = {
        "input": ("input_tokens", "prompt_tokens", "prompt_token_count"),
        "output": ("output_tokens", "completion_tokens", "candidates_token_count"),
        "total": ("total_tokens", "total_token_count"),
        "pages_processed": ("pages_processed",),
        "document_size_bytes": ("doc_size_bytes", "document_size_bytes"),
    }
    result: dict[str, int] = {}
    for target, names in aliases.items():
        for name in names:
            value = source.get(name) if isinstance(source, dict) else getattr(source, name, None)
            if isinstance(value, int):
                result[target] = value
                break
    return result or None


def flush_langfuse() -> None:
    client = get_langfuse()
    if client is not None:
        try:
            client.flush()
        except Exception:
            logger.exception("langfuse.flush_failed")


def reset_langfuse_for_tests() -> None:
    """Clear cached configuration after tests mutate environment variables."""
    get_langfuse.cache_clear()


__all__ = [
    "flush_langfuse",
    "get_langfuse",
    "observation",
    "reset_langfuse_for_tests",
    "response_usage",
]
