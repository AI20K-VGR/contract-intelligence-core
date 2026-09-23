import csv
from io import BytesIO
from pathlib import Path

import pymupdf
import pytest
from PIL import Image, ImageDraw


@pytest.fixture
def synthetic_pdf(tmp_path: Path) -> Path:
    path = tmp_path / "synthetic.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=300, height=400)
        page.insert_text((25, 50), "SYNTHETIC contract for OCR testing only.")
        page.insert_text((25, 75), "Amount 100000000. Date 15/09/2026.")
        page = pdf.new_page(width=300, height=400)
        image = Image.new("RGB", (300, 400), "white")
        ImageDraw.Draw(image).text((20, 30), "SYNTHETIC scanned page", fill="black")
        buffer = BytesIO()
        image.save(buffer, format="PNG")
        page.insert_image(page.rect, stream=buffer.getvalue())
        pdf.save(path)
    return path


@pytest.fixture
def manifest(tmp_path: Path, synthetic_pdf: Path) -> Path:
    path = tmp_path / "manifest.csv"
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.DictWriter(stream, fieldnames=["sample_id", "file_path", "language"])
        writer.writeheader()
        writer.writerow(
            {"sample_id": "SYNTHETIC", "file_path": str(synthetic_pdf), "language": "en"}
        )
    return path
