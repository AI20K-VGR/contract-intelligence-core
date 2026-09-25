import argparse
import hashlib
import json
import logging
import sys
from datetime import UTC, datetime
from pathlib import Path

import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.application.use_cases.build_snapshot import BuildSnapshot
from contract_ocr.application.use_cases.classify_pdf import PdfPageClassifier
from contract_ocr.application.use_cases.process_document import ProcessDocument
from contract_ocr.application.use_cases.run_benchmark import RunBenchmark
from contract_ocr.domain.entities import Document, Experiment
from contract_ocr.infrastructure.config import load_settings, read_manifest
from contract_ocr.infrastructure.image.degradation import VARIANTS, degrade
from contract_ocr.infrastructure.image.preprocessing import ImagePreprocessor
from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.metrics.evaluation import SampleEvaluator
from contract_ocr.infrastructure.ocr.mistral_ocr import MistralOCREngine
from contract_ocr.infrastructure.pdf.pymupdf_extractor import PyMuPDFExtractor
from contract_ocr.infrastructure.reporting import FileReporter, write_csv, write_json

PROJECT_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_CONFIG = PROJECT_ROOT / "configs" / "default.yaml"


def benchmark(args: argparse.Namespace) -> None:
    settings = load_settings(args.config)
    requested = set(args.engines.split(","))
    if requested - {"pymupdf"}:
        raise ValueError("engines must be pymupdf")
    selected = set(args.experiments.split(",")) if args.experiments else None
    settings.experiments = [
        e
        for e in settings.experiments
        if e.engine in requested and (selected is None or e.id in selected)
    ]
    if not settings.experiments or (selected and selected != {e.id for e in settings.experiments}):
        raise ValueError("no experiments selected or unknown/incompatible experiment IDs")
    engines = {}
    processor = ProcessDocument(
        PyMuPDFExtractor(),
        PdfRenderer(),
        ImagePreprocessor(),
        PdfPageClassifier(**settings.classifier),
    )
    runner = RunBenchmark(
        processor,
        SampleEvaluator(settings.evaluation.get("bbox_iou_threshold", 0.5)),
        FileReporter(),
    )
    samples = read_manifest(args.manifest, args.root)
    rows = runner.execute(samples, settings, engines, args.output.resolve())
    print(
        json.dumps(
            {
                "report": str(args.output.resolve()),
                "n": len(rows),
                "success": sum(r["status"] == "SUCCESS" for r in rows),
                "failed": sum(r["status"] == "FAILED" for r in rows),
                "skipped": sum(r["status"] == "SKIPPED" for r in rows),
            }
        )
    )


def inspect(args: argparse.Namespace) -> None:
    extractor = PyMuPDFExtractor()
    classifier = PdfPageClassifier(**load_settings(args.config).classifier)
    with extractor.open(str(args.file)) as pdf:
        results = [
            classifier.classify(i + 1, *extractor.evidence(page)).model_dump(mode="json")
            for i, page in enumerate(pdf)
        ]
    print(json.dumps(results, ensure_ascii=False, indent=2))


def snapshot(args: argparse.Namespace) -> None:
    """Produce one ai1.snapshot.v1 document handoff file for AI2 (see
    docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md and docs/ai1.snapshot.v1.schema.json)."""
    settings = load_settings(args.config)
    engine = None
    if args.engine == "mistral":
        engine = MistralOCREngine()
    processor = ProcessDocument(
        PyMuPDFExtractor(),
        PdfRenderer(),
        ImagePreprocessor(),
        PdfPageClassifier(**settings.classifier),
    )
    experiment = Experiment(id="snapshot", engine=args.engine if engine else "pymupdf")
    document = processor.execute(
        str(args.file),
        args.document_id,
        experiment,
        engine,
        args.output / "_raw",
        "snapshot-cli",
        args.dpi,
    )
    snapshot_id = args.snapshot_id or (
        f"ocr-run-{datetime.now(UTC).strftime('%Y%m%d-%H%M%S')}-{args.document_id}"
    )
    doc_dir = args.output / args.dossier_id / args.document_id
    result = BuildSnapshot(PdfRenderer(), image_dpi=args.image_dpi).execute(
        document,
        snapshot_id=snapshot_id,
        dossier_id=args.dossier_id,
        document_role=args.role,
        filename=args.filename or args.file.name,
        engine_name=engine.name if engine else "pymupdf",
        engine_version=str(engine.model) if engine else pymupdf.VersionBind,
        image_output_dir=doc_dir / snapshot_id,
        image_uri_prefix=f"storage://ocr/{snapshot_id}",
    )
    out_path = doc_dir / f"{snapshot_id}.json"
    write_json(out_path, result.model_dump(mode="json"))
    print(
        json.dumps(
            {
                "snapshot_id": snapshot_id,
                "path": str(out_path.resolve()),
                "page_count": result.page_count,
                "input_type": result.input_type,
            }
        )
    )


def visualize(args: argparse.Namespace) -> None:
    document = Document.model_validate_json(args.prediction.read_text(encoding="utf-8"))
    page = next((p for p in document.pages if p.page_number == args.page), None)
    if page is None:
        raise ValueError("page not present in prediction")
    with PyMuPDFExtractor().open(document.source_file) as pdf:
        image = Image.fromarray(PdfRenderer().render(pdf[args.page - 1], args.dpi))
    draw = ImageDraw.Draw(image)
    count = 0
    for line in page.lines:
        for item, color in [(line, "red"), *((word, "blue") for word in line.words)]:
            if item.bbox:
                b = item.bbox
                draw.rectangle(
                    [
                        b.x1 * image.width,
                        b.y1 * image.height,
                        b.x2 * image.width,
                        b.y2 * image.height,
                    ],
                    outline=color,
                    width=2,
                )
                count += 1
    args.output.parent.mkdir(parents=True, exist_ok=True)
    image.save(args.output)
    print(f"Saved {args.output}; boxes={count} (red=line, blue=word)")


def generate(args: argparse.Namespace) -> None:
    if not args.file:
        raise ValueError("--file is required; original dataset files are never modified")
    output = args.output.resolve()
    allowed = (args.root / "data/generated").resolve()
    if not output.is_relative_to(allowed):
        raise ValueError("generated files must be under <root>/data/generated")
    variants = args.variants.split(",") if args.variants else VARIANTS
    if set(variants) - set(VARIANTS):
        raise ValueError("unknown degradation variant")
    digest = hashlib.sha256(args.file.read_bytes()).hexdigest()[:12]
    target = output / f"{digest}-seed{args.seed}"
    target.mkdir(parents=True, exist_ok=False)
    rows, records = [], []
    with PyMuPDFExtractor().open(str(args.file)) as pdf:
        for index, page in enumerate(pdf):
            image = PdfRenderer().render(page, 300)
            for variant in variants:
                sample_id = f"G{digest}_p{index + 1:03d}_{variant.replace('+', 'plus').replace('-', 'minus')}"
                variant_seed = int.from_bytes(
                    hashlib.sha256(f"{args.seed}:{index}:{variant}".encode()).digest()[:4], "big"
                )
                result, matrix = degrade(image, variant, variant_seed)
                path = target / f"{sample_id}.pdf"
                dpi = int(variant[3:]) if variant.startswith("dpi") else 300
                # Image-only PDFs enter the exact same benchmark path as real scans.
                from io import BytesIO

                import pymupdf

                buffer = BytesIO()
                Image.fromarray(result).save(buffer, format="PNG")
                with pymupdf.open() as generated:
                    new_page = generated.new_page(
                        width=result.shape[1] * 72 / dpi, height=result.shape[0] * 72 / dpi
                    )
                    new_page.insert_image(new_page.rect, stream=buffer.getvalue())
                    generated.save(path)
                rows.append(
                    {
                        "sample_id": sample_id,
                        "file_path": str(path),
                        "source": str(args.file.resolve()),
                        "language": args.language,
                        "input_type": "scanned",
                        "quality": "generated",
                        "degradation": variant,
                        "dpi": dpi,
                        "ground_truth_text": "",
                        "ground_truth_bbox": "",
                        "notes": f"source page {index + 1}; synthetic degradation, not synthetic ground truth",
                    }
                )
                records.append(
                    {
                        "sample_id": sample_id,
                        "source_page": index + 1,
                        "seed": variant_seed,
                        "variant": variant,
                        "source_shape": list(image.shape),
                        "output_shape": list(result.shape),
                        "transform": matrix.tolist(),
                    }
                )
    write_csv(target / "manifest.csv", rows, ["sample_id", "file_path"])
    write_json(
        target / "generation.json",
        {
            "source": str(args.file.resolve()),
            "source_sha256": hashlib.sha256(args.file.read_bytes()).hexdigest(),
            "seed": args.seed,
            "samples": records,
        },
    )
    print(f"Generated n={len(rows)} samples in {target}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Local contract OCR experiments")
    sub = parser.add_subparsers(dest="command", required=True)
    run = sub.add_parser("benchmark")
    run.add_argument("--manifest", type=Path, default=Path("data/manifest.csv"))
    run.add_argument("--root", type=Path, default=Path.cwd())
    run.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    run.add_argument("--engines", default="pymupdf")
    run.add_argument("--experiments", default="")
    run.add_argument("--output", type=Path, required=True)
    run.set_defaults(func=benchmark)
    check = sub.add_parser("inspect")
    check.add_argument("--file", type=Path, required=True)
    check.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    check.set_defaults(func=inspect)
    snap = sub.add_parser("snapshot")
    snap.add_argument("--file", type=Path, required=True)
    snap.add_argument("--document-id", required=True)
    snap.add_argument("--dossier-id", required=True)
    snap.add_argument("--role", choices=["contract", "annex"], required=True)
    snap.add_argument("--filename", default="")
    snap.add_argument("--config", type=Path, default=DEFAULT_CONFIG)
    snap.add_argument("--engine", default="none", choices=["none", "mistral"])
    snap.add_argument("--dpi", type=int, default=300)
    snap.add_argument("--image-dpi", type=int, default=150)
    snap.add_argument("--snapshot-id", default="")
    snap.add_argument("--output", type=Path, default=Path("data/generated/snapshots"))
    snap.set_defaults(func=snapshot)
    overlay = sub.add_parser("visualize")
    overlay.add_argument("--prediction", type=Path, required=True)
    overlay.add_argument("--page", type=int, default=1)
    overlay.add_argument("--dpi", type=int, default=150)
    overlay.add_argument("--output", type=Path, required=True)
    overlay.set_defaults(func=visualize)
    degradation = sub.add_parser("generate-degraded")
    degradation.add_argument("--file", type=Path)
    degradation.add_argument("--root", type=Path, default=Path.cwd())
    degradation.add_argument("--output", type=Path, default=Path("data/generated"))
    degradation.add_argument("--seed", type=int, default=42)
    degradation.add_argument("--language", default="vi")
    degradation.add_argument("--variants", default="")
    degradation.set_defaults(func=generate)
    args = parser.parse_args(argv)
    logging.basicConfig(level=logging.INFO, format="%(message)s")
    try:
        args.func(args)
    except (ValueError, OSError) as exc:
        print(f"Error: {exc}", file=sys.stderr)
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
