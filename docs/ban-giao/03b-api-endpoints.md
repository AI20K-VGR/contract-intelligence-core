# Phụ lục 03b · Danh sách endpoint của backend

> **Tệp sinh tự động** bởi `backend/scripts/export_api_doc.py` từ chính ứng dụng FastAPI. Không sửa tay: sửa code rồi chạy lại script.

- Phiên bản backend: `2.0.0+sprint3-backend`
- Số endpoint: 108
- Cột **Quyền**: vai trò được gọi (Quản trị luôn được). "Quyền theo hồ sơ" nghĩa là cần đăng nhập, còn được làm gì do ACL của từng hồ sơ quyết định (chủ hồ sơ, người được chia sẻ, Quản trị).
- Mọi endpoint có token cần header `Authorization: Bearer <access_token>` và `X-Tenant-Id`.
- Request/response chi tiết: [03c-openapi-backend.json](03c-openapi-backend.json) (mở bằng Swagger Editor hoặc import vào Postman).


## `admin`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/admin/activity` | Vận hành, Thẩm định, Quản trị | Recent tenant activity | 200, 422 |
| `POST` | `/api/v1/admin/monitoring/session` | Quản trị | Open the monitoring dashboard (sets the /grafana cookie) | 200, 422 |
| `GET` | `/api/v1/admin/storage` | Vận hành, Thẩm định, Quản trị | Tenant storage usage | 200, 422 |

## `ai`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/ai/jobs/{job_id}` | Quản trị | Proxy tới AI service — polling trạng thái job nội bộ | 200, 422, 502 |
| `DELETE` | `/api/v1/ai/jobs/{job_id}` | Quản trị | Cancel AI service job — proxy sang DELETE /jobs/{id} | 200, 422 |

## `auth`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/auth/me` | Đã đăng nhập (quyền theo hồ sơ) | Get current user profile (từ Keycloak JWT claims) | 200, 401, 422 |
| `POST` | `/api/v1/auth/webhooks/keycloak` | Không cần token | Keycloak user event webhook — sync user vào local DB | 200, 400, 401, 422, 500 |

## `batches`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/batches` | Đã đăng nhập (quyền theo hồ sơ) | List batches | 200, 422 |
| `POST` | `/api/v1/batches` | Vận hành, Quản trị | Tạo batch từ ZIP + manifest.csv | 202, 400, 403, 422 |
| `GET` | `/api/v1/batches/{batch_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Batch | 200, 404, 422 |
| `POST` | `/api/v1/batches/{batch_id}/cancel` | Vận hành, Quản trị | Cancel Batch | 200, 403, 404, 409, 422 |
| `POST` | `/api/v1/batches/{batch_id}/resume` | Vận hành, Quản trị | Resume Batch | 200, 403, 404, 409, 422 |
| `GET` | `/api/v1/batches/{batch_id}/summary` | Đã đăng nhập (quyền theo hồ sơ) | Thống kê: succeeded, failed, pending_review, total_cost_usd | 200, 422 |

## `citations`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/citations/{citation_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Citation | 200, 404, 422 |

## `clause-nodes`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/clause-nodes/{node_id}/review` | Đã đăng nhập (quyền theo hồ sơ) | Thẩm định hiện hành của điều khoản + lịch sử ai sửa, lúc nào | 200, 404, 422 |
| `POST` | `/api/v1/clause-nodes/{node_id}/review` | Thẩm định, Quản trị | Lưu thẩm định trích dẫn (append-only, optimistic concurrency) | 200, 403, 404, 409, 422 |

## `documents`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/documents/{document_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Document | 200, 404, 422 |
| `GET` | `/api/v1/documents/{document_id}/clauses` | Đã đăng nhập (quyền theo hồ sơ) | Clause tree of document | 200, 422 |
| `GET` | `/api/v1/documents/{document_id}/content` | Đã đăng nhập (quyền theo hồ sơ) | Stream PDF binary từ MinIO/local storage | 200, 206, 304, 404, 416, 422 |
| `GET` | `/api/v1/documents/{document_id}/facts` | Đã đăng nhập (quyền theo hồ sơ) | List facts extracted from document | 200, 422 |
| `GET` | `/api/v1/documents/{document_id}/lines` | Đã đăng nhập (quyền theo hồ sơ) | OCR lines of every page of a document, in one response | 200, 422 |
| `GET` | `/api/v1/documents/{document_id}/pages` | Đã đăng nhập (quyền theo hồ sơ) | List pages of document | 200, 422 |
| `GET` | `/api/v1/documents/{document_id}/pages/{page_no}/image` | Đã đăng nhập (quyền theo hồ sơ) | Stream page image (PNG/WebP) from storage | 200, 404, 422 |
| `POST` | `/api/v1/documents/{document_id}/re-ocr` | Vận hành, Thẩm định, Quản trị | Tạo yêu cầu re-OCR | 202, 400, 403, 422, 503 |
| `GET` | `/api/v1/documents/{document_id}/re-ocr-requests` | Đã đăng nhập (quyền theo hồ sơ) | List re-OCR requests cho document | 200, 422 |
| `GET` | `/api/v1/documents/{document_id}/tables` | Đã đăng nhập (quyền theo hồ sơ) | Tables detected in document | 200, 422 |

## `dossiers`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/dossiers` | Đã đăng nhập (quyền theo hồ sơ) | List dossiers | 200, 422 |
| `POST` | `/api/v1/dossiers` | Vận hành, Quản trị | Tạo dossier + upload file hợp đồng/phụ lục | 202, 400, 403, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Dossier | 200, 404, 422 |
| `PATCH` | `/api/v1/dossiers/{dossier_id}` | Vận hành, Quản trị | Patch Dossier | 200, 403, 404, 422 |
| `DELETE` | `/api/v1/dossiers/{dossier_id}` | Vận hành, Quản trị | Xóa hồ sơ (tombstone + purge async) | 202, 403, 404, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/access` | Đã đăng nhập (quyền theo hồ sơ) | Get Dossier Access | 200, 404, 422 |
| `PUT` | `/api/v1/dossiers/{dossier_id}/access` | Vận hành, Quản trị | Update Dossier Access | 200, 404, 422, 503 |
| `PATCH` | `/api/v1/dossiers/{dossier_id}/ai2-content-sharing-consent` | Đã đăng nhập (quyền theo hồ sơ) | Update Ai2 Content Sharing Consent | 200, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/ai2/contract-graph/{graph_kind}` | Đã đăng nhập (quyền theo hồ sơ) | Get Dossier Ai2 Contract Graph | 200, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/ai2/contract-graph/{graph_kind}/evidence` | Đã đăng nhập (quyền theo hồ sơ) | Get Dossier Ai2 Contract Graph Evidence | 200, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/ai2/processing-trace` | Đã đăng nhập (quyền theo hồ sơ) | Get Dossier Ai2 Processing Trace | 200, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/ai2/reindex` | Vận hành, Quản trị | Gửi lại kết quả OCR đã có cho AI2 dựng lại dữ liệu hỏi đáp (không OCR lại) | 202, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/ai2/retry` | Vận hành, Quản trị | Chạy lại AI2 (trích xuất/so sánh) mà không OCR lại | 202, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/approve` | Quản trị | Ký duyệt chính thức — tạo snapshot checksum | 200, 403, 404, 409, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/conflicts` | Đã đăng nhập (quyền theo hồ sơ) | Findings needing reviewer (= v_conflict) | 200, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/documents` | Đã đăng nhập (quyền theo hồ sơ) | List Dossier Documents | 200, 404, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/external-approvals` | Vận hành, Thẩm định, Quản trị | List external approvals | 200, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/external-approvals` | Quản trị | Tạo external approval grant | 201, 403, 404, 409, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/facts` | Đã đăng nhập (quyền theo hồ sơ) | List facts + effective values (with current_version) | 200, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/findings` | Đã đăng nhập (quyền theo hồ sơ) | List findings trong dossier | 200, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/lock` | Thẩm định, Quản trị | Khóa dossier — không cho sửa đổi | 200, 403, 404, 409, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/manifest` | Vận hành, Quản trị | Get Dossier Manifest | 200, 403, 404, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/manifest/confirm` | Vận hành, Quản trị | Confirm Dossier Manifest | 200, 403, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/ocr` | Vận hành, Quản trị | Chạy lại OCR cho hồ sơ đã tải | 202, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/ocr/retry-failed` | Vận hành, Quản trị | Chạy lại OCR chỉ cho tài liệu lỗi; tài liệu đã xong được giữ | 202, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/reprocess` | Vận hành, Quản trị | Reprocess dossier (new immutable pipeline run) | 202, 403, 404, 409, 422 |
| `GET` | `/api/v1/dossiers/{dossier_id}/review-items` | Thẩm định, Quản trị | Queue review items ưu tiên | 200, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/runs` | Vận hành, Quản trị | Trigger pipeline run | 202, 403, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/search` | Đã đăng nhập (quyền theo hồ sơ) | Hỏi đáp trên hồ sơ (AI2) | 200, 404, 422 |
| `POST` | `/api/v1/dossiers/{dossier_id}/split` | Vận hành, Quản trị | Tách file trộn (hợp đồng + phụ lục) thành từng tài liệu rồi xử lý | 202, 404, 409, 422 |
| `POST` | `/api/v1/dossiers/{id}/ask` | Đã đăng nhập (quyền theo hồ sơ) | Ask a question about the dossier (same policy chain as /query) | 200, 400, 403, 404, 422, 429, 502 |
| `GET` | `/api/v1/dossiers/{id}/queries` | Đã đăng nhập (quyền theo hồ sơ) | Lịch sử hỏi đáp trên hồ sơ (mới nhất trước) | 200, 403, 404, 422 |
| `POST` | `/api/v1/dossiers/{id}/query` | Đã đăng nhập (quyền theo hồ sơ) | Query dossier via AI2 (ACL + quota + QueryTrace + ACL on citations) | 200, 400, 403, 404, 422, 429, 502 |
| `GET` | `/api/v1/dossiers/{id}/semantic-results` | Đã đăng nhập (quyền theo hồ sơ) | Semantic Results | 200, 422 |

## `external-approvals`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `POST` | `/api/v1/external-approvals/callback` | Quản trị | Webhook nhận response từ DocuSign/SAP/ERP | 200, 403, 404, 422 |

## `facts`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/facts/{fact_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Fact | 200, 404, 422 |

## `findings`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/findings/{finding_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Finding | 200, 404, 422 |
| `GET` | `/api/v1/findings/{finding_id}/review` | Đã đăng nhập (quyền theo hồ sơ) | Thẩm định hiện hành của xung đột + lịch sử ai sửa, lúc nào | 200, 404, 422 |
| `POST` | `/api/v1/findings/{finding_id}/review` | Thẩm định, Quản trị | Lưu thẩm định xung đột (append-only, optimistic concurrency) | 200, 403, 404, 409, 422 |

## `health`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/health` | Không cần token | Health | 200 |

## `healthz`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/healthz` | Không cần token | Liveness probe — kiểm tra backend process còn sống | 200 |

## `ops`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/ops/metrics` | Quản trị | Ops dashboard — server load, latency, cost theo ngày | 200, 403, 422 |
| `GET` | `/api/v1/ops/service-logs` | Quản trị | Read normalized Backend/AI2/Frontend logs | 200, 422 |
| `POST` | `/api/v1/ops/service-logs` | Quản trị | Ingest normalized service log receipts | 201, 422 |

## `optimization`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/optimization/campaigns` | Quản trị | List optimization campaigns | 200, 422 |
| `POST` | `/api/v1/optimization/campaigns` | Quản trị | Create Campaign | 201, 422 |
| `GET` | `/api/v1/optimization/campaigns/{campaign_id}` | Quản trị | Get Campaign | 200, 404, 422 |
| `GET` | `/api/v1/optimization/candidates` | Quản trị | List Candidates | 200, 422 |
| `POST` | `/api/v1/optimization/candidates` | Quản trị | Create Candidate | 201, 422 |
| `GET` | `/api/v1/optimization/candidates/{candidate_id}` | Quản trị | Get Candidate | 200, 404, 422 |
| `POST` | `/api/v1/optimization/candidates/{candidate_id}/promote` | Quản trị | Promote Candidate | 200, 409, 422 |
| `GET` | `/api/v1/optimization/experiments` | Quản trị | List Experiments | 200, 422 |
| `POST` | `/api/v1/optimization/experiments` | Quản trị | Create Experiment | 201, 422 |
| `GET` | `/api/v1/optimization/experiments/{experiment_id}/results` | Quản trị | Get Experiment Results | 200, 422 |
| `POST` | `/api/v1/optimization/experiments/{experiment_id}/run` | Quản trị | Run Experiment | 202, 409, 422 |

## `pages`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/pages/{page_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Page | 200, 404, 422 |

## `re-ocr-requests`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/re-ocr-requests/{request_id}` | Đã đăng nhập (quyền theo hồ sơ) | Chi tiết 1 re-OCR request — poll status | 200, 404, 422 |

## `readyz`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/readyz` | Không cần token | Readiness probe — kiểm tra DB + AI2 sẵn sàng | 200 |

## `review-items`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/review-items/{item_id}` | Thẩm định, Quản trị | Get Review Item | 200, 404, 422 |
| `POST` | `/api/v1/review-items/{item_id}/actions` | Thẩm định, Quản trị | Submit review action (optimistic concurrency via base_version) | 200, 403, 404, 409, 422 |
| `GET` | `/api/v1/review-items/{item_id}/revisions` | Thẩm định, Quản trị | Append-only review revisions trail | 200, 404, 422 |

## `review-queue`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/review-queue` | Thẩm định, Quản trị | Hồ sơ đang chờ tôi thẩm định | 200, 422 |

## `runs`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/runs` | Đã đăng nhập (quyền theo hồ sơ) | List pipeline runs | 200, 422 |
| `GET` | `/api/v1/runs/{run_id}` | Đã đăng nhập (quyền theo hồ sơ) | Get Run | 200, 404, 422 |
| `POST` | `/api/v1/runs/{run_id}/cancel` | Vận hành, Quản trị | Cancel running pipeline run | 200, 403, 404, 409, 422 |
| `GET` | `/api/v1/runs/{run_id}/events` | Đã đăng nhập (quyền theo hồ sơ) | Server-Sent Events stream — real-time pipeline run updates | 200, 403, 404, 422 |
| `GET` | `/api/v1/runs/{run_id}/steps` | Đã đăng nhập (quyền theo hồ sơ) | 11 steps S0..S10 status | 200, 422 |

## `tenants`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/tenants/{tenant_id}/lexicon` | Đã đăng nhập (quyền theo hồ sơ) | Read Lexicon | 200, 422 |
| `POST` | `/api/v1/tenants/{tenant_id}/lexicon/commands` | Đã đăng nhập (quyền theo hồ sơ) | Mutate Lexicon | 200, 422 |

## `uploads`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `POST` | `/api/v1/uploads` | Vận hành, Quản trị | Mở phiên tải hồ sơ theo khúc | 201, 413, 422, 429 |
| `GET` | `/api/v1/uploads/{upload_id}` | Vận hành, Quản trị | Trạng thái phiên tải lên: các khúc đã nhận | 200, 404, 410, 422 |
| `DELETE` | `/api/v1/uploads/{upload_id}` | Vận hành, Quản trị | Huỷ phiên tải lên và xoá các khúc đã gửi | 204, 404, 409, 422 |
| `POST` | `/api/v1/uploads/{upload_id}/complete` | Vận hành, Quản trị | Ghép các khúc và tạo hồ sơ (như POST /dossiers) | 202, 404, 409, 410, 413, 422 |
| `PUT` | `/api/v1/uploads/{upload_id}/files/{file_index}/chunks/{chunk_no}` | Vận hành, Quản trị | Gửi một khúc của một tệp (byte thô) | 204, 404, 409, 410, 422 |

## `users`

| Method | Đường dẫn | Quyền | Mô tả | Mã trả về |
|---|---|---|---|---|
| `GET` | `/api/v1/users` | Quản trị | List / search users | 200, 422 |
| `POST` | `/api/v1/users` | Quản trị | Create user and send password-set invite | 201, 422 |
| `GET` | `/api/v1/users/directory` | Vận hành, Quản trị | Tenant members a dossier can be shared with | 200, 422 |
| `GET` | `/api/v1/users/lookup` | Vận hành, Quản trị | Find the one tenant member with this exact email (for sharing) | 200, 404, 422 |
| `PATCH` | `/api/v1/users/{id}` | Quản trị | Update user role | 200, 422 |
| `POST` | `/api/v1/users/{id}/disable` | Quản trị | Disable user in Keycloak | 200, 422 |
| `POST` | `/api/v1/users/{id}/enable` | Quản trị | Enable user in Keycloak | 200, 422 |
| `POST` | `/api/v1/users/{id}/invite` | Quản trị | Resend UPDATE_PASSWORD invite email | 200, 422 |
