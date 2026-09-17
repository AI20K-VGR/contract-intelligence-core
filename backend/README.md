# backend/

REST API server cho dự án **Contract Intelligence** — FastAPI monolith với cấu trúc DDD + Clean Architecture.

> **Ngữ cảnh làm việc:** đọc `backend/CONTEXT.md` trước khi bắt đầu bất kỳ task nào.
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

---

## Tài liệu liên quan

| File | Mục đích |
|---|---|
| `backend/CONTEXT.md` | Ngữ cảnh làm việc cho backend engineer |
| `docs/DOC-04-architecture.md` | Kiến trúc tổng thể |
| `docs/DOC-04c-database-erd.md` | Sơ đồ ERD đầy đủ |
| `docs/DOC-04d-backend-architecture.md` | Quy tắc layering chi tiết + ADR |
| `docs/DOC-05-api-spec.yaml` | OpenAPI spec |
