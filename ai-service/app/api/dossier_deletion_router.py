"""Signed internal dossier erasure endpoint (PostgreSQL only)."""

from fastapi import APIRouter, HTTPException
from sqlalchemy.exc import SQLAlchemyError

from app.security.service_envelope import ServiceEnvelopeError, verify_service_envelope
from app.tools.dossier_deletion import purge_dossier
from app.tools.persist import DATA

router = APIRouter()


@router.delete("/api/v1/dossiers/{dossier_id}")
def delete_dossier(dossier_id: str, payload: dict) -> dict:
    if payload.get("dossier_id") != dossier_id:
        raise HTTPException(422, detail={"code": "SERVICE_DOSSIER_MISMATCH"})
    try:
        envelope = verify_service_envelope(payload, required_scope="ai2.dossier.delete")
    except ServiceEnvelopeError as exc:
        raise HTTPException(401, detail={"code": exc.code}) from exc
    if payload.get("tenant_id") != envelope.tenant_id:
        raise HTTPException(403, detail={"code": "SERVICE_TENANT_MISMATCH"})
    try:
        return purge_dossier(envelope.tenant_id, dossier_id, data_dir=DATA)
    except (OSError, SQLAlchemyError) as exc:
        # Never return DB parameters, local paths or contract content in an error.
        raise HTTPException(503, detail={"code": "AI2_PURGE_INCOMPLETE", "retryable": True}) from exc
