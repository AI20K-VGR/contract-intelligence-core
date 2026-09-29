from scripts import markdown_to_png as md2png


def test_the_title_and_intro_join_the_first_section():
    text = "# Báo cáo\n\nGiới thiệu.\n\n## 1. Kết quả\n\nA\n\n## 2. Bảng\n\nB\n"

    parts = md2png.sections(text)

    assert [title for title, _ in parts] == ["1. Kết quả", "2. Bảng"]
    assert parts[0][1].startswith("# Báo cáo")
    assert parts[1][1].startswith("## 2. Bảng")


def test_a_report_without_sections_is_one_image():
    assert md2png.sections("# Báo cáo\n\nChỉ có đoạn mở đầu.") == [
        ("report", "# Báo cáo\n\nChỉ có đoạn mở đầu.")
    ]


def test_file_names_drop_vietnamese_diacritics():
    assert md2png.slug("Cờ review và độ tin cậy dòng") == "co-review-va-do-tin-cay-dong"
