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

## 🌿 Quy ước làm việc trên repo

Quy tắc đầy đủ (tiếng Anh) ở [CONTRIBUTING.md](CONTRIBUTING.md); GitHub ruleset và check `pr-guard` cưỡng chế các điểm chính:

```
feature branch  ──PR──▶  develop  ──release PR──▶  main
(feature/…, feat/…)      2 approvals              2 approvals, chỉ squash merge
```

- `develop` là nhánh mặc định; **không ai push thẳng** vào `develop` hoặc `main`.
- Mỗi PR cần **2 approval từ đồng đội** (không tự approve; push mới làm mất approval cũ), resolve hết
  review thread, `pr-guard` xanh.
- `main` chỉ nhận PR từ `develop`, `release/*` hoặc `hotfix/*`.
- Tên nhánh: `^(feat|feature|fix|docs|chore|refactor|test|hotfix|release)/[a-z0-9._-]+$`,
  ví dụ `feature/backend-upload-api`, `hotfix/fix-flyway-migration`, `release/v0.1.0`.
- Tiêu đề PR: `<type>(<scope>): <summary>`, scope là `frontend | backend | ai | docs | infra | repo`.
- **Không commit hợp đồng, bản scan, file nén** (thật hay test) vào repo; `pr-guard` chặn các file
  `.pdf .docx .tif .jpg .png .zip …` ngoài `docs/assets/`. Dữ liệu mẫu để trên OneDrive, đọc qua đường dẫn ngoài repo.

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
