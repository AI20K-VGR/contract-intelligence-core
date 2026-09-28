"""Unit tests for Citation Guard — OCR span verification."""

from __future__ import annotations

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from contract_intelligence.extraction.infrastructure.persistence.orm import OcrLineORM
from contract_intelligence.shared.ai.citation_guard import (
    reconstruct_ocr_span,
    sha256_hex,
    verify_citation,
)
from contract_intelligence.shared.ai.schemas import CitationItem, CitationSegmentItem
from contract_intelligence.shared.base import new_ulid
from contract_intelligence.shared.persistence.base import Base
from contract_intelligence.shared.persistence.orm_registry import import_all_models

pytestmark = pytest.mark.asyncio


@pytest_asyncio.fixture
async def session() -> AsyncSession:
    import_all_models()
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    factory = async_sessionmaker(engine, expire_on_commit=False)
    async with factory() as sess:
        doc_id = "doc_cit_1"
        # "Hello World" spans 0..11
        sess.add(
            OcrLineORM(
                id=new_ulid("ln_"),
                tenant_id="ten_test",
                document_id=doc_id,
                page_no=1,
                line_no=1,
                text="Hello World",
                bbox="[0,0,100,20]",
                confidence="0.99",
                doc_char_start=0,
                doc_char_end=11,
            )
        )
        await sess.commit()
        yield sess
    await engine.dispose()


def _citation(*, quote: str, start: int, end: int, sha: str = "") -> CitationItem:
    return CitationItem(
        quote=quote,
        quote_sha256=sha or sha256_hex(quote),
        doc_char_start=start,
        doc_char_end=end,
        segments=[
            CitationSegmentItem(
                page_no=1,
                line_id="ln_1",
                char_start=start,
                char_end=end,
                bbox=[0.0, 0.0, 1.0, 1.0],
            )
        ],
    )


async def test_reconstruct_ocr_span(session: AsyncSession) -> None:
    span = await reconstruct_ocr_span(
        session, document_id="doc_cit_1", doc_char_start=0, doc_char_end=5
    )
    assert span == "Hello"


async def test_verify_citation_accepts_matching_quote(session: AsyncSession) -> None:
    cit = _citation(quote="Hello World", start=0, end=11)
    result = await verify_citation(session, document_id="doc_cit_1", citation=cit)
    assert result.accepted is True
    assert result.quote_sha256 == sha256_hex("Hello World")


async def test_verify_citation_rejects_mismatch(session: AsyncSession) -> None:
    cit = _citation(quote="FAKE QUOTE", start=0, end=11)
    result = await verify_citation(session, document_id="doc_cit_1", citation=cit)
    assert result.accepted is False
    assert result.reason == "quote_mismatch"


async def test_verify_citation_rejects_missing_span(session: AsyncSession) -> None:
    cit = _citation(quote="x", start=100, end=110)
    result = await verify_citation(session, document_id="doc_cit_1", citation=cit)
    assert result.accepted is False
    assert result.reason == "no_ocr_span"
