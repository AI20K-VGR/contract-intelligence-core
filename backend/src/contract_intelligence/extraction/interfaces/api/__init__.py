"""API namespace marker."""

from fastapi import APIRouter

router = APIRouter(prefix="/api/v1/extraction", tags=["extraction"])
