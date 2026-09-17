# backend/

> **Skeleton đang review trên `feature/backend-setup` — phụ trách: Backend Engineer.** Theo DOC-03 CON-06, business feature code chỉ bắt đầu sau khi mentor phê duyệt kiến trúc và cấu trúc project.

Thư mục này chứa REST API server và orchestration cho dự án **Contract Intelligence**.

## Tech stack (DOC-04 ADR-01, §3.1)

- Python 3.12 (target; skeleton hiện khai báo `>=3.11`, phải nâng `requires-python`, Ruff và MyPy target trước merge)
- FastAPI + Uvicorn; OpenAPI tại `/openapi.json`, Swagger `/docs`, ReDoc `/redoc`
- Pydantic v2 + pydantic-settings
- SQLAlchemy 2.x async + `asyncpg`; migration bằng Alembic
- PostgreSQL: system of record và task queue MVP (`FOR UPDATE SKIP LOCKED`, lease token, heartbeat)
- MinIO S3-compatible cho PDF/render (tách bucket), adapter ở infrastructure
- `httpx` client gọi `ai-service` (`extraction/infrastructure/ai_client`)
- OpenTelemetry + structlog (profile optional)
- pytest / pytest-asyncio / httpx, Ruff, MyPy strict, import-linter (CI gate)

## Kiến trúc đích

Clean Architecture + DDD, modular monolith chia theo **bounded context** (DOC-04 §3.2):

```
src/contract_intelligence/
├── contract/      # Dossier, DocumentVersion, Manifest, Job
├── extraction/    # Page, OcrLine, Citation, ClauseNode, Fact, PipelineRun, ai_client
├── conflict/      # Finding, FindingSide, AnnexLink
├── review/        # ReviewItem, ReviewRevision, DossierApproval
├── shared/        # Shared kernel: event, exception, base
└── config/        # settings, logging
```

Mỗi context có đủ 4 layer `domain` → `application` → `infrastructure` → `interfaces`. Dependency rule: `domain` chỉ stdlib/shared; `application` chỉ domain/shared; `infrastructure` implement Protocol và không import router; `interfaces` chỉ parse HTTP/DTO rồi gọi application service. `import-linter` cưỡng chế rule này trong CI.

## Ranh giới với ai-service (DOC-04 ADR-02/03, §5)

Backend là **public API**, owner của domain/persistence/Alembic, auth/RBAC, task queue và orchestration. Mô hình tích hợp là **backend-push**:

1. Orchestrator ghi task vào PostgreSQL qua outbox; dispatcher claim task bằng lease token.
2. Dispatcher gọi `ai-service` `POST /jobs/{ocr|reocr|idp}` với `task_id`, `attempt_id`, URL artifact ngắn hạn và config digest, rồi poll `GET /jobs/{id}`.
3. Kết quả (snapshot v3 / AI2 result envelope + digest) đi qua result adapter: JSON Schema + semantic validator, rồi persist + outbox trong một transaction.
4. Backend là nơi duy nhất phát domain event (`ValidatedSnapshotPublished`, `SnapshotRevisionPublished`, `ReOcrScheduled`, …).

Backend không nhận callback URL do client cung cấp; `ai-service` không kết nối PostgreSQL và không sở hữu queue.

## Tài liệu chuẩn

[`docs/DOC-04-architecture.md`](../docs/DOC-04-architecture.md) (kiến trúc, ADR, change record §22), [`docs/DOC-05-api-spec.yaml`](../docs/DOC-05-api-spec.yaml) (public API), [`docs/contracts/`](../docs/contracts/README.md) (wire contracts và validation fixtures).
