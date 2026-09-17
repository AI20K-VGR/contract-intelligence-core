import json
import os
import subprocess
import sys

import pymupdf
import pytest

from app.document_processing import process_page
from app.evidence import citation, validate_result
from app.storage import ArtifactStore, digest


@pytest.mark.parametrize("rotation", [0, 90, 180, 270])
def test_rotated_cropped_native_geometry(tmp_path, rotation):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=600, height=800)
        page.insert_text((100, 150), "100.000.000 VND")
        page.set_cropbox(pymupdf.Rect(40, 50, 550, 750))
        page.set_rotation(rotation)
        source = pdf.tobytes()
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }
    page = process_page(payload, {"dpi": 100, "max_pixels": 2_000_000}, store)
    assert page["engine"] == "pymupdf"
    cit = citation(page, page["lines"][0], "run")
    assert 0 <= cit["bbox"][0] < cit["bbox"][2] <= 1
    assert 0 <= cit["bbox"][1] < cit["bbox"][3] <= 1
    validate_result({"citations": [cit], "pages": [page], "facts": [], "findings": []})


def test_scan_routes_to_local_ocr_and_empty_is_not_blank(tmp_path, monkeypatch):
    import io

    from PIL import Image

    import app.document_processing as processing

    image = Image.new("RGB", (200, 100), "white")
    png = io.BytesIO()
    image.save(png, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=200, height=100)
        page.insert_image(page.rect, stream=png.getvalue())
        source = pdf.tobytes()
    called = []

    def mock_ocr(*args, **kwargs):
        called.append(kwargs)
        return {"text": []}

    monkeypatch.setattr(processing.pytesseract, "image_to_data", mock_ocr)
    store = ArtifactStore(tmp_path)
    payload = {
        "document_id": "doc",
        "role": "contract",
        "sha256": digest(source),
        "storage_key": store.put(source, "pdf"),
        "page_number": 1,
    }
    result = process_page(
        payload,
        {"dpi": 100, "max_pixels": 2_000_000, "ocr_languages": "vie+eng", "ocr_timeout_seconds": 5},
        store,
    )
    assert called[0]["lang"] == "vie+eng"
    assert result["status"] == "needs_review"
    assert result["issue"] == "EMPTY_OCR_REQUIRES_REVIEW"


def test_migration_on_empty_database(tmp_path):
    from pathlib import Path

    from sqlalchemy import create_engine, inspect

    database_url = f"sqlite:///{tmp_path / 'migration.db'}"
    result = subprocess.run(
        [sys.executable, "-m", "alembic", "upgrade", "head"],
        env={**os.environ, "CI_DATABASE_URL": database_url},
        capture_output=True,
        text=True,
        timeout=30,
    )
    assert result.returncode == 0, result.stderr
    engine = create_engine(database_url)
    schema = json.loads(Path("migrations/versions/0001_schema.json").read_text())
    assert set(t["name"] for t in schema) <= set(inspect(engine).get_table_names())
    assert "analysis_revisions" in inspect(engine).get_table_names()
    engine.dispose()
