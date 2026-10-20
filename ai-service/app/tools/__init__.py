"""Tool public names loaded lazily to keep tool/pipeline imports acyclic."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "ToolBlocked": ("app.tools.gateway", "ToolBlocked"),
    "ToolGateway": ("app.tools.gateway", "ToolGateway"),
    "DossierRecord": ("app.tools.store", "DossierRecord"),
    "InMemorySnapshotStore": ("app.tools.store", "InMemorySnapshotStore"),
    "SQLiteJobStore": ("app.tools.jobs", "SQLiteJobStore"),
    "JobOwnershipConflict": ("app.tools.jobs", "JobOwnershipConflict"),
    "JobNonceReplayConflict": ("app.tools.jobs", "JobNonceReplayConflict"),
}

__all__ = list(_EXPORTS)


def __getattr__(name: str):
    target = _EXPORTS.get(name)
    if target is None:
        raise AttributeError(f"module {__name__!r} has no attribute {name!r}")
    module_name, attribute_name = target
    value = getattr(import_module(module_name), attribute_name)
    globals()[name] = value
    return value
