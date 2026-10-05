from __future__ import annotations

from app.contracts.clause_frames import ClauseFrame, Evidence, Slot
from app.pipeline.frame_context import _round_robin_frames


def _frame(identifier, document_id):
    evidence = Evidence(document_id, f"snapshot-{document_id}", identifier, "source text")
    return ClauseFrame(
        identifier,
        "OBLIGATION",
        "SALES",
        document_id,
        evidence.snapshot_id,
        (evidence,),
        (("action", Slot("PAY", "GROUNDED", (evidence,))),),
        "dossier",
    )


def test_context_budget_gives_late_annex_a_turn_before_body_uses_all_call_slots():
    frames = (
        _frame("body-1", "body"),
        _frame("body-2", "body"),
        _frame("body-3", "body"),
        _frame("annex-1", "annex"),
    )

    ordered = _round_robin_frames(frames)

    assert [item.frame_id for item in ordered] == ["body-1", "annex-1", "body-2", "body-3"]
    assert {item.frame_id for item in ordered} == {item.frame_id for item in frames}
