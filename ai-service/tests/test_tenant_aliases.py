from dataclasses import FrozenInstanceError

import pytest

from app.pipeline.runtime import ProcessingRuntime
from app.pipeline.tenant_aliases import (
    ApprovedAlias,
    ApprovedAliasSnapshot,
    propose_aliases,
    validate_alias,
)


@pytest.mark.parametrize(
    "source,symbol,kind",
    [
        ("trả", "PAY", "action"),
        ("thực hiện", "PERFORM", "action"),
        ("trả tiền", "INVENTED", "action"),
        ("chậm trả", "PAY", "qualifier"),
        ("trả tiền\nĐiều 2", "PAY", "action"),
    ],
)
def test_invalid_alias_is_rejected(source, symbol, kind):
    with pytest.raises(ValueError):
        validate_alias(source, symbol, kind, minimum_length=4)


def test_policy_is_required_and_aliases_are_immutable_tenant_pins():
    with pytest.raises(ValueError):
        validate_alias("trả tiền", "PAY", "action", minimum_length=None)
    alias = ApprovedAlias("trả tiền", "PAY", "action", "proposal-1")
    snapshot = ApprovedAliasSnapshot("tenant-a", 3, (alias,))
    assert snapshot.resolve("tenant-a", 3, "TRẢ TIỀN", "action").method == "TENANT_ALIAS"
    assert snapshot.resolve("tenant-b", 3, "trả tiền", "action") is None
    assert snapshot.resolve("tenant-a", 2, "trả tiền", "action") is None
    with pytest.raises(FrozenInstanceError):
        snapshot.version = 4
    with pytest.raises(ValueError):
        ApprovedAliasSnapshot(
            "tenant-a", 3, (alias, ApprovedAlias("TRẢ TIỀN", "DELIVER", "action", "p2"))
        )


def test_egress_denied_uses_shared_runtime_without_provider_request():
    runtime = ProcessingRuntime(egress_allowed=False, max_llm_calls=1)
    result = propose_aliases(
        "trả tiền", "source-1", kind="action", runtime=runtime, client=None, minimum_length=4
    )
    assert result.proposals == ()
    assert result.reason == "PROVIDER_UNAVAILABLE"
    assert runtime.llm_calls_used == 0
    assert runtime.issues[0][0] == "EGRESS_DENIED"


class Client:
    def __init__(self, symbol="PAY"):
        self.symbol = symbol
        self.calls = 0

    def configured(self):
        return True

    def complete_json(self, system, user, **kwargs):
        self.calls += 1
        return {"proposals": [{"source": "trả tiền", "symbol": self.symbol, "kind": "action"}]}


def test_proposals_debit_same_runtime_and_unknown_symbols_stay_rejected():
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    client = Client()
    first = propose_aliases(
        "trả tiền", "source-1", kind="action", runtime=runtime, client=client, minimum_length=4
    )
    assert first.proposals[0].source_ref == "source-1"
    assert first.proposals[0].status == "DRAFT"
    assert runtime.llm_calls_used == 1
    second = propose_aliases(
        "trả tiền", "source-1", kind="action", runtime=runtime, client=client, minimum_length=4
    )
    assert second.proposals == ()
    assert client.calls == 1
    bad = propose_aliases(
        "trả tiền",
        "source-1",
        kind="action",
        runtime=ProcessingRuntime(egress_allowed=True, max_llm_calls=1),
        client=Client("INVENTED"),
        minimum_length=4,
    )
    assert bad.proposals == ()
    assert bad.reason == "INVALID_PROPOSAL"


def test_missing_policy_does_not_call_llm():
    runtime = ProcessingRuntime(egress_allowed=True, max_llm_calls=1)
    client = Client()
    result = propose_aliases(
        "trả tiền", "source-1", kind="action", runtime=runtime, client=client, minimum_length=None
    )
    assert result.reason == "POLICY_NOT_FROZEN"
    assert client.calls == 0
