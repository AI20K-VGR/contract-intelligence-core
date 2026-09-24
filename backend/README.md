# backend/

REST API server cho dự án **Contract Intelligence** — FastAPI monolith với cấu trúc DDD + Clean Architecture.

> **Ngữ cảnh làm việc:** đọc `backend/CONTEXT.md` trước khi bắt đầu bất kỳ task nào.
> **Code regulations (CI rules):** đọc `backend/CONTRIBUTING.md` để biết pre-commit checklist + quy tắc tránh CI fail.
> **Kiến trúc chi tiết:** xem `docs/DOC-04d-backend-architecture.md`.
> **Sơ đồ quan hệ database:** xem `docs/DOC-04c-database-erd.md`.

---

## Tech stack

| Hạng mục | Công nghệ |
|---|---|
| Ngôn ngữ | Python 3.11+ |
| Web framework | FastAPI + Uvicorn |
| ORM | SQLAlchemy 2.x (async) |
| Migration | Alembic |
| Validation | Pydantic v2 |
| File storage | MinIO (S3-compatible) |
| Settings | pydantic-settings |
| Test | pytest + pytest-asyncio + httpx |
| Lint / format | Ruff |
| Layering | import-linter (enforce DDD) |
| Container | Docker |

---

## Quy tắc bất di bất dịch: Dependency Rule

> **Các tầng trên CHỈ được gọi xuống tầng dưới. KHÔNG bao giờ gọi ngược.**

```
interfaces  ──▶  application  ──▶  domain
       │                  │
       └──────────────────┴──▶  infrastructure  ──▶  domain
                                                    (impl interface từ domain)
```

| Tầng | Phụ thuộc vào | KHÔNG được phép |
|---|---|---|
| `domain/` | *(chỉ stdlib + `shared/`)* | framework, ORM, FastAPI, SQLAlchemy, MinIO |
| `application/` | `domain/`, `shared/` | FastAPI, SQLAlchemy, MinIO |
| `infrastructure/` | `domain/`, `application/` (chỉ interface), `shared/` | FastAPI (router), API DTO |
| `interfaces/` | `application/`, `shared/` | domain repository impl, ORM trực tiếp |

Quy tắc này được **enforce tự động** bởi `import-linter` (xem `.importlinter`). CI fail nếu vi phạm.

---

## Cấu trúc thư mục

```
backend/
├── src/contract_intelligence/
│   ├── main.py                          # FastAPI app entry point
│   ├── config/                          # Settings, logging
│   ├── shared/                          # Shared kernel — cross-cutting
│   ├── contract/                        # Bounded context: hợp đồng
│   ├── extraction/                      # Bounded context: trích xuất
│   ├── conflict/                        # Bounded context: xung đột
│   ├── review/                          # Bounded context: HITL review
│   └── migrations/                      # Alembic (gốc cho cả src)
├── alembic/                             # Alembic config
├── tests/
│   ├── unit/                            # Unit test theo từng bounded context
│   ├── integration/                     # API integration test
│   └── architecture/                    # Layer conformance test (pytest-import-linter)
├── pyproject.toml                       # Poetry/uv + tool config
├── .importlinter                        # Layer dependency rules
├── alembic.ini
├── Dockerfile
└── README.md
```

Mỗi bounded context (`contract`, `extraction`, `conflict`, `review`) đều có **đủ 4 layer**:

```
{bounded_context}/
├── domain/          # Entities, value objects, enums, repository ABC
├── application/     # Services, DTOs, use cases
├── infrastructure/  # Persistence impl, storage adapter, external client
└── interfaces/      # FastAPI routers
```

---

## Cách đặt code mới

| Bạn muốn… | Đặt vào đây |
|---|---|
| Định nghĩa entity / value object / enum | `{module}/domain/entities/` hoặc `{module}/domain/value_objects/` |
| Định nghĩa abstract repository | `{module}/domain/repositories/` |
| Use case / orchestration | `{module}/application/services/` |
| DTO input / output | `{module}/application/dtos/` |
| Triển khai repository (SQLAlchemy) | `{module}/infrastructure/persistence/` |
| Adapter MinIO / OpenAI | `{module}/infrastructure/storage/` hoặc `{module}/infrastructure/ai_client/` |
| REST endpoint | `{module}/interfaces/api/routers/` |
| Enum / exception / event dùng chung | `shared/` |

---

## Chạy local

```bash
# Cài dependency
uv sync

# Chạy FastAPI
uv run uvicorn contract_intelligence.main:app --reload

# Test
uv run pytest

# Lint + enforce layering
uv run ruff check .
uv run lint-imports          # alias cho `import-linter --config .importlinter`
```

## Kết nối AI1 OCR service

### Kafka (đường runtime — DOC-05d / DOC-05e)

Backend publish `dossier.uploaded` → orchestrator worker publish
`ci.ai1.ocr.commands` → AI1 Kafka worker chạy OCR → `ci.ai1.ocr.results` →
backend persist snapshot → (nếu `AI2_WIRE_ENABLED=true`) publish
`ci.ai2.idp.commands` → AI2 Kafka worker → `ci.ai2.idp.results` →
backend persist findings / `PENDING_REVIEW`.

```powershell
# Terminal A — Kafka + MinIO + DB (từ repo root)
docker compose up -d kafka minio minio-init backend-db backend backend-worker ai1-worker ai2-worker

# Hoặc chạy worker local (Kafka đã up)
cd backend
uv run python -m contract_intelligence.worker
```

Chi tiết:
- AI1 OCR: `docs/DOC-05d-kafka-ai1-ocr-contract.md`
- AI2 IDP (MVP body-only): `docs/DOC-05e-kafka-ai2-idp-contract.md`

### HTTP job API (demo / manual only)

Backend giữ quyền điều phối và lưu trữ; `ai-service` chỉ nhận một URL tải PDF có
thời hạn, xử lý OCR, rồi trả về job có thể polling. Swagger của backend vẫn là
`http://127.0.0.1:8000/docs`; nhóm vận hành kiểm tra kết nối qua nhóm endpoint
**AI-Service** (`GET /api/v1/readyz`, `GET/DELETE /api/v1/ai/jobs/{job_id}`).

Chạy AI1 ở terminal khác:

```powershell
cd ai-service
uv sync --extra web
uv run --extra web uvicorn contract_ocr.web.app:app --host 127.0.0.1 --port 8001
```

Sau đó đặt trong `backend/.env`:

```dotenv
AI_SERVICE_MODE=http
AI_SERVICE_URL=http://127.0.0.1:8001
AI_SERVICE_TIMEOUT_SECONDS=30
```

AI1 công bố contract riêng ở `http://127.0.0.1:8001/docs`: `POST /api/v1/jobs/ocr`,
`GET/DELETE /api/v1/jobs/{job_id}` và `GET /healthz`. `source_blob_get_url` phải là
URL tải PDF ngắn hạn và `source_sha256` phải khớp file. Nếu backend cấp
`render_target.presigned_put_urls`, AI1 sẽ tải PNG render lên các URL đó; nếu không,
snapshot đánh dấu rõ render chưa được lưu bền vững.

---

## Tài liệu liên quan

| File | Mục đích |
|---|---|
| `backend/CONTEXT.md` | Ngữ cảnh làm việc cho backend engineer |
| `docs/DOC-04-architecture.md` | Kiến trúc tổng thể |
| `docs/DOC-04c-database-erd.md` | Sơ đồ ERD đầy đủ |
| `docs/DOC-04d-backend-architecture.md` | Quy tắc layering chi tiết + ADR |
| `docs/DOC-05-api-spec.yaml` | OpenAPI spec |
