# Ghép dòng OCR bị ngắt thành một node đoạn văn

Ngày: 2026-10-16 · Nhánh: `feature/ai2-contract-graph` · Nguồn: `plans/reports/ai2-quality-review-261016-1502-seeded-defect-gate-report.md` mục 5.1

## Vấn đề

`ai1_snapshot_adapter._line_nodes` tạo một `StructuralNode` cho mỗi dòng OCR. Điều khoản xuống dòng bị cắt: "4.1. … đã bao gồm" + node mồ côi "thuế giá trị gia tăng.", "Điều chỉnh khoản 2 Điều 5 … 10 ngày kể" + "từ ngày nhận được hóa đơn…". Frame, ứng viên pairs và classifier chỉ thấy nửa câu, nên thay đổi 07 → 10 ngày không tới bước review.

## Thiết kế

Ghép ngay trong `_line_nodes`, trong phạm vi một trang. Dòng hiện tại được nối vào node văn bản trước đó khi **đủ cả bốn** điều kiện:

1. Node trước là CLAUSE/UNNUMBERED_BLOCK dựng từ dòng liền trước (không phải FIELD/labelled fact, không có dòng bị `consumed` ở giữa).
2. Dòng trước **không** kết thúc bằng dấu câu kết thúc (`. ; : ! ? …`, bỏ qua ngoặc/nháy đóng).
3. Dòng trước "đầy dòng": độ dài ≥ 60% dòng dài nhất trang; nếu có hình học thì cạnh phải ≥ 85% cạnh phải lớn nhất. Điều này chặn tiêu đề ngắn và ô bảng ("1. Bảng giá hạng mục" + "Hạng mục").
4. Dòng hiện tại **không** mở khối mới: số thứ tự (`1.`, `2.1.`, `a)`, `-`), từ khóa cấu trúc (Điều/Chương/Mục/Phần/Phụ lục/Khoản/Điểm), dòng toàn chữ hoa, "Trang N", và không phải labelled fact.

Node ghép giữ `node_id` và `order` của dòng đầu. `text`/`raw_label` = các dòng nối bằng `\n` (vẫn là chuỗi con chính xác của `page.text`, nên citation qua `_span_for_line_ids` không đổi). `source_line_ids` gồm mọi dòng, `bbox` là hợp của các bbox.

## Hệ quả và rủi ro

- `clause_compare._build_outline` đang bỏ qua node nhiều dòng (để tránh node dự phòng cả trang `page_N_text`). Sửa thành: map mọi dòng của node `line:*`, vẫn bỏ qua node trang.
- Node id của các dòng nối tiếp (vốn là node mồ côi) biến mất. Golden `idp_flag_off_golden.json` / `idp_graph_on_golden.json` sẽ đổi và được chụp lại bằng `scripts/capture_idp_golden.py` sau khi đã đọc diff.
- Không ghép qua ranh giới trang hay file (ghi nhận là giới hạn).
- Dữ liệu đã lưu không bị migrate. Hồ sơ cũ chỉ đổi khi reprocess/reindex.

## Kiểm chứng

- Unit test trên `adapt_be_ai2_processing_request`: ghép đúng 3 ca của HD-TEST; không ghép tiêu đề ngắn, ô bảng, dòng kết thúc bằng dấu chấm, dòng mở bằng số thứ tự hay chữ hoa; citation của node ghép `VALID`.
- Bộ seeded: 4 xfail (`test_wrapped_clause_is_one_node`, `test_planted_value_change_reaches_review`) phải XPASS rồi bỏ đánh dấu.
- Toàn bộ test ai-service, golden chụp lại có diff đã đọc, và live gate `run_live`.

## Kết quả (2026-10-16)

- Đã cài trong `_line_nodes` + `_continues_previous` (`app/pipeline/ai1_snapshot_adapter.py`), `clause_compare._build_outline` map mọi dòng của node `line:*`.
- Bổ sung so với thiết kế, đều có test: ngưỡng độ dài tuyệt đối 45 ký tự (trang chỉ toàn dòng ngắn đã ghép nhầm "Điều 1. Các bên" + "Bên A thanh toán."); hàng bảng `| … |` không bao giờ được nối vào hay nối thêm (kiểm trên OCR thật: 10–11 hàng bảng từng bị gộp vào một node); dòng labelled (FIELD) cũng nhận phần đuôi bị ngắt, trừ trường hợp tổng tiền lấy từ dòng kế tiếp.
- Kiểm trên request thật trong DB local (offline): 5 hồ sơ HD-TEST có khoảng 21 lần ghép mỗi hồ sơ, tất cả đúng; hồ sơ có bảng có 0 lần ghép (không có dòng nào bị ngắt).
- Golden không đổi; `test_hd_gold.py` và `test_structure_reconstruction.py` pass 6/6; toàn bộ ai-service 1907 pass (chỉ còn `test_a8` fail do môi trường).
- Bộ seeded: 4 xfail đều XPASS rồi được gỡ đánh dấu; 29/29 xanh. Trên OCR thật: 5.2 ↔ PL02 §1 = `COMPARABLE_DIFFERENCE slots_differ:deadline`.
- Live gate ×3: CONFLICT/DUPLICATE/REFERENCE ×2 đều 3/3; cạnh bị cấm = 0.

## Ghép qua ranh giới trang: đo đạc và phương án (chưa chốt)

Đo trên toàn bộ request lưu trong DB local (chỉ đọc; 11 tài liệu khác nhau, 434 trang, 423 ranh giới trang), dùng đúng tiêu chí `_continues_previous` và bỏ qua chân trang/đầu trang:

- Dòng bị ngắt **trong** trang: 1013 (991 sau khi chặn dòng toàn chữ hoa ở phía trước). Dòng bị ngắt **qua** trang: 5, tức ≈ 1,2% số ranh giới trang và ≈ 0,5% tổng số dòng bị ngắt; cả 5 đều là ca thật (3 câu khác nhau, lặp lại do cùng tài liệu xuất hiện ở nhiều hồ sơ). Lần đo đầu ra 1046 và 6, vì hàng bảng ngăn bằng tab và dòng mở bằng số La Mã "IV.1." bị ghép nhầm; lỗi này đã sửa, có test.
- Một ca thật đổi nghĩa giá trị: "thời hạn: 6 ngày" ‖ "lịch …" (6 ngày *lịch*). Ca cắt ngang qua trang làm sai giá trị chứ không chỉ cụt chữ.
- Corpus nhỏ và phần lớn là tài liệu kiểm thử: tỷ lệ chỉ mang tính chỉ báo.

Ràng buộc: giữa dòng cuối trang N và dòng đầu trang N+1 luôn có chân trang/đầu trang, nên quote của cả câu **không phải một đoạn liền** trong toàn văn. `Citation` của AI2 chỉ có một `page_revision_id`; `citation_guard` của Backend so khớp một span.

| Phương án | Cách làm | Ảnh hưởng |
|---|---|---|
| A. Giữ nguyên, chỉ báo | Phát hiện câu bị ngắt qua trang và gắn issue `CLAUSE_CONTINUES_ON_NEXT_PAGE` để người duyệt biết | Không đổi hợp đồng; giá trị ở phần sau trang vẫn có thể sai, nhưng được hiện ra |
| B. Citation nhiều đoạn (đúng chuẩn) | Node logic = phần trang N + phần trang N+1; `Citation.segments[]` mỗi đoạn một trang, mỗi đoạn là chuỗi con chính xác của trang đó; `verify` và `citation_guard` kiểm từng đoạn; UI tô sáng nhiều đoạn | Đổi hợp đồng dữ liệu AI2→BE→UI, có migration cho citation đã lưu; khối lượng lớn nhất |
| C. Hai evidence cho một frame | Giữ 2 node theo trang để citation đúng; frame/slot ở câu bị ngắt mang 2 `Evidence` (đã có sẵn kiểu tuple); pairs dùng text logic | Không đổi wire; chạm frame extraction và cách pairs dựng citation; pairs chỉ cite được một node |
| D. Citation neo trang đầu | Node mang text đầy đủ, citation chỉ phủ phần trên trang N | Rẻ nhưng yếu: phần giá trị nằm ở trang sau không có bằng chứng tô sáng. Không khuyến nghị |

Đã làm, áp dụng cho mọi phương án: `citation_guard.reconstruct_ocr_span` chèn lại `\n` cho khoảng trống 1 ký tự giữa hai dòng. Trước đó **mọi quote nhiều dòng**, kể cả node đoạn văn trong trang, đều bị Backend từ chối (`quote_mismatch`) và fact bị đẩy sang người duyệt.

## Quyết định: phương án A (2026-10-16)

Đã cài `_cross_page_wrap_issues` (`ai1_snapshot_adapter.py`), gọi trong `adapt_snapshot` sau khi đã có đủ các trang của một tài liệu:

- Mỗi cặp trang liền nhau: node nội dung cuối trang N và node nội dung đầu trang N+1 (bỏ dòng lặp trên ≥ 2 trang, dòng toàn chữ hoa, "Trang N"), xét bằng đúng `_continues_previous`.
- Khớp thì phát `CLAUSE_CONTINUES_ON_NEXT_PAGE`: `NEEDS_REVIEW`, `stage=STRUCTURE`, `document_id`, `location="page N->N+1"`, `evidence_refs=[node cuối trang N, node đầu trang N+1]`. **Không ghép node**, nên citation giữ nguyên một trang.
- Kiểm trên request thật (offline): 5 issue cho đúng 5 ca thật (3 câu), không báo nhầm.

Lỗi phát hiện thêm và đã sửa (có test): dòng toàn chữ hoa ở **phía trước** (đầu trang "TÀI LIỆU MẪU…") từng nhận câu đầu trang làm phần nối tiếp. Số lần ghép trong trang sau khi sửa: 991 (trước: 1013).

Kiểm chứng: `tests/test_paragraph_nodes.py` 48 pass (cùng seeded/structure/clause_compare); toàn bộ ai-service 1915 pass (chỉ `test_a8` fail do môi trường).

Còn mở: phương án B (citation nhiều đoạn) khi có số liệu trên tài liệu khách hàng thật. UI/Backend hiển thị issue này như mọi handoff issue khác; chưa có thao tác "xem hai nửa" riêng.
