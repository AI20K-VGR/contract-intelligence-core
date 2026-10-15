from types import SimpleNamespace

from app.pipeline.ai1_snapshot_adapter import _semantic_profile


class _Profile:
    context_bounds = {"max_hops": 2, "max_nodes": 8}

    def model_copy(self, *, deep: bool):
        return self


def _request(profile: _Profile) -> SimpleNamespace:
    return SimpleNamespace(
        semantic_profile=profile,
        dossier_members=[SimpleNamespace(document_id="doc-1", snapshot_id="snap-1")],
    )


def test_semantic_profile_is_enabled_when_env_is_absent(monkeypatch):
    profile = _Profile()
    calls = []
    monkeypatch.delenv("AI2_SEMANTIC_ENABLED", raising=False)
    monkeypatch.setattr(
        "app.pipeline.frame_context.effective_context_bounds",
        lambda bounds: calls.append(bounds),
    )

    record = SimpleNamespace()
    _semantic_profile(_request(profile), record)

    assert calls == [profile.context_bounds]
    assert record.semantic_profile is profile


def test_semantic_profile_can_be_disabled_explicitly(monkeypatch):
    profile = _Profile()
    calls = []
    monkeypatch.setenv("AI2_SEMANTIC_ENABLED", "false")
    monkeypatch.setattr(
        "app.pipeline.frame_context.effective_context_bounds",
        lambda bounds: calls.append(bounds),
    )

    record = SimpleNamespace()
    _semantic_profile(_request(profile), record)

    assert calls == []
    assert record.semantic_profile is profile
