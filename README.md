# Contract Intelligence

Hệ thống **OCR / IDP (Intelligent Document Processing)** xử lý hợp đồng thương mại tự động: trích xuất điều khoản, phát hiện xung đột giữa các điều khoản, và hỗ trợ review bán tự động (Human-in-the-Loop).

---

## 📁 Cấu trúc monorepo

```
contract-intelligence/
├── backend/        # Java Spring Boot — REST API, Clean Architecture + DDD
├── frontend/       # Web UI cho reviewer / operator (Node/React/Vue — sẽ chốt sau)
├── ai-service/     # Python service cho OCR / IDP / LLM extraction (nếu tách riêng)
├── docs/           # Tài liệu sản phẩm & kỹ thuật (Product Vision, Architecture, API Spec)
└── README.md       # File này
```

### Vai trò từng thư mục

| Thư mục | Mục đích | Công nghệ dự kiến |
|---|---|---|
| `backend/` | API server, xử lý nghiệp vụ chính, lưu trữ, quản lý luồng review | Java 17, Spring Boot 3.x, PostgreSQL, Flyway |
| `frontend/` | Giao diện upload hợp đồng, review điều khoản, xử lý conflict | Node.js (React hoặc Vue — chưa chốt) |
| `ai-service/` | Worker OCR/IDP/LLM, tách riêng để scale độc lập với backend | Python (FastAPI / Celery worker) |
| `docs/` | Product vision, system design, database schema, API spec, ADRs | Markdown + OpenAPI YAML |

> **Lưu ý:** `ai-service/` là *tuỳ chọn*. Phiên bản đầu có thể chạy OCR/IDP như một adapter trong `backend/` (gọi external service). Khi cần scale/đổi model độc lập, tách ra thư mục riêng.

---

## 🌿 Quy ước branch

Dùng mô hình **trunk-based + feature branch** đơn giản:

```
main                          # nhánh chính, luôn deployable
feature/<phần>-<tên-task>     # ví dụ:
feat/<phần>-<tên-task>        #   feature/backend-upload-api
hotfix/<tên-task>             #   feat/frontend-clause-review
release/<version>             #   hotfix/fix-flyway-migration
                              #   release/v0.1.0
```

### Đặt tên chi tiết

| Prefix | Ý nghĩa | Ví dụ |
|---|---|---|
| `feature/backend-*` | Tính năng mới ở backend | `feature/backend-upload-api` |
| `feature/frontend-*` | Tính năng mới ở frontend | `feature/frontend-clause-editor` |
| `feature/ai-*` | Tính năng mới ở ai-service | `feature/ai-clause-extractor` |
| `feature/docs-*` | Cập nhật tài liệu | `feature/docs-api-spec-v2` |
| `feat/*` | Alias ngắn cho `feature/*` | `feat/backend-conflict-detection` |
| `hotfix/*` | Sửa bug khẩn cấp trên main | `hotfix/fix-auth-token-expiry` |
| `release/*` | Chuẩn bị bản phát hành | `release/v0.1.0` |

### Quy tắc
- Tên branch dùng **kebab-case**, không viết hoa, không dấu.
- Mỗi branch tương ứng **một PR**.
- PR vào `main` cần ít nhất **1 reviewer**; squash merge khi approved.
- Xoá branch sau khi merge.

---

## 🚀 Bắt đầu nhanh

> Từng thư mục con sẽ có `README.md` riêng hướng dẫn cụ thể khi được generate.

```bash
# Clone repo
git clone <repo-url>
cd contract-intelligence

# Mở backend
cd backend && ./mvnw spring-boot:run

# Mở frontend (sau khi generate)
cd ../frontend && npm install && npm run dev

# Mở ai-service (sau khi generate)
cd ../ai-service && python -m venv venv && source venv/bin/activate && pip install -r requirements.txt
```

---

## 📚 Tài liệu

Xem thư mục [`docs/`](./docs/):

- `DOC-01-product-vision.md` — Tầm nhìn sản phẩm, vấn đề, đối tượng người dùng
- `DOC-04-architecture.md` — System design, database schema, ADRs
- `DOC-05-api-spec.yaml` — OpenAPI 3.0 spec cho REST API

---

## 👥 Team & Trách nhiệm

| Thư mục | Phụ trách |
|---|---|
| `backend/` | Backend Engineer |
| `frontend/` | Frontend Engineer |
| `ai-service/` | AI Engineer |
| `docs/` | Toàn team review & cập nhật |

---

## 📄 License

Internal / Proprietary — chưa public license.
