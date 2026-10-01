# DOC-04d · BACKEND ARCHITECTURE — Layering & DDD

**Kiến trúc backend: Clean Architecture / DDD — Dependency Rule — Layer Enforcement**

Dự án: VSF OJT Batch 3 · Phiên bản 0.1
Ngày tạo: 17/09/2026

---

## Mục lục

0. [Thông tin tài liệu](#0-thông-tin-tài-liệu)
1. [Tổng quan kiến trúc](#1-tổng-quan-kiến-trúc)
2. [Dependency Rule — Tầng trên chỉ gọi tầng dưới](#2-dependency-rule--tầng-trên-chỉ-gọi-tầng-dưới)
3. [Bounded Context và Aggregate Roots](#3-bounded-context-và-aggregate-roots)
4. [Anti-Corruption Layer — Protocol Pattern](#4-anti-corruption-layer--protocol-pattern)
5. [Cấu trúc thư mục đầy đủ](#5-cấu-trúc-thư-mục-đầy-đủ)
6. [Cách thêm module mới](#6-cách-thêm-module-mới)
7. [Enforcement — import-linter + ruff + CI](#7-enforcement--import-linter--ruff--ci)
8. [Những lỗi thường gặp và cách tránh](#8-những-lỗi-thường-gặp-và-cách-tránh)
9. [ADR — Architecture Decision Records](#9-adr--architecture-decision-records)

---

## 0. Thông tin tài liệu

| Trường | Nội dung |
|---|---|
| Mã tài liệu | DOC-04d |
| Dự án | VSF OJT Batch 3 |
| Trạng thái | Bản nháp |
| Tham chiếu | `backend/pyproject.toml`, `backend/.importlinter`, `backend/CONTEXT.md` |

---

## 1. Tổng quan kiến trúc

Backend tuân theo **Clean Architecture** + **DDD** với 4 bounded context. Mỗi context có đủ 4 tầng:

```
interfaces/    →  FastAPI routers, exception handlers         (Tầng 4 — ngoài cùng)
application/  →  Use cases, DTOs                          (Tầng 3)
domain/       →  Entities, enums, repository protocols      (Tầng 2)
infrastructure/ → SQLAlchemy impl, MinIO adapter, AI client (Tầng 1 — gần nhất với nền)
```

**Sơ đồ luồng call:**

```
HTTP Request
    ↓
interfaces (FastAPI router)      ← chỉ import FastAPI + application
    ↓
application (service)            ← chỉ import domain entity + Protocol
    ↓
domain (entity)                  ← chỉ import shared/ + stdlib
    ↑
infrastructure (repo impl)      ← impl domain Protocol + import ORM
    ↑
interfaces ← KHÔNG BAO GIỜ gọi infrastructure trực tiếp
```

**Lý do chọn Clean Architecture:**

| Lý do | Giải thích |
|---|---|
| **Test được** | Domain logic không phụ thuộc FastAPI/SQLAlchemy → unit test không cần DB |
| **Tái sử dụng** | Application service dùng lại cho CLI, test harness, worker |
| **Thay đổi an toàn** | Thay MinIO bằng S3 không sửa domain/application |
| **Onboard nhanh** | Member mới biết chính xác đặt code ở đâu |

---

## 2. Dependency Rule — Tầng trên chỉ gọi tầng dưới

Đây là quy tắc **bất di bất dịch** — vi phạm = CI fail.

### 2.1 Bảng quy tắc chi tiết

| Tầng | Được phép import | Cấm |
|---|---|---|
| `domain/` | stdlib, `shared/`, **KHÔNG** `fastapi`, `sqlalchemy`, `pydantic`, `minio`, `httpx`, bất kỳ bounded context nào khác | Mọi framework, mọi bounded context khác |
| `application/` | `domain/`, `shared/`, **KHÔNG** `infrastructure/`, `interfaces/`, `fastapi`, `sqlalchemy` | infrastructure, interfaces, framework |
| `infrastructure/` | `domain/` (Protocol), `application/` (Protocol), `shared/`, framework | `interfaces/` (router/API) |
| `interfaces/` | `application/`, `shared/` | `domain/` impl (entity thuần OK), `infrastructure/` impl |

### 2.2 Cross-module Communication

Các bounded context **không được** gọi repository/implementation của nhau. Giao tiếp qua:

| Cách | Khi nào dùng |
|---|---|
| **Domain Event** (xem `shared/events.py`) | Khi context A cần thông báo cho context B một sự kiện nghiệp vụ (bất đồng bộ) |
| **Public Application Service** | Khi cần gọi đồng bộ (ví dụ review cần đọc fact từ extraction) — phơi service qua DI |
| **Shared Kernel** (`shared/`) | Enum, exception, base class dùng chung |

> **Không bao giờ** import `XxxRepositoryImpl` từ module khác. Nếu cần, hãy define Protocol trong domain và implement ở infrastructure.

### 2.3 Ví dụ vi phạm

```python
# ❌ SAI — domain import FastAPI
# backend/contract/domain/entities/dossier.py
from fastapi import UploadFile  # CẤM

# ❌ SAI — application import infrastructure impl
# backend/contract/application/services/upload_service.py
from contract.infrastructure.persistence import SqlDossierRepository  # CẤM

# ✅ ĐÚNG — application dùng Protocol (định nghĩa ở domain)
# backend/contract/application/services/upload_service.py
from contract.domain.repositories import DossierRepository  # Protocol

async def get_dossier(id: str) -> Dossier:
    # Dùng DossierRepository Protocol
    # Runtime sẽ inject SqlDossierRepository (implement Protocol)
```

---

## 3. Bounded Context và Aggregate Roots

### 3.1 Tổng quan 4 context

| Context | Module | Aggregate Roots | DB Tables | Trách nhiệm |
|---|---|---|---|---|
| Contract | `contract/` | `Dossier`, `Document`, `Job` | `dossier`, `document`, `job` | Upload, state machine, file storage |
| Extraction | `extraction/` | `Page`, `OcrLine`, `Citation`, `ClauseNode`, `Fact`, `PipelineRun` | `page`, `ocr_line`, `citation`, `clause_node`, `fact` | Nhận & lưu kết quả OCR/trích xuất |
| Conflict | `conflict/` | `Finding`, `FindingSide`, `AnnexLink` | `finding`, `finding_side`, `annex_link` | Lưu phát hiện conflict |
| Review | `review/` | `ReviewItem`, `ReviewAction`, `DossierApproval` | `review_item`, `review_action`, `dossier_approval` | HITL queue, optimistic concurrency |

### 3.2 Entity trong domain layer

Domain entity là `@dataclass` plain Python — không có decorator SQLAlchemy:

```python
# ✅ ĐÚNG — plain dataclass
@dataclass(eq=False)
class Dossier(BaseEntity[str]):
    id: str = field(default_factory=lambda: new_ulid("dos_"))
    name: str = ""
    has_conflicts: bool = False
    documents: list[Document] = field(default_factory=list, repr=False)
```

```python
# ❌ SAI — dùng SQLAlchemy decorator trong domain
from sqlalchemy import Column, String, Boolean
class Dossier(Base):
    __tablename__ = "dossier"
    id = Column(String, primary_key=True)  # CẤM trong domain/
```

**Tại sao?** Để domain logic test được mà không cần SQLAlchemy engine. Sprint 2 sẽ map trong `infrastructure/persistence/`.

---

## 4. Anti-Corruption Layer — Protocol Pattern

### 4.1 Vấn đề

Application layer cần gọi infrastructure (ví dụ: repository) nhưng **không được import infrastructure** (vi phạm Dependency Rule). Giải pháp: **Protocol** (Python `Protocol` + `@runtime_checkable`).

### 4.2 Pattern

```
domain/repositories/dossier_repository.py   ← Protocol (định nghĩa)
        ↑
application/service/upload_service.py       ← dùng Protocol (type hint)
        ↑
infrastructure/persistence/               ← implement Protocol
```

**Protocol** (domain):

```python
# contract/domain/repositories/dossier_repository.py
from typing import Protocol, runtime_checkable

@runtime_checkable
class DossierRepository(Protocol):
    async def get(self, dossier_id: str) -> Dossier | None: ...
    async def add(self, dossier: Dossier) -> None: ...
```

**Application** (chỉ type hint, không import impl):

```python
# contract/application/services/upload_service.py
class ContractUploadService:
    def __init__(self, *, dossier_repo: DossierRepository) -> None:
        self._dossier_repo = dossier_repo  # Protocol inject
```

**Infrastructure** (implement):

```python
# contract/infrastructure/persistence/dossier_repository_impl.py
class SqlDossierRepository:
    async def get(self, dossier_id: str) -> Dossier | None:
        # SQLAlchemy query here
        ...
```

### 4.3 Protocol cho external IO

External adapters (MinIO, AI Service) cũng dùng Protocol để application không phụ thuộc SDK:

```python
# extraction/infrastructure/ai_client/ai_service_client.py
@runtime_checkable
class AiServicePort(Protocol):
    async def submit_extraction_job(self, *, dossier_id: str) -> str: ...
    async def poll_extraction_result(self, ai_job_id: str) -> dict[str, object]: ...
```

---

## 5. Cấu trúc thư mục đầy đủ

```
backend/
├── src/contract_intelligence/
│   ├── main.py                          # FastAPI app + exception handler
│   ├── config/                         # Settings (pydantic-settings), logging
│   │   ├── settings.py                 # DATABASE_URL, MINIO_*, AI_*, OTEL_*
│   │   └── logging.py                  # structlog setup
│   ├── shared/                        # Shared kernel
│   │   ├── base.py                     # BaseEntity (dataclass), BaseRepository (ABC)
│   │   ├── exceptions.py               # DomainException hierarchy
│   │   ├── events.py                  # DomainEvent (Pydantic) + catalog
│   │   ├── responses.py               # ApiResponse envelope
│   │   └── utils.py                  # normalize_text, to_iso_date
│   ├── contract/                        # Bounded context: contract lifecycle
│   │   ├── domain/
│   │   │   ├── entities/
│   │   │   │   ├── dossier.py         # @dataclass, state machine logic
│   │   │   │   ├── document.py        # @dataclass
│   │   │   │   └── job.py             # @dataclass, JobStatus enum
│   │   │   └── repositories/
│   │   │       ├── dossier_repository.py   # Protocol
│   │   │       ├── document_repository.py  # Protocol
│   │   │       └── job_repository.py       # Protocol
│   │   ├── application/
│   │   │   ├── services/
│   │   │   │   ├── contract_upload_service.py   # use case
│   │   │   │   └── contract_status_service.py   # use case
│   │   │   └── dtos/
│   │   │       ├── contract_upload_request.py   # Pydantic input
│   │   │       └── contract_status_response.py  # Pydantic output
│   │   ├── infrastructure/
│   │   │   ├── persistence/
│   │   │   │   ├── dossier_repository_impl.py  # SQLAlchemy impl
│   │   │   │   ├── document_repository_impl.py  # SQLAlchemy impl
│   │   │   │   └── job_repository_impl.py       # SQLAlchemy impl
│   │   │   └── storage/
│   │   │       └── minio_adapter.py             # MinIO SDK impl
│   │   └── interfaces/
│   │       └── api/routers/
│   │           ├── contract_upload_router.py    # @router.post(...)
│   │           └── contract_status_router.py     # @router.get(...)
│   ├── extraction/                    # Bounded context: trích xuất
│   │   ├── domain/entities/          # Page, OcrLine, Citation, ClauseNode, Fact, PipelineRun
│   │   ├── domain/repositories/      # Protocol (PageRepository, CitationRepository, FactRepository)
│   │   ├── application/services/     # ExtractionResultService
│   │   ├── application/dtos/         # FactResponse
│   │   ├── infrastructure/persistence/   # SQLAlchemy impl
│   │   ├── infrastructure/ai_client/     # AiServiceClient (HTTP → ai-service)
│   │   └── interfaces/api/routers/       # extraction_router
│   ├── conflict/                      # Bounded context: conflict detection
│   │   ├── domain/entities/          # Finding, FindingSide, AnnexLink
│   │   ├── domain/repositories/      # Protocol (FindingRepository)
│   │   ├── application/services/     # ConflictQueryService
│   │   ├── infrastructure/persistence/  # SQLAlchemy impl
│   │   └── interfaces/api/routers/       # conflict_router
│   ├── review/                        # Bounded context: HITL review
│   │   ├── domain/entities/          # ReviewItem, ReviewAction, DossierApproval
│   │   ├── domain/repositories/      # Protocol (ReviewItemRepository)
│   │   ├── application/services/     # ReviewActionService (P0-05 optimistic concurrency)
│   │   ├── infrastructure/persistence/  # SQLAlchemy impl
│   │   └── interfaces/api/routers/       # review_router
│   └── migrations/                   # Alembic (tại root của package)
├── alembic/                          # Alembic config
│   ├── env.py                        # async engine setup
│   ├── script.py.mako
│   └── versions/
│       └── v1__init.py              # V1 schema (stub — Sprint 2 autogenerate)
├── tests/
│   ├── conftest.py                   # Shared fixtures
│   ├── unit/
│   │   ├── test_domain_entities.py   # Entity invariant tests
│   │   └── test_shared.py            # shared/ utilities tests
│   └── architecture/
│       └── test_layer_conformance.py  # import-linter + ruff + domain purity
├── pyproject.toml                    # Poetry + tool config (import-linter, ruff, mypy)
├── .importlinter                    # Layer dependency rules (6 contracts)
├── alembic.ini
├── requirements.txt
├── Dockerfile
└── README.md
```

---

## 6. Cách thêm module mới

Giả sử thêm bounded context `billing/`:

```
contract_intelligence/billing/
├── domain/
│   ├── __init__.py
│   ├── entities/
│   │   ├── __init__.py
│   │   └── invoice.py
│   └── repositories/
│       ├── __init__.py
│       └── invoice_repository.py     # Protocol
├── application/
│   ├── __init__.py
│   ├── services/
│   │   ├── __init__.py
│   │   └── billing_service.py
│   └── dtos/
│       └── __init__.py
├── infrastructure/
│   ├── __init__.py
│   ├── persistence/
│   │   ├── __init__.py
│   │   └── invoice_repository_impl.py  # SQLAlchemy impl
│   └── payment_gateway/
│       ├── __init__.py
│       └── payment_gateway_adapter.py
└── interfaces/
    ├── __init__.py
    └── api/
        ├── __init__.py
        └── routers/
            ├── __init__.py
            └── billing_router.py
```

**Sau đó cập nhật:**
1. `backend/.importlinter` — thêm `contract_intelligence.billing.*` vào đúng vị trí trong layer contracts
2. `backend/pyproject.toml` — thêm banned-api nếu cần
3. `backend/src/contract_intelligence/main.py` — include router
4. `backend/tests/architecture/test_layer_conformance.py` — thêm domain purity test
5. `backend/.github/workflows/backend-ci.yml` — thêm layer contract vào import-linter

---

## 7. Enforcement — import-linter + ruff + CI

### 7.1 import-linter — Dependency Rule

Công cụ chính enforce layer boundaries. Config trong `backend/.importlinter`:

```
6 contracts:
1. domain_purity              — domain không import framework/context khác
2. application_no_infra_or_interfaces — application không import infra/interfaces
3. infrastructure_no_interfaces — infra không import interfaces
4. cross_module_independence  — application module A không import infra module B
5–8. *_layers               — enforce exact layer order per context
```

**Chạy thủ công:**
```bash
cd backend
uv run python -m import_linter --config .importlinter
```

**CI:** job `lint-layers` trong `.github/workflows/backend-ci.yml` fail nếu vi phạm.

### 7.2 ruff — Banned API

`ruff` dùng `TID` (flake8-tidy-imports) + `banned-api` để cấm import framework ở domain:

```toml
[tool.ruff.lint.tidy-imports.banned-api]
"sqlalchemy.orm".msg = "Domain layer không được import trực tiếp từ SQLAlchemy ORM. Dùng Protocol trong domain/repositories/"
"fastapi".msg = "Domain layer không được import FastAPI. Dùng router trong interfaces/"
```

### 7.3 CI Pipeline

```
push/PR backend/ →
  ├─ lint-layers:    import-linter (Dependency Rule)
  ├─ lint:            ruff check + format
  ├─ typecheck:       mypy strict
  └─ test-unit:       pytest (unit + architecture)
```

---

## 8. Những lỗi thường gặp và cách tránh

### Lỗi 1: Import framework trong domain

```python
# ❌ SAI
from fastapi import HTTPException

# ✅ ĐÚNG
from pydantic import BaseModel   # Pydantic OK trong shared/ hoặc application DTO
# Hoặc dùng plain dataclass
```

### Lỗi 2: Import infrastructure impl vào application

```python
# ❌ SAI
from contract.infrastructure.persistence import SqlDossierRepository

# ✅ ĐÚNG — dùng Protocol (inject qua __init__ hoặc FastAPI Depends)
async def my_service(dossier_repo: DossierRepository) -> None:
    ...
```

### Lỗi 3: Gọi repository impl của module khác

```python
# ❌ SAI — extraction gọi contract infrastructure
from extraction.infrastructure.ai_client import SomeClient

# ✅ ĐÚNG — giao tiếp qua Domain Event
await self._event_publisher.publish(DossierCreated(...))
```

### Lỗi 4: Đặt business logic trong router

```python
# ❌ SAI — logic nghiệp vụ trong FastAPI router
@router.post("/dossiers")
async def create(name: str):
    if len(name) > 255:
        raise HTTPException(422)  # Logic ở đây
    dossier = Dossier(name=name)
    await repo.add(dossier)  # Không có transaction

# ✅ ĐÚNG — logic trong application service, router chỉ parse/validate
@router.post("/dossiers")
async def create(req: ContractUploadRequest):
    dossier_id = await upload_service.execute(req)  # Transaction ở đây
    return ApiResponse(data=dossier_id)
```

---

## 9. ADR — Architecture Decision Records

### ADR-04d-01: Clean Architecture + DDD thay vì simple layered

**Quyết định:** Dùng Clean Architecture (4 tầng) + DDD (4 bounded context) cho backend.

**Hệ quả:**
- ✅ Domain logic hoàn toàn test được không cần DB
- ✅ Thay đổi infrastructure (MinIO → S3) không ảnh hưởng business logic
- ✅ Member mới có hướng dẫn rõ ràng đặt code ở đâu
- ⚠️ Overhead ban đầu: phải define Protocol cho mỗi external IO
- ⚠️ Số lượng file nhiều hơn simple structure

**Tham khảo:** `backend/CONTEXT.md` §3.1

---

### ADR-04d-02: Domain entity là plain dataclass, không dùng SQLAlchemy trong domain

**Quyết định:** `@dataclass` thuần thay vì `@dataclass_mixins` hay `declarative_base`.

**Hệ quả:**
- ✅ Unit test không cần SQLAlchemy
- ✅ Entity có thể dùng cho CLI, worker, test harness
- ⚠️ Phải map trong `infrastructure/persistence/` (2 lần khai báo)
- ⚠️ Cần SQLAlchemy `ash` để hydrate entity từ row

**Tham khảo:** `backend/src/contract_intelligence/shared/base.py`

---

### ADR-04d-03: Protocol pattern cho tất cả external IO

**Quyết định:** Dùng `typing.Protocol` + `@runtime_checkable` thay vì ABC hay dependency injection framework.

**Hệ quả:**
- ✅ Không cần DI framework (như `punq`, `dependency-injector`)
- ✅ Runtime type check an toàn
- ✅ Explicit — Protocol nằm trong domain/repositories/ hoặc infrastructure/

**Tham chiếu:** `backend/src/contract_intelligence/contract/domain/repositories/dossier_repository.py`

---

### ADR-04d-04: import-linter enforce Dependency Rule

**Quyết định:** Dùng `import-linter` với 6 contracts trong CI thay vì chỉ convention/review.

**Hệ quả:**
- ✅ CI fail tự động nếu vi phạm — không phụ thuộc reviewer
- ✅ Violation được báo chi tiết (source → forbidden module)
- ⚠️ Thêm thời gian chạy CI (~10-30s)

**Tham chiếu:** `backend/.importlinter`, `.github/workflows/backend-ci.yml`

---

**Hết DOC-04d · Backend Architecture v0.1**
