"""Interfaces layer — FastAPI routers, exception handlers.

Tầng ngoài cùng. Đây là nơi DUY NHẤT import FastAPI/Request/Response.
"""

from contract_intelligence.contract.interfaces.api.routers import (
    contract_status_router,
    contract_upload_router,
)

__all__ = ["contract_upload_router", "contract_status_router"]
