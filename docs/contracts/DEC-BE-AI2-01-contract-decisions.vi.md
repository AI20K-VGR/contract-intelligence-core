# DEC-BE-AI2-01: Các điểm chốt của contract Backend ↔ AI2

**Trạng thái:** `proposed`, chờ duyệt
**Ngày:** 2026-09-29
**Người soạn:** Chương (Backend)
**Người duyệt:** Chương (Backend), Văn Dũng (AI2). Riêng D6 và D8 cần thêm Trang (Lead).
**Bổ sung cho:** [BE-AI2-PROCESSING-CONTRACT.vi.md](BE-AI2-PROCESSING-CONTRACT.vi.md), [AI2-SERVICE-ENVELOPE-v1.vi.md](AI2-SERVICE-ENVELOPE-v1.vi.md)
**Căn cứ:**
- Code của nhánh `feature/sprint3-backend` (`d667bd9`).
- Kế hoạch tuần 3 của AI2: `plans/reports/ke-hoach-ai2-tuan3-260928-261004.md`, commit `63a07c1`.

---

## Cách dùng tài liệu này

Mỗi mục D1–D10 gồm bốn phần: **hiện trạng** (dẫn tới code), **đề xuất**, **việc của từng bên** và **ô duyệt**. Người duyệt đánh dấu `[x]` và ghi chú nếu không đồng ý.

Khi cả hai bên duyệt xong:
1. Đổi trạng thái sang `accepted`.
2. Chép các quy tắc đã chốt vào `BE-AI2-PROCESSING-CONTRACT.vi.md`.
3. Nếu mục nào đổi schema, cập nhật file `*.schema.json` tương ứng.

**Hạn:** D1, D2, D4, D10 cần chốt **trước T4 30/09**, vì bốn mục này chặn việc của AI2 trong tuần. D6 và D8 chốt cùng Lead **trước T5 01/10**.

## Tóm tắt

| # | Chủ đề | Đề xuất ngắn | Hạn |
|---|---|---|---|
| D1 | Kênh gọi | Chỉ HTTP `/jobs/idp` + poll; Kafka AI2 ra khỏi Sprint 2 | 30/09 |
| D2 | Xác thực HMAC | Giữ tham số hiện tại; một secret mới dùng chung cho 3 service | 30/09 |
| D3 | Mạng | Không publish 8002; healthcheck gọi `/healthz` | 01/10 |
| D4 | Snapshot và digest | Chỉ `ai1.snapshot.v1`; `source_digest` là 64 hex chữ thường, không có tiền tố | 30/09 |
| D5 | Hồ sơ nhiều file | Gửi đủ snapshot; role theo `doc_type`; quan hệ `ANNEX_OF` do Backend quyết định | 01/10 |
| D6 | `policy_flags` | Egress bật/tắt bằng biến môi trường cho từng luồng, mặc định `false` | 01/10 (Lead) |
| D7 | Idempotency và retry | Key `<run_id>:ai2`, cố định trong một run; `attempt` tăng khi retry | 01/10 |
| D8 | Ánh xạ trạng thái | Tách "AI2 xong" khỏi "chờ review" | 01/10 (Lead) |
| D9 | Xử lý kết quả | Lưu ở dạng đề xuất, publish sau khi reviewer duyệt | 01/10 |
| D10 | Contract hỏi đáp | AI2 trả `query_snapshot_digest` trong result; Backend lưu nguyên giá trị, không tự tính | 30/09 |

---

## D1. Kênh gọi AI2

**Hiện trạng:**
- Compose gọi AI2 qua HTTP (`AI_SERVICE_MODE: http`, `AI2_BASE_URL: http://ai2-service:8002`).
- Worker gọi `submit_ai2_processing` rồi `poll_ai2_processing` (`backend/.../worker.py:1079`).
- Phía AI2, `app/transport/kafka_idp_worker.py` lại tự ghi mình là "runtime path", còn `/jobs/idp` là "demo-only". Hai phía đang mô tả ngược nhau.

**Đề xuất:**
- Trong Sprint 2, kênh chính thức là HTTP: `POST /jobs/idp` trả `202` kèm `job_id`, sau đó Backend poll `GET /jobs/{job_id}`.
- Kafka giữ cho AI1 (DOC-05d). Kafka của AI2 (DOC-05e) để lại cho Sprint 3.
- Backend gộp hai bộ hàm trùng nhau trong `infrastructure/ai_adapters.py`: giữ `submit_ai2_processing`/`poll_ai2_processing`, bỏ `submit_idp_job`/`get_idp_job`/`poll_idp_job` và `build_idp_request` (bản chỉ gửi một snapshot, có `max_llm_calls=0`).

**Việc cần làm:**
- AI2: sửa docstring của `kafka_idp_worker.py` và `/jobs/idp`. Ghi đúng kênh vào phần AI2 của Architecture doc.
- Backend: xoá bộ hàm trùng; ghi DOC-05e là "chưa dùng trong Sprint 2".

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

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
- Chênh lệch đồng hồ cho phép: ±60 giây. AI2 xác nhận con số này, hoặc sửa theo giá trị đang dùng trong `service_envelope.py`.

**Việc cần làm:**
- AI2: xác nhận `service_envelope.py` chuẩn hoá JSON giống bảng trên, kể cả `ensure_ascii=False`. Chỉ cần lệch một chi tiết là mọi request bị 401.
- Backend: thêm vào CI một test ký thử bằng secret cố định và so với vector mẫu do AI2 cung cấp.

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

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

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

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

**Việc cần làm:**
- AI2: chuẩn hoá digest ngay khi nhận request.
- AI1 (Đức Dũng): chốt một phiên bản snapshot (xem kế hoạch AI2 §5).

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D5. Hồ sơ nhiều file: member và quan hệ

**Hiện trạng** (`canonical_processing.py:234-365`):
- Backend gửi mọi snapshot đã chọn của hồ sơ.
- `role` bằng `body` khi `doc_type == "contract"`; mọi trường hợp khác là `annex`.
- `role_relation_map[]` chỉ chứa quan hệ `annex_of` mà Backend đã lưu. Hồ sơ chỉ có thân HĐ thì không có quan hệ nào.
- Upload file trộn giờ được tách thành nhiều tài liệu trước khi OCR (`d667bd9`).

**Đề xuất:**
- Mỗi request có **đúng một** member `body`. Nếu hồ sơ không có hoặc có nhiều hơn một tài liệu `contract`, Backend không gửi sang AI2 mà báo lỗi cấu hình hồ sơ. AI2 không tự chọn.
- Phụ lục không có quan hệ `ANNEX_OF` vẫn được gửi với `role=annex`. AI2 được so sánh nó với thân HĐ, nhưng mọi finding ghi rõ là "quan hệ chưa xác nhận" (khớp với DEC-1 của AI2).
- Tài liệu tách ra từ file trộn mang `doc_type` từ bước phân loại. Người dùng sửa được role trước khi chạy AI2.
- AI2 không suy luận, không sửa role hay quan hệ.

**Việc cần làm:**
- Backend: chặn trường hợp có 0 hoặc nhiều hơn 1 body trước khi submit, kèm mã lỗi.
- AI2: finding liên tài liệu khi thiếu `ANNEX_OF` phải gắn nhãn "chưa xác nhận".

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D6. `policy_flags`: egress, vector và ngân sách (cần Lead)

**Hiện trạng:**

| Luồng | Nơi đặt | `egress_allowed` | `use_vector` | Ngân sách |
|---|---|---|---|---|
| Xử lý hồ sơ | `canonical_processing.py:354-363` (hard-code) | `false` | `true` | `300s + 2s × số trang`, `max_llm_calls=20`, `max_embedding_tokens=50000` |
| Hỏi đáp | `settings.py:229-247` (qua env) | `false` | `false` | timeout 20 giây |

Kế hoạch AI2 (O6) ghi compose của nhánh AI2 để egress mặc định `true`. Hai nhánh đang lệch nhau.

**Đề xuất:**
- Egress của luồng xử lý hồ sơ đọc từ biến env `AI2_PROCESSING_EGRESS_ALLOWED`, không hard-code nữa. Egress của hỏi đáp giữ `AI2_QUERY_EGRESS_ALLOWED`. Cả hai mặc định `false`.
- Bật egress thì phải ghi tên provider LLM và dữ liệu nào được gửi ra ngoài vào Architecture doc (O6).
- Giữ các giới hạn ngân sách hiện tại. AI2 phải tuân thủ: vượt `max_llm_calls` thì trả `review_state=INSUFFICIENT_EVIDENCE` kèm lý do, không dừng job với `FAILED`.
- Khi `egress_allowed=false`, AI2 không được gọi LLM bên ngoài. Kết quả vẫn phải `SUCCEEDED`, chỉ với phần xử lý bằng luật cố định, **không** được trả `LLM_UNAVAILABLE`.

**Lead cần chốt:** bản demo online có bật egress hay không, dùng provider nào, và giới hạn chi tiêu bao nhiêu (kế hoạch AI2 §7 mục 1).

**Việc cần làm:**
- Backend: đọc egress của luồng xử lý từ env.
- AI2: xác nhận hành vi khi egress tắt và khi vượt ngân sách.

- [ ] Chương duyệt  - [ ] Dũng duyệt  - [ ] Trang duyệt  Ghi chú:

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

- Nếu cùng `(idempotency_key, attempt)` mà payload khác, AI2 trả `409`. Backend coi đây là lỗi lập trình và không retry.
- Backend retry tối đa 3 attempt cho một run.

**Việc cần làm:**
- AI2: xác nhận `409` và việc trả lại cùng `job_id`.
- Backend: thêm giới hạn attempt và nhánh xử lý `retryable=false`.

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

## D8. Ánh xạ trạng thái AI2 sang trạng thái hồ sơ (cần Lead)

**Hiện trạng:**
- `persistence.py:155-168` coi mọi `review_state != PASS` là `NEEDS_REVIEW` và đặt `evidence_ready=false`.
- Hồ sơ dừng ở trạng thái `extracted`. UI không phân biệt được "AI2 đã xong, đang chờ reviewer" với "AI2 chưa xong".

**Đề xuất:**

| AI2 `status` + `review_state` | Trạng thái hồ sơ | UI hiển thị |
|---|---|---|
| `SUCCEEDED` + `PASS` | `pending_review` | "Chờ duyệt": reviewer vẫn duyệt, vì kết quả chỉ là đề xuất (D9) |
| `SUCCEEDED` + `NEEDS_REVIEW` | `pending_review` | "Chờ duyệt", kèm số mục cần xem |
| `SUCCEEDED` + `INSUFFICIENT_EVIDENCE` | `pending_review` | "Chờ duyệt, thiếu bằng chứng" |
| `SUCCEEDED` + `BLOCKED` | `failed` | Lỗi, kèm mã từ `errors[]` hoặc lý do chặn |
| `FAILED` | retry theo D7; hết lượt thì `failed` | Lỗi, kèm `code` |

- `evidence_ready` chỉ cho biết đủ bằng chứng để publish. Nó **không** quyết định hồ sơ có vào hàng chờ review hay không.

**Lead cần chốt:** UI dùng tên trạng thái `pending_review` hay `extracted` cho "chờ duyệt" (kế hoạch AI2 §7 mục 4).

**Việc cần làm:**
- Backend: sửa bước chuyển trạng thái trong worker; thêm migration nếu cần giá trị trạng thái mới.
- AI2: không phải làm gì.

- [ ] Chương duyệt  - [ ] Dũng duyệt  - [ ] Trang duyệt  Ghi chú:

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
- AI2: bảo đảm mục 1, mục 3 và mục 6 ngay ở đầu ra.

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

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
- **Request `/query`:** `query`, `dossier_id`, `tenant_id`, `actor_id`, `snapshot_version`, `snapshot_digest`, `query_contract_version="ai2.query.v1"`, `acl_context`, `policy_flags`, cùng envelope scope `ai2.query`.
  - `acl_context` là `user_id` của người hỏi. AI2 chỉ dùng để ghi log và audit, không dùng để phân quyền; Backend đã kiểm tra quyền trước khi gọi.
- **Response:** `state`, `answer`, `citations[]`, `used_llm`, `reasoning_trace`, `retrieval_layer`.
  - `state` chỉ nhận `ANSWERED`, `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE`. AI2 xác nhận lại danh sách này.
  - UI hiện `used_llm` dưới dạng một nhãn nhỏ.
- **Timeout:** giữ 20 giây. Đo lại trên máy chủ ngày 02/10 (O7).

**Việc cần làm:**
- AI2: thêm `query_snapshot_digest` vào result và schema; chốt danh sách giá trị `state`.
- Backend: lưu digest theo AI2 trả về, xoá code tự tính, xoá phương án thay thế.

- [ ] Chương duyệt  - [ ] Dũng duyệt  Ghi chú:

---

## Ngoài phạm vi DEC này

Các mục sau để lại cho Sprint 3:
- Kênh Kafka cho AI2.
- Re-OCR theo yêu cầu của AI2.
- Conflict ngữ nghĩa.
- Offset ô bảng từ AI1.
- Quy tắc ưu tiên khi phụ lục ký sau sửa văn bản ký trước. Mục này sẽ có một DEC riêng.

## Lịch sử

| Ngày | Thay đổi | Người |
|---|---|---|
| 2026-09-29 | Bản đề xuất đầu tiên | Chương |
