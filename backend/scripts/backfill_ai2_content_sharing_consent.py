"""Operator-only, auditable rollout of AI2 content-sharing consent.

Dry-run is the default. Applying requires --apply and a rollout id. This module
never prints dossier identifiers, names, or metadata.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from contract_intelligence.contract.infrastructure.persistence.deletion_ledger import (
    DeletionLedgerORM,
)
from contract_intelligence.contract.infrastructure.persistence.orm import DossierORM
from contract_intelligence.shared.audit import AuditEventORM, add_audit_event

CONSENT_KEY = "ai2_content_sharing_consent"
ROLLOUT_ACTION = "ai2.content_sharing_consent_rollout"
ROLLBACK_ACTION = "ai2.content_sharing_consent_rollout_rollback"
CONSENT_ACTIONS = (ROLLOUT_ACTION, ROLLBACK_ACTION, "ai2.content_sharing_consent_changed")


def _event_id(rollout_id: str, dossier_id: str, action: str) -> str:
    digest = hashlib.sha256(f"{rollout_id}\0{dossier_id}\0{action}".encode()).hexdigest()[:32]
    return f"aud_ai2_{digest}"


async def _active_candidates(session: AsyncSession) -> list[DossierORM]:
    excluded = select(DeletionLedgerORM.dossier_id).where(
        DeletionLedgerORM.tenant_id == DossierORM.tenant_id
    )
    result = await session.scalars(
        select(DossierORM)
        .where(
            DossierORM.deleted_at.is_(None),
            DossierORM.purge_completed_at.is_(None),
            DossierORM.purge_status.is_(None),
        )
        .where(~DossierORM.id.in_(excluded))
        .order_by(DossierORM.id)
        .with_for_update()
    )
    return list(result.all())


async def apply_rollout(
    session: AsyncSession, *, rollout_id: str, actor_id: str, apply: bool = False
) -> dict[str, int]:
    rows = await _active_candidates(session)
    updated = skipped = 0
    for dossier in rows:
        metadata = dict(dossier.metadata_json or {})
        prior = metadata.get(CONSENT_KEY, "__absent__")
        if prior is True:
            skipped += 1
            continue
        if prior is False:
            latest = await session.scalar(
                select(AuditEventORM)
                .where(
                    AuditEventORM.dossier_id == dossier.id,
                    AuditEventORM.action.in_(CONSENT_ACTIONS),
                )
                .order_by(AuditEventORM.occurred_at.desc(), AuditEventORM.id.desc())
                .limit(1)
            )
            if latest is not None and latest.action == "ai2.content_sharing_consent_changed":
                skipped += 1
                continue
        # Only expected legacy states are eligible; malformed values fail closed.
        if prior not in (False, None, "__absent__"):
            skipped += 1
            continue
        event_id = _event_id(rollout_id, dossier.id, ROLLOUT_ACTION)
        existing = await session.get(AuditEventORM, event_id)
        if existing:
            skipped += 1
            continue
        updated += 1
        if not apply:
            continue
        metadata[CONSENT_KEY] = True
        dossier.metadata_json = metadata
        add_audit_event(
            session,
            tenant_id=dossier.tenant_id,
            actor_id=actor_id,
            action=ROLLOUT_ACTION,
            entity_type="dossier",
            entity_id=dossier.id,
            dossier_id=dossier.id,
            from_state="absent" if prior == "__absent__" else json.dumps(prior),
            to_state="true",
            detail={
                "rollout_id": rollout_id,
                "prior": "absent" if prior == "__absent__" else prior,
                "new": True,
            },
        ).id = event_id
    return {"eligible": len(rows), "updated": updated, "skipped": skipped}


async def rollback_rollout(
    session: AsyncSession, *, rollout_id: str, actor_id: str
) -> dict[str, int]:
    rows = await _active_candidates(session)
    restored = skipped = 0
    for dossier in rows:
        event_id = _event_id(rollout_id, dossier.id, ROLLOUT_ACTION)
        original = await session.get(AuditEventORM, event_id)
        if original is None:
            continue
        events = await session.scalars(
            select(AuditEventORM)
            .where(
                AuditEventORM.dossier_id == dossier.id, AuditEventORM.action.in_(CONSENT_ACTIONS)
            )
            .order_by(AuditEventORM.occurred_at.desc(), AuditEventORM.id.desc())
        )
        latest = events.first()
        current = (dossier.metadata_json or {}).get(CONSENT_KEY, "__absent__")
        if latest is None or latest.id != event_id or current is not True:
            skipped += 1
            continue
        rollback_id = _event_id(rollout_id, dossier.id, ROLLBACK_ACTION)
        if await session.get(AuditEventORM, rollback_id):
            skipped += 1
            continue
        details = json.loads(original.detail or "{}")
        metadata = dict(dossier.metadata_json or {})
        prior = details.get("prior", "__absent__")
        if prior in ("__absent__", "absent"):
            metadata.pop(CONSENT_KEY, None)
        else:
            metadata[CONSENT_KEY] = prior
        dossier.metadata_json = metadata
        add_audit_event(
            session,
            tenant_id=dossier.tenant_id,
            actor_id=actor_id,
            action=ROLLBACK_ACTION,
            entity_type="dossier",
            entity_id=dossier.id,
            dossier_id=dossier.id,
            from_state="true",
            to_state="absent" if prior == "__absent__" else json.dumps(prior),
            detail={"rollout_id": rollout_id, "compensates": event_id},
        ).id = rollback_id
        restored += 1
    return {"restored": restored, "skipped": skipped}


async def preview_rollback(session: AsyncSession, *, rollout_id: str) -> dict[str, int]:
    rows = await _active_candidates(session)
    restorable = skipped = 0
    for dossier in rows:
        event_id = _event_id(rollout_id, dossier.id, ROLLOUT_ACTION)
        original = await session.get(AuditEventORM, event_id)
        if original is None:
            continue
        latest = await session.scalar(
            select(AuditEventORM)
            .where(
                AuditEventORM.dossier_id == dossier.id,
                AuditEventORM.action.in_(CONSENT_ACTIONS),
            )
            .order_by(AuditEventORM.occurred_at.desc(), AuditEventORM.id.desc())
            .limit(1)
        )
        rollback_id = _event_id(rollout_id, dossier.id, ROLLBACK_ACTION)
        if (
            latest is not None
            and latest.id == event_id
            and (dossier.metadata_json or {}).get(CONSENT_KEY) is True
            and await session.get(AuditEventORM, rollback_id) is None
        ):
            restorable += 1
        else:
            skipped += 1
    return {"restorable": restorable, "skipped": skipped}


async def _run(args: argparse.Namespace) -> None:
    from contract_intelligence.shared.persistence import (
        bind_engine,
        create_async_engine,
        get_session_factory,
        reset_engine,
    )

    if args.apply and (not args.rollout_id or not args.expected_digest):
        raise SystemExit(
            "--apply requires --rollout-id and --expected-digest from a reviewed dry-run"
        )
    if not args.rollout_id:
        args.rollout_id = "dry-run"
    engine = create_async_engine()
    bind_engine(engine)
    try:
        factory = get_session_factory()
        async with factory() as session, session.begin():
            candidates = await _active_candidates(session)
            candidate_digest = hashlib.sha256(
                "\n".join(sorted(row.id for row in candidates)).encode()
            ).hexdigest()
            if args.apply and candidate_digest != args.expected_digest:
                raise SystemExit("candidate digest changed since dry-run; run dry-run again")
            result = (
                await rollback_rollout(session, rollout_id=args.rollout_id, actor_id=args.actor)
                if args.rollback and args.apply
                else await preview_rollback(session, rollout_id=args.rollout_id)
                if args.rollback
                else await apply_rollout(
                    session, rollout_id=args.rollout_id, actor_id=args.actor, apply=args.apply
                )
            )
    finally:
        reset_engine()
        await engine.dispose()
    print(
        json.dumps(
            {
                "mode": (
                    "rollback-apply"
                    if args.rollback and args.apply
                    else "rollback-dry-run"
                    if args.rollback
                    else "apply"
                    if args.apply
                    else "dry-run"
                ),
                "candidate_count": len(candidates),
                "candidate_digest": candidate_digest,
                **result,
            },
            sort_keys=True,
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--rollout-id")
    parser.add_argument(
        "--expected-digest", help="candidate digest returned by the reviewed dry-run"
    )
    parser.add_argument("--actor", default="system:ai2-consent-rollout")
    parser.add_argument(
        "--apply", action="store_true", help="persist consent changes; default is dry-run"
    )
    parser.add_argument(
        "--rollback", action="store_true", help="conditionally compensate this rollout"
    )
    asyncio.run(_run(parser.parse_args()))


if __name__ == "__main__":
    main()
