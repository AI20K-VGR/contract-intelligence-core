"""Cross-cutting persistence module.

NOTE: Do NOT re-export ``orm_registry`` here. Importing the package must stay
layer-safe for application services (e.g. reocr_service → shared.persistence).
Callers that need ``import_all_models`` must import
``contract_intelligence.shared.persistence.orm_registry`` directly
(composition root / alembic only).
"""

from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.job_queue import (
    ClaimedJob,
    claim_next_job,
    complete_job,
    enqueue_job,
    extend_lease,
    fail_job,
    reap_expired_leases,
)
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
    "ClaimedJob",
    "SessionDep",
    "bind_engine",
    "claim_next_job",
    "complete_job",
    "create_async_engine",
    "create_session_factory",
    "enqueue_job",
    "extend_lease",
    "fail_job",
    "get_async_session",
    "get_engine",
    "get_session_factory",
    "reap_expired_leases",
    "reset_engine",
]
