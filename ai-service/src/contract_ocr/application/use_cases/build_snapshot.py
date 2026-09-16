"""Builds the ai1.snapshot.v1 handoff contract from an internal (benchmark-shaped)
Document produced by ProcessDocument.

Kept as a separate conversion step, not a change to ProcessDocument itself, so the
internal engine-comparison schema (domain/entities.py) stays free to evolve while
the frozen AI2 handoff contract (domain/snapshot.py) does not move under them.

Known, disclosed gaps versus the handoff request (see docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md):
- `blocks[]` is always empty; no heading/paragraph grouping is implemented yet.
- `tables[]` is always empty; no table-structure detection exists in any engine yet.
- "PARTIAL" is inferred with two interim heuristics (missing line geometry, low
  OCR confidence) pending a real partial-extraction signal from the engines.
"""

import hashlib
from pathlib import Path

import pymupdf
from PIL import Image

from contract_ocr.domain.entities import Document as InternalDocument
from contract_ocr.domain.entities import Line as InternalLine
from contract_ocr.domain.entities import Page as InternalPage
from contract_ocr.domain.enums import InputType, Status
from contract_ocr.domain.snapshot import (
    DocumentRole,
    DocumentSnapshot,
    DossierDocumentRef,
    DossierManifest,
    EngineInfo,
    PageImageRef,
    PageStatus,
    SnapshotInputType,
    SnapshotLine,
    SnapshotPage,
    SnapshotWord,
)
from contract_ocr.infrastructure.image.renderer import PdfRenderer

LOW_CONFIDENCE_THRESHOLD = 0.5
_INPUT_TYPE_MAP: dict[InputType, SnapshotInputType] = {
    InputType.TEXT_LAYER: "TEXT_LAYER",
    InputType.SCANNED: "SCANNED_OCR",
    InputType.MIXED: "MIXED",
}


def source_digest(path: str) -> str:
    digest = hashlib.sha256()
    with Path(path).open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return f"sha256:{digest.hexdigest()}"


def id_prefix(document_id: str) -> str:
    """`s{n}` embeds the snapshot schema major version in every line/word id so a
    consumer can tell the id scheme's era without loading the enclosing document."""
    from contract_ocr.domain.snapshot import SNAPSHOT_SCHEMA_VERSION

    major = SNAPSHOT_SCHEMA_VERSION.rsplit(".v", 1)[-1]
    return f"{document_id}:s{major}"


class BuildSnapshot:
    def __init__(self, renderer: PdfRenderer | None = None, image_dpi: int = 150) -> None:
        self.renderer = renderer or PdfRenderer()
        self.image_dpi = image_dpi

    def execute(
        self,
        document: InternalDocument,
        *,
        snapshot_id: str,
        dossier_id: str,
        document_role: DocumentRole,
        filename: str,
        engine_name: str,
        engine_version: str,
        image_output_dir: Path,
        image_uri_prefix: str,
    ) -> DocumentSnapshot:
        image_output_dir.mkdir(parents=True, exist_ok=True)
        digest = source_digest(document.source_file)
        pages: list[SnapshotPage] = []
        with pymupdf.open(document.source_file) as pdf:
            for index, internal_page in enumerate(document.pages):
                try:
                    page_snapshot = self._build_page(
                        internal_page,
                        pdf[index],
                        document_id=document.document_id,
                        image_output_dir=image_output_dir,
                        image_uri_prefix=image_uri_prefix,
                    )
                except Exception as exc:
                    # A page must never make the whole snapshot disappear (handoff §5
                    # "OCR lỗi"); fall back to the same 1x1 placeholder convention
                    # documented in OUTPUT_SCHEMA.md for unreadable page geometry.
                    page_snapshot = SnapshotPage(
                        page_number=internal_page.page_number,
                        input_type=_INPUT_TYPE_MAP[internal_page.input_type],
                        source_page_width=1,
                        source_page_height=1,
                        rotation_degrees=0,
                        page_image_ref=None,
                        status="FAILED",
                        error=f"{type(exc).__name__}: {exc}",
                    )
                pages.append(page_snapshot)
        input_types = {p.input_type for p in pages}
        doc_input_type: SnapshotInputType = (
            next(iter(input_types)) if len(input_types) == 1 else "MIXED"
        )
        return DocumentSnapshot(
            snapshot_id=snapshot_id,
            source_digest=digest,
            dossier_id=dossier_id,
            document_id=document.document_id,
            filename=filename,
            document_role=document_role,
            input_type=doc_input_type,
            engine=EngineInfo(name=engine_name, version=engine_version),
            page_count=len(pages),
            processing_ms=sum(p.processing_ms for p in document.pages),
            pages=pages,
        )

    def _build_page(
        self,
        internal_page: InternalPage,
        pdf_page: pymupdf.Page,
        *,
        document_id: str,
        image_output_dir: Path,
        image_uri_prefix: str,
    ) -> SnapshotPage:
        prefix = id_prefix(document_id)
        page_no = internal_page.page_number
        image = self.renderer.render(pdf_page, self.image_dpi)
        Image.fromarray(image).save(image_output_dir / f"page-{page_no:03d}.png")
        image_ref = PageImageRef(
            uri=f"{image_uri_prefix}/page-{page_no:03d}.png",
            width_px=image.shape[1],
            height_px=image.shape[0],
        )
        common = dict(
            page_number=page_no,
            input_type=_INPUT_TYPE_MAP[internal_page.input_type],
            source_page_width=pdf_page.rect.width,
            source_page_height=pdf_page.rect.height,
            rotation_degrees=pdf_page.rotation,
            page_image_ref=image_ref,
        )

        # A page with no text and no imagery at all is unambiguously blank in the
        # source, regardless of how the classifier routed it (it still tries OCR,
        # which then reports SKIPPED/FAILED on empty output). Ground truth wins:
        # handoff §5 requires blank pages to be SUCCESS + "blank_page", not an error.
        if not pdf_page.get_text().strip() and not pdf_page.get_image_info():
            return SnapshotPage(**common, status="SUCCESS", text="", warnings=["blank_page"])

        if internal_page.status is Status.FAILED:
            return SnapshotPage(
                **common, status="FAILED", error=internal_page.error or "OCR failed"
            )
        if internal_page.status is Status.SKIPPED:
            reason = internal_page.error or "no OCR engine selected for this page"
            return SnapshotPage(**common, status="FAILED", error=f"SKIPPED: {reason}")

        return self._build_success_page(common, internal_page, prefix)

    def _build_success_page(
        self, common: dict, internal_page: InternalPage, prefix: str
    ) -> SnapshotPage:
        page_no = internal_page.page_number
        if not internal_page.lines or not any(line.text.strip() for line in internal_page.lines):
            return SnapshotPage(**common, status="SUCCESS", text="", warnings=["blank_page"])

        lines_payload: list[SnapshotLine] = []
        words_payload: list[SnapshotWord] = []
        text_parts: list[str] = []
        page_cursor = 0
        line_seq = 0
        word_seq = 0
        missing_geometry = 0
        low_confidence = 0

        for line in internal_page.lines:
            start = page_cursor
            end = start + len(line.text)
            text_parts.append(line.text)
            page_cursor = end + 1  # account for the "\n" joiner

            if line.bbox is None:
                missing_geometry += 1
                continue
            if line.confidence is not None and line.confidence < LOW_CONFIDENCE_THRESHOLD:
                low_confidence += 1

            line_seq += 1
            line_id = f"{prefix}:p{page_no:03d}:l{line_seq:03d}"
            line_words = self._build_words(line, line_id, prefix, page_no, word_seq)
            word_seq += len(line_words)
            lines_payload.append(
                SnapshotLine(
                    line_id=line_id,
                    text=line.text,
                    page_char_start=start,
                    page_char_end=end,
                    bbox_normalized=[line.bbox.x1, line.bbox.y1, line.bbox.x2, line.bbox.y2],
                    word_ids=[w.word_id for w in line_words],
                )
            )
            words_payload.extend(line_words)

        warnings = []
        if missing_geometry:
            warnings.append("missing_line_geometry")
        if low_confidence:
            warnings.append("low_confidence_lines")
        status: PageStatus = "PARTIAL" if warnings else "SUCCESS"

        return SnapshotPage(
            **common,
            status=status,
            text="\n".join(text_parts),
            lines=lines_payload,
            words=words_payload,
            warnings=warnings,
        )

    @staticmethod
    def _build_words(
        line: InternalLine, line_id: str, prefix: str, page_no: int, start_seq: int
    ) -> list[SnapshotWord]:
        words: list[SnapshotWord] = []
        cursor = 0
        seq = start_seq
        for word in line.words:
            idx = line.text.index(word.text, cursor)
            w_start, w_end = idx, idx + len(word.text)
            cursor = w_end
            if word.bbox is None:
                continue
            seq += 1
            words.append(
                SnapshotWord(
                    word_id=f"{prefix}:p{page_no:03d}:w{seq:04d}",
                    line_id=line_id,
                    text=word.text,
                    line_char_start=w_start,
                    line_char_end=w_end,
                    bbox_normalized=[word.bbox.x1, word.bbox.y1, word.bbox.x2, word.bbox.y2],
                    confidence=word.confidence,
                )
            )
        return words


def build_dossier_manifest(
    dossier_id: str, documents: list[tuple[str, str, DocumentRole]]
) -> DossierManifest:
    return DossierManifest(
        dossier_id=dossier_id,
        documents=[
            DossierDocumentRef(document_id=doc_id, filename=filename, document_role=role)
            for doc_id, filename, role in documents
        ],
    )
