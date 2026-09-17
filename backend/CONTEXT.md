# backend/CONTEXT.md

> **Mục đích:** File ngữ cảnh dành cho Backend Engineer làm việc trong module `backend/`. Agent đọc file này trước khi bắt đầu bất kỳ task nào trong backend. Không cần tra tài liệu ở thư mục khác.

---

## Table of Contents

1. [Tổng quan dự án](#1-tổng-quan-dự-án)
2. [Vai trò Backend Engineer trong team](#2-vai-trò-backend-engineer-trong-team)
3. [Kiến trúc hệ thống](#3-kiến-trúc-hệ-thống)
4. [Vòng đời nghiệp vụ hợp đồng (State machine)](#4-vòng-đời-nghiệp-vụ-hợp-đồng-state-machine)
5. [Data model / Database schema](#5-data-model--database-schema)
6. [API Spec (DOC-05)](#6-api-spec-doc-05)
7. [Contract kỹ thuật Backend ↔ AI Service](#7-contract-kỹ-thuật-backend--ai-service)
8. [Way of Working / quy tắc dự án](#8-way-of-working--quy-tắc-dự-án)
9. [Trạng thái hiện tại / Đã quyết định](#9-trạng-thái-hiện-tại--đã-quyết-định)

---

## 1. Tổng quan dự án

> TODO: Điền nội dung
> - Tên dự án, mã dự án (PROD-01)
> - Mục tiêu tổng quát
> - Timeline: 3 Sprint (chi tiết từng sprint)
> - 4 tính năng cốt lõi:
>   1. Trích xuất / bóc tách điều khoản (Clause Extraction)
>   2. Trích dẫn luật / căn cứ pháp lý (Legal Citation)
>   3. Phát hiện xung đột giữa các điều khoản (Conflict Detection)
>   4. HITL Review — Human-in-the-Loop xử lý các trường hợp không chắc chắn

---

## 2. Vai trò Backend Engineer trong team

> TODO: Điền nội dung
> - Thành viên team: ai, vai trò từng người (Backend, Frontend, AI Engineer, Mentor, PO...)
> - **Phạm vi Backend:**
>   - Nhận file hợp đồng upload từ client
>   - Quản lý trạng thái job (job state machine)
>   - Lưu metadata, trích xuất, xung đột vào DB
>   - Trả dữ liệu cho màn hình HITL Review
>   - Nhận kết quả OCR/conflict từ AI Service (qua callback hoặc poll)
>   - Gửi job đến AI Service (OCR/Extraction, Conflict Detection)
> - **Out of scope:**
>   - Không implement microservices — Backend là monolith
>   - Không tự tạo repo mới
>   - Không implement OCR worker hoặc conflict detection worker (việc của AI Engineer)
>   - Không làm giao diện người dùng (Frontend)

---

## 3. Kiến trúc hệ thống

### 3.1 Quyết định kiến trúc

| Quyết định | Giá trị |
|---|---|
| **Deployment** | Monolith — Modular Monolith (không microservices) |
| **Design pattern** | Domain-Driven Design (DDD) |
| **Backend** | Python 3.11 + FastAPI |
| **AI Service** | Python (FastAPI) — tách riêng, giao tiếp qua HTTP REST |
| **Database** | PostgreSQL + SQLAlchemy (ORM) |
| **Migration** | Alembic |
| **Object storage** | MinIO (S3-compatible) |
| **Frontend** | React / Vue (chưa chốt) |

**Lý do chọn Monolith:**
- Team chỉ có 4 thành viên (1 Backend, 1 Frontend, 2 AI Engineer), timeline OJT chỉ khoảng 1 tháng
- Microservices phù hợp khi cần scale độc lập hoặc nhiều team làm song song không phụ thuộc nhau — cả 2 điều kiện này chưa đúng ở giai đoạn hiện tại
- Overhead vận hành (network giữa các service, container, service discovery, distributed tracing) tốn thời gian mà nhóm không có
- Lợi ích scale độc lập chưa thực sự cần thiết ở quy mô OJT 1 tháng

**Lý do chọn Modular Monolith:**
- Một codebase Backend duy nhất, chia rõ ranh giới theo DDD
- Mã nguồn dễ bảo trì, dễ kiểm soát
- Có thể tách thành Microservices trong tương lai nếu quy mô mở rộng mà không cần thiết kế lại từ đầu

**Lý do chọn DDD:**
- Nghiệp vụ hợp đồng có domain rõ: upload → extract → conflict → review
- 5 bounded context tách biệt, dễ phân công work
- Dễ mở rộng khi cần tách AI service ra worker riêng

### 3.2 Bounded Context — 5 module

| Module | Trách nhiệm |
|---|---|
| `contract` | Quản lý vòng đời hợp đồng, upload, metadata, state machine |
| `extraction` | Lưu kết quả trích xuất điều khoản, pages, bounding box |
| `conflict` | Lưu kết quả phát hiện xung đột, ánh xạ clause conflict |
| `review` | Lưu review log, duyệt/kết quả HITL |
| `shared` | Common types, enums, utils, exceptions, domain events |

### 3.3 Nguyên tắc Dependency Rule

Các bounded context giao tiếp với nhau thông qua **Domain Event** hoặc **Application Service công khai (public)**, tuyệt đối không truy cập trực tiếp vào Repository của module khác.

- **Domain layer** không phụ thuộc framework — không import FastAPI, SQLAlchemy engine trực tiếp vào domain entity
- **Infrastructure** phụ thuộc Domain (đúng Dependency Rule: infrastructure → domain, không ngược lại)
- **Application layer** chỉ gọi public method của Domain, không import implementation detail từ module khác
- Nguyên tắc này giữ đúng Clean Architecture, đồng thời tạo tiền đề để tách module thành service độc lập trong tương lai nếu cần, mà không phải viết lại logic nghiệp vụ

### 3.4 Cấu trúc thư mục

> Tech stack: **Python 3.11 + FastAPI** + SQLAlchemy + Alembic + MinIO

Ánh xạ từ Java/Spring Boot DDD → Python/FastAPI DDD:

| Java (`com.vsf.contractintel`) | Python (`contract_intelligence`) |
|---|---|
| `domain/model/*.java` | `domain/entities/*.py` |
| `domain/repository/*.java` | `domain/repositories/*.py` |
| `application/*Service.java` | `application/services/*.py` |
| `infrastructure/persistence/*Impl.java` | `infrastructure/persistence/*.py` |
| `infrastructure/storage/*Adapter.java` | `infrastructure/storage/*.py` |
| `infrastructure/client/*Client.java` | `infrastructure/ai_client/*.py` |
| `interfaces/rest/*Controller.java` | `interfaces/api/routers/*.py` |
| `@RestController` | `@router` (FastAPI) |
| `@Entity` / `@Table` | SQLAlchemy `Base` + `Table` |
| `@Repository` | SQLAlchemy `AsyncSession` |
| `DomainEvent` | Pydantic `BaseModel` event |

```
backend/
├── src/contract_intelligence/
│   ├── __init__.py
│   ├── main.py                          # FastAPI app entry point
│   │
│   ├── shared/                          # Shared kernel
│   │   ├── __init__.py
│   │   ├── base.py                      # BaseEntity, BaseRepository
│   │   ├── responses.py                 # ApiResponse, ErrorResponse
│   │   ├── exceptions.py                # DomainException, DomainErrorCode
│   │   ├── events.py                    # DomainEvent (BaseModel)
│   │   └── utils.py                     # Common utilities
│   │
│   ├── config/                          # Application configuration
│   │   ├── __init__.py
│   │   ├── settings.py                  # pydantic-settings (DATABASE_URL, MINIO_*, AI_*)
│   │   └── logging.py                  # Logging setup
│   │
│   ├── contract/                        # Bounded Context: contract lifecycle
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── contract.py          # Contract (ORM model)
│   │   │   │   └── contract_page.py     # ContractPage (ORM model)
│   │   │   ├── enums.py                 # ContractStatus enum
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       └── contract_repository.py  # ContractRepository (abstract)
│   │   ├── application/
│   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── contract_upload_service.py
│   │   │   │   └── contract_status_service.py
│   │   │   └── dtos/
│   │   │       ├── __init__.py
│   │   │       ├── contract_upload_request.py
│   │   │       └── contract_status_response.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   ├── persistence/
│   │   │   │   ├── __init__.py
│   │   │   │   └── contract_repository_impl.py  # implements ContractRepository
│   │   │   └── storage/
│   │   │       ├── __init__.py
│   │   │       └── minio_adapter.py     # MinIO file storage adapter
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       └── api/
│   │           ├── __init__.py
│   │           └── routers/
│   │               ├── __init__.py
│   │               ├── contract_upload_router.py  # @router.post("/contracts/upload")
│   │               └── contract_status_router.py  # @router.get("/contracts/{id}")
│   │
│   ├── extraction/                      # Bounded Context: clause extraction
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── clause.py           # Clause (ORM model, self-referential)
│   │   │   │   ├── bounding_box.py     # BoundingBox (JSONB field)
│   │   │   │   └── appendix_table.py   # AppendixTable (ORM model)
│   │   │   ├── enums.py                # ClauseLevel (CHAPTER/ARTICLE/CLAUSE/POINT)
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       └── clause_repository.py
│   │   ├── application/
│   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   └── extraction_result_service.py
│   │   │   └── dtos/
│   │   │       └── __init__.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   ├── persistence/
│   │   │   │   ├── __init__.py
│   │   │   │   └── clause_repository_impl.py
│   │   │   └── ai_client/
│   │   │       ├── __init__.py
│   │   │       ├── schemas.py           # ExtractionJobRequest, ExtractionJobResponse
│   │   │       └── ai_service_client.py  # HTTP client → ai-service/
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       └── api/
│   │           ├── __init__.py
│   │           └── routers/
│   │               ├── __init__.py
│   │               └── extraction_router.py
│   │
│   ├── conflict/                       # Bounded Context: conflict detection
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   └── conflict.py         # Conflict (ORM model)
│   │   │   ├── enums.py                # ConflictType enum
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       └── conflict_repository.py
│   │   ├── application/
│   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── conflict_query_service.py
│   │   │   │   └── conflict_result_service.py
│   │   │   └── dtos/
│   │   │       └── __init__.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   ├── persistence/
│   │   │   │   ├── __init__.py
│   │   │   │   └── conflict_repository_impl.py
│   │   │   └── ai_client/
│   │   │       ├── __init__.py
│   │   │       ├── schemas.py          # ConflictJobRequest, ConflictJobResponse
│   │   │       └── ai_service_client.py  # HTTP client → ai-service/ (hoặc rule-based)
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       └── api/
│   │           ├── __init__.py
│   │           └── routers/
│   │               ├── __init__.py
│   │               └── conflict_router.py
│   │
│   ├── review/                         # Bounded Context: HITL review
│   │   ├── __init__.py
│   │   ├── domain/
│   │   │   ├── __init__.py
│   │   │   ├── entities/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── review_log.py       # ReviewLog (ORM model)
│   │   │   │   └── review_action.py    # ReviewAction enum
│   │   │   └── repositories/
│   │   │       ├── __init__.py
│   │   │       └── review_log_repository.py
│   │   ├── application/
│   │   │   ├── __init__.py
│   │   │   ├── services/
│   │   │   │   ├── __init__.py
│   │   │   │   ├── clause_review_service.py
│   │   │   │   └── conflict_resolution_service.py
│   │   │   └── dtos/
│   │   │       ├── __init__.py
│   │   │       └── review_request.py
│   │   ├── infrastructure/
│   │   │   ├── __init__.py
│   │   │   └── persistence/
│   │   │       ├── __init__.py
│   │   │       └── review_log_repository_impl.py
│   │   └── interfaces/
│   │       ├── __init__.py
│   │       └── api/
│   │           ├── __init__.py
│   │           └── routers/
│   │               ├── __init__.py
│   │               ├── review_router.py    # HITL review endpoints
│   │               └── approval_router.py   # Approval endpoint
│   │
│   └── migrations/                     # Alembic migrations (tại root của package)
│       ├── __init__.py
│       └── versions/
│           └── V1__init.sql            # Init schema: contracts, clauses, conflicts, review_logs
│
├── tests/
│   ├── __init__.py
│   ├── unit/
│   │   ├── __init__.py
│   │   ├── contract/
│   │   │   └── test_contract_upload_service.py
│   │   ├── extraction/
│   │   │   └── test_extraction_result_service.py
│   │   ├── conflict/
│   │   │   └── test_conflict_query_service.py
│   │   └── review/
│   │       └── test_clause_review_service.py
│   └── integration/
│       ├── __init__.py
│       ├── conftest.py                 # pytest fixtures: DB, MinIO mock
│       └── test_api_contracts.py
│
├── alembic.ini
├── alembic/
│   ├── env.py
│   ├── script.py.mako
│   └── versions/
│       └── V1__init_schema.py          # Auto-generated migration
│
├── requirements.txt
├── pyproject.toml
└── Dockerfile
```

### 3.5 Phạm vi Backend trong DDD

| Module | Làm gì | Không làm gì |
|---|---|---|
| `contract` | Upload, lưu file vào MinIO, quản lý job status | OCR, trích xuất |
| `extraction` | Nhận kết quả từ AI, lưu vào DB | Không gọi OCR trực tiếp |
| `extraction/infrastructure/ai_client` | Gửi job đến ai-service qua HTTP REST | Không xử lý AI model |
| `conflict` | Lưu kết quả xung đột từ AI, hoặc rule-based nếu BE tự implement | Không train model |
| `review` | Lưu HITL review log | Không làm AI |
| `shared` | Enum, exception, DTO, domain events | — |

### 3.6 Giao tiếp Backend ↔ AI Service

```
Backend (FastAPI)  ──HTTP REST──→  AI Service (FastAPI/Python)
     │                                    │
     ├── POST /jobs/extraction            ├── /jobs/extraction
     ├── GET  /jobs/{id}                 ├── /jobs/{id}
     ├── POST /jobs/conflict              ├── /jobs/conflict
     │                                    │
     └── (v1: Polling)                   └── (v1: Polling response)
```

- **Protocol:** REST/JSON qua HTTP (không dùng gRPC/message queue trong phase 1)
- **v1:** Backend poll AI Service để lấy kết quả
- **Authentication:** API Key đơn giản (商量 thêm với AI Engineer)

---

## 4. Vòng đời nghiệp vụ hợp đồng (State machine)

### 4.1 Luồng trạng thái chính

```
uploaded → processing → extracted → conflict_detected → pending_review → reviewed | approved
```

| Trạng thái | Mô tả |
|---|---|
| `uploaded` | File đã nhận, đang đợi gửi sang AI Service |
| `processing` | Đang OCR / Extraction |
| `extracted` | Đã trích xuất xong, đang kiểm tra xung đột |
| `conflict_detected` | Có xung đột phát hiện, cần review |
| `pending_review` | Đang chờ HITL review (có thể có hoặc không xung đột) |
| `reviewed` | Đã review xong, chờ approve |
| `approved` | Đã approve — hoàn thành |

### 4.2 Trạng thái lỗi

> TODO: Mô tả trạng thái lỗi
> ```
> failed → error_message (chi tiết lỗi lưu trong bảng contracts)
> ```

### 4.3 Ràng buộc nghiệp vụ

> TODO: Điền nội dung
> - Giới hạn file: tối đa 50MB, chỉ chấp nhận PDF
> - Tên file tiếng Việt: xử lý encoding không lỗi font
> - Batch upload: 1 item lỗi không fail cả lô (chi tiết xử lý như thế nào)

---

## 5. Data model / Database schema

> **Phiên bản đã chốt:** v1.0 · 2026-09-17 (sau P0 optimistic concurrency + 2 concern)
>
> **DDL canonical (SQL file):** `docs/DOC-04b-postgres-schema.sql` — dùng để sinh Alembic migration V1.
>
> **Nguyên tắc cứng:**
> - Kết quả máy (`document_text`, `ocr_line`, `citation`, `clause_node`, `fact`, `finding`, `finding_side`) và audit (`review_action`, `job_event`, `usage_ledger`, `dossier_approval`) chỉ INSERT — trigger `forbid_mutation()` chặn UPDATE/DELETE, role ứng dụng không có quyền UPDATE/DELETE trên các bảng này.
> - **Optimistic concurrency** cho review: `review_item.version INT NOT NULL DEFAULT 1`. Client echo `base_version`; server UPDATE atomic với `WHERE version = base_version`. Mismatch (0 row affected) → 409.
> - **Ngày hiệu lực/ký** lưu trực tiếp trên `document` (`signing_date`, `effective_date`) — không tính động từ `fact` khi query. S7 cập nhật các cột này sau khi trích xuất & validate fact ngày.
> - ID có tiền tố theo loại (`dos_`, `doc_`, `pg_`, `run_`, `ln_`, `cit_`, `fct_`, `fnd_`, `ri_`, `ra_`) — ULID, sắp xếp theo thời gian.
> - Bbox dùng **Canonical Page Space (CPS)**: `[x0, y0, x1, y1]` chuẩn hóa 0..1, gốc trên-trái sau khi áp `/Rotate`.
> - Mọi cột thời gian là `TIMESTAMPTZ` UTC.

### 5.0 ERD rút gọn

```
batch 1─* job 1─* pipeline_run 1─* job_step
                              ├─* usage_ledger
                              └─* task
dossier 1─* document 1─* page 1─* ocr_line
              │              └─* page_step_stat
              ├─* clause_node (self-ref cha-con)
              ├─* fact 1─1 citation
              └─* annex_link *─1 document(contract)
dossier 1─* finding 1─* finding_side *─1 citation
dossier 1─* review_item 1─* review_action *─1 app_user
dossier 1─* dossier_approval
```

### 5.1 DDL chốt cuối — xem `docs/DOC-04b-postgres-schema.sql`

DDL đầy đủ 23 bảng + 27 index + trigger + view nằm trong file SQL. Bảng tóm tắt bên dưới chỉ liệt kê cột đặc biệt & ràng buộc quan trọng.

| # | Bảng | Cột đặc biệt / ràng buộc | Bất biến? |
|---|---|---|---|
| 1 | `app_user` | `role` enum, `password_hash` (argon2) | Không |
| 2 | `batch` | `auto_paused` | Không |
| 3 | `dossier` | `has_conflicts` | Không |
| 4 | `document` | **`signing_date DATE`**, **`effective_date DATE`**, `role` enum, `sha256`, `page_count` | Không |
| 5 | `job` | `status` enum, `current_run_id` FK → `pipeline_run` | Không |
| 6 | `pipeline_run` | `config_snapshot JSONB`, `pipeline_version`, `git_sha` | Không |
| 7 | `job_step` | `UNIQUE(run_id, document_id, step)` checkpoint | Không |
| 8 | `task` | `FOR UPDATE SKIP LOCKED` qua index `idx_task_ready` | Không |
| 9 | `page` | `kind` enum, `transform JSONB`, `rotation` | Không |
| 10 | `page_step_stat` | `duration_ms`, `cache_hit` | Không |
| 11 | `document_text` | `UNIQUE(document_id, run_id)` | **Có** |
| 12 | `ocr_line` | `doc_char_start/end`, `words JSONB`, `flags JSONB` | **Có** |
| 13 | `citation` | `segments JSONB`, `quote_sha256` | **Có** |
| 14 | `clause_node` | `parent_id` self-ref, `stable_path` | **Có** |
| 15 | `fact` | `extractor`, `validation_status`, `citation_id` FK | **Có** |
| 16 | `annex_link` | `annex_sequence`, `effective_date`, `score` | **Có** |
| 17 | `finding` | `disposition`, `severity`, `scope` | **Có** |
| 18 | `finding_side` | `UNIQUE(finding_id, side)`, `citation_id` cả 2 phía | **Có** |
| 19 | `review_item` | **`version INT NOT NULL DEFAULT 1`** (P0), `target_type`, `priority` | Không (version tăng) |
| 20 | `review_action` | **`base_version INT NOT NULL`** (echo từ client), `corrected_value/bbox`, `action` enum | **Có** |
| 21 | `dossier_approval` | `snapshot_sha256`, `comment` | **Có** |
| 22 | `job_event` | `from_status`, `to_status`, `actor` | **Có** |
| 23 | `usage_ledger` | `cost_usd NUMERIC(12,6)`, `price_version` | **Có** |

### 5.2 Optimistic Concurrency — luồng & ràng buộc (P0-05)

**Đặc tả:**
- `review_item.version` là số nguyên đơn, tăng mỗi khi có `review_action` được ghi nhận cho item đó.
- Mỗi request `POST /review-items/{id}/actions` **bắt buộc** gửi `base_version` (int, min 1).
- Server thực thi trong **một transaction**:

```sql
UPDATE review_item
SET version = version + 1,
    status = CASE WHEN $1 = 'needs_more_evidence'
                  THEN 'awaiting_evidence' ELSE 'resolved' END,
    updated_at = now()
WHERE id = :item_id
  AND version = :base_version
RETURNING version, status;
```

- Nếu `RETURNING` trả 0 dòng → **409 Conflict**.
- Nếu 1 dòng → INSERT `review_action` với `base_version = :base_version`.
- `Idempotency-Key` (header) cho phép retry trong 60s với cùng payload trả về cùng response.

**Tại sao đơn giản hơn revision chain:**
- Một `review_item` ↔ một target (fact/finding/clause…) trong một run. Không cần revision chain dài trên `review_action`.
- `base_version` đủ để phát hiện ghi đè lặng lẽ — A và B cùng đọc `version=3`, A gửi với `base_version=3` thành công → `version=4`. B gửi với `base_version=3` → 0 rows → 409.
- Audit trail vẫn đầy đủ qua `review_action` (append-only) — biết ai sửa cái gì lúc nào.

### 5.3 Ngày hiệu lực & `annex_sequence` — denormalize

- `document.signing_date`: ngày ký (từ fact `date.signing`).
- `document.effective_date`: ngày có hiệu lực (từ fact `date.effective`).
- Cả hai nullable — không phải hợp đồng nào cũng có đủ.
- **S7** sau khi trích xuất fact ngày & validate sẽ UPDATE ngược lên `document` (không qua `fact`).
- **S8** dùng `effective_date` (fallback `signing_date`, fallback `uploaded_at`) để sắp xếp `annex_sequence` — query `ORDER BY` không join `fact`.
- Index phụ trợ: `idx_document_order(dossier_id, role, order_index)` + filter thêm ở application layer.

### 5.4 Bộ Indexes bắt buộc (27 index)

DDL đầy đủ ở `docs/DOC-04b-postgres-schema.sql` §7. Tóm tắt:

| Index | Bảng | Cột | Phục vụ |
|---|---|---|---|
| `idx_document_dossier_id` | document | `dossier_id` | List tài liệu của dossier |
| `idx_document_order` | document | `dossier_id, role, order_index` | Sort tài liệu theo thứ tự |
| `idx_page_document_id` | page | `document_id` | List trang |
| `idx_job_dossier_id` | job | `dossier_id` | List job của dossier |
| `idx_job_status` | job | `status` | Filter trạng thái |
| `idx_job_step_run_id` | job_step | `run_id` | Tra cứu checkpoint theo run |
| `idx_task_ready` | task | `priority, run_after` WHERE status='queued' | Worker dequeue |
| `idx_task_job_id` | task | `job_id` | Tra cứu task theo job |
| `idx_ocr_line_page_run` | ocr_line | `page_id, run_id` | API OCR theo trang+run |
| `idx_citation_document_run` | citation | `document_id, run_id` | API resolve citation |
| `idx_clause_node_doc_run` | clause_node | `document_id, run_id` | API cây điều khoản |
| `idx_fact_document_run` | fact | `document_id, run_id` | API facts |
| `idx_fact_key` | fact | `key` | Lọc theo key |
| `idx_fact_citation_id` | fact | `citation_id` | Join fact↔citation |
| `idx_finding_dossier_run` | finding | `dossier_id, run_id` | API findings |
| `idx_finding_side_finding_id` | finding_side | `finding_id` | 2 phía của finding |
| `idx_finding_side_fact_id` | finding_side | `fact_id` | Ngược từ fact |
| `idx_finding_side_citation_id` | finding_side | `citation_id` | Ngược từ citation |
| `idx_review_item_dossier` | review_item | `dossier_id, status` | Queue review |
| `idx_review_item_target` | review_item | `target_type, target_id` | Lookup theo target |
| `idx_review_action_item` | review_action | `review_item_id, created_at DESC` | Lịch sử action theo item |
| `idx_usage_ledger_run` | usage_ledger | `run_id` | Đo chi phí theo run |
| `idx_usage_ledger_dossier` | usage_ledger | `dossier_id` | Đo chi phí theo dossier |

### 5.5 View nghiệp vụ

Xem DDL §9 trong `docs/DOC-04b-postgres-schema.sql`:

- `v_conflict` — finding cần reviewer (`disposition IN (comparable_difference, candidate_amendment, insufficient_evidence) OR confidence < 0.6`).
- `v_fact_effective` — fact + action mới nhất qua `review_item.version`. Có `current_item_version` cho client echo.

### 5.6 Lưu ý quan trọng (v1.0)

> - **bbox** lưu `JSONB` dạng `[x0,y0,x1,y1]` theo Canonical Page Space (CPS, 0..1).
> - **File gốc** lưu vào `BlobStore` (`./data/blobs/pdf/<sha256>.pdf`), DB chỉ giữ URI.
> - **Optimistic concurrency**: client gửi `base_version`, server UPDATE atomic với `WHERE version = :base_version`. 0 rows → 409.
> - **Ngày hiệu lực/ký**: lưu trên `document.signing_date` / `document.effective_date`, cập nhật ở S7.
> - **Không lưu file nhị phân trong PostgreSQL** — artifact ở `./data/artifacts/<run_id>/...`.
> - Mọi cột thời gian là `TIMESTAMPTZ` UTC; client convert theo locale.
> - Migration quản lý bằng **Alembic** (theo `backend/CONTEXT.md` mục 3.4); `docs/DOC-04b-postgres-schema.sql` là V1 ban đầu.

### 5.2 Bảng `batch`

```sql
CREATE TABLE batch (
    id              TEXT PRIMARY KEY,                     -- prefix "btc_"
    name            TEXT NOT NULL,
    created_by      TEXT NOT NULL REFERENCES app_user(id),
    auto_paused     BOOLEAN NOT NULL DEFAULT false,
    auto_pause_reason TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX batch_created_at_idx ON batch(created_at DESC);
```

### 5.3 Bảng `dossier`

```sql
CREATE TABLE dossier (
    id              TEXT PRIMARY KEY,                     -- prefix "dos_"
    name            TEXT NOT NULL,
    batch_id        TEXT REFERENCES batch(id),
    has_conflicts   BOOLEAN NOT NULL DEFAULT false,
    latest_job_id   TEXT,                                 -- FK added after job exists
    created_by      TEXT NOT NULL REFERENCES app_user(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX dossier_batch_idx         ON dossier(batch_id) WHERE batch_id IS NOT NULL;
CREATE INDEX dossier_has_conflicts_idx ON dossier(has_conflicts) WHERE has_conflicts;
CREATE INDEX dossier_created_at_idx    ON dossier(created_at DESC);
```

### 5.4 Bảng `document`

```sql
CREATE TABLE document (
    id              TEXT PRIMARY KEY,                     -- prefix "doc_"
    dossier_id      TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    role            TEXT NOT NULL CHECK (role IN ('contract','annex')),
    order_index     INTEGER NOT NULL,
    filename        TEXT NOT NULL,
    sha256          TEXT NOT NULL,                        -- content addressing
    blob_uri        TEXT NOT NULL,                        -- data/blobs/pdf/<sha256>.pdf
    page_count      INTEGER NOT NULL,
    lang_detected   TEXT,                                 -- 'vi'|'en'|'bilingual'
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (dossier_id, order_index)
);
CREATE INDEX document_dossier_idx ON document(dossier_id);
CREATE INDEX document_sha256_idx  ON document(sha256);     -- dedup lookup
```

### 5.5 Bảng `page`

```sql
CREATE TABLE page (
    id              TEXT PRIMARY KEY,                     -- prefix "pg_"
    document_id     TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    page_no         INTEGER NOT NULL,
    kind            TEXT NOT NULL CHECK (kind IN ('native','scanned','hybrid')),
    width_pt        REAL NOT NULL,
    height_pt       REAL NOT NULL,
    rotation        INTEGER NOT NULL DEFAULT 0 CHECK (rotation IN (0,90,180,270)),
    mediabox        JSONB NOT NULL,
    cropbox         JSONB NOT NULL,
    transform       JSONB NOT NULL DEFAULT '{}'::jsonb,   -- ma trận M của S3
    render_uri      TEXT,
    preview_uri     TEXT,
    render_dpi      INTEGER NOT NULL DEFAULT 300,
    features        JSONB NOT NULL DEFAULT '{}'::jsonb,   -- text_chars, text_quality, image_coverage, blur_score, skew_deg
    quality         JSONB NOT NULL DEFAULT '{}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (document_id, page_no)
);
CREATE INDEX page_document_idx ON page(document_id);
CREATE INDEX page_kind_idx     ON page(kind);
```

### 5.6 Bảng `job` (điều phối, không bất biến)

```sql
CREATE TABLE job (
    id              TEXT PRIMARY KEY,                     -- prefix "job_"
    dossier_id      TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    batch_id        TEXT REFERENCES batch(id),
    status          TEXT NOT NULL CHECK (status IN (
                        'uploaded','processing','extracted','pending_review',
                        'reviewed','approved','failed')),
    current_run_id  TEXT,                                 -- FK after pipeline_run
    has_conflicts   BOOLEAN NOT NULL DEFAULT false,
    error_code      TEXT,
    error_detail    JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX job_dossier_idx      ON job(dossier_id, created_at DESC);
CREATE INDEX job_status_idx       ON job(status);
CREATE INDEX job_batch_status_idx ON job(batch_id, status) WHERE batch_id IS NOT NULL;

ALTER TABLE dossier
    ADD CONSTRAINT dossier_latest_job_fk FOREIGN KEY (latest_job_id) REFERENCES job(id);
```

### 5.7 Bảng `job_event` (audit, append-only)

```sql
CREATE TABLE job_event (
    id              BIGSERIAL PRIMARY KEY,
    job_id          TEXT NOT NULL REFERENCES job(id),
    from_status     TEXT,
    to_status       TEXT NOT NULL,
    actor           TEXT NOT NULL,                        -- 'system' | user_id
    reason          TEXT,
    payload         JSONB,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX job_event_job_idx ON job_event(job_id, created_at DESC);
```

### 5.8 Bảng `pipeline_run`

```sql
CREATE TABLE pipeline_run (
    id                TEXT PRIMARY KEY,                   -- prefix "run_"
    job_id            TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    dossier_id        TEXT NOT NULL REFERENCES dossier(id),
    status            TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','dead')),
    config_snapshot   JSONB NOT NULL,                     -- OCR mode, model, prompt versions, thresholds, git_sha
    pipeline_version  TEXT NOT NULL,
    git_sha           TEXT,
    trace_id          TEXT,
    started_at        TIMESTAMPTZ,
    finished_at       TIMESTAMPTZ,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX pipeline_run_job_idx     ON pipeline_run(job_id, created_at DESC);
CREATE INDEX pipeline_run_dossier_idx ON pipeline_run(dossier_id, created_at DESC);

ALTER TABLE job
    ADD CONSTRAINT job_current_run_fk FOREIGN KEY (current_run_id) REFERENCES pipeline_run(id);
```

### 5.9 Bảng `job_step` (checkpoint)

```sql
CREATE TABLE job_step (
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id) ON DELETE CASCADE,
    document_id     TEXT REFERENCES document(id),
    step            TEXT NOT NULL CHECK (step IN ('S0','S1','S2','S3','S4','S5','S6','S7','S8','S9','S10')),
    status          TEXT NOT NULL CHECK (status IN ('queued','running','succeeded','failed','retrying','skipped')),
    attempt         INTEGER NOT NULL DEFAULT 0,
    pages           INTEGER,
    duration_ms     INTEGER,
    error_code      TEXT,
    metrics         JSONB,
    started_at      TIMESTAMPTZ,
    finished_at     TIMESTAMPTZ,
    PRIMARY KEY (run_id, document_id, step)
);
CREATE INDEX job_step_status_idx ON job_step(status);
```

### 5.10 Bảng `task` (hàng đợi trên PostgreSQL)

```sql
CREATE TABLE task (
    id            BIGSERIAL PRIMARY KEY,
    kind          TEXT NOT NULL,
    job_id        TEXT NOT NULL REFERENCES job(id) ON DELETE CASCADE,
    batch_id      TEXT REFERENCES batch(id),
    payload       JSONB NOT NULL DEFAULT '{}'::jsonb,
    traceparent   TEXT,
    status        TEXT NOT NULL DEFAULT 'queued' CHECK (status IN ('queued','running','succeeded','failed','dead')),
    priority      INTEGER NOT NULL DEFAULT 100,
    attempts      INTEGER NOT NULL DEFAULT 0,
    max_attempts  INTEGER NOT NULL DEFAULT 3,
    run_after     TIMESTAMPTZ NOT NULL DEFAULT now(),
    locked_by     TEXT,
    locked_at     TIMESTAMPTZ,
    heartbeat_at  TIMESTAMPTZ,
    last_error    JSONB,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX task_ready_idx ON task(priority, run_after) WHERE status = 'queued';
CREATE INDEX task_running_idx ON task(heartbeat_at) WHERE status = 'running';
```

### 5.11 Bảng `page_step_stat`

```sql
CREATE TABLE page_step_stat (
    id            BIGSERIAL PRIMARY KEY,
    page_id       TEXT NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    run_id        TEXT NOT NULL REFERENCES pipeline_run(id),
    step          TEXT NOT NULL,
    engine        TEXT NOT NULL,
    duration_ms   INTEGER NOT NULL,
    cache_hit     BOOLEAN NOT NULL DEFAULT false,
    created_at    TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX page_step_stat_page_idx ON page_step_stat(page_id);
CREATE INDEX page_step_stat_run_idx  ON page_step_stat(run_id, step);
```

### 5.12 Bảng `document_text` (bất biến)

```sql
CREATE TABLE document_text (
    document_id    TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id         TEXT NOT NULL REFERENCES pipeline_run(id),
    text           TEXT NOT NULL,                         -- NFC, mỗi dòng kết thúc \n
    normalization  TEXT NOT NULL DEFAULT 'NFC',
    created_at     TIMESTAMPTZ NOT NULL DEFAULT now(),
    PRIMARY KEY (document_id, run_id)
);
```

### 5.13 Bảng `ocr_line` (bất biến — kết quả OCR)

```sql
CREATE TABLE ocr_line (
    id              TEXT PRIMARY KEY,                     -- prefix "ln_"
    page_id         TEXT NOT NULL REFERENCES page(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id),
    line_no         INTEGER NOT NULL,
    text            TEXT NOT NULL,                        -- NFC
    bbox            JSONB NOT NULL,                       -- CPS [x0,y0,x1,y1]
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    doc_char_start  INTEGER NOT NULL,
    doc_char_end    INTEGER NOT NULL,
    words           JSONB NOT NULL DEFAULT '[]'::jsonb,   -- [{text, bbox, char_span, bbox_source}]
    source          JSONB NOT NULL,                       -- {text, geometry, engine}
    flags           JSONB NOT NULL DEFAULT '{}'::jsonb,   -- {numeric_mismatch, unaligned, region}
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (doc_char_end > doc_char_start),
    UNIQUE (page_id, run_id, line_no)
);
CREATE INDEX ocr_line_page_idx ON ocr_line(page_id);
CREATE INDEX ocr_line_run_idx  ON ocr_line(run_id);

-- Trigger chặn UPDATE/DELETE
CREATE TRIGGER ocr_line_immutable
    BEFORE UPDATE OR DELETE ON ocr_line
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.14 Bảng `doc_table` & `table_cell` (bất biến)

```sql
CREATE TABLE doc_table (
    id              TEXT PRIMARY KEY,                     -- prefix "tbl_"
    document_id     TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id),
    page_no         INTEGER NOT NULL,
    bbox            JSONB NOT NULL,                       -- CPS
    rows_count      INTEGER NOT NULL,
    cols_count      INTEGER NOT NULL,
    has_borders     BOOLEAN NOT NULL,
    is_multi_page   BOOLEAN NOT NULL DEFAULT false,
    continued_from  TEXT REFERENCES doc_table(id),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX doc_table_document_idx ON doc_table(document_id);

CREATE TABLE table_cell (
    id              TEXT PRIMARY KEY,                     -- prefix "tcl_"
    table_id        TEXT NOT NULL REFERENCES doc_table(id) ON DELETE CASCADE,
    row_idx         INTEGER NOT NULL,
    col_idx         INTEGER NOT NULL,
    row_span        INTEGER NOT NULL DEFAULT 1,
    col_span        INTEGER NOT NULL DEFAULT 1,
    text            TEXT NOT NULL,
    bbox            JSONB NOT NULL,                       -- CPS
    is_header       BOOLEAN NOT NULL DEFAULT false,
    char_span_doc   INT4RANGE,                            -- pg range type
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX table_cell_table_idx ON table_cell(table_id, row_idx, col_idx);

CREATE TRIGGER doc_table_immutable
    BEFORE UPDATE OR DELETE ON doc_table
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER table_cell_immutable
    BEFORE UPDATE OR DELETE ON table_cell
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.15 Bảng `clause_node` & `clause_region` (bất biến)

```sql
CREATE TABLE clause_node (
    id              TEXT PRIMARY KEY,                     -- prefix "cln_"
    document_id     TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id),
    node_type       TEXT NOT NULL CHECK (node_type IN ('annex','article','clause','point','preamble','signature_block')),
    label           TEXT NOT NULL,                        -- "Điều 5"
    number          TEXT,
    title           TEXT,
    text            TEXT NOT NULL,
    lang            TEXT,                                 -- 'vi'|'en'|'bilingual'
    parent_id       TEXT REFERENCES clause_node(id),
    doc_char_start  INTEGER NOT NULL,
    doc_char_end    INTEGER NOT NULL,
    page_start      INTEGER NOT NULL,
    page_end        INTEGER NOT NULL,
    line_ids        JSONB NOT NULL DEFAULT '[]'::jsonb,
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    stable_path     TEXT NOT NULL,                        -- "annex-01/art-5/cl-2/pt-a"
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (doc_char_end > doc_char_start)
);
CREATE INDEX clause_node_document_idx ON clause_node(document_id);
CREATE INDEX clause_node_parent_idx   ON clause_node(parent_id);
CREATE INDEX clause_node_path_idx     ON clause_node(stable_path);

CREATE TABLE clause_region (
    id              TEXT PRIMARY KEY,                     -- prefix "clr_"
    clause_node_id  TEXT NOT NULL REFERENCES clause_node(id) ON DELETE CASCADE,
    page_no         INTEGER NOT NULL,
    bbox            JSONB NOT NULL,                       -- CPS
    bbox_source     TEXT NOT NULL CHECK (bbox_source IN ('native','detector','estimated','human')),
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX clause_region_node_idx ON clause_region(clause_node_id);

CREATE TRIGGER clause_node_immutable
    BEFORE UPDATE OR DELETE ON clause_node
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER clause_region_immutable
    BEFORE UPDATE OR DELETE ON clause_region
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.16 Bảng `citation` (bất biến — cốt lõi của BR-07/BR-08)

```sql
CREATE TABLE citation (
    id              TEXT PRIMARY KEY,                     -- prefix "cit_"
    document_id     TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id),
    quote           TEXT NOT NULL,
    quote_sha256    TEXT NOT NULL,
    segments        JSONB NOT NULL,                       -- [{page_no, line_id, char_start, char_end, bbox, bbox_level}]
    doc_char_start  INTEGER NOT NULL,
    doc_char_end    INTEGER NOT NULL,
    coord_system    JSONB NOT NULL DEFAULT '{"space":"CPS","range":"0..1","origin":"top-left","format":"x0,y0,x1,y1"}'::jsonb,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now(),
    CHECK (doc_char_end > doc_char_start)
);
CREATE INDEX citation_document_idx ON citation(document_id);
CREATE INDEX citation_run_idx      ON citation(run_id);

CREATE TRIGGER citation_immutable
    BEFORE UPDATE OR DELETE ON citation
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.17 Bảng `fact` (bất biến)

```sql
CREATE TABLE fact (
    id                  TEXT PRIMARY KEY,                 -- prefix "fct_"
    document_id         TEXT NOT NULL REFERENCES document(id) ON DELETE CASCADE,
    run_id              TEXT NOT NULL REFERENCES pipeline_run(id),
    key                 TEXT NOT NULL,                    -- 'price.total', 'party.name', ...
    fact_type           TEXT NOT NULL,                    -- money|date|duration|party|tax_code|quantity|text|...
    raw_text            TEXT NOT NULL,
    normalized_value    JSONB,
    context_clause_id   TEXT REFERENCES clause_node(id),
    context_text        TEXT,
    confidence          REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    extractor           TEXT NOT NULL,                    -- 'rule:money@1' | 'llm:gpt-5.6-terra@extract.v1'
    validation_status   TEXT NOT NULL DEFAULT 'passed' CHECK (validation_status IN ('passed','failed','skipped')),
    validation_notes    JSONB,
    citation_id         TEXT NOT NULL REFERENCES citation(id),
    trace_id            TEXT,
    observation_id      TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX fact_document_idx ON fact(document_id);
CREATE INDEX fact_key_idx      ON fact(key);
CREATE INDEX fact_clause_idx   ON fact(context_clause_id);

CREATE TRIGGER fact_immutable
    BEFORE UPDATE OR DELETE ON fact
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.18 Bảng `annex_link` (bất biến — BR-06 + concern 1)

```sql
CREATE TABLE annex_link (
    id                    TEXT PRIMARY KEY,               -- prefix "alnk_"
    dossier_id            TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    annex_document_id     TEXT NOT NULL REFERENCES document(id),
    contract_document_id  TEXT NOT NULL REFERENCES document(id),
    score                 REAL NOT NULL,
    status                TEXT NOT NULL CHECK (status IN ('linked','linked_needs_review','unlinked')),
    annex_sequence        INTEGER NOT NULL,               -- thứ tự hiệu lực
    effective_date        DATE,                            -- FIX: denormalized từ fact (concern 1)
    date_source           TEXT CHECK (date_source IN ('fact.date.signing','fact.date.effective','fallback_upload_order','none')),
    evidence_citation_id  TEXT REFERENCES citation(id),
    created_at            TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (annex_document_id)
);
CREATE INDEX annex_link_dossier_idx ON annex_link(dossier_id, annex_sequence);
CREATE INDEX annex_link_status_idx  ON annex_link(status);

CREATE TRIGGER annex_link_immutable
    BEFORE UPDATE OR DELETE ON annex_link
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.19 Bảng `finding` & `finding_side` (bất biến)

```sql
CREATE TABLE finding (
    id              TEXT PRIMARY KEY,                     -- prefix "fnd_"
    dossier_id      TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    run_id          TEXT NOT NULL REFERENCES pipeline_run(id),
    finding_type    TEXT NOT NULL CHECK (finding_type IN ('structured','semantic')),
    scope           TEXT NOT NULL CHECK (scope IN ('within_document','contract_annex','annex_annex')),
    key_or_topic    TEXT NOT NULL,
    disposition     TEXT NOT NULL CHECK (disposition IN (
                        'comparable_match','comparable_difference','candidate_amendment',
                        'not_comparable','insufficient_evidence')),
    severity        TEXT NOT NULL CHECK (severity IN ('high','medium','low')),
    confidence      REAL NOT NULL CHECK (confidence BETWEEN 0 AND 1),
    rationale       TEXT,
    method          TEXT NOT NULL,                        -- 'rule:money_compare@1' | 'llm:gpt-5.6-terra@semantic_compare.v1'
    trace_id        TEXT,
    observation_id  TEXT,
    created_at      TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX finding_dossier_idx     ON finding(dossier_id);
CREATE INDEX finding_disposition_idx ON finding(disposition) WHERE disposition IN ('comparable_difference','candidate_amendment','insufficient_evidence');
CREATE INDEX finding_severity_idx    ON finding(severity);

CREATE TABLE finding_side (
    finding_id      TEXT NOT NULL REFERENCES finding(id) ON DELETE CASCADE,
    side            TEXT NOT NULL CHECK (side IN ('a','b')),
    document_id     TEXT NOT NULL REFERENCES document(id),
    fact_id         TEXT REFERENCES fact(id),
    clause_node_id  TEXT REFERENCES clause_node(id),
    citation_id     TEXT NOT NULL REFERENCES citation(id),  -- BR-14: cả hai phía đều có citation
    value_snapshot  JSONB,
    PRIMARY KEY (finding_id, side)
);
CREATE INDEX finding_side_doc_idx ON finding_side(document_id);

CREATE TRIGGER finding_immutable
    BEFORE UPDATE OR DELETE ON finding
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
CREATE TRIGGER finding_side_immutable
    BEFORE UPDATE OR DELETE ON finding_side
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- View: Conflict = tập finding cần reviewer xử lý (DOC-03, không phải entity)
CREATE VIEW v_conflict AS
SELECT f.*
FROM finding f
WHERE f.disposition IN ('comparable_difference','candidate_amendment','insufficient_evidence')
   OR f.confidence < 0.6;
```

### 5.20 Bảng `review_item` (điều phối)

```sql
CREATE TABLE review_item (
    id                  TEXT PRIMARY KEY,                 -- prefix "ri_"
    dossier_id          TEXT NOT NULL REFERENCES dossier(id) ON DELETE CASCADE,
    run_id              TEXT NOT NULL REFERENCES pipeline_run(id),
    target_type         TEXT NOT NULL CHECK (target_type IN ('fact','finding','annex_link','clause_node','table_cell','citation')),
    target_id           TEXT NOT NULL,                    -- không FK cứng vì target có thể thuộc bảng bất biến
    reason              TEXT NOT NULL,
    priority            TEXT NOT NULL CHECK (priority IN ('P1','P2','P3')),
    status              TEXT NOT NULL DEFAULT 'open' CHECK (status IN ('open','awaiting_evidence','resolved')),
    -- OPTIMISTIC CONCURRENCY: revision hiệu lực của target (concern P0)
    current_revision_no INTEGER NOT NULL DEFAULT 0,       -- 0 = máy, 1..N = review_action
    source_trace_id     TEXT,
    source_observation_id TEXT,
    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    updated_at          TIMESTAMPTZ NOT NULL DEFAULT now(),
    UNIQUE (target_type, target_id, run_id)
);
CREATE INDEX review_item_dossier_idx    ON review_item(dossier_id);
CREATE INDEX review_item_dossier_state  ON review_item(dossier_id, status) WHERE status <> 'resolved';
CREATE INDEX review_item_priority_idx   ON review_item(priority) WHERE status <> 'resolved';
```

### 5.21 Bảng `review_action` (append-only + optimistic concurrency)

```sql
CREATE TABLE review_action (
    id                  TEXT PRIMARY KEY,                 -- prefix "ra_"
    review_item_id      TEXT NOT NULL REFERENCES review_item(id),
    target_type         TEXT NOT NULL CHECK (target_type IN ('fact','finding','annex_link','clause_node','table_cell','citation')),  -- mirror của review_item để query
    target_id           TEXT NOT NULL,
    action              TEXT NOT NULL CHECK (action IN ('confirm','correct','reject','needs_more_evidence')),
    corrected_value     JSONB,
    corrected_bbox      JSONB,                            -- theo CPS, dùng từ S2–3
    comment             TEXT,
    reviewer_id         TEXT NOT NULL REFERENCES app_user(id),

    -- OPTIMISTIC CONCURRENCY (concern P0): mỗi target có chuỗi revision đếm bằng số nguyên.
    -- base_action_id    : NULL nếu submit dựa trên giá trị máy (revision 0);
    --                     là id của action trước đó nếu submit dựa trên action đó.
    -- expected_revision_no : revision_no của action đang xem (NULL = xem máy).
    -- revision_no        : revision mới = expected + 1 (server gán, atomic).
    base_action_id      TEXT REFERENCES review_action(id),
    expected_revision_no INTEGER,                         -- NULL = dựa trên máy (rev=0)
    revision_no         INTEGER NOT NULL,                  -- 1, 2, 3, ...

    created_at          TIMESTAMPTZ NOT NULL DEFAULT now(),

    -- Constraint semantics: action 'correct' phải có corrected_value hoặc corrected_bbox
    CHECK (action <> 'correct' OR corrected_value IS NOT NULL OR corrected_bbox IS NOT NULL),
    -- base_action_id phải thuộc cùng target (enforce bằng trigger — xem dưới)
    CHECK (revision_no >= 1)
);
CREATE INDEX review_action_target_idx ON review_action(target_type, target_id, revision_no DESC);
CREATE INDEX review_action_item_idx   ON review_action(review_item_id, created_at DESC);
CREATE INDEX review_action_reviewer_idx ON review_action(reviewer_id, created_at DESC);

-- Append-only: không cho UPDATE/DELETE
CREATE TRIGGER review_action_immutable
    BEFORE UPDATE OR DELETE ON review_action
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();

-- Constraint: base_action_id (nếu có) phải cùng target với action mới
CREATE OR REPLACE FUNCTION check_review_action_base() RETURNS trigger AS $$
DECLARE
    base_target_type TEXT;
    base_target_id   TEXT;
BEGIN
    IF NEW.base_action_id IS NULL THEN
        RETURN NEW;
    END IF;
    SELECT target_type, target_id INTO base_target_type, base_target_id
    FROM review_action WHERE id = NEW.base_action_id;
    IF base_target_type IS NULL THEN
        RAISE EXCEPTION 'base_action_id % không tồn tại', NEW.base_action_id;
    END IF;
    IF base_target_type <> NEW.target_type OR base_target_id <> NEW.target_id THEN
        RAISE EXCEPTION 'base_action_id % thuộc target khác với action mới', NEW.base_action_id;
    END IF;
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

CREATE TRIGGER review_action_base_check
    BEFORE INSERT ON review_action
    FOR EACH ROW EXECUTE FUNCTION check_review_action_base();
```

**Server-side stored procedure để chốt optimistic concurrency:**

```sql
-- Trả về action_id mới nếu insert thành công, NULL nếu conflict (409).
-- expected_rev: revision hiệu lực hiện tại (0 = máy, hoặc revision_no của action mới nhất)
CREATE OR REPLACE FUNCTION submit_review_action(
    p_review_item_id   TEXT,
    p_target_type      TEXT,
    p_target_id        TEXT,
    p_action           TEXT,
    p_corrected_value  JSONB,
    p_corrected_bbox   JSONB,
    p_comment          TEXT,
    p_reviewer_id      TEXT,
    p_base_action_id   TEXT,        -- NULL nếu dựa trên máy
    p_expected_rev     INTEGER      -- NULL = dựa trên máy (rev=0)
) RETURNS TABLE(new_action_id TEXT, new_revision_no INTEGER) AS $$
DECLARE
    v_new_id TEXT;
    v_new_rev INTEGER;
    v_current_rev INTEGER;
BEGIN
    -- Lấy revision hiệu tại của target
    SELECT COALESCE(MAX(revision_no), 0) INTO v_current_rev
    FROM review_action
    WHERE target_type = p_target_type AND target_id = p_target_id;

    -- Kiểm tra concurrent update
    IF p_expected_rev IS DISTINCT FROM v_current_rev THEN
        RETURN;  -- trả về 0 row → API map sang 409
    END IF;

    v_new_rev := v_current_rev + 1;
    v_new_id  := 'ra_' || gen_random_uuid()::text;  -- hoặc ULID generator

    INSERT INTO review_action (
        id, review_item_id, target_type, target_id, action,
        corrected_value, corrected_bbox, comment, reviewer_id,
        base_action_id, expected_revision_no, revision_no
    ) VALUES (
        v_new_id, p_review_item_id, p_target_type, p_target_id, p_action,
        p_corrected_value, p_corrected_bbox, p_comment, p_reviewer_id,
        p_base_action_id, p_expected_rev, v_new_rev
    );

    -- Cập nhật trạng thái review_item
    IF p_action = 'needs_more_evidence' THEN
        UPDATE review_item SET status = 'awaiting_evidence', updated_at = now()
        WHERE id = p_review_item_id;
    ELSE
        UPDATE review_item
        SET status = 'resolved', current_revision_no = v_new_rev, updated_at = now()
        WHERE id = p_review_item_id;
    END IF;

    RETURN QUERY SELECT v_new_id, v_new_rev;
END;
$$ LANGUAGE plpgsql;
```

### 5.22 Bảng `dossier_approval` (append-only)

```sql
CREATE TABLE dossier_approval (
    id                TEXT PRIMARY KEY,                   -- prefix "apr_"
    dossier_id        TEXT NOT NULL REFERENCES dossier(id),
    run_id            TEXT NOT NULL REFERENCES pipeline_run(id),
    approved_by       TEXT NOT NULL REFERENCES app_user(id),
    approved_at       TIMESTAMPTZ NOT NULL DEFAULT now(),
    snapshot_sha256   TEXT NOT NULL,                      -- SHA-256 của export JSON
    comment           TEXT
);
CREATE INDEX dossier_approval_dossier_idx ON dossier_approval(dossier_id, approved_at DESC);

CREATE TRIGGER dossier_approval_immutable
    BEFORE UPDATE OR DELETE ON dossier_approval
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.23 Bảng `usage_ledger` (append-only, cost/usage)

```sql
CREATE TABLE usage_ledger (
    id                BIGSERIAL PRIMARY KEY,
    run_id            TEXT NOT NULL REFERENCES pipeline_run(id),
    dossier_id        TEXT NOT NULL,
    step              TEXT NOT NULL,                      -- 'ocr'|'extract'|'compare'
    provider          TEXT NOT NULL,                      -- 'openai'|'local'
    model_requested   TEXT NOT NULL,
    model_returned    TEXT,
    input_tokens      INTEGER NOT NULL DEFAULT 0,
    cached_tokens     INTEGER NOT NULL DEFAULT 0,
    output_tokens     INTEGER NOT NULL DEFAULT 0,
    reasoning_tokens  INTEGER,
    pages             INTEGER NOT NULL DEFAULT 0,
    cache_hit         BOOLEAN NOT NULL DEFAULT false,
    latency_ms        INTEGER,
    cost_usd          NUMERIC(12,6) NOT NULL,
    price_version     TEXT NOT NULL,                      -- version của pricing.yaml
    trace_id          TEXT,
    observation_id    TEXT,
    created_at        TIMESTAMPTZ NOT NULL DEFAULT now()
);
CREATE INDEX usage_ledger_run_idx       ON usage_ledger(run_id);
CREATE INDEX usage_ledger_dossier_idx   ON usage_ledger(dossier_id, created_at DESC);
CREATE INDEX usage_ledger_created_idx   ON usage_ledger(created_at DESC);

CREATE TRIGGER usage_ledger_immutable
    BEFORE UPDATE OR DELETE ON usage_ledger
    FOR EACH ROW EXECUTE FUNCTION forbid_mutation();
```

### 5.24 View giá trị hiệu lực (đã fix P0: dùng `revision_no` thay vì `created_at`)

```sql
-- View: giá trị hiệu lực của fact = giá trị của action có revision_no lớn nhất
CREATE VIEW v_fact_effective AS
SELECT f.id                AS fact_id,
       f.document_id,
       f.key,
       f.normalized_value  AS machine_value,
       CASE ra.action
           WHEN 'correct' THEN COALESCE(ra.corrected_value, f.normalized_value)
           WHEN 'reject'  THEN NULL
           ELSE f.normalized_value
       END                 AS effective_value,
       COALESCE(ra.action, 'unreviewed')                AS review_state,
       ra.corrected_bbox,
       ra.reviewer_id,
       ra.created_at       AS reviewed_at,
       ra.revision_no      AS current_revision_no,         -- FIX P0
       ra.id               AS current_action_id,           -- FIX P0: client echo cái này
       f.citation_id       AS original_citation_id
FROM fact f
LEFT JOIN LATERAL (
    SELECT a.*
    FROM review_action a
    WHERE a.target_type = 'fact' AND a.target_id = f.id
    ORDER BY a.revision_no DESC                            -- FIX P0: thay vì created_at DESC
    LIMIT 1
) ra ON TRUE;

-- Tương tự cho clause_node, finding, table_cell, citation, annex_link
-- (mỗi cái một view; định nghĩa tương tự, đổi bảng gốc)
```

### 5.25 View tóm tắt batch

```sql
---

## 6. API Spec (DOC-05)

> **File gốc OpenAPI 3.1:** `docs/DOC-05-api-spec.yaml` (1645 dòng, đã viết xong Sprint 1)
>
> Endpoint map nhanh theo tag OpenAPI — xem file YAML để biết request/response đầy đủ.

### 6.1 Nhóm Upload & Quản lý

| Method | Path | Mô tả |
|---|---|---|
| POST | `/api/v1/dossiers` | Tạo dossier + upload multipart (`contract` + `annexes[]`) → 202 |
| GET | `/api/v1/dossiers` | List, filter `status`, `has_conflicts`, `batch_id`, `q` |
| GET | `/api/v1/dossiers/{id}` | Chi tiết dossier |
| POST | `/api/v1/dossiers/{id}/reprocess` | Tạo job mới (giữ job cũ) |
| POST | `/api/v1/batches` | Upload ZIP + manifest.csv → 202 |
| GET | `/api/v1/batches/{id}/summary` | Done / Needs Review / Failed / In progress + cost |
| POST | `/api/v1/batches/{id}/resume` | Bỏ `auto_paused` |

### 6.2 Nhóm Status / Trích xuất

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/v1/jobs/{id}` | Trạng thái job, tiến độ, link trace |
| POST | `/api/v1/jobs/{id}/retry` | Retry từ bước lỗi |
| GET | `/api/v1/documents/{id}/pages` | Metadata các trang |
| GET | `/api/v1/documents/{id}/pages/{no}/image?variant=preview\|render` | Ảnh trang |
| GET | `/api/v1/documents/{id}/pages/{no}/ocr?level=line\|word` | OCR text + bbox |
| GET | `/api/v1/documents/{id}/clauses` | Cây điều khoản + region |
| GET | `/api/v1/documents/{id}/tables` | Bảng có cấu trúc |
| GET | `/api/v1/dossiers/{id}/facts?effective=true` | Fact + giá trị hiệu lực + `version` |
| GET | `/api/v1/dossiers/{id}/findings` | Toàn bộ finding |
| GET | `/api/v1/dossiers/{id}/conflicts` | Finding cần reviewer (= view v_conflict) |
| GET | `/api/v1/citations/{id}` | Resolve citation (URL ảnh + bbox) |

### 6.3 Nhóm HITL Review

| Method | Path | Mô tả |
|---|---|---|
| GET | `/api/v1/dossiers/{id}/review-items` | Hàng đợi review |
| GET | `/api/v1/review-items/{id}` | Chi tiết item + `version` |
| **POST** | **`/api/v1/review-items/{id}/actions`** | **Submit action — bắt buộc `base_version`** |
| POST | `/api/v1/dossiers/{id}/approve` | Approve (chỉ khi job=`reviewed`) |
| GET | `/api/v1/dossiers/{id}/audit` | Dòng thời gian job_event + review_action |
| GET | `/api/v1/dossiers/{id}/export` | Export JSON kết quả + effective |

### 6.4 Format response chuẩn

```json
{
  "data": { ... },
  "meta": {
    "request_id": "req_01J...",
    "trace_id": "0a1b2c3d...",
    "timestamp": "2026-09-17T10:30:00Z"
  }
}
```

Lỗi dùng `application/problem+json` (RFC 9457):

```json
{
  "type": "about:blank",
  "title": "Conflict",
  "status": 409,
  "code": "REVISION_CONFLICT",
  "detail": "Item was modified by another reviewer (current version: 4).",
  "trace_id": "0a1b2c3d..."
}
```

### 6.5 Ví dụ Review Action (Optimistic Concurrency)

**Request:**
```http
POST /api/v1/review-items/ri_01J9ZT7W2C/actions
Content-Type: application/json
Idempotency-Key: 5d7a0c1e-7f7e-4a39-9d1f-2d7c3b8f9a10

{
  "action": "correct",
  "base_version": 3,
  "corrected_value": { "amount": 120000000, "currency": "VND" },
  "corrected_bbox": null,
  "comment": "OCR đọc thiếu chữ số 2; đối chiếu dòng Bằng chữ."
}
```

**Server xử lý (transaction):**

```sql
UPDATE review_item
SET version = version + 1,
    status = 'resolved',
    updated_at = now()
WHERE id = 'ri_01J9ZT7W2C'
  AND version = 3
RETURNING version, status;
-- 0 rows → 409 Conflict
-- 1 row  → INSERT review_action (base_version = 3)
```

**Response 200:**
```json
{
  "data": {
    "review_action_id": "ra_01J9ZT8B4K",
    "item_status": "resolved",
    "new_version": 4,
    "effective_value": { "amount": 120000000, "currency": "VND" },
    "machine_value": { "amount": 100000000, "currency": "VND" },
    "job_status": "pending_review",
    "open_items_remaining": 5,
    "idempotent_replay": false
  },
  "meta": { "request_id": "...", "trace_id": "...", "timestamp": "..." }
}
```

**Response 409:**
```json
{
  "data": {
    "error": {
      "code": "REVISION_CONFLICT",
      "message": "Item was modified by another reviewer before yours."
    },
    "current_state": {
      "current_version": 4,
      "effective_value": { "amount": 110000000, "currency": "VND" },
      "review_state": "corrected"
    }
  },
  "meta": { "request_id": "...", "trace_id": "...", "timestamp": "..." }
}
```

### 6.6 Conventions chung

| Chủ đề | Quy ước |
|---|---|
| Base URL | `/api/v1` |
| Định dạng | JSON UTF-8, thời gian ISO 8601 có timezone |
| Lỗi | `application/problem+json` (RFC 9457) + `code` nội bộ + `trace_id` |
| Idempotency | Header `Idempotency-Key` cho POST; lặp lại trả cùng response trong 60s |
| Pagination | Cursor (`?cursor=&limit=`), mặc định 50, tối đa 200 |
| Truy vết | Header `X-Trace-Id` để debug |
| Xác thực | Session cookie HttpOnly (`ci_session`), SameSite=Lax |
| Tài liệu UI | `/docs` (Swagger UI), `/redoc` |
| Đổi version | Breaking change → `/api/v2` |

---

## 7. Contract kỹ thuật Backend ↔ AI Service

> **Mục đích:** Định nghĩa rõ interface giao tiếp giữa Backend và AI Service để hai bên develop độc lập.

### 7.1 Interface 1: OCR/IDP Extraction

> TODO: Định nghĩa request/response schema
> ```yaml
> # Request
> {
>   "job_id": "...",
>   "file_url": "...",
>   "filename": "..."
> }
>
> # Response
> {
>   "job_id": "...",
>   "status": "success|failed",
>   "pages": [...],
>   "clauses": [...]
> }
> ```

### 7.2 Interface 2: Conflict Detection

> TODO: Định nghĩa request/response schema
> ```yaml
> # Request
> {
>   "job_id": "...",
>   "contract_id": "...",
>   "clauses": [...]
> }
>
> # Response
> {
>   "job_id": "...",
>   "status": "success|failed",
>   "conflicts": [...]
> }
> ```

### 7.3 Format lỗi chung

> TODO: Quy định format lỗi khi AI Service trả về failed
> ```json
> {
>   "job_id": "...",
>   "status": "failed",
>   "error_code": "...",
>   "error_message": "..."
> }
> ```

### 7.4 Vấn đề cần AI Engineer xác nhận

> TODO: Liệt kê các câu hỏi/issue đang chờ AI Engineer
> Ví dụ:
> - Sync hay async (callback / poll / webhook)?
> - Retry policy như thế nào?
> - Authentication giữa BE và AI Service?
> - MinIO bucket cho file gốc đặt ở đâu?

---

## 8. Way of Working / quy tắc dự án

### 8.1 Báo cáo & Tracker

> TODO: Điền nội dung
> - Nơi gửi daily report: (Slack channel / email / tool nào)
> - Nơi cập nhật tracker: (Jira / Notion / Google Sheet / tool nào)
> - Bằng chứng GitHub: mỗi commit cần associate với task nào

### 8.2 Quy tắc code

> TODO: Điền nội dung
> - Mentor phải duyệt kiến trúc trước khi code
> - Chỉ dùng repo do mentor cấp (không tự tạo repo)
> - Tối đa 3 repo cho toàn dự án: (liệt kê)
> - Branch naming convention: `feature/backend-<task-name>`, `hotfix/<name>`
> - PR yêu cầu ít nhất 1 reviewer

### 8.3 Coding standards

> TODO: Điền nội dung
> - Code style (PEP 8 / Ruff)
> - Test coverage tối thiểu
> - Security: không commit secrets, dùng environment variables

---

## 9. Trạng thái hiện tại / Đã quyết định

### 9.1 Đã quyết định ✅

| # | Quyết định | Ngày |
|---|---|---|
| 1 | Monolith + DDD | 2026-09-16 |
| 2 | Backend: Python 3.11 + FastAPI (không phải Java/Spring Boot) | 2026-09-16 |
| 3 | AI Service: Python FastAPI, tách riêng backend | 2026-09-16 |
| 4 | Giao tiếp BE ↔ AI: REST HTTP (v1: Polling) | 2026-09-16 |
| 5 | Database: PostgreSQL + SQLAlchemy | 2026-09-16 |
| 6 | Object storage: MinIO (không lưu file trong DB) | 2026-09-16 |
| 7 | Bbox lưu dạng JSONB | 2026-09-16 |
| 8 | Tối đa 3 repo (BE / FE / AI), do mentor cấp | 2026-09-16 |
| 9 | Không microservices trong phase đồ án | 2026-09-16 |
| 10 | Migration: Alembic | 2026-09-16 |

### 9.2 Đã chốt bổ sung (lock schema v1.0 — 2026-09-17)

| # | Quyết định | Ngày | Ghi chú |
|---|---|---|---|
| 11 | Schema DB v1.0 khớp DOC-04 | 2026-09-17 | `docs/DOC-04b-postgres-schema.sql` (DDL canonical) + `backend/CONTEXT.md` mục 5 |
| 12 | **Optimistic concurrency cho review** (P0-05) | 2026-09-17 | `review_item.version INT NOT NULL DEFAULT 1`. Client echo `base_version`; server `UPDATE … WHERE version = :base_version`. 0 rows → 409. Không stored procedure, không revision chain. |
| 13 | **Ngày hiệu lực/kyý denormalize** (concern 1) | 2026-09-17 | `document.signing_date DATE` + `document.effective_date DATE`. Cập nhật ở S7, không tính động khi query. |
| 14 | **Indexes đầy đủ** (concern 2) | 2026-09-17 | 25 index (13 FK, 6 status filter, 6 composite citation/effective). Danh sách đầy đủ ở `DOC-04b-postgres-schema.sql` §8. |
| 15 | Conflict là **view** `v_conflict` | 2026-09-17 | Theo DOC-03; không tạo bảng `conflict` riêng |
| 16 | Effective value dùng `review_item.version` | 2026-09-17 | `v_fact_effective` join theo `review_item`, expose `current_item_version` cho client echo |
| 17 | Alembic migration V1 | 2026-09-17 | Sinh từ `DOC-04b-postgres-schema.sql` — chưa sinh, backlog Sprint 2 |

### 9.3 Đang chờ xác nhận ⏳ (chưa resolve)

| # | Vấn đề | Chờ ai | Ghi chú mới |
|---|---|---|---|
| 1 | **Authentication BE↔AI:** API Key hay JWT? | AI Engineer | DOC-04 dùng OTel + session cookie local; BE↔AI trong cùng compose nên mạng nội bộ, có thể chỉ cần shared secret |
| 2 | **AI Service URL:** Self-hosted hay cloud (OpenAI/Anthropic)? | AI Engineer | DOC-04 mục 0.3 đã chốt GPT-5.6 Terra (cần mentor duyệt M1); chế độ `local_only` luôn chạy được |
| 3 | **OCR Engine:** PaddleOCR, EasyOCR, hay cloud API? | AI Engineer | DOC-04 D3: hybrid detector local + Terra, ADR-003 |
| 4 | **LLM Model:** ChatGPT API, Claude API, hay open-source (LLaMA)? | AI Engineer | DOC-04 chốt: `gpt-5.6-terra` (reasoning effort `low`); fallback local qua Ollama |
| 5 | **Conflict Detection:** Rule-based (BE tự làm) hay AI (AI Engineer)? | Team thống nhất | DOC-04 6.10: comparator có cấu trúc (rule) + comparator ngữ nghĩa (LLM có grounding). BE có thể implement rule đầy đủ; semantic dùng AI Service |
| 6 | **MinIO:** Self-hosted hay dùng S3 bucket có sẵn? | Mentor | DOC-04 D11: `./data` qua interface `BlobStore`, MinIO chỉ là lựa chọn khi scale |
| 7 | **Frontend:** React hay Vue? | Frontend Engineer | DOC-04 D10: React 18 + TypeScript + Vite |
| 8 | **Chính sách ưu tiên hợp đồng – phụ lục** (DOC-04 M3) | Mentor | Mặc định: chỉ hiển thị "đề xuất" trong UI |
| 9 | **Ngưỡng metric chọn OCR engine** (DOC-04 M4) | Mentor | Ví dụ: CER ≤ 5%, VDA ≥ 97%, line Hit@0.5 ≥ 95% |
| 10 | **Triển khai Langfuse** (DOC-04 M2) | Mentor | `langfuse_local` mặc định; cần quyết xem có dùng chung máy team hay cloud |

### 9.4 ADR cần sinh thêm (Sprint tiếp theo)

| ADR | Tiêu đề | Trạng thái |
|---|---|---|
| ADR-012 | Optimistic concurrency cho review (P0-05) | Cần viết — nội dung đã chốt trong `DOC-04b-postgres-schema.sql` và `backend/CONTEXT.md` mục 5.2 |

---

*File được tạo: 2026-09-15. Cập nhật: 2026-09-17 (schema v1.0, 3 quyết định kiến trúc).*
