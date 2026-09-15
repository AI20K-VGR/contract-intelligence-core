from collections import defaultdict

import pymupdf

from contract_ocr.domain.bbox import BBox
from contract_ocr.domain.entities import Line, Page, Word


class PyMuPDFExtractor:
    def open(self, path: str) -> pymupdf.Document:
        return pymupdf.open(path)

    def evidence(self, page: pymupdf.Page) -> tuple[int, int, int, float]:
        words = page.get_text("words")
        spans = sum(
            len(line["spans"])
            for block in page.get_text("dict")["blocks"]
            if block["type"] == 0
            for line in block["lines"]
        )
        # Exact rectangle union via vertical slabs; repeated/overlapping images count once.
        rects = [
            pymupdf.Rect(info["bbox"]) * page.rotation_matrix & page.rect
            for info in page.get_image_info()
        ]
        xs = sorted({x for r in rects for x in (r.x0, r.x1)})
        area = 0.0
        for left, right in zip(xs, xs[1:]):
            intervals = sorted(
                (r.y0, r.y1) for r in rects if r.x0 < right and r.x1 > left and not r.is_empty
            )
            end, height = -float("inf"), 0.0
            for low, high in intervals:
                height += max(0.0, high - max(low, end))
                end = max(end, high)
            area += (right - left) * height
        text = page.get_text()
        return len(text.strip()), len(words), spans, min(1.0, area / page.rect.get_area())

    def extract(self, page: pymupdf.Page, document_id: str) -> Page:
        width, height = page.rect.width, page.rect.height
        groups = defaultdict(list)
        for index, word in enumerate(page.get_text("words", sort=True), 1):
            rect = pymupdf.Rect(word[:4]) * page.rotation_matrix
            box = BBox.normalize(list(rect), width, height)
            groups[(word[5], word[6])].append(
                Word(
                    word_id=f"{document_id}-p{page.number + 1:03d}-w{index:04d}",
                    text=word[4],
                    bbox=box,
                )
            )
        lines = []
        for index, words in enumerate(groups.values(), 1):
            boxes = [w.bbox for w in words]
            box = BBox(
                x1=min(b.x1 for b in boxes),
                y1=min(b.y1 for b in boxes),
                x2=max(b.x2 for b in boxes),
                y2=max(b.y2 for b in boxes),
            )
            lines.append(
                Line(
                    line_id=f"{document_id}-p{page.number + 1:03d}-l{index:04d}",
                    text=" ".join(w.text for w in words),
                    words=words,
                    bbox=box,
                )
            )
        return Page(
            page_number=page.number + 1,
            width=width,
            height=height,
            dimension_unit="pt",
            rotation=page.rotation,
            engine="pymupdf",
            model=pymupdf.VersionBind,
            lines=lines,
            geometry_available=bool(lines),
        )
