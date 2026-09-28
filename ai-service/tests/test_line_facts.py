"""OCR lines with a clear label become facts. Bare numbers do not."""

from __future__ import annotations

from app.pipeline.ai1_snapshot_adapter import adapt_snapshot
from app.pipeline.contract_events import extract_contract_events
from app.pipeline.idp import run_idp
from app.tools.store import InMemorySnapshotStore
from tests.test_same_snapshot_pair import _page, _snapshot


def test_party_tax_payment_and_annex_total_are_facts() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "more-facts",
            [
                _page(
                    1,
                    [
                        "BÊN A (CHỦ ĐẦU TƯ)",
                        "Tên đơn vị: CÔNG TY CỔ PHẦN PHÚC THỊNH",
                        "Mã số thuế: 0109988776",
                        "BÊN B (NHÀ CUNG CẤP)",
                        "Tên đơn vị: CÔNG TY TNHH CÔNG NGHỆ MINH HẢI",
                        "Mã số thuế: 0201122334",
                        "4.1. Tổng giá trị hợp đồng tạm tính là 1.286.400.000 đồng.",
                        "4.2. Bên A thanh toán 30% trong vòng 07 ngày; 40% sau triển khai; 30% còn lại.",
                        "6.2. Thực hiện thanh toán theo đúng điều kiện hợp đồng.",
                    ],
                ),
                _page(2, ["PHỤ LỤC 01 - BẢNG", "|  Tổng cộng |  |  |  |  | 4.149.360.000  |"]),
            ],
        )
    )
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    by_key: dict[str, list[str]] = {}
    for fact in job.contribution.facts:
        by_key.setdefault(fact.item_key or "", []).append(fact.raw_value)
    assert "PHÚC THỊNH" in by_key["party_a"][0]
    assert "MINH HẢI" in by_key["party_b"][0]
    assert by_key["mst_party_a"] == ["0109988776"]
    assert by_key["mst_party_b"] == ["0201122334"]
    assert set(by_key["contract_value"]) == {"1286400000", "4149360000"}
    assert len(by_key["payment_schedule"]) == 1
    assert "30%" in by_key["payment_schedule"][0]
    assert "6.2" not in by_key["payment_schedule"][0]


def test_other_contract_shapes_keep_only_labelled_facts() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "other-shapes",
            [
                _page(
                    1,
                    [
                        "BÊN A (BÊN MUA):TRƯỜNG TIỂU HỌC VÀ TRUNG HỌC CƠ SỞ LÊ LỢI",
                        "Mã số thuế: 5900985976",
                        "1. Phương thức thanh toán: Chuyển khoản",
                        "2. Thời hạn thanh toán: Bên A sẽ thanh toán cho Bên B trong vòng 30 ngày làm",
                        "Giá trị hợp đồng đã thực hiện:49.900.000 (Bốn mươi chín triệu chín trăm nghìn đồng)",
                        "ĐẠI DIỆN BÊN A",
                    ],
                ),
                _page(
                    2,
                    [
                        "Ben A: CONG TY TNHH MINH HOA. Dai dien: Nguyen Van A. Ma so thue: 0101234567.",
                        "1.1. Bên giao thầu (Bên A — Chủ đầu tư)",
                        "- Tên đầy đủ: Công ty cổ phần Đầu tư ABC",
                        "- Giấy chứng nhận đăng ký doanh nghiệp số 0312345678 do Phòng Đăng ký.",
                        "Mã số thuế ghi tại Điều này: 0312345678",
                        "1.2. Bên nhận thầu (Bên B — Nhà thầu thi công)",
                        "- Tên đầy đủ: Công ty trách nhiệm hữu hạn Xây lắp XYZ",
                        "- Mã số thuế: 0322222222",
                        "1.3. Ghi nhận cố ý lệch",
                        "Tại trang đóng dấu, Bên A được ghi: Công ty ABC, MST 0399999999.",
                        "Trong danh mục nhà cung cấp, MST 0311111111 — trùng tên.",
                        "Hop dong co hieu luc ke tu ngay ky. Tien do thanh toan: 30% tam ung, 40% sau ban giao, 30% sau nghiem thu.",
                        "|  TOTAL | Tong gia tri thanh toan |  |  |  | 28.391.200  |",
                        "|  A-01 | Gia tri / muc dich su dung item 1 | seat | 2 | 120.000 | 240.000  |",
                        "| Tạm ứng | 30%, thu hồi dần từ các đợt thanh toán khối lượng |",
                    ],
                ),
            ],
        )
    )
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    by_key: dict[str, list[str]] = {}
    for fact in job.contribution.facts:
        by_key.setdefault(fact.item_key or "", []).append(fact.raw_value)
    assert "LÊ LỢI" in by_key["party_a"][0]
    assert "MINH HOA" in by_key["party_a"][1]
    assert any("Đầu tư ABC" in value for value in by_key["party_a"])
    assert any("XYZ" in value for value in by_key["party_b"])
    assert "5900985976" in by_key["mst_party_a"]
    assert "0101234567" in by_key["mst_party_a"]
    assert "0312345678" in by_key["mst_party_a"]
    assert "0399999999" in by_key["mst_party_a"]
    assert by_key["mst_party_a"].count("0312345678") == 1
    assert by_key["mst_party_b"] == ["0322222222"]
    assert by_key["mst"] == ["0311111111"]
    assert "49900000" in by_key["contract_value"]
    assert "28391200" in by_key["contract_value"]
    assert "240000" not in by_key["contract_value"]
    assert any("30%" in value and "40%" in value for value in by_key["payment_schedule"])
    assert "Chuyển khoản" in by_key["payment_method"][0]
    assert "30 ngày" in by_key["payment_term"][0]
    assert not any("Tạm ứng" in value for value in by_key.get("payment_schedule", []))
    assert not any("ĐẠI DIỆN" in value for value in by_key["party_a"])


def test_total_label_takes_the_amount_on_the_next_line() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "tong-cong",
            [
                _page(
                    1,
                    [
                        "Tổng cộng",
                        "49,900,000",
                        "2,000,000",
                    ],
                )
            ],
        )
    )
    store = InMemorySnapshotStore()
    store.put(adapted.record)
    job = run_idp(adapted.record, adapted.envelope, store=store)
    assert job.contribution is not None
    values = [fact.normalized_value for fact in job.contribution.facts if fact.item_key == "contract_value"]
    assert values == ["49900000"]


def test_party_event_is_only_the_heading() -> None:
    adapted = adapt_snapshot(
        _snapshot(
            "party-event",
            [
                _page(
                    1,
                    [
                        "BÊN A (CHỦ ĐẦU TƯ)",
                        "6.2. Bên A thanh toán theo điều kiện hợp đồng.",
                    ],
                )
            ],
        )
    )
    events = extract_contract_events(adapted.record)
    party = [event for event in events if event.event_type == "PARTY_DECLARATION"]
    assert len(party) == 1
    assert "CHỦ ĐẦU TƯ" in party[0].raw_text
    assert any(event.event_type == "PAYMENT" for event in events)
