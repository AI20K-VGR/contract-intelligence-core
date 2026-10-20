"""Cross-cutting persistence module.

NOTE: Do NOT re-export ``orm_registry`` here. Importing the package must stay
layer-safe for application services (e.g. reocr_service → shared.persistence).
Callers that need ``import_all_models`` must import
``contract_intelligence.shared.persistence.orm_registry`` directly
(composition root / alembic only).
"""

from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.session import (
    SessionDep,
    bind_engine,
    create_async_engine,
    create_session_factory,
    get_async_session,
    get_engine,
    get_session_factory,
    reset_engine,
)

__all__ = [
    "Base",
    "SessionDep",
    "bind_engine",
    "create_async_engine",
    "create_session_factory",
    "get_async_session",
    "get_engine",
    "get_session_factory",
    "reset_engine",
]
