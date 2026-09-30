# DEC-BE-AI2-01: Các điểm chốt của contract Backend ↔ AI2

**Trạng thái:** `accepted-backend`. Backend (Chương) chốt D1–D12. Lead (Trang) đã duyệt D8, D11 (phương án A) và D12 ngày 30/09; **D6 chưa duyệt** (chưa có provider và trần chi tiêu). Chờ Văn Dũng (AI2) duyệt lại đúng commit này.
**Ngày:** 2026-09-29
**Người soạn:** Chương (Backend)
**Người duyệt:** Chương (Backend), Văn Dũng (AI2), Trang (Lead) cho D6, D8, D11 và D12. Trang đã duyệt D8, D11 (phương án A) và D12 ngày 30/09; D6 chưa duyệt.
**Bổ sung cho:** [BE-AI2-PROCESSING-CONTRACT.vi.md](BE-AI2-PROCESSING-CONTRACT.vi.md), [AI2-SERVICE-ENVELOPE-v1.vi.md](AI2-SERVICE-ENVELOPE-v1.vi.md)
**Căn cứ:**
- Code của nhánh `feature/sprint3-backend` (`d667bd9`).
- Kế hoạch tuần 3 của AI2: `plans/reports/ke-hoach-ai2-tuan3-260928-261004.md`, commit `63a07c1`.

---

## Cách dùng tài liệu này

Mỗi mục D1–D12 gồm bốn phần: **hiện trạng** (dẫn tới code), **đề xuất**, **việc của từng bên** và **ô duyệt**. Người duyệt đánh dấu `[x]` và ghi chú nếu không đồng ý.

Khi cả hai bên duyệt xong:
1. Đổi trạng thái sang `accepted`.
2. Chép các quy tắc đã chốt vào `BE-AI2-PROCESSING-CONTRACT.vi.md`.
3. Nếu mục nào đổi schema, cập nhật file `*.schema.json` tương ứng.

**Hạn:** D1, D2, D4, D10 cần chốt **trước T4 30/09**, vì bốn mục này chặn việc của AI2 trong tuần. D6 và D8 chốt cùng Lead **trước T5 01/10**. D11: AI2 lên Postgres (schema `ai2`) trước lần deploy online đầu tiên, chậm nhất 03/10 (việc A7).

## Tóm tắt

| # | Chủ đề | Đề xuất ngắn | Hạn |
|---|---|---|---|
| D1 | Kênh gọi | Tới hết Sprint 2 (04/10, gồm buổi demo): chỉ HTTP `/jobs/idp` + poll, **không làm Kafka trước demo**. Hướng Sprint 3: Kafka theo DOC-05e khi DOC-05e §12 đạt, HTTP làm fallback | 30/09 |
| D2 | Xác thực HMAC | Giữ tham số hiện tại; lệch đồng hồ 30 giây, TTL tối đa 3600 giây; một secret mới dùng chung cho 3 service; `/query` bắt buộc có chữ ký (`AI2_QUERY_REQUIRE_SIGNATURE=true`) | 30/09 |
| D3 | Mạng | Không publish 8002; healthcheck gọi `/healthz` | 01/10 |
| D4 | Snapshot và digest | Chỉ `ai1.snapshot.v1`; `source_digest` là 64 hex chữ thường, không có tiền tố | 30/09 |
| D5 | Hồ sơ nhiều file | Gửi đủ snapshot, **tối đa 6 file**; role theo `doc_type`; quan hệ `ANNEX_OF` do Backend quyết định | 01/10 |
| D6 | `policy_flags` | Egress theo env từng luồng, mặc định `false`; xử lý hồ sơ `use_vector=false`. **Chưa bật egress và vector trên bản online** cho tới khi Lead ghi provider và trần chi tiêu | 01/10 (Lead, chưa duyệt) |
| D7 | Idempotency và retry | Key `<run_id>:ai2`, cố định trong một run; `attempt` tăng khi retry; payload tất định; chỉ retry khi `FAILED` và có lỗi `retryable=true` | 01/10 |
| D8 | Ánh xạ trạng thái | Tách "AI2 xong" khỏi "chờ review" | 01/10 (Lead) |
| D9 | Xử lý kết quả | Lưu ở dạng đề xuất, publish sau khi reviewer duyệt | 01/10 |
| D10 | Contract hỏi đáp | AI2 trả `query_snapshot_digest` trong result; Backend lưu nguyên giá trị, không tự tính; `state` có 4 giá trị, thêm `BLOCKED` | 30/09 |
| D12 | Hồ sơ nhiều hợp đồng (Sprint 3) | Cho phép nhiều `body`; AI2 so từng cặp hợp đồng; AI2 nhận `max_body_members` trước, Backend nới `/split` và manifest sau | Trước khi làm DOC-11 §4.2 mục 12 |
| D11 | Nơi lưu dữ liệu AI2 | **Phương án A (Lead duyệt 30/09):** nghiệp vụ ở Postgres của Backend; trạng thái riêng của AI2 ở schema `ai2` trong cùng Postgres, AI2 tự quản migration | Trước lần deploy online đầu tiên |

---

## D1. Kênh gọi AI2

**Hiện trạng:**
- Compose gọi AI2 qua HTTP (`AI_SERVICE_MODE: http`, `AI2_BASE_URL: http://ai2-service:8002`).
- Worker gọi `submit_ai2_processing` rồi `poll_ai2_processing` (`backend/.../worker.py:1079`).
- Phía AI2, `app/transport/kafka_idp_worker.py` lại tự ghi mình là "runtime path", còn `/jobs/idp` là "demo-only". Hai phía đang mô tả ngược nhau.

**Đề xuất:**
- **Tới hết Sprint 2 (04/10, gồm buổi demo):** kênh chính thức là HTTP: `POST /jobs/idp` trả `202` kèm `job_id`, sau đó Backend poll `GET /jobs/{job_id}`. Không làm Kafka trước demo. (DOC-12 dự kiến demo ngày 02/10; lịch chính thức do Lead hỏi mentor.)
- **Hướng Sprint 3:** processing chuyển sang Kafka theo [DOC-05e](../DOC-05e-kafka-ai2-idp-contract.md): gửi cả hồ sơ, payload lớn qua MinIO, sự kiện `started`, dedupe theo `(idempotency_key, attempt)`, watchdog ở Backend. Kafka chỉ thành đường chạy thật khi DOC-05e §12 bước 3 đạt; tới lúc đó HTTP vẫn là runtime, sau đó là fallback qua `AI2_TRANSPORT=http`. Hướng này cần AI2 duyệt ở DOC-05e §13.
- `/query` giữ HTTP đồng bộ ở cả hai sprint.
- Backend gộp hai bộ hàm trùng nhau trong `infrastructure/ai_adapters.py`: giữ `submit_ai2_processing`/`poll_ai2_processing`, bỏ `submit_idp_job`/`get_idp_job`/`poll_idp_job` và `build_idp_request` (bản chỉ gửi một snapshot, có `max_llm_calls=0`).

**Việc cần làm:**
- AI2: sửa docstring của `kafka_idp_worker.py` (dòng 7) và `/jobs/idp` cho đúng: HTTP là đường chạy tới khi DOC-05e §12 đạt, Kafka là đích Sprint 3. Ghi đúng kênh vào phần AI2 của Architecture doc. Duyệt checklist DOC-05e §13.
- Backend: xoá bộ hàm trùng; làm phần Kafka theo `plans/260930-be-ai2-kafka/plan.md` sau khi AI2 duyệt DOC-05e §13. Trạng thái DOC-05e (hướng đã chốt, runtime vẫn là HTTP) nằm ở PR #36; DEC này không sửa DOC-05e.

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D2. Xác thực bằng service envelope (HMAC)

**Hiện trạng:** tham số lấy từ `backend/.../config/settings.py:192-198` và `ai_adapters.py:124-169`.

| Tham số | Giá trị |
|---|---|
| `schema_version` | `ai2.service-envelope.v1` |
| `issuer` / `audience` / `key_id` | `backend-service` / `vsf-ai2` / `default` |
| Thời hạn | `expires_at = issued_at + 300` |
| Scope | `ai2.jobs.submit` cho submit và poll; `ai2.query` cho hỏi đáp |
| Payload đem đi hash | JSON của payload **đã bỏ** `service_envelope`, `sort_keys=True`, `separators=(",", ":")`, `ensure_ascii=False`, mã hoá UTF-8 |
| Chữ ký | HMAC-SHA256 trên envelope **đã bỏ** `signature`, chuẩn hoá JSON theo cùng cách |
| Poll | Header `X-AI2-Service-Envelope`, ký payload `{"operation":"get_job","job_id":…,"dossier_id":…}` |

**Đề xuất:**
- Giữ nguyên các tham số trên và coi đây là giá trị chính thức.
- Mỗi môi trường (local, online) dùng **một** secret riêng. Secret này đặt giống nhau cho `backend`, `backend-worker` và `ai2-service`, và không dùng lại secret dev.
- Thiếu secret thì cả hai phía đều từ chối (fail-closed), như code hiện tại.
- Chênh lệch đồng hồ cho phép: **30 giây** (`AI2_SERVICE_CLOCK_SKEW_SECONDS`, giá trị `service_envelope.py` đang dùng). Khoảng `expires_at - issued_at` tối đa **3600 giây** (`AI2_SERVICE_MAX_TTL_SECONDS`); Backend dùng 300 giây.
- **`/query` bắt buộc có chữ ký.** Env `AI2_QUERY_REQUIRE_SIGNATURE`, mặc định `true`: request không có envelope bị trả `401 SERVICE_ENVELOPE_MISSING`. Chỉ compose local hoặc test cần nhánh cũ mới đặt `false`. Lý do: khi LLM và vector bật, người gọi không chữ ký đọc được hồ sơ và làm phát sinh chi phí.

**Việc cần làm:**
- AI2: xác nhận `service_envelope.py` chuẩn hoá JSON giống bảng trên, kể cả `ensure_ascii=False`. Chỉ cần lệch một chi tiết là mọi request bị 401.
- AI2: cung cấp một vector ký mẫu (secret, payload, envelope, chữ ký) để Backend đưa vào CI; thêm `AI2_QUERY_REQUIRE_SIGNATURE` (mặc định `true`).
- Backend: thêm vào CI một test ký thử bằng secret cố định và so với vector mẫu do AI2 cung cấp. Compose online không đặt `AI2_QUERY_REQUIRE_SIGNATURE` (giữ mặc định `true`).

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D3. Mạng và healthcheck

**Hiện trạng:**
- `docker-compose.yml:461` publish `8002:8002` ra máy host. AI2 có các endpoint `/api/workspace/*` không cần xác thực.
- Healthcheck ở `docker-compose.yml:474` gọi `/health`. Theo kế hoạch của AI2 (O2), `/health` gọi LLM thật mỗi 15 giây.

**Đề xuất:**
- Bản online không publish cổng 8002; chỉ Backend gọi AI2 qua mạng Docker.
- Bản local vẫn được publish 8002 để debug, qua biến `AI2_HOST_PORT`.
- Healthcheck của container chuyển sang `/healthz`, endpoint không gọi LLM. `/health` chỉ dùng khi kiểm tra thủ công.

**Việc cần làm:**
- AI2: đổi healthcheck.
- Backend: tách override compose cho bản online, không có `ports` cho `ai2-service`.

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D4. Phiên bản snapshot và định dạng digest

**Hiện trạng:**
- Backend chỉ gửi `ai1.snapshot.v1`.
- Backend cắt tiền tố `sha256:` và đưa về chữ thường trước khi gửi (`canonical_processing.py:27`, `_wire_source_digest`).
- Bản sửa `32106c7` phía AI2 chấp nhận dạng `sha256:<hex>` của snapshot OCR-lab.
- Tài liệu vẫn nhắc cả v1 lẫn v3.

**Đề xuất:**
- Trên dây giữa Backend và AI2 chỉ có `ai1.snapshot.v1`. `ai1.snapshot.v3` chỉ tồn tại bên trong adapter persistence của Backend.
- `source_digest` và `snapshot_digest` trên dây là **64 ký tự hex chữ thường, không có tiền tố**.
- AI2 vẫn được nhận dạng `sha256:<hex>` để tương thích, nhưng phải chuẩn hoá về dạng trên trước khi so sánh hay lưu.
- `snapshot_digest` trong `snapshot_identities[]` là SHA-256 của snapshot đã chuẩn hoá JSON theo quy tắc ở D2.

**Liên quan DOC-04:** ADR-05 đang ghi `ai1.snapshot.v3` là bản chuyển giao chuẩn. Code và `BE-AI2-PROCESSING-CONTRACT.vi.md` §5.1 đã dùng v1 trên dây và chỉ giữ v3 trong adapter của Backend. PR này sửa câu chữ của ADR-05 cho khớp: v1 trên dây Backend → AI2, v3 chỉ ở phía Backend. Phiên bản AI1 xuất ra do AI1 chốt (DOC-11 §4.3 #7).

**Việc cần làm:**
- AI2: chuẩn hoá digest ngay khi nhận request.
- AI1 (Đức Dũng): chốt một phiên bản snapshot (xem kế hoạch AI2 §5).

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D5. Hồ sơ nhiều file: member và quan hệ

**Hiện trạng** (`canonical_processing.py:234-365`):
- Backend gửi mọi snapshot đã chọn của hồ sơ.
- `role` bằng `body` khi `doc_type == "contract"`; mọi trường hợp khác là `annex`.
- `role_relation_map[]` chỉ chứa quan hệ `annex_of` mà Backend đã lưu. Hồ sơ chỉ có thân HĐ thì không có quan hệ nào.
- Upload file trộn giờ được tách thành nhiều tài liệu trước khi OCR (`d667bd9`).

**Đề xuất:**
- **Sprint 2:** mỗi request có **đúng một** member `body`, vì schema và adapter hiện tại đòi như vậy. Nếu hồ sơ không có hoặc có nhiều hơn một tài liệu `contract`, Backend không gửi sang AI2 mà báo lỗi cấu hình hồ sơ. AI2 không tự chọn.
- **Sprint 3:** luật "đúng một body" được nới theo D12, để so được hợp đồng với hợp đồng (DOC-11 mục 1 số 7, DOC-11 §4.2 mục 12).
- Phụ lục không có quan hệ `ANNEX_OF` vẫn được gửi với `role=annex`. AI2 được so sánh nó với thân HĐ, nhưng mọi finding ghi rõ là "quan hệ chưa xác nhận" (khớp với DEC-1 của AI2).
- Tài liệu tách ra từ file trộn mang `doc_type` từ bước phân loại. Người dùng sửa được role trước khi chạy AI2.
- AI2 không suy luận, không sửa role hay quan hệ.
- **Tối đa 6 file một hồ sơ.** Request của AI2 nhận `snapshots` từ 1 đến 6 phần tử (`be.ai2.processing.request.v1.schema.json`, `maxItems: 6`; `wire.py`). Backend chặn hồ sơ có hơn 6 tài liệu trước khi gửi: mã lỗi `DOSSIER_TOO_MANY_DOCUMENTS`, HTTP `422`, câu trên UI "Hồ sơ tối đa 6 tài liệu". `API-BE.md` và DOC-05b cập nhật cùng việc B4, không nằm trong PR này.

**Việc cần làm:**
- Backend: chặn trường hợp có 0 hoặc nhiều hơn 1 body, và hồ sơ hơn 6 tài liệu, trước khi submit, kèm mã lỗi.
- AI2: finding liên tài liệu khi thiếu `ANNEX_OF` phải gắn nhãn "chưa xác nhận".

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D6. `policy_flags`: egress, vector và ngân sách (cần Lead)

**Hiện trạng:**

| Luồng | Nơi đặt | `egress_allowed` | `use_vector` | Ngân sách |
|---|---|---|---|---|
| Xử lý hồ sơ | `canonical_processing.py:354-363` (hard-code) | `false` | `true` | `300s + 2s × số trang`, `max_llm_calls=20`, `max_embedding_tokens=50000` |
| Hỏi đáp | `settings.py:229-247` (qua env) | `false` | `false` | timeout 20 giây |

Kế hoạch AI2 (O6) ghi compose của nhánh AI2 để egress mặc định `true`. Hai nhánh đang lệch nhau.

**Đề xuất:**
- Egress của luồng xử lý hồ sơ đọc từ biến env `AI2_PROCESSING_EGRESS_ALLOWED`, không hard-code nữa. Egress của hỏi đáp giữ `AI2_QUERY_EGRESS_ALLOWED`. Cả hai mặc định `false`.
- **Vector (cập nhật 30/09):**
  - **Bản online chưa bật egress và vector** (Lead, 30/09): chưa có tên provider và trần chi tiêu. `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_VECTOR` và `AI2_VECTOR_RECALL_ENABLED` giữ `false`. Chỉ bật sau khi Lead ghi provider và trần chi tiêu vào DEC này.
  - Công tắc thật của vector là env `AI2_VECTOR_RECALL_ENABLED` phía AI2; `use_vector` trong request chỉ cho phép hoặc cấm theo từng lời gọi.
  - Khi bật: vector trên `/query` dựa vào **egress của chính request `/query`**, không dựa vào egress lúc xử lý hồ sơ (giá trị đó luôn `false`).
  - `/query` có trần embedding. **AI2 đọc trần này từ env của mình**, Backend không gửi trong request. Lần hỏi đầu tiên embed cả hồ sơ, nên không được để chi phí không giới hạn.
  - Luồng xử lý hồ sơ đặt `use_vector=false`: hiện là `true` (`canonical_processing.py:357`) nhưng không có tác dụng.
- Bật egress thì phải ghi tên provider LLM và dữ liệu nào được gửi ra ngoài vào Architecture doc (O6).
- Giữ các giới hạn ngân sách hiện tại. AI2 phải tuân thủ: vượt `max_llm_calls` thì trả `review_state=INSUFFICIENT_EVIDENCE` kèm lý do, không dừng job với `FAILED`.
- Khi `egress_allowed=false`, AI2 không được gọi LLM bên ngoài. Kết quả vẫn phải `SUCCEEDED`, chỉ với phần xử lý bằng luật cố định, **không** được trả `LLM_UNAVAILABLE`.

**Lead cần chốt:** bản demo online có bật egress hay không, dùng provider nào, và giới hạn chi tiêu bao nhiêu (kế hoạch AI2 §7 mục 1).

**Việc cần làm:**
- Backend: đọc egress của luồng xử lý từ env; `use_vector=false` cho luồng xử lý. Chỉ bật `AI2_QUERY_USE_VECTOR` và `AI2_QUERY_EGRESS_ALLOWED` khi Lead đã duyệt D6 **và** A3 đã deploy.
- AI2: vector trên `/query` dựa vào egress của `/query`; trần embedding cho `/query` đọc từ env của AI2; viết test cho hai cam kết của mục này: egress tắt thì vẫn `SUCCEEDED`, vượt `max_llm_calls` thì trả `INSUFFICIENT_EVIDENCE`.

- [x] Chương duyệt  - [ ] Dũng duyệt  - [ ] Trang duyệt  Ghi chú: bật sau khi Lead ghi provider và trần chi tiêu vào DEC.

## D7. Idempotency, attempt và retry

**Hiện trạng:**
- `request_id` và `idempotency_key` đều bằng `f"{run_id}:ai2"` (`canonical_processing.py:344-347`).
- Mỗi lần gửi lại, Backend tạo envelope mới (nonce mới); AI2 gộp trùng theo cặp `(idempotency_key, attempt)`.
- Backend bỏ qua tối đa 5 lỗi tạm thời liên tiếp (timeout, 429, 5xx), giãn cách kiểu backoff, tối đa 30 giây (`ai_adapters.py:201-217`).

**Đề xuất:**

| Tình huống | `idempotency_key` | `attempt` |
|---|---|---|
| Gửi lại vì mất phản hồi mạng | giữ nguyên | giữ nguyên, nên nhận lại cùng `job_id` |
| Retry sau `FAILED` có `retryable=true` | giữ nguyên | +1 |
| OCR lại một phần (`709e70d`) hoặc bộ snapshot thay đổi | run mới, nên key mới | 1 |
| `FAILED` với `retryable=false` | không retry; báo lỗi lên UI | — |

- Nếu cùng `(idempotency_key, attempt)` mà payload khác, AI2 trả `409` (`IDEMPOTENCY_PAYLOAD_CONFLICT`). Backend coi đây là lỗi lập trình và không retry.
- **Payload tất định.** Cùng `(idempotency_key, attempt)` thì payload (bỏ `service_envelope`) phải giống hệt từng byte, kể cả khi dựng lại sau khi worker crash hoặc message được giao lại. Hiện Backend ghi `created_at = datetime.now()` mỗi lần dựng snapshot (`canonical_processing.py:211`), nên dựng lại là nhận `409` và run fail. Sửa: `created_at` lấy từ thời điểm lưu snapshot, không lấy giờ hiện tại.
- **Định nghĩa "job được retry":** `status=FAILED` **và** có ít nhất một phần tử trong `errors[]` mang `retryable=true`. `retryable` gắn với **mã lỗi** (lỗi tạm như 429/529, timeout provider: `true`; lỗi contract, dữ liệu sai: `false`), không suy ra từ `review_state`. Với `FAILED`, `review_state` không có nghĩa (sai contract hoặc worker lỗi thì AI2 trả `BLOCKED`, hết thời gian thì `NEEDS_REVIEW`), nên Backend bỏ qua `review_state` khi quyết định retry. Hồ sơ `SUCCEEDED` + `BLOCKED` thì không retry (D8).
- Backend retry tối đa 3 attempt cho một run.

**Việc cần làm:**
- AI2: đã có `409` và trả lại cùng `job_id` (xác nhận trong review 30/09). Sửa cờ `retryable`: hiện mọi lỗi có `review_state=BLOCKED` được đánh `retryable=true` (`wire.py`). Đổi thành: `retryable` theo mã lỗi, không theo `review_state`.
- Backend: payload tất định (`created_at` từ lúc lưu snapshot); thêm giới hạn attempt và nhánh xử lý `retryable=false`; retry theo đúng định nghĩa ở trên.

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D8. Ánh xạ trạng thái AI2 sang trạng thái hồ sơ (cần Lead)

**Hiện trạng:**
- `persistence.py:155-168` coi mọi `review_state != PASS` là `NEEDS_REVIEW` và đặt `evidence_ready=false`.
- Hồ sơ dừng ở trạng thái `extracted`. UI không phân biệt được "AI2 đã xong, đang chờ reviewer" với "AI2 chưa xong".

**Đề xuất:**

| AI2 `status` + `review_state` | Trạng thái hồ sơ | UI hiển thị |
|---|---|---|
| `SUCCEEDED` + `PASS` | `pending_review` | "Chờ rà soát": reviewer vẫn rà soát, vì kết quả chỉ là đề xuất (D9) |
| `SUCCEEDED` + `NEEDS_REVIEW` | `pending_review` | "Chờ rà soát", kèm số mục cần xem |
| `SUCCEEDED` + `INSUFFICIENT_EVIDENCE` | `pending_review` | "Chờ rà soát, thiếu bằng chứng" |
| `SUCCEEDED` + `BLOCKED` | `failed` | Lỗi, kèm mã từ `errors[]` hoặc lý do chặn |
| `FAILED` | retry theo D7; hết lượt thì `failed` | Lỗi, kèm `code` |

- `evidence_ready` chỉ cho biết đủ bằng chứng để publish. Nó **không** quyết định hồ sơ có vào hàng chờ review hay không.
- **Khi `status` khác `SUCCEEDED` thì Backend bỏ qua `review_state`** và chỉ dựa vào `status` và `errors[]` (D7). Lý do: `review_state` không có nghĩa khi job không `SUCCEEDED`. Ví dụ ở AI2: sai contract hoặc worker lỗi trả `BLOCKED` (`main.py:259`), hết thời gian trả `NEEDS_REVIEW` (`idp.py:442`).

**Lead đã chốt (30/09):** trạng thái hồ sơ là `pending_review`. Nhãn UI là **"Chờ rà soát"**, như màn danh sách đang có. Không dùng chữ "Chờ duyệt".

**Việc cần làm:**
- Backend: sửa bước chuyển trạng thái trong worker theo bảng trên (worker đã chuyển sang `pending_review` khi `SUCCEEDED`; còn thiếu `SUCCEEDED` + `BLOCKED` → `failed`, và bỏ qua `review_state` khi `status` khác `SUCCEEDED`).
- AI2: không phải làm gì.

- [x] Chương duyệt  - [ ] Dũng duyệt  - [x] Trang duyệt: `pending_review`, nhãn "Chờ rà soát" (review PR #37, 30/09)  Ghi chú:

## D9. Backend lưu và kiểm tra gì trong kết quả

**Đề xuất:**

1. **Kiểm tra trước khi lưu.** Nếu một trong các điều sau sai, Backend coi cả result là không hợp lệ và không lưu phần nào:
   - `input_snapshots[]` khớp các `snapshot_identities` đã gửi;
   - mọi `citation_id` trong fact, finding và evidence issue đều có trong `result.citations[]`.
2. **Lưu ở dạng đề xuất.** `index_contribution.state` luôn là `propose`. Chỉ khi reviewer xác nhận hoặc sửa thì fact và finding mới được publish; job `SUCCEEDED` không đủ để publish.
3. **Bbox.** AI2 chỉ chuyển tiếp geometry sẵn có trong snapshot. Backend từ chối citation có bbox không khớp với dòng hoặc span của snapshot.
4. **Citation `UNVERIFIED`**, ví dụ ô bảng phụ lục chưa có offset: vẫn được lưu nhưng gắn cờ, UI hiện cảnh báo, và chúng không được tính vào điều kiện `evidence_ready`.
5. **`table_id` và `cell_id`:** Backend lưu nếu có (trường tuỳ chọn, bổ sung thêm), để UI làm sáng đúng ô bảng.
6. **Finding liên tài liệu** phải có citation ở cả hai phía. Nếu thiếu một phía, finding bị hạ xuống `NEEDS_REVIEW`.

**Việc cần làm:**
- Backend: bước kiểm tra ở mục 1 và mục 3.
- AI2: bảo đảm mục 1, mục 3 và mục 6 ngay ở đầu ra (đã có `validate_processing_result`, xác nhận trong review 30/09). Sửa comment lỗi thời ở `wire.py`: comment nói `table_id`/`cell_id` không đi trên dây, thực tế có.

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D10. Contract hỏi đáp `ai2.query.v1`

**Hiện trạng: đây là điểm dễ vỡ nhất.**
- Với `query_contract_version="ai2.query.v1"`, AI2 bắt buộc `snapshot_digest` phải khớp `record.pins.source_snapshot_digest`; sai thì trả `INSUFFICIENT_EVIDENCE` (`ai-service/app/api/main.py:775-800`).
- Mỗi hồ sơ nhiều file chỉ có **một** giá trị digest như vậy.
- Backend **tự tính lại** digest bằng cách mô phỏng thuật toán nội bộ của AI2 (`worker.py:140-172`, `_ai2_query_snapshot_digest`): dựng một payload `ai2.idp.request.v1` giả, gồm manifest, `task_id` và `attempt_id`, rồi hash. Sau đó lưu vào `dossier.metadata["ai2_snapshot_digest"]` (`worker.py:810`).
- Nếu chưa có giá trị này, API hỏi đáp dùng `dossier.checksum` thay thế (`api/v1/dossiers.py:113`, `contract_router.py:1167`). Giá trị đó chắc chắn không khớp.
- Hệ quả: chỉ cần AI2 đổi cách dựng hoặc hash payload nội bộ là mọi câu hỏi trả `INSUFFICIENT_EVIDENCE`, mà không có test nào báo lỗi.

**Đề xuất:**
- AI2 thêm trường `query_snapshot_digest` (64 hex) vào `ai2.be.processing.result.v1`. Đây là giá trị AI2 sẽ đòi khi nhận `/query`.
- Backend lưu **nguyên** giá trị đó vào `dossier.metadata["ai2_snapshot_digest"]`, bỏ hàm `_ai2_query_snapshot_digest`, và bỏ phương án dùng `dossier.checksum`. Chưa có digest thì API trả "hồ sơ chưa xử lý xong", không gọi AI2.
- **Chuyển tiếp:** result có `query_snapshot_digest` thì Backend dùng giá trị đó; chưa có thì tạm tính như cũ. Xoá hẳn phần tự tính sau khi bản AI2 có trường này đã deploy.
- Trường này nằm trong payload `ai2.be.processing.result.v1`, nên dùng chung cho HTTP và Kafka. Trường `query_binding` ở envelope Kafka mà DOC-05e v2 §5.2 đề xuất được bỏ, để chỉ có một cách.
- **Request `/query`:** `query`, `dossier_id`, `tenant_id`, `actor_id`, `snapshot_version`, `snapshot_digest`, `query_contract_version="ai2.query.v1"`, `acl_context`, `policy_flags`, cùng envelope scope `ai2.query`.
  - `acl_context` là `user_id` của người hỏi. AI2 chỉ dùng để ghi log và audit, không dùng để phân quyền; Backend đã kiểm tra quyền trước khi gọi.
- **Response:** `state`, `answer`, `citations[]`, `used_llm`, `reasoning_trace`, `retrieval_layer`.
  - `state` nhận **bốn** giá trị: `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`. Chốt 30/09 theo đề xuất của AI2: `/query` hiện đã trả `BLOCKED`, và "hồ sơ bị khoá hoặc bị chính sách chặn" có nghĩa riêng, không gộp vào thiếu bằng chứng. Backend hiển thị `BLOCKED` là "không trả lời được do bị chặn", không coi là lỗi hệ thống.
  - UI hiện `used_llm` dưới dạng một nhãn nhỏ.
- **Timeout:** giữ 20 giây. Đo lại trên máy chủ ngày 02/10 (O7).

**Việc cần làm:**
- AI2 (**việc gấp nhất**): thêm `query_snapshot_digest` (64 hex, lấy từ `record.pins.source_snapshot_digest`) vào `ai2.be.processing.result.v1` và cập nhật file schema. Backend chờ việc này mới bỏ được code tự tính digest.
- Backend: lưu digest theo AI2 trả về, xoá code tự tính, xoá phương án thay thế.

- [x] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D11. AI2 lưu dữ liệu bền ở đâu

**Hiện trạng:**
- Kết quả nghiệp vụ AI2 **đã nằm trong Postgres của Backend**, và Backend là bên ghi: `pipeline_run.ai2_result_json`, `ai2_result_digest` (migration `v10`), cùng các bảng fact, finding, citation và review.
- Trạng thái riêng của AI2 vẫn nằm trong SQLite hoặc RAM:

  | Kho | Code | Chứa gì |
  |---|---|---|
  | Job store | `app/tools/jobs.py` (`AI2_JOB_DB`) | Toàn bộ request Backend gửi, kể cả snapshot, và kết quả job |
  | Snapshot store | `app/api/main.py:70` (`InMemorySnapshotStore`) | Hồ sơ đã nhận, để trả lời `/query`. Nằm trong RAM; khởi động lại thì dựng lại từ job store (`main.py:82`) |
  | Durable run store | `app/tools/durable.py` | Run, checkpoint, event, audit, outbox |
  | Vector | `app/reasoning/vector_recall.py` (`AI2_VECTOR_DB`) | Embedding cho vector recall |
  | Workspace demo | `app/tools/persist.py` | Session của các trang demo `/api/workspace/*` |

- `ai-service` chưa có driver Postgres.
- **Rủi ro:** container AI2 bị tạo lại mà không có volume thì job store mất. Khi đó `/query` trả `INSUFFICIENT_EVIDENCE` cho mọi hồ sơ cũ, và poll job cũ nhận `404`.
- DOC-11 §3 (Lead) đã định hướng: *"bản online của AI2 ghi dữ liệu bền vào PostgreSQL. SQLite chỉ còn trong test."*

**Đề xuất:**
1. **Nguồn sự thật của dữ liệu nghiệp vụ** là Postgres của Backend, và chỉ Backend ghi vào đó. AI2 không đọc, không ghi bảng của Backend.
2. **Trạng thái riêng của AI2** (job store, durable run store, nonce đã dùng) chuyển vào **cùng cụm Postgres, schema `ai2`**:
   - AI2 kết nối qua biến `AI2_DATABASE_URL`, bằng user `ai2_app`;
   - `ai2_app` chỉ có quyền trên schema `ai2`;
   - user của Backend không có quyền gì trên schema `ai2`.
3. **Migration của schema `ai2` do AI2 tự quản**, bằng alembic riêng trong `ai-service`, với bảng version đặt trong schema `ai2`. Alembic của Backend không đụng tới schema này. Backend chỉ tạo schema và user trong script khởi tạo DB khi deploy.
4. **Snapshot store vẫn nằm trong RAM**, và vẫn được dựng lại từ job store khi khởi động. Job store đã ở Postgres thì khởi động lại không mất gì.
5. **Vector chưa bật trên bản online** (D6 chưa duyệt). `vectors.sqlite` là **cache** embedding, không phải nguồn sự thật; volume cho nó vẫn giữ (Lead, 30/09). AI2 đề xuất chuyển vector vào schema `ai2` bằng pgvector và bỏ hẳn SQLite: quyết định **cùng lúc với D6**, vì chỉ cần khi vector bật.
6. **Workspace demo** (`persist.py`) không chạy trên bản online, vì các endpoint `/api/workspace/*` không được mở ra ngoài (D3).
7. **Job store, query store và durable run store của AI2 dùng Postgres (schema `ai2`) ngay từ lần deploy online đầu tiên** (AI2 cam kết 30/09). Việc AI2 bỏ SQLite cả ở local và test là lựa chọn nội bộ của AI2, không đổi contract.
8. **Phục hồi khi AI2 mất dữ liệu:** Backend gửi lại `/jobs/idp` với `attempt` mới (D7), dùng snapshot đã lưu phía Backend, qua `POST /dossiers/{id}/ai2/retry`. AI2 không cần sao lưu riêng.
9. **Volume:** không cần volume cho `AI2_JOB_DB` khi job store đã ở Postgres (mục 7). Volume cho `vectors.sqlite` (`AI2_VECTOR_DB`) vẫn giữ (Lead, 30/09). `AI2_VECTOR_RECALL_ENABLED` giữ `false` trên bản online (D6). Image không chứa `data/` (O4).

**Việc cần làm:**
- AI2:
  - chuyển job store, query store và durable run store sang Postgres (schema `ai2`) trước lần deploy online đầu tiên, có test chạy trên Postgres thật;
  - thêm alembic riêng;
  - đọc `AI2_DATABASE_URL`.
- Backend:
  - script khởi tạo tạo schema `ai2` và user `ai2_app`;
  - compose đặt `AI2_DATABASE_URL` cho `ai2-service`;
  - giữ volume cho `vectors.sqlite`, bỏ volume cho `AI2_JOB_DB` khi AI2 đã chạy trên Postgres; `AI2_VECTOR_RECALL_ENABLED=false` (mục 9);
  - kiểm tra `ai2/retry` dựng lại được hồ sơ sau khi AI2 mất dữ liệu.

**Liên quan DOC-04 ADR-02:** ADR-02 (17/09) ghi *"`ai-service` không kết nối PostgreSQL"*. DOC-11 §3 (29/09) yêu cầu *"bản online của AI2 ghi dữ liệu bền vào PostgreSQL"*. Hai tài liệu đang mâu thuẫn, và thực tế AI2 cũng đã không còn stateless: job store là SQLite. PR này thêm **ADR-14** vào DOC-04; Lead chấp nhận ngày 30/09 (phương án A). ADR-14 cho AI2 giữ trạng thái riêng trong schema `ai2`, và **giữ nguyên** phần còn lại của ADR-02: không ghi business table, không sở hữu queue hay lease, không có public API. Architecture Lead chọn một trong hai phương án:

| Phương án | Nội dung | Được | Mất |
|---|---|---|---|
| **A** (đề xuất) | ADR-14 được chấp nhận; AI2 dùng schema `ai2` như mục 2–3 ở trên | Khớp DOC-11 và cam kết Sprint 3 "AI2 trên Postgres"; khởi động lại không mất gì | Thêm một kết nối DB và một bộ migration |
| **B** | Giữ ADR-02: AI2 không nối Postgres; SQLite trên volume; khi mất dữ liệu thì Backend gửi lại `/jobs/idp` (mục 8) | Không đổi kiến trúc | Phải sửa DOC-11 §3; tạo lại container mà không có volume thì hỏi đáp tạm hỏng cho tới khi Backend gửi lại |

**Lead chọn phương án A (30/09).** ADR-14 chuyển sang được chấp nhận. Không sửa DOC-11 §3.

**Hạn:** mục 2, 3 và 7 trước lần deploy online đầu tiên (AI2 đề xuất, thay cho hạn 18/10). Nếu kịp, ngoại lệ tạm "AI2 còn SQLite trên volume `ai2_data`" ở DOC-12 §9 mục 1 không còn cần.

- [x] Chương duyệt  - [ ] Dũng duyệt  - [x] Trang duyệt: phương án A (review PR #37, 30/09)  Ghi chú: vector và pgvector theo D6.

## D12. Hồ sơ nhiều hợp đồng (Sprint 3)

**Hiện trạng:** DOC-11 mục 1 số 7 và DOC-11 §4.2 mục 12 yêu cầu finding hợp đồng–hợp đồng, với cùng điều kiện trích dẫn hai phía như finding có phụ lục. Hiện có bốn chỗ bắt đúng một hợp đồng:
- D5 (Sprint 2);
- adapter AI2, ở `BE-AI2-PROCESSING-CONTRACT.vi.md` §2 (*"Backend phải gửi đúng một member `body`"*);
- bước tách file `POST /dossiers/{id}/split` (PR #36);
- xác nhận manifest.

Giữ nguyên thì hồ sơ có hai hợp đồng không bao giờ tới được AI2.

**Đề xuất:**
- Request cho phép **một hoặc nhiều** member `body`.
- Phụ lục vẫn có `ANNEX_OF` trỏ tới **một** `body` cụ thể. Phụ lục không có quan hệ thì dùng quy tắc "chưa xác nhận" của D5.
- AI2 so **từng cặp `body`** (hợp đồng–hợp đồng), và so mỗi phụ lục với `body` mà nó `ANNEX_OF`.
  - Finding hợp đồng–hợp đồng dùng cùng shape và cùng điều kiện citation hai phía như finding có phụ lục (D9).
  - Mỗi phía của finding ghi rõ `member_id`.
- Luật "đúng một body" chỉ bỏ khi AI2 xử lý được nhiều body, qua cờ `max_body_members` trong `policy_flags`: Sprint 2 là `1`, Sprint 3 nâng lên. Như vậy Backend không gửi request mà AI2 chưa đọc được.
- **Thứ tự bắt buộc: AI2 trước, Backend sau.** `policy_flags` phía AI2 đặt `extra="forbid"`. Backend gửi `max_body_members` trước khi AI2 nhận trường này thì mọi request bị `422`.
- Backend bỏ luật "đúng một hợp đồng" ở `/split` và manifest **cùng lúc** với AI2, không bỏ trước.
- Schema: `be.ai2.processing.request.v1` thêm `policy_flags.max_body_members`. Bỏ ràng buộc "đúng một body" là thay đổi về nghĩa, nên AI2 và Backend cùng tăng lên `v1.1` và có test hai phía.

**Việc cần làm:**
- AI2: so cặp body–body; hỗ trợ `max_body_members`.
- Backend: nới luật ở `/split`, manifest và adapter khi `max_body_members > 1`; API conflict trả cặp hai hợp đồng.
- Trang: màn đối soát đọc được finding giữa hai hợp đồng.

**Hạn:** chốt trước khi bắt đầu DOC-11 §4.2 mục 12 trong Sprint 3.

**Lead đã duyệt (30/09):** quy tắc Sprint 3. AI2 nhận `max_body_members` trước, Backend mới nới `/split` và manifest. Màn đối soát hai hợp đồng là việc frontend sau.

- [x] Chương duyệt  - [ ] Dũng duyệt  - [x] Trang duyệt: quy tắc Sprint 3 (review PR #37, 30/09)  Ghi chú:

---

## Việc của từng bên sau review AI2 (30/09)

Review của Văn Dũng ở PR #37 xác nhận D2, D4, D5, D7 (409 và cùng `job_id`) và D9 đã khớp code AI2. Các chỗ còn lệch được chốt như trên. Danh sách việc:

**AI2**

| # | Mục | Việc | Hạn |
|---|---|---|---|
| A1 | D10 | Thêm `query_snapshot_digest` vào result và schema (**gấp nhất**, Backend chờ việc này) | 01/10 |
| A2 | D7 | `retryable` theo mã lỗi, không theo `review_state` (bỏ quy tắc đánh `retryable=true` cho mọi lỗi `BLOCKED`); retry chỉ khi `FAILED` và có lỗi `retryable=true` | 01/10 |
| A3 | D6 | Vector `/query` dựa vào egress của `/query`; trần embedding của `/query` đọc từ env AI2; test egress tắt → `SUCCEEDED`, vượt `max_llm_calls` → `INSUFFICIENT_EVIDENCE` | 02/10 |
| A4 | D2 | `AI2_QUERY_REQUIRE_SIGNATURE` (mặc định `true`, thiếu chữ ký → `401 SERVICE_ENVELOPE_MISSING`); vector ký mẫu cho CI của Backend | 02/10 |
| A5 | D12 | Nhận `policy_flags.max_body_members` **trước** khi Backend gửi | Trước DOC-11 §4.2 mục 12 |
| A6 | D1, D9 | Docstring `kafka_idp_worker.py`; comment lỗi thời về `table_id`/`cell_id` trong `wire.py` | 02/10 |
| A7 | D11 | Job store, query store, durable run store trên Postgres (schema `ai2`), alembic riêng, `AI2_DATABASE_URL` | Trước deploy online đầu tiên |

**Backend**

| # | Mục | Việc | Hạn |
|---|---|---|---|
| B1 | D7 | Payload tất định: `created_at` của snapshot lấy từ lúc lưu, không `datetime.now()` | 01/10 |
| B2 | D10 | Dùng `query_snapshot_digest` khi có, tạm tính như cũ khi chưa có; xoá hẳn `_ai2_query_snapshot_digest` và phương án `dossier.checksum` sau khi AI2 deploy A1 | Theo A1 |
| B3 | D6 | Egress luồng xử lý từ env; `use_vector=false` cho luồng xử lý. Bật vector cho `/query` chỉ khi Lead duyệt D6 **và** A3 đã deploy | 02/10 (phần bật: sau D6 và A3) |
| B4 | D5 | Chặn 0 hoặc nhiều body; hồ sơ hơn 6 tài liệu trả `422 DOSSIER_TOO_MANY_DOCUMENTS` ("Hồ sơ tối đa 6 tài liệu"); cập nhật `API-BE.md` và DOC-05b cùng lúc | 02/10 |
| B5 | D8 | `SUCCEEDED` + `BLOCKED` → `failed`; bỏ qua `review_state` khi `status` khác `SUCCEEDED` | 02/10 |
| B6 | D3, D11 | Override compose online: không publish 8002, healthcheck `/healthz`; script khởi tạo DB tạo schema `ai2` và user `ai2_app`, đặt `AI2_DATABASE_URL`; bỏ volume `AI2_JOB_DB` khi AI2 đã trên Postgres, giữ volume `vectors.sqlite`; `AI2_VECTOR_RECALL_ENABLED=false`; không tắt `AI2_QUERY_REQUIRE_SIGNATURE` | Trước deploy online đầu tiên |
| B7 | D1 | Xoá `submit_idp_job`/`get_idp_job`/`poll_idp_job`/`build_idp_request` trong `ai_adapters.py` | 02/10 |
| B8 | D2 | Test CI ký bằng vector mẫu của AI2 | Theo A4 |

**Lead (Trang):** đã duyệt D8, D11 (phương án A), D12 ngày 30/09. Còn D6: ghi provider và trần chi tiêu thì mới bật egress và vector online.

---

## Ngoài phạm vi DEC này

Các mục sau để lại cho Sprint 3:
- Không làm Kafka cho AI2 trước demo; hướng Sprint 3 nằm ở D1.
- Re-OCR theo yêu cầu của AI2.
- Conflict ngữ nghĩa.
- Offset ô bảng từ AI1.
- Quy tắc ưu tiên khi phụ lục ký sau sửa văn bản ký trước. Mục này sẽ có một DEC riêng.

## Lịch sử

| Ngày | Thay đổi | Người |
|---|---|---|
| 2026-09-29 | Bản đề xuất đầu tiên | Chương |
| 2026-09-29 | Thêm D11 (nơi lưu dữ liệu AI2). Backend chốt D1–D11 và chép vào `BE-AI2-PROCESSING-CONTRACT.vi.md` §6 | Chương |
| 2026-09-30 | Sửa câu theo comment của Văn Dũng lúc 09:08: `FAILED` không phải lúc nào cũng mang `BLOCKED` (hết thời gian là `NEEDS_REVIEW`), nên D7, D8 và §6.3 ghi "`review_state` không có nghĩa khi job không `SUCCEEDED`"; quy tắc giữ nguyên. Hạn D11 thành trước deploy online đầu tiên (chậm nhất 03/10). Dòng "Người duyệt" ghi đúng quyết định Lead | Chương |
| 2026-09-30 | Theo comment của Văn Dũng lúc 08:45: `FAILED` luôn mang `review_state="BLOCKED"`. Sửa D7, A2 và §6.3: `retryable` theo mã lỗi, không theo `review_state`; câu cũ "BLOCKED không bao giờ retry" sẽ chặn mọi retry, kể cả lỗi tạm. D8 ghi rõ giá trị `BLOCKED` | Chương |
| 2026-09-30 | Theo review của Trang (lần 3, gồm quyết định Lead) và Văn Dũng ở PR #37: Lead duyệt D8 (`pending_review`, "Chờ rà soát"), D11 phương án A (ADR-14 được chấp nhận), D12; D6 chưa duyệt nên vector và egress online giữ `false`; D1 bỏ câu "đã thống nhất", không làm Kafka trước demo; D2 `AI2_QUERY_REQUIRE_SIGNATURE`; D5 mã lỗi `DOSSIER_TOO_MANY_DOCUMENTS`; D8 bỏ qua `review_state` khi không `SUCCEEDED`; D11 AI2 lên Postgres trước deploy online, pgvector quyết cùng D6; trần embedding `/query` do AI2 đọc từ env; B3 sau A3; thêm A7 | Chương |
| 2026-09-30 | Theo review của Văn Dũng (AI2) ở PR #37: D2 lệch đồng hồ 30 giây, TTL tối đa 3600 giây, tắt `/query` không chữ ký online; D5 tối đa 6 file; D6 bật vector cho `/query` online, dựa vào egress của `/query`, trần `max_embedding_tokens`; D7 payload tất định và định nghĩa retry; D8 `review_state=null`; D10 `state` thêm `BLOCKED`, chuyển tiếp digest, bỏ `query_binding`; D11 vector bật, volume gồm `vectors.sqlite`; D12 AI2 nhận `max_body_members` trước; thêm bảng việc của từng bên | Chương |
| 2026-09-30 | Theo review của Trang ở PR #37 (lần 2): D1 tách Sprint 2 (HTTP) và Sprint 3 (Kafka theo DOC-05e v2, PR #36); PR này thôi sửa DOC-05e để không ghi đè PR #36; dòng mở đầu `BE-AI2-PROCESSING-CONTRACT` §6 ghi D6, D8, D11, D12 còn chờ Lead | Chương |
| 2026-09-29 | Theo review của Trang ở PR #37: thêm D12 (nhiều hợp đồng); D5 chỉ áp dụng cho Sprint 2; D11 nêu mâu thuẫn với ADR-02 kèm phương án A/B và ADR-14 (Đề xuất); D4 sửa ADR-05 cho khớp; DOC-05e trỏ tới D1 (phần sửa DOC-05e đã rút ở `2bc7515`, PR này không còn sửa file đó) | Chương |
