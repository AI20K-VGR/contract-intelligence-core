from pathlib import Path

import pymupdf

from benchmark.pipeline import prepare_dataset


def test_prepare_always_renders_pdf_pages_to_images(tmp_path: Path) -> None:
    scans = tmp_path / "scans"
    scans.mkdir()
    pdf_path = scans / "scan.pdf"
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=100, height=100)
        page.insert_text((10, 20), "Selectable text must still be rendered")
        pdf.save(pdf_path)

    documents = prepare_dataset(scans, tmp_path / "data", {"render": {"dpi": 72}})

    assert len(documents) == 1
    assert documents[0].page_count == 1
    image = Path(documents[0].pages[0].image_path)
    assert image.suffix == ".png"
    assert image.exists()
