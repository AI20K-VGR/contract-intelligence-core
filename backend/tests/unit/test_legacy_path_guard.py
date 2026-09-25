from contract_intelligence.shared.ai.client import canonical_ai_service_mode


def test_canonical_mode_rejects_implicit_stub() -> None:
    assert canonical_ai_service_mode(None) == "http"
    assert canonical_ai_service_mode("stub") == "http"


def test_explicit_compatibility_mode_is_the_only_stub_opt_in() -> None:
    assert canonical_ai_service_mode("compatibility") == "stub"
    assert canonical_ai_service_mode("http") == "http"
