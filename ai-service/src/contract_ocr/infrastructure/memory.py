"""Give memory back to the OS after a large OCR job.

Same helper as AI2's ``app/ops/memory.py`` (the two images share no code).

Housekeeping, not the fix: what kept the services' memory high was objects
kept after each job (fixed where they were kept). A job's freed memory mostly
goes back by itself; ``malloc_trim`` returns what glibc still holds in free
heap pages, and ``MALLOC_ARENA_MAX`` (docker-compose.yml) keeps the number of
per-thread heaps small. Measured on a simulated 200-page job: a few MiB.
"""

from __future__ import annotations

import ctypes
import ctypes.util
import gc
import logging
import sys
from functools import cache

logger = logging.getLogger(__name__)


@cache
def _malloc_trim():
    if not sys.platform.startswith("linux"):
        return None
    name = ctypes.util.find_library("c")
    if not name:
        return None
    try:
        trim = ctypes.CDLL(name).malloc_trim
    except (OSError, AttributeError):  # musl and other libcs have no malloc_trim
        return None
    trim.argtypes = [ctypes.c_size_t]
    trim.restype = ctypes.c_int
    return trim


def release_memory() -> bool:
    """Collect garbage, then hand free heap pages back to the OS.

    Returns whether ``malloc_trim`` ran. Never raises: this is housekeeping
    after a job, not part of its result.
    """

    try:
        gc.collect()
        trim = _malloc_trim()
        if trim is None:
            return False
        trim(0)
        return True
    except Exception:  # pragma: no cover - defensive
        logger.debug("memory.release_failed", exc_info=True)
        return False
