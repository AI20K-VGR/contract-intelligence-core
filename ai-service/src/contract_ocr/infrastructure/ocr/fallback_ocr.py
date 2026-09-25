"""Per-page fallback from a primary OCR engine to a secondary one, used only
when the primary can't serve the request at all (quota exhausted, out of
credits, rate limited) -- never for an ordinary transcription mistake, since
switching engines is not guaranteed to fix that and would mask the real
error instead of surfacing it.
"""

import logging
from typing import Any

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.domain.entities import Context, OCRResult

logger = logging.getLogger(__name__)

# HTTP statuses that mean "this API key/account cannot serve more requests
# right now", as opposed to a transient or content-specific failure.
# 402 Payment Required: out of credits (seen from Mistral's API).
# 403 Forbidden: some providers reuse this for a suspended/exhausted key.
# 429 Too Many Requests: rate limit or quota exceeded.
_QUOTA_STATUS_CODES = {402, 403, 429}
_QUOTA_MESSAGE_TOKENS = (
    "insufficient",
    "quota",
    "rate limit",
    "429",
    "out of credit",
    "credit balance",
)


def _is_quota_error(exc: Exception) -> bool:
    response = getattr(exc, "raw_response", None) or getattr(exc, "response", None)
    status = getattr(response, "status_code", None)
    if status in _QUOTA_STATUS_CODES:
        return True
    message = str(exc).lower()
    return any(token in message for token in _QUOTA_MESSAGE_TOKENS)


class FallbackOCREngine(OCREngine):
    """Delegates to `primary`; on a quota/rate-limit/no-credit error for a
    given page, retries that same page with `fallback` instead. Any other
    exception (a genuine transcription failure, a malformed image, etc.)
    propagates unchanged -- silently swapping engines would not fix it and
    would hide what actually went wrong.
    """

    def __init__(self, primary: OCREngine, fallback: OCREngine) -> None:
        self.primary = primary
        self.fallback = fallback
        self.name = primary.name
        self.model = primary.model
        self.runtime_info = primary.runtime_info

    def recognize_page(self, page_image: Any, context: Context) -> OCRResult:
        try:
            return self.primary.recognize_page(page_image, context)
        except EngineUnavailable:
            raise
        except Exception as exc:
            if not _is_quota_error(exc):
                raise
            logger.warning(
                "ocr.primary_quota_exhausted document_id=%s page=%s primary=%s "
                "falling_back_to=%s error=%s",
                context.document_id,
                context.page,
                self.primary.name,
                self.fallback.name,
                exc,
            )
            return self.fallback.recognize_page(page_image, context)
