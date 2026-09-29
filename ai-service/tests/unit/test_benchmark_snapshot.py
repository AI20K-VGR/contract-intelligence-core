from scripts import benchmark_snapshot as bench


def test_critical_fields_cover_money_quantities_percentages_dates_and_numbers():
    text = (
        "Giá trị 12.500.000.000 đồng, số lượng 1.200, tạm ứng 25%, ký ngày 05/10/2026, "
        "Hợp đồng số 1026/2026/TLT-BA/MDTP. MST: 0101234567."
    )

    fields = bench.extract_critical_fields(text, page=3)

    assert {(f.type, f.value) for f in fields} == {
        ("MONEY", "12.500.000.000"),
        ("QUANTITY", "1.200"),
        ("PERCENTAGE", "25"),
        ("DATE", "05/10/2026"),
        ("CONTRACT_NUMBER", "1026/2026/TLT-BA/MDTP"),
        ("TAX_CODE", "0101234567"),
    }
    assert {f.page for f in fields} == {3}


def test_markdown_tables_unescape_cells_and_leave_out_the_contradiction_appendix():
    text = (
        "# PHỤ LỤC II\n\n| Mã | Diễn giải |\n|---|---|\n| A\\|1 | dòng 1<br>dòng 2 |\n| B | x |\n\n"
        f"{bench.CONTRADICTION_HEADING}\n\n| # | Chủ đề |\n|---|---|\n| 1 | VAT |\n"
    )

    tables = bench.parse_markdown_tables(text)

    assert tables == [
        {"header": ["Mã", "Diễn giải"], "rows": [["A|1", "dòng 1 dòng 2"], ["B", "x"]]}
    ]


def test_table_rows_are_exact_changed_missing_or_extra():
    ground_truth = [["1", "a"], ["2", "b"], ["3", "c"], ["4", "d"]]
    ocr = [["1", "a"], ["2", "B"], ["4", "d"], ["5", "e"]]

    outcome = bench.align_table_rows(ground_truth, ocr)

    assert [o["state"] for o in outcome] == ["exact", "changed", "missing", "exact"]
    assert (outcome[1]["cells_ok"], outcome[1]["cells"]) == (1, 2)
    assert outcome[0]["extra_ocr_rows"] == 1


def test_a_markdown_table_row_is_compared_cell_by_cell():
    assert bench._plain("|  DV-201 | Hồ sơ pháp lý nhóm 2 | bộ  |") == (
        "DV-201\nHồ sơ pháp lý nhóm 2\nbộ"
    )
    assert bench._plain("|---|:---:|") == ""
    assert bench._plain("3.1. Đối tượng của Hợp đồng") == "3.1. Đối tượng của Hợp đồng"


def test_only_the_line_holding_an_error_is_marked_wrong():
    reference = "Điều 3. Đối tượng\n3.1. Bên A giao việc cho Bên B."

    wrong = bench.line_errors(reference, ["Điều 3. Đối tượng", "3.1. Bên A giao viêc cho Bên B."])

    assert wrong == [False, True]


def test_a_run_the_ocr_skipped_is_reported_as_lost_text():
    skipped = "Mức phí áp dụng cho việc cấp phát sổ theo dõi tài sản bằng 2,5% giá trị phần việc. "
    reference = f"Bên A giao việc. {skipped}Bên B nhận việc."

    spans = bench.lost_spans(reference, "Bên A giao việc. Bên B nhận việc.")

    assert sum(s["chars"] for s in spans) == len(skipped)
    assert "2,5%" in spans[0]["text"]
    assert bench.lost_spans("Bên A giao việc.", "Bên A giao viêc.") == []


def test_sections_start_on_the_page_their_title_opens():
    pages = [
        "HỢP ĐỒNG LIÊN DANH\nĐiều 1. Định nghĩa",
        "3.5. Mười Phụ lục gồm Phụ lục I yêu cầu kỹ thuật\nPHỤ LỤC I — YÊU CẦU KỸ THUẬT\nI.1. ...",
        "tiếp theo phụ lục I",
        "PHỤ LỤC II — BẢNG GIÁ CHI TIẾT\n| Mã | Diễn giải |",
    ]
    titles = [
        "HỢP ĐỒNG CHÍNH",
        "PHỤ LỤC I — YÊU CẦU KỸ THUẬT VÀ TIÊU CHUẨN CHẤP NHẬN",
        "PHỤ LỤC II — BẢNG GIÁ CHI TIẾT",
    ]

    starts = bench.section_start_pages(pages, titles)

    assert starts == [1, 2, 4]
    assert bench.page_sections(len(pages), starts) == [0, 1, 1, 2]
