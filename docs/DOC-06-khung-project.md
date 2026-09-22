# DOC-06 · Khung dự án

> **Contract Intelligence** — Luồng end-to-end · Ranh giới subsystem · Input/Output ghép nối

---

## Thông tin tài liệu

| Trường | Nội dung |
|---|---|
| Mã tài liệu | PP-002 — Project Framework |
| Phiên bản | v1.0 Draft |
| Ngày | 22/09/2026 |
| Mục tiêu | Tài liệu khung để 4 thành viên bám vào phát triển và ghép nối |
| Team | Lead & FE: Trang · BE: Chương · AI1-OCR: Đức Dũng · AI2-Reasoning: Văn Dũng |
| Demo deadline | Thứ 6 cuối tuần này — thông luồng end-to-end |
| Tài liệu gốc | DOC-02 BRD · DOC-03 PRD v0.11 · DOC-04 Architecture · DOC-05 API Specs v0.3.0 · PV1 Product Vision |

---

## 1. Tổng quan luồng end-to-end

Toàn bộ hệ thống có **3 đường chạy chính**. Mỗi đường đi qua đúng các subsystem theo thứ tự — không subsystem nào được gọi tắt bước hoặc gọi chéo.

| Path | Luồng |
|---|---|
| **Processing path** | FE Upload → Backend tạo Dossier/Job → AI1 OCRSnapshot → Backend nhận state → AI2 Process → Backend persist candidate/review state → FE Review |
| **Query path** | FE Search/Ask → Backend ACL/policy → AI2 L0/L1/L2/L3 → grounded result + citations → Backend audit → FE mở đúng nguồn |
| **Rerun path** | Reviewer báo lỗi → Backend tạo run mới → AI1 re-OCR vùng/page cần thiết → snapshot mới → AI2 re-process; output cũ không bị ghi đè |

### 1.1 Processing Path — Upload đến Review

| Bước | Ai thực hiện | Làm gì | Output sang bước tiếp |
|---|---|---|---|
| 1 | FE (Trang) | Operator upload PDF + metadata dossier lên Backend | Multipart request → `POST /dossiers` |
| 2 | Backend (Chương) | Xác thực JWT, kiểm tenant, tạo Dossier + Document + Job, lưu file vào Object Storage | Dossier ID + Job ID + file stored → gửi job sang AI1 |
| 3 | AI1 (Đức Dũng) | Nhận job, OCR từng trang, dựng StructuralNode + LogicalTable + bbox | OCRSnapshot (versioned, immutable) → trả về Backend |
| 4 | Backend (Chương) | Nhận snapshot ID/version/quality từ AI1, validate, cập nhật Job state, gửi tiếp sang AI2 | Snapshot contract → gửi sang AI2 |
| 5 | AI2 (Văn Dũng) | Validate handoff, dựng relation graph, extract fact/finding, pair body–annex, propose index | `CandidateFinding[]` + `IndexContribution` (propose) → trả Backend |
| 6 | Backend (Chương) | Persist fact/finding/conflict, tạo ReviewItem queue, cập nhật dossier state → `PENDING_REVIEW` | Review state → FE poll/notify |
| 7 | FE (Trang) | Hiển thị dossier tree, finding panel, bbox highlight; Reviewer confirm / `NEEDS_REVIEW` / báo citation lỗi | Review action → `POST /review-items/{id}/actions` |
| 8 | Backend (Chương) | Lưu ReviewRevision (append-only), cập nhật review state, khi đủ điều kiện → `APPROVED` | Final state + audit log |

### 1.2 Query Path — Tìm kiếm & Ask

| Bước | Ai thực hiện | Làm gì | Output sang bước tiếp |
|---|---|---|---|
| 1 | FE (Lead) | Reviewer nhập query/câu hỏi trong phạm vi dossier | Request → Backend `/search` hoặc `/ask` |
| 2 | Backend (Chương) | Kiểm ACL, kiểm quota/rate limit, forward sang AI2 với dossier context | Query + ACL-validated context → AI2 |
| 3 | AI2 (Văn Dũng) | Chạy L0 deterministic → L1 retrieval → L2 planner → L3 grounding; trả result + citations + state | Result `{answer, citations[], state}` → Backend |
| 4 | Backend (Chương) | Ghi QueryTrace (actor/version/citations), enforce ACL lần 2, trả payload FE | Result payload + audit → FE |
| 5 | FE (Lead) | Hiển thị result, highlight bbox, mở đúng page/node; Reviewer confirm hoặc báo lỗi | Review action nếu cần |

### 1.3 Rerun Path — Khi reviewer báo lỗi

| Bước | Ai thực hiện | Làm gì | Output sang bước tiếp |
|---|---|---|---|
| 1 | FE (Lead) | Reviewer báo citation lỗi hoặc `NEEDS_REVIEW` trên finding/node cụ thể | Action → Backend |
| 2 | Backend (Chương) | Tạo Run mới, lưu reason, **không xóa** snapshot/finding cũ | New Run ID → AI1 |
| 3 | AI1 (Đức Dũng) | Re-OCR đúng page/vùng được chỉ định; tạo snapshot version mới | New OCRSnapshot version → Backend → AI2 |
| 4 | AI2 (Văn Dũng) | Re-process trên snapshot mới; output cũ không bị ghi đè | New `CandidateFinding[]` → Backend |
| 5 | Backend (Chương) | Persist version mới, giữ lineage cũ, tạo ReviewItem mới | Reviewer thấy cả old và new version |

---

## 2. Ranh giới giữa các subsystem

### 2.1 Bảng ranh giới — Ai làm gì & Không làm gì

| Subsystem | Người phụ trách | Được làm | Không được làm |
|---|---|---|---|
| Frontend | Lead (kiêm FE) | Upload file + metadata; hiển thị dossier tree/structure/table/finding; bbox highlight; search/ask UI; submit review action; poll job status | Không gọi AI1/AI2 trực tiếp; không tự quyết quyền/ACL; không giữ business truth ở local state; không tự suy dossier "đúng" |
| Backend | Chương | Auth/JWT/Tenant/RBAC; tạo Dossier/Document/Job/Run; gọi AI1 và AI2 qua adapter; persist tất cả state; ACL trước mọi read/write; audit log; ReviewItem queue; sign URL | Không tự OCR; không tự reasoning; không import AI implementation vào domain; không để AI1/AI2 gọi nhau trực tiếp |
| AI1 — OCR | Đức Dũng | Classify trang; preprocess; layout detect; OCR text + bbox; dựng StructuralNode + LogicalTable; validate; publish OCRSnapshot immutable | Không làm legal semantics/conflict; không sở hữu dossier lifecycle; không publish active index; Vision chỉ là targeted fallback (không tạo bbox giả) |
| AI2 — Reasoning | Văn Dũng | Validate handoff snapshot; dựng relation graph; extract fact/finding có citation; pair body–annex; L0→L3 query reasoning; propose IndexContribution | Không OCR lại PDF; không dựng geometry; không tự publish active index (chỉ propose); không gửi full PDF vào prompt; không tạo citation khi evidence failed |

### 2.2 Điểm giao nhau quan trọng & Quy tắc không được vi phạm

| Điểm giao | Quy tắc cứng |
|---|---|
| FE → Backend | FE chỉ gửi file + metadata được phép; không tự xác định tenant; FE state là projection từ Backend — refresh phải dựng lại được từ payload |
| Backend → AI1 | Backend submit job qua adapter/port; AI1 không được biết về dossier lifecycle hay ACL |
| AI1 → Backend | AI1 trả OCRSnapshot có version/provenance/digest/quality; Backend validate schema trước khi dùng; snapshot là immutable sau publish |
| Backend → AI2 | Backend gửi snapshot contract đã validate; AI2 không nhận raw OCR provider payload; AI2 không tự mở full PDF |
| AI2 → Backend | AI2 trả `CandidateFinding` + `IndexContribution(propose)`; Backend/reviewer mới quyết định publish active index |
| Review Action | Machine output không bao giờ bị overwrite; mỗi sửa đổi tạo ReviewRevision mới append-only |
| Rerun | Output cũ (snapshot/finding/review) không bị xóa; version mới và cũ cùng tồn tại và truy được |

---

## 3. Input / Output chi tiết từng subsystem

### 3.1 Frontend — Lead (kiêm FE)

| | Chi tiết |
|---|---|
| **INPUT nhận vào** | File PDF từ Operator (upload). Payload JSON từ Backend: dossier tree, `StructuralNode[]`, `LogicalTable[]`, `finding[]`, job status, `citation[]`, review state. Action từ Reviewer: confirm / `NEEDS_REVIEW` / báo citation lỗi |
| **OUTPUT gửi ra** | `POST /dossiers` — multipart (file + metadata). `POST /dossiers/{id}/manifest/confirm` — xác nhận role/relation. `POST /review-items/{id}/actions` — submit review action kèm `base_version`. GET polling: `/jobs/{id}`, `/dossiers/{id}`, `/dossiers/{id}/review-items` |
| **State FE giữ** | Projection từ Backend (không phải source of truth). Refresh/reload phải dựng lại được từ API response — không phụ thuộc local state |
| **Màn hình T1 cần có** | Job list · Upload & manifest confirm · Dossier tree/overview · Search & result · Page viewer + bbox highlight · Finding panel · Edit node + revision history |

### 3.2 Backend — Chương

| | Chi tiết |
|---|---|
| **INPUT nhận vào** | Từ FE: multipart upload, manifest confirm, review actions, search/ask query. Từ AI1: OCRSnapshot (`snapshot_id`, `version`, `quality`, `provenance`). Từ AI2: `CandidateFinding[]`, `IndexContribution(propose)`. Từ External: webhook callback DocuSign/SAP (`POST /external-approvals/callback`) |
| **OUTPUT gửi ra** | Sang AI1: job submission (`dossier_id`, `document_id`, file reference, OCR profile). Sang AI2: snapshot contract (`snapshot_id` + dossier members + role/relation). Sang FE: dossier tree, job status, review payload, search result, citation URL, signed PDF URL. Sang Audit: append-only event log (không chứa raw contract text) |
| **Persist (nguồn sự thật)** | Dossier / Document / Job / Run lifecycle state. OCRSnapshot metadata (không lưu nội dung OCR raw — AI1 giữ). Fact / Finding / Conflict (từ AI2). ReviewItem / ReviewRevision (append-only). Audit log. IndexVersion state (propose → active / rollback) |
| **Tech stack** | Ngôn ngữ/framework: Python (FastAPI) + uv. Database: PostgreSQL (Alembic). Object Storage (PDF): MinIO (S3-compatible). Message queue/async: Apache Kafka (KRaft) + aiokafka. IAM/Auth: Keycloak |
| **Base URL** | Local: `http://localhost:8000/api/v1`. Staging: `https://api.contractintel.internal/api/v1` |

### 3.3 AI1 — OCR & Document Ingestion — Đức Dũng

| | Chi tiết |
|---|---|
| **INPUT nhận vào** | Job từ Backend: `dossier_id`, `document_id`, file reference (path/URL object storage), OCR profile (`default` / `high_res` / `table_optimized`). Re-OCR request: page range / region bbox cụ thể + profile |
| **OUTPUT bắt buộc trả về Backend** | OCRSnapshot gồm: `pages[]` — PageProfile (`kind`: native/scan/mixed/bad, dimensions, transform, quality_state); `nodes[]` — `StructuralNode[]` (`label_raw`, `normalized_type`, `parent_id`, `order`, `citation{doc,page,bbox}`, `status`); `tables[]` — `LogicalTable[]` (header, rows, cells, page_span, bbox[], citations[], validation_checks); `source_files[]` — document identity mapping; `provenance`: `{engine, run_id, profile_pins, timestamp}`; `digest`: hash để AI2 verify; `quality_state`: overall + per-page |
| **Bất biến sau publish** | Snapshot đã publish **không được sửa**. Re-OCR tạo snapshot version **mới**. |
| **Table state AI2 phải hiểu** | `NOT_PRESENT` / `DETECTED` (thiếu cells → `TABLE_STRUCTURE_UNAVAILABLE`) / `UNKNOWN` / `FAILED` — không biến failure thành absence |
| **Tech stack** | OCR engine chính: Mistral OCR 4.1. Vision fallback: Multimodal LLM (GPT/Gemini). Layout detect: Mistral OCR Blocks + PaddleOCR PP-StructureV3. Framework serve: FastAPI |
| **Ranh giới Vision** | Vision chỉ đọc text ở cell/region đã có bbox từ layout detect. Model-generated coordinate **không** được thành citation chính thức. |

### 3.4 AI2 — Semantics & Reasoning — Văn Dũng

| | Chi tiết |
|---|---|
| **INPUT nhận vào** | Snapshot contract từ Backend: `snapshot_id` + `version` + `digest` + `dossier_members[]` + role/relation. Query từ Backend: query text + `dossier_id` + ACL context + policy flags (`use_vector`, `egress_allowed`). **Không** nhận raw PDF; **không** nhận raw OCR provider payload |
| **OUTPUT Processing (sang Backend)** | `CandidateFinding[]`: `fact_id`, `typed_value` (raw + normalized + unit), context, `citations[{doc,page,bbox,snapshot_version}]`, `confidence_flags`; `finding_id`, `model_disposition` (`comparable_match` / `comparable_difference` / `candidate_amendment` / `not_comparable` / `insufficient_evidence`); `pair_id` (body–annex pair), `evidence_both_sides`; `quality_flags`, `review_state`. `IndexContribution` (propose — chờ Backend/reviewer gate) |
| **OUTPUT Query/Ask (sang Backend)** | `{ state: ANSWERED \| NEEDS_REVIEW \| INSUFFICIENT_EVIDENCE \| BLOCKED, answer: string \| null, citations: [{doc, page, bbox, snapshot_version}], retrieval_layer: L0\|L1\|L2\|L3, reasoning_trace: [...] }` |
| **Query layers** | L0 deterministic → L1 retrieval (exact → structured → BM25) → L2 planner (chỉ compare/cascade) → L3 grounding (bắt buộc trước output) |
| **Tech stack** | LLM: TBD (local test: NineRouter/OpenAI-compatible, gpt-4o-mini). Embedding: TBD (local test: text-embedding-3-small, 1536d). Vector store: SQLiteVectorIndex (local test). BM25: custom BM25-lite. Framework: FastAPI/Uvicorn |
| **Policy gates** | Nếu egress denied → deterministic local vẫn chạy, external LLM bị block. Nếu embedding budget exceeded → chạy không vector, trả `BUDGET_EXCEEDED`. Nếu LLM chưa cấu hình → fallback deterministic/review, pipeline không chết |

---

## 4. Trạng thái Dossier & Job

### 4.1 Dossier lifecycle

| Trạng thái | Ý nghĩa | Ai set | Điều kiện chuyển tiếp |
|---|---|---|---|
| `UPLOADED` | File đã nhận, chưa xử lý | Backend (sau `POST /dossiers`) | Manifest được confirm → `PROCESSING` |
| `PROCESSING` | Pipeline AI1+AI2 đang chạy | Backend (sau `POST /runs`) | AI2 trả xong → `PENDING_REVIEW` hoặc `FAILED` |
| `PENDING_REVIEW` | Có ReviewItem chờ reviewer xử lý | Backend | Mọi review item resolved → `REVIEWED` |
| `REVIEWED` | Reviewer đã xử lý hết finding | Backend | Reviewer approve → `APPROVED` |
| `APPROVED` | Dossier được phê duyệt chính thức | Backend (`POST /approve` — ADMIN) | Chỉ khi mọi review items resolved |
| `FAILED` | Pipeline lỗi | Backend | Reprocess → `PROCESSING` mới |
| `ARCHIVED` | Lưu trữ, không xuất hiện search active | Backend/Policy | Restore → `ACTIVE` |
| `SOFT_DELETED` | Xóa mềm, ẩn khỏi UI/search | Backend | Restore trong 30 ngày → trạng thái trước |

### 4.2 Job/Run state

| Trạng thái | Ý nghĩa | Hành động tiếp theo |
|---|---|---|
| `QUEUED` | Job đã tạo, chờ xử lý | AI1 nhận job |
| `PROCESSING` | Đang chạy pipeline | Poll `GET /jobs/{id}` |
| `PASS` | AI1/AI2 hoàn thành, quality đạt | Backend persist → `PENDING_REVIEW` |
| `NEEDS_REVIEW` | Pipeline xong nhưng có trang/node/table quality thấp | ReviewItem được tạo tự động |
| `INSUFFICIENT_EVIDENCE` | Query/result không đủ evidence để trả lời | Không trả câu khẳng định |
| `BLOCKED` | Policy gate chặn (egress, budget) | Check policy/config |
| `FAILED` | Pipeline lỗi hẳn | Retry (`POST /jobs/{id}/retry`) hoặc reprocess |

---

## 5. Danh sách cần chốt trước khi code

### 5.1 Tech Stack — Trang (Frontend)

| Hạng mục | Endpoint | Ảnh hưởng tới |
|---|---|---|
| Poll job state | `GET /jobs/{job_id}` — lặp đến khi `PENDING_REVIEW` | FE biết lúc nào fetch data tiếp theo |
| Fetch dossier overview | `GET /dossiers/{id}` — lấy `documents[]` + manifest status | Dossier tree render ở bước 7 |
| Fetch facts | `GET /dossiers/{id}/facts` — lấy `Fact[]` + `citation[]` + `current_version` | Finding panel bước 7 |
| Fetch findings/conflicts | `GET /dossiers/{id}/conflicts` — lấy `Finding[]` + `model_disposition` + evidence | Finding panel + candidate difference bước 7 |
| Resolve citation (lazy) | `GET /citations/{id}` — lấy bbox + `page_image_url` | Bbox highlight khi reviewer click finding |

### 5.2 Tech Stack — Chương (Backend)

| Hạng mục | Công nghệ | Ảnh hưởng tới |
|---|---|---|
| Ngôn ngữ/Framework Backend | 【TBD】Python FastAPI | Toàn bộ BE module |
| Database chính | 【TBD】PostgreSQL | BE persist, schema migration |
| Object Storage (lưu PDF) | 【TBD】MinIO / S3-compatible | `file_ref` gửi sang AI1, signed URL trả FE |
| Message queue / Async | 【TBD】Apache Kafka (KRaft) | Orchestration job từ BE sang AI1 và AI2 |
| Auth JWT library | 【TBD】PyJWT | Xác thực JWT, phân quyền tenant/RBAC toàn bộ API |

### 5.3 Tech Stack — Đức Dũng (AI1)

| Hạng mục | Công nghệ | Ảnh hưởng tới |
|---|---|---|
| OCR engine chính | Mistral OCR 4.1 | Chất lượng text + bbox toàn bộ pipeline OCR, từ classify trang đến dựng StructuralNode |
| Layout detect | Mistral OCR Blocks/BBox + rule-based reconstruction; PaddleOCR PP-StructureV3 fallback | Table detection, tách region paragraph/header/footer, đầu vào cho dựng LogicalTable |
| Vision fallback | Multimodal LLM — GPT Vision / Gemini Vision, chỉ targeted fallback | Xử lý cell/region OCR thất bại; không được tạo bbox giả; ảnh hưởng policy egress |
| Serve / OpenAPI | FastAPI standalone + OpenAPI contract, BE gọi qua adapter/API | Handoff contract BE↔AI1, định dạng job submit và snapshot trả về |
| Snapshot format | JSON metadata + Object Storage cho raw/processed artifacts; DB lưu trạng thái/index | Quyết định cách AI2 nhận snapshot, cách Backend lưu metadata và tái lập provenance |

### 5.4 Tech Stack — Văn Dũng (AI2)

| Hạng mục | Công nghệ | Ảnh hưởng tới |
|---|---|---|
| LLM cho extraction/reasoning | TBD — production model/provider chưa chốt. Local test only: NineRouter/OpenAI-compatible (`gpt-4o-mini` default) | Extract fact từ node/table, reasoning finding, quyết định disposition; ảnh hưởng policy gate egress |
| Embedding model | TBD — production model chưa chốt. Local test only: `openrouter/openai/text-embedding-3-small`, 1536d | Vector recall trong L1 retrieval, chất lượng semantic search |
| Vector store | SQLiteVectorIndex — local demo/test only. Production: TBD | Lưu và truy vấn embedding cho IndexContribution, L1 vector recall |
| BM25 engine | Custom BM25-lite | Exact/keyword retrieval trong L1, kết hợp với vector recall cho hybrid search |
| Framework serve AI2 | FastAPI/Uvicorn | Handoff contract BE↔AI2, định dạng query/processing request và response trả về |
