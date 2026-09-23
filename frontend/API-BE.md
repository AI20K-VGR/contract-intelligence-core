# API Backend — lookup khi nối frontend

Spec: **Contract Intelligence API** `1.1.0+sprint4-ai-integration` (DOC-05b + DOC-05c).  
Đã chốt theo OpenAPI backend (envelope `{ data, meta }`, header `X-Backend-Version`).

Dùng file này khi bỏ mock: mở mục tương ứng màn hình / file `src/data/*`, copy endpoint + shape, nối `src/api/client.ts`.

Prefix mọi path JSON: `/api/v1`. Base URL: `VITE_API_BASE_URL` (mặc định `http://127.0.0.1:8080`).

---

## Cách tra

1. Biết **route / page** → bảng [A. Route FE → mục](#a-route-fe--mục)
2. Biết **file mock** → bảng [B. Mock file → mục](#b-mock-file--mục)
3. Nối xong một phần: bỏ import `src/data/...` của phần đó, giữ UI.

---

## A. Route FE → mục

| Route FE | Page / layout | Nối mục |
|---|---|---|
| `/` | `LoginPage` | [1. Auth](#1-auth) |
| `/tong-quan` | `OverviewPage` | [15. Chưa có trên BE](#15-fe-có--be-chưa-có-endpoint) |
| `/nguoi-dung-phan-quyen` | `UsersPage` | [18. Quản lý người dùng](#18-quản-lý-người-dùng) |
| `/ho-so` · `/ho-so-cua-toi` | `MyDossiersPage` | [2. List dossier](#2-list-dossier) |
| `/tao-ho-so` | `CreateDossierPage` | [3. Upload dossier](#3-upload-dossier) |
| `/xac-nhan-manifest/:dossierId` | `ManifestConfirmPage` | [19. Xác nhận manifest](#19-xác-nhận-manifest) |
| `/tien-trinh-phan-tich` | `AnalysisProgressPage` | [4. Pipeline run](#4-pipeline-run) |
| `/doi-soat-xung-dot` | `ClauseConflictPage` | [9. Conflict / finding](#9-conflict--finding) |
| `/ho-so-hop-dong` | `DossierReviewPage` | [5](#5-chi-tiết-dossier--document) · [7](#7-clause-tree) · [8](#8-fact--citation) · [15](#15-fe-có--be-chưa-có-endpoint) (search + audit) |
| `/doi-soat-trich-dan` | `CitationComparePage` | [6](#6-page-image--pdf) · [8](#8-fact--citation) · [10](#10-review-hitl) |
| `/nhan-xet-chinh-sua` | `CitationSplitViewPage` | [7](#7-clause-tree) · [8](#8-fact--citation) · [10](#10-review-hitl) |
| `/chinh-sua-trich-dan` | `CitationEditPage` | [8](#8-fact--citation) · [10](#10-review-hitl) |
| `/nhat-ky-phap-ly` | `DossierReviewPage` tab activity | [10. Revisions](#10-review-hitl) · [15](#15-fe-có--be-chưa-có-endpoint) |
| `/duoc-chia-se-voi-toi` · `/tim-kiem-xuyen-ho-so` · `/cai-dat` | Placeholder | [15](#15-fe-có--be-chưa-có-endpoint) |
| `/trung-tam-phan-tich` · `/kho-dieu-khoan-mau` · `/tuan-thu-rui-ro` | Placeholder | [15](#15-fe-có--be-chưa-có-endpoint) · [13](#13-batch--ops--optimization) (ops admin) |
| — | Khóa / duyệt hồ sơ | [11. Lock & approve](#11-lock--approve) |
| — | Re-OCR | [12. Re-OCR](#12-re-ocr) |
| — | Batch ZIP | [13. Batch](#13-batch--ops--optimization) |
| — | Health | [14. Health & AI job](#14-health--ai-job) |

---

## B. Mock file → mục

| File mock hiện tại | Thay bằng |
|---|---|
| `src/auth/session.ts` (`DEMO_USERS`, `loginAs`, `loginWithEmail`) | [1. Auth](#1-auth) |
| `src/data/dossiers.ts` | [2. List dossier](#2-list-dossier) |
| `src/data/upload.ts` | [3. Upload dossier](#3-upload-dossier) — page gọi `src/api/dossiers.ts`; file này chỉ còn `dossierCategories` |
| `src/data/analysisProgress.ts` | [4. Pipeline run](#4-pipeline-run) |
| `src/data/clauseConflicts.ts` | [9. Conflict](#9-conflict--finding) |
| `src/data/citationEdit.ts` | [8](#8-fact--citation) + [10](#10-review-hitl) |
| `src/data/citationSplitView.ts` | [7](#7-clause-tree) + [8](#8-fact--citation) |
| `src/data/dossierSearch.ts` | **Không có search API** — [15](#15-fe-có--be-chưa-có-endpoint) |
| `src/data/auditLog.ts` | Gần nhất: review revisions — [10](#10-review-hitl) · còn lại [15](#15-fe-có--be-chưa-có-endpoint) |
| `src/data/overview.ts` | Bảng thành viên Tổng quan vẫn mock. Quản lý user thật: [18](#18-quản-lý-người-dùng) |
| `src/api/client.ts` (stub) | [0. Client](#0-client--quy-ước) |

`CitationComparePage` còn mock **inline** (`relatedCitations`), không nằm trong `src/data/`.

---

## 0. Client & quy ước

Mọi JSON (trừ binary PDF/ảnh và SSE) trả về:

```ts
type ApiMeta = {
  trace_id?: string | null
  request_id?: string | null
  page?: number | null
  page_size?: number | null
  total?: number | null
}

type ApiResponse<T> = {
  data: T
  meta?: ApiMeta
}
```

Header response: `X-Backend-Version`.

### Request headers (mọi endpoint trừ health)

| Header | Bắt buộc? | Ghi chú |
|---|---|---|
| `Authorization: Bearer <jwt>` | Có (security `HTTPBearer`) | JWT Keycloak RS256 |
| `X-Tenant-Id` | Nên gửi | Lấy từ `GET /auth/me` → `tenant_id` |
| `Idempotency-Key` | Chỉ review action | Replay window (BE dành cho hardening sau) |
| `Content-Type` | JSON: `application/json` · upload: **không set tay** (FormData) | |

`src/api/client.ts` hiện **không** gắn token / tenant / unwrap `data`. Khi nối: thêm wrapper `getJson` / `postJson` / `postMultipart` trả về `res.data`, ném lỗi theo status.

### Auth lỗi thường gặp

| HTTP | Khi nào |
|---|---|
| 401 | Token invalid / hết hạn / không phải Keycloak |
| 403 | Sai role (xem từng endpoint) |
| 404 | Không tìm thấy (đúng tenant) |
| 409 | Conflict nghiệp vụ (run đang chạy, version review, đã lock, …) |
| 422 | Validation (Pydantic / FastAPI) |

Role BE (JWT claim `role`): `OPERATOR` | `REVIEWER` | `ADMINISTRATOR`.

Role FE mock hiện tại: `admin` | `user` — **không trùng tên**. Map đề xuất:

| FE mock | BE |
|---|---|
| `admin` | `ADMINISTRATOR` |
| `user` (upload / tạo HS) | `OPERATOR` |
| `user` (rà soát citation / conflict) | `REVIEWER` |

`ADMINISTRATOR` kế thừa `OPERATOR` trên nhiều endpoint ghi.

### Hai lớp status — đừng trộn

**Job dossier** (`latest_job_status`):

`uploaded | processing | extracted | pending_review | reviewed | approved | failed`

**Pipeline run** (`runs.status`):

`queued | running | completed | failed | cancelled`

OpenAPI list runs: filter `completed` được map `completed` ↔ `succeeded` phía BE.

UI list hồ sơ (`processing | ready | review`) map đề xuất:

| UI `DossierStatus` | Gợi ý từ BE |
|---|---|
| `processing` | `latest_job_status` ∈ `uploaded`, `processing` **hoặc** run `queued`/`running` |
| `review` | `pending_review` **hoặc** `has_conflicts` / `open_review_items` / `pending_conflicts` > 0 |
| `ready` | `extracted` · `reviewed` · `approved` và không còn conflict mở |

---

## 1. Auth

**FE:** `LoginPage`, `AuthProvider`, `session.ts`  
**Bỏ:** `DEMO_USERS`, `loginAs`, `loginWithEmail`, `sessionStorage` lexis-session (thay bằng token Keycloak).

Login **không** nằm trong API này. FE lấy JWT từ Keycloak (Authorization Code / SSO), rồi gọi:

### `GET /api/v1/auth/me`

Pass-through claims — **không query DB**.

```ts
type MeResponse = {
  id: string
  email: string
  display_name: string
  role: string          // OPERATOR | REVIEWER | ADMINISTRATOR
  tenant_id: string
}
// envelope: ApiResponse<MeResponse>
```

Map UI: `user.name` ← `display_name`, `user.role` ← map bảng trên, giữ `tenant_id` trên client để gắn `X-Tenant-Id`.

### `POST /api/v1/auth/webhooks/keycloak`

Webhook Keycloak → sync `app_user`. **Không gọi từ browser.** Header `X-Keycloak-Signature` (HMAC). 401 nếu signature sai.

---

## 2. List dossier

**FE:** `MyDossiersPage` ← `src/data/dossiers.ts`

### `GET /api/v1/dossiers`

Query:

| Param | Type | Mặc định | Ý nghĩa |
|---|---|---|---|
| `status` | string? | — | Filter (string BE; không enum cứng trên OpenAPI) |
| `has_conflicts` | boolean? | — | |
| `batch_id` | string? | — | |
| `q` | string? max 200 | — | Tìm theo **tên** dossier |
| `limit` | 1..100 | 20 | |
| `offset` | ≥0 | 0 | |

Pagination nằm ở `meta.total` / `meta.page` / `meta.page_size`.

```ts
type DossierSummaryDTO = {
  id: string
  name: string
  batch_id?: string | null
  has_conflicts?: boolean          // default false
  latest_job_status?: JobStatus | null
  open_review_items?: number       // default 0
  pending_conflicts?: number       // default 0
  metadata?: Record<string, unknown> | null
  created_at: string               // date-time
}
```

Map UI `Dossier`:

| UI | BE |
|---|---|
| `id` | `id` |
| `title` | `name` |
| `code` | `metadata.code` nếu FE ghi lúc upload/patch — **không có field `code` riêng** |
| `status` | derive từ `latest_job_status` + `has_conflicts` / `open_review_items` |
| `reviewNote` | ví dụ ``${pending_conflicts} điều khoản bất thường`` |
| `documents` | **không có trên list** — cần `GET /dossiers/{id}` hoặc `GET .../documents` |
| `updated` | list chỉ có `created_at` — `updated_at` ở **detail** |
| `access` / chia sẻ | **không có API share** |
| `progress` / `progressLabel` | **không có trên list** — poll `GET /runs?dossier_id=` hoặc SSE |

Điều hướng hiện tại `dossierOpenTo()`:

| UI status | Route | Khi nối |
|---|---|---|
| processing | `/tien-trinh-phan-tich` | mang `dossierId` + `runId` (query/state) |
| review | `/doi-soat-xung-dot` | mang `dossierId` |
| ready | `/ho-so-hop-dong` | mang `dossierId` |

RBAC list: **mọi user đã auth**.

---

## 3. Upload dossier

**FE:** `CreateDossierPage` ← `src/api/dossiers.ts` (`createDossier`, `patchDossier`)  
Đã chốt OpenAPI: màn `/tao-ho-so` gọi **3b** `POST /api/v1/dossiers` → **202**. Multipart `contract` + `metadata` JSON `{ name }` + `annexes[]`. Nhận `dossier_id` + `job_id`, hiện **UPLOADED**.

Mã vụ việc / phân loại / quyền riêng tư **không** nằm trong body POST (OpenAPI metadata chỉ `{ name, tags?, notes? }`). Sau 202 FE gọi `PATCH /dossiers/{id}` `{ metadata: { code, category, privacy } }`. PATCH lỗi không huỷ hồ sơ vừa tạo.

Có **2** POST. Màn tạo hồ sơ dùng 3b. 3a (`/dossiers/upload`) khi muốn auto-run pipeline.

### 3a. Nên dùng: `POST /api/v1/dossiers/upload` → **202**

Multipart:

| Field | Type | Bắt buộc |
|---|---|---|
| `contract_file` | file PDF | có |
| `name` | string 1..255 | có |
| `annex_files` | file[] PDF | không |
| `auto_run` | boolean | không, default `true` |
| `batch_id` | string | không |

RBAC: `OPERATOR` | `ADMINISTRATOR`. 400 file thiếu/sai, 403 sai role.

```ts
type UploadedDocumentInfo = {
  id: string
  role: string              // contract | annex
  order_index: number
  filename: string
  sha256: string
  blob_uri: string
  page_count?: number
  size_bytes?: number
}

type DossierUploadResponse = {
  dossier_id: string
  run_id?: string | null    // poll GET /runs/{run_id}
  documents?: UploadedDocumentInfo[]
  status?: string           // default "accepted"
}
```

Sau 202: `navigate('/tien-trinh-phan-tich', { state: { dossierId, runId, name } })`.

**Form UI thừa so với API:** mã vụ việc, phân loại, quyền riêng tư. `upload` **không** nhận metadata. Cách nối:

1. `POST /dossiers/upload` với `name` + files  
2. `PATCH /dossiers/{id}` body `{ metadata: { code, category, privacy } }`

### 3b. Đã chốt — màn tạo hồ sơ: `POST /api/v1/dossiers` → **202**

OpenAPI `Body_create_dossier` / `DossierCreatedDTO`. Header: `Authorization`, `X-Tenant-Id`. RBAC: `OPERATOR` | `ADMINISTRATOR`.

Multipart:

| Field | Type | Bắt buộc |
|---|---|---|
| `contract` | file PDF | có |
| `metadata` | **string JSON** `{ name, tags?, notes? }` | có |
| `annexes` | file[] | không |

```ts
type DossierCreatedDTO = {
  dossier_id: string
  job_id?: string | null
}
```

| HTTP | OpenAPI | UI |
|---|---|---|
| 202 | `{ data: DossierCreatedDTO }` | hiện UPLOADED + id |
| 400 | Missing contract file | Thiếu tệp PDF hợp đồng |
| 403 | Insufficient role | Chỉ vận hành và quản trị |
| 422 | Invalid metadata JSON | Metadata không đúng JSON |

Muốn chạy pipeline: `POST /dossiers/{id}/runs` ([4](#4-pipeline-run)).

Sau khi có `dossier_id`, màn `/tao-ho-so` mở `/xac-nhan-manifest/:dossierId` để xác nhận thành viên, vai trò tài liệu và quan hệ. Contract: [19](#19-xác-nhận-manifest). Bước này chưa chạy pipeline.

### Sửa metadata sau: `PATCH /api/v1/dossiers/{dossier_id}`

RBAC: `OPERATOR` | `ADMINISTRATOR`.

```ts
type DossierUpdateBody = {
  name?: string | null
  metadata?: Record<string, unknown> | null
}
// 200 → ApiResponse<DossierDetailDTO>
```

---

## 4. Pipeline run

**FE:** `AnalysisProgressPage` ← `src/data/analysisProgress.ts`  
UI đang 4 phase giả: Tải tệp → OCR → Điều khoản → Hoàn tất. BE có **11 step S0..S10**.

### Trigger: `POST /api/v1/dossiers/{dossier_id}/runs` → **202**

RBAC: `OPERATOR` (+ admin kế thừa). 404 dossier, 409 **đã có run active**.

```ts
type CreateRunRequestDTO = {
  config_override?: {
    ocr_profile?: 'standard' | 'high_res_binarize' | 'table_optimized' | null
    prompt_candidate_id?: string | null
    confidence_threshold?: number | null  // 0..1
  } | null
}

type PipelineRunSummaryDTO = {
  run_id: string
  dossier_id: string
  status: string            // queued | running | completed | failed | cancelled
  triggered_by?: string | null
  duration_seconds?: number | null
  created_at?: string | null
  finished_at?: string | null
}
```

### Reprocess: `POST /api/v1/dossiers/{dossier_id}/reprocess` → **202**

Run mới immutable. 409 nếu đang có run active.

```ts
type ReprocessAcceptedDTO = {
  dossier_id: string
  job_id?: string | null
}
```

### List: `GET /api/v1/runs`

Query: `dossier_id?`, `status?` (`queued|running|completed|failed|cancelled`), `limit` (1..100 default 20), `offset`.

### Chi tiết: `GET /api/v1/runs/{run_id}`

404 nếu không có. Cùng `PipelineRunSummaryDTO` (+ config snapshot trong implementation; schema summary không liệt kê extra fields).

### Steps S0..S10: `GET /api/v1/runs/{run_id}/steps`

`ApiResponse<any[]>` — OpenAPI không schema hóa từng step. UI progress: poll endpoint này hoặc SSE `step.changed`.

Map phase UI (tùy product, chỉ gợi ý):

| UI phase | Step BE (gợi ý) |
|---|---|
| 1. Tải tệp | S0 ingest |
| 2. Nhận diện chữ | OCR steps đầu |
| 3. Phân tích điều khoản | clause / fact |
| 4. Hoàn tất | S10 + run `completed` |

Danh sách file đang xử lý: `GET /dossiers/{id}/documents` — không có % per-file trên OpenAPI; % đang mock.

### Cancel: `POST /api/v1/runs/{run_id}/cancel`

403 / 404 / 409 (không cancellable).

### SSE realtime: `GET /api/v1/runs/{run_id}/events`

`text/event-stream`. Events:

| Event | Khi nào |
|---|---|
| `run.started` | mở stream |
| `step.changed` | 1 step S0..S10 đổi trạng thái |
| `run.status_changed` | đổi status run |
| `run.completed` | terminal → đóng stream |
| `error` | lỗi / run not found |
| `:heartbeat` | 15s |

**Trình duyệt `EventSource` không gửi `Authorization`.** Không dùng:

```js
new EventSource(url, { headers: { Authorization } }) // không work
```

Cách nối: `fetch` + `ReadableStream`, cookie session, hoặc token query (nếu BE cho phép — spec hiện để header).

Khi `run.completed` / `failed`: điều hướng review hoặc conflict tùy `has_conflicts` / `open_review_items`.

---

## 5. Chi tiết dossier + document

**FE:** header hồ sơ trên review / conflict; số tài liệu trên list.

### `GET /api/v1/dossiers/{dossier_id}`

404 nếu không có.

```ts
type DocumentRole = 'contract' | 'annex'

type DocumentSummaryDTO = {
  id: string
  dossier_id: string
  role: DocumentRole
  order_index: number
  filename: string
  sha256: string
  page_count?: number
  file_size_bytes?: number
  lang_detected?: string | null
}

type DossierDetailDTO = {
  id: string
  name: string
  batch_id?: string | null
  has_conflicts?: boolean
  latest_job_id?: string | null
  latest_job_status?: JobStatus | null
  documents?: DocumentSummaryDTO[]
  open_review_items?: number
  pending_conflicts?: number
  metadata?: Record<string, unknown> | null
  created_at: string
  updated_at: string
}
```

### `GET /api/v1/dossiers/{dossier_id}/documents`

```ts
type DocumentListItemDTO = {
  id: string
  dossier_id: string
  role: string
  filename: string
  file_size_bytes: number
  page_count: number
  signing_date?: string | null
  document_number?: string | null
  sha256: string
}
```

### `GET /api/v1/documents/{document_id}`

Thêm `storage_path`, `ocr_status` (default `pending`), `created_at`.

```ts
type DocumentDetailDTO = DocumentListItemDTO & {
  storage_path: string
  ocr_status?: string
  created_at: string
}
```

### PDF gốc (binary, không envelope): `GET /api/v1/documents/{document_id}/content`

`Content-Type: application/pdf`. Dùng blob URL cho viewer (màn citation compare). 404 nếu không có.

---

## 6. Page image + PDF

**FE:** zoom/page trên `CitationComparePage`, preview trang.

### `GET /api/v1/documents/{document_id}/pages`

```ts
type PageDTO = {
  id: string
  document_id: string
  page_no: number
  kind?: string            // default "native"
  width_pt: number
  height_pt: number
  rotation?: number
  render_dpi?: number      // default 300
  preview_uri?: string | null
  render_uri?: string | null
  quality?: Record<string, unknown> | null
}
```

### Ảnh trang (binary): `GET /api/v1/documents/{document_id}/pages/{page_no}/image`

- Path `page_no` ≥ 1  
- Query `variant=preview|render` (default `preview`)  
- `image/png` hoặc `image/webp`  
- 404 page/image missing  

Cần `Authorization` — `<img src>` trần sẽ 401. Nối: fetch blob + `URL.createObjectURL`, hoặc proxy cùng cookie.

### `GET /api/v1/pages/{page_id}`

Page + OCR lines. Schema OpenAPI: `dict[str, Any]`. 404 nếu không có.

---

## 7. Clause tree

**FE:** `ContractMindmap`, tab điều khoản, `CitationSplitViewPage` (article/khoản).

### `GET /api/v1/documents/{document_id}/clauses`

Query: `run_id?` (nên gửi run vừa xong).

```ts
type ClauseRegionDTO = {
  page_no: number
  bbox?: number[]
  bbox_source?: string | null
}

type ClauseNodeDTO = {
  id: string
  document_id: string
  node_type: string          // article > clause > point
  label: string
  number?: string | null
  title?: string | null
  text?: string
  lang?: string | null
  parent_id?: string | null
  stable_path?: string
  page_start?: number
  page_end?: number
  confidence?: number
  regions?: ClauseRegionDTO[]
  children?: ClauseNodeDTO[]
}
```

### `GET /api/v1/documents/{document_id}/tables`

Query: `run_id?`.

```ts
type TableCellDTO = {
  row_idx: number
  col_idx: number
  row_span?: number
  col_span?: number
  text?: string
  bbox?: number[]
  is_header?: boolean
  confidence?: number
}

type DocTableDTO = {
  id: string
  document_id: string
  page_no: number
  bbox?: number[]
  rows_count?: number
  cols_count?: number
  has_borders?: boolean
  is_multi_page?: boolean
  continued_from?: string | null
  cells?: TableCellDTO[]
}
```

---

## 8. Fact + citation

**FE:** citation compare / split / edit, “độ tin cậy”, quote + vị trí trang.

### Facts theo dossier (HITL — có version): `GET /api/v1/dossiers/{dossier_id}/facts`

| Query | Default | |
|---|---|---|
| `effective` | `true` | kèm `current_version` để optimistic lock |
| `key` | — | filter 1 fact key |

Response có ETag (dossier-level concurrency).

```ts
type CitationDTO = {
  id: string
  document_id: string
  run_id?: string | null
  quote?: string
  quote_sha256?: string
  segments?: unknown[]      // bbox segments
  doc_char_span?: number[]
  coord_system?: string | null
}

type FactDTO = {
  id: string
  document_id: string
  run_id?: string | null
  key: string
  fact_type: string
  raw_text?: string
  normalized_value?: unknown
  context_clause_id?: string | null
  context_text?: string | null
  confidence?: number
  extractor?: string
  validation_status?: string
  citation?: CitationDTO | null
  trace_id?: string | null
}

type FactEffectiveDTO = {
  fact: FactDTO
  machine_value?: unknown
  effective_value?: unknown
  review_state?: string     // default "unreviewed"
  reviewer_id?: string | null
  reviewed_at?: string | null
  review_item_id?: string | null
  current_version?: number  // default 0 — BẮT BUỘC echo thành base_version
}
```

Map UI citation:

| UI | BE |
|---|---|
| title / khoản | `fact.key` + clause `context_clause_id` → [7](#7-clause-tree) |
| excerpt / quote | `citation.quote` hoặc `fact.raw_text` |
| confidence | `fact.confidence` |
| page | `citation.segments` / clause `page_start` |
| hash | `citation.quote_sha256` |
| status locked/waiting | `review_state` + review item `status` |

### Facts theo document: `GET /api/v1/documents/{document_id}/facts`

`ApiResponse<any[]>` — schema lỏng hơn dossier-level.

### `GET /api/v1/facts/{fact_id}` — `dict` + citation. 404.

### `GET /api/v1/citations/{citation_id}` — quote + segments bbox. 404.

Highlight PDF: lấy `segments` bbox, overlay lên ảnh [6](#6-page-image--pdf).

---

## 9. Conflict / finding

**FE:** `ClauseConflictPage` ← `src/data/clauseConflicts.ts`

Hai list:

| Endpoint | Ý nghĩa |
|---|---|
| `GET /dossiers/{id}/findings` | Mọi phát hiện |
| `GET /dossiers/{id}/conflicts` | Subset cần reviewer: disposition thuộc conflict set **hoặc** `confidence < 0.6` |

### `GET /api/v1/dossiers/{dossier_id}/findings`

Query: `disposition?`, `scope?`, `limit` (1..100 default 20), `offset`.

### `GET /api/v1/dossiers/{dossier_id}/conflicts`

Query: `limit`, `offset`.

### `GET /api/v1/findings/{finding_id}` — 404.

```ts
type FindingSideDTO = {
  side: string
  document_id: string
  document_role?: string | null
  fact_id?: string | null
  clause_node_id?: string | null
  citation?: Record<string, unknown> | null
  value_snapshot?: unknown
}

type FindingReviewDTO = {
  item_id: string
  status: string
  current_version?: number
}

type FindingDTO = {
  id: string
  dossier_id: string
  run_id?: string | null
  finding_type: string
  scope: string
  key_or_topic: string
  disposition: string
  severity: string
  confidence?: number
  rationale?: string | null
  method?: string
  sides?: FindingSideDTO[]     // 2 phía đối sánh
  disclaimer?: string          // default: không phải kết luận pháp lý
  review?: FindingReviewDTO | null
}
```

Map UI `ClauseConflict`:

| UI | BE |
|---|---|
| `id` / `code` | `id` |
| `title` / `field` | `key_or_topic` |
| `comparison` | ghép `sides[].value_snapshot` |
| `risk` high/resolved | `severity` + `review.status` / `disposition` |
| `diagnosis` | `rationale` |
| `source1` / `source2` | `sides[0]` / `sides[1]` |
| `value` | `value_snapshot` |
| quote highlight | `sides[].citation` |
| `choice` | **không lưu trên finding** — submit [10](#10-review-hitl) qua `review.item_id` |

Chọn nguồn / overlay / reject trên UI = `POST /review-items/{item_id}/actions` với `base_version` = `review.current_version`. Thiếu `review.item_id` thì list `GET .../review-items` filter `target_id = finding.id`.

---

## 10. Review HITL

**FE:** nút xác nhận / sửa / từ chối trên conflict + citation pages.  
RBAC list/get: `REVIEWER` | `ADMINISTRATOR`. Action cùng role. 403 nếu OPERATOR thuần.

### Queue: `GET /api/v1/dossiers/{dossier_id}/review-items`

Query: `priority?` (`P1|P2|P3`), `status?` (`open|resolved|awaiting_evidence`), `limit`, `offset`.  
Thứ tự ưu tiên BE: P1 > P2 > P3.

```ts
type ReviewItemDTO = {
  id: string
  dossier_id: string
  run_id: string
  target_type: string
  target_id: string
  reason?: string
  priority?: string         // default P3
  status?: string           // default open
  version?: number          // default 1 — dùng cho base_version
  source_trace_id?: string | null
  source_observation_id?: string | null
  target_snapshot?: Record<string, unknown> | null
  created_at?: string | null
}
```

### `GET /api/v1/review-items/{item_id}` — có `version`. 404.

### Audit trail item: `GET /api/v1/review-items/{item_id}/revisions`

```ts
type ReviewItemRevisionDTO = {
  revision_number: number
  action: string
  author_user_id: string
  author_role?: string | null
  comment?: string | null
  corrected_value?: unknown
  corrected_bbox?: unknown
  previous_version?: number | null
  created_at?: string | null
}
```

Đây là phần **gần nhất** với tab nhật ký — append-only theo 1 review item, không phải audit toàn dossier (`src/data/auditLog.ts`).

### Submit: `POST /api/v1/review-items/{item_id}/actions`

Header optional: `Idempotency-Key`.

```ts
type ReviewActionRequestDTO = {
  action: string            // confirm | correct | reject | needs_more_evidence
  base_version: number      // version client đang thấy; 0 = machine baseline
  corrected_value?: Record<string, unknown> | null  // bắt buộc nếu action=correct
  corrected_bbox?: unknown[] | null
  comment?: string | null   // max 2000
}

type ReviewActionResponseDTO = {
  review_action_id: string
  item_status: string
  new_version: number
  effective_value?: unknown
  machine_value?: unknown
  job_status?: string | null
  open_items_remaining?: number | null
  idempotent_replay?: boolean
}
```

| HTTP | |
|---|---|
| 200 | OK |
| 403 | Sai role |
| 404 | Không có item |
| 409 | `base_version` lệch — body có `current_state`; reload item, gửi lại `version` mới |
| 422 | Action invalid / thiếu `corrected_value` |

Map UI conflict:

| UI Decision | `action` |
|---|---|
| confirm nguồn đã chọn | `confirm` (kèm `corrected_value` nếu BE yêu cầu side đã pick) |
| overlay | `correct` + `corrected_value` / `corrected_bbox` |
| reject | `reject` |
| (citation) needs more evidence | `needs_more_evidence` → status `awaiting_evidence` |

**Luôn** gửi `base_version` = `item.version` hoặc `finding.review.current_version` hoặc `fact.current_version`.

---

## 11. Lock & approve

Chưa có màn FE riêng — gắn vào review khi queue = 0.

### `POST /api/v1/dossiers/{dossier_id}/lock` — RBAC `REVIEWER` | `ADMINISTRATOR`

200 `DossierDetailDTO`. 409 already locked.

### `POST /api/v1/dossiers/{dossier_id}/approve` — **ADMINISTRATOR only**

Tạo snapshot checksum.

```ts
type ApproveRequestDTO = {
  comment?: string | null   // max 2000
}
```

409 preconditions not met (ví dụ còn open review / chưa lock — theo BE).

### External approval

`POST /api/v1/dossiers/{dossier_id}/external-approvals` → **201**  
RBAC **ADMINISTRATOR**. 409 nếu chưa approve hoặc đang có grant pending.

```ts
type ExternalApprovalRequestDTO = {
  provider: 'docusign' | 'sap_ariba' | 'corporate_sso'
  approver_email: string    // 3..255
  approver_name?: string | null
  expires_in_hours?: number // 1..720, default 72
  notes?: string | null
}

type ExternalApprovalGrantDTO = {
  id: string
  dossier_id: string
  provider: string
  status: string
  approver_email: string
  external_reference_id?: string | null
  digital_signature_hash?: string | null
  granted_at?: string | null
  created_at?: string | null
}
```

`GET /api/v1/dossiers/{dossier_id}/external-approvals` — list grants.

`POST /api/v1/external-approvals/callback` — webhook DocuSign/SAP (không gọi từ FE):

```ts
type ExternalApprovalCallbackDTO = {
  grant_id: string
  status: 'approved' | 'rejected'
  external_reference_id?: string | null
  digital_signature_hash?: string | null
  signature_certificate?: string | null
  signed_at?: string | null
}
```

---

## 12. Re-OCR

Chưa có màn FE. RBAC tạo request: `OPERATOR` | `REVIEWER` | `ADMINISTRATOR`.

### `POST /api/v1/documents/{document_id}/re-ocr` → **202**

```ts
type ReOcrRequestPayloadDTO = {
  profile: 'high_res_binarize' | 'table_optimized' | 'handwritten_vietnamese'
  page_numbers?: number[]
  reason?: string | null
}

type ReOcrRequestRecordDTO = {
  id: string
  document_id: string
  profile: string
  page_numbers?: number[]
  status: string
  requested_by?: string | null
  created_at?: string | null
  completed_at?: string | null
  job_id?: string | null
  reason?: string | null
}
```

`GET /api/v1/documents/{document_id}/re-ocr-requests` — list.  
`GET /api/v1/re-ocr-requests/{request_id}` — poll 1 request.

---

## 13. Batch / ops / optimization

Admin/ops. FE overview hiện **không** gọi các endpoint này.

### Batch (ZIP + `manifest.csv`)

`POST /api/v1/batches` multipart → **202** — RBAC OPERATOR (+ admin):

| Field | |
|---|---|
| `manifest` | file `manifest.csv` |
| `archive` | ZIP |
| `name` | optional |

```ts
type BatchCreatedDTO = {
  batch_id: string
  dossier_count?: number
  dossier_ids?: string[]
  job_ids?: string[]
}
```

`GET /api/v1/batches?status=&limit=&offset=`  
`status` pattern: `processing|completed|partial_failed|failed|cancelled`

```ts
type BatchListItemDTO = {
  batch_id: string
  status: string
  total_dossiers?: number
  completed_dossiers?: number
  failed_dossiers?: number
  name?: string | null
  created_at?: string | null
}

type BatchDetailDTO = BatchListItemDTO & {
  dossiers?: Record<string, unknown>[]
}
```

`GET /api/v1/batches/{batch_id}`  
`GET /api/v1/batches/{batch_id}/summary` — `dict` (succeeded, failed, pending_review, total_cost_usd)  
`POST /api/v1/batches/{batch_id}/cancel` — 409 already terminal  
`POST /api/v1/batches/{batch_id}/resume` — 409 not resumable  

List dossier theo batch: `GET /dossiers?batch_id=`.

### Ops metrics: `GET /api/v1/ops/metrics`

**ADMINISTRATOR only.** `dict` (load, latency, cost theo ngày). 403 nếu không phải admin.

### Optimization (prompt/model experiments)

| Method | Path | Status |
|---|---|---|
| GET/POST | `/optimization/campaigns` | 200 / 201 |
| GET | `/optimization/campaigns/{campaign_id}` | 200/404 |
| GET/POST | `/optimization/candidates` | 200 / 201 |
| GET | `/optimization/candidates/{id}` | 200/404 |
| POST | `/optimization/candidates/{id}/promote` | 200, 409 already production |
| GET/POST | `/optimization/experiments` | 200 / 201 |
| POST | `/optimization/experiments/{id}/run` | 202, 409 running/finished |
| GET | `/optimization/experiments/{id}/results` | 200 |

```ts
type CreateCampaignRequestDTO = {
  name: string              // 1..255
  description?: string | null
  target_metric: 'f1_score' | 'precision' | 'latency' | 'cost'
  baseline_score: number
}

type CreateCandidateRequestDTO = {
  campaign_id: string
  name: string
  prompt_template: string
  model_name: string
  temperature?: number      // default 0
}

type CreateExperimentRequestDTO = {
  campaign_id: string
  candidate_id: string
  golden_dataset_version: string
  sample_size?: number      // default 100, min 1
}
```

DTO đọc: `OptimizationCampaignDTO`, `OptimizationCandidateDTO`, `OptimizationExperimentDTO`, `ExperimentResultDTO` (f1, precision, recall, latency, cost, breakdown_by_clause_type).

---

## 14. Health & AI job

Thường không gắn UI user. Dùng khi hiện “AI down” trên màn progress.

| Method | Path | Auth | Ý nghĩa |
|---|---|---|---|
| GET | `/health` | spec vẫn liệt kê bearer | health đơn giản |
| GET | `/api/v1/healthz` | bearer trên spec | liveness — luôn 200 nếu process sống |
| GET | `/api/v1/readyz` | bearer | readiness DB + AI; **503** nếu AI down (HTTP mode) |
| GET | `/api/v1/ai/jobs/{job_id}` | bearer | proxy AI `GET /jobs/{id}` — poll không cần biết dossier. 502 AI down |
| DELETE | `/api/v1/ai/jobs/{job_id}` | OPERATOR+ | proxy cancel AI job |

`job_id` dossier: `DossierCreatedDTO.job_id` / `latest_job_id` / `ReprocessAcceptedDTO.job_id` — khác `run_id`.

---

## 15. FE có — BE chưa có endpoint

Giữ mock hoặc ẩn màn cho đến khi BE bổ sung. Đừng bịa API.

| UI | File | Lý do |
|---|---|---|
| Login Google / SSO / quick admin-user | `LoginPage` | Auth = Keycloak ngoài OpenAPI; API chỉ `/auth/me` |
| Tổng quan team + activity | `overview.ts` | Không có list users / invite / share |
| Người dùng & phân quyền | `UsersPage` | FE đã gọi. BE làm theo `BE-USER-ADMIN.md` — [18](#18-quản-lý-người-dùng) |
| Được chia sẻ với tôi | Placeholder | Không có share grant |
| Tìm kiếm xuyên hồ sơ | Placeholder | `GET /dossiers?q=` chỉ search **tên** dossier |
| Tìm trong 1 hồ sơ (Ctrl+K) | `dossierSearch.ts` | Không có full-text / semantic search |
| Nhật ký pháp lý toàn dossier | `auditLog.ts` | Chỉ `review-items/.../revisions` theo 1 item |
| Quyền riêng tư / chia sẻ lúc tạo HS | `CreateDossierPage` | Không có field privacy; nhét `metadata` nếu BE chấp nhận opaque object |
| Mã vụ việc `code` | list + create | Không có field; dùng `metadata.code` |
| Kho điều khoản mẫu | Placeholder | Không có |
| Tuân thủ & rủi ro (trang riêng) | Placeholder | Gần nhất: findings/conflicts |
| Trung tâm phân tích | Placeholder | Gần nhất: ops metrics + optimization (admin) |
| Cài đặt | Placeholder | Không có |

---

## 16. Thứ tự nối đề xuất

1. **Client** — Bearer + `X-Tenant-Id` + unwrap `{ data, meta }` + lỗi 401/403/409  
2. **Auth** — Keycloak token → `GET /auth/me` → bỏ `DEMO_USERS`  
3. **Upload** — màn `/tao-ho-so` dùng `POST /dossiers` (3b) → `dossier_id` + `job_id`, status UPLOADED, rồi xác nhận manifest ([19](#19-xác-nhận-manifest)). Auto-run: `POST /dossiers/upload` (3a) → `run_id`  
4. **Progress** — `GET /runs/{id}` + `/steps` (poll); SSE nếu giải được auth  
5. **List** — `GET /dossiers` thay `myDossiers`  
6. **Conflict** — `GET .../conflicts` + actions review  
7. **Citation / clause / page image** — facts + clauses + pages  
8. **Lock / approve** khi queue = 0  
9. Phần [15](#15-fe-có--be-chưa-có-endpoint) để sau

Route cần **param id** (hiện UI không có): `/ho-so/:dossierId`, `/tien-trinh-phan-tich/:runId`, `/doi-soat-xung-dot/:dossierId`, `/doi-soat-trich-dan/:factId` (hoặc `reviewItemId`).

---

## 17. Checklist copy khi mở 1 PR nối API

```
Màn: _______________________
File FE: ___________________
Mục API-BE.md: #___________
Method + path: _____________
RBAC: ______________________
Request: headers / query / body
Response: data type + meta
Lỗi cần UI: 401 403 404 409 422
Bỏ mock: src/data/__________
Verify: [ ] happy path  [ ] 409  [ ] empty list
```

---

## 18. Quản lý người dùng

**FE:** `UsersPage` (`/nguoi-dung-phan-quyen`), `src/api/users.ts`  
**BE:** đã có trên OpenAPI (`/api/v1/users`…). Chi tiết vận hành Keycloak/SMTP: [`BE-USER-ADMIN.md`](./BE-USER-ADMIN.md).

Browser không gọi Keycloak Admin API. Mọi thao tác đi qua backend, kèm Bearer của admin.

| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/users` | Danh sách. Query `q`, `role`, `status`, `limit`, `offset` |
| POST | `/api/v1/users` | Tạo user + email đặt mật khẩu |
| PATCH | `/api/v1/users/{id}` | Đổi `role` |
| POST | `/api/v1/users/{id}/disable` | Khóa |
| POST | `/api/v1/users/{id}/enable` | Mở khóa |
| POST | `/api/v1/users/{id}/invite` | Gửi lại email |

RBAC: **ADMINISTRATOR** only. `OPERATOR` và `REVIEWER` vẫn vào cùng giao diện user; chỉ `ADMINISTRATOR` vào trang này.

---

## 19. Xác nhận manifest

**FE:** `ManifestConfirmPage` (`/xac-nhan-manifest/:dossierId`), `src/api/manifest.ts`  
**BE:** đã có trên OpenAPI: `GET /dossiers/{id}/manifest`, `POST .../manifest/confirm`. Chi tiết UI: [`BE-MANIFEST-CONFIRM.md`](./BE-MANIFEST-CONFIRM.md).

Sau upload, operator hoặc administrator xác nhận tài liệu thuộc hồ sơ, vai trò từng tệp và quan hệ. Quan hệ `confirmation: "unconfirmed"` phải được đánh dấu trên UI cho đến khi xác nhận hoặc bác bỏ. Nút gửi không hoàn tất khi còn quan hệ chưa xác nhận.

| Method | Path | Việc |
|---|---|---|
| GET | `/api/v1/dossiers/{dossier_id}/manifest` | Bản đề xuất: members, role, relations |
| POST | `/api/v1/dossiers/{dossier_id}/manifest/confirm` | Ghi nhận xác nhận |

RBAC: **OPERATOR** hoặc **ADMINISTRATOR**. `REVIEWER` nhận 403. Confirm không tạo pipeline run.
