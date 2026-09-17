"""Base abstractions thuần Python — không phụ thuộc ORM/framework.

Đây là nền tảng cho mọi entity và repository trong domain layer.
Domain layer chỉ phụ thuộc các abstraction này — không biết SQLAlchemy là gì.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Generic, TypeVar

# -----------------------------------------------------------------------------
# Identifiers
# -----------------------------------------------------------------------------
EntityId = TypeVar("EntityId", bound=str)


def new_ulid(prefix: str = "") -> str:
    """Sinh ULID có tiền tố (vd ``dos_01HZ...``).

    Dùng ``python-ulid`` đã khai báo trong ``pyproject.toml``. Trả về ``str``
    thay vì ``ULID`` để serialization an toàn với Pydantic/JSON.
    """
    from ulid import ULID  # import trong hàm để tránh phụ thuộc lúc import module

    return f"{prefix}{ULID()}"


def utcnow() -> datetime:
    """Datetime UTC có timezone — alias cho dễ test/mock."""
    return datetime.now(tz=UTC)


# -----------------------------------------------------------------------------
# Base Entity
# -----------------------------------------------------------------------------
@dataclass(eq=False)
class BaseEntity(Generic[EntityId]):
    """Base class cho mọi entity trong domain.

    Pure Python — KHÔNG dùng SQLAlchemy ``@dataclass`` hay Pydantic ``BaseModel``.
    Concrete ORM mapping được thực hiện trong ``infrastructure/persistence/``.

    Subclass **bắt buộc** khai báo ``id`` và dùng ``field(default_factory=...)``
    để tự sinh khi ``__init__`` chưa nhận từ DB.
    """

    id: EntityId = field(...)  # type: ignore[assignment]
    created_at: datetime = field(default_factory=utcnow)
    updated_at: datetime = field(default_factory=utcnow)

    def __eq__(self, other: object) -> bool:
        if not isinstance(other, BaseEntity):
            return NotImplemented
        return self.id == other.id

    def __hash__(self) -> int:
        return hash(self.id)

    def touch(self) -> None:
        """Cập nhật ``updated_at`` khi entity thay đổi."""
        self.updated_at = utcnow()


# -----------------------------------------------------------------------------
# Base Repository (Protocol)
# -----------------------------------------------------------------------------
@dataclass
class Page(Generic[EntityId]):
    """Pagination result cho repository.list()."""

    items: list[BaseEntity]
    total: int
    limit: int
    offset: int


class BaseRepository(ABC, Generic[EntityId]):
    """Abstract Repository — domain định nghĩa, infrastructure impl.

    Mọi repository cụ thể PHẢI kế thừa class này và override các method.
    Application layer chỉ phụ thuộc Protocol/ABC này, không phụ thuộc
    SQLAlchemy cụ thể.
    """

    @abstractmethod
    async def get(self, entity_id: EntityId) -> BaseEntity | None: ...

    @abstractmethod
    async def list(
        self,
        *,
        limit: int = 50,
        offset: int = 0,
        **filters: object,
    ) -> Page: ...

    @abstractmethod
    async def add(self, entity: BaseEntity) -> None: ...

    @abstractmethod
    async def save(self, entity: BaseEntity) -> None: ...

    @abstractmethod
    async def delete(self, entity_id: EntityId) -> None: ...
