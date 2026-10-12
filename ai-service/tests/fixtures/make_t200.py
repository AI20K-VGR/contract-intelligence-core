"""Build a 200-page PDF whose every page is different.

Never build it by copying one page 200 times: ``ProcessDocument`` reads
pixel-identical pages once (SHA of the rendered pixels) and hands the other
199 the same reading, so a test on such a file would pass without rendering
or reading 199 of its pages.

Run ``python tests/fixtures/make_t200.py [out.pdf]`` (default ``t200.pdf``).
"""

from __future__ import annotations

import sys
from pathlib import Path

import pymupdf

PAGES = 200


def make_t200(path: str | Path, pages: int = PAGES) -> Path:
    path = Path(path)
    document = pymupdf.open()
    for i in range(pages):
        page = document.new_page()
        page.insert_text(
            (72, 100 + (i % 7) * 13),
            f"Trang {i + 1} - Điều {i % 20 + 1}",
            fontsize=11,
        )
    document.save(path)
    document.close()
    return path


if __name__ == "__main__":
    print(make_t200(sys.argv[1] if len(sys.argv) > 1 else "t200.pdf"))
