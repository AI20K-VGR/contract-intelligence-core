"""Model family of a provider model id (RT-04), shared by the labeler (P1) and classifier (P3/P5).

The id may carry a router prefix (``gh/gpt-4o-mini``, ``openai/gpt-4.1``): only the segment after
the last ``/`` counts. Anything not recognised is ``unknown`` and callers fail closed on it.
"""

from __future__ import annotations

import re

OPENAI = "openai"
ANTHROPIC = "anthropic"
UNKNOWN = "unknown"

# ``o\d`` reasoning models ("o1", "o3-mini"); a bare "o…" word ("openchat", "olmo") is not one
_OPENAI = re.compile(r"(?:gpt|chatgpt)|o\d+(?![a-z])")
_ANTHROPIC = re.compile(r"claude")


def family(model_id: str | None) -> str:
    name = (model_id or "").strip().rsplit("/", 1)[-1].lower()
    if _OPENAI.match(name):
        return OPENAI
    if _ANTHROPIC.match(name):
        return ANTHROPIC
    return UNKNOWN
