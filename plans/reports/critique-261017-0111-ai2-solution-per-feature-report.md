# Phản biện giải pháp AI2 theo từng tính năng

Ngày 2026-10-17. Đầu vào: `codebase-map-261017-0111-ai2-feature-flows-report.md`, các số đo seeded/live/production trong phiên 2026-10-16. Kết luận: **PASS** (đủ tốt cho tính năng), **PASS_WITH_RISK** (dùng được nhưng có rủi ro đã biết), **BLOCKED** (chưa đạt yêu cầu tính năng).

## Tóm tắt

| # | Tính năng | Kết luận | Lý do chính |
|---|---|---|---|
| 1 | OCR → node đoạn văn | PASS_WITH_RISK | Ghép trong trang đúng trên dữ liệu thật; câu bị ngắt qua trang chỉ được báo |
| 2 | Luồng 1 (sửa đổi tường minh) | PASS_WITH_RISK | Đúng trên mọi hồ sơ seeded; không so giá trị cũ → mới; dẫn chiếu có thể bị coi là sửa đổi |
| 3 | Luồng 2, sinh ứng viên | **BLOCKED (hồ sơ lớn)** / PASS (hồ sơ nhỏ) | Bùng nổ O(k²) làm job hồ sơ 202 trang không chạy xong |
| 4 | Luồng 2, classifier LLM | PASS_WITH_RISK | Mọi kỳ vọng live đạt; phủ tối đa 40 cặp; timeout ngắt quãng |
| 5 | Semantic frame và so sánh | PASS_WITH_RISK | Dev 42/42; bỏ qua phần cuối hồ sơ lớn; câu tham số dạng danh từ chưa so được |
| 6 | Budget / chi phí LLM | **BLOCKED (hồ sơ lớn)** | 20 lời gọi cố định, cạn ở mọi lượt; không co giãn |
| 7 | Citation | PASS_WITH_RISK | Toàn vẹn một trang và guard đã sửa; chưa đo tỉ lệ VALID thật |
| 8 | Query (hỏi đáp) | **Chưa đánh giá được** | Không có gold; vector recall "được tất hoặc mất tất" |
| 9 | Vận hành và quan sát | PASS | Log có tên tầng, quota fail-fast, `PARTIAL_*` trên trace |

## Chi tiết

### 1. OCR → node đoạn văn: PASS_WITH_RISK
- **Ổn:** 5 hồ sơ thật có khoảng 21 lần ghép mỗi hồ sơ, đều đúng; bảng `|`/tab, tiêu đề, dòng toàn chữ hoa không bị ghép; citation vẫn VALID.
- **Rủi ro:** câu bị ngắt qua trang (≈ 1,2% ranh giới trang) chỉ được báo, giá trị nằm ở trang sau vẫn có thể bị đọc sai ("6 ngày" ‖ "lịch"). Ngưỡng 45 ký tự và 60% là heuristic, chưa thử trên OCR có cột đôi hay khổ ngang.
- **Kịch bản chưa có trong gold:** văn bản hai cột; OCR không có bbox; dòng tiếng Anh xen lẫn.

### 2. Luồng 1: PASS_WITH_RISK
- **Ổn:** địa chỉ UNIQUE và không đoán đích; đã sửa lỗi điểm "a)" sau khoản "3.1.".
- **Rủi ro:** cạnh sửa đổi chỉ nối hai đầu mà **không so giá trị cũ → mới**, nên UI không hiện "07 → 10"; người duyệt phải tự đọc. Seed 001 có "từ chối nghiệm thu theo quy định tại khoản 1 Điều 6", câu dẫn chiếu nhưng vẫn bị coi là sửa đổi (lỗi đã thấy, chưa sửa). Câu giới hạn phạm vi ("Khoản 2 Điều 7 không áp dụng…") không thành cạnh luồng 1.
- **Kịch bản thiếu:** sửa đổi nhiều đích trong một câu; phụ lục sửa phụ lục; sửa đổi lần hai đè lần một.

### 3. Luồng 2, sinh ứng viên: BLOCKED với hồ sơ lớn
- **Bằng chứng:** hồ sơ `dos_01M5197DFQ…` (202 trang, 11.770 node, 11.653 node `UNNUMBERED_BLOCK`) có job thật `FAILED/WORKER_INTERRUPTED` sau 745 giây ở stage `contract_graph_pairs`. Đo offline: không xong trong 25 phút, ngay ở nguồn SAME_ARTICLE.
- **Nguyên nhân [ASSUMED, cần đo kích thước nhóm]:** SAME_ARTICLE/SAME_KEY ghép **mọi cặp trong nhóm** trước khi cắt top-K; nhóm hàng nghìn node cho ra hàng triệu cặp.
- **Yêu cầu tối thiểu:** giới hạn số cặp khi sinh (cửa sổ lân cận/chỉ cặp liền kề), checkpoint thời gian trong bước tất định, issue rõ ràng khi bị cắt.

### 4. Luồng 2, classifier: PASS_WITH_RISK
- **Ổn:** live trên 4 hồ sơ: mọi CONFLICT/DUPLICATE/REFERENCE kỳ vọng đều đạt, không có cạnh bị cấm; validator đã bỏ nhãn "1.1".
- **Rủi ro:** tối đa 5 × 8 = 40 cặp mỗi hồ sơ, nên ở hồ sơ lớn độ phủ chỉ vài phần trăm; 6 `LLM_TIMEOUT` mỗi 4 lượt đều ở `pairs` (batch 15–31 giây so với timeout 45 giây); bộ nhãn eval chỉ có 1 CONFLICT đã duyệt, nên **chưa đo được độ chính xác thống kê**.

### 5. Semantic: PASS_WITH_RISK
- **Ổn:** seeded dev 42/42; thay đổi 07→10 và 05→03 tới review; bẫy báo nhầm "05" ↔ "5" đạt.
- **Rủi ro:** `build_semantic_extension` duyệt **theo thứ tự tài liệu và `break`** ở 256 node / 32 KB, nên phụ lục cuối hồ sơ lớn không bao giờ có frame. Mỗi frame tốn một lời gọi LLM. Câu tham số dạng danh từ ("Thời gian giao hàng là…") chưa so được (held-out 20/21; quyết định A chưa chốt). Bộ từ vựng hành động hẹp (6 + ACCEPT).

### 6. Budget / chi phí: BLOCKED với hồ sơ lớn
- 20 lời gọi đặt cứng ở Backend (`canonical_processing.py:388`, schema `le=20`), dùng chung cho mọi tầng và cạn ở **mọi** lượt đã đo; thời gian thì đã co giãn theo số trang nhưng số lời gọi thì không. Token của semantic không được ghi lại, nên chi phí phải ước lượng.

### 7. Citation: PASS_WITH_RISK
- **Ổn:** quy tắc một trang và chuỗi con chính xác được giữ; guard Backend đã nhận quote nhiều dòng.
- **Rủi ro:** chưa đo tỉ lệ citation VALID và `citation_guard_rejected` trên hồ sơ thật sau khi ghép đoạn văn.

### 8. Query: chưa đánh giá được
- Khoảng 6.000 dòng trong `reasoning/*` mà không có gold seeded nào. Vector recall lập index cả hồ sơ trong budget 50.000 token và tắt hẳn khi vượt.

### 9. Vận hành: PASS
- `ai2.llm_call_failed operation=…`, `LLM_QUOTA_EXHAUSTED` dừng ngay, trace `PARTIAL_*`, issue câu bị ngắt qua trang.

## Ưu tiên đề xuất

1. **P0:** sửa bùng nổ cặp ứng viên (mục 3), vì hồ sơ lớn hiện không xử lý xong. Kèm hồ sơ seeded lớn tổng hợp để đo.
2. **P1:** semantic ưu tiên node trong cặp so sánh và gom nhiều frame vào một lời gọi (mục 5, 6), không đổi hợp đồng dữ liệu.
3. **P1:** chốt quyết định A (câu tham số) và chia budget theo tầng.
4. **P2:** luồng 1 hiện giá trị cũ → mới; sửa dẫn chiếu bị coi là sửa đổi.
5. **P2:** gold cho query và tỉ lệ citation VALID; mở rộng nhãn CONFLICT/DUPLICATE.
