"""Print the page quality check for PDFs -- local only, no OCR call is made.

    uv run python scripts/check_page_quality.py data/raw/scanned_bad/*.pdf
    uv run python scripts/check_page_quality.py some.pdf --dpi 150

Pages with a usable text layer are skipped, as in the pipeline: only pages that
would be sent to OCR are checked. The last line says whether the document would
be refused (AI1_LOW_QUALITY_DOCUMENT) or OCR'd.
"""

import argparse
import glob
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "src"))

from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier  # noqa: E402
from contract_ocr.application.use_cases.process_document import MAX_LOW_QUALITY_SHARE  # noqa: E402
from contract_ocr.infrastructure.image.page_ink import is_blank  # noqa: E402
from contract_ocr.infrastructure.image.page_quality import (  # noqa: E402
    MAX_NOISE,
    MAX_SPECKLE_PER_MEGAPIXEL,
    MIN_CONTRAST,
    MIN_SHARPNESS,
    assess,
    measure,
)
from contract_ocr.infrastructure.image.renderer import PdfRenderer  # noqa: E402
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor  # noqa: E402


def check(path: str, dpi: int) -> None:
    extractor, renderer, classifier = PyMuPDFExtractor(), PdfRenderer(), PdfPageClassifier()
    print(f"\n{path}")
    print(f"{'page':>4}  {'sharp':>6}  {'contrast':>8}  {'noise':>5}  {'speckle':>7}  verdict")
    checked, poor = 0, []
    with extractor.open(path) as pdf:
        for index in range(len(pdf)):
            page = pdf[index]
            evidence = classifier.classify(index + 1, *extractor.evidence(page))
            if evidence.usable_text and not evidence.requires_ocr_regions:
                print(f"{index + 1:>4}  text layer, not OCR'd")
                continue
            image = renderer.render(page, dpi)
            if evidence.native_text_length == 0 and is_blank(image):
                print(f"{index + 1:>4}  blank, not OCR'd")
                continue
            checked += 1
            signals = measure(image, dpi)
            if signals is None:
                print(f"{index + 1:>4}  too little ink to judge -> OK")
                continue
            reasons = assess(image, dpi)
            if reasons:
                poor.append(index + 1)
            print(
                f"{index + 1:>4}  {signals['sharpness']:>6.3f}  {signals['contrast']:>8.1f}  "
                f"{signals['noise']:>5.2f}  {signals['speckle']:>7.1f}  "
                + ("POOR: " + "+".join(reasons) if reasons else "OK")
            )
    if not checked:
        print("no page would be OCR'd")
        return
    share = len(poor) / checked
    refused = poor and len(poor) >= MAX_LOW_QUALITY_SHARE * checked
    print(
        f"=> {len(poor)}/{checked} OCR pages poor ({share:.0%}): "
        + (
            "REFUSED, no OCR call (AI1_LOW_QUALITY_DOCUMENT)"
            if refused
            else "OCR'd; poor pages read once and flagged"
        )
    )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("pdfs", nargs="+")
    parser.add_argument("--dpi", type=int, default=150)
    args = parser.parse_args()
    print(
        f"thresholds: sharpness < {MIN_SHARPNESS}, contrast < {MIN_CONTRAST}, "
        f"noise > {MAX_NOISE}, speckle > {MAX_SPECKLE_PER_MEGAPIXEL}/MP; "
        f"refuse at >= {MAX_LOW_QUALITY_SHARE:.0%} poor pages"
    )
    for pattern in args.pdfs:
        for path in sorted(glob.glob(pattern)) or [pattern]:
            check(path, args.dpi)


if __name__ == "__main__":
    main()
