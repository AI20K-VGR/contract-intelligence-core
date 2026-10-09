import pytest
from pydantic import ValidationError

from app.contracts.wire import ProcessingPolicyFlags
from app.pipeline.ai1_snapshot_adapter import adapt_be_ai2_processing_request
from app.tools.persist import record_to_dict
from fixtures.contract_graph_pair_records import pair_record
from scripts.capture_idp_golden import _request_payload


@pytest.mark.parametrize("value", [True, False, None])
def test_adapter_maps_egress_allowed_to_consent(value):
    payload = _request_payload()
    if value is None:
        payload["policy_flags"].pop("egress_allowed")
    else:
        payload["policy_flags"]["egress_allowed"] = value
    _, adapted = adapt_be_ai2_processing_request(payload)
    assert adapted.record.content_sharing_consent is bool(value)


def test_consent_not_in_record_to_dict():
    rec = pair_record()
    rec.content_sharing_consent = True
    assert "content_sharing_consent" not in record_to_dict(rec)


def test_policy_flags_contract_unchanged():
    assert set(ProcessingPolicyFlags.model_fields) == {"egress_allowed", "use_vector", "budget_limits"}
    with pytest.raises(ValidationError):
        ProcessingPolicyFlags(content_sharing_consent=True)


def test_consent_default_false_for_non_adapter_records():
    assert pair_record().content_sharing_consent is False
