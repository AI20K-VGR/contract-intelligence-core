"""Immutable semantic frames; unknown values retain their evidence and reason."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import date
from decimal import Decimal
from typing import Literal

from app.contracts.contract_profiles import ContractType

SlotState = Literal["GROUNDED", "UNKNOWN", "ABSENT", "UNSUPPORTED"]
Family = Literal["OBLIGATION", "RIGHT", "PROHIBITION", "REMEDY", "PARAMETER", "DEFINITION"]
SEMANTIC_DISPOSITIONS = frozenset({
    "GENERAL_VS_SPECIFIC", "NEEDS_REVIEW_BACKOFF", "SCOPE_DIFFERS", "NEEDS_REVIEW_UNPARSED",
    "NOT_COMPARABLE", "GRADUATED", "DUPLICATE", "COMPARABLE_DIFFERENCE",
    "CONFLICT_CANDIDATE", "CUMULATIVE",
})
FAMILIES = frozenset({"OBLIGATION", "RIGHT", "PROHIBITION", "REMEDY", "PARAMETER", "DEFINITION"})
SLOT_NAMES = frozenset({
    "actor", "beneficiary", "action", "qualifier", "modality_negation", "object_scope",
    "condition", "exception", "temporal_trigger", "deadline", "amount", "currency",
    "unit", "deadline_unit", "base", "period", "parameter", "definition",
})


@dataclass(frozen=True, slots=True)
class Evidence:
    document_id: str
    snapshot_id: str
    source_ref: str
    raw: str

    def __post_init__(self) -> None:
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.document_id, self.snapshot_id, self.source_ref, self.raw)):
            raise ValueError("evidence requires document, snapshot, source and raw span")


@dataclass(frozen=True, slots=True)
class Slot:
    value: str | Decimal | None
    state: SlotState
    evidence: tuple[Evidence, ...]
    reason: str = ""

    def __post_init__(self) -> None:
        if self.state not in {"GROUNDED", "UNKNOWN", "ABSENT", "UNSUPPORTED"}:
            raise ValueError("unknown slot state")
        if not isinstance(self.evidence, tuple) or any(not isinstance(ev, Evidence) for ev in self.evidence):
            raise TypeError("slot evidence must be an immutable Evidence tuple")
        if self.value is not None and not isinstance(self.value, (str, Decimal)):
            raise TypeError("slot value must be immutable text or Decimal")
        if isinstance(self.value, Decimal) and not self.value.is_finite():
            raise ValueError("nonfinite slot value")
        if self.state == "GROUNDED" and (self.value is None or (isinstance(self.value, str) and not self.value.strip()) or not self.evidence):
            raise ValueError("grounded slot requires value and evidence")
        if self.state == "ABSENT" and (self.value is not None or not self.evidence):
            raise ValueError("absent slot requires source evidence and no value")


@dataclass(frozen=True, slots=True)
class ClauseFrame:
    frame_id: str
    family: Family
    profile: str
    document_id: str
    snapshot_id: str
    evidence: tuple[Evidence, ...]
    slots: tuple[tuple[str, Slot], ...]
    dossier_id: str

    def __post_init__(self) -> None:
        if self.family not in FAMILIES:
            raise ValueError("unsupported frame family")
        ContractType(self.profile)
        if any(not isinstance(value, str) or not value.strip()
               for value in (self.frame_id, self.document_id, self.snapshot_id, self.dossier_id)):
            raise ValueError("frame identity required")
        if not isinstance(self.evidence, tuple) or not self.evidence or not isinstance(self.slots, tuple):
            raise ValueError("immutable evidence and slots required")
        names = [name for name, _ in self.slots]
        if len(set(names)) != len(names):
            raise ValueError("duplicate slot")
        if any(name not in SLOT_NAMES or not isinstance(slot, Slot) for name, slot in self.slots):
            raise ValueError("unsupported slot")
        all_evidence = (*self.evidence, *(ev for _, slot in self.slots for ev in slot.evidence))
        if any(not isinstance(ev, Evidence) or (ev.document_id, ev.snapshot_id)
               != (self.document_id, self.snapshot_id) for ev in all_evidence):
            raise ValueError("evidence scope mismatch")

    def get(self, name: str) -> Slot | None:
        return next((slot for key, slot in self.slots if key == name), None)


@dataclass(frozen=True, slots=True)
class ClauseKey:
    key: tuple[str, ...] | None
    certainty: Literal["DEFINITE", "UNKNOWN"]
    reason: str
    method: str = "CLOSED_SYMBOL"
    alias_digest: str | None = None
    alias_version: int | None = None
    alias_proposal_ids: tuple[str, ...] = ()

    def __post_init__(self) -> None:
        if self.certainty not in {"DEFINITE", "UNKNOWN"}:
            raise ValueError("unsupported key certainty")
        if self.certainty == "UNKNOWN" and self.key is not None:
            raise ValueError("uncertain key cannot have definite identity")
        if self.certainty == "DEFINITE" and (not isinstance(self.key, tuple) or not self.key
                or any(not isinstance(value, str) or not value.strip() for value in self.key)):
            raise ValueError("definite key requires immutable symbols")


@dataclass(frozen=True, slots=True)
class FramePair:
    left_id: str
    right_id: str
    disposition: str
    reason: str
    left_evidence: tuple[Evidence, ...]
    right_evidence: tuple[Evidence, ...]
    review_state: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"

    def __post_init__(self) -> None:
        if self.disposition not in SEMANTIC_DISPOSITIONS or self.review_state != "NEEDS_REVIEW":
            raise ValueError("unsupported pair disposition or review state")
        if not self.left_id or not self.right_id or self.left_id == self.right_id or not self.reason:
            raise ValueError("pair identity and reason required")
        if any(not isinstance(items, tuple) or not items or
               any(not isinstance(ev, Evidence) for ev in items)
               for items in (self.left_evidence, self.right_evidence)):
            raise ValueError("two immutable evidence sides required")


@dataclass(frozen=True, slots=True)
class TimelineEdge:
    edge_id: str
    source_id: str
    target_id: str | None
    relation: Literal["REFERENCES", "AMENDS"]
    evidence: tuple[Evidence, ...]
    date_role: Literal["EFFECTIVE", "SIGNING", "UNKNOWN"] = "UNKNOWN"
    date_value: str | None = None
    acceptance: Slot | None = None
    value_slot: str | None = None

    def __post_init__(self) -> None:
        if not self.edge_id or not self.source_id or self.target_id == "":
            raise ValueError("timeline identity required")
        if self.relation not in {"REFERENCES", "AMENDS"}:
            raise ValueError("unsupported timeline relation")
        if not isinstance(self.evidence, tuple) or not self.evidence:
            raise ValueError("timeline evidence required")
        if any(not isinstance(ev, Evidence) for ev in self.evidence):
            raise TypeError("timeline Evidence required")
        if self.date_role not in {"EFFECTIVE", "SIGNING", "UNKNOWN"}:
            raise ValueError("unknown date role")
        if self.value_slot is not None and self.value_slot not in SLOT_NAMES:
            raise ValueError("unsupported proposed value slot")
        if self.acceptance is not None and not isinstance(self.acceptance, Slot):
            raise TypeError("acceptance Slot required")
        if self.date_value is not None:
            date.fromisoformat(self.date_value)


@dataclass(frozen=True, slots=True)
class TimelineEntry:
    edge: TimelineEdge
    reasons: tuple[str, ...]
    proposed_value: Slot | None = None
    review_state: Literal["NEEDS_REVIEW"] = "NEEDS_REVIEW"

    def __post_init__(self) -> None:
        if self.review_state != "NEEDS_REVIEW" or not isinstance(self.reasons, tuple):
            raise ValueError("timeline is review-only with immutable reasons")
        if self.proposed_value is not None and (
                self.edge.relation != "AMENDS" or self.proposed_value.state != "GROUNDED"):
            raise ValueError("proposed value requires grounded amendment")
