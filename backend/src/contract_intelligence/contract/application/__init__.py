"""Application layer — use cases (services) & DTOs.

Application service **orchestrate** domain entities + repositories.
KHÔNG biết ORM, MinIO, FastAPI. Nếu cần external IO, depend vào Protocol
định nghĩa trong domain hoặc infrastructure (qua DI).
"""

from contract_intelligence.contract.application import dtos, services

__all__ = ["services", "dtos"]
