"""Unit tests cho shared/ utilities."""

from datetime import datetime, timedelta, timezone

from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.exceptions import (
    DomainErrorCode,
    DomainException,
    NotFoundError,
    ReviewVersionConflict,
)
from contract_intelligence.shared.utils import normalize_text, safe_filename, to_iso_z


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


class TestSafeFilename:
    def test_strips_path_traversal(self) -> None:
        assert safe_filename("../../etc/passwd") == "passwd"
        assert safe_filename(r"..\..\windows\system32\config") == "config"

    def test_fallback_on_empty(self) -> None:
        assert safe_filename(None) == "upload.bin"
        assert safe_filename("...") == "upload.bin"


class TestToIsoZ:
    def test_normalizes_offset_to_utc_z(self) -> None:
        plus7 = datetime(2026, 1, 1, 19, 0, tzinfo=timezone(timedelta(hours=7)))
        assert to_iso_z(plus7) == "2026-01-01T12:00:00Z"

    def test_naive_assumed_utc(self) -> None:
        naive = datetime(2026, 1, 1, 12, 0)
        assert to_iso_z(naive) == "2026-01-01T12:00:00Z"


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
