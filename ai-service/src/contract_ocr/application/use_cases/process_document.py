import json
import logging
from concurrent.futures import ThreadPoolExecutor
from contextvars import copy_context
from pathlib import Path
from time import perf_counter

import numpy as np

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.application.ports.pdf_extractor import PdfExtractor, Preprocessor, Renderer
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.extract_scanned_tables import build_scanned_tables
from contract_ocr.domain.entities import Context, Document, Experiment, Page
from contract_ocr.domain.enums import Status
from contract_ocr.infrastructure.observability import observation

logger = logging.getLogger("contract_ocr.pages")


class ProcessDocument:
    def __init__(
        self,
        extractor: PdfExtractor,
        renderer: Renderer,
        preprocessor: Preprocessor,
        classifier: PdfPageClassifier,
    ) -> None:
        self.extractor, self.renderer, self.preprocessor, self.classifier = (
            extractor,
            renderer,
            preprocessor,
            classifier,
        )

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
    ) -> Document:
        """max_workers only parallelizes the OCR engine call itself (network-bound API
        engines): PDF reading/classification/rendering always stays sequential because
        the underlying PDF SDK page object is not safe for concurrent access, and a
        single loaded local model is not safe (or faster) for concurrent inference
        either. Callers must only raise max_workers for stateless remote engines."""
        result = Document(document_id=document_id, source_file=source)
        with self.extractor.open(source) as pdf:
            if len(pdf) == 0:
                raise ValueError("document has no pages")
            pages: list[Page | None] = [None] * len(pdf)
            ocr_jobs = []
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
                        self._finish_page(
                            pages, index, page_result, start, experiment, run_id, document_id
                        )
                    elif engine is None:
                        reason = (
                            "No usable native text layer"
                            if not evidence.usable_text
                            else "MIXED page (native text plus heavy image overlay) requires "
                            "an OCR engine to read the image-covered regions; none provided"
                        )
                        page_result.status, page_result.error = Status.SKIPPED, reason
                        page_result.evidence, page_result.input_type = evidence, evidence.input_type
                        self._finish_page(
                            pages, index, page_result, start, experiment, run_id, document_id
                        )
                    else:
                        # Covers both SCANNED and MIXED pages. Known limitation for MIXED:
                        # this re-OCRs the *whole* page rather than compositing the already-
                        # good native text with OCR of just the image-covered regions (the
                        # "region routing" cell of the target pipeline). Re-reading the full
                        # page is strictly safer than the previous behaviour (silently
                        # keeping native-only text and dropping the image), but it is not yet
                        # the sub-page compositing the target architecture describes.
                        original = self.renderer.render(page, dpi)
                        image, transform = self.preprocessor.apply(
                            original, experiment.preprocessing
                        )
                        context = Context(
                            document_id=document_id,
                            page=index + 1,
                            output_dir=str(output / f"p{index + 1:03d}"),
                        )
                        ocr_jobs.append(
                            (index, page_result, image, transform, original.shape, context, start)
                        )
                except Exception as exc:
                    page_result.status, page_result.error = (
                        Status.FAILED,
                        f"{type(exc).__name__}: {exc}",
                    )
                    self._finish_page(
                        pages, index, page_result, start, experiment, run_id, document_id
                    )

            def run_ocr_job(job: tuple) -> None:
                index, page_result, image, transform, original_shape, context, start = job
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
                            page_result.status, page_result.error = (
                                Status.FAILED,
                                "Empty extraction result",
                            )
                    except EngineUnavailable as exc:
                        page_result.status, page_result.error = Status.SKIPPED, str(exc)
                    except Exception as exc:
                        page_result.status, page_result.error = (
                            Status.FAILED,
                            f"{type(exc).__name__}: {exc}",
                        )
                    if page_span is not None:
                        page_span.update(
                            output={
                                "status": str(page_result.status),
                                "line_count": len(page_result.lines),
                                "table_count": len(page_result.tables),
                                "geometry_available": page_result.geometry_available,
                            },
                            level="ERROR" if page_result.status == Status.FAILED else "DEFAULT",
                            status_message=(
                                "OCR page failed; inspect application logs"
                                if page_result.status == Status.FAILED
                                else None
                            ),
                        )
                self._finish_page(pages, index, page_result, start, experiment, run_id, document_id)

            if ocr_jobs:
                if max_workers > 1 and len(ocr_jobs) > 1:
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        # OpenTelemetry context is not copied into worker threads by
                        # ThreadPoolExecutor. Give every page its own context copy so
                        # page/model observations stay under the document OCR trace.
                        futures = [
                            pool.submit(copy_context().run, run_ocr_job, job) for job in ocr_jobs
                        ]
                        for future in futures:
                            future.result()
                else:
                    for job in ocr_jobs:
                        run_ocr_job(job)

        result.pages = pages
        return result

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
