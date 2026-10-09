"""Recognise provider model families used by the contract-pair classifier."""

from __future__ import annotations

import re

OPENAI = "openai"
ANTHROPIC = "anthropic"
GOOGLE = "google"
UNKNOWN = "unknown"
CLASSIFIER_FAMILIES = frozenset({ANTHROPIC, GOOGLE, OPENAI})

_OPENAI = re.compile(r"(?:gpt|chatgpt)|o\d+(?![a-z])")
_ANTHROPIC = re.compile(r"claude")
_GOOGLE = re.compile(r"(?:gemini|gemma)")


def model_name(model_id: str | None) -> str:
    """Return the provider-independent model segment used for comparisons."""

    return (model_id or "").strip().rsplit("/", 1)[-1].lower()


def family(model_id: str | None) -> str:
    name = model_name(model_id)
    if _OPENAI.match(name):
        return OPENAI
    if _ANTHROPIC.match(name):
        return ANTHROPIC
    if _GOOGLE.match(name):
        return GOOGLE
    return UNKNOWN


def classifier_family_ok(model_id: str | None) -> bool:
    return family(model_id) in CLASSIFIER_FAMILIES
