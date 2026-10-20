# DOC-10 · Báo cáo sửa backend (24/09–27/09/2026)

> **Contract Intelligence** — Những chỗ backend đã có sẵn bị sửa từ 24/09 đến 27/09/2026. File thêm mới không nằm trong báo cáo này.

---

## 0. Thông tin tài liệu

| Trường | Nội dung |
|---|---|
| Mã tài liệu | DOC-10 — Báo cáo sửa backend |
| Phạm vi | File đã có trong `backend/src` bị sửa trên nhánh `feature/code-full` |
| Khoảng thời gian | 24/09/2026 – 27/09/2026 |
| Ngày viết | 28/09/2026 |
| Người sửa | Trần Thị Kiều Trang · Nguyễn Đức Dũng · Trần Văn Dũng |

---

## 1. Trần Thị Kiều Trang

### 24/9 — `0344691` — Nối bản 1 cho frontend

Để màn tổng quan và hồ sơ chạy được, và có API quyền truy cập cùng tiến độ OCR.

- `users.py`: ghi nhật ký mời, đổi vai trò, khóa, mở khóa, gửi lại lời mời.
- `contract_router.py` và `contract_service.py`: chạy lại OCR, xóa hồ sơ hai bước, cập nhật quyền xem.
- `settings.py`: thêm URL Keycloak nội bộ trong Docker, tách khỏi issuer public.
- `logging.py`: tắt màu log trên Windows khi không có colorama.

### 24/9 — `fecb329` — Giữ cây điều khoản đúng bản 1

AI1 trả `parent_id` là id trong snapshot, không phải id trong database, nên cây điều khoản bị mất cha.

- `ai1_adapter.py`, `schemas.py`, `persistence.py`: map `source_id` sang id dòng rồi gắn `parent_id` trước khi ghi.

### 24/9 — `bb88c5f` — Nhật ký theo email và tải PDF trích dẫn

Màn hoạt động cần hiện email người làm, và file trích dẫn nằm trên object storage.

- `activity_feed.py`: actor chuyển từ tên hiển thị sang email, thêm sự kiện xóa hồ sơ.
- `users.py`: nhật ký admin ghi email.
- `contract_service.py`: file `s3://` tải bằng `download_object`.
- `contract_router.py`: ghi nhật ký khi chạy lại OCR.

### 24/9 — `32c1871` — Cho CI đọc hoạt động và tài liệu được

Test không có database, SQLite trả giờ không có múi giờ, object storage có thể không có file.

- `activity_feed.py`: giờ feed là UTC, bỏ hồ sơ đã xóa khỏi danh sách tạo mới.
- `contract_router.py`: không ghi nhật ký khi chưa gắn database.
- `contract_service.py`: file không thấy thì trả 404.

### 24/9 — `4848204` — Mail chia sẻ và chỉ người còn quyền mới xem được

Người được mời cần mail đặt mật khẩu, người đã có tài khoản cần mail mở hồ sơ, và danh sách phải ẩn quyền đã thu hồi.

- `contract_router.py`: mail Keycloak trước, SMTP sau, chặn đọc khi quyền bị thu.
- `repository_impl.py`: lọc danh sách theo chủ hồ sơ hoặc quyền chia sẻ còn hiệu lực.
- `keycloak_admin.py`: gửi mail đăng nhập khi chia sẻ.
- `dossier_deletion_service.py`: commit trước khi xóa file nền.

### 25/9 — `2f6052c` — Thẩm định điều khoản, trích dẫn và hoạt động trong cùng một luồng

Người thẩm định cần tìm hồ sơ, mở điều khoản được trích, và xem hoạt động của chính mình.

- `review_full_router.py`: thêm `GET`/`POST` thẩm định điều khoản.
- `activity_feed.py` và `admin_overview.py`: Operator và Reviewer xem được feed, nhưng chỉ thấy việc của mình. Admin xem cả tenant.
- `settings.py`: timeout và cờ gọi AI2 cho ô tìm hồ sơ.
- `contract_service.py`: commit trước khi trả response, xác nhận manifest đã tải mà không đổi trạng thái OCR.
- `repository_impl.py`: khớp quyền chia sẻ theo email, không chỉ theo id.

### 27/9 — `a9b0e5b` — So sánh hợp đồng với phụ lục vừa tải

Số liệu lệch giữa thân hợp đồng và phụ lục cần thành finding có trích dẫn trên cả hai tài liệu, và màn xung đột chỉ hiện lần chạy mới nhất.

- `persistence.py`: context finding chỉ giữ khi có bằng chứng trên ít nhất hai tài liệu, mỗi phía trỏ citation thật, ghi thêm `run_id`.
- `conflict` `repository_impl.py`: ẩn finding của lần chạy cũ, gắn quote và bbox vào từng phía.

### 27/9 — `5e8d2c6` — Hiện tên người thẩm định trên cây điều khoản

Hai màn cần cùng một dòng thời gian theo vị trí, và cần tên cùng email người thẩm định.

- `review_full_router.py`: thêm `GET`/`POST` `/findings/{id}/review`.
- `review_service.py` và DTO: trạng thái, lịch sử, và thẩm định cũ của lần phân tích trước.
- `conflict` `repository_impl.py`: lấy lượt thẩm định mới nhất, join ra tên và email.
- `auth_router.py`: lần gọi profile đầu tiên tạo dòng `app_user` để join được tên.

---

## 2. Nguyễn Đức Dũng

### 25/9 — `4c803b6` — OCR benchmark

`ai1_adapter.py`, kèm test `test_ai1_adapter.py`.

Phần chuyển snapshot AI1 sang schema v3 cũ không đưa dòng tiêu đề của bảng vào. Nó còn đánh dấu nhầm dòng dữ liệu đầu tiên là tiêu đề, nên nội dung OCR thật bị coi như tiêu đề.

Sau khi sửa:

- Tiêu đề thành dòng 0, với bbox chia đều trong khung bảng.
- Các dòng dữ liệu lùi xuống một dòng và đều có `is_header=False`.
- `rows_count` và `cols_count` đã tính cả dòng tiêu đề.

### 27/9 02:21 — `82c2027` — Sửa CI

- `contract_router.py` (API search hồ sơ): mỗi hit trả thêm `node_id`, `citation_id`, `breadcrumb`, `validation_status`. Khi AI2 không trả `page` thì lấy trang đầu trong `page_range`. Gửi rõ `policy_flags: {"egress_allowed": False}` sang AI2.
- `persistence.py`: tách biến `metadata` ra trước khi kiểm tra kiểu để mypy qua. Hành vi không đổi.
- `test_contract_router.py`: 2 test search cho dossier có `created_by`, nên không còn bị ACL trả 403. Test so với dạng trả về thật (`reasoning_trace`, `state: INSUFFICIENT_EVIDENCE`) thay vì field `notes` đã không còn.

### 27/9 02:22 — `96bedfa` — Chỉ chạy ruff format, không đổi logic

- `activity_feed.py`
- `conflict` `repository_impl.py`
- `contract` `repository_impl.py`

Mỗi file chỉ gộp một biểu thức nhiều dòng thành một dòng.

---

## 3. Trần Văn Dũng

### 24/9 — `eea49d6` — Hỏi AI2 đúng snapshot vừa OCR

Ô tìm hồ sơ gửi câu hỏi mà không kèm digest thì AI2 không mở được snapshot vừa chạy.

- `dossiers.py`: payload query thêm `snapshot_digest` lấy từ checksum hồ sơ, `query_contract_version`, `tenant_id` và `actor_id`.
- `ai_adapters.py`: thêm gửi job AI2 và poll kết quả có chữ ký HMAC. `query_ai2` gọi theo hợp đồng `ai2.query.v1`.

### 24/9 — `44930a0` — Search trả được chỗ trích, và xác nhận manifest thì AI2 được chạy

Hit tìm kiếm trước đó chỉ có chữ và số trang. Worker không biết manifest đã xác nhận.

- `contract_router.py`: hit giữ `source_file_id`, `line_id`, bbox và đọc `text_span`. Search gửi digest snapshot. Xác nhận manifest thì publish `dossier.manifest.confirmed`.
- `contract_service.py`: danh sách hồ sơ chỉ gửi `viewer_id` khi đang lọc theo người xem, để test cũ không gãy.
- `repository_impl.py`: map checksum hồ sơ. Câu SQL quyền chia sẻ chạy được cả SQLite và Postgres.

### 25/9 — `923d6de` — Nối đủ đường AI1 sang AI2

OCR xong và manifest đã xác nhận thì backend phải tự gửi AI2, rồi ghi fact và finding về database.

- `worker.py`: sau OCR, `_run_ai2_if_ready` chỉ chạy khi manifest đã confirmed và lần chạy chưa có kết quả AI2.
- `persistence.py`: ghi kết quả AI2 thành fact và finding mà màn đối soát đọc được.
- `schemas.py`: thêm trường wire cho handoff AI2.
- `client.py`: client gọi AI2 theo base URL và timeout trong cấu hình.
- `ai1_adapter.py`: snapshot AI1 giữ `source_id` và `parent_source_id` để còn map cha con.
- `settings.py`: topic Kafka AI2, secret HMAC, issuer và audience.
- `dossiers.py`: API hồ sơ đi cùng hợp đồng query mới.
- `contract_router.py`: search dùng payload query đã có digest.
- `contract_service.py`: tạo hồ sơ và manifest khớp đường AI2.
- `dossier.py`: hồ sơ mang checksum làm digest snapshot.
- `main.py`: gắn consumer và router của đường AI2.
- extraction ORM và repository: lưu run và kết quả để worker khỏi gửi AI2 lần nữa.
- `approval_router.py`, `review_full_router.py`, `dependencies.py`, `dependencies_approval.py`: cổng review và approval dùng chung dependency đã khóa quyền.

### 25/9 — `dcb7917` — Hết lỗi kiểu để CI và handoff AI2 chạy lại

Biến trùng tên và thiếu kiểu làm mypy và pytest đỏ. Không đổi luật nghiệp vụ.

- `settings.py`: thêm `ai2_wire_enabled` và số lần poll IDP.
- `repository_impl.py`: khai báo kiểu cho câu SQL chia sẻ.
- `contract_router.py`: xuống dòng chỗ map trạng thái search, cùng bộ trạng thái như trước.
- `ai_adapters.py`: adapter HTTP AI2 khớp chữ ký envelope.
- `ai1_adapter.py`: đổi tên biến `source_id` để không đè biến ngoài.
- `canonical_processing.py`: tách biến `engine` ra trước khi kiểm tra kiểu.
- `worker.py`: kiểm tra tài liệu có `blob_uri` trước khi tạo URL, và đổi tên biến lỗi cho mypy.
