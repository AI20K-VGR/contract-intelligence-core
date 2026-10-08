from __future__ import annotations

import hashlib

import pytest

from evals.contract_graph.pairs import corpus

SALES_URL = "https://example.test/mau-hop-dong-mua-ban"


def contract_text(
    party: str = "Công ty TNHH Alpha",
    address: str = "số 12 Nguyễn Trãi, quận Thanh Xuân, Hà Nội",
    annex: bool = True,
    amend_in_annex: bool = False,
    articles: int = 6,
) -> str:
    """Synthetic SALES contract: ``articles`` Điều (Điều 2 has points), optional annex."""

    blocks = [
        [
            "ĐIỀU 1: ĐỐI TƯỢNG HỢP ĐỒNG",
            f"1. Bên Bán là {party} đồng ý bán và Bên Mua đồng ý mua máy phát điện 500 kVA.",
            "2. Hàng hóa mới một trăm phần trăm, sản xuất trong năm ký kết hợp đồng.",
            "3. Xuất xứ hàng hóa được ghi rõ trong chứng nhận của nhà sản xuất.",
        ],
        [
            "Điều 2 – Giá và phương thức thanh toán",
            "1. Giá hợp đồng là một tỷ hai trăm triệu đồng, đã bao gồm thuế giá trị gia tăng.",
            "2. Bên Mua thanh toán theo các đợt sau:",
            "a) Đợt một tạm ứng ba mươi phần trăm giá trị trong năm ngày kể từ ngày ký.",
            "b) Đợt hai thanh toán phần còn lại trong mười lăm ngày kể từ ngày nghiệm thu.",
            "3. Mọi khoản thanh toán thực hiện bằng chuyển khoản vào tài khoản của Bên Bán.",
        ],
        [
            "Điều 3. Giao hàng",
            f"1. Bên Bán giao hàng tại {address} trong thời hạn ba mươi ngày.",
            "2. Chi phí vận chuyển và bốc dỡ do Bên Bán chịu cho đến khi giao xong.",
        ],
        [
            "Điều 4. Bảo hành",
            "1. Thời hạn bảo hành là hai mươi bốn tháng kể từ ngày nghiệm thu hàng hóa.",
            "2. Bên Bán sửa chữa hoặc thay thế hàng lỗi trong bảy ngày kể từ khi nhận thông báo.",
        ],
        [
            "Điều 5. Phạt vi phạm",
            "1. Bên vi phạm nghĩa vụ chịu phạt tám phần trăm giá trị phần nghĩa vụ bị vi phạm.",
            "2. Bên Mua chậm thanh toán chịu lãi chậm trả theo lãi suất ngân hàng công bố.",
        ],
        [
            "Điều 6. Giải quyết tranh chấp",
            "1. Tranh chấp được giải quyết bằng thương lượng trong thời hạn ba mươi ngày.",
            "2. Hết thời hạn thương lượng, một bên có quyền khởi kiện tại tòa án có thẩm quyền.",
        ],
        [
            "Điều 7. Điều khoản chung",
            "1. Hợp đồng có hiệu lực kể từ ngày hai bên ký và đóng dấu hợp lệ.",
            "2. Hợp đồng lập thành bốn bản có giá trị pháp lý như nhau, mỗi bên giữ hai bản.",
        ],
    ]
    lines = ["HỢP ĐỒNG MUA BÁN HÀNG HÓA", f"Bên Bán: {party}, địa chỉ {address}."]
    for block in blocks[:articles]:
        lines.extend(block)
    if annex:
        lines.append("PHỤ LỤC 01")
        if amend_in_annex:
            lines.append(
                "1. Sửa đổi khoản 1 Điều 2 như sau: “1. Giá hợp đồng là một tỷ ba trăm triệu đồng.”"
            )
        else:
            lines.append("1. Danh mục hàng hóa gồm máy phát điện, tủ điện và cáp đấu nối đi kèm.")
        lines.append("2. Thông số kỹ thuật chi tiết theo catalogue của nhà sản xuất đính kèm.")
    return "\n".join(lines)


def source(url: str = SALES_URL, profile: str = "SALES") -> dict:
    return {"url": url, "profile": profile, "title": "mẫu", "has_annex_section": True, "note": ""}


def service_text() -> str:
    """Another topic (office cleaning), another vocabulary, same shape."""

    return "\n".join(
        [
            "Điều 1. Phạm vi dịch vụ",
            "1. Bên cung ứng làm sạch sàn, kính và khu vệ sinh của tòa văn phòng mỗi tối.",
            "2. Nhân viên vệ sinh mặc đồng phục và đeo thẻ khi làm việc tại tòa nhà.",
            "Điều 2. Phí dịch vụ",
            "1. Phí dịch vụ hằng tháng là bốn mươi lăm triệu đồng cho toàn bộ diện tích.",
            "2. Phí được điều chỉnh khi diện tích làm sạch tăng quá mười phần trăm.",
            "Điều 3. Hóa chất và dụng cụ",
            "1. Bên cung ứng tự trang bị máy chà sàn, hóa chất có nguồn gốc rõ ràng.",
            "2. Hóa chất phải an toàn với người dùng và không làm hư hại bề mặt đá.",
            "Điều 4. Nghiệm thu chất lượng",
            "1. Đại diện tòa nhà kiểm tra chất lượng mỗi sáng theo bảng tiêu chí đính kèm.",
            "2. Hạng mục không đạt phải được làm lại trong vòng hai giờ kể từ khi báo.",
            "Điều 5. Chấm dứt dịch vụ",
            "1. Mỗi bên được đơn phương chấm dứt khi báo trước ba mươi ngày bằng văn bản.",
            "2. Bên cung ứng hoàn trả thẻ ra vào và tài sản mượn khi chấm dứt dịch vụ.",
            "Điều 6. Bảo mật",
            "1. Nhân viên không được tiết lộ tài liệu nhìn thấy trong khi dọn văn phòng.",
            "2. Vi phạm bảo mật là căn cứ để thay nhân viên ngay trong ngày phát hiện.",
        ]
    )


def test_normalize_headings_variants():
    text = "\n".join(
        [
            "ĐIỀU 1: ĐỐI TƯỢNG",
            "Điều 2 – Giá",
            "Điều 3. Thanh toán",
            "DIEU 4 - Bao hanh",
            "PHỤ LỤC 01",
            "Phụ lục",
            "Hai bên thực hiện theo Điều 5: nội dung đã thỏa thuận.",
        ]
    )

    assert corpus.normalize_headings(text).split("\n") == [
        "Điều 1. ĐỐI TƯỢNG",
        "Điều 2. Giá",
        "Điều 3. Thanh toán",
        "Điều 4. Bao hanh",
        "Phụ lục 01",
        "Phụ lục",
        "Hai bên thực hiện theo Điều 5: nội dung đã thỏa thuận.",
    ]


def test_build_doc_inherits_heading():
    doc = corpus.build_doc(source(), contract_text())
    by_text = {n["text"]: n for n in doc["nodes"]}

    point = next(n for t, n in by_text.items() if t.startswith("Đợt hai"))
    assert point["heading"] == "Điều 2. Giá và phương thức thanh toán"
    annex_clause = next(n for t, n in by_text.items() if t.startswith("Danh mục"))
    assert annex_clause["heading"] == "Phụ lục 01"
    assert all(len(n["heading"]) <= 120 for n in doc["nodes"])
    # an article root with a short title stays: it has children
    assert "Giao hàng" in by_text
    assert doc["n_articles"] == 6
    assert doc["profile"] == "SALES"


def test_short_leaf_nodes_dropped():
    text = contract_text().replace(
        "3. Xuất xứ hàng hóa được ghi rõ trong chứng nhận của nhà sản xuất.", "3. Không."
    )
    doc = corpus.build_doc(source(), text)

    assert all(n["text"] != "Không." for n in doc["nodes"])


def test_doc_with_fewer_than_five_articles_rejected():
    with pytest.raises(corpus.RejectedDocument) as excinfo:
        corpus.build_doc(source(), contract_text(articles=4))

    assert excinfo.value.n_articles == 4


def test_doc_id_is_stable_hash_of_url():
    doc = corpus.build_doc(source(), contract_text())

    assert doc["doc_id"] == "pd-" + hashlib.sha256(SALES_URL.encode("utf-8")).hexdigest()[:10]
    assert corpus.build_doc(source(), contract_text(annex=False))["doc_id"] == doc["doc_id"]
    assert all(n["node_id"].startswith(doc["doc_id"] + ":") for n in doc["nodes"])


def test_near_duplicates_share_cluster():
    original = corpus.build_doc(source("https://a.test/1"), contract_text())
    copied = corpus.build_doc(
        source("https://b.test/2"),
        contract_text(party="Công ty Cổ phần Beta", address="số 8 Lê Lợi, quận 1, TP.HCM"),
    )
    other = corpus.build_doc(source("https://c.test/3", "SUPPLY_SERVICE"), service_text())

    assert corpus.jaccard(corpus.shingles(corpus.doc_text(original)),
                          corpus.shingles(corpus.doc_text(copied))) >= 0.8
    clusters = corpus.near_duplicate_clusters([other, copied, original])

    assert sorted(sorted(c["doc_ids"]) for c in clusters) == sorted(
        [sorted([original["doc_id"], copied["doc_id"]]), [other["doc_id"]]]
    )
    assert clusters == corpus.near_duplicate_clusters([original, other, copied])


def test_same_article_headings_share_cluster_even_when_text_differs():
    first = corpus.build_doc(source("https://a.test/1"), contract_text(annex=False))
    rewritten = contract_text(annex=False)
    for word, other in (
        ("Bên Bán", "Người bán"),
        ("Bên Mua", "Người mua"),
        ("ngày", "hôm"),
        ("trong", "trong vòng"),
        ("đồng", "VNĐ"),
    ):
        rewritten = rewritten.replace(word, other)
    second = corpus.build_doc(source("https://b.test/2"), rewritten)

    assert corpus.jaccard(corpus.shingles(corpus.doc_text(first)),
                          corpus.shingles(corpus.doc_text(second))) < 0.8
    clusters = corpus.near_duplicate_clusters([first, second])

    assert len(clusters) == 1


def test_content_contamination_detected():
    spike_clause = (
        "Nếu Bên Mua chậm thanh toán theo thời hạn quy định tại Hợp Đồng thì Bên Mua sẽ thanh "
        "toán tiền lãi với lãi suất 0,5% trên số tiền chậm thanh toán mỗi ngày."
    )
    spike = corpus.Spike.from_texts(urls=["https://spike.test/heldout"], texts=[spike_clause])
    clean = corpus.build_doc(source("https://new.test/x"), contract_text())
    dirty_text = contract_text().replace(
        "2. Bên Mua chậm thanh toán chịu lãi chậm trả theo lãi suất ngân hàng công bố.",
        "2. " + spike_clause,
    )
    dirty = corpus.build_doc(source("https://new.test/y"), dirty_text)

    assert corpus.contaminated(clean, spike) is False
    assert corpus.contaminated(dirty, spike) is True
    assert corpus.contaminated({**clean, "url": "http://www.spike.test/heldout/"}, spike) is True
    assert corpus.contaminated({**clean, "url": "repo:ai-service/fixtures/x.md"}, spike) is True


def test_real_spike_sources_load():
    spike = corpus.load_spike()

    assert spike.clause_shingles
    assert any("luatvantin.com.vn" in url for url in spike.urls)
