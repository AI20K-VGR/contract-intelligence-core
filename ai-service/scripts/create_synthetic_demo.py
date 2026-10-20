"""Create clearly labeled synthetic smoke data, never real benchmark evidence."""

from pathlib import Path

import pymupdf

from contract_ocr.infrastructure.reporting import write_csv


def main() -> None:
    directory = Path("data/generated/synthetic_demo").resolve()
    directory.mkdir(parents=True, exist_ok=False)
    text = "SYNTHETIC OCR smoke test only.\nAmount 100000000. Date 15/09/2026."
    reference = directory / "reference.txt"
    reference.write_text(text, encoding="utf-8")
    native = directory / "native.pdf"
    scan = directory / "scan.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=200)
        page.insert_text((30, 50), text)
        pdf.save(native)
        pixmap = page.get_pixmap(dpi=150)
        with pymupdf.open() as scanned:
            target = scanned.new_page(width=400, height=200)
            target.insert_image(target.rect, stream=pixmap.tobytes("png"))
            scanned.save(scan)
    write_csv(
        directory / "manifest.csv",
        [
            {
                "sample_id": sample_id,
                "file_path": str(path),
                "source": "SYNTHETIC - software smoke test only",
                "language": "en",
                "input_type": kind,
                "quality": "synthetic",
                "ground_truth_text": str(reference),
            }
            for sample_id, path, kind in (
                ("SYNTHETIC_NATIVE", native, "text_layer"),
                ("SYNTHETIC_SCAN", scan, "scanned"),
            )
        ],
        ["sample_id", "file_path"],
    )
    print(f"Synthetic demo manifest: {directory / 'manifest.csv'}")


if __name__ == "__main__":
    main()
