from __future__ import annotations

from pathlib import Path

import pytest

from app.contracts.contract_profiles import (
    PROFILE_SCHEMA_VERSION,
    ContractType,
    FieldMappingStatus,
    get_contract_profile,
    map_profile_field,
    profile_registry,
)


def test_wave_profiles_are_versioned_and_include_annex_extensions():
    expected = {
        "SALES",
        "SUPPLY_SERVICE",
        "LEASE",
        "CONSTRUCTION_WORK",
        "EMPLOYMENT",
        "NDA",
    }

    assert {item.contract_type.value for item in profile_registry()} == expected
    for contract_type in expected:
        profile = get_contract_profile(contract_type)
        assert profile.schema_version == PROFILE_SCHEMA_VERSION
        assert profile.version == 1
        assert profile.fields
        assert profile.aliases
        assert profile.annex_extensions


def test_profile_alias_maps_to_canonical_field_without_guessing_type():
    profile = get_contract_profile(ContractType.SALES)
    raw_key = "\u0110\u01a1n gi\u00e1"

    mapping = map_profile_field(profile, raw_key)

    assert mapping.status is FieldMappingStatus.MAPPED
    assert mapping.key == "unit_price"
    assert mapping.raw_key == raw_key


def test_profile_aliases_are_utf8_and_do_not_contain_mojibake():
    profile = get_contract_profile(ContractType.SALES)
    aliases = [alias for field in profile.fields for alias in field.aliases]

    assert "\u0111\u01a1n gi\u00e1" in aliases
    source_paths = (Path(__file__), Path(__file__).parents[1] / "app" / "contracts" / "contract_profiles.py")
    forbidden_bytes = tuple(bytes.fromhex(value) for value in ("ef bf bd", "c3 83", "c3 84", "c3 86"))
    for source_path in source_paths:
        source_bytes = source_path.read_bytes()
        assert not any(marker in source_bytes for marker in forbidden_bytes), source_path


def test_unknown_profile_field_preserves_raw_evidence_and_needs_review():
    profile = get_contract_profile("SALES")

    mapping = map_profile_field(profile, "mystery commercial term", raw_value="raw text")

    assert mapping.status is FieldMappingStatus.UNMAPPED
    assert mapping.review_state == "NEEDS_REVIEW"
    assert mapping.raw_key == "mystery commercial term"
    assert mapping.raw_value == "raw text"


def test_unknown_profile_type_is_safe_and_does_not_fall_back_to_sales():
    with pytest.raises(KeyError):
        get_contract_profile("NOT_A_CONTRACT_TYPE")
