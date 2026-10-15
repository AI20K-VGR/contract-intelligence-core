"""Model family of a provider model id (RT-04), shared by the labeler (P1) and classifier (P3/P5).

The id may carry a router prefix (``gh/gpt-4o-mini``, ``openai/gpt-4.1``): only the segment after
the last ``/`` counts. Anything not recognised is ``unknown`` and callers fail closed on it.
"""

from app.pipeline.contract_graph.model_family import (
    ANTHROPIC,
    CLASSIFIER_FAMILIES,
    GOOGLE,
    OPENAI,
    UNKNOWN,
    classifier_family_ok,
    family,
    model_name,
)

__all__ = [
    "ANTHROPIC", "CLASSIFIER_FAMILIES", "GOOGLE", "OPENAI", "UNKNOWN",
    "classifier_family_ok", "classifier_model_differs_from_labeler", "family", "model_name",
]


def classifier_model_differs_from_labeler(classifier: str | None, labeler: str | None) -> bool:
    """Require a different concrete model from the frozen labeler model."""

    classifier_name, labeler_name = model_name(classifier), model_name(labeler)
    if not labeler_name:
        return bool(classifier_name)
    return bool(classifier_name and classifier_name != labeler_name
                and not classifier_name.startswith(labeler_name + "-")
                and not labeler_name.startswith(classifier_name + "-"))
