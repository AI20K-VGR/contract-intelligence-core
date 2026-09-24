"""Pipeline public names loaded lazily to keep tool/pipeline imports acyclic."""

from __future__ import annotations

from importlib import import_module


_EXPORTS = {
    "CandidatePairer": ("app.pipeline.candidate", "CandidatePairer"),
    "ClauseChunker": ("app.pipeline.clause", "ClauseChunker"),
    "FactExtractor": ("app.pipeline.fact", "FactExtractor"),
    "GroundingGate": ("app.pipeline.grounding", "GroundingGate"),
    "HandoffValidator": ("app.pipeline.handoff", "HandoffValidator"),
    "IndexStore": ("app.pipeline.index", "IndexStore"),
    "ObjectRouter": ("app.pipeline.router", "ObjectRouter"),
    "TablePipeline": ("app.pipeline.table", "TablePipeline"),
    "run_idp": ("app.pipeline.idp", "run_idp"),
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
