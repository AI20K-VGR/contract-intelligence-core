# Review PR #123 — fix(backend): cut per-dossier requests on the dossier list

Phạm vi: low-effort, đọc diff một lượt (bỏ qua các file test), không chạy test, không tạo worktree. Chưa đọc kỹ các comment đã có trên PR; trước khi đăng, cần đối chiếu để không trùng.

## Các phát hiện (xếp theo mức độ)

1. **[Medium] `backend/src/contract_intelligence/contract/infrastructure/persistence/job_repository_impl.py:31,43`**: `latest_by_dossiers` và `latest_for_dossier` ở đây `raise NotImplementedError`, nên che mất cài đặt mặc định của Protocol (vòng lặp gọi `list`). Nếu class này đang được inject ở đâu đó (stub, in-memory hay adapter thay thế), `GET /dossiers` và `_hydrate_latest_job` sẽ trả 500, trong khi trước PR vẫn chạy được qua `list`. Cách sửa: xoá hai override này để dùng default, hoặc xác nhận class này không bao giờ được wire.
2. **[Low] `backend/src/contract_intelligence/contract/infrastructure/persistence/repository_impl.py` (`document_summaries`, vòng lặp pages)**: `first_error` chỉ được gán khi `failed_pages == 0`. Giả sử trang lỗi đầu tiên có `ai1_page_status=FAILED` nhưng không có `error`, còn trang sau có `error`: `first_error` sẽ là `None`. Worker (`worker.py:1031`) thì lấy lỗi đầu tiên khác rỗng. Như vậy hai nơi lệch nhau và UI hiển thị "N trang lỗi" mà không có lý do. Cách sửa: `if error and ocr["first_error"] is None:`.
3. **[Low] `repository_impl.py` (`document_summaries`)**: khi hồ sơ không có tài liệu role CONTRACT, `contract_ocr` lấy tài liệu đầu tiên bất kể role (ví dụ phụ lục). Tên trường vì thế dễ gây hiểu nhầm. Cần xác nhận đây đúng là hành vi cũ của frontend; nếu đúng, ghi rõ trong DOC-05b.
4. **[Info] `shared/server_timing.py`**: listener gắn ở cấp class `Engine` toàn cục và `listen_for_queries` không bao giờ gỡ ra. Prod mặc định tắt (`compose.prod.yml` đặt `false`, `exposed` cũng cho ra tắt), nên rủi ro lộ thông tin thấp. Không chặn merge.

Những điểm đã kiểm tra và không thấy vấn đề: cả hai query batch (`document` và `page`) đều lọc `tenant_id`. `latest_by_dossiers` lọc `tenant_id`, và thứ tự `created_at desc, id desc` khớp với `list` (thêm tie-break `id`). ACL trên list tách theo `CITATION_READ` (counts) và `QUERY` (ocr). Cache ledger chỉ ghi nhớ khi bảng đã tồn tại từ trước, nên an toàn với rollback.

Chồng lấn với PR #125: diff của PR này không đụng `ai-service/` hay `frontend/src/components/ai2-graph`. Chưa kiểm tra xung đột ở `docs/DOC-05b` và `versioning.py` (bump `v3.3.0`); nếu #125 cũng bump contract version thì sẽ xung đột.

## Verdict

**Approve kèm điều kiện (nit)**: không có lỗi chặn merge nào chắc chắn. Phát hiện 1 cần tác giả xác nhận class trong `job_repository_impl.py` không được wire; nếu có được wire thì phải request changes.

## Bản nháp comment PR (tiếng Việt)

> Cảm ơn PR, hướng batch hoá `latest_by_dossiers` / `document_summaries` hợp lý, và các query đều có `tenant_id`. Còn vài điểm:
>
> 1. `job_repository_impl.py`: hai method `latest_by_dossiers` / `latest_for_dossier` đang `raise NotImplementedError`, nên che mất default của Protocol (fallback qua `list`). Nếu class này được dùng ở bất kỳ đâu thì `GET /dossiers` sẽ 500. Mình đề xuất xoá hai override để dùng default, hoặc bạn xác nhận giúp là class này không được wire.
> 2. `document_summaries`: `first_error` chỉ được gán khi `failed_pages == 0`. Nếu trang FAILED đầu tiên không có `error` thì lỗi của các trang sau bị bỏ qua, lệch với cách worker lấy lỗi khác rỗng đầu tiên. Gợi ý sửa: `if error and ocr["first_error"] is None`.
> 3. Khi hồ sơ không có tài liệu CONTRACT, `contract_ocr` đang lấy tài liệu đầu tiên (có thể là phụ lục). Nếu đó là chủ ý thì nhờ bạn ghi rõ trong DOC-05b.
> 4. Bump `__api_contract__` lên `v3.3.0` có thể xung đột với PR #125 nếu PR đó cũng bump version, cần thống nhất thứ tự merge.
