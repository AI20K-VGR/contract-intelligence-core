from __future__ import annotations

import pytest


@pytest.fixture
def regression_case():
    """Synthetic evidence distilled from the development dossier's OCR report."""
    return {
        "source_kind": "synthetic_from_development_regression",
        "contract_value": {
            "body": 12_340_000,
            "annex": 45_670_000,
            "currency": "VND",
        },
        "contract_schedule": [
            {"milestone": "advance", "percent": 20, "trigger": "contract_signed"},
            {"milestone": "progress", "percent": 50, "trigger": "work_progress"},
            {"milestone": "final", "percent": 30, "trigger": "acceptance"},
        ],
        "annex_schedule": [
            {"milestone": "advance", "percent": 10, "trigger": "contract_signed"},
            {"milestone": "materials", "percent": 30, "trigger": "materials_delivered"},
            {"milestone": "installation", "percent": 25, "trigger": "installation_complete"},
            {"milestone": "handover", "percent": 25, "trigger": "handover"},
            {"milestone": "final", "percent": 10, "trigger": "final_acceptance"},
        ],
        "boq": {
            "source_rows_count": 30,
            "summarized_line_amounts": [10_000_000, 8_000_000, 5_456_750],
            "subtotal": 38_765_432,
            "tax_percent": 8,
            "tax_amount": 1_876_540,
            "total_after_tax": 25_333_290,
        },
        "valid_single_schedule": [
            {"milestone": "advance", "percent": 20},
            {"milestone": "progress", "percent": 50},
            {"milestone": "final", "percent": 30},
        ],
        "negative_controls": {
            "generic_contract_confirmation_is_not_amendment": True,
            "installments_within_one_schedule_are_not_conflicts": True,
            "payment_triggers_remain_distinct": True,
        },
    }


def test_synthetic_regression_case_preserves_conflict_and_negative_controls(
    regression_case,
):
    assert regression_case["source_kind"] == "synthetic_from_development_regression"
    assert regression_case["contract_value"] == {
        "body": 12_340_000,
        "annex": 45_670_000,
        "currency": "VND",
    }

    contract_schedule = regression_case["contract_schedule"]
    annex_schedule = regression_case["annex_schedule"]
    assert [milestone["percent"] for milestone in contract_schedule] == [20, 50, 30]
    assert [milestone["percent"] for milestone in annex_schedule] == [10, 30, 25, 25, 10]
    assert sum(milestone["percent"] for milestone in contract_schedule) == 100
    assert sum(milestone["percent"] for milestone in annex_schedule) == 100
    assert contract_schedule[-1]["trigger"] != annex_schedule[-1]["trigger"]

    boq = regression_case["boq"]
    assert boq["source_rows_count"] == 30
    assert sum(boq["summarized_line_amounts"]) == 23_456_750
    assert boq["subtotal"] == 38_765_432
    assert boq["subtotal"] - sum(boq["summarized_line_amounts"]) == 15_308_682
    assert boq["tax_amount"] == sum(boq["summarized_line_amounts"]) * boq["tax_percent"] // 100
    assert boq["total_after_tax"] == sum(boq["summarized_line_amounts"]) + boq["tax_amount"]

    assert sum(item["percent"] for item in regression_case["valid_single_schedule"]) == 100
    assert regression_case["negative_controls"] == {
        "generic_contract_confirmation_is_not_amendment": True,
        "installments_within_one_schedule_are_not_conflicts": True,
        "payment_triggers_remain_distinct": True,
    }
