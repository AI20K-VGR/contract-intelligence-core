from contract_ocr.infrastructure.image.line_geometry import LineBox
from contract_ocr.infrastructure.ocr.text_geometry_alignment import align

# 10 px per character on a synthetic page; lines are 20 px tall, 30 px apart.
PX = 10


def _box(row: int, chars: int, *, x0: int = 100, gap_rows: int = 0) -> LineBox:
    y0 = 100 + (row + gap_rows) * 30
    return LineBox(x0, y0, x0 + chars * PX, y0 + 20)


def _text(chars: int) -> str:
    return ("x" * 9 + " ") * (chars // 10) + "x" * (chars % 10)


def test_paragraph_segments_take_their_wrapped_visual_lines():
    # heading (1 line), a paragraph wrapping over 3 lines, a 2-line paragraph
    texts = [_text(40), _text(80 + 80 + 30), _text(80 + 50)]
    boxes = [_box(0, 40), _box(1, 80), _box(2, 80), _box(3, 30), _box(4, 80), _box(5, 50)]
    result = align(texts, boxes)
    assert [s.box_indices for s in result.segments] == [[0], [1, 2, 3], [4, 5]]
    assert not result.unread_ink and not result.text_without_ink
    assert all(not s.poor for s in result.segments)


def test_ink_the_transcription_skipped_is_reported_not_absorbed():
    lengths = [45, 80, 62, 80, 38, 70, 80, 55]
    boxes = [_box(row, chars, gap_rows=row) for row, chars in enumerate(lengths)]
    skipped = 3
    texts = [_text(c) for idx, c in enumerate(lengths) if idx != skipped]
    result = align(texts, boxes)
    assert result.unread_ink == [skipped]
    assert [s.box_indices for s in result.segments] == [[b] for b in range(8) if b != skipped]


def test_text_with_no_ink_behind_it_is_reported():
    lengths = [45, 80, 62, 80, 38, 70]
    boxes = [_box(row, chars, gap_rows=row) for row, chars in enumerate(lengths)]
    texts = [_text(c) for c in lengths]
    texts.insert(2, _text(120))  # a line the transcriber invented
    result = align(texts, boxes)
    assert result.text_without_ink == [2]
    assert result.segments[2].poor
    assert [s.box_indices for i, s in enumerate(result.segments) if i != 2] == [[b] for b in range(6)]


def test_a_run_does_not_bridge_a_large_vertical_gap():
    # Two 1-line paragraphs of similar length separated by a big gap: the
    # first segment must not swallow both boxes even if lengths are fuzzy.
    texts = [_text(90), _text(50)]
    boxes = [_box(0, 60), _box(1, 40, gap_rows=4)]
    result = align(texts, boxes)
    assert result.segments[0].box_indices == [0]
    assert result.segments[1].box_indices == [1]


def test_content_anchors_resolve_runs_of_similar_length_lines():
    # Five list items of near-identical length plus one untranscribed line at
    # the top: by length alone every shift costs about the same.
    lengths = [30, 31, 30, 32, 31, 30]
    boxes = [_box(row, chars) for row, chars in enumerate(lengths)]
    texts = [_text(c) for c in lengths[1:]]
    anchors = [(0, boxes[row].y0, 2000, boxes[row].y1) for row in range(1, 6)]
    result = align(texts, boxes, anchors)
    assert [s.box_indices for s in result.segments] == [[1], [2], [3], [4], [5]]
    assert result.unmatched_boxes == [0]


def test_empty_inputs():
    assert align([], []).segments == []
    result = align([_text(30)], [])
    assert result.text_without_ink == [0]
