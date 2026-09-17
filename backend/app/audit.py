from sqlalchemy import select

from app.models import AuditEvent


def log_event(
    db, dossier_id, actor, action, object_type, object_id,
    request_id=None, result="success", detail=None,
):
    db.add(
        AuditEvent(
            dossier_id=dossier_id,
            actor=actor,
            action=action,
            object_type=object_type,
            object_id=object_id,
            request_id=request_id,
            result=result,
            detail=detail or {},
        )
    )


def audit_trail(db, dossier_id):
    events = db.scalars(
        select(AuditEvent)
        .where(AuditEvent.dossier_id == dossier_id)
        .order_by(AuditEvent.created_at, AuditEvent.id)
    )
    return [
        {
            "id": e.id,
            "actor": e.actor,
            "action": e.action,
            "object_type": e.object_type,
            "object_id": e.object_id,
            "request_id": e.request_id,
            "result": e.result,
            "detail": e.detail,
            "created_at": e.created_at,
        }
        for e in events
    ]
