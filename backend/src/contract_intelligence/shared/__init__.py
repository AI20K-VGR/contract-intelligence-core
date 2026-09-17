"""Shared kernel — shared types & cross-cutting concerns.

Mọi bounded context đều được phép import từ ``shared/`` mà KHÔNG vi phạm
Dependency Rule. Đây là **shared kernel** theo nghĩa DDD.

Quy tắc:
- **KHÔNG** import framework (FastAPI, SQLAlchemy) trực tiếp từ ``shared/``.
- Nếu cần ORM/Pydantic, đặt trong sub-module riêng (``shared/persistence/`` chẳng hạn)
  và bounded context tự quyết định có dùng hay không.
"""

from contract_intelligence.shared.base import BaseEntity, BaseRepository

__all__ = ["BaseEntity", "BaseRepository"]
