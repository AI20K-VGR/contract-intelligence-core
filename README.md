# Contract Intelligence

Hệ thống **OCR / IDP (Intelligent Document Processing)** xử lý hợp đồng thương mại tự động: trích xuất điều khoản, phát hiện xung đột giữa các điều khoản, và hỗ trợ review bán tự động (Human-in-the-Loop).

---

## 📁 Cấu trúc monorepo

```
contract-intelligence/
├── backend/        # Python 3.12 + FastAPI — REST API, Clean Architecture + DDD, orchestration
├── frontend/       # Web UI cho reviewer / operator (React + PDF viewer)
├── ai-service/     # Python HTTP service cho OCR / IDP (AI1/AI2), stateless, backend gọi qua HTTP
├── docs/           # Tài liệu sản phẩm & kỹ thuật (Product Vision, Architecture, API Spec)
└── README.md       # File này
```

### Vai trò từng thư mục

| Thư mục | Mục đích | Công nghệ dự kiến |
|---|---|---|
| `backend/` | Public API, domain, RBAC, persistence, task dispatcher gọi ai-service, luồng review | Python 3.12, FastAPI, SQLAlchemy 2 async + asyncpg, Alembic, PostgreSQL, MinIO |
| `frontend/` | Giao diện dossier/job list, evidence viewer, review điều khoản, xử lý conflict | React + PDF viewer |
| `ai-service/` | HTTP service OCR/layout (AI1) và IDP (AI2); stateless, không truy cập DB | Python 3.12, FastAPI, PaddleOCR/Tesseract baseline |
| `docs/` | Product vision, BRD, PRD, architecture, API spec, contracts, evaluation | Markdown + OpenAPI YAML + JSON Schema |

> **Quyết định kiến trúc (DOC-04 ADR-01/02/03, change record 2026-09-17):** Backend FastAPI sở hữu API, dữ liệu, task queue và điều phối; `ai-service` là HTTP service nội bộ được backend gọi theo mô hình push (`POST /jobs` + polling), không kết nối PostgreSQL. PostgreSQL là source of truth và task queue MVP; MinIO lưu PDF/render. Xem [DOC-04](docs/DOC-04-architecture.md).

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

# Hạ tầng local (PostgreSQL + MinIO) — profile local-baseline, xem DOC-04 §18.2
docker compose up -d postgres minio

# Mở backend (Python 3.12, FastAPI) — skeleton dùng uv + hatchling, xem backend/README.md
cd backend && pip install uv && uv sync --extra dev
uv run alembic upgrade head && uv run uvicorn contract_intelligence.main:app --reload --port 8000

# Mở ai-service (sau khi generate)
cd ../ai-service && python -m venv .venv && . .venv/bin/activate && pip install -r requirements.txt
uvicorn app.main:app --port 8100

# Mở frontend (sau khi generate)
cd ../frontend && npm install && npm run dev
```

---

## 📚 Tài liệu

Xem thư mục [`docs/`](./docs/):

- `DOC-01-product-vision.md` — Tầm nhìn sản phẩm, vấn đề, đối tượng người dùng
- `DOC-02-brd.md` — Business requirements, BR/NFR
- `DOC-03-prd.md` — Product requirements, acceptance, constraints
- `DOC-04-architecture.md` — System design, ADRs, state machines, change record (§22)
- `DOC-05-api-spec.yaml` — OpenAPI 3.0 spec cho REST API public
- `DOC-06-eval-report.md` — Evaluation protocol và report template
- `contracts/` — JSON Schema wire contracts và validation fixtures
- `DOCUMENT-GOVERNANCE.md` — authority, metadata, archive policy

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
