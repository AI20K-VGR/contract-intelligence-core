# Tài liệu bàn giao

Bộ tài liệu bàn giao dự án Contract Intelligence. Số thứ tự theo danh mục bàn giao của nhóm. Markdown trong repo là bản gốc; bản PDF xuất ra để nộp, không sửa trực tiếp (xem `docs/governance/DOCUMENT-GOVERNANCE.md`).

| STT | Tài liệu | Người phụ trách | Tệp | Trạng thái |
|---|---|---|---|---|
| 1 | Kiến trúc hệ thống | Trang | | Chưa có trong thư mục này |
| 2 | Thiết kế Cơ sở dữ liệu | Chương | [02-thiet-ke-csdl.md](02-thiet-ke-csdl.md), phụ lục [02b](02b-csdl-chi-tiet.md) | Xong (schema backend `v25`, AI2 `0009`) |
| 3 | Tài liệu API | Chương | [03-tai-lieu-api.md](03-tai-lieu-api.md), phụ lục [03b](03b-api-endpoints.md), [03c](03c-openapi-backend.json) | Xong (API `v4.1.0`) |
| 4 | Cấu trúc thư mục & Quy chuẩn Code | Văn Dũng | | Chưa có trong thư mục này |
| 5 | Yêu cầu hệ thống | Đức Dũng | | Chưa có trong thư mục này |
| 6 | Hướng dẫn cài đặt Local | Chương | [06-huong-dan-cai-dat-local.md](06-huong-dan-cai-dat-local.md) | Xong |
| 7 | Hướng dẫn Deploy Server | Chương | [07-huong-dan-deploy.md](07-huong-dan-deploy.md) | Đang viết |
| 8 | Tài liệu cấu hình (biến môi trường) | Văn Dũng | | Chưa có trong thư mục này |
| 9 | Kịch bản kiểm thử | Đức Dũng | | Chưa có trong thư mục này |
| 10 | Hướng dẫn sử dụng | Trang | | Chưa có trong thư mục này |
| 11 | Tài liệu Quản trị viên | Chương | [11-admin-guide.md](11-admin-guide.md) | Đang viết |
| 12 | Danh sách tài khoản | Chương | [12-danh-sach-tai-khoan.md](12-danh-sach-tai-khoan.md) | Đang viết |
| 13 | Thông tin Bản quyền | Trang | | Chưa có trong thư mục này |
| 14 | Biên bản nghiệm thu & Bàn giao | Trang | | Chưa có trong thư mục này |

## Tệp sinh tự động

Không sửa tay các tệp này; sửa code hoặc migration rồi chạy lại script:

| Tệp | Script | Cách chạy |
|---|---|---|
| `02b-csdl-chi-tiet.md` | `backend/scripts/export_schema_doc.py` | Xem [02](02-thiet-ke-csdl.md) §6 |
| `03b-api-endpoints.md`, `03c-openapi-backend.json` | `backend/scripts/export_api_doc.py` | `cd backend && uv run python scripts/export_api_doc.py ../docs/ban-giao` |
