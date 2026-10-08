from __future__ import annotations

import io
import zipfile

from conftest import fixture_text

from evals.contract_graph.normalize import docx_to_text, html_to_text, operative_body


def test_block_tags_become_paragraph_breaks():
    raw = (
        "<html><body><p>Điều 1. Ph&#7841;m vi</p><p>1. Kho&agrave;n m&#7897;t;<br>d&ograve;ng hai.</p>"
        "<table><tr><td>Ô một</td><td>Ô hai</td></tr><tr><td>Hàng hai.</td></tr></table>"
        "<script>Điều 9. trong script</script><style>.x{}</style></body></html>"
    )

    lines = html_to_text(raw).split("\n")

    assert lines[0] == "Điều 1. Phạm vi"
    assert lines[1] == "1. Khoàn một;"
    assert lines[2] == "dòng hai."
    assert lines[3] == "Ô một Ô hai"
    assert lines[4] == "Hàng hai."
    assert "Điều 9" not in html_to_text(raw)


def test_inline_tags_do_not_split_suffix_labels():
    raw = '<p><span lang="VI">a</span>1<span>)<a href="#_ftn15"><span>[15]</span></a> </span>Riêng hợp đồng.</p>'

    assert html_to_text(raw) == "a1)[15] Riêng hợp đồng."


def test_json_escaped_html_payload_is_decoded():
    escaped = html_to_text(fixture_text("mini_vbhn_escaped.html"))
    plain = html_to_text(fixture_text("mini_vbhn.html"))

    assert "u003c" not in escaped and "\\n" not in escaped
    assert "đ)[3] Nội dung của điểm đ mới." in escaped
    assert "[3] Điểm này được bổ sung theo quy định tại điểm b khoản 2 Điều 1" in escaped
    # the payload re-renders the visible document: merged once, no duplicate lines
    assert escaped == plain
    # a payload chunk that shares nothing with the visible page is another document, not this one
    assert "Văn bản liên quan" not in escaped


def test_hard_wrapped_paragraph_is_joined():
    raw = (
        "<p>2. Sửa đổi, bổ sung một<br>số điểm của khoản<br>1 và khoản 2 Điều 3 như sau:<br>"
        "a) Sửa đổi điểm c như sau:<br>nội dung mới.</p>"
    )

    lines = html_to_text(raw).split("\n")

    assert lines[0] == "2. Sửa đổi, bổ sung một số điểm của khoản"
    assert lines[1] == "1 và khoản 2 Điều 3 như sau:"
    # a line ending with ':' is a heading for what follows, never joined
    assert lines[2] == "a) Sửa đổi điểm c như sau:"
    assert lines[3] == "nội dung mới."


def test_label_line_is_never_joined_to_previous_line():
    raw = "<p>2. Theo hình thức giá hợp đồng</p><p>a) Hợp đồng trọn gói</p><p>d1)[8] Hợp đồng khác</p>"

    assert html_to_text(raw).split("\n") == [
        "2. Theo hình thức giá hợp đồng",
        "a) Hợp đồng trọn gói",
        "d1)[8] Hợp đồng khác",
    ]


def test_operative_body_skips_toc_and_takes_longest_article_1():
    text = html_to_text(fixture_text("mini_amending.html"))

    body = operative_body(text)

    assert body.startswith("Điều 1. Sửa đổi, bổ sung một số điều")
    assert "4. Bãi bỏ khoản 3 Điều 7." in body
    assert "Điều 2. Hiệu lực" not in body
    assert "1. Sửa đổi, bổ sung khoản 2 Điều 3 như sau:" in body


def test_operative_body_ignores_quoted_article_heading():
    text = (
        "Điều 1. Sửa đổi, bổ sung một số điều của Nghị định số 10/2020/NĐ-CP như sau: "
        "1. Sửa đổi Điều 2 như sau: “Điều 2. Nội dung mới của Điều 2 gốc.” "
        "2. Bãi bỏ khoản 3 Điều 7. "
        'Điều 2. Hiệu lực thi hành Nghị định này có hiệu lực từ ngày ký "Điều 2. trích dẫn".'
    )

    body = operative_body(text)

    assert "2. Bãi bỏ khoản 3 Điều 7." in body
    assert "Hiệu lực thi hành" not in body


def test_operative_body_other_article():
    text = "Điều 1. Phạm vi. Điều 2. Sửa đổi Thông tư như sau: 1. Bãi bỏ khoản 1 Điều 4. Điều 3. Hiệu lực."

    assert operative_body(text, article="2", next_article="3") == (
        "Điều 2. Sửa đổi Thông tư như sau: 1. Bãi bỏ khoản 1 Điều 4."
    )


def _docx(document_xml: str, footnotes_xml: str | None) -> bytes:
    buf = io.BytesIO()
    with zipfile.ZipFile(buf, "w") as zf:
        zf.writestr("word/document.xml", document_xml)
        if footnotes_xml is not None:
            zf.writestr("word/footnotes.xml", footnotes_xml)
    return buf.getvalue()


W = 'xmlns:w="http://schemas.openxmlformats.org/wordprocessingml/2006/main"'


def test_docx_footnote_reference_becomes_inline_marker():
    document = (
        f"<w:document {W}><w:body>"
        "<w:p><w:r><w:t>Điều 3. Giải thích từ ngữ</w:t></w:r></w:p>"
        '<w:p><w:r><w:t>2.</w:t></w:r><w:r><w:footnoteReference w:id="2"/></w:r>'
        '<w:r><w:t xml:space="preserve"> Nội dung mới của khoản 2.</w:t></w:r></w:p>'
        "</w:body></w:document>"
    )
    footnotes = (
        f"<w:footnotes {W}>"
        '<w:footnote w:type="separator" w:id="-1"><w:p><w:r><w:t></w:t></w:r></w:p></w:footnote>'
        '<w:footnote w:id="2"><w:p><w:r><w:t>Khoản này được sửa đổi, bổ sung theo quy định tại '
        "khoản 1 Điều 1 Nghị định số 20/2021/NĐ-CP.</w:t></w:r></w:p></w:footnote>"
        "</w:footnotes>"
    )

    text = docx_to_text(_docx(document, footnotes))

    lines = text.split("\n")
    assert lines[0] == "Điều 3. Giải thích từ ngữ"
    assert lines[1] == "2.[1] Nội dung mới của khoản 2."
    assert lines[-1] == (
        "[1] Khoản này được sửa đổi, bổ sung theo quy định tại khoản 1 Điều 1 Nghị định số 20/2021/NĐ-CP."
    )


def test_docx_without_footnotes_part_is_body_only():
    document = f"<w:document {W}><w:body><w:p><w:r><w:t>Điều 1. Phạm vi</w:t></w:r></w:p></w:body></w:document>"

    assert docx_to_text(_docx(document, None)) == "Điều 1. Phạm vi"
