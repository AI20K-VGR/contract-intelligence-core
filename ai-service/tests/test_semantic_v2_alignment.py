from __future__ import annotations

from decimal import Decimal

from app.contracts.clause_frames import SLOT_NAMES, ClauseFrame, Evidence, Slot
from app.pipeline.clause_keys import build_candidates


def make_frame(
    identifier: str,
    *,
    document: str = "body",
    dossier: str = "dossier",
    modality: str = "REQUIRED",
    amount: str = "30",
    unit: str = "percent",
    trigger: str | None = "SIGNING",
    deadline: str | None = None,
    scope: str | None = "invoice",
    action: str = "PAY",
    actor: str | None = "A",
    condition: str | None = None,
    exception: str | None = None,
    family: str = "OBLIGATION",
) -> ClauseFrame:
    evidence = Evidence(document, f"snapshot-{document}", identifier, "grounded source")
    values: dict[str, str | Decimal | None] = {
        "actor": actor,
        "action": action,
        "modality_negation": modality,
        "object_scope": scope,
        "amount": Decimal(amount) if amount is not None else None,
        "unit": unit,
        "currency": None,
        "base": None,
        "period": None,
        "temporal_trigger": trigger,
        "deadline": deadline,
        "deadline_unit": "day" if deadline is not None else None,
        "condition": condition,
        "exception": exception,
        "beneficiary": None,
        "qualifier": None,
    }
    slots = []
    for name in sorted(SLOT_NAMES):
        value = values.get(name)
        state = "GROUNDED" if value is not None else "ABSENT"
        if name == "object_scope" and scope is None:
            state = "UNKNOWN"
        slots.append((name, Slot(value, state, (evidence,), "unknown_scope" if state == "UNKNOWN" else "")))
    return ClauseFrame(
        identifier, family, "SALES", document, f"snapshot-{document}",
        (evidence,), tuple(slots), dossier,
    )


def test_opposite_grounded_polarity_is_an_alignment_candidate():
    left = make_frame("left", modality="REQUIRED")
    right = make_frame("right", document="annex", modality="PROHIBITED")

    pairs = build_candidates((left, right))

    assert len(pairs) == 1
    assert "SEMANTIC_ALIGNMENT" in pairs[0].sources


def test_same_payment_event_different_amount_is_retained_across_documents():
    left = make_frame("left", amount="30")
    right = make_frame("right", document="annex", amount="40")

    pairs = build_candidates((left, right))

    assert len(pairs) == 1
    assert "SAME_KEY" in pairs[0].sources


def test_unknown_actor_does_not_create_alignment_candidate():
    left = make_frame("left", actor=None)
    right = make_frame("right", document="annex", actor=None)

    assert build_candidates((left, right)) == ()


def test_alignment_never_crosses_dossiers():
    left = make_frame("left", dossier="dossier-a")
    right = make_frame("right", document="annex", dossier="dossier-b")

    assert build_candidates((left, right)) == ()
