# Contract Intelligence

Hệ thống **OCR / IDP (Intelligent Document Processing)** xử lý hợp đồng thương mại tự động: trích xuất điều khoản, phát hiện xung đột giữa các điều khoản, và hỗ trợ review bán tự động (Human-in-the-Loop).

---

## 📁 Cấu trúc monorepo

```
contract-intelligence-core/
├── backend/        # API + worker điều phối pipeline (Python, FastAPI, SQLAlchemy async)
├── frontend/       # Web UI cho reviewer / operator / admin (Vite + React + TypeScript)
├── ai-service/     # AI1 OCR worker (src/contract_ocr) + AI2 IDP service (app/)
├── ai1/            # Tài liệu bàn giao và contract của AI1
├── evals/          # Bộ đánh giá AI2 (golden set, card, corpus)
├── keycloak/       # Image Keycloak + realm cấu hình sẵn
├── infra/          # Cấu hình Prometheus, Grafana
├── deploy/         # Compose production, Caddy, script deploy
├── docs/           # Tài liệu sản phẩm & kỹ thuật, contract giữa các service
└── docker-compose.yml
```

### Vai trò và công nghệ

| Thư mục | Mục đích | Công nghệ |
|---|---|---|
| `backend/` | REST API, nghiệp vụ hồ sơ/hợp đồng, phân quyền, luồng review; worker điều phối OCR (AI1) và IDP (AI2) | Python 3.11, FastAPI, Uvicorn, SQLAlchemy 2 (async) + asyncpg, Alembic, Pydantic v2, aiokafka, MinIO/S3 (aioboto3), Keycloak (PyJWT, python-keycloak), structlog, OpenTelemetry, Prometheus; quản lý dependency bằng `uv` |
| `frontend/` | Upload hợp đồng, review điều khoản, xử lý conflict, chia sẻ hồ sơ, trang quản trị | Node 20+, Vite 7, React 19, TypeScript 5.9, React Router 7, Tailwind CSS 4, oidc-client-ts |
| `ai-service/` | AI1: worker OCR nhận lệnh qua Kafka. AI2: service IDP/trích xuất/hỏi đáp gọi qua HTTP | Python 3.11–3.12, FastAPI, Kafka, PostgreSQL + pgvector (AI2), `uv` |
| `docs/` | Product vision, kiến trúc, schema DB, API spec, contract giữa các service | Markdown, OpenAPI YAML, JSON Schema |

### Hạ tầng (`docker-compose.yml`)

| Thành phần | Dùng cho |
|---|---|
| PostgreSQL 16 + pgvector (`backend-db`) | DB của backend (schema `public`) và AI2 (schema `ai2`) |
| PostgreSQL 16 (`keycloak-db`) + Keycloak 26 | Đăng nhập, phân vai trò (OIDC) |
| Apache Kafka 3.7 | Hàng đợi lệnh/kết quả giữa backend và AI1 |
| MinIO | Lưu file PDF và kết quả OCR |
| Mailpit | Hộp thư local cho email mời/đặt mật khẩu |
| Prometheus, Grafana, Node Exporter, cAdvisor | Giám sát, xem tại **Quản trị → Giám sát hệ thống** (chỉ ADMINISTRATOR), chi tiết ở [`docs/MONITORING.md`](docs/MONITORING.md) |

### Kiến trúc backend

`backend/src/contract_intelligence/` chia theo bounded context (`contract`, `extraction`, `conflict`, `review`, `identity`), mỗi context tách `domain` / `application` / `infrastructure` / `interfaces`. Phần dùng chung nằm ở `shared/`, `infrastructure/`, `api/`; worker điều phối pipeline ở `worker.py`. Ranh giới giữa các tầng được kiểm bằng `import-linter`. Migration DB dùng Alembic (`backend/alembic/`), chạy tự động khi container backend khởi động.

---

## 🌿 Quy ước làm việc trên repo

Quy tắc đầy đủ (tiếng Anh) ở [CONTRIBUTING.md](CONTRIBUTING.md); hướng dẫn thao tác cụ thể (tiếng Việt)
ở [GITFLOWS.md](GITFLOWS.md). GitHub ruleset và check `pr-guard` cưỡng chế các điểm chính:

```
feature branch  ──PR──▶  develop  ──release PR──▶  main
(feature/…, feat/…)      2 approvals              2 approvals, chỉ squash merge
```

- `develop` là nhánh mặc định; **không ai push thẳng** vào `develop` hoặc `main`.
- Mỗi PR cần **2 approval từ đồng đội** (không tự approve; push mới làm mất approval cũ), resolve hết
  review thread, `pr-guard` xanh.
- `main` chỉ nhận PR từ `develop`, `release/*` hoặc `hotfix/*`.
- Tên nhánh: `^(feat|feature|fix|docs|chore|refactor|test|hotfix|release)/[a-z0-9._-]+$`,
  ví dụ `feature/backend-upload-api`, `hotfix/fix-alembic-migration`, `release/v0.1.0`.
- Tiêu đề PR: `<type>(<scope>): <summary>`, scope là `frontend | backend | ai | docs | infra | repo`.
- **Không commit hợp đồng, bản scan, file nén** (thật hay test) vào repo; `pr-guard` chặn các file
  `.pdf .docx .tif .jpg .png .zip …` ngoài `docs/assets/`. Dữ liệu mẫu để trên OneDrive, đọc qua đường dẫn ngoài repo.

---

## 🚀 Bắt đầu nhanh

Hướng dẫn chạy sạch từ một checkout duy nhất, cấu hình AI2, kiểm tra graph và xử lý lỗi nằm tại [docs/AI2-LOCAL-SETUP.md](docs/AI2-LOCAL-SETUP.md). Cần Docker Desktop/Compose v2 và Node.js 20+; cài [`uv`](https://docs.astral.sh/uv/) nếu chạy Python ngoài Docker.

```bash
git clone https://github.com/AI20K-VGR/contract-intelligence-core.git
cd contract-intelligence-core

# Cấu hình khóa AI1/AI2 cục bộ trong file bị gitignore
cp ai-service/.env.example ai-service/.env

docker compose up -d --build

cd frontend
npm ci
npm run dev
```

Chi tiết ports, đăng nhập local, OCR, graph, query, consent và troubleshooting: [hướng dẫn local đầy đủ](docs/AI2-LOCAL-SETUP.md).

### Kiểm tra Backend trước khi mở PR

```bash
cd backend
uv run ruff check . && uv run mypy src && uv run lint-imports && uv run pytest tests/unit tests/architecture
```

Chi tiết từng phần: [`backend/README.md`](backend/README.md), [`ai-service/README.md`](ai-service/README.md), [`HUONG-DAN-CHAY.md`](HUONG-DAN-CHAY.md), [`deploy/README.md`](deploy/README.md).

---

## 📚 Tài liệu

Xem thư mục [`docs/`](./docs/), các tài liệu chính:

- `DOC-01-product-vision.md` — Tầm nhìn sản phẩm, vấn đề, đối tượng người dùng
- `DOC-04-architecture.md`, `DOC-04d-backend-architecture.md` — Kiến trúc hệ thống và backend, ADRs
- `DOC-04b-postgres-schema.sql`, `DOC-04c-database-erd.md` — Schema và ERD database
- `DOC-05-api-spec.yaml` — OpenAPI 3.0 spec cho REST API
- `DOC-05b-frontend-backend-api-contract.md` — Contract API giữa frontend và backend
- `DOC-05c` → `DOC-05e`, `contracts/` — Contract giữa backend và AI1/AI2 (HTTP, Kafka, JSON Schema)
- `DOC-07-khung-project.md` — Khung dự án: luồng end-to-end, ranh giới subsystem, I/O ghép nối
- `DOC-12-ke-hoach-deploy-backend.md` — Kế hoạch deploy
- `MONITORING.md` — Giám sát hệ thống

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
