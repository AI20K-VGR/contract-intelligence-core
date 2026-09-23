"""Section 9: bordered-table grid detection must find real ruling lines in a
rendered page image, and must not report a table where there isn't one."""

from io import BytesIO

import pymupdf
from PIL import Image, ImageDraw

from contract_ocr.infrastructure.image.renderer import PdfRenderer
from contract_ocr.infrastructure.image.table_grid import detect_bordered_tables

ROWS_Y = [50, 80, 110, 140]
COLS_X = [40, 140, 240, 340]


def _bordered_table_image(dpi: int = 150):
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        shape = page.new_shape()
        for y in ROWS_Y:
            shape.draw_line((COLS_X[0], y), (COLS_X[-1], y))
        for x in COLS_X:
            shape.draw_line((x, ROWS_Y[0]), (x, ROWS_Y[-1]))
        shape.finish()
        shape.commit()
        data = [["STT", "Ten hang", "So luong"], ["1", "Hang A", "10"], ["2", "Hang B", "20"]]
        for r, row in enumerate(data):
            for c, val in enumerate(row):
                page.insert_text((COLS_X[c] + 5, ROWS_Y[r] + 20), val, fontsize=10)
        return PdfRenderer().render(page, dpi)


def test_detects_a_real_bordered_table_grid_at_the_right_pixel_positions():
    image = _bordered_table_image(dpi=150)
    grids = detect_bordered_tables(image)
    assert len(grids) == 1
    grid = grids[0]
    assert len(grid.row_boundaries) == len(ROWS_Y)
    assert len(grid.col_boundaries) == len(COLS_X)
    scale = 150 / 72
    for detected, expected in zip(grid.row_boundaries, ROWS_Y, strict=True):
        assert abs(detected - expected * scale) <= 3
    for detected, expected in zip(grid.col_boundaries, COLS_X, strict=True):
        assert abs(detected - expected * scale) <= 3

    cells = grid.cells()
    assert len(cells) == 3  # 3 row-bands (header + 2 data rows)
    assert len(cells[0]) == 3  # 3 column-bands


def test_cells_partition_the_grid_bbox_into_a_row_major_matrix():
    image = _bordered_table_image()
    grid = detect_bordered_tables(image)[0]
    cells = grid.cells()
    for r, row in enumerate(cells):
        for c, (x0, y0, x1, y1) in enumerate(row):
            assert x0 == grid.col_boundaries[c] and x1 == grid.col_boundaries[c + 1]
            assert y0 == grid.row_boundaries[r] and y1 == grid.row_boundaries[r + 1]


def test_plain_text_page_has_no_table_grid():
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        page.insert_text((30, 50), "Not a table, just a paragraph of text.")
        page.insert_text((30, 70), "Another ordinary line of body text here.")
        image = PdfRenderer().render(page, 150)
    assert detect_bordered_tables(image) == []


def test_a_single_ruled_line_is_not_a_table():
    # A horizontal divider (common under a heading/signature block) must not be
    # misreported as a 1-row, 1-column "table".
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        shape = page.new_shape()
        shape.draw_line((40, 100), (360, 100))
        shape.finish()
        shape.commit()
        image = PdfRenderer().render(page, 150)
    assert detect_bordered_tables(image) == []


def test_blank_page_has_no_table_grid():
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=400, height=300)
        image = PdfRenderer().render(page, 150)
    assert detect_bordered_tables(image) == []


def test_works_on_a_genuinely_scanned_style_raster_image_not_just_vector_pdf():
    # Detection must operate on pixels alone: build the table as a PNG raster
    # (PIL, no PDF vector drawing ops) and re-embed it as an image-only PDF page
    # -- the same shape a real photographed/scanned page would have.
    canvas = Image.new("RGB", (800, 600), "white")
    draw = ImageDraw.Draw(canvas)
    rows_y = [100, 200, 300, 400]
    cols_x = [80, 320, 560, 720]
    for y in rows_y:
        draw.line([(cols_x[0], y), (cols_x[-1], y)], fill="black", width=3)
    for x in cols_x:
        draw.line([(x, rows_y[0]), (x, rows_y[-1])], fill="black", width=3)
    buffer = BytesIO()
    canvas.save(buffer, format="PNG")
    with pymupdf.open() as pdf:
        page = pdf.new_page(width=canvas.width, height=canvas.height)
        page.insert_image(page.rect, stream=buffer.getvalue())
        image = PdfRenderer().render(page, 72)
    grids = detect_bordered_tables(image)
    assert len(grids) == 1
    assert len(grids[0].row_boundaries) == len(rows_y)
    assert len(grids[0].col_boundaries) == len(cols_x)
