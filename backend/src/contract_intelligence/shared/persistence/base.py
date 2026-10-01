"""Cross-cutting persistence — Base registry cho SQLAlchemy ORM.

Module này import SQLAlchemy DeclarativeBase và re-export.
Mọi bounded context (contract/extraction/...) dùng chung Base này
để Alembic autogenerate có thể phát hiện tất cả tables.

Tại sao KHÔNG đặt ở `shared/base.py`?
    File đó dùng cho **domain layer** (pure Python, không ORM).
    Nếu gộp vào, `shared.base` sẽ bị phụ thuộc bởi SQLAlchemy —
    vi phạm shared kernel rule (domain entities không import framework).
"""

from __future__ import annotations

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Declarative base class — tất cả ORM model kế thừa class này.

    Alembic env.py import ``Base.metadata`` để autogenerate migrations.
    Bounded context import Base ở infrastructure layer, không import ở domain.

    Usage:
        from contract_intelligence.shared.persistence import Base

        class AppUserORM(Base):
            __tablename__ = "app_user"
            id: Mapped[str] = mapped_column(Text, primary_key=True)
    """


__all__ = ["Base"]
