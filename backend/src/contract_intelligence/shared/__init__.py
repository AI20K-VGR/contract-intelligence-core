"""Shared kernel — shared types & cross-cutting concerns.

Mọi bounded context đều được phép import từ ``shared/`` mà KHÔNG vi phạm
Dependency Rule. Đây là **shared kernel** theo nghĩa DDD.

Quy tắc:
- Package initializer phải **framework-free** (không import FastAPI/JWT/SQLAlchemy).
  Domain entities import ``shared.base`` / ``shared.exceptions``; nếu ``__init__``
  kéo ``shared.auth`` thì mọi domain load FastAPI qua transitive import.
- Auth sống trong ``shared.auth`` — callers import trực tiếp từ đó.
- ORM/Pydantic đặt trong sub-module riêng (``shared/persistence/`` …).
"""

from contract_intelligence.shared.base import BaseEntity, BaseRepository

__all__ = [
    "BaseEntity",
    "BaseRepository",
]
