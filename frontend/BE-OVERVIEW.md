# Tổng quan hệ thống — phần backend chưa có

Frontend màn `/tong-quan` (`src/pages/OverviewPage.tsx`) đã bỏ mock.

Đã nối API có sẵn:

| Việc trên UI | API |
|---|---|
| Tổng người dùng | `GET /api/v1/users?limit=1` → `meta.total` |
| Lời mời chờ duyệt | `GET /api/v1/users?status=invited&limit=1` → `meta.total` |
| Hồ sơ hoạt động | `GET /api/v1/dossiers?limit=1` → `meta.total` |
| Bảng thành viên | `GET /api/v1/users` (`q`, `role`, `limit`, `offset`) |

Contract user: [`BE-USER-ADMIN.md`](./BE-USER-ADMIN.md). Contract hồ sơ: mục 2 trong [`API-BE.md`](./API-BE.md).

Các phần dưới đây **chưa có endpoint**. UI không bịa số và không gọi path giả. Khi backend làm xong, frontend sẽ nối đúng contract này.

Prefix `/api/v1`. Envelope `{ data, meta }`. Header: `Authorization: Bearer`, `X-Tenant-Id`.

RBAC mọi endpoint dưới đây: **chỉ `ADMINISTRATOR`**. Role khác trả **403**.

---

## 1. Dung lượng lưu trữ

Card “Dung lượng” đang hiện “Chưa có số liệu”.

### `GET /api/v1/admin/storage`

`200`:

```ts
type StorageUsageDTO = {
  used_bytes: number
  quota_bytes: number | null
}
```

`quota_bytes` null khi tenant chưa đặt hạn mức. FE hiện thanh phần trăm chỉ khi có quota.

| HTTP | Khi nào |
|---|---|
| 401 | JWT không hợp lệ |
| 403 | Không phải `ADMINISTRATOR` |
| 404 | Route chưa mount. Detail `Not Found` thuần — FE hiểu là API chưa triển khai |

---

## 2. Nhật ký hoạt động toàn hệ thống

Cột “Hoạt động gần đây” đang trống. Không dùng `GET /review-items/{id}/revisions` vì đó là nhật ký một mục rà soát, không phải feed tenant.

### `GET /api/v1/admin/activity`

Query: `limit` 1..50 mặc định 8, `offset` ≥ 0.

`200` → `data: ActivityEventDTO[]`, `meta.total`.

```ts
type ActivityEventDTO = {
  id: string
  occurred_at: string
  actor_display_name: string | null
  title: string
  detail: string | null
}
```

Sự kiện tối thiểu cần ghi: mời / khóa user, tạo hồ sơ, chia sẻ hồ sơ, đăng nhập. Không trả payload nhạy cảm (mật khẩu, token, nội dung hợp đồng).

| HTTP | Khi nào |
|---|---|
| 401 | JWT không hợp lệ |
| 403 | Không phải `ADMINISTRATOR` |
| 404 | Route chưa mount |
| 422 | `limit` / `offset` sai |

---

## 3. Số hồ sơ được chia sẻ theo thành viên

Cột “Được chia sẻ” đã bỏ khỏi bảng tổng quan. `UserDTO` không có số hồ sơ user được chia sẻ, và chưa có API share grant.

Khi có chia sẻ, bổ sung trên `GET /api/v1/users` (không tạo path mới):

```ts
type UserDTO = {
  // các field hiện tại trong BE-USER-ADMIN.md
  shared_dossier_count: number
}
```

`0` khi user chưa được chia sẻ hồ sơ nào. Admin không thấy hồ sơ người khác trừ khi có grant.

---

## 4. Xuất báo cáo

Nút “Xuất báo cáo” đã bỏ. Không có file để tải.

### `GET /api/v1/admin/overview/export`

Query `format`: `csv` (bắt buộc ở bản đầu).

`200`: file `text/csv`, `Content-Disposition: attachment`. Không bọc envelope JSON.

Nội dung: cùng số liệu card tổng quan (số user, số lời mời, số hồ sơ, dung lượng nếu mục 1 đã có) cộng danh sách thành viên trang hiện không phân trang — toàn bộ tenant sau lọc không áp dụng; export là snapshot tenant.

| HTTP | Khi nào |
|---|---|
| 401 | JWT không hợp lệ |
| 403 | Không phải `ADMINISTRATOR` |
| 404 | Route chưa mount |
| 422 | `format` không hỗ trợ |

---

## 5. Biến động số người dùng

Badge “+3” trên card tổng người dùng là mock, đã bỏ. Không cần endpoint riêng: tổng hiện tại lấy từ `meta.total`. Biến động theo kỳ chỉ làm khi sản phẩm yêu cầu so sánh.
