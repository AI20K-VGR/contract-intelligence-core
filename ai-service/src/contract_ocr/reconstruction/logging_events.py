"""Structured event logging for the reconstruction pipeline (section 18).

Every event is a small JSON object with an `event` name and identifying
fields (document id, page range, decision). Full contract text is never
logged — only counts, ids and decisions.
"""

from __future__ import annotations

import json
import logging
from typing import Any

logger = logging.getLogger("contract_ocr.reconstruction")


def log_event(event: str, **fields: Any) -> None:
    logger.info(json.dumps({"event": event, **fields}, ensure_ascii=False))
