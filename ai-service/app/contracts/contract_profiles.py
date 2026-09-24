"""Versioned contract-type field profiles at the AI2 semantic boundary.

Profiles describe routing vocabulary only.  They never replace source text or
create a fact without evidence; an unmapped key remains raw and needs review.
"""

from __future__ import annotations

import unicodedata
from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict, Field


PROFILE_SCHEMA_VERSION = "ai2.contract-type-profile.v1"


class ContractType(str, Enum):
    SALES = "SALES"
    SUPPLY_SERVICE = "SUPPLY_SERVICE"
    LEASE = "LEASE"
    CONSTRUCTION_WORK = "CONSTRUCTION_WORK"
    EMPLOYMENT = "EMPLOYMENT"
    NDA = "NDA"


class FieldMappingStatus(str, Enum):
    MAPPED = "MAPPED"
    UNMAPPED = "UNMAPPED"


class ProfileField(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(min_length=1, max_length=32)
    value_type: str = Field(min_length=1, max_length=40)
    normalization: str = Field(min_length=1, max_length=120)
    evidence_policy: str = Field(min_length=1, max_length=120)


class AnnexExtension(BaseModel):
    model_config = ConfigDict(extra="forbid")

    key: str = Field(min_length=1, max_length=120)
    aliases: list[str] = Field(min_length=1, max_length=32)
    field_keys: list[str] = Field(min_length=1, max_length=32)


class ContractTypeProfile(BaseModel):
    model_config = ConfigDict(extra="forbid")

    schema_version: str = PROFILE_SCHEMA_VERSION
    contract_type: ContractType
    version: int = Field(ge=1)
    fields: list[ProfileField] = Field(min_length=1, max_length=64)
    aliases: list[str] = Field(min_length=1, max_length=32)
    annex_extensions: list[AnnexExtension] = Field(min_length=1, max_length=32)


class FieldMapping(BaseModel):
    model_config = ConfigDict(extra="forbid")

    status: FieldMappingStatus
    key: str | None = None
    raw_key: str
    raw_value: Any = None
    review_state: str


def _fold(value: str) -> str:
    text = unicodedata.normalize("NFD", value.strip().casefold())
    text = "".join(char for char in text if unicodedata.category(char) != "Mn")
    return text.replace("\u0111", "d").replace("\u0110", "d")


def _field(key: str, *aliases: str, value_type: str = "text") -> ProfileField:
    return ProfileField(
        key=key,
        aliases=[key, *aliases],
        value_type=value_type,
        normalization="preserve_raw_and_normalize_when_evidenced",
        evidence_policy="citation_required",
    )


def _annex(key: str, *aliases: str, fields: list[str]) -> AnnexExtension:
    return AnnexExtension(key=key, aliases=[key, *aliases], field_keys=fields)


_COMMON = [
    _field("effective_date", "ngay hieu luc", "effective date", value_type="date"),
    _field("parties", "ben", "parties", value_type="party"),
]
_ANNEXES = [
    _annex("price", "gia", "don gia", fields=["unit_price", "total_price"]),
    _annex("quantity", "so luong", fields=["quantity"]),
    _annex("technical_scope", "pham vi ky thuat", fields=["technical_scope"]),
    _annex("schedule", "tien do", fields=["milestone", "delivery_date"]),
    _annex("sla", "service level", fields=["sla"]),
    _annex("payment", "thanh toan", fields=["payment_terms"]),
    _annex("acceptance", "nghiem thu", fields=["acceptance_criteria"]),
    _annex("amendment", "dieu chinh", fields=["amendment_reference"]),
]


def _profile(contract_type: ContractType, fields: list[ProfileField], aliases: list[str]) -> ContractTypeProfile:
    return ContractTypeProfile(
        contract_type=contract_type,
        version=1,
        fields=[*_COMMON, *fields],
        aliases=[contract_type.value, *aliases],
        annex_extensions=_ANNEXES,
    )


_PROFILES: dict[ContractType, ContractTypeProfile] = {
    ContractType.SALES: _profile(
        ContractType.SALES,
        [
            _field("item", "hang hoa", "san pham"),
            _field("quantity", "so luong", value_type="decimal"),
            _field("unit_price", "\u0111\u01a1n gi\u00e1", "don gia", value_type="money"),
            _field("total_price", "tong gia", "gia tri hop dong", value_type="money"),
            _field("vat", "thue vat", value_type="percentage"),
            _field("delivery_terms", "giao hang"),
            _field("acceptance_criteria", "nghiem thu"),
            _field("warranty", "bao hanh"),
        ],
        ["mua ban", "sale"],
    ),
    ContractType.SUPPLY_SERVICE: _profile(
        ContractType.SUPPLY_SERVICE,
        [
            _field("supply_scope", "pham vi cung cap"),
            _field("specification", "thong so"),
            _field("sla", "service level agreement"),
            _field("milestone", "moc tien do"),
            _field("acceptance_criteria", "nghiem thu"),
            _field("payment_terms", "thanh toan"),
            _field("warranty", "bao hanh"),
        ],
        ["cung cap", "dich vu"],
    ),
    ContractType.LEASE: _profile(
        ContractType.LEASE,
        [
            _field("leased_asset", "tai san thue"),
            _field("lease_term", "thoi han thue"),
            _field("handover", "ban giao"),
            _field("rent", "tien thue", value_type="money"),
            _field("deposit", "dat coc", value_type="money"),
            _field("maintenance", "bao tri"),
            _field("return_terms", "hoan tra"),
        ],
        ["thue", "rental"],
    ),
    ContractType.CONSTRUCTION_WORK: _profile(
        ContractType.CONSTRUCTION_WORK,
        [
            _field("work_scope", "pham vi cong viec"),
            _field("bill_of_quantities", "boq", "khoi luong"),
            _field("schedule", "tien do"),
            _field("acceptance_criteria", "nghiem thu"),
            _field("penalty", "phat"),
            _field("warranty", "bao hanh"),
            _field("variation", "phat sinh"),
        ],
        ["xay dung", "thi cong"],
    ),
    ContractType.EMPLOYMENT: _profile(
        ContractType.EMPLOYMENT,
        [
            _field("position", "vi tri"),
            _field("work_location", "dia diem lam viec"),
            _field("employment_term", "thoi han"),
            _field("salary", "luong", value_type="money"),
            _field("allowance", "phu cap", value_type="money"),
            _field("working_hours", "gio lam"),
            _field("leave", "nghi phep"),
            _field("termination", "cham dut"),
        ],
        ["lao dong", "nhan su"],
    ),
    ContractType.NDA: _profile(
        ContractType.NDA,
        [
            _field("confidential_information", "thong tin mat"),
            _field("permitted_purpose", "muc dich su dung"),
            _field("receiving_party", "ben nhan"),
            _field("exceptions", "ngoai le"),
            _field("confidentiality_term", "thoi han bao mat"),
            _field("return_or_destroy", "hoan tra huy"),
        ],
        ["bao mat", "non disclosure"],
    ),
}


def profile_registry() -> tuple[ContractTypeProfile, ...]:
    """Return immutable-by-convention copies of the supported wave profiles."""

    return tuple(profile.model_copy(deep=True) for profile in _PROFILES.values())


def get_contract_profile(contract_type: ContractType | str, *, version: int = 1) -> ContractTypeProfile:
    try:
        kind = contract_type if isinstance(contract_type, ContractType) else ContractType(str(contract_type).upper())
    except ValueError as exc:
        raise KeyError(f"unknown contract type: {contract_type}") from exc
    profile = _PROFILES[kind]
    if profile.version != version:
        raise KeyError(f"unsupported {kind.value} profile version: {version}")
    return profile.model_copy(deep=True)


def map_profile_field(
    profile: ContractTypeProfile,
    raw_key: str,
    *,
    raw_value: Any = None,
) -> FieldMapping:
    folded = _fold(raw_key)
    for field in profile.fields:
        if folded in {_fold(alias) for alias in field.aliases}:
            return FieldMapping(
                status=FieldMappingStatus.MAPPED,
                key=field.key,
                raw_key=raw_key,
                raw_value=raw_value,
                review_state="PASS",
            )
    return FieldMapping(
        status=FieldMappingStatus.UNMAPPED,
        raw_key=raw_key,
        raw_value=raw_value,
        review_state="NEEDS_REVIEW",
    )
