"""Bounded in-process caches.

AI2 is a long-lived process: a module-level dict that gains one entry per job
or dossier and never drops any grows until the container runs out of memory.
Durable state lives in Postgres (``JOB_STORE``, ``ai2.dossier_query_snapshots``);
these maps are only caches in front of it, so they keep the most recent
entries and forget the rest.
"""

from __future__ import annotations

import os
from collections import OrderedDict
from typing import TypeVar

K = TypeVar("K")
V = TypeVar("V")


class BoundedDict(OrderedDict[K, V]):
    """Insertion-ordered dict that drops its oldest entries past ``maxsize``.

    ``maxsize=None`` means unbounded. Writing a key marks it most recent;
    ``touch`` does the same for a read, which makes the map an LRU.
    """

    def __init__(self, maxsize: int | None = None) -> None:
        super().__init__()
        if maxsize is not None and maxsize < 1:
            raise ValueError("maxsize must be at least 1")
        self.maxsize = maxsize

    def __setitem__(self, key: K, value: V) -> None:
        super().__setitem__(key, value)
        self.move_to_end(key)
        if self.maxsize is not None:
            while len(self) > self.maxsize:
                self.popitem(last=False)

    def touch(self, key: K) -> None:
        if key in self:
            self.move_to_end(key)


def env_capacity(name: str, default: int | None) -> int | None:
    """Capacity from ``name``: a positive integer, ``0`` for unbounded, else ``default``."""

    raw = (os.getenv(name) or "").strip()
    if not raw:
        return default
    try:
        value = int(raw)
    except ValueError:
        return default
    if value == 0:
        return None
    return value if value > 0 else default
