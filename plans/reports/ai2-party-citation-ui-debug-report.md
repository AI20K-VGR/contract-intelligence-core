# Báo cáo debug/fix: hỏi thông tin Bên A và mở citation

## Hiện tượng

Với hồ sơ `dos_01M38T3PD2Z45CJXGS6FQGKSWX`, câu hỏi `Thông tin bên A` trả về một đoạn điều khoản như tên/alias của Bên A. Danh sách nguồn chỉ là chuỗi `line:*`, không có thao tác mở nguồn trên UI.

## Nguyên nhân đã xác nhận

1. `assemble_party()` dùng các câu nhắc vai trò chung để suy ra tên pháp nhân.
2. Backend projection `_hits_from_ai2()` làm rơi `source_file_id`, `line_ids` và `bbox`.
3. Frontend hiển thị hit tìm kiếm bằng text thường, không tạo citation action.
4. Endpoint search gửi `snapshot_digest` từ `dossier.checksum`; trường này chỉ có sau approval, trong khi AI2 cần digest của canonical processing request. Vì vậy các hồ sơ đã chạy AI2 vẫn có thể bị trả `INSUFFICIENT_EVIDENCE`.

## Thay đổi

- Chỉ field `party_*` explicit hoặc câu khai báo có nhãn rõ như `Bên A được ghi: Công ty ...` mới được dùng để dựng tên/alias; câu nhắc trong clause chỉ là evidence.
- Câu trả lời party card chỉ hiển thị số vị trí có citation, không đẩy raw line ID vào câu trả lời.
- Giữ source file, line ID, page và bbox qua backend/frontend.
- Hit hợp lệ trên đúng document/page trở thành button; click mở citation pane và vùng highlight trên PDF.
- Lưu `ai2_snapshot_digest` sau khi AI2 processing thành công; query dùng digest này và chỉ fallback về approval checksum.
- Backfill digest cho các dossier đã xử lý thành công trong database local hiện tại.

## Kiểm chứng

- Live search hồ sơ `dos_01M38T3PD2Z45CJXGS6FQGKSWX`: HTTP 200, `connected=true`, 12 hit có source metadata; câu trả lời ghi `Tên/alias: (không tách được tên)` và MST `0399999999`.
- Backend: `26 passed` (`test_contract_router.py`, `test_worker_pipeline_run.py`).
- AI2 reasoning: `25 passed, 3 skipped`.
- Frontend: `npm run build` thành công.
- Live smoke test các nhóm hỏi Bên A, giá trị hợp đồng, thời hạn thanh toán và mức phạt: các hit có nguồn đều giữ đủ metadata định vị; câu hỏi không có structured evidence vẫn trả trạng thái thiếu bằng chứng thay vì bịa giá trị.
- `git diff --check`: không có lỗi diff; chỉ còn cảnh báo chuyển đổi LF/CRLF của Git.
