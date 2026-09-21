"""Domain exception hierarchy.

Exception trong domain layer là pure Python — không phụ thuộc FastAPI/HTTP.
Mapping sang HTTP status code được làm trong ``interfaces/api/exception_handler.py``.
"""

from __future__ import annotations

from enum import StrEnum
from typing import Any


class DomainErrorCode(StrEnum):
    """Mã lỗi nghiệp vụ — bounded context tự định nghĩa thêm khi cần."""

    # Lỗi chung
    NOT_FOUND = "NOT_FOUND"
    VALIDATION_FAILED = "VALIDATION_FAILED"
    INVARIANT_VIOLATION = "INVARIANT_VIOLATION"

    # Vòng đời hợp đồng
    INVALID_STATE_TRANSITION = "INVALID_STATE_TRANSITION"
    JOB_ALREADY_RUNNING = "JOB_ALREADY_RUNNING"
    DOSSIER_HAS_PENDING_REVIEW = "DOSSIER_HAS_PENDING_REVIEW"

    # HITL review
    REVIEW_VERSION_CONFLICT = "REVIEW_VERSION_CONFLICT"
    REVIEW_ITEM_NOT_OPEN = "REVIEW_ITEM_NOT_OPEN"

    # Conflict
    INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"

    # Hệ thống
    EXTERNAL_SERVICE_ERROR = "EXTERNAL_SERVICE_ERROR"
    STORAGE_ERROR = "STORAGE_ERROR"


class DomainException(Exception):
    """Base class cho mọi exception nghiệp vụ.

    Không bao giờ expose trực tiếp ra HTTP — ``interfaces/api`` sẽ map sang
    response JSON theo format ``ApiResponse`` chuẩn (xem ``shared/responses.py``).
    """

    def __init__(
        self,
        code: DomainErrorCode,
        message: str,
        *,
        details: dict[str, Any] | None = None,
        cause: Exception | None = None,
    ) -> None:
        super().__init__(message)
        self.code = code
        self.message = message
        self.details = details or {}
        self.cause = cause

    def __str__(self) -> str:  # pragma: no cover — trivial
        return f"[{self.code.value}] {self.message}"


class NotFoundError(DomainException):
    """Entity không tồn tại — tương ứng HTTP 404."""

    def __init__(self, entity_type: str, entity_id: str) -> None:
        super().__init__(
            DomainErrorCode.NOT_FOUND,
            f"{entity_type} với id={entity_id!r} không tồn tại",
            details={"entity_type": entity_type, "entity_id": entity_id},
        )


class ValidationError(DomainException):
    """Input không hợp lệ — HTTP 422."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(DomainErrorCode.VALIDATION_FAILED, message, details=details)


class InvariantViolation(DomainException):
    """Vi phạm bất biến nghiệp vụ — HTTP 409."""

    def __init__(self, message: str, **details: Any) -> None:
        super().__init__(DomainErrorCode.INVARIANT_VIOLATION, message, details=details)


class InvalidStateTransition(DomainException):
    """Chuyển trạng thái không hợp lệ — HTTP 409."""

    def __init__(self, from_state: str, to_state: str, entity: str) -> None:
        super().__init__(
            DomainErrorCode.INVALID_STATE_TRANSITION,
            f"{entity}: không thể chuyển từ {from_state!r} sang {to_state!r}",
            details={"entity": entity, "from": from_state, "to": to_state},
        )


class ReviewVersionConflict(DomainException):
    """Optimistic concurrency fail trên ``review_item.version`` — HTTP 409."""

    def __init__(
        self,
        review_item_id: str,
        expected_version: int,
        current_version: int,
        *,
        current_state: dict[str, Any] | None = None,
    ) -> None:
        message = (
            f"Version conflict: another action was submitted before yours "
            f"(current version: {current_version})."
        )
        details: dict[str, Any] = {
            "review_item_id": review_item_id,
            "expected_version": expected_version,
            "current_version": current_version,
        }
        if current_state is not None:
            details["current_state"] = current_state
        super().__init__(
            DomainErrorCode.REVIEW_VERSION_CONFLICT,
            message,
            details=details,
        )
        self.current_state = current_state
