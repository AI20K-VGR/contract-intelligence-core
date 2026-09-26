# Plan: AI2 giữ cổng citation, không ép PASS

**Đã chốt bởi người dùng** trong goal: sau khi plan này tồn tại thì chấp nhận và cook.
**Cook của phạm vi này** là các test EC đã chạy xanh, không phải viết lại toàn bộ AI2.

## Hướng đã chọn

Giữ pipeline deterministic: luật L0, trích đúng chữ, không chọn legal winner, không gọi LLM khi egress hoặc hạn mức embedding không cho phép. Cổng citation (`app/pipeline/citations.py`) chỉ trả VALID khi có source hash, quote hash, offset và line id. Fixture EC không mang hash thì job ở `NEEDS_REVIEW` là đúng, không phải lỗi cần hạ xuống PASS.

## Đã làm

- Năm case im lặng (EC-005, 007, 031, 033, 047) thành `NEEDS_REVIEW` có issue, không thêm node. Commit `2128d23`.
- EC-050 và EC-055 thành `BLOCKED` nhưng extraction cục bộ vẫn `SUCCEEDED`. Cùng commit.
- EC-014 không còn bị coi là header trang. Commit `198e426`.
- 56 EC giữ nguyên node, nhãn và dòng bảng; không có `legal_winner`. Commit `025b842`.
- Câu "seller tax code" map tới `mst_seller` và trích MST `0311111111`. File `app/reasoning/query.py`.

## Không làm

- Không điền hash giả để 14 case (EC-001, 009, 010, 016, 022, 023, 025, 030, 034, 035, 036, 037, 038, 051) thành PASS. Lý do: `citations.py` dòng 86–88 và 113–114 từ chối citation khi thiếu hash hoặc line id.
- Không đưa pgvector, ACL backend, OCR engine vào AI2. Các mục đó nằm ngoài service này trong `docs/ai2/AI2-06-implementation-gap.vi.md`.

## Nghiệm thu

`uv run pytest -q tests/test_ec_audit.py tests/test_ec_silent_pass.py tests/test_ec_policy_block.py tests/test_reasoning.py tests/test_catalog.py` trong `ai-service` phải xanh.
