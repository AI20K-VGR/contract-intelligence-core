"""Transport boundary primitives for canonical events and UI protocols."""

from .events import (
    DeliveryClassification,
    DeliveryDecision,
    DeliveryStatus,
    EventEnvelope,
    SseSession,
    classify_delivery,
    map_to_agui,
    validate_a2ui_catalog,
    validate_scope,
)

__all__ = [
    "DeliveryClassification",
    "DeliveryDecision",
    "DeliveryStatus",
    "EventEnvelope",
    "SseSession",
    "classify_delivery",
    "map_to_agui",
    "validate_a2ui_catalog",
    "validate_scope",
]
