from contract_ocr.reconstruction.boundary_detector import detect_boundary
from contract_ocr.reconstruction.header_footer_detector import detect_header_footer

from .factories import make_block, make_page


def test_detect_boundary_excludes_headers_footers_and_page_numbers():
    pages = []
    for page_number in range(1, 6):
        blocks = [
            make_block(f"p{page_number}_hdr", "ABC CORPORATION", type="header", bbox=(100, 20, 900, 60)),
            make_block(
                f"p{page_number}_body1", f"Nội dung điều khoản trang {page_number} phần một.", bbox=(100, 300, 1000, 400)
            ),
            make_block(
                f"p{page_number}_body2", f"Nội dung điều khoản trang {page_number} phần hai.", bbox=(100, 420, 1000, 500)
            ),
            make_block(
                f"p{page_number}_pgnum", f"Page {page_number} of 5", type="page_number", bbox=(700, 2270, 900, 2310)
            ),
        ]
        pages.append(make_page("doc1", page_number, blocks))

    profile = detect_header_footer(pages)
    context = detect_boundary(pages[0], pages[1], profile)

    previous_ids = [b.block_id for b in context.previous_blocks]
    next_ids = [b.block_id for b in context.next_blocks]

    assert "p1_hdr" not in previous_ids
    assert "p1_pgnum" not in previous_ids
    assert "p2_hdr" not in next_ids
    assert previous_ids == ["p1_body1", "p1_body2"]
    assert next_ids == ["p2_body1", "p2_body2"]
    assert context.previous_page == 1
    assert context.next_page == 2
    assert context.document_id == "doc1"


def test_detect_boundary_limits_to_window_size():
    blocks_prev = [make_block(f"a{i}", f"Đoạn văn số {i}.", bbox=(100, 100 + i * 50, 1000, 140 + i * 50)) for i in range(6)]
    blocks_next = [make_block(f"b{i}", f"Đoạn văn tiếp theo số {i}.", bbox=(100, 100 + i * 50, 1000, 140 + i * 50)) for i in range(6)]
    previous_page = make_page("doc1", 1, blocks_prev)
    next_page = make_page("doc1", 2, blocks_next)

    profile = detect_header_footer([previous_page, next_page])
    context = detect_boundary(previous_page, next_page, profile, window=3)

    assert [b.block_id for b in context.previous_blocks] == ["a3", "a4", "a5"]
    assert [b.block_id for b in context.next_blocks] == ["b0", "b1", "b2"]


def test_detect_boundary_drops_empty_blocks():
    blocks_prev = [
        make_block("p1_a", "Nội dung có thật.", bbox=(100, 300, 1000, 350)),
        make_block("p1_empty", "   ", bbox=(100, 400, 1000, 420)),
    ]
    blocks_next = [
        make_block("p2_empty", "", bbox=(100, 100, 1000, 120)),
        make_block("p2_a", "Nội dung tiếp theo.", bbox=(100, 200, 1000, 250)),
    ]
    previous_page = make_page("doc1", 1, blocks_prev)
    next_page = make_page("doc1", 2, blocks_next)

    profile = detect_header_footer([previous_page, next_page])
    context = detect_boundary(previous_page, next_page, profile)

    assert [b.block_id for b in context.previous_blocks] == ["p1_a"]
    assert [b.block_id for b in context.next_blocks] == ["p2_a"]
