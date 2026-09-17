"""Unit tests cho shared/ utilities."""

from contract_intelligence.shared.base import new_ulid, utcnow
from contract_intelligence.shared.utils import normalize_text
from contract_intelligence.shared.exceptions import (
    DomainException,
    DomainErrorCode,
    NotFoundError,
    ReviewVersionConflict,
)


class TestNewUlid:
    def test_prefix(self) -> None:
        uid = new_ulid("dos_")
        assert uid.startswith("dos_")

    def test_unique(self) -> None:
        u1 = new_ulid()
        u2 = new_ulid()
        assert u1 != u2


class TestNormalizeText:
    def test_nfc_normalizes_vietnamese(self) -> None:
        # "hợp đồng" với Unicode cách viết khác nhau
        raw = "h\u006f\u0302p \u0111\u006f\u0302ng"  # decomposed
        normalized = normalize_text(raw)
        assert "\u0302" not in normalized  # đã compose thành "ô", "ồ"


class TestDomainExceptions:
    def test_not_found_error_code(self) -> None:
        err = NotFoundError("Dossier", "dos_abc")
        assert err.code == DomainErrorCode.NOT_FOUND
        assert "dos_abc" in str(err)

    def test_review_version_conflict_details(self) -> None:
        err = ReviewVersionConflict(
            review_item_id="ri_123",
            expected_version=3,
            current_version=4,
        )
        assert err.details["expected_version"] == 3
        assert err.details["current_version"] == 4
        assert err.code == DomainErrorCode.REVIEW_VERSION_CONFLICT

    def test_domain_exception_chain(self) -> None:
        cause = ValueError("root cause")
        err = DomainException(
            code=DomainErrorCode.EXTERNAL_SERVICE_ERROR,
            message="AI service unavailable",
            cause=cause,
        )
        assert err.cause is cause
