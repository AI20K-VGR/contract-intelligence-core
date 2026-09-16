import json
import logging
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from time import perf_counter

from contract_ocr.application.ports.ocr_engine import EngineUnavailable, OCREngine
from contract_ocr.application.ports.pdf_extractor import PdfExtractor, Preprocessor, Renderer
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.domain.entities import Context, Document, Experiment, Page
from contract_ocr.domain.enums import Status

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
        single loaded local model (Paddle/DeepSeek) is not safe for concurrent inference
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
                    if evidence.usable_text:
                        page_result = self.extractor.extract(page, document_id)
                        page_result.evidence, page_result.input_type = evidence, evidence.input_type
                        self._finish_page(
                            pages, index, page_result, start, experiment, run_id, document_id
                        )
                    elif engine is None:
                        page_result.status, page_result.error = (
                            Status.SKIPPED,
                            "No usable native text layer",
                        )
                        self._finish_page(
                            pages, index, page_result, start, experiment, run_id, document_id
                        )
                    else:
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
                try:
                    recognized = engine.recognize_page(image, context)
                    self.preprocessor.restore(
                        recognized.lines, transform, image.shape, original_shape
                    )
                    page_result.lines = recognized.lines
                    page_result.raw_markdown = recognized.raw_markdown
                    page_result.raw_output_path = recognized.raw_output_path
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
                self._finish_page(pages, index, page_result, start, experiment, run_id, document_id)

            if ocr_jobs:
                if max_workers > 1 and len(ocr_jobs) > 1:
                    with ThreadPoolExecutor(max_workers=max_workers) as pool:
                        list(pool.map(run_ocr_job, ocr_jobs))
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
