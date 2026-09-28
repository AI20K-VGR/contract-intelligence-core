from types import SimpleNamespace

from contract_intelligence.contract.interfaces.api.routers.contract_router import (
    ai2_search_policy_flags,
)


def test_search_policy_stays_closed_until_egress_is_enabled(monkeypatch) -> None:
    monkeypatch.setattr(
        "contract_intelligence.config.settings.get_settings",
        lambda: SimpleNamespace(ai2_query_egress_allowed=False, ai2_query_use_vector=False),
    )
    assert ai2_search_policy_flags() == {
        "egress_allowed": False,
        "use_llm": False,
        "use_vector": False,
    }


def test_search_policy_enables_llm_when_egress_is_allowed(monkeypatch) -> None:
    monkeypatch.setattr(
        "contract_intelligence.config.settings.get_settings",
        lambda: SimpleNamespace(ai2_query_egress_allowed=True, ai2_query_use_vector=False),
    )
    assert ai2_search_policy_flags() == {
        "egress_allowed": True,
        "use_llm": True,
        "use_vector": False,
    }
