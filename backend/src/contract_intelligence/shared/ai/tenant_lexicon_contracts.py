"""Contract governance; freeze policy chỉ được inject từ cấu hình tin cậy."""

from __future__ import annotations

import hashlib
import json
import re
import unicodedata
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

ACTION_SYMBOLS = frozenset(
    {
        "PAY",
        "DELIVER",
        "ACCEPT",
        "NOTIFY",
        "TERMINATE",
        "COMPENSATE",
        "PENALTY",
        "DISCLOSE",
        "KEEP_CONFIDENTIAL",
        "RETURN",
        "REPAIR",
        "PERFORM",
    }
)
QUALIFIER_SYMBOLS = frozenset({"BREACH", "DELAY", "NONPAYMENT", "DAMAGE", "CONFIDENTIALITY"})
STOPLIST = frozenset({"thực hiện", "làm", "có", "được", "phải", "áp dụng", "không"})


class ClosedModel(BaseModel):
    model_config = ConfigDict(extra="forbid", frozen=True, strict=True)


class Assignment(ClosedModel):
    expert_id: str = Field(min_length=1, max_length=128)
    expertise_ref: str = Field(min_length=1, max_length=256)
    expires_at: datetime

    @field_validator("expires_at")
    @classmethod
    def finite_expiry(cls, value: datetime) -> datetime:
        if value.tzinfo is None:
            raise ValueError("assignment needs timezone")
        return value


class Proposal(ClosedModel):
    source: str = Field(min_length=1, max_length=120)
    symbol: str
    kind: Literal["action", "qualifier"]
    source_ref: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def closed_alias(self) -> Proposal:
        validate_alias(self.source, self.symbol, self.kind, minimum_length=4)
        return self


class ProposalTarget(ClosedModel):
    proposal_id: str = Field(min_length=1, max_length=128)


class ActiveAlias(ClosedModel):
    source: str
    symbol: str
    kind: Literal["action", "qualifier"]
    proposal_id: str = Field(min_length=1)

    @model_validator(mode="after")
    def validated_alias(self) -> ActiveAlias:
        validate_alias(self.source, self.symbol, self.kind, minimum_length=4)
        return self


class PromotionOptIn(ClosedModel):
    enabled: bool
    consent_ref: str = Field(min_length=1, max_length=256)


class ErrorMeasurement(ClosedModel):
    proposal_id: str = Field(min_length=1, max_length=128)
    errors: int = Field(ge=0)
    denominator: int = Field(ge=0)
    labels_ref: str = Field(min_length=1, max_length=256)

    @model_validator(mode="after")
    def counts(self) -> ErrorMeasurement:
        if self.errors > self.denominator:
            raise ValueError("errors exceed denominator")
        return self


class ActivationPolicy(ClosedModel):
    policy_digest: str = Field(pattern=r"^[a-f0-9]{64}$")
    minimum_length: int = Field(ge=4, le=120)
    revoke_error_rate: float = Field(ge=0, le=1, allow_inf_nan=False)
    assignment_sla_ref: str = Field(min_length=1)
    backlog_policy_ref: str = Field(min_length=1)
    activation_review_ref: str = Field(min_length=1)
    promotion_consent_text_ref: str = Field(min_length=1)


class LexiconCommand(ClosedModel):
    action: Literal[
        "ASSIGN", "PROPOSE", "APPROVE", "REJECT", "REVOKE", "OPT_IN", "PROMOTE", "MEASURE"
    ]
    base_version: int = Field(ge=0)
    idempotency_key: str = Field(min_length=1, max_length=128)
    # JSON command payload validated with the action-specific closed DTO in service.
    payload: dict[str, object]

    @property
    def digest(self) -> str:
        return digest_json(self.model_dump(mode="json"))


def digest_json(value: object) -> str:
    return hashlib.sha256(
        json.dumps(value, ensure_ascii=False, sort_keys=True, separators=(",", ":")).encode()
    ).hexdigest()


def normalize_source(source: str) -> str:
    return " ".join(unicodedata.normalize("NFC", source).casefold().split())


def validate_alias(source: str, symbol: str, kind: str, *, minimum_length: int) -> str:
    if not re.fullmatch(r"[\w -]{1,120}", source):
        raise ValueError("Chỉ chấp nhận cụm alias trừu tượng")
    normalized = normalize_source(source)
    if len(normalized) < minimum_length or normalized in STOPLIST:
        raise ValueError("Alias ngắn hoặc quá chung")
    symbols = ACTION_SYMBOLS if kind == "action" else QUALIFIER_SYMBOLS
    if symbol not in symbols:
        raise ValueError("Symbol ngoài enum đóng")
    return normalized
