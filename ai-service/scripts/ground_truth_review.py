"""Convert ground-truth text files to/from a readable Markdown review file.

The benchmark reads `data/ground_truth/text/<id>.txt`, pages separated by a form
feed (\\f). That is hard to edit by eye, so `export` writes
`data/ground_truth/review/<id>.md`: one "## Trang N" section per page, the page
image beside it, and the page text in a fenced block that keeps every line as-is.
Edit the Markdown, then `import` it back into the .txt the benchmark uses.

    uv run python scripts/ground_truth_review.py export [--pdf-dir data/raw/hard_cases]
    uv run python scripts/ground_truth_review.py import
"""

from __future__ import annotations

import argparse
import csv
import re
from pathlib import Path

import pymupdf

ROOT = Path(__file__).resolve().parents[1]
TEXT_DIR = ROOT / "data" / "ground_truth" / "text"
REVIEW_DIR = ROOT / "data" / "ground_truth" / "review"
MANIFEST = ROOT / "data" / "manifest.csv"
FENCE = "````text"  # four backticks: page text may itself contain ``` runs
_SECTION = re.compile(r"^## Trang (\d+)\s*$", re.M)
_BLOCK = re.compile(r"^````text\n(.*?)^````\s*$", re.M | re.S)


def _pdf_paths() -> dict[str, Path]:
    if not MANIFEST.exists():
        return {}
    with MANIFEST.open(encoding="utf-8") as stream:
        return {row["sample_id"]: ROOT / row["file_path"] for row in csv.DictReader(stream)}


def export(dpi: int) -> None:
    pdfs = _pdf_paths()
    REVIEW_DIR.mkdir(parents=True, exist_ok=True)
    for text_file in sorted(TEXT_DIR.glob("*.txt")):
        sample_id = text_file.stem
        pages = text_file.read_text(encoding="utf-8").split("\f")
        images: list[str | None] = [None] * len(pages)
        pdf_path = pdfs.get(sample_id)
        if pdf_path and pdf_path.exists():
            image_dir = REVIEW_DIR / sample_id
            image_dir.mkdir(exist_ok=True)
            with pymupdf.open(pdf_path) as pdf:
                for index in range(min(len(pdf), len(pages))):
                    name = f"page_{index + 1:03d}.png"
                    pdf[index].get_pixmap(dpi=dpi).save(image_dir / name)
                    images[index] = f"{sample_id}/{name}"
        parts = [
            f"# {sample_id}",
            "",
            f"Nguồn: `{pdf_path.relative_to(ROOT).as_posix() if pdf_path else 'không rõ'}` · "
            f"{len(pages)} trang",
            "",
            "Sửa chữ **bên trong** khối ```` của từng trang cho đúng với ảnh. Không xoá dòng "
            "`## Trang N` hay dấu ````. Sửa xong chạy "
            "`uv run python scripts/ground_truth_review.py import`.",
        ]
        for number, (text, image) in enumerate(zip(pages, images, strict=True), 1):
            parts += ["", "---", "", f"## Trang {number}", ""]
            if image:
                parts += [f"<img src=\"{image}\" width=\"600\">", ""]
            parts += [FENCE, text, "````"]
        (REVIEW_DIR / f"{sample_id}.md").write_text(
            "\n".join(parts) + "\n", encoding="utf-8", newline=""
        )
        print(f"exported {sample_id}.md ({len(pages)} trang)")


def import_() -> None:
    for review in sorted(REVIEW_DIR.glob("*.md")):
        content = review.read_text(encoding="utf-8")
        sections = list(_SECTION.finditer(content))
        pages = []
        for i, section in enumerate(sections):
            end = sections[i + 1].start() if i + 1 < len(sections) else len(content)
            block = _BLOCK.search(content, section.end(), end)
            if block is None:
                raise SystemExit(f"{review.name}: Trang {section.group(1)} thiếu khối {FENCE}")
            pages.append(block.group(1).rstrip("\n"))
        (TEXT_DIR / f"{review.stem}.txt").write_text(
            "\f".join(pages), encoding="utf-8", newline=""
        )
        print(f"imported {review.stem}.txt ({len(pages)} trang)")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="command", required=True)
    exporter = sub.add_parser("export")
    exporter.add_argument("--dpi", type=int, default=100)
    sub.add_parser("import")
    args = parser.parse_args()
    export(args.dpi) if args.command == "export" else import_()


if __name__ == "__main__":
    main()
