from unittest import mock

import pytest
from jsonschema import Draft202012Validator

from app.contracts import schema_validation
from app.contracts.errors import ContractValidationError


def test_validation_stops_at_the_first_error_instead_of_collecting_all(monkeypatch):
    # A 200-page snapshot with one bad field per word produced ~10^5 errors; sorting them all
    # to report one held more than 2 GiB and OOM-killed AI2.
    monkeypatch.setattr(
        schema_validation,
        "load_contract_schema",
        lambda _f: {"type": "array", "items": {"type": "integer"}},
    )
    original, produced = Draft202012Validator.iter_errors, []

    def counting(self, instance, *args, **kwargs):
        for error in original(self, instance, *args, **kwargs):
            produced.append(error)
            yield error

    with (
        mock.patch.object(Draft202012Validator, "iter_errors", counting),
        pytest.raises(ContractValidationError, match=r"^0: "),
    ):
        schema_validation.validate_contract(["x"] * 10_000, "unused.json", error_code="X")
    assert len(produced) == 1
