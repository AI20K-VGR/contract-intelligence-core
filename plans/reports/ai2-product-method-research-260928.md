# Research: Phương án nào đang làm chức năng AI2 trong product

**Mode**: depth
**Date**: 2026-09-28
**Sources reviewed**: 8 (toàn bộ trong repo; không dùng web vì câu hỏi là code product này)

## Summary

Product không để model đọc hợp đồng rồi chọn bên thắng. AI2 nhận snapshot AI1, rút fact bằng quy tắc trên dòng OCR, chỉ gọi LLM khi quy tắc không chuẩn hóa được, rồi đưa cặp khác nhau cho người thẩm định. Thiếu câu “theo Phụ lục N” là ghi chú chưa xác nhận, không xóa cặp. Câu model viết lại mà không nằm trong nguồn không được PASS.

Phương án này đang nằm trong `run_idp` và được DEC-1 khóa. Ba test vừa chạy: `3 passed in 4.42s`.

## Options / Comparison

| Option | Pros | Cons | Project fit |
|---|---|---|---|
| A. Rút fact cục bộ, LLM chỉ chuẩn hóa, người xem cặp | Bám đúng chữ OCR; không bịa phụ lục; không chọn thắng | Bỏ sót câu không khớp nhãn; LLM vẫn có thể viết lại câu | Đang chạy |
| B. LLM đọc cả hợp đồng và kết luận quan hệ | Viết được câu trôi | Bịa nguồn, chọn thắng, không kiểm được | DEC-1 cấm |
| C. Embedding quyết định hai đoạn có liên quan | Gợi ý đoạn gần nghĩa | Không phải bằng chứng chữ | DEC-1 cấm dùng để quyết định quan hệ |
| D. Không thấy “Phụ lục N” thì bỏ cặp | Ít cảnh báo hơn | Giấu khác biệt giá trị thật | DEC-1 cấm; test bắt buộc giữ cặp |

## Recommendation

**Priority 1**: Option A. Điều kiện: snapshot AI1 đã có dòng OCR; egress/LLM chỉ bật khi được phép; mọi cặp khác nhau ra `NEEDS_REVIEW`, không ra kết luận pháp lý.

**Fallback**: không có fallback trong product. Hết ngân sách hoặc không được gọi ra ngoài thì vẫn rút fact cục bộ, tắt LLM (`idp.py` đặt `llm = None` khi hết budget, và chặn egress).

## Phương án đang chạy

1. Worker backend, sau khi AI1 và manifest sẵn sàng, gửi job sang AI2 rồi lưu kết quả (`worker.py:467`, submit quanh `worker.py:592`).
2. `run_idp` (`idp.py:41`) rút cục bộ trước. Gọi model ngoài bị đóng khi không được phép hoặc hết budget (`idp.py:70-90`).
3. Fact lấy từ dòng OCR có nhãn (`ai1_snapshot_adapter.py:2053`, `_labelled_line_facts` tại `ai1_snapshot_adapter.py:2208`).
4. Chuẩn hóa: alias, số, số có phân tách nghìn, cụm “đồng” đi L0. Chỉ khi các nhánh đó không ra giá trị và LLM được cấu hình thì gọi `complete_json`, provenance `L2` (`fact.py:83-121`). Prompt cấm dịch, cấm object, cấm bịa, cấm kết luận pháp lý (`fact.py:124-128`).
5. So cặp cùng `item_key` trong một snapshot. Không chọn bên thắng (`compare.py:48`).
6. Cổng grounding: chữ gốc nằm trong nguồn thì PASS, trừ khi câu đã chuẩn hóa không còn là đoạn của nguồn. Câu viết lại thành `NEEDS_REVIEW`. Số thuần rút từ số gốc vẫn PASS (`grounding.py:12-19`, `grounding.py:177-187`).

## Vì sao chọn A

DEC-1 (`docs/decisions.md:12-14`, trạng thái active, 2026-09-27) ghi: cùng `item_key` trong một snapshot thì hiện cặp và hai citation. Thiếu dẫn chiếu phụ lục là chú thích chưa xác nhận, không xóa cặp. Không bịa câu dẫn chiếu. Không chọn bên thắng. Không dùng embedding để quyết định quan hệ.

Lý do gắn với việc làm: người thẩm định phải thấy hai chỗ chữ thật. Model kết luận thắng thì product không còn chỗ để người kiểm. Embedding chỉ đo gần nghĩa, không chứng minh hai dòng là cùng một điều khoản.

## Chứng minh

Lệnh vừa chạy trong `ai-service`:

`uv run pytest tests/test_gap_as_note.py tests/test_l0.py::test_grounding_rejects_a_rewritten_normalization tests/test_l0.py::test_grounding_keeps_digit_normalization -q`

Kết quả OBSERVED: `3 passed in 4.42s`.

| Việc phương án hứa | Chỗ khóa | Kết quả lần chạy này |
|---|---|---|
| Thân không nhắc phụ lục vẫn giữ cặp giá trị, quan hệ `UNCONFIRMED`, không bịa “theo Phụ lục 01” | `tests/test_gap_as_note.py:12-48` | passed |
| Câu LLM viết lại không được PASS | `tests/test_l0.py:157-166` | passed |
| Chuẩn hóa số từ chữ gốc vẫn PASS | `tests/test_l0.py:169` | passed |

`test_gap_as_note.py` dựng snapshot hai trang (1.000.000.000 và 1.200.000.000), chạy `run_idp`, rồi assert còn `COMPARABLE_DIFFERENCE` và `relation == UNCONFIRMED`.

## Evidence and references

[1] `docs/decisions.md:12-14` | repo | 2026-09-27 | VERIFIED (đọc file lần này)
[2] `ai-service/app/pipeline/idp.py:41-90` | repo | 2026-09-28 | VERIFIED
[3] `ai-service/app/pipeline/fact.py:83-128` | repo | 2026-09-28 | VERIFIED
[4] `ai-service/app/pipeline/compare.py:48` | repo | 2026-09-28 | VERIFIED
[5] `ai-service/app/pipeline/grounding.py:12-19` và `:177-187` | repo | 2026-09-28 | VERIFIED
[6] `backend/src/contract_intelligence/worker.py:467` và `:592` | repo | 2026-09-28 | VERIFIED
[7] pytest 3 passed, 4.42s | lệnh ở trên | 2026-09-28 | OBSERVED

## Open questions

- [ASSUMED] Hồ sơ 20 trang đang lưu vẫn ra đúng 7 fact và một cặp nếu chạy lại job hôm nay. Lần replay cũ không được chạy lại trong lượt này. Muốn chốt: chạy lại `run_idp` trên OCR của dossier đó.
- [ASSUMED] Màn hình product đang đọc đúng `pipeline_run.ai2_result_json` của job mới nhất. Lượt này không mở dossier trên trình duyệt.
- Câu “số lần thẩm định trên SQL” đã được đo riêng (join cũ đếm 4, lateral đếm 2) và không thuộc phương pháp rút fact.
