# Xác nhận manifest — việc backend cần làm

Frontend đã có màn `/xac-nhan-manifest/:dossierId` (`src/pages/ManifestConfirmPage.tsx`) và đã gọi các API trong file này (`src/api/manifest.ts`). Backend chưa có các path này.

Sau `POST /api/v1/dossiers`, hồ sơ ở trạng thái job `uploaded`. Operator hoặc administrator mở màn này để xác nhận ba thứ: tài liệu nào thuộc hồ sơ (membership), vai trò từng tài liệu, và quan hệ giữa các tài liệu. Quan hệ đề xuất phải có `confirmation: "unconfirmed"` cho đến khi người dùng xác nhận hoặc bác bỏ. Frontend đánh dấu rõ từng dòng đó và không gửi xác nhận khi còn dòng chưa xác nhận.

Màn này không gọi `POST /dossiers/{id}/runs`. Pipeline phân tích vẫn là bước sau.

`REVIEWER` không xác nhận manifest. Chỉ `OPERATOR` và `ADMINISTRATOR`.

---

## 1. API

Prefix `/api/v1`. Envelope giống các API khác:

```json
{ "data": {}, "meta": {} }
```

Header request FE đã gửi: `Authorization: Bearer <jwt>`, `X-Tenant-Id`, `Accept: application/json`, `X-Request-Id`. Body JSON kèm `Content-Type: application/json`.

RBAC cả GET và POST: **`OPERATOR` hoặc `ADMINISTRATOR`**. Role khác, kể cả `REVIEWER`, trả **403**. Sai tenant trả **404** (không lộ hồ sơ tenant khác).

### `ManifestMemberDTO`

```ts
type DocumentRole = 'contract' | 'annex'

type ManifestMemberDTO = {
  document_id: string
  filename: string
  role: DocumentRole
  included: boolean          // true = thuộc hồ sơ sau khi xác nhận
  order_index: number
  page_count?: number | null
  file_size_bytes?: number | null
}
```

`included: false` giữ file đã upload nhưng tài liệu không nằm trong tập thành viên gửi sang AI2. Không xóa blob.

### `ManifestRelationDTO`

```ts
type RelationType = 'annex_of' | 'amends' | 'supersedes' | 'supplements'
type RelationConfirmation = 'unconfirmed' | 'confirmed' | 'rejected'

type ManifestRelationDTO = {
  id: string
  source_document_id: string
  target_document_id: string
  relation_type: RelationType
  confirmation: RelationConfirmation
}
```

Câu trên UI:

| `relation_type` | Nghĩa |
|---|---|
| `annex_of` | nguồn là phụ lục của đích |
| `amends` | nguồn sửa đổi đích |
| `supersedes` | nguồn thay thế đích |
| `supplements` | nguồn bổ sung đích |

`unconfirmed` là đề xuất, chưa phải sự thật. FE tô dòng này (nền và nhãn "Chưa xác nhận") cho đến khi người dùng bấm xác nhận hoặc bác bỏ.

### `ManifestDTO`

```ts
type ManifestDTO = {
  dossier_id: string
  status: 'pending' | 'confirmed'
  version: number             // tăng 1 mỗi lần confirm thành công
  latest_job_status?: string | null
  members: ManifestMemberDTO[]
  relations: ManifestRelationDTO[]
  confirmed_at?: string | null // ISO-8601, null khi pending
}
```

`status` của manifest khác `latest_job_status`. Confirm không đổi job status và không tạo run.

### Đề xuất lúc tạo hồ sơ

Trong `POST /api/v1/dossiers`, sau khi ghi document:

- Tệp `contract` → member `role: "contract"`, `included: true`, `order_index: 0`.
- Từng tệp annex, theo thứ tự nhận → member `role: "annex"`, `included: true`, `order_index` từ 1.
- Mỗi annex có một quan hệ tới hợp đồng: `relation_type: "annex_of"`, `confirmation: "unconfirmed"`, `id` mới.
- Không có annex thì `relations: []`.
- `status: "pending"`, `version: 1`, `confirmed_at: null`.

FE không tự tạo quan hệ đề xuất khi danh sách rỗng.

### `GET /api/v1/dossiers/{dossier_id}/manifest`

`200` → `data: ManifestDTO`.

Dùng để dựng lại màn sau refresh. FE không giữ manifest trong state của trang upload.

### `POST /api/v1/dossiers/{dossier_id}/manifest/confirm`

```json
{
  "version": 1,
  "members": [
    { "document_id": "doc-contract", "role": "contract", "included": true },
    { "document_id": "doc-annex", "role": "annex", "included": true }
  ],
  "relations": [
    {
      "id": "rel-1",
      "source_document_id": "doc-annex",
      "target_document_id": "doc-contract",
      "relation_type": "annex_of",
      "confirmation": "confirmed"
    }
  ]
}
```

- `version`: đúng bản client đang thấy.
- `members`: đủ mọi document của hồ sơ, không thêm id lạ, không bỏ id. `role` là `contract` hoặc `annex`.
- `relations[].id`: id đã có, hoặc `null` khi người dùng thêm quan hệ mới trên màn.
- `relations[].confirmation`: chỉ `confirmed` hoặc `rejected`. Gửi `unconfirmed` thì **422** `relations_unconfirmed`.
- Quan hệ đang lưu mà body bỏ sót: **422** `relation_missing`. Nếu quan hệ đó còn `unconfirmed`, code ưu tiên `relations_unconfirmed`.
- Ít nhất một member `included: true` và `role: "contract"`. Không thì **422** `contract_required`.
- Quan hệ `confirmed` phải nối hai member `included: true`, hai id khác nhau, đúng `relation_type`. Quan hệ `rejected` được phép trỏ tới member `included: false`.
- Trùng cùng nguồn, đích và `relation_type` trong các quan hệ không `rejected`: **422** `relation_duplicate`.

`200` → `data: ManifestDTO` với `status: "confirmed"`, `version` tăng 1, `confirmed_at` là thời điểm ghi, mọi quan hệ trả về chỉ còn `confirmed` hoặc `rejected` (không còn `unconfirmed`). `latest_job_status` giữ nguyên, thường là `uploaded`.

Việc backend làm, trong một transaction:

1. Khóa dossier theo tenant.
2. Từ chối nếu manifest đã `confirmed`.
3. So `version`.
4. Kiểm members và relations theo quy tắc trên.
5. Ghi membership, role, relation. Quan hệ `id: null` được cấp id mới.
6. Không xóa file của member `included: false`.
7. Không tạo pipeline run.

### Lỗi

FE đọc `detail` (string) và `code` (nếu có).

```json
{ "detail": "Còn quan hệ chưa xác nhận", "code": "relations_unconfirmed" }
```

| HTTP | `code` | Khi nào |
|---|---|---|
| 401 | | JWT không hợp lệ hoặc hết hạn |
| 403 | | Không phải `OPERATOR` hoặc `ADMINISTRATOR` |
| 404 | | `{dossier_id}` không có trong tenant. Detail `Not Found` thuần (route chưa mount) FE hiểu là API chưa được triển khai |
| 409 | `manifest_version_conflict` | `version` lệch. FE tải lại GET |
| 409 | `manifest_already_confirmed` | Gửi confirm khi đã `confirmed` |
| 422 | `relations_unconfirmed` | Còn quan hệ `unconfirmed`, hoặc body gửi `confirmation: "unconfirmed"` |
| 422 | `relation_missing` | Body bỏ một quan hệ đã có |
| 422 | `contract_required` | Không còn hợp đồng chính thuộc hồ sơ |
| 422 | `member_missing` | Thiếu document của hồ sơ |
| 422 | `member_unknown` | `document_id` không thuộc hồ sơ |
| 422 | `member_role_invalid` | `role` ngoài `contract` \| `annex` |
| 422 | `relation_member_invalid` | Quan hệ `confirmed` không nối hai member đang thuộc hồ sơ |
| 422 | `relation_self` | Nguồn và đích trùng nhau |
| 422 | `relation_duplicate` | Trùng bộ nguồn, đích, loại quan hệ |
| 422 | `relation_type_invalid` | `relation_type` ngoài enum |
| 422 | | Body sai kiểu, thiếu field |

Không có idempotent replay. Lần POST thứ hai sau khi đã confirmed trả 409 `manifest_already_confirmed`.
