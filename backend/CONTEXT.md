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
| **Deployment** | Monolith (không microservices) |
| **Design pattern** | Domain-Driven Design (DDD) |
| **Backend** | Python 3.11 + FastAPI |
| **AI Service** | Python (FastAPI) — tách riêng, giao tiếp qua HTTP REST |
| **Database** | PostgreSQL + SQLAlchemy (ORM) |
| **Object storage** | MinIO (S3-compatible) |
| **Migration** | Alembic |
| **Frontend** | React / Vue (chưa chốt) |

**Lý do Monolith:**
- Dự án đồ án, team nhỏ (2-3 người), timeline ngắn
- OCR/conflict worker không cần scale độc lập ở phase 1
- Dễ quản lý, dễ debug trong quá trình học

**Lý do DDD:**
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

> TODO: Điền nội dung
> - Domain layer không phụ thuộc framework (không import Spring, javax.persistence trực tiếp vào domain entity)
> - Module giao tiếp qua **Domain Event** hoặc **Application Service** (không gọi thẳng Repository của module khác)
> - Infrastructure phụ thuộc Domain (không ngược lại)

### 3.4 Cấu trúc thư mục

> Tech stack thực tế: **Python 3.11 + FastAPI** (không phải Java/Spring Boot)

```
backend/
├── src/contract_intelligence/
│   ├── main.py                    # FastAPI app entry point
│   ├── shared/                    # Shared kernel: common types, exceptions, utils
│   ├── config/                    # Settings, environment config
│   │
│   ├── contract/                  # Bounded context: contract lifecycle
│   │   ├── domain/                # Entities: Contract, ContractStatus
│   │   ├── application/           # Use cases: upload, get_status
│   │   └── infrastructure/         # MinIO storage, PostgreSQL repository
│   │
│   ├── extraction/                # Bounded context: clause extraction
│   │   ├── domain/                # Entity: Clause, ClauseType (Điều/Khoản/Điểm)
│   │   ├── application/           # Use case: save_extraction_result
│   │   └── infrastructure/
│   │       └── ai_client/
│   │           └── ai_service_client.py  # HTTP REST → gọi ai-service/
│   │
│   ├── conflict/                  # Bounded context: conflict detection
│   │   ├── domain/                # Entity: Conflict, ConflictType
│   │   ├── application/           # Use case: save_conflict_result
│   │   └── infrastructure/
│   │       └── ai_client/        # HTTP REST → gọi ai-service/ (hoặc rule-based nếu BE tự làm)
│   │
│   └── review/                    # Bounded context: HITL review
│       ├── domain/                # Entity: ReviewLog, ReviewAction
│       ├── application/           # Use case: submit_review, approve
│       └── infrastructure/         # PostgreSQL repository
│
├── tests/
│   ├── unit/
│   └── integration/
├── requirements.txt
└── pyproject.toml / Dockerfile
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
> - Giới hạn file: tối đa 10MB, chỉ chấp nhận PDF
> - Tên file tiếng Việt: xử lý encoding không lỗi font
> - Batch upload: 1 item lỗi không fail cả lô (chi tiết xử lý như thế nào)

---

## 5. Data model / Database schema

### 5.1 Bảng `contracts`

> TODO: Điền schema chi tiết
> - columns: id, filename, original_filename, file_size, status, uploaded_by, error_message, created_at, updated_at...

### 5.2 Bảng `contract_pages`

> TODO: Điền schema chi tiết
> - columns: id, contract_id, page_number, image_url, width, height...

### 5.3 Bảng `clauses`

> TODO: Điền schema chi tiết
> - Tự tham chiếu: Điều → Khoản → Điểm
> - columns: id, contract_id, parent_clause_id, page_number, type (chapter/article/clause/point), title, content, bbox (JSONB)...

### 5.4 Bảng `appendix_tables`

> TODO: Điền schema chi tiết
> - Lưu bảng biểu trong phụ lục hợp đồng

### 5.5 Bảng `conflicts`

> TODO: Điền schema chi tiết
> - columns: id, contract_id, clause_a_id, clause_b_id, conflict_type, severity, description...

### 5.6 Bảng `review_logs`

> TODO: Điền schema chi tiết
> - columns: id, contract_id, action, performed_by, note, created_at...

### 5.7 Lưu ý quan trọng

> - **bbox** lưu dạng `JSONB` (tọa độ bounding box từ OCR)
> - **File gốc** lưu vào MinIO (object storage), không lưu trong DB
> - Không lưu file nhị phân trong PostgreSQL

---

## 6. API Spec (DOC-05)

> File gốc: `docs/DOC-05-api-spec.yaml`

### 6.1 Nhóm Upload

> TODO: Liệt kê endpoint upload
> Ví dụ:
> - `POST /api/v1/contracts/upload`
> - `POST /api/v1/contracts/batch`

### 6.2 Nhóm Status / Kết quả

> TODO: Liệt kê endpoint truy vấn trạng thái và kết quả
> Ví dụ:
> - `GET /api/v1/contracts/{id}`
> - `GET /api/v1/contracts/{id}/clauses`
> - `GET /api/v1/contracts/{id}/conflicts`

### 6.3 Nhóm HITL Review

> TODO: Liệt kê endpoint HITL
> Ví dụ:
> - `POST /api/v1/contracts/{id}/review`
> - `GET /api/v1/contracts/{id}/review/logs`

### 6.4 Format response chuẩn

> TODO: Định nghĩa ApiResponse<T>
> ```json
> {
>   "data": { ... },
>   "error": null,
>   "meta": {
>     "timestamp": "2026-09-15T00:00:00Z",
>     "requestId": "..."
>   }
> }
> ```

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
> - Code style (Google Java Style / Checkstyle)
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

### 9.2 Đang chờ xác nhận ⏳

| # | Vấn đề | Chờ ai |
|---|---|---|
| 1 | **Authentication BE↔AI:** API Key hay JWT? | AI Engineer |
| 2 | **AI Service URL:** Self-hosted hay cloud (OpenAI/Anthropic)? | AI Engineer |
| 3 | **OCR Engine:** PaddleOCR, EasyOCR, hay cloud API? | AI Engineer |
| 4 | **LLM Model:** ChatGPT API, Claude API, hay open-source (LLaMA)? | AI Engineer |
| 5 | **Conflict Detection:** Rule-based (BE tự làm) hay AI (AI Engineer)? | Team thống nhất |
| 6 | **MinIO:** Self-hosted hay dùng S3 bucket có sẵn? | Mentor |
| 7 | **Frontend:** React hay Vue? | Frontend Engineer |

---

*File được tạo: 2026-09-15. Cập nhật bởi: Backend Engineer.*
