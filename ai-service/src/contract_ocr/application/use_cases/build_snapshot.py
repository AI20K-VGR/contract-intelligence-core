"""Builds the ai1.snapshot.v1 handoff contract from an internal (benchmark-shaped)
Document produced by ProcessDocument.

Kept as a separate conversion step, not a change to ProcessDocument itself, so the
internal engine-comparison schema (domain/entities.py) stays free to evolve while
the frozen AI2 handoff contract (domain/snapshot.py) does not move under them.

Known, disclosed gaps versus the handoff request (see docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md):
- `blocks[]` is always empty; no heading/paragraph grouping is implemented yet.
- `tables[]` IS now populated for every input type: native `find_tables()` for
  TEXT_LAYER (pymupdf_extractor.py), bordered ruling-line grid detection for
  SCANNED_OCR/MIXED with a non-Mistral engine (extract_scanned_tables.py, bordered-
  table only -- borderless is a real, disclosed gap, see docs/ai1-decisions.md
  D5/D7), and Mistral OCR's own markdown pipe-tables (infrastructure/ocr/
  markdown_tables.py, borderless-capable since it reads Mistral's own table
  segmentation rather than pixels) when `engine.name == "mistral_ocr"` -- see
  ProcessDocument.run_ocr_job, which prefers an engine-supplied `OCRResult.tables`
  over the pixel detector whenever one is present. The separate, tested
  `contract_ocr.table_reconstruct` package (word/bbox-based) still has no caller
  here; it targets a different problem (native/OCR word-level fragments with no
  ready-made row/column structure), not needed for the Mistral path.
- `table_continuity[]` (document-level, added for task section 11) now links a
  page's last table to the next page's first when they look like one table split by
  a page break -- hard guards (including a repeated-total-row / new-section-heading
  / anchor-reset check, and a leading-column sequence-number continuity signal in
  the rule score) then a deterministic score, with an opt-in DeepSeek gray-zone
  agent for the remaining ambiguous middle (`table_continuity_agent`, off by
  default -- see `application/use_cases/table_continuity.py`'s own docstring,
  mirroring `backend/app/table_continuity.py`'s three-tier design). It records a
  MERGE/SPLIT/NEEDS_REVIEW decision, never merges rows/cells itself.
- `nodes[]` (document-level clause/section hierarchy, added for task section 8) IS
  now populated via BuildStructure, but only within-page: a clause whose body is
  split across a page break is not spliced back together yet (see
  build_structure.py's own docstring) -- cross-page *structural* continuity (as
  opposed to tables) remains deferred.
- "PARTIAL" is inferred with two interim heuristics (missing line geometry, low
  OCR confidence) pending a real partial-extraction signal from the engines.
"""

import hashlib
from pathlib import Path

import pymupdf
from PIL import Image

from contract_ocr.application.use_cases.build_structure import BuildStructure
from contract_ocr.application.use_cases.table_continuity import link_continuities
from contract_ocr.domain.entities import Document as InternalDocument
from contract_ocr.domain.entities import Line as InternalLine
from contract_ocr.domain.entities import Page as InternalPage
from contract_ocr.domain.entities import Table as InternalTable
from contract_ocr.domain.enums import InputType, Status
from contract_ocr.domain.snapshot import (
    Cell,
    DocumentRole,
    DocumentSnapshot,
    DossierDocumentRef,
    DossierManifest,
    EngineInfo,
    PageImageRef,
    PageStatus,
    Row,
    SnapshotInputType,
    SnapshotLine,
    SnapshotPage,
    SnapshotWord,
    Table,
    TableContinuityLink,
    TableStatus,
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
    def __init__(
        self,
        renderer: PdfRenderer | None = None,
        image_dpi: int = 150,
        structure_builder: BuildStructure | None = None,
        table_continuity_agent: bool = False,
    ) -> None:
        self.renderer = renderer or PdfRenderer()
        self.image_dpi = image_dpi
        self.structure_builder = structure_builder or BuildStructure()
        # Opt-in DeepSeek gray-zone agent for table_continuity.link_continuities, off
        # by default -- mirrors backend/app's per-job `table_continuity_agent` config,
        # never a deployment-wide default (see table_continuity.py's own docstring).
        self.table_continuity_agent = table_continuity_agent

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
        # Internal Line.line_id -> emitted SnapshotLine.line_id, populated as pages
        # are built; BuildStructure uses it so a node's line_ids are ids a consumer
        # can actually resolve in `pages[].lines`, not the internal benchmark id.
        line_id_map: dict[str, str] = {}
        with pymupdf.open(document.source_file) as pdf:
            for index, internal_page in enumerate(document.pages):
                try:
                    page_snapshot = self._build_page(
                        internal_page,
                        pdf[index],
                        document_id=document.document_id,
                        image_output_dir=image_output_dir,
                        image_uri_prefix=image_uri_prefix,
                        line_id_map=line_id_map,
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
        nodes = self.structure_builder.execute(document, line_id_map)
        continuity_links = link_continuities(
            [(page.page_number, page.tables) for page in document.pages],
            config={"table_continuity_agent": self.table_continuity_agent},
        )
        table_continuity = [
            TableContinuityLink(
                from_table_id=link.from_table_id,
                from_page=link.from_page,
                to_table_id=link.to_table_id,
                to_page=link.to_page,
                decision=link.decision,
                confidence=link.confidence,
                reason_codes=link.reason_codes,
            )
            for link in continuity_links
        ]
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
            table_continuity=table_continuity,
            processing_ms=sum(p.processing_ms for p in document.pages),
            pages=pages,
            nodes=nodes,
        )

    def _build_page(
        self,
        internal_page: InternalPage,
        pdf_page: pymupdf.Page,
        *,
        document_id: str,
        image_output_dir: Path,
        image_uri_prefix: str,
        line_id_map: dict[str, str],
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

        return self._build_success_page(common, internal_page, prefix, line_id_map)

    def _build_success_page(
        self,
        common: dict,
        internal_page: InternalPage,
        prefix: str,
        line_id_map: dict[str, str],
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
            line_id_map[line.line_id] = line_id
            line_words = self._build_words(line, line_id, prefix, page_no, word_seq)
            word_seq += len(line_words)
            lines_payload.append(
                SnapshotLine(
                    line_id=line_id,
                    text=line.text,
                    page_char_start=start,
                    page_char_end=end,
                    bbox_normalized=[line.bbox.x1, line.bbox.y1, line.bbox.x2, line.bbox.y2],
                    # `line.geometry_provenance` is guaranteed non-None here: the domain
                    # Line model itself refuses a bbox without one (section 6 gate).
                    geometry_provenance=line.geometry_provenance,
                    word_ids=[w.word_id for w in line_words],
                )
            )
            words_payload.extend(line_words)

        warnings = []
        if missing_geometry:
            warnings.append("missing_line_geometry")
        if low_confidence:
            warnings.append("low_confidence_lines")
        # Engine review flags name internal line ids; rewrite them to the ids a
        # consumer can resolve in `lines` (a line with no geometry has none).
        review, informational = [], []
        for code in internal_page.warnings:
            if code.startswith("needs_review:"):
                _, reason, internal_id = code.split(":", 2)
                review.append(f"needs_review:{reason}:{line_id_map.get(internal_id, 'unpositioned')}")
            else:
                informational.append(code)
        status: PageStatus = "PARTIAL" if warnings or review else "SUCCESS"
        warnings = [*warnings, *review, *informational]
        table_status, tables_payload = self._build_tables(internal_page.tables, prefix, page_no)

        return SnapshotPage(
            **common,
            status=status,
            text="\n".join(text_parts),
            lines=lines_payload,
            words=words_payload,
            table_status=table_status,
            tables=tables_payload,
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
                    geometry_provenance=word.geometry_provenance,
                    confidence=word.confidence,
                )
            )
        return words

    @staticmethod
    def _build_tables(
        internal_tables: list[InternalTable],
        prefix: str,
        page_no: int,
    ) -> tuple[TableStatus, list[Table]]:
        # A detector runs for every input type now: native `find_tables()` for
        # TEXT_LAYER (pymupdf_extractor.py), bordered ruling-line grid detection for
        # SCANNED_OCR/MIXED (extract_scanned_tables.py). Both are BORDERED-table only
        # -- a borderless table is not detected either way (section 9's word-
        # alignment approach needs word-level OCR this codebase does not produce for
        # scanned pages -- see docs/ai1-decisions.md). `NOT_PRESENT` therefore means
        # "no bordered table detected", not "definitely no table of any kind" --
        # still a real distinction from `NOT_CHECKED` (section 15), which is reserved
        # for genuinely un-attempted detection (a FAILED/SKIPPED page never reaches
        # this method at all, so it keeps the model default).
        if not internal_tables:
            return "NOT_PRESENT", []

        tables: list[Table] = []
        for t_index, table in enumerate(internal_tables, 1):
            rows: list[Row] = []
            for r_index, row in enumerate(table.rows, 1):
                cells: list[Cell] = []
                for c_index, cell in enumerate(row.cells, 1):
                    cell_id = (
                        f"{prefix}:p{page_no:03d}:t{t_index:03d}:r{r_index:03d}:c{c_index:03d}"
                    )
                    if cell.bbox is None:
                        cells.append(Cell(cell_id=cell_id, text=cell.text))
                    else:
                        cells.append(
                            Cell(
                                cell_id=cell_id,
                                text=cell.text,
                                bbox_normalized=[
                                    cell.bbox.x1,
                                    cell.bbox.y1,
                                    cell.bbox.x2,
                                    cell.bbox.y2,
                                ],
                                geometry_provenance=cell.geometry_provenance,
                            )
                        )
                rows.append(
                    Row(
                        row_id=f"{prefix}:p{page_no:03d}:t{t_index:03d}:r{r_index:03d}", cells=cells
                    )
                )
            # `table.bbox`/`geometry_provenance` are guaranteed non-None here: the
            # internal Table model refuses a table without them (section 6 gate).
            tables.append(
                Table(
                    table_id=table.table_id,
                    bbox_normalized=[table.bbox.x1, table.bbox.y1, table.bbox.x2, table.bbox.y2],
                    geometry_provenance=table.geometry_provenance,
                    header=table.header,
                    rows=rows,
                )
            )
        return "DETECTED", tables


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
