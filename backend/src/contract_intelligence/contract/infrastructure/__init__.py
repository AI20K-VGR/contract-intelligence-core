"""Infrastructure layer — ORM persistence, external adapters.

Triển khai các Protocol định nghĩa trong ``domain/repositories/``.
KHÔNG import FastAPI ở đây (router nằm trong ``interfaces/``).
"""

from contract_intelligence.contract.infrastructure import persistence, storage

__all__ = ["persistence", "storage"]
