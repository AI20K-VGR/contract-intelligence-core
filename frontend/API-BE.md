# API Backend — lookup khi nối frontend

Spec: **Contract Intelligence API** `1.1.0+sprint4-ai-integration` (DOC-05b + DOC-05c).  
Đã chốt theo OpenAPI backend (envelope `{ data, meta }`, header `X-Backend-Version`).
Hợp đồng FE-BE: **DOC-05b `v5.1.0`**, header response `X-API-Contract: v5.1.0`. 4 endpoint `/notifications` của `v1.6.0` vẫn là đề xuất, backend chưa có ([24](#24-thông-báo-cá-nhân-đề-xuất-be-chưa-có)).

Từ `v2.1.0`:

- `v3.0.0` (siết quyền trước pentest): token không có role ứng dụng trả `403`; `/ai/jobs/{id}` chỉ `ADMINISTRATOR`; batch cancel/resume chỉ người tạo hoặc `ADMINISTRATOR`. Frontend không dùng các endpoint này.
- `v3.1.0`: bật consent AI2 cho hồ sơ đã qua AI2 thì backend tự cho AI2 chạy lại; response consent thêm `ai2_reindex_queued` ([26](#26-đồ-thị-hợp-đồng-vết-xử-lý-và-consent-ai2-v210)).
- `v3.2.0`: tiến độ trong bước `progress` trên `/runs/{id}/steps` và SSE `step.changed`; mã lỗi job `AI1_NO_READABLE_PAGE` ([mục steps](#steps-s0s10-get-apiv1runsrun_idsteps)).
- `v3.3.0`: `GET /dossiers` thêm `document_counts`, `contract_ocr`; header `Server-Timing`. Frontend chưa đọc hai trường này (màn danh sách vẫn gọi `/documents`, `/pages` từng dòng).
- `v4.0.0` (**breaking**): chia sẻ hồ sơ chỉ với người dùng có thật trong cùng tenant ([20](#20-chia-sẻ-hồ-sơ-chỉ-đọc--được-sửa-có-hạn)); thêm `GET /users/lookup`; OPERATOR gọi `/users/directory` phải có `q` từ 3 ký tự (frontend không gọi danh bạ); `POST /users`, `/invite` trả `422 email_domain_undeliverable` ([18](#18-quản-lý-người-dùng)).
- `v4.1.0`: đăng xuất có hiệu lực ngay. Keycloak báo phiên kết thúc qua back-channel logout (`POST /api/v1/auth/backchannel-logout`, chỉ Keycloak gọi trong mạng nội bộ, Caddy trả 404 từ Internet); access token của phiên đó nhận `401` `{"detail": "Session has ended"}` thay vì chờ hết hạn. Frontend không phải sửa ([1](#1-auth)).
- `v5.0.0` (**breaking**): không gửi được thư thì không có quyền. `PUT /dossiers/{id}/access` trả `422 share_recipient_undeliverable` khi người nhận mới có tên miền không nhận thư (không lưu gì), và gỡ người gửi thư lỗi, trả họ trong `email_not_sent: [{email, reason}]` ([20](#20-chia-sẻ-hồ-sơ-chỉ-đọc--được-sửa-có-hạn)).
- `v5.1.0`: thư mời bị trả về. Người dùng trong `GET /users`, `POST /users`... có thêm `invite_delivery` (`pending`, `sent`, `bounced`, `null`) và `invite_delivery_reason` ([18](#18-quản-lý-người-dùng)).

Dùng file này khi bỏ mock: mở mục tương ứng màn hình / file `src/data/*`, copy endpoint + shape, nối `src/api/client.ts`.

Prefix mọi path JSON: `/api/v1`. Base URL: `VITE_API_BASE_URL` (mặc định `http://127.0.0.1:8080`).

---

## Cách tra

1. Biết **route / page** → bảng [A. Route FE → mục](#a-route-fe--mục)
2. Biết **file mock** → bảng [B. Mock file → mục](#b-mock-file--mục)
3. Nối xong một phần: bỏ import `src/data/...` của phần đó, giữ UI.

---

## A. Route FE → mục

| Route FE                                                            | Page / layout                    | Nối mục                                                                                                                                   |
| ------------------------------------------------------------------- | -------------------------------- | ----------------------------------------------------------------------------------------------------------------------------------------- |
| `/`                                                                 | `LoginPage`                      | [1. Auth](#1-auth)                                                                                                                        |
| `/tong-quan`                                                        | `OverviewPage`                   | [18](#18-quản-lý-người-dùng) · [2](#2-list-dossier) · phần chưa có: [`BE-OVERVIEW.md`](./BE-OVERVIEW.md)                                  |
| `/nguoi-dung-phan-quyen`                                            | `UsersPage`                      | [18. Quản lý người dùng](#18-quản-lý-người-dùng)                                                                                          |
| `/ho-so` · `/ho-so-cua-toi`                                         | `MyDossiersPage`                 | [2. List dossier](#2-list-dossier)                                                                                                        |
| `/tao-ho-so`                                                        | `CreateDossierPage`              | [3. Upload dossier](#3-upload-dossier)                                                                                                    |
| `/tien-trinh-phan-tich`                                             | `AnalysisProgressPage`           | [4. Pipeline run](#4-pipeline-run)                                                                                                        |
| `/doi-soat-xung-dot`                                                | `ClauseConflictPage`             | [9. Conflict / finding](#9-conflict--finding)                                                                                             |
| `/ho-so-hop-dong`                                                   | `DossierReviewPage`              | [5](#5-chi-tiết-dossier--document) · [7](#7-clause-tree) · [8](#8-fact--citation) · [15](#15-fe-có--be-chưa-có-endpoint) (search + audit) |
| `/doi-soat-trich-dan`                                               | `CitationComparePage`            | [6](#6-page-image--pdf) · [8](#8-fact--citation) · [10](#10-review-hitl)                                                                  |
| `/nhan-xet-chinh-sua`                                               | `CitationSplitViewPage`          | [7](#7-clause-tree) · [8](#8-fact--citation) · [10](#10-review-hitl)                                                                      |
| `/chinh-sua-trich-dan`                                              | `CitationEditPage`               | [8](#8-fact--citation) · [10](#10-review-hitl)                                                                                            |
| `/nhat-ky-phap-ly`                                                  | `DossierReviewPage` tab activity | [10. Revisions](#10-review-hitl) · [15](#15-fe-có--be-chưa-có-endpoint)                                                                   |
| `/duoc-chia-se-voi-toi` · `/tim-kiem-xuyen-ho-so` · `/cai-dat`      | Placeholder                      | [15](#15-fe-có--be-chưa-có-endpoint)                                                                                                      |
| `/trung-tam-phan-tich` · `/kho-dieu-khoan-mau` · `/tuan-thu-rui-ro` | Placeholder                      | [15](#15-fe-có--be-chưa-có-endpoint) · [13](#13-batch--ops--optimization) (ops admin)                                                     |
| —                                                                   | Khóa / duyệt hồ sơ               | [11. Lock & approve](#11-lock--approve)                                                                                                   |
| —                                                                   | Re-OCR                           | [12. Re-OCR](#12-re-ocr)                                                                                                                  |
| —                                                                   | Batch ZIP                        | [13. Batch](#13-batch--ops--optimization)                                                                                                 |
| —                                                                   | Health                           | [14. Health & AI job](#14-health--ai-job)                                                                                                 |

---

## B. Mock file → mục

| File mock hiện tại                                                | Thay bằng                                                                                                     |
| ----------------------------------------------------------------- | ------------------------------------------------------------------------------------------------------------- |
| `src/auth/session.ts` (`DEMO_USERS`, `loginAs`, `loginWithEmail`) | [1. Auth](#1-auth)                                                                                            |
| `src/data/dossiers.ts`                                            | [2. List dossier](#2-list-dossier)                                                                            |
| `src/data/upload.ts`                                              | [3. Upload dossier](#3-upload-dossier) — page gọi `src/api/dossiers.ts`; file này chỉ còn `dossierCategories` |
| `src/data/analysisProgress.ts`                                    | [4. Pipeline run](#4-pipeline-run)                                                                            |
| `src/data/clauseConflicts.ts`                                     | [9. Conflict](#9-conflict--finding)                                                                           |
| `src/data/citationEdit.ts`                                        | [8](#8-fact--citation) + [10](#10-review-hitl)                                                                |
| `src/data/citationSplitView.ts`                                   | [7](#7-clause-tree) + [8](#8-fact--citation)                                                                  |
| `src/data/dossierSearch.ts`                                       | **Không có search API** — [15](#15-fe-có--be-chưa-có-endpoint)                                                |
| `src/data/auditLog.ts`                                            | Gần nhất: review revisions — [10](#10-review-hitl) · còn lại [15](#15-fe-có--be-chưa-có-endpoint)             |
| `src/data/overview.ts`                                            | Đã bỏ. Tổng quan gọi `GET /users` và `GET /dossiers`. Phần chưa có API: [`BE-OVERVIEW.md`](./BE-OVERVIEW.md)  |
| `src/api/client.ts` (stub)                                        | [0. Client](#0-client--quy-ước)                                                                               |

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

Header response: `X-API-Contract` (hiện `v3.2.0`). `X-Backend-Version` chỉ có ở dev/test; bản online không gửi.

### Request headers (mọi endpoint trừ health)

| Header                        | Bắt buộc?                                                       | Ghi chú                                   |
| ----------------------------- | --------------------------------------------------------------- | ----------------------------------------- |
| `Authorization: Bearer <jwt>` | Có (security `HTTPBearer`)                                      | JWT Keycloak RS256                        |
| `X-Tenant-Id`                 | Nên gửi                                                         | Lấy từ `GET /auth/me` → `tenant_id`       |
| `Idempotency-Key`             | Chỉ review action                                               | Replay window (BE dành cho hardening sau) |
| `Content-Type`                | JSON: `application/json` · upload: **không set tay** (FormData) |                                           |

`src/api/client.ts` hiện **không** gắn token / tenant / unwrap `data`. Khi nối: thêm wrapper `getJson` / `postJson` / `postMultipart` trả về `res.data`, ném lỗi theo status.

### Auth lỗi thường gặp

| HTTP | Khi nào                                                        |
| ---- | -------------------------------------------------------------- |
| 401  | Token invalid / hết hạn / không phải Keycloak. **v4.1.0:** phiên Keycloak đã kết thúc (đăng xuất, quản trị khoá tài khoản) dù token chưa hết hạn |
| 403  | Sai role (xem từng endpoint)                                   |
| 404  | Không tìm thấy (đúng tenant)                                   |
| 409  | Conflict nghiệp vụ (run đang chạy, version review, đã lock, …) |
| 422  | Validation (Pydantic / FastAPI)                                |

Body `401` là `{"detail": "..."}` của FastAPI, không theo envelope `error`: `Token has expired`, `Invalid token`, hoặc **`Session has ended`** (v4.1.0). Cả ba đều xử lý như hết phiên (về màn đăng nhập); không cần đọc nội dung `detail`.

Role BE (JWT claim `role`): `OPERATOR` | `REVIEWER` | `ADMINISTRATOR`.

Role FE mock hiện tại: `admin` | `user` — **không trùng tên**. Map đề xuất:

| FE mock                              | BE              |
| ------------------------------------ | --------------- |
| `admin`                              | `ADMINISTRATOR` |
| `user` (upload / tạo HS)             | `OPERATOR`      |
| `user` (rà soát citation / conflict) | `REVIEWER`      |

`ADMINISTRATOR` kế thừa `OPERATOR` trên nhiều endpoint ghi.

### Hai lớp status — đừng trộn

**Job dossier** (`latest_job_status`):

`uploaded | processing | extracted | pending_review | reviewed | approved | failed`

**Pipeline run** (`runs.status`):

`queued | running | completed | failed | cancelled`

OpenAPI list runs: filter `completed` được map `completed` ↔ `succeeded` phía BE.

UI list hồ sơ (`processing | ready | review`) map đề xuất:

| UI `DossierStatus` | Gợi ý từ BE                                                                               |
| ------------------ | ----------------------------------------------------------------------------------------- |
| `processing`       | `latest_job_status` ∈ `uploaded`, `processing` **hoặc** run `queued`/`running`            |
| `review`           | `pending_review` **hoặc** `has_conflicts` / `open_review_items` / `pending_conflicts` > 0 |
| `ready`            | `extracted` · `reviewed` · `approved` và không còn conflict mở                            |

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
  role: string // OPERATOR | REVIEWER | ADMINISTRATOR
  tenant_id: string
}
// envelope: ApiResponse<MeResponse>
```

Map UI: `user.name` ← `display_name`, `user.role` ← map bảng trên, giữ `tenant_id` trên client để gắn `X-Tenant-Id`.

### `POST /api/v1/auth/webhooks/keycloak`

Webhook Keycloak → sync `app_user`. **Không gọi từ browser.** Header `X-Keycloak-Signature` (HMAC). 401 nếu signature sai.

### `POST /api/v1/auth/backchannel-logout` (v4.1.0)

**Chỉ Keycloak gọi**, trong mạng nội bộ (`http://backend:8000`); Caddy trả `404` cho đường dẫn này từ Internet, và nó không có trong OpenAPI. Khi một phiên kết thúc (người dùng đăng xuất, quản trị đăng xuất hộ hoặc khoá tài khoản), Keycloak gửi `logout_token` (form) và backend chặn mọi access token của phiên đó (`sid`): các request sau nhận `401` `{"detail": "Session has ended"}` thay vì chờ token hết hạn (tối đa 15 phút). Frontend **không gọi** endpoint này và không phải sửa gì: vẫn đăng xuất bằng `signoutRedirect()`, `401` vẫn mở hộp thoại hết phiên.

---

## 2. List dossier

**FE:** `MyDossiersPage` ← `src/data/dossiers.ts`

### `GET /api/v1/dossiers`

Query:

| Param           | Type            | Mặc định | Ý nghĩa                                          |
| --------------- | --------------- | -------- | ------------------------------------------------ |
| `status`        | string?         | —        | Filter (string BE; không enum cứng trên OpenAPI) |
| `has_conflicts` | boolean?        | —        |                                                  |
| `batch_id`      | string?         | —        |                                                  |
| `q`             | string? max 200 | —        | Tìm theo **tên** dossier                         |
| `limit`         | 1..100          | 20       |                                                  |
| `offset`        | ≥0              | 0        |                                                  |

Pagination nằm ở `meta.total` / `meta.page` / `meta.page_size`.

```ts
type DossierSummaryDTO = {
  id: string
  name: string
  batch_id?: string | null
  has_conflicts?: boolean // default false
  latest_job_status?: JobStatus | null
  open_review_items?: number // default 0
  pending_conflicts?: number // default 0
  metadata?: Record<string, unknown> | null
  locked?: boolean // v1.7.0 — hồ sơ đã khoá để phê duyệt
  approved_at?: string | null // v1.7.0 — null khi chưa duyệt
  my_access?: DossierMyAccessDTO // v1.7.0
  created_at: string // date-time
}

// v1.7.0 — việc người gọi làm được trên hồ sơ, theo ACL của backend
type DossierMyAccessDTO = {
  owner: boolean // người gọi là chủ hồ sơ
  permission: 'edit' | 'read' | null // null: không có lượt chia sẻ (chủ hồ sơ)
  expires_at: string | null
  expired: boolean
  can_edit: boolean // sửa hồ sơ (DOSSIER_EDIT)
  can_review: boolean // ghi thẩm định (REVIEW_MUTATE)
  can_see_review: boolean // xem thẩm định (REVIEW_READ)
  can_manage: boolean // chia sẻ / quản lý (DOSSIER_MANAGE)
  can_approve: boolean // phê duyệt (APPROVE)
}
```

Ví dụ một `REVIEWER` được chia sẻ quyền `edit`:

```json
{
  "locked": false,
  "approved_at": null,
  "my_access": {
    "owner": false,
    "permission": "edit",
    "expires_at": "2026-10-20T00:00:00+00:00",
    "expired": false,
    "can_edit": false,
    "can_review": true,
    "can_see_review": true,
    "can_manage": false,
    "can_approve": false
  }
}
```

- FE ẩn/hiện nút theo các cờ `can_*`, **không** tự suy ra từ `metadata.shared_with`.
- `my_access` chỉ trả lời theo ACL. Hồ sơ `locked: true` vẫn từ chối mọi thay đổi và review dù `can_*` là `true`, nên FE **vẫn phải xét `locked`**.
- `permission`: lượt chia sẻ còn hạn lâu nhất dành cho người gọi (ưu tiên `edit`). Không còn lượt nào còn hạn thì là lượt hết hạn gần nhất, kèm `expired: true`.

Map UI `Dossier`:

| UI                           | BE                                                                                   |
| ---------------------------- | ------------------------------------------------------------------------------------ |
| `id`                         | `id`                                                                                 |
| `title`                      | `name`                                                                               |
| `code`                       | `metadata.code` nếu FE ghi lúc upload/patch — **không có field `code` riêng**        |
| `status`                     | derive từ `latest_job_status` + `has_conflicts` / `open_review_items`                |
| `reviewNote`                 | ví dụ `${pending_conflicts} điều khoản bất thường`                                   |
| `documents`                  | **không có trên list** — cần `GET /dossiers/{id}` hoặc `GET .../documents`           |
| `updated`                    | list chỉ có `created_at` — `updated_at` ở **detail**                                 |
| `access` / chia sẻ           | `my_access` (v1.7.0); đổi quyền qua [20](#20-chia-sẻ-hồ-sơ-chỉ-đọc--được-sửa-có-hạn) |
| `progress` / `progressLabel` | **không có trên list** — poll `GET /runs?dossier_id=` hoặc SSE                       |

Điều hướng hiện tại `dossierOpenTo()`:

| UI status  | Route                   | Khi nối                                  |
| ---------- | ----------------------- | ---------------------------------------- |
| processing | `/tien-trinh-phan-tich` | mang `dossierId` + `runId` (query/state) |
| review     | `/doi-soat-xung-dot`    | mang `dossierId`                         |
| ready      | `/ho-so-hop-dong`       | mang `dossierId`                         |

RBAC list: **mọi user đã auth**.

---

## 3. Upload dossier

**FE:** `CreateDossierPage` ← `src/api/dossiers.ts` (`createDossier`, `patchDossier`)  
Đã chốt OpenAPI: màn `/tao-ho-so` gọi **3b** `POST /api/v1/dossiers` → **202**. Multipart `contract` + `metadata` JSON `{ name }` + `annexes[]`. Nhận `dossier_id` + `job_id`, hiện **UPLOADED**.

**Giới hạn (DOC-05b v2.0.1):** mỗi file tối đa 50 MiB (backend trả `413` JSON); trên bản online **cả request tối đa 100 MB** vì Cloudflare gói Free, quá thì Cloudflare trả `413` dạng **HTML** (không parse body). Bộ hồ sơ lớn hơn thì bớt phụ lục hoặc tải phụ lục qua `POST /dossiers/{id}/documents`.

Mã vụ việc / phân loại / quyền riêng tư **không** nằm trong body POST (OpenAPI metadata chỉ `{ name, tags?, notes? }`). Sau 202 FE gọi `PATCH /dossiers/{id}` `{ metadata: { code, category, privacy } }`. PATCH lỗi không huỷ hồ sơ vừa tạo.

Chỉ còn **1** POST tạo hồ sơ (3b). Endpoint cũ 3a `POST /dossiers/upload` (chạy pipeline trong tiến trình backend, không qua Kafka) **đã bị gỡ** — gọi vào sẽ nhận 404/405. Pipeline OCR tự chạy sau 3b: backend publish `dossier.uploaded`, worker gửi lệnh AI1 rồi AI2.

### 3b. Đã chốt — màn tạo hồ sơ: `POST /api/v1/dossiers` → **202**

OpenAPI `Body_create_dossier` / `DossierCreatedDTO`. Header: `Authorization`, `X-Tenant-Id`. RBAC: `OPERATOR` | `ADMINISTRATOR`.

Multipart:

| Field      | Type                                      | Bắt buộc |
| ---------- | ----------------------------------------- | -------- |
| `contract` | file PDF                                  | có       |
| `metadata` | **string JSON** `{ name, tags?, notes? }` | có       |
| `annexes`  | file[]                                    | không    |

```ts
type DossierCreatedDTO = {
  dossier_id: string
  job_id?: string | null
}
```

| HTTP | OpenAPI                       | UI                                                                                                                                                                                                             |
| ---- | ----------------------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| 202  | `{ data: DossierCreatedDTO }` | hiện UPLOADED + id                                                                                                                                                                                             |
| 400  | Missing contract file         | Thiếu tệp PDF hợp đồng                                                                                                                                                                                         |
| 403  | Insufficient role             | Chỉ vận hành và quản trị                                                                                                                                                                                       |
| 422  | Invalid metadata JSON         | Metadata không đúng JSON                                                                                                                                                                                       |
| 422  | `DOSSIER_TOO_MANY_DOCUMENTS`  | Quá 6 tệp (1 hợp đồng + tối đa 5 phụ lục). Giới hạn đếm tệp, không đếm trang. Hiện `error.message`, ví dụ: "Hồ sơ tối đa 6 file PDF (1 hợp đồng và tối đa 5 phụ lục). Bạn đã chọn 7 file." Không tạo hồ sơ nào |

Muốn chạy pipeline: `POST /dossiers/{id}/runs` ([4](#4-pipeline-run)).

Vai trò hợp đồng/phụ lục chọn lúc tải lên được backend tự xác nhận (`confirm_uploaded_manifest`, cũng chạy sau `POST /dossiers/{id}/split`), nên không có màn xác nhận manifest. Sau khi có `dossier_id`, màn `/tao-ho-so` mở `/tien-trinh-phan-tich/:dossierId` (hoặc `/tach-file/:dossierId` khi tệp gồm cả hợp đồng và phụ lục). Xem [19](#19-xác-nhận-manifest).

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
    confidence_threshold?: number | null // 0..1
  } | null
}

type PipelineRunSummaryDTO = {
  run_id: string
  dossier_id: string
  status: string // queued | running | completed | failed | cancelled
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

`ApiResponse<RunStepDTO[]>`, theo thứ tự S0..S10 (DOC-05 `RunStep`). Mỗi phần tử giống payload SSE `step.changed`. UI progress: endpoint này khi mở trang, rồi SSE `step.changed`.

```ts
type RunStepDTO = {
  step: string // S0..S10
  status: 'queued' | 'running' | 'succeeded' | 'failed'
  attempt: number
  pages: number | null
  duration_ms: number | null
  progress: StepProgressDTO | null // v3.2.0
  created_at: string
}

type StepProgressDTO = {
  done: number // 0..total
  total: number // >= 1
  unit: 'page' | 'document' | 'chunk' | 'clause' | 'pair'
}
```

**Tiến độ trong bước (`progress`, DOC-05b v3.2.0):**

- `null`: bước không đo được, UI hiện vòng quay. Có giá trị: UI ghi "37/202 trang" theo `unit` (trang, tài liệu, đoạn, điều khoản, cặp) và vẽ vòng %. `unit` lạ thì coi như `null` (`parseStepProgress` ở `src/api/runEvents.ts`).
- Bước `succeeded` có `done = total`. Bước quay lại `queued` (chạy lại) có `progress: null`. `done` không giảm.
- Trong lúc bước `running`, BE phát lại `step.changed` khi `done` tăng: không quá 1 lần mỗi giây, mỗi lần ít nhất 5% (khoảng 20 lần mỗi bước), hoặc tăng bất kỳ sau 15 giây. Bước đứng yên không có tin mới. Tin chỉ đổi `progress` thì UI chỉ cập nhật vòng tiến độ, không thêm dòng nhật ký và không tải lại cả hồ sơ mỗi lần.
- Nguồn theo bước:

| Bước           | `unit`                                            | Có số khi nào                                                                                                         |
| -------------- | ------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------- |
| S0, S1         | —                                                 | Luôn `null`                                                                                                           |
| S2             | `page` (`document` khi tài liệu chưa có số trang) | Trang đã OCR / tổng trang cả hồ sơ. Theo từng tài liệu xong; theo từng trang khi AI1 gửi `ai1.ocr.progress` (DOC-05d) |
| S3, S8         | như S2                                            | Chỉ được đánh dấu khi AI1 xong cả hồ sơ, nên thấy thẳng `done = total`                                                |
| S4–S7, S9, S10 | `chunk`, `clause`, `pair`…                        | Khi AI2 trả `progress` trong `GET /jobs/{id}` (#116). Trước đó `null`                                                 |

Nghĩa bước theo BE: S2 là cả lượt OCR của AI1 (chữ, bố cục, bảng); S4 là lúc AI2 bắt đầu xử lý hồ sơ. Nhãn ở `RUN_STEP_LABELS` theo nghĩa này.

**Không đọc được trang nào (v3.2.0):** AI1 trả mọi trang lỗi (ví dụ thiếu khoá OCR vision) thì job `failed` với `error_code: "AI1_NO_READABLE_PAGE"`, S2, S3, S8 `failed`, không gửi sang AI2. UI báo lỗi OCR và cho "Chạy lại phần OCR lỗi" (`POST /dossiers/{id}/ocr/retry-failed`) sau khi sửa cấu hình.

Danh sách file đang xử lý: `GET /dossiers/{id}/documents`. Trang OCR của một tài liệu chỉ có sau khi cả tài liệu xong; số trang đang đọc lấy từ `progress` của S2.

### Cancel: `POST /api/v1/runs/{run_id}/cancel`

403 / 404 / 409 (không cancellable).

### SSE realtime: `GET /api/v1/runs/{run_id}/events`

`text/event-stream`. Events:

| Event                | Khi nào                                                      |
| -------------------- | ------------------------------------------------------------ |
| `run.started`        | mở stream                                                    |
| `step.changed`       | 1 step S0..S10 đổi trạng thái, hoặc `progress` tăng (v3.2.0) |
| `run.status_changed` | đổi status run                                               |
| `run.completed`      | terminal → đóng stream                                       |
| `error`              | lỗi / run not found                                          |
| `:heartbeat`         | 15s                                                          |

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
  locked?: boolean // v1.7.0
  approved_at?: string | null // v1.7.0
  my_access?: DossierMyAccessDTO // v1.7.0 — kiểu ở mục 2
  created_at: string
  updated_at: string
}
```

`locked`, `approved_at`, `my_access` giống hệt trên list ([2](#2-list-dossier)): FE ẩn/hiện nút theo `my_access.can_*`, và vẫn phải xét `locked` (hồ sơ khoá thì backend từ chối thay đổi/review dù `can_*` là `true`).

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

**v2.0.2:** file đi thẳng từ storage theo từng khúc. `Range: bytes=a-b` (một khoảng) → `206` kèm `Content-Range`; khoảng ngoài file → `416`; `If-None-Match` khớp `ETag` (sha256 của file) → `304`. CORS cho đọc `Accept-Ranges`, `Content-Range`, `Content-Length`, `ETag`, nên pdf.js mở được bằng `getDocument({ url, httpHeaders })` để tải theo trang.

---

## 6. Page image + PDF

**FE:** zoom/page trên `CitationComparePage`, preview trang.

### `GET /api/v1/documents/{document_id}/pages`

```ts
type PageDTO = {
  id: string
  document_id: string
  page_no: number
  kind?: string // default "native"
  width_pt: number
  height_pt: number
  rotation?: number
  render_dpi?: number // default 300
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
  node_type: string // article > clause > point
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

| Query       | Default |                                          |
| ----------- | ------- | ---------------------------------------- |
| `effective` | `true`  | kèm `current_version` để optimistic lock |
| `key`       | —       | filter 1 fact key                        |

Response có ETag (dossier-level concurrency).

```ts
type CitationDTO = {
  id: string
  document_id: string
  run_id?: string | null
  quote?: string
  quote_sha256?: string
  segments?: unknown[] // bbox segments
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
  review_state?: string // default "unreviewed"
  reviewer_id?: string | null
  reviewed_at?: string | null
  review_item_id?: string | null
  current_version?: number // default 0 — BẮT BUỘC echo thành base_version
}
```

Map UI citation:

| UI                    | BE                                                            |
| --------------------- | ------------------------------------------------------------- |
| title / khoản         | `fact.key` + clause `context_clause_id` → [7](#7-clause-tree) |
| excerpt / quote       | `citation.quote` hoặc `fact.raw_text`                         |
| confidence            | `fact.confidence`                                             |
| page                  | `citation.segments` / clause `page_start`                     |
| hash                  | `citation.quote_sha256`                                       |
| status locked/waiting | `review_state` + review item `status`                         |

### Facts theo document: `GET /api/v1/documents/{document_id}/facts`

`ApiResponse<any[]>` — schema lỏng hơn dossier-level.

### `GET /api/v1/facts/{fact_id}` — `dict` + citation. 404.

### `GET /api/v1/citations/{citation_id}` — quote + segments bbox. 404.

Highlight PDF: lấy `segments` bbox, overlay lên ảnh [6](#6-page-image--pdf).

---

## 9. Conflict / finding

**FE:** `ClauseConflictPage` ← `src/data/clauseConflicts.ts`

Hai list:

| Endpoint                       | Ý nghĩa                                                                         |
| ------------------------------ | ------------------------------------------------------------------------------- |
| `GET /dossiers/{id}/findings`  | Mọi phát hiện                                                                   |
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

type FindingReviewLatestDTO = {
  action: string // confirm | reject (dữ liệu cũ có thể là correct)
  comment?: string | null
  reviewer_id?: string | null
  reviewer_name?: string | null
  reviewer_email?: string | null
  reviewed_at?: string | null // ISO 8601
  action_count?: number // tổng số lượt thẩm định của item
}

type FindingReviewDTO = {
  item_id: string
  status: string
  current_version?: number
  latest?: FindingReviewLatestDTO | null // v1.3.0; null khi chưa ai thẩm định
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
  sides?: FindingSideDTO[] // 2 phía đối sánh
  disclaimer?: string // default: không phải kết luận pháp lý
  review?: FindingReviewDTO | null
}
```

Map UI `ClauseConflict`:

| UI                    | BE                                                                             |
| --------------------- | ------------------------------------------------------------------------------ |
| `id` / `code`         | `id`                                                                           |
| `title` / `field`     | `key_or_topic`                                                                 |
| `comparison`          | ghép `sides[].value_snapshot`                                                  |
| `risk` high/resolved  | `severity` + `review.status` / `disposition`                                   |
| `diagnosis`           | `rationale`                                                                    |
| `source1` / `source2` | `sides[0]` / `sides[1]`                                                        |
| `value`               | `value_snapshot`                                                               |
| quote highlight       | `sides[].citation`                                                             |
| `choice`              | **không lưu trên finding** — submit [10](#10-review-hitl) qua `review.item_id` |

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
  priority?: string // default P3
  status?: string // default open
  version?: number // default 1 — dùng cho base_version
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
  action: string // confirm | correct | reject | needs_more_evidence
  base_version: number // version client đang thấy; 0 = machine baseline
  corrected_value?: Record<string, unknown> | null // bắt buộc nếu action=correct
  corrected_bbox?: unknown[] | null
  comment?: string | null // max 2000
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

| HTTP |                                                                                   |
| ---- | --------------------------------------------------------------------------------- |
| 200  | OK                                                                                |
| 403  | Sai role                                                                          |
| 404  | Không có item                                                                     |
| 409  | `base_version` lệch — body có `current_state`; reload item, gửi lại `version` mới |
| 422  | Action invalid / thiếu `corrected_value`                                          |

Map UI conflict:

| UI Decision                    | `action`                                                      |
| ------------------------------ | ------------------------------------------------------------- |
| confirm nguồn đã chọn          | `confirm` (kèm `corrected_value` nếu BE yêu cầu side đã pick) |
| overlay                        | `correct` + `corrected_value` / `corrected_bbox`              |
| reject                         | `reject`                                                      |
| (citation) needs more evidence | `needs_more_evidence` → status `awaiting_evidence`            |

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
  comment?: string | null // max 2000
}
```

409 preconditions not met (ví dụ còn open review / chưa lock — theo BE).

### External approval

`POST /api/v1/dossiers/{dossier_id}/external-approvals` → **201**  
RBAC **ADMINISTRATOR**. 409 nếu chưa approve hoặc đang có grant pending.

```ts
type ExternalApprovalRequestDTO = {
  provider: 'docusign' | 'sap_ariba' | 'corporate_sso'
  approver_email: string // 3..255
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

| Field      |                     |
| ---------- | ------------------- |
| `manifest` | file `manifest.csv` |
| `archive`  | ZIP                 |
| `name`     | optional            |

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

| Method   | Path                                     | Status                      |
| -------- | ---------------------------------------- | --------------------------- |
| GET/POST | `/optimization/campaigns`                | 200 / 201                   |
| GET      | `/optimization/campaigns/{campaign_id}`  | 200/404                     |
| GET/POST | `/optimization/candidates`               | 200 / 201                   |
| GET      | `/optimization/candidates/{id}`          | 200/404                     |
| POST     | `/optimization/candidates/{id}/promote`  | 200, 409 already production |
| GET/POST | `/optimization/experiments`              | 200 / 201                   |
| POST     | `/optimization/experiments/{id}/run`     | 202, 409 running/finished   |
| GET      | `/optimization/experiments/{id}/results` | 200                         |

```ts
type CreateCampaignRequestDTO = {
  name: string // 1..255
  description?: string | null
  target_metric: 'f1_score' | 'precision' | 'latency' | 'cost'
  baseline_score: number
}

type CreateCandidateRequestDTO = {
  campaign_id: string
  name: string
  prompt_template: string
  model_name: string
  temperature?: number // default 0
}

type CreateExperimentRequestDTO = {
  campaign_id: string
  candidate_id: string
  golden_dataset_version: string
  sample_size?: number // default 100, min 1
}
```

DTO đọc: `OptimizationCampaignDTO`, `OptimizationCandidateDTO`, `OptimizationExperimentDTO`, `ExperimentResultDTO` (f1, precision, recall, latency, cost, breakdown_by_clause_type).

---

## 14. Health & AI job

Thường không gắn UI user. Dùng khi hiện “AI down” trên màn progress.

| Method | Path                       | Auth                    | Ý nghĩa                                                              |
| ------ | -------------------------- | ----------------------- | -------------------------------------------------------------------- |
| GET    | `/health`                  | spec vẫn liệt kê bearer | health đơn giản                                                      |
| GET    | `/api/v1/healthz`          | bearer trên spec        | liveness — luôn 200 nếu process sống                                 |
| GET    | `/api/v1/readyz`           | bearer                  | readiness DB + AI; **503** nếu AI down (HTTP mode)                   |
| GET    | `/api/v1/ai/jobs/{job_id}` | bearer                  | proxy AI `GET /jobs/{id}` — poll không cần biết dossier. 502 AI down |
| DELETE | `/api/v1/ai/jobs/{job_id}` | OPERATOR+               | proxy cancel AI job                                                  |

`job_id` dossier: `DossierCreatedDTO.job_id` / `latest_job_id` / `ReprocessAcceptedDTO.job_id` — khác `run_id`.

---

## 15. FE có — BE chưa có endpoint

Giữ mock hoặc ẩn màn cho đến khi BE bổ sung. Đừng bịa API.

| UI                                                                      | File                | Lý do                                                                    |
| ----------------------------------------------------------------------- | ------------------- | ------------------------------------------------------------------------ |
| Login Google / SSO / quick admin-user                                   | `LoginPage`         | Auth = Keycloak ngoài OpenAPI; API chỉ `/auth/me`                        |
| Tổng quan: dung lượng, hoạt động tenant, số hồ sơ chia sẻ, xuất báo cáo | `BE-OVERVIEW.md`    | User list và dossier list đã nối. Các phần còn lại chưa có endpoint      |
| Người dùng & phân quyền                                                 | `UsersPage`         | FE đã gọi. BE làm theo `BE-USER-ADMIN.md` — [18](#18-quản-lý-người-dùng) |
| Được chia sẻ với tôi                                                    | Placeholder         | Không có share grant                                                     |
| Tìm kiếm xuyên hồ sơ                                                    | Placeholder         | `GET /dossiers?q=` chỉ search **tên** dossier                            |
| Tìm trong 1 hồ sơ (Ctrl+K)                                              | `dossierSearch.ts`  | Không có full-text / semantic search                                     |
| Nhật ký pháp lý toàn dossier                                            | `auditLog.ts`       | Chỉ `review-items/.../revisions` theo 1 item                             |
| Quyền riêng tư / chia sẻ lúc tạo HS                                     | `CreateDossierPage` | Không có field privacy; nhét `metadata` nếu BE chấp nhận opaque object   |
| Mã vụ việc `code`                                                       | list + create       | Không có field; dùng `metadata.code`                                     |
| Kho điều khoản mẫu                                                      | Placeholder         | Không có                                                                 |
| Tuân thủ & rủi ro (trang riêng)                                         | Placeholder         | Gần nhất: findings/conflicts                                             |
| Trung tâm phân tích                                                     | Placeholder         | Gần nhất: ops metrics + optimization (admin)                             |
| Cài đặt                                                                 | Placeholder         | Không có                                                                 |

---

## 16. Thứ tự nối đề xuất

1. **Client** — Bearer + `X-Tenant-Id` + unwrap `{ data, meta }` + lỗi 401/403/409
2. **Auth** — Keycloak token → `GET /auth/me` → bỏ `DEMO_USERS`
3. **Upload** — màn `/tao-ho-so` dùng `POST /dossiers` (3b) → `dossier_id` + `job_id`, status UPLOADED, rồi xác nhận manifest ([19](#19-xác-nhận-manifest)). Pipeline tự chạy qua Kafka (endpoint 3a đã gỡ)
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

| Method | Path                         | Việc                                                      |
| ------ | ---------------------------- | --------------------------------------------------------- |
| GET    | `/api/v1/users`              | Danh sách. Query `q`, `role`, `status`, `limit`, `offset` |
| POST   | `/api/v1/users`              | Tạo user + email đặt mật khẩu                             |
| PATCH  | `/api/v1/users/{id}`         | Đổi `role`                                                |
| POST   | `/api/v1/users/{id}/disable` | Khóa                                                      |
| POST   | `/api/v1/users/{id}/enable`  | Mở khóa                                                   |
| POST   | `/api/v1/users/{id}/invite`  | Gửi lại email                                             |
| GET    | `/api/v1/users/lookup`       | Một thành viên cùng tenant theo đúng email (v4.0.0)       |

RBAC: **ADMINISTRATOR** only, trừ `GET /users/lookup` (cả **OPERATOR**, để chia sẻ hồ sơ bằng email).

**v4.0.0:** email thuộc tên miền không nhận thư (`.local`, `.test`, `.example`, `.invalid`, `localhost`, `example.com/net/org`) thì `POST /users` và `POST /users/{id}/invite` trả `422 email_domain_undeliverable`, không tạo người dùng, không gửi thư. FE hiện "Tên miền email không nhận được thư, vui lòng kiểm tra lại." (`userAdminErrorMessage`).

**v5.1.0, thư mời bị trả về:** Gmail nhận thư mời cả khi địa chỉ không tồn tại, rồi mới gửi thư "Address not found" về hộp thư gửi. Backend đọc thư đó qua IMAP và trả `invite_delivery` (`pending` khi vừa gửi, `sent` khi quá 10 phút không thấy thư trả về, `bounced` khi bị trả thư, `null` khi không biết) cùng `invite_delivery_reason` (`mailbox_not_found` hoặc `rejected`). FE: `UsersPage` hiện "Đang chờ xác nhận gửi thư" dưới nhãn "Đã mời" khi `pending`, và nhãn đỏ "Không gửi được thư" khi `bounced`. Trong lúc còn người `pending` trên trang hoặc người vừa tạo, vừa gửi lại lời mời, trang hỏi lại `GET /users` mỗi 10 giây (người vừa tạo được hỏi bằng `q=<email>`). Khi một người chuyển sang `bounced`, trang hiện cảnh báo không tự đóng do `inviteBounceMessage` (`src/api/users.ts`) dựng: "Không gửi được email mời tới <email> vì không tìm thấy địa chỉ này. Kiểm tra lại email và tạo người dùng với địa chỉ đúng." Backend không đọc được hộp thư (`invite_delivery = null`) thì trang giữ như trước.

### `GET /api/v1/users/lookup?email=` (v4.0.0)

OPERATOR, ADMINISTRATOR. Trả `{ id, email, display_name, role }` khi có đúng một người **đã kích hoạt** cùng tenant trùng đúng email (không phân biệt hoa thường). Khác tenant, bị khoá, chưa kích hoạt (`invited`) hay không tồn tại đều trả `404 user_not_found` cùng một câu. FE: `lookupUserByEmail` (`src/api/users.ts`) trả `null` khi 404, màn Quyền truy cập báo "Không tìm thấy email này trong đơn vị của bạn, hoặc người này chưa kích hoạt tài khoản. Vui lòng kiểm tra lại." Chỉ chia sẻ bằng email với người đã kích hoạt (Lead chốt 18/10, PR #128). `OPERATOR` và `REVIEWER` vẫn vào cùng giao diện user; chỉ `ADMINISTRATOR` vào trang này.

---

## 19. Xác nhận manifest

**FE:** không có màn xác nhận manifest và không gọi hai endpoint dưới đây. Backend tự xác nhận vai trò đã chọn lúc tải lên (`POST /dossiers`) và lúc tách tệp (`POST /dossiers/{id}/split`) bằng `confirm_uploaded_manifest` (`contract_router.py`), trước khi trả `202`. Worker chỉ gửi hồ sơ sang AI2 khi manifest đã `confirmed`, nên OCR xong là AI2 chạy ngầm, không chờ người dùng.

**BE:** hai endpoint vẫn có trên OpenAPI, dùng được cho công cụ hoặc client khác:

| Method | Path                                             | Việc                                  |
| ------ | ------------------------------------------------ | ------------------------------------- |
| GET    | `/api/v1/dossiers/{dossier_id}/manifest`         | Bản đề xuất: members, role, relations |
| POST   | `/api/v1/dossiers/{dossier_id}/manifest/confirm` | Ghi nhận xác nhận                     |

RBAC: **OPERATOR** hoặc **ADMINISTRATOR**. `REVIEWER` nhận 403. Confirm không tạo pipeline run.

## 20. Chia sẻ hồ sơ: chỉ đọc / được sửa, có hạn

### `PUT /api/v1/dossiers/{dossier_id}/access`

Chỉ **chủ hồ sơ** hoặc **ADMINISTRATOR** gọi được. Người khác nhận 403, kể cả khi được chia sẻ quyền `edit`.

```json
{
  "scope": "shared_out",
  "shared_with": [
    {
      "id": "usr_…",
      "email": "a@vgr.vn",
      "display_name": "A",
      "permission": "read",
      "expires_at": "2026-10-18T17:00:00+07:00"
    }
  ]
}
```

| Trường       | Giá trị                             | Ghi chú                                                                                                                                                                                                             |
| ------------ | ----------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `permission` | `read` \| `edit`                    | `read`: xem hồ sơ, điều khoản, fact, finding, hỏi đáp. `edit`: thêm thẩm định, chạy lại OCR/AI2, sửa hồ sơ, xác nhận manifest. **Bỏ trống thì là `edit`**, để client cũ chạy như trước. FE nên luôn gửi trường này. |
| `expires_at` | ISO-8601 hoặc `null`                | Phải ở tương lai, nếu không trả **422**. Server lưu theo UTC (`…+00:00`). `null` là không hết hạn.                                                                                                                  |
| `status`     | `invited` \| `active` \| `disabled` | `disabled` thu hồi quyền ngay.                                                                                                                                                                                      |

Khi quyền hết hạn hoặc bị `disabled`:

- Hồ sơ biến khỏi `GET /dossiers` của người được chia sẻ.
- Mọi API trên hồ sơ đó trả **403**, kể cả SSE `/runs/{id}/events`.

Người có quyền `read` gọi API sửa thì nhận **403**, `detail`: "Bạn chỉ có quyền xem hồ sơ này, hoặc quyền đã hết hạn." Các API sửa gồm: `PATCH /dossiers/{id}`, `POST /dossiers/{id}/ocr`, `/ai2/retry`, `/runs`, `/reprocess`, `/manifest/confirm`, `POST /runs/{id}/cancel`, `POST /documents/{id}/re-ocr` và `POST /review-items/{id}/actions`.

**v4.0.0, kiểm tra người nhận:** người nhận mới (`id` chưa có trong `shared_with` đang lưu) phải là người dùng đang bật cùng tenant với người gọi; `id`, `email`, `display_name`, `status` lấy từ Keycloak, không lấy từ body. Có người không hợp lệ thì trả `422 share_recipient_not_found` (`details.rejected_emails`), Keycloak không trả lời thì `503 keycloak_unavailable`; cả hai trường hợp đều không lưu gì, không gửi thư. Người đã được chia sẻ gửi lại thì giữ danh tính đã lưu, chỉ đổi `permission`/`expires_at`. Thư chia sẻ tới tên miền không nhận thư bị bỏ qua, quyền vẫn lưu. FE: `accessSaveErrorMessage` (`src/api/dossiers.ts`) hiện câu không tìm thấy kèm các email bị từ chối.

**v5.0.0, không gửi được thư thì không có quyền** (`scope=shared_out`, người nhận mới): email trống hoặc thuộc tên miền không nhận thư (`.local`, `.test`…) trả `422 share_recipient_undeliverable` (`details.rejected_emails`), không lưu gì. Gửi thư lỗi (Keycloak/SMTP) thì backend gỡ người đó khỏi `shared_with` sau khi gửi và trả `email_not_sent: { email: string; reason: 'undeliverable' | 'send_failed' }[]` (rỗng khi ai cũng nhận được); gỡ hết thì `scope` là `mine`. Lượt chia sẻ cũ giữ nguyên. FE: `accessSaveErrorMessage` hiện lỗi 422 trong hộp chia sẻ; `shareEmailNotice` (`src/api/dossiers.ts`) dựng cảnh báo cho `email_not_sent`, `AccessPage` hiện và không tự đóng.

`DELETE /dossiers/{id}` và `PUT /dossiers/{id}/access` chỉ chủ hồ sơ hoặc ADMINISTRATOR. `PATCH /dossiers/{id}` bỏ qua `created_by`, `access_scope`, `shared_with` trong `metadata`. Muốn đổi quyền thì dùng endpoint này.

## 21. Lịch sử hỏi đáp

### `GET /api/v1/dossiers/{dossier_id}/queries?limit=20&offset=0`

Trả các lần hỏi đáp (`/ask`, `/query`, `/search`) trên hồ sơ, mới nhất trước. Dữ liệu lưu trong DB nên vẫn còn sau khi server khởi động lại.

Chỉ trả câu hỏi **của chính người gọi**, kể cả chủ hồ sơ và ADMINISTRATOR (Lead chốt 14/10, DOC-05b `v2.0.0`). `scope` chỉ còn nhận `mine` (mặc định); `scope=all` trả `422`. Frontend không gửi `scope=all`.

Cần quyền xem hồ sơ (như `GET /dossiers/{id}`). Người khác tenant, hoặc có quyền chia sẻ đã hết hạn / bị tắt, nhận 403/404.

```json
{
  "data": [
    {
      "trace_id": "qtr_…",
      "endpoint": "ask",
      "actor_id": "usr_…",
      "question": "Giá trị hợp đồng là bao nhiêu?",
      "answer": "1.286.400.000 đồng",
      "state": "PASS",
      "citations": [],
      "error_code": null,
      "created_at": "2026-10-01T09:12:00+00:00"
    }
  ],
  "meta": { "page": 1, "page_size": 20, "total": 1 }
}
```

`endpoint` là `ask`, `query` hoặc `search` (thanh hỏi đáp). Lần hỏi mà AI2 lỗi vẫn có trong lịch sử, với `answer: null` và `error_code` (ví dụ `AI2_QUERY_FAILED`). Với `search`, `error_code` là `AI2_UNAVAILABLE` khi AI2 lỗi hoặc quá thời gian chờ. Câu hỏi gửi qua `search` trước DOC-05b v1.5.1 chỉ có trace, nên hiện với `answer: null` và `error_code: null`. Xoá hồ sơ thì câu trả lời bị xoá theo.

## 22. Chạy lại phần OCR lỗi (giữ phần đã xong)

### `POST /api/v1/dossiers/{dossier_id}/ocr/retry-failed` → **202**

Dùng khi hồ sơ lỗi ở bước OCR (`latest_job_status = failed` với mã lỗi OCR, ví dụ `AI1_TIMEOUT`, `AI1_OCR_FAILED`, `AI1_RESULT_UNREADABLE`).

- Backend mở run mới, **giữ kết quả OCR của các tài liệu đã xong** (kể cả kết quả về sau khi run đã lỗi), và chỉ gửi lại tài liệu còn thiếu cho AI1.
- Nếu mọi tài liệu đã có kết quả, run chuyển thẳng sang AI2, không OCR lại trang nào.
- Theo dõi tiến độ bằng SSE `/runs/{run_id}/events` của run mới, như khi upload.

| Trả về                     | Khi nào                                                                    |
| -------------------------- | -------------------------------------------------------------------------- |
| 202 `{"status": "queued"}` | Đã nhận                                                                    |
| 409                        | Job không lỗi ở bước OCR. Lỗi AI2 thì dùng `POST /dossiers/{id}/ai2/retry` |
| 403                        | Không có quyền sửa hồ sơ (§20)                                             |

`POST /dossiers/{id}/ocr` (chạy lại OCR toàn bộ) vẫn giữ nguyên hành vi cũ.

## 23. Tách file trộn (hợp đồng + phụ lục trong một PDF)

**Bước 1: tải lên nhưng chưa xử lý.** `POST /api/v1/dossiers` như cũ, thêm `"split_pending": true` vào `metadata`:

```json
{ "name": "Hợp đồng kèm phụ lục", "split_pending": true }
```

Backend lưu file nhưng **chưa gửi OCR**, để không trang nào bị OCR hai lần.

**Bước 2: người dùng xác nhận khoảng trang và vai trò.** `POST /api/v1/dossiers/{dossier_id}/split` → **202**

```json
{
  "document_id": "doc_… (file vừa tải)",
  "parts": [
    { "page_start": 1, "page_end": 6, "role": "contract" },
    { "page_start": 7, "page_end": 10, "role": "annex" }
  ]
}
```

- Mỗi phần thành **một tài liệu riêng** (PDF cắt từ file gốc). File gốc bị bỏ.
- Vai trò được xác nhận, rồi mọi tài liệu được gửi OCR riêng, như khi tải lên từng file.
- Theo dõi tiến độ bằng SSE như thường lệ.
- Gửi **một phần phủ cả file** nghĩa là không cần tách, xử lý luôn.

Trả về: `{ dossier_id, status: "queued", documents: [{ id, role, filename, page_start, page_end, page_count }] }`.

| Lỗi                                             | Khi nào                                                                                                                                                                                                      |
| ----------------------------------------------- | ------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------ |
| 422                                             | Các phần không phủ đủ trang 1..N theo thứ tự (thiếu, chồng lấn), hoặc `page_end < page_start`                                                                                                                |
| 422 `contract_required` / `contract_not_unique` | Hồ sơ không có, hoặc có nhiều hơn **một**, hợp đồng                                                                                                                                                          |
| 422 `DOSSIER_TOO_MANY_DOCUMENTS`                | Sau khi tách hồ sơ quá 6 tài liệu (mỗi phần là một tài liệu, cộng các tài liệu khác của hồ sơ). Hiện `error.message`, ví dụ: "Sau khi tách, hồ sơ tối đa 6 tài liệu. Cách tách này làm hồ sơ có 7 tài liệu." |
| 409                                             | Hồ sơ không tải lên với `split_pending`, hoặc đã bắt đầu xử lý (tách lúc này sẽ OCR lại)                                                                                                                     |
| 403                                             | Không có quyền sửa hồ sơ                                                                                                                                                                                     |

Chưa có: AI1 tự đề xuất chỗ cắt. Hiện người dùng nhập khoảng trang trên màn xác nhận.

## 24. Thông báo cá nhân (đề xuất, BE chưa có)

Đề xuất trong DOC-05b v1.6.0, mục "Thông báo cá nhân": `GET /notifications`, `GET /notifications/unread-count`, `POST /notifications/{id}/read`, `POST /notifications/read-all`. Backend **chưa có**.

`NotificationBell` (`src/api/notifications.ts`) đã gọi đúng 4 endpoint này, nhưng chỉ hiện khi build với `VITE_ENABLE_NOTIFICATIONS=true`. Cờ mặc định tắt. Khi backend xong thì bật cờ.

Header `X-API-Contract` lên thẳng `v1.7.0` từ `v1.5.1`, bỏ qua `v1.6.0` vì 4 endpoint này chưa có.

## 25. Danh bạ thành viên & hàng chờ thẩm định (v1.7.0)

DOC-05b `v1.7.0`, mục "Chia sẻ hồ sơ & hàng chờ thẩm định". Backend **đã có**. Response bọc `{ data, meta }`, phân trang bằng `limit` (1..100, mặc định 20) và `offset`; `meta.total` là tổng số dòng.

### `GET /api/v1/users/directory?q=&role=&limit=20&offset=0`

Danh bạ thành viên cùng tenant để chọn người khi chia sẻ hồ sơ ([20](#20-chia-sẻ-hồ-sơ-chỉ-đọc--được-sửa-có-hạn)).

| Param    | Type                                         | Mặc định | Ý nghĩa                                                       |
| -------- | -------------------------------------------- | -------- | ------------------------------------------------------------- |
| `q`      | string?                                      | —        | Tìm theo email hoặc tên hiển thị (không phân biệt hoa thường) |
| `role`   | `OPERATOR` \| `REVIEWER` \| `ADMINISTRATOR`? | —        | Dùng `role=REVIEWER` cho ô "Giao cho người thẩm định"         |
| `limit`  | 1..100                                       | 20       |                                                               |
| `offset` | ≥0                                           | 0        |                                                               |

```json
{
  "data": [
    {
      "id": "8f1c…",
      "email": "reviewer@ci.local",
      "display_name": "Demo Reviewer",
      "role": "REVIEWER"
    }
  ],
  "meta": {
    "trace_id": null,
    "request_id": null,
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

- Mỗi người chỉ có đúng 4 trường `id`, `email`, `display_name`, `role`. `id` (Keycloak `sub`) là `id` của phần tử `shared_with` khi gọi `PUT /dossiers/{id}/access`.
- Chỉ trả người đang `active` và có `tenant_id` trùng tenant của người gọi. User không có `tenant_id`, người `invited` (chưa đặt mật khẩu) và `disabled` **không** hiện. Khác `GET /users` của ADMINISTRATOR ([18](#18-quản-lý-người-dùng)), nơi user không có `tenant_id` vẫn hiện.
- Sắp xếp theo email.

RBAC: **OPERATOR**, **ADMINISTRATOR**. `REVIEWER` nhận 403.

| Lỗi                        | Khi nào                 |
| -------------------------- | ----------------------- |
| 401                        | Token không hợp lệ      |
| 403                        | Người gọi là `REVIEWER` |
| 503 `keycloak_unavailable` | Keycloak không trả lời  |

### `GET /api/v1/review-queue?limit=20&offset=0`

Hồ sơ còn mục review mở (`open` hoặc `awaiting_evidence`) mà người gọi được thẩm định: là chủ hồ sơ, hoặc được chia sẻ quyền `edit` còn hạn. `ADMINISTRATOR` cũng cần là chủ hoặc có chia sẻ.

| Param    | Type   | Mặc định |
| -------- | ------ | -------- |
| `limit`  | 1..100 | 20       |
| `offset` | ≥0     | 0        |

```json
{
  "data": [
    {
      "dossier_id": "dos_…",
      "dossier_name": "Hợp đồng mua bán 2026",
      "dossier_status": "pending_review",
      "created_at": "2026-10-09T09:12:00+00:00",
      "is_owner": false,
      "grant_expires_at": "2026-10-20T00:00:00+00:00",
      "open_review_items": 5,
      "pending_conflicts": 2,
      "p1": 1,
      "p2": 3,
      "p3": 1
    }
  ],
  "meta": {
    "trace_id": null,
    "request_id": null,
    "page": 1,
    "page_size": 20,
    "total": 1
  }
}
```

- Sắp xếp: hồ sơ nhiều mục P1 hơn xếp trước, rồi tới hồ sơ tạo sớm hơn.
- `open_review_items` bằng `p1 + p2 + p3`; `pending_conflicts` là phần nằm trên finding (xung đột chưa xử lý).
- `grant_expires_at`: lúc quyền thẩm định của người gọi hết hạn; `null` với chủ hồ sơ hoặc lượt chia sẻ không có hạn.
- Không có hồ sơ nào thì `data: []`, `meta.total: 0`.

RBAC: **REVIEWER**, **ADMINISTRATOR**. `OPERATOR` nhận 403.

| Lỗi | Khi nào                 |
| --- | ----------------------- |
| 401 | Token không hợp lệ      |
| 403 | Người gọi là `OPERATOR` |

## 26. Đồ thị hợp đồng, vết xử lý và consent AI2 (v2.1.0)

Đọc kết quả AI2 qua backend; frontend không gọi AI2 trực tiếp. Chi tiết ở DOC-05b, mục "Đồ thị hợp đồng, vết xử lý và consent AI2 (v2.1.0)".

| Phương thức | Endpoint                                                         | Quyền                                                 | Ghi chú                                                                                                                                                         |
| ----------- | ---------------------------------------------------------------- | ----------------------------------------------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| `GET`       | `/api/v1/dossiers/{id}/ai2/contract-graph/{graph_kind}`          | đọc trích dẫn                                         | `graph_kind`: `pair` (Quan hệ điều khoản) hoặc `operation` (Sửa đổi điều khoản). Query bắt buộc `job_id`, `snapshot_digest`; tuỳ chọn `cursor`, `limit` (1–100) |
| `GET`       | `/api/v1/dossiers/{id}/ai2/contract-graph/{graph_kind}/evidence` | đọc trích dẫn                                         | Bằng chứng của một quan hệ: `job_id`, `snapshot_digest`, `node_id`, `citation_ref`                                                                              |
| `GET`       | `/api/v1/dossiers/{id}/ai2/processing-trace`                     | đọc trích dẫn                                         | Vết xử lý AI2: `job_id`, `snapshot_digest`                                                                                                                      |
| `PATCH`     | `/api/v1/dossiers/{id}/ai2-content-sharing-consent`              | chủ hồ sơ hoặc ADMINISTRATOR (`my_access.can_manage`) | Body `{"enabled": true}` hoặc `false`. Trả `{dossier_id, enabled, effective_from: "next_request", ai2_reindex_queued}` (v3.1.0)                                 |

- `snapshot_digest` phải là của hồ sơ hiện tại, không thì `409 AI2_SNAPSHOT_CHANGED`. `next_cursor` gửi lại nguyên văn; con trỏ hỏng `400 GRAPH_CURSOR_INVALID`, của lần chạy khác `409 GRAPH_CURSOR_STALE`.
- Quan hệ do đồ thị sinh ra luôn ở trạng thái chờ rà soát; UI không hiển thị như đã duyệt.
- Consent đọc ở `detail.metadata.ai2_content_sharing_consent === true`. Hồ sơ mới nhận mặc định của server (bản online: bật). Chỉ người có `can_manage` thấy ô bật/tắt; người khác chỉ thấy trạng thái. `PATCH /dossiers/{id}` thường không đổi được trường này.
- **v3.1.0:** bật consent (từ chưa bật sang `true`) cho hồ sơ mà lượt chạy cuối đã qua AI2 thì backend tự cho AI2 dựng lại hồ sơ từ OCR đã lưu, trả `ai2_reindex_queued: true`; kết quả mới có sau khi lượt đó xong. `false` khi tắt consent, consent đã bật sẵn, hồ sơ chưa qua AI2, hoặc không gửi được sự kiện (consent vẫn lưu; dùng `POST /dossiers/{id}/ai2/reindex`).
- `503` (`AI2_GRAPH_UNAVAILABLE`, `AI2_GRAPH_EVIDENCE_UNAVAILABLE`, `AI2_TRACE_UNAVAILABLE`): AI2 chưa trả được, cho thử lại.
