from __future__ import annotations

import json

import pytest
from conftest import COMMITTED_DATA, fixture_text

from evals.contract_graph.gold import (
    EXTRACTOR_VERSION,
    Note,
    anchor_target,
    build_gold,
    canonical_address,
    extract_notes,
    gold_summary,
    note_op,
    note_source,
)
from evals.contract_graph.normalize import html_to_text, split_notes

DECREE_TITLE = (
    "Nghị định số 50/2021/NĐ-CP sửa đổi, bổ sung một số điều của Nghị định số 37/2015/NĐ-CP"
)


def test_op_is_read_before_theo_quy_dinh_tai():
    note = Note(7, f"Điểm này được bổ sung theo quy định tại điểm đ khoản 2 Điều 1 {DECREE_TITLE}.")

    assert note_op(note) == "INSERTION"
    assert note_op(
        Note(2, f"Khoản này được sửa đổi, bổ sung theo quy định tại khoản 1 Điều 1 {DECREE_TITLE}.")
    ) == ("SUBSTITUTION")


def test_repeal_and_phrase_ops_map():
    assert note_op(
        Note(
            1, "Khoản này được bãi bỏ theo quy định tại khoản 4 Điều 1 Thông tư số 26/2015/TT-BTC."
        )
    ) == ("REPEAL")
    assert note_op(
        Note(
            2,
            "Bỏ cụm từ “hoặc chi nhánh” theo quy định tại khoản 2 Điều 1 Thông tư số 26/2015/TT-BTC.",
        )
    ) == ("REPEAL")
    assert note_op(
        Note(
            3,
            "Thay cụm từ “A” bằng cụm từ “B” theo quy định tại khoản 3 Điều 1 Thông tư số 26/2015/TT-BTC.",
        )
    ) == ("SUBSTITUTION")
    assert note_op(
        Note(
            4,
            "Cụm từ “A” được thay thế bằng cụm từ “B” theo quy định tại khoản 3 Điều 1 Luật số 26/2018/QH14.",
        )
    ) == ("SUBSTITUTION")


def test_source_address_canonical_keeps_d_stroke():
    src, doc = note_source(
        Note(7, f"Điểm này được bổ sung theo quy định tại điểm đ khoản 2 Điều 1 {DECREE_TITLE}.")
    )

    assert src == "diem đ khoan 2 dieu 1"
    assert src != "diem d khoan 2 dieu 1"
    assert doc == "50/2021/NĐ-CP"
    assert canonical_address("điểm d khoản 2 Điều 1") == "diem d khoan 2 dieu 1"
    assert canonical_address("Phụ lục 01") == "phu luc 1"
    assert canonical_address("khoản 05 Điều 012") == "khoan 5 dieu 12"


def test_source_picks_the_citation_of_the_pair_document():
    note = Note(
        9,
        "Khoản này được sửa đổi, bổ sung lần thứ 01 theo quy định tại khoản 3 Điều 1 Thông tư số 26/2015/TT-BTC, "
        "có hiệu lực kể từ ngày 01/01/2015; được bãi bỏ lần thứ 02 theo quy định tại điểm b khoản 2 Điều 1 "
        "Thông tư số 130/2016/TT-BTC, có hiệu lực kể từ ngày 01/7/2016.",
    )

    assert note_source(note, "26/2015/TT-BTC") == ("khoan 3 dieu 1", "26/2015/TT-BTC")
    assert note_op(note, "26/2015/TT-BTC") == "SUBSTITUTION"
    assert note_source(note, "130/2016/TT-BTC") == ("diem b khoan 2 dieu 1", "130/2016/TT-BTC")
    assert note_op(note, "130/2016/TT-BTC") == "REPEAL"
    assert note_source(note, "99/2019/NĐ-CP") == (None, None)


def test_anchor_target_from_marker_position():
    body = "\n".join(
        [
            "Điều 3. Phạm vi",
            "1. Khoản một.",
            "Điều 4. Loại hợp đồng",
            "1. Theo tính chất:",
            "c) Điểm c của khoản 1.",
            "2. Theo giá:",
            "a) Trọn gói;",
            "c)[3] Nội dung mới.",
        ]
    )

    assert anchor_target(body, 3, "điểm") == "diem c khoan 2 dieu 4"
    assert anchor_target(body, 3, "khoản") == "khoan 2 dieu 4"
    assert anchor_target(body, 3, "điều") == "dieu 4"
    assert anchor_target(body, 3, "cụm từ") == "diem c khoan 2 dieu 4"
    assert anchor_target(body, 9, "điểm") is None


def test_anchor_target_marker_on_article_heading():
    body = "Điều 22. Quyết toán\n3. Khoản ba.\nĐiều 23. Thanh lý hợp đồng xây dựng [18]\nViệc thanh lý."

    assert anchor_target(body, 18, "điều") == "dieu 23"
    assert anchor_target(body, 18, "khoản") is None


def test_anchor_target_is_none_where_no_canonical_address_exists():
    body = "\n".join(
        [
            "Điều 9. Hiệu lực",
            "1. Thông tư có hiệu lực.",
            "PHỤ LỤC",
            "1.[29] Mẫu TMĐT-1.",
            "Phụ lục 2",
            "3.[31] Mẫu 3.",
        ]
    )

    # an annex without a number has no canonical address: never fall back to the previous article
    assert anchor_target(body, 29, "phụ lục") is None
    assert anchor_target(body, 29, "khoản") is None
    assert anchor_target(body, 29, None) is None
    assert anchor_target(body, 31, "khoản") == "khoan 3 phu luc 2"
    assert anchor_target(body, 31, "mẫu") is None
    # a chapter heading belongs to no article: "Tên chương này" / phrase notes on it never anchor
    # into the article before it
    chapter = "Điều 4. Phạm vi\n2. Khoản hai.\nChương II QUẢN LÝ WEBSITE [7]\nĐiều 5. Đăng ký"
    assert anchor_target(chapter, 7, "chương") is None
    assert anchor_target(chapter, 7, None) is None


def test_suffix_canonical_forms():
    assert canonical_address("điểm d1 khoản 2 Điều 3") == "diem d1 khoan 2 dieu 3"
    assert canonical_address("khoản 05a Điều 18") == "khoan 5a dieu 18"
    assert canonical_address("Điều 30a") == "dieu 30a"
    assert canonical_address("điểm d1 khoản 2 Điều 3") != canonical_address("điểm d khoản 2 Điều 3")


def test_anchor_target_on_suffix_labels():
    body, _ = split_notes(html_to_text(fixture_text("mini_suffix_vbhn.html")))

    assert anchor_target(body, 1, "điểm") == "diem d1 khoan 2 dieu 3"
    assert anchor_target(body, 2, "điểm") == "diem d2 khoan 2 dieu 3"
    assert anchor_target(body, 3, "khoản") == "khoan 5a dieu 18"
    assert anchor_target(body, 4, "điều") == "dieu 30a"

    records = build_gold(
        "mini-suffix", html_to_text(fixture_text("mini_suffix_vbhn.html")), "30/2022/NĐ-CP"
    )
    targets = [r["target_address"] for r in records]
    assert targets == [
        "diem d1 khoan 2 dieu 3",
        "diem d2 khoan 2 dieu 3",
        "khoan 5a dieu 18",
        "dieu 30a",
    ]
    assert not any(t in {"diem d khoan 2 dieu 3", "khoan 5 dieu 18", "dieu 30"} for t in targets)
    assert {r["op"] for r in records} == {"INSERTION"}


def test_notes_citing_other_documents_are_filtered():
    text = html_to_text(fixture_text("mini_vbhn.html"))

    notes = extract_notes(text)
    records = build_gold("mini", text, "20/2021/NĐ-CP")

    assert [n.no for n in notes] == [1, 2, 3, 4, 5, 6]
    assert [r["note_no"] for r in records] == [1, 2, 3, 4, 5]
    assert all(r["amending_doc"] == "20/2021/NĐ-CP" for r in records)
    assert [(r["src_address"], r["op"], r["target_address"]) for r in records] == [
        ("khoan 1 dieu 1", "SUBSTITUTION", "khoan 2 dieu 3"),
        ("diem a khoan 2 dieu 1", "SUBSTITUTION", "diem c khoan 1 dieu 4"),
        ("diem b khoan 2 dieu 1", "INSERTION", "diem đ khoan 2 dieu 4"),
        ("khoan 3 dieu 1", "INSERTION", "khoan 5 dieu 6"),
        ("khoan 4 dieu 1", "REPEAL", "khoan 3 dieu 7"),
    ]


def test_unmatched_op_is_other_and_counted_not_scored():
    text = "\n".join(
        [
            "Điều 5. Giấy phép",
            "1.[1] Nội dung.",
            "2.[2] Nội dung khác.",
            "[1] Khoản này được đình chỉ thi hành theo quy định tại khoản 2 Điều 1 Nghị định số 20/2021/NĐ-CP.",
            "[2] Khoản này được bổ sung theo quy định tại khoản 3 Điều 1 Nghị định số 20/2021/NĐ-CP.",
        ]
    )

    records = build_gold("p", text, "20/2021/NĐ-CP")

    assert [r["op"] for r in records] == ["OTHER", "INSERTION"]
    assert gold_summary(records) == {"INSERTION": 1, "OTHER": 1}


def test_gold_records_are_not_approved():
    records = build_gold("mini", html_to_text(fixture_text("mini_vbhn.html")), "20/2021/NĐ-CP")

    assert records
    for record in records:
        assert record["approved"] is False
        assert record["extractor_version"] == EXTRACTOR_VERSION
        assert record["pair_id"] == "mini"
        assert set(record) == {
            "pair_id",
            "note_no",
            "op",
            "level",
            "src_address",
            "amending_doc",
            "target_address",
            "note_text",
            "approved",
            "extractor_version",
        }
        assert len(record["note_text"]) <= 200


# ---- Tests After: committed dataset -------------------------------------------------------------

SUFFIX_VALUE = r"(?:diem [a-zđ]\d+|khoan \d+[a-zđ]|dieu \d+[a-zđ])\b"


def _nd50_gold() -> list[dict]:
    path = COMMITTED_DATA / "nd50-2021" / "gold.jsonl"
    if not path.exists():
        pytest.fail(f"committed pair nd50-2021 missing: {path}")
    return [
        json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()
    ]


def test_nd50_gold_suffix_targets():
    import re

    gold = _nd50_gold()
    suffixed = [
        r
        for r in gold
        if r["op"] == "INSERTION"
        and r["target_address"]
        and re.search(SUFFIX_VALUE, r["target_address"])
    ]
    listing = "\n".join(
        f"[{r['note_no']}] {r['src_address']} -> {r['target_address']}" for r in suffixed
    )

    assert len(suffixed) == 7, f"suffix INSERTION targets for review:\n{listing}"
    by_note = {r["note_no"]: r["target_address"] for r in gold}
    assert by_note[8] == "diem d1 khoan 2 dieu 3"
    assert by_note[9] == "diem d2 khoan 2 dieu 3"
