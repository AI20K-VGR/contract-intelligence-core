from types import SimpleNamespace

from contract_intelligence.api.v1.dossiers import _no_semantic_result_coming


def test_query_semantic_gate_defaults_on(monkeypatch):
    monkeypatch.delenv("AI2_SEMANTIC_ENABLED", raising=False)

    run = SimpleNamespace(status="running", config_snapshot="{}")

    assert _no_semantic_result_coming(run) is None


def test_query_semantic_gate_can_be_disabled_explicitly(monkeypatch):
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "false")

    run = SimpleNamespace(status="running", config_snapshot="{}")

    assert _no_semantic_result_coming(run) == "SEMANTIC_DISABLED"
