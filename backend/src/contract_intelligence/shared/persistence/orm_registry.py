"""Import all SQLAlchemy ORM models so ``Base.metadata`` is complete.

Alembic ``env.py`` and ``create_all`` callers MUST import this module
(or call ``import_all_models()``) before reading ``Base.metadata``.
"""

from __future__ import annotations


def import_all_models() -> None:
    """Eagerly import every ORM module that registers tables on ``Base``."""
    # isort: off
    import contract_intelligence.identity.infrastructure.persistence.orm  # noqa: F401
    import contract_intelligence.contract.infrastructure.persistence.orm  # noqa: F401
    import contract_intelligence.contract.infrastructure.persistence.orm_others  # noqa: F401
    import contract_intelligence.extraction.infrastructure.persistence.orm  # noqa: F401
    import contract_intelligence.extraction.infrastructure.persistence.orm_reocr  # noqa: F401
    import contract_intelligence.conflict.infrastructure.persistence.orm  # noqa: F401
    import contract_intelligence.review.infrastructure.persistence.orm  # noqa: F401
    import contract_intelligence.review.infrastructure.persistence.orm_approval  # noqa: F401
    import contract_intelligence.contract.infrastructure.persistence.deletion_ledger  # noqa: F401
    import contract_intelligence.admin.activity_feed  # noqa: F401
    # isort: on


__all__ = ["import_all_models"]
