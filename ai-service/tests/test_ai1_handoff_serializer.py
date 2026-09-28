from __future__ import annotations

from contract_ocr.application.use_cases.ai2_snapshot_handoff import to_ai2_snapshot_v1
from contract_ocr.domain.snapshot import (
    DocumentSnapshot,
    EngineInfo,
    SnapshotLine,
    SnapshotPage,
    SnapshotWord,
)

from app.contracts.schema_validation import validate_contract
from app.pipeline.ai1_snapshot_adapter import adapt_snapshot_v1


def test_ai1_handoff_serializer_emits_ai2_canonical_snapshot() -> None:
    snapshot = DocumentSnapshot(
        snapshot_id="ocr-run-test-001",
        source_digest=f"sha256:{'a' * 64}",
        dossier_id="dossier-test-001",
        document_id="doc-test-001",
        filename="contract.pdf",
        document_role="contract",
        input_type="TEXT_LAYER",
        engine=EngineInfo(name="pymupdf", version="test"),
        page_count=1,
        processing_ms=1.0,
        pages=[
            SnapshotPage(
                page_number=1,
                status="SUCCESS",
                input_type="TEXT_LAYER",
                source_page_width=100,
                source_page_height=100,
                text="Hello world",
                lines=[
                    SnapshotLine(
                        line_id="line-1",
                        text="Hello world",
                        page_char_start=0,
                        page_char_end=11,
                        bbox_normalized=[0.1, 0.1, 0.9, 0.2],
                        geometry_provenance="MEASURED",
                        word_ids=["word-1"],
                    )
                ],
                words=[
                    SnapshotWord(
                        word_id="word-1",
                        line_id="line-1",
                        text="Hello",
                        line_char_start=0,
                        line_char_end=5,
                        bbox_normalized=[0.1, 0.1, 0.4, 0.2],
                        geometry_provenance="MEASURED",
                        confidence=0.99,
                    )
                ],
                table_status="NOT_PRESENT",
            )
        ],
    )

    payload = to_ai2_snapshot_v1(snapshot, created_at="2026-09-22T10:00:00Z")

    validate_contract(payload, "ai1.snapshot.v1.schema.json", error_code="TEST")
    adapt_snapshot_v1(payload)
    assert payload["source_digest"] == "a" * 64
    assert payload["pages"][0]["page_no"] == 1
    assert payload["pages"][0]["lines"][0]["raw_text"] == "Hello world"
    assert payload["pages"][0]["lines"][0]["words"][0]["char_end"] == 5
