# Báo cáo lỗi AI2 trả về thiếu snapshot/citation

## Triệu chứng

UI trả về `AI2 chưa nhận được snapshot/citation có thẩm quyền cho hồ sơ này` cho phần lớn hồ sơ.

## Bằng chứng tái hiện

- `POST /api/v1/dossiers/{id}/query` chỉ tìm record trong `InMemorySnapshotStore` của AI2.
- AI2 lưu job thành công trong `/app/data/ai2/jobs.sqlite`, nhưng restart container làm mất toàn bộ record trong RAM.
- Kiểm tra 6 hồ sơ cho thấy 3 hồ sơ từng ở `manifest=pending`; 2 hồ sơ có job `SUCCEEDED` nhưng snapshot không còn trong RAM.
- Khi rebuild AI2, SQLite vẫn giữ đầy đủ request có `snapshots`; dữ liệu có thể dùng để khôi phục.
- Một số retry OCR cũ còn đụng trigger append-only vì backend cố xoá `page`, `clause_node` hoặc `doc_table` trước khi ghi lại cùng `document_id`.

## Nguyên nhân gốc

1. Kho canonical phục vụ query của AI2 là in-memory nhưng không được hydrate từ job store khi process khởi động lại.
2. Worker chỉ chạy AI2 sau khi manifest được xác nhận; các manifest pending bị chặn đúng theo policy.
3. Luồng retry OCR cũ không tương thích với các bảng evidence append-only.

## Thay đổi đã thực hiện

- Thêm `SQLiteJobStore.list_succeeded()` để đọc các job thành công theo thứ tự cập nhật.
- Thêm startup hydration trong `ai-service/app/api/main.py`; job hỏng bị bỏ qua có cảnh báo, không làm service chết.
- Thêm regression test cho hydration và danh sách job thành công.
- Worker backend nhận diện lỗi append-only, rollback phần persist bị từ chối nhưng vẫn dùng canonical snapshot đã nhận để chuyển tiếp AI2.
- Xác nhận các manifest pending của các hồ sơ còn lại và chạy lại OCR/AI2 trong phạm vi môi trường local.

## Kết quả kiểm tra

- AI2: `14 passed` cho `tests/test_api.py tests/test_job_store.py`.
- Backend worker pipeline: `2 passed` cho `tests/unit/test_worker_pipeline_run.py`.
- Sau restart AI2, các job cũ được hydrate và truy vấn có citation trở lại.
- Một hồ sơ còn không thể OCR lại vì source blob trong storage trả `HTTP 404`; đây là lỗi dữ liệu file nguồn, không phải lỗi snapshot store hay API key.
