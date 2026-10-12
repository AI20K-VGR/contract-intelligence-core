import hashlib
import json
import logging
import threading
from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from time import perf_counter

import numpy as np

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.application.ports.pdf_extractor import (
    PageQualityAssessor,
    PdfExtractor,
    Preprocessor,
    Renderer,
)
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.duplicate_pages import mark_duplicate_pages
from contract_ocr.application.use_cases.extract_scanned_tables import build_scanned_tables
from contract_ocr.domain.entities import Context, Document, Experiment, Page
from contract_ocr.domain.enums import InputType, Status
from contract_ocr.infrastructure.image.page_ink import is_blank, unexplained_lines
from contract_ocr.infrastructure.observability import observation

logger = logging.getLogger("contract_ocr.pages")

# Share of the pages to OCR that may be hard to read before the whole document
# is refused unread: past it the reading would mostly be guesswork, paid for
# page by page, and a rescan is the cheaper fix.
MAX_LOW_QUALITY_SHARE = 0.3
# ...and never on fewer poor pages than this: a text-layer contract whose only
# scan is a speckled signature page (1 of 1 OCR pages) must still be read.
MIN_LOW_QUALITY_PAGES = 3


class LowQualityDocument(Exception):
    """Too many pages are too poor to read; nothing was sent to the OCR engine."""

    def __init__(self, pages: dict[int, list[str]], ocr_pages: int) -> None:
        self.pages, self.ocr_pages = pages, ocr_pages
        listed = ", ".join(f"p{page}:{'+'.join(reasons)}" for page, reasons in pages.items())
        super().__init__(
            f"{len(pages)} of {ocr_pages} scanned pages are too poor to read ({listed}); "
            "rescan the document"
        )


class ProcessDocument:
    def __init__(
        self,
        extractor: PdfExtractor,
        renderer: Renderer,
        preprocessor: Preprocessor,
        classifier: PdfPageClassifier,
        quality: PageQualityAssessor | None = None,
        max_low_quality_share: float = MAX_LOW_QUALITY_SHARE,
        min_low_quality_pages: int = MIN_LOW_QUALITY_PAGES,
    ) -> None:
        """`quality` checks every page to OCR before any OCR call. At least
        `min_low_quality_pages` hard-to-read pages that are also at least
        `max_low_quality_share` of them raise `LowQualityDocument` and nothing
        is sent; otherwise each such page is read once only
        (`Context.low_quality`) and flagged `low_quality_scan:<reasons>`.
        None skips the check."""
        self.extractor, self.renderer, self.preprocessor, self.classifier = (
            extractor,
            renderer,
            preprocessor,
            classifier,
        )
        self.quality = quality
        self.max_low_quality_share = max_low_quality_share
        self.min_low_quality_pages = min_low_quality_pages

    def execute(
        self,
        source: str,
        document_id: str,
        experiment: Experiment,
        engine: OCREngine | None,
        output: Path,
        run_id: str,
        dpi: int = 300,
        max_workers: int = 1,
        on_page_done: Callable[[int, int], None] | None = None,
    ) -> Document:
        """max_workers only parallelizes the OCR engine call itself (network-bound API
        engines): PDF reading/classification/rendering always stays sequential because
        the underlying PDF SDK page object is not safe for concurrent access, and a
        single loaded local model is not safe (or faster) for concurrent inference
        either. Callers must only raise max_workers for stateless remote engines.

        Pages are read in two passes so memory does not grow with the document:

        1. Survey, one page at a time: classify, render, decide blank / text-layer /
           duplicate, and judge scan quality. The image is dropped before the next
           page. The low-quality gate then sees every page before any OCR call.
        2. OCR: the pages to read are rendered again, in order, each only once one
           of `max_workers` slots is free, and released when their OCR ends. At
           most `max_workers` page images are held at once, whatever the length.

        Duplicates of a page are known after the survey, take no slot, and get
        the source page's reading once all OCR has finished.

        `on_page_done(done, total)` is called after each page is finished, with
        `done` rising by one per call (serialized, so it never goes back)."""
        result = Document(document_id=document_id, source_file=source)
        with self.extractor.open(source) as pdf:
            if len(pdf) == 0:
                raise ValueError("document has no pages")
            pages: list[Page | None] = [None] * len(pdf)
            total = len(pdf)
            done = 0
            done_lock = threading.Lock()

            def finish(index: int, page_result: Page, start: float) -> None:
                nonlocal done
                self._finish_page(pages, index, page_result, start, experiment, run_id, document_id)
                if on_page_done is not None:
                    with done_lock:
                        done += 1
                        on_page_done(done, total)

            # (index, page_result, context, start, quality_issues) per page to OCR.
            planned: list[tuple[int, Page, Context, float, list[str]]] = []
            first_page_with: dict[str, int] = {}
            reused: list[tuple[int, Page, int, float]] = []
            for index in range(len(pdf)):
                start = perf_counter()
                page_result = Page(
                    page_number=index + 1,
                    width=1,
                    height=1,
                    engine=engine.name if engine else "pymupdf",
                    model=engine.model if engine else "native",
                )
                try:
                    page = pdf[index]
                    page_result.width, page_result.height = page.rect.width, page.rect.height
                    page_result.dimension_unit = "pt"
                    page_result.rotation = page.rotation
                    evidence = self.classifier.classify(index + 1, *self.extractor.evidence(page))
                    page_result.evidence = evidence
                    page_result.input_type = evidence.input_type
                    # `requires_ocr_regions` (not `usable_text` alone) gates the native-only
                    # fast path: a MIXED page has usable text *and* a large image the text
                    # layer says nothing about, so it must not silently skip OCR (section 3).
                    if evidence.usable_text and not evidence.requires_ocr_regions:
                        page_result = self.extractor.extract(page, document_id)
                        page_result.evidence, page_result.input_type = evidence, evidence.input_type
                        finish(index, page_result, start)
                        continue
                    # Every other page is rendered: OCR needs the image, and a look at
                    # it first can make the OCR call unnecessary.
                    original = self.renderer.render(page, dpi)
                    if evidence.native_text_length == 0 and is_blank(original):
                        # Handoff §5: a blank page is SUCCESS + "blank_page". Decided
                        # here, before a paid OCR call comes back empty and reads as
                        # an extraction failure.
                        page_result.engine, page_result.model = "pymupdf", "native"
                        page_result.warnings = ["blank_page"]
                        page_result.evidence = evidence.model_copy(
                            update={"reason_codes": [*evidence.reason_codes, "BLANK_PAGE"]}
                        )
                        finish(index, page_result, start)
                        continue
                    if "SHORT_NATIVE_TEXT" in evidence.reason_codes:
                        native = self.extractor.extract(page, document_id)
                        covered = [line.bbox for line in native.lines if line.bbox is not None]
                        if covered and not unexplained_lines(original, covered):
                            evidence = evidence.model_copy(
                                update={
                                    "input_type": InputType.TEXT_LAYER,
                                    "usable_text": True,
                                    "requires_ocr_regions": False,
                                    "reason_codes": [
                                        *evidence.reason_codes,
                                        "SHORT_TEXT_COVERS_ALL_INK",
                                    ],
                                }
                            )
                            native.evidence, native.input_type = evidence, evidence.input_type
                            finish(index, native, start)
                            continue
                    if engine is None:
                        reason = (
                            "No usable native text layer"
                            if not evidence.usable_text
                            else "MIXED page (native text plus heavy image overlay) requires "
                            "an OCR engine to read the image-covered regions; none provided"
                        )
                        page_result.status, page_result.error = Status.SKIPPED, reason
                        page_result.evidence, page_result.input_type = evidence, evidence.input_type
                        finish(index, page_result, start)
                    else:
                        # Covers both SCANNED and MIXED pages. Known limitation for MIXED:
                        # this re-OCRs the *whole* page rather than compositing the already-
                        # good native text with OCR of just the image-covered regions (the
                        # "region routing" cell of the target pipeline). Re-reading the full
                        # page is strictly safer than the previous behaviour (silently
                        # keeping native-only text and dropping the image), but it is not yet
                        # the sub-page compositing the target architecture describes.
                        image, transform = self.preprocessor.apply(
                            original, experiment.preprocessing
                        )
                        # The same sheet embedded twice renders to identical pixels, and
                        # identical pixels get the same reading: pay for it once.
                        digest = hashlib.sha256(
                            f"{image.shape}".encode() + np.ascontiguousarray(image).tobytes()
                        ).hexdigest()
                        if digest in first_page_with:
                            reused.append((index, page_result, first_page_with[digest], start))
                            continue
                        first_page_with[digest] = index
                        # Judged on the scan as it came, before preprocessing.
                        quality_issues = self.quality.assess(original, dpi) if self.quality else []
                        if quality_issues:
                            page_result.evidence = evidence.model_copy(
                                update={
                                    "reason_codes": [*evidence.reason_codes, "LOW_QUALITY_SCAN"]
                                }
                            )
                        context = Context(
                            document_id=document_id,
                            page=index + 1,
                            output_dir=str(output / f"p{index + 1:03d}"),
                            low_quality=bool(quality_issues),
                        )
                        planned.append((index, page_result, context, start, quality_issues))
                        # Only the verdicts are kept: the image is rendered again for OCR.
                        del original, image
                except Exception as exc:
                    page_result.status, page_result.error = (
                        Status.FAILED,
                        f"{type(exc).__name__}: {exc}",
                    )
                    finish(index, page_result, start)

            def run_ocr_job(job: tuple) -> None:
                (
                    index,
                    page_result,
                    image,
                    transform,
                    original_shape,
                    context,
                    start,
                    quality_issues,
                ) = job
                with observation(
                    "process-page",
                    input={
                        "document_id": document_id,
                        "page_number": index + 1,
                        "engine": engine.name,
                    },
                    metadata={"feature": "document-ocr", "experiment": experiment.id},
                ) as page_span:
                    try:
                        recognized = engine.recognize_page(image, context)
                        self.preprocessor.restore(
                            recognized.lines, transform, image.shape, original_shape
                        )
                        page_result.lines = recognized.lines
                        if recognized.tables:
                            # The engine's own response already segments tables from prose
                            # (currently only Mistral OCR -- see infrastructure/ocr/
                            # markdown_tables.py) -- its tables are the real, parsed
                            # content, so the pixel-based bordered-grid detector below
                            # would only ever add noise (it cannot see markdown at all)
                            # and never runs for this page.
                            page_result.tables = recognized.tables
                        else:
                            # A detection failure must not fail an otherwise-successful page.
                            try:
                                page_result.tables = build_scanned_tables(
                                    image,
                                    page_result.lines,
                                    document_id=document_id,
                                    page_number=index + 1,
                                    inverse_transform=np.linalg.inv(transform),
                                    original_shape=original_shape,
                                )
                            except Exception:
                                page_result.tables = []
                        page_result.raw_markdown = recognized.raw_markdown
                        page_result.raw_output_path = recognized.raw_output_path
                        page_result.warnings = list(recognized.warnings)
                        page_result.width, page_result.height = original_shape[1], original_shape[0]
                        page_result.dimension_unit = "px"
                        page_result.preprocessing = experiment.preprocessing
                        page_result.transform = transform.tolist()
                        page_result.geometry_available = any(
                            line.bbox is not None for line in recognized.lines
                        )
                        if not any(line.text.strip() for line in page_result.lines):
                            # Blank sheets never reach the engine, so there is ink here
                            # that no reader turned into text: a signature- or stamp-only
                            # page, a photo -- or a misread. Neither blank nor a failed
                            # page: kept, and flagged for a person to look at.
                            page_result.warnings.append("no_text_found")
                    except EngineUnavailable as exc:
                        page_result.status, page_result.error = Status.SKIPPED, str(exc)
                    except Exception as exc:
                        page_result.status, page_result.error = (
                            Status.FAILED,
                            f"{type(exc).__name__}: {exc}",
                        )
                    if quality_issues:
                        page_result.warnings.append(f"low_quality_scan:{'+'.join(quality_issues)}")
                    if page_span is not None:
                        page_span.update(
                            output={
                                "status": str(page_result.status),
                                "line_count": len(page_result.lines),
                                "table_count": len(page_result.tables),
                                "geometry_available": page_result.geometry_available,
                                "low_quality_scan": quality_issues,
                            },
                            level="ERROR" if page_result.status == Status.FAILED else "DEFAULT",
                            status_message=(
                                "OCR page failed; inspect application logs"
                                if page_result.status == Status.FAILED
                                else None
                            ),
                        )
                finish(index, page_result, start)

            poor = {plan[0] + 1: plan[4] for plan in planned if plan[4]}
            if (
                poor
                and len(poor) >= self.min_low_quality_pages
                and len(poor) >= self.max_low_quality_share * len(planned)
            ):
                raise LowQualityDocument(poor, len(planned))

            def render_job(plan: tuple[int, Page, Context, float, list[str]]) -> tuple | None:
                """Render one planned page for OCR; a page that fails to render is finished."""
                index, page_result, context, start, quality_issues = plan
                try:
                    original = self.renderer.render(pdf[index], dpi)
                    image, transform = self.preprocessor.apply(original, experiment.preprocessing)
                except Exception as exc:
                    page_result.status, page_result.error = (
                        Status.FAILED,
                        f"{type(exc).__name__}: {exc}",
                    )
                    finish(index, page_result, start)
                    return None
                return (
                    index,
                    page_result,
                    image,
                    transform,
                    original.shape,
                    context,
                    start,
                    quality_issues,
                )

            if planned and max_workers > 1 and len(planned) > 1:
                # Rendering stays on this thread (the PDF page object is not
                # thread-safe). A slot is taken before a page is rendered and given
                # back when its OCR ends, so at most `max_workers` images exist.
                slots = threading.BoundedSemaphore(max_workers)

                def ocr_then_free_slot(job: tuple) -> None:
                    try:
                        run_ocr_job(job)
                    finally:
                        slots.release()

                with ThreadPoolExecutor(max_workers=max_workers) as pool:
                    futures = []
                    for plan in planned:
                        slots.acquire()
                        job = render_job(plan)
                        if job is None:
                            slots.release()
                            continue
                        # OpenTelemetry context is not copied into worker threads by
                        # ThreadPoolExecutor. Give every page its own context copy so
                        # page/model observations stay under the document OCR trace.
                        futures.append(pool.submit(copy_context().run, ocr_then_free_slot, job))
                        del job
                    for future in futures:
                        future.result()
            else:
                for plan in planned:
                    job = render_job(plan)
                    if job is not None:
                        run_ocr_job(job)
                    del job

            for index, page_result, source_index, start in reused:
                self._reuse_reading(pages[source_index], page_result, document_id)
                finish(index, page_result, start)

        result.pages = pages
        mark_duplicate_pages(result)
        return result

    @staticmethod
    def _reuse_reading(source: Page, target: Page, document_id: str) -> None:
        """Give `target` the OCR reading of the pixel-identical `source` page.
        Line, word and table ids are re-issued under the target's page number: an
        id must resolve to exactly one page downstream."""
        prefix = f"{document_id}-p{target.page_number:03d}"
        renamed: dict[str, str] = {}
        lines = []
        word_seq = 0
        for line_seq, line in enumerate(source.lines, 1):
            line_id = f"{prefix}-l{line_seq:04d}"
            renamed.setdefault(line.line_id, line_id)
            words = []
            for word in line.words:
                word_seq += 1
                words.append(word.model_copy(update={"word_id": f"{prefix}-w{word_seq:04d}"}))
            lines.append(line.model_copy(update={"line_id": line_id, "words": words}))
        warnings = []
        for code in source.warnings:
            if code.startswith("needs_review:"):
                _, reason, line_id = code.split(":", 2)
                code = f"needs_review:{reason}:{renamed.get(line_id, line_id)}"
            warnings.append(code)
        target.lines = lines
        target.tables = [
            table.model_copy(update={"table_id": f"{prefix}-t{seq:03d}"})
            for seq, table in enumerate(source.tables, 1)
        ]
        target.warnings = [*warnings, f"ocr:reused_reading_of_p{source.page_number}"]
        target.status, target.error = source.status, source.error
        for name in (
            "width",
            "height",
            "dimension_unit",
            "raw_markdown",
            "raw_output_path",
            "geometry_available",
            "preprocessing",
            "transform",
        ):
            setattr(target, name, getattr(source, name))

    def _finish_page(
        self,
        pages: list[Page | None],
        index: int,
        page_result: Page,
        start: float,
        experiment: Experiment,
        run_id: str,
        document_id: str,
    ) -> None:
        page_result.processing_ms = (perf_counter() - start) * 1000
        pages[index] = page_result
        logger.info(
            json.dumps(
                {
                    "run_id": run_id,
                    "sample_id": document_id,
                    "document_id": document_id,
                    "page": index + 1,
                    "engine": page_result.engine,
                    "experiment": experiment.id,
                    "elapsed_ms": round(page_result.processing_ms, 3),
                    "status": page_result.status,
                }
            )
        )
