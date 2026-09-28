# Research: Vì sao từng bước của phương án AI2

**Mode**: depth
**Date**: 2026-09-28
**Sources reviewed**: 6

## Summary

Mỗi bước phục vụ một việc: người rà phải mở lại đúng hai chỗ chữ, máy không kết luận pháp lý. Bước sau không được phá bước trước. Hướng bị loại ở bước ghép cặp là chặn khi thân không viết “Phụ lục 01”, và để model hoặc embedding chọn phụ lục nào sửa điều nào.

## Các bước và lý do chọn

### 1. Máy chỉ đưa ứng viên, người quyết định

BRD cấm hệ thống gắn hiệu lực, thứ tự ưu tiên tài liệu, hay `LEGAL_WINNER` (`docs/ai2/AI2-DOC-02-brd.vi.md:9`). Mọi bước sau được chọn vì chúng dừng ở “khác nhau / thiếu dẫn chiếu”, không đi tới “bên này thắng”.

### 2. AI2 chạy sau snapshot AI1

Worker chỉ submit khi manifest và input AI1 đã có (`backend/src/contract_intelligence/worker.py:467-479`). AI2 không tự OCR. Không có dòng AI1 thì không có chỗ để trích dẫn.

### 3. Hết quyền gọi ra ngoài thì vẫn rút cục bộ, không hủy cả job

`run_idp` đặt `llm = None` khi hết budget hoặc egress không được duyệt, và vẫn để rút fact cục bộ (`ai-service/app/pipeline/idp.py:65-94`). Lý do ghi trong comment: gói cho người rà vẫn phải ra. Tắt cả job vì model chết thì người rà không thấy gì.

### 4. Fact lấy từ dòng OCR có nhãn, không bảo model đọc cả trang

Nhãn trên dòng đi vào `_labelled_line_facts` (`ai-service/app/pipeline/ai1_snapshot_adapter.py:2053`, hàm tại `:2208`). Người rà bấm đúng dòng đó. Model tự viết giá trị thì không còn dòng để mở.

### 5. L0 trước, LLM chỉ khi L0 không ra giá trị

`_normalize` thử alias, số, số có dấu phân tách, cụm “đồng”, rồi mới `complete_json` (`fact.py:83-121`). Brainstorm lát 5: fact L0 làm được thì không gọi LLM dù egress đang bật (`plans/reports/ai2-five-slice-brainstorm-260927.md:43`). Số “1.286.400.000 đồng” là quy tắc. Đưa nó cho model dễ thành một câu khác, rồi cổng grounding phải xử lý câu đó.

Object lồng bị từ chối, provenance giữ L0 (`tests/test_l0.py:369-387`). Một dict không phải giá trị để đặt cạnh dòng OCR.

### 6. Câu viết lại không được hưởng PASS của chữ gốc

Chữ gốc nằm trong nguồn thì bình thường PASS. Nếu câu đã chuẩn hóa không còn là đoạn của nguồn, và không phải dạng số thuần của cùng số tiền, trạng thái thành `NEEDS_REVIEW` (`grounding.py:16-18`, `grounding.py:177-187`). Nếu không có bước này, câu model sửa OCR vẫn PASS vì chữ OCR gốc có nằm trên trang.

### 7. Ghép cùng `item_key` trong một snapshot

Ba hướng trong brainstorm (`plans/reports/ai2-five-slice-brainstorm-260927.md:17-25`):

| Hướng | Vì sao không phải mặc định |
|---|---|
| A. Thiếu chữ “Phụ lục 01” ở thân thì không ghép | Báo cáo ghi hồ sơ `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` không có chữ đó. Người rà không thấy hai giá trị. Lượt này không mở lại OCR hồ sơ đó. |
| B. Cùng `item_key` thì hiện cặp và hai citation. Thiếu dẫn chiếu là chú thích chưa xác nhận | Lát nhỏ nhất vẫn cho thấy cả hai số và mở cả hai nguồn |
| C. Embedding hoặc LLM chọn phụ lục nào sửa điều nào | Phán đoán gần pháp lý. Đắt và chậm |

Đã chọn B. DEC-1 ghi lại (`docs/decisions.md:12-14`). `compare_facts` ghi một finding là hai nguồn, không có bên thắng (`compare.py:48`).

### 8. Không bịa câu “theo Phụ lục 01”

Thiếu câu trên trang là thiếu bằng chứng, không phải lý do để viết câu đó vào nguồn. Test `test_missing_annex_mention_is_unconfirmed_note_not_a_dropped_pair` bắt cặp còn `COMPARABLE_DIFFERENCE`, quan hệ `UNCONFIRMED`, và chữ “theo Phụ lục 01” không xuất hiện trong trang (`tests/test_gap_as_note.py:12-48`).

### 9. Chưa tách sáu bộ trích theo loại hợp đồng

Sáu profile đã có file và test, pipeline trích xuất không gọi chúng. Brainstorm: không xây sáu bộ trước khi có bộ mẫu người duyệt (`ai2-five-slice-brainstorm-260927.md:37-39`). Một bộ trích dùng chung. Nhãn loại, nếu làm sau, chỉ là cờ cần rà.

### 10. Sửa cây trên bản sao, không ghi đè dòng AI1

Brainstorm lát 3: ghi đè node gốc làm mất chỗ đối chiếu (`ai2-five-slice-brainstorm-260927.md:31-35`). Cạnh suy ra phải trỏ về dòng gốc. Thiếu tín hiệu thì thành cờ, không thành cạnh im.

## Recommendation

Giữ đúng thứ tự này. Bỏ bước 6 thì câu model sửa OCR được PASS. Bỏ bước 7 hướng B thì hồ sơ không viết “Phụ lục 01” lại im. Đổi bước 7 sang hướng C thì máy chọn quan hệ pháp lý, trái BRD.

## Evidence and references

[1] `docs/ai2/AI2-DOC-02-brd.vi.md:9` | repo | 2026-09-20 | VERIFIED
[2] `plans/reports/ai2-five-slice-brainstorm-260927.md:17-47` | repo | 2026-09-27 | VERIFIED
[3] `docs/decisions.md:12-14` | repo | 2026-09-27 | VERIFIED
[4] `backend/src/contract_intelligence/worker.py:467-479` | repo | 2026-09-28 | VERIFIED
[5] `ai-service/app/pipeline/idp.py:65-94` | repo | 2026-09-28 | VERIFIED
[6] `ai-service/app/pipeline/fact.py:83-128` | repo | 2026-09-28 | VERIFIED
[7] `ai-service/app/pipeline/grounding.py:16-18` và `:177-187` | repo | 2026-09-28 | VERIFIED
[8] `ai-service/app/pipeline/compare.py:48` | repo | 2026-09-28 | VERIFIED
[9] `ai-service/tests/test_gap_as_note.py:12-48` | repo | 2026-09-28 | VERIFIED (đọc assert; không chạy lại pytest trong lượt này)
[10] `ai-service/tests/test_l0.py:369-387` | repo | 2026-09-28 | VERIFIED (đọc assert)

## Open questions

- [ASSUMED] Hồ sơ `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` thật sự không chứa chữ “Phụ lục 01” ở thân. Não trạng này lấy từ báo cáo brainstorm, chưa đọc lại OCR trong lượt này. Muốn chốt: đọc dòng OCR trang thân của dossier đó.
- [PRIOR] Ba test khóa cặp và grounding đã `3 passed` ở lượt research trước. Lượt này không chạy lại.
