# DEC-BE-AI1-01: Chia lệnh OCR theo cụm trang

**Trạng thái:** `accepted`. Chương (Backend) và Đức Dũng (AI1) duyệt ngày 01/10 (PR #48, commit `04f0def`); Trang approve PR #48 cùng ngày.
**Ngày:** 2026-10-01
**Người soạn:** Chương (Backend)
**Người duyệt:** Đức Dũng (AI1), Chương (Backend)
**Bổ sung cho:** [DOC-05d](../DOC-05d-kafka-ai1-ocr-contract.md) (Kafka Backend ↔ AI1)
**Căn cứ:**
- DOC-11 §4.2 việc 5 (Backend) và §4.3 việc 3 (AI1): chia lệnh OCR theo cụm trang, chạy song song, có trần số cụm chạy cùng lúc; một cụm treo thì chỉ cụm đó timeout, cụm khác giữ kết quả.
- Code trên `develop` (`cb27fbc`).

---

## Cách dùng tài liệu này

Mỗi mục C1–C9 gồm **hiện trạng**, **đề xuất** và **ô duyệt**. Người duyệt đánh dấu `[x]` và ghi chú nếu không đồng ý. Câu hỏi cho AI1 nằm ở mục [Câu hỏi cho AI1](#câu-hỏi-cho-ai1).

Khi hai bên duyệt xong:
1. Đổi trạng thái sang `accepted`.
2. Chép các quy tắc đã chốt vào DOC-05d (thêm §9 "Cụm trang") khi xong bước 5 của [Thứ tự triển khai](#thứ-tự-triển-khai), vì DOC-05d mô tả hành vi đang chạy.
3. Mỗi bên làm phần việc của mình ở [Việc của từng bên](#việc-của-từng-bên), theo thứ tự triển khai ở cuối tài liệu.

**Hạn:** AI1 trả lời câu hỏi và duyệt trước **T6 02/10**, để hai bên làm trong Sprint 3.

## Vấn đề

Với một PDF 200 trang (khoảng 50 MiB), hiện tại:

| Điểm | Hiện trạng | Hệ quả |
|---|---|---|
| Lệnh OCR | Một lệnh cho cả tài liệu, `pages_to_process` = 1..200 (`worker.py:818`) | Một trang treo thì cả tài liệu chờ tới hạn run (600 + 30 × 200 = 6600 giây) rồi `AI1_TIMEOUT`, mất kết quả của cả 200 trang |
| AI1 nhận trang | `align_pages_to_pdf` ép về toàn bộ dải trang (`kafka_worker.py:138`); `_run_backend_ocr` từ chối tập con (`backend_ocr_job.py:283`) | Backend không gửi được một phần tài liệu |
| Song song | AI1 OCR tối đa 8 trang cùng lúc trong **một** tài liệu (`AI1_MAX_PAGES_IN_FLIGHT`, `backend_ocr_job.py:38`), nhưng worker xử lý **từng lệnh một** (vòng `async for`, `_process_lock`) | Trong lúc một tài liệu 200 trang đang chạy, mọi hồ sơ khác phải xếp hàng chờ |
| Kafka | Topic `ci.ai1.ocr.commands` tự tạo (`KAFKA_AUTO_CREATE_TOPICS_ENABLE`), nên chỉ có 1 partition; compose có đúng một `ai1-worker` (`container_name`) | Không chạy thêm worker được |
| Tiến độ | Backend chỉ nhận `completed` hoặc `failed` cho cả tài liệu | UI không biết trang nào xong, trang nào lỗi |

Riêng `nodes[]` (cây điều khoản) và `table_continuity[]` được dựng trên **cả tài liệu** (`build_snapshot.py:165`), và `mark_duplicate_pages` cũng so mọi trang của tài liệu (`process_document.py:273`). Nếu chia cụm mà mỗi cụm tự dựng snapshot, một điều khoản hoặc một bảng nằm vắt qua ranh giới hai cụm sẽ bị cắt đôi.

## Tóm tắt

| # | Chủ đề | Đề xuất ngắn |
|---|---|---|
| C1 | Hai pha | Pha 1: AI1 OCR từng cụm, trả kết quả trang. Pha 2: AI1 dựng snapshot cuối từ mọi cụm (`ai1.ocr.assemble`). Snapshot cuối giữ đúng dạng `ai1.snapshot.v1` hiện tại |
| C2 | Cỡ cụm | 20 trang (`AI1_OCR_CHUNK_PAGES`); tài liệu tới 20 trang đi một lệnh như hiện nay; `0` = tắt chia cụm |
| C3 | Lệnh và sự kiện | Lệnh cụm thêm trường `chunk`; sự kiện mới `ai1.ocr.chunk_started`, `ai1.ocr.chunk_completed`, `ai1.ocr.chunk_failed`; kết quả cụm luôn ghi lên MinIO |
| C4 | Song song và trần | Topic 6 partition, key = `chunk_id`; AI1 chạy nhiều replica; Backend gửi tối đa 2 cụm của một run cùng lúc; trần provider tính theo số request (khoảng 16 ở `budget`, chế độ của bản online), E6 chốt số replica |
| C5 | Lỗi một cụm | Backend tự gửi lại cụm lỗi tạm 1 lần; quá số lần thì run `failed`, cụm đã xong được giữ, "chạy lại phần lỗi" chỉ gửi cụm còn thiếu |
| C6 | Thời hạn | Hạn cụm = 120 + 30 × số trang của cụm, tính từ `chunk_started`; hạn run giữ nguyên làm trần ngoài |
| C7 | Tiến độ | Backend ghi số cụm và số trang đã xong vào bước S2, SSE phát qua sự kiện bước sẵn có |
| C8 | Idempotency | Backend nhận kết quả cụm theo `(run_id, chunk_id, attempt_id)` và đúng URI đã cấp; bản trùng bị bỏ qua |
| C9 | Chất lượng trang khi chia cụm | Trước khi chia cụm, Backend gửi `ai1.ocr.inspect` cho cả tài liệu; AI1 đo chất lượng và quyết định từ chối theo quy tắc của #47; không từ chối thì danh sách trang xấu đi kèm lệnh của từng cụm (`chunk.low_quality_pages`) |

---

## C1. Hai pha: OCR theo cụm, dựng snapshot một lần

**Đề xuất:**

```
Backend                                   AI1
  │ ai1.ocr.inspect             ───────►  đo chất lượng mọi trang, không gọi OCR (C9)
  │                             ◄───────  ai1.ocr.inspected (hoặc ai1.ocr.failed nếu từ chối)
  │ ai1.ocr.command (cụm 1..k)  ───────►  OCR các trang của cụm, upload ảnh trang
  │                             ◄───────  ai1.ocr.chunk_started / chunk_completed (kết quả trang trên MinIO)
  │  ... đủ mọi cụm của tài liệu ...
  │ ai1.ocr.assemble            ───────►  đọc kết quả mọi cụm, dựng nodes + table_continuity + snapshot
  │                             ◄───────  ai1.ocr.completed (như hiện nay, result_ref)
```

- **Pha 1 (OCR cụm):** phần tốn tiền và tốn thời gian (gọi engine OCR). Mỗi cụm chỉ OCR các trang của nó, giữ **số trang tuyệt đối** trong tài liệu (cụm 3 là trang 41–60, không đánh lại 1–20).
- **Pha 2 (assemble):** không gọi engine OCR. AI1 dựng `nodes[]`, `table_continuity[]` và snapshot `ai1.snapshot.v1` từ các trang của mọi cụm, rồi trả `ai1.ocr.completed` đúng như hiện nay.
- **Bước nào cần nhìn cả tài liệu thì chạy ở pha 2**, không chạy theo cụm:
  - `mark_duplicate_pages` (đánh dấu trang trùng hoặc gần trùng theo văn bản), hiện chạy cuối `ProcessDocument.execute` (`process_document.py:273`), chuyển sang assemble.
  - Header/footer lặp (`running_text`) và nối bảng (`table_continuity`) đã nằm trong bước dựng snapshot, nên tự động thuộc pha 2.
  - Chi phí chấp nhận trong pha đầu: trang trùng pixel chỉ được dùng lại trong cùng một cụm. Hai trang giống hệt nhau ở hai cụm khác nhau sẽ bị OCR hai lần.
- Kết quả trang của pha 1 (`ai1.pages.v1`) **do AI1 định nghĩa**. Backend không đọc nội dung, chỉ giữ URI, sha256 và số byte để chuyển lại cho AI1 ở pha 2.
- Phía sau `ai1.ocr.completed` không đổi gì: Backend xử lý như hiện nay (`_record_ai1_document`, `worker.py:253`), AI2 nhận cùng dạng snapshot.

**Phương án đã cân nhắc và không chọn:** mỗi cụm trả một snapshot đầy đủ rồi Backend ghép lại. Không chọn vì Backend sẽ phải dựng lại cây điều khoản và nối bảng qua ranh giới cụm. Đó là logic hiểu tài liệu của AI1, Backend không nên giữ.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C2. Cỡ cụm

**Đề xuất:**
- `AI1_OCR_CHUNK_PAGES` (env của `backend-worker`), mặc định **20**. Cụm cuối có thể ngắn hơn. Tài liệu 200 trang thành 10 cụm.
- Tài liệu có **tới 20 trang**: một lệnh `ai1.ocr.command` như hiện nay, không có `chunk`, không cần assemble. Hồ sơ nhỏ giữ nguyên đường chạy cũ.
- `AI1_OCR_CHUNK_PAGES=0`: tắt chia cụm. Dùng để triển khai từng bước (xem [Thứ tự triển khai](#thứ-tự-triển-khai)).

**Vì sao 20:** với 8 trang chạy cùng lúc, một cụm xong trong khoảng 3 lượt gọi engine. Kết quả khoảng 71 KiB/trang (DOC-05d §6), tức khoảng 1,4 MiB cho một cụm. Hạn cụm 720 giây (C6) vẫn đủ ngắn để một trang treo không kéo dài quá lâu.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C3. Lệnh và sự kiện

### Lệnh OCR một cụm (`ai1.ocr.command`)

Giữ nguyên `event_type` và các trường hiện có, thêm trường `chunk`:

```json
{
  "task_id": 4821937,
  "attempt_id": 1,
  "tenant_id": "tenant_vgr_01",
  "document_id": "doc_01J9X1AB",
  "source_blob_get_url": "http://minio:9000/dossiers/...?X-Amz-...",
  "source_sha256": "a1b2c3...",
  "pages_to_process": [41, 42, 43, 44, 45, 46, 47, 48, 49, 50, 51, 52, 53, 54, 55, 56, 57, 58, 59, 60],
  "chunk": {
    "chunk_id": "doc_01J9X1AB:c03",
    "index": 3,
    "count": 10,
    "page_start": 41,
    "page_end": 60,
    "document_page_count": 200,
    "low_quality_pages": { "57": ["speckle"] }
  },
  "render_target": {
    "dpi": 150,
    "format": "PNG",
    "presigned_put_urls": { "41": "...", "60": "..." }
  },
  "options": {
    "engine": "mistral",
    "dpi": 150,
    "language": "vi",
    "document_role": "contract",
    "filename": "hop-dong.pdf",
    "result_target": {
      "put_url": "http://minio:9000/ci-render/doc_01J9X1AB/ai1-result/run_01…/c03.json?X-Amz-…",
      "uri": "s3://ci-render/doc_01J9X1AB/ai1-result/run_01…/c03.json",
      "content_type": "application/json"
    }
  }
}
```

| Trường | Quy tắc |
|---|---|
| `chunk` | Có thì AI1 chỉ OCR `pages_to_process` và trả kết quả trang (pha 1). Không có thì xử lý cả tài liệu như hiện nay |
| `pages_to_process` | Đúng dải `page_start..page_end`, số trang tuyệt đối |
| `low_quality_pages` | Các trang xấu **của cụm này** theo kết quả `ai1.ocr.inspected` (C9), kèm lý do. AI1 không đo lại; các trang này chỉ đọc một lần và gắn `low_quality_scan:<lý do>`. Rỗng `{}` khi cụm không có trang xấu |
| `chunk_id` | `<document_id>:c<index 2 chữ số>`; `index` bắt đầu từ 1 |
| `task_id` | Riêng cho từng cụm (Backend băm từ `chunk_id`), để dedupe `(document_id, task_id, attempt_id)` ở DOC-05d §6 không gộp hai cụm |
| `attempt_id` | Lần gửi của cụm: 1, rồi 2 khi Backend gửi lại (C5) |
| `presigned_put_urls` | Chỉ các trang của cụm |
| `result_target` | Luôn có; mỗi cụm một object riêng |
| `correlation` | Như hiện nay, thêm `chunk_id`. AI1 trả lại nguyên `correlation` trong mọi sự kiện của cụm |
| Message key | `chunk_id` (C4) |

### Sự kiện của cụm (`ci.ai1.ocr.results`)

| `event_type` | Khi nào | `payload` |
|---|---|---|
| `ai1.ocr.chunk_started` | AI1 bắt đầu xử lý cụm (đã nhận lệnh, trước khi tải PDF) | `{"chunk_id", "job_id", "started_at"}` |
| `ai1.ocr.chunk_completed` | OCR xong và kết quả trang đã ghi lên `result_target` | xem dưới |
| `ai1.ocr.chunk_failed` | Lỗi cả cụm (tải PDF, sai sha256, engine hết lượt thử...) | `{"chunk_id", "job_id", "error": {"code", "message", "retryable"}}` |

```json
{
  "chunk_id": "doc_01J9X1AB:c03",
  "job_id": "ai1_abc123",
  "status": "completed",
  "result_ref": {
    "schema_version": "ai1.pages.v1",
    "uri": "s3://ci-render/doc_01J9X1AB/ai1-result/run_01…/c03.json",
    "sha256": "<hex>",
    "bytes": 1468000
  },
  "usage": { "engine": "mistral", "pages": 20, "failed_pages": [57] }
}
```

- Một trang lỗi trong cụm **không** làm cụm lỗi. Trang đó vẫn có trong kết quả với `status=FAILED`, giống hiện nay, và `usage.failed_pages` liệt kê số trang lỗi để Backend báo tiến độ (C7).
- `error.retryable` theo **mã lỗi**, cùng quy tắc với AI2 (DEC-BE-AI2-01 D7): lỗi tạm (429/529 của provider, mất kết nối MinIO) là `true`; PDF hỏng, sai sha256 là `false`. Mã lỗi theo DOC-11 §2: `AI1_RATE_LIMITED`, `AI1_UNAVAILABLE`, `AI1_TIMEOUT`, `AI1_SOURCE_INVALID`, `AI1_OCR_FAILED`.

### Lệnh dựng snapshot (`ai1.ocr.assemble`)

Backend gửi khi mọi cụm của một tài liệu đã `chunk_completed`. Topic `ci.ai1.ocr.commands`, key `document_id`:

```json
{
  "task_id": 102938,
  "attempt_id": 1,
  "tenant_id": "tenant_vgr_01",
  "document_id": "doc_01J9X1AB",
  "source_blob_get_url": "http://minio:9000/dossiers/...?X-Amz-...",
  "source_sha256": "a1b2c3...",
  "document_page_count": 200,
  "chunks": [
    {
      "chunk_id": "doc_01J9X1AB:c01",
      "page_start": 1,
      "page_end": 20,
      "result_get_url": "http://minio:9000/ci-render/...c01.json?X-Amz-…",
      "sha256": "<hex>",
      "bytes": 1452000
    }
  ],
  "options": {
    "engine": "mistral",
    "dpi": 150,
    "language": "vi",
    "document_role": "contract",
    "filename": "hop-dong.pdf",
    "result_target": { "put_url": "…", "uri": "s3://ci-render/doc_01J9X1AB/ai1-result/run_01….json", "content_type": "application/json" }
  }
}
```

- `chunks` theo thứ tự trang và phủ đủ 1..`document_page_count`, không hở, không chồng.
- `source_blob_get_url` và `source_sha256` **bắt buộc** (Q3): `BuildSnapshot` mở PDF gốc để tính `source_digest`, lấy kích thước từng trang và render ảnh trang (`build_snapshot.py:129–145`). Chỉ bỏ được khi pha 1 lưu sẵn kích thước và ảnh trang; khi đó sửa DEC trước.
- AI1 kiểm tra `sha256` của từng kết quả cụm, dựng snapshot rồi trả `ai1.ocr.completed` hoặc `ai1.ocr.failed` **đúng như DOC-05d §5**. `result_target` là đường dẫn của cả tài liệu, giống hiện nay.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C4. Song song và trần số cụm

**Đề xuất:**
- **Kafka:** tạo trước topic `ci.ai1.ocr.commands` với **6 partition** bằng script khởi tạo, không để tự tạo. Key = `chunk_id`, nên các cụm của một tài liệu rải ra nhiều partition. Lệnh assemble dùng key `document_id`.
- **AI1:** chạy `ai1-worker` thành **nhiều replica** trong cùng group `ci-ai1-ocr`: bỏ `container_name` trong compose, đặt `AI1_WORKER_REPLICAS`, mặc định 2. Mỗi replica vẫn OCR 8 trang cùng lúc như hiện nay.
- **Backend:** mỗi run gửi tối đa **2 cụm cùng lúc** (`AI1_OCR_MAX_CHUNKS_IN_FLIGHT`). Mỗi khi một cụm xong hoặc lỗi hẳn, Backend gửi cụm kế tiếp. Nhờ vậy một tài liệu 200 trang không đổ cả 10 cụm vào hàng đợi, và cụm của hồ sơ khác được chen vào giữa.

**Trần gọi provider (tính theo số request, không theo số trang):**
- Số trang OCR cùng lúc tối đa = số replica × `AI1_MAX_PAGES_IN_FLIGHT` = 2 × 8 = 16 trang.
- Mỗi trang gọi Mistral 1 lần ở `AI1_COST_MODE=budget`, 2 lần ở `accuracy` (2512 và 4-1 chạy song song), có thể thêm GPT cho các dòng mâu thuẫn. Vì vậy số request Mistral cùng lúc khoảng **16** ở `budget` và **32** ở `accuracy`.
- `ai1-worker` đọc `AI1_COST_MODE` từ `ai-service/.env` qua `env_file` (`docker-compose.yml:427`); `.env.example` đặt `budget`. Code chỉ rơi về `accuracy` (`backend_ocr_job.py:196`) khi `.env` thiếu biến này. Bản online chạy **`budget`** (AI1 chốt 01/10, xem review approve #48): khoảng 16 request Mistral cùng lúc.
- `AI1_WORKER_REPLICAS = 2` và `AI1_MAX_PAGES_IN_FLIGHT = 8` là giá trị tạm. E6 đo xem có bị 429 không, rồi mới chốt hai giá trị này. Đổi chúng không cần đổi contract.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C5. Lỗi một cụm

**Đề xuất:**
- `chunk_failed` có `retryable=true`, hoặc cụm quá hạn (C6): Backend **tự gửi lại cụm đó một lần** với `attempt_id` + 1 (`AI1_OCR_CHUNK_MAX_ATTEMPTS`, mặc định 2). Các cụm khác không bị ảnh hưởng.
- `retryable=false`, hoặc đã hết lượt gửi lại: run `failed` với mã lỗi của cụm (`AI1_TIMEOUT` khi quá hạn). Kết quả của các cụm đã xong **được giữ trên run**.
- "Chạy lại phần OCR lỗi" (`POST /dossiers/{id}/ocr/retry-failed`): run mới mang theo các cụm đã xong và chỉ gửi cụm còn thiếu, giống cách đang làm với từng tài liệu.
- Kết quả cụm về muộn, sau khi run đã `failed`: vẫn được giữ, như quy tắc hiện tại với kết quả tài liệu.
- Lỗi ở pha assemble: `ai1.ocr.failed` như hiện nay. "Chạy lại phần lỗi" chỉ gửi lại lệnh assemble, không OCR lại.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C6. Thời hạn

**Đề xuất:**
- **Hạn cụm** = `AI1_CHUNK_DEADLINE_BASE_SECONDS` (120) + `AI1_DEADLINE_PER_PAGE_SECONDS` (30) × số trang của cụm, tức 720 giây cho cụm 20 trang. Tính từ lúc nhận `chunk_started`, vì cụm có thể phải chờ trong hàng đợi Kafka. Nếu chưa nhận `chunk_started` thì tính từ lúc gửi, cộng thêm hạn của một cụm (thời gian chờ tối đa của một cụm phía trước).
- **Hạn assemble:** 300 giây từ lúc gửi.
- **Hạn run** giữ nguyên (600 + 30 × tổng số trang của hồ sơ) làm trần ngoài; presigned URL vẫn sống lâu hơn hạn run 10 phút.
- Watchdog hiện có (`worker.py:1590`) kiểm tra thêm hạn cụm, theo cùng chu kỳ.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C7. Tiến độ

**Đề xuất:** mỗi sự kiện cụm, Backend cập nhật `metrics` của bước S2:

```json
{ "chunks_total": 10, "chunks_done": 4, "pages_total": 200, "pages_done": 80, "failed_pages": [57] }
```

SSE đã phát thay đổi của bước, nên không cần sự kiện SSE mới. Hiển thị trên UI là việc riêng của Frontend, cập nhật DOC-05b sau; AI1 không cần làm gì thêm ngoài `usage.failed_pages`.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C8. Idempotency

**Đề xuất:**
- Backend chỉ nhận `chunk_completed` khi `(run_id, chunk_id, attempt_id)` đúng là lần gửi đang chờ, và `result_ref.uri` đúng URI Backend đã cấp. Bản trùng, hoặc kết quả của một lần gửi cũ đã bị thay, thì bỏ qua (có log).
- AI1 giữ cách dedupe `event_id` trong bộ nhớ như hiện nay. Khi chạy nhiều replica, một lệnh gửi lại có thể rơi vào replica khác và bị OCR lần hai. Kết quả vẫn đúng vì Backend bỏ bản trùng, chỉ tốn thêm lượt gọi. Chấp nhận trong pha này.
- Mỗi cụm tải lại cả PDF (tối đa 50 MiB) qua presigned GET: 10 cụm là khoảng 500 MiB trong mạng nội bộ, chấp nhận được. AI1 có thể cache theo `source_sha256` nếu muốn; contract không bắt buộc.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

## C9. Kiểm tra chất lượng trang khi chia cụm

**Hiện trạng:** #47 thêm bước kiểm tra chất lượng trang trước khi gọi OCR. Tài liệu bị từ chối (`AI1_LOW_QUALITY_DOCUMENT`) khi số trang xấu ≥ 3 **và** ≥ 30% số trang phải OCR. Quy tắc này cần nhìn cả tài liệu, còn mỗi lệnh cụm chỉ chứa các trang của một cụm.

**Đã chốt (Q7, AI1 chọn phương án (a) ngày 01/10):** đo cả tài liệu một lần trước khi chia cụm.

- Không chọn cách mỗi cụm tự đo: các cụm đầu đã OCR và trả tiền xong thì cụm sau mới từ chối, và hai cụm của cùng một tài liệu có thể cho kết quả ngược nhau.
- Bước đo chạy cục bộ, không gọi model, khoảng 0,1–0,2 giây/trang ở 150 DPI, tức khoảng 20–40 giây cho 200 trang.

**Lệnh đo (`ai1.ocr.inspect`):** topic `ci.ai1.ocr.commands`, key `document_id`. Chỉ gửi khi tài liệu sẽ được chia cụm; tài liệu tới 20 trang đi một lệnh như hiện nay và tự đo bên trong lệnh đó (như #47).

```json
{
  "task_id": 102938,
  "attempt_id": 1,
  "tenant_id": "tenant_vgr_01",
  "document_id": "doc_01J9X1AB",
  "source_blob_get_url": "http://minio:9000/dossiers/...?X-Amz-...",
  "source_sha256": "a1b2c3...",
  "options": { "dpi": 150, "document_role": "contract", "filename": "hop-dong.pdf" }
}
```

**Kết quả (`ai1.ocr.inspected`, topic `ci.ai1.ocr.results`):**

```json
{
  "job_id": "ai1_def456",
  "document_page_count": 200,
  "ocr_pages": 180,
  "low_quality_pages": { "57": ["speckle"], "133": ["blur", "low_contrast"] },
  "refused": false
}
```

| Trường | Quy tắc |
|---|---|
| `ocr_pages` | Số trang phải OCR (trang scan và trang MIXED), là mẫu số của ngưỡng 30% |
| `low_quality_pages` | Mọi trang xấu của tài liệu kèm lý do, cùng định dạng `error.pages` của #47 |
| `refused` | AI1 quyết định theo quy tắc của #47. Backend không tự tính lại |

- **Bị từ chối:** AI1 trả `ai1.ocr.failed` với `error.code = AI1_LOW_QUALITY_DOCUMENT`, `retryable=false` và `error.pages` (DOC-05d §5), không trả `ai1.ocr.inspected`. Run `failed`, không cụm nào được gửi.
- **Không bị từ chối:** Backend lưu kết quả đo trên run, chia cụm, và đặt `chunk.low_quality_pages` cho từng cụm bằng các trang xấu nằm trong cụm đó (C3).
- **Hạn:** 60 + 0,5 × số trang (giây) từ lúc gửi, tức 160 giây cho 200 trang. Lỗi tạm (`retryable=true`) hoặc quá hạn thì Backend gửi lại một lần với `attempt_id` + 1, như C5.
- **Chạy lại phần lỗi:** run mới mang theo kết quả đo cùng các cụm đã xong, không đo lại. Kết quả đo chỉ phụ thuộc file nguồn (`source_sha256`), nên vẫn đúng.
- **Dùng sau này (chưa làm lần này):** `ai1.ocr.inspected` có thể trả thêm danh sách trang phải OCR, để Backend chỉ chia cụm các trang đó.

- [x] Đức Dũng duyệt  - [x] Chương duyệt  Ghi chú:

---

## Câu hỏi cho AI1

| # | Câu hỏi | Vì sao cần |
|---|---|---|
| Q1 | ~~`ProcessDocument.execute` chạy được trên một tập trang và giữ số trang tuyệt đối không?~~ **Được (K1).** AI1 thêm tham số danh sách trang, `page_number = index + 1` vẫn là số tuyệt đối; khi lệnh có `chunk` thì bỏ `align_pages_to_pdf` và kiểm tra ở `backend_ocr_job.py:283` | Điều kiện của pha 1 |
| Q2 | ~~Kết quả trang có lưu ra JSON rồi đọc lại để dựng snapshot được không?~~ **Được.** `Page` là entity pydantic (`domain/entities.py:109`); giữ tên `ai1.pages.v1` | Điều kiện của pha 2 |
| Q3 | ~~`BuildSnapshot` có cần PDF gốc ở pha 2 không?~~ **Có.** Giữ `source_blob_get_url` trong lệnh assemble (C3) | Giảm tải và thời gian của pha 2 |
| Q4 | ~~`ai1-worker` chạy nhiều replica được không?~~ **Được.** Trạng thái cục bộ chỉ có `_processed`, `_backend_jobs`, `_engine_cache` và thư mục tạm của từng job; bỏ `container_name` là đủ | C4 |
| Q5 | ~~AI1 tách được mã lỗi và `retryable` không?~~ **Được (K3).** Hiện có `AI1_OCR_FAILED`, `AI1_RESULT_UPLOAD_FAILED`, `AI1_LOW_QUALITY_DOCUMENT` (#47, `retryable=false`) | Backend cần biết lỗi nào gửi lại được (C5) |
| Q6 | ~~Cỡ cụm 20 trang và 8 trang cùng lúc có hợp với hạn mức Mistral không?~~ **Chưa có số đo.** Bản online chạy `budget`: khoảng 16 request cùng lúc (32 nếu chuyển `accuracy`); E6 đo 429 rồi chốt (C4) | C2, C4 |
| Q7 | ~~Kiểm tra chất lượng trang của #47 khi chia cụm: đo cả tài liệu trước (a) hay mỗi cụm tự đo (b)?~~ **Đã chốt 01/10: AI1 chọn (a), xem C9.** | Tránh hai cụm của cùng một tài liệu cho kết quả ngược nhau, và tránh OCR (tốn tiền) các cụm đầu rồi mới từ chối ở cụm sau |

## Việc của từng bên

**AI1 (Đức Dũng)**

| # | Mục | Việc |
|---|---|---|
| K1 | C1, C3 | Nhận lệnh có `chunk`: chỉ OCR `pages_to_process`, upload ảnh các trang đó, ghi kết quả trang lên `result_target`, trả `chunk_started` / `chunk_completed` / `chunk_failed`. Lệnh không có `chunk` chạy như hiện nay |
| K2 | C1, C3 | Lệnh `ai1.ocr.assemble`: đọc kết quả các cụm, chạy `mark_duplicate_pages` trên cả tài liệu, dựng `nodes`, `table_continuity` và snapshot, trả `ai1.ocr.completed` / `ai1.ocr.failed` như DOC-05d §5 |
| K3 | C3, C5 | Mã lỗi và `retryable` theo mã |
| K4 | C4 | `ai1-worker` chạy nhiều replica (bỏ `container_name`, `AI1_WORKER_REPLICAS`) |
| K5 | C9 | Lệnh `ai1.ocr.inspect` trả `ai1.ocr.inspected` hoặc `ai1.ocr.failed` (`AI1_LOW_QUALITY_DOCUMENT`); lệnh cụm nhận `chunk.low_quality_pages` và không đo lại |

**Backend (Chương)**

| # | Mục | Việc |
|---|---|---|
| E1 | C2, C3, C4 | Chia lệnh theo cụm, key `chunk_id`, gửi tối đa `AI1_OCR_MAX_CHUNKS_IN_FLIGHT` cụm mỗi run |
| E2 | C1, C8 | Lưu trạng thái từng cụm trên run, nhận kết quả cụm, gửi assemble khi đủ cụm |
| E3 | C5, C6 | Hạn cụm trong watchdog, tự gửi lại cụm lỗi tạm; "chạy lại phần lỗi" theo cụm |
| E4 | C7 | Tiến độ S2 |
| E5 | C4 | Script tạo topic 6 partition; compose cho phép nhiều replica AI1; kiểm tra lúc deploy rằng `ai-service/.env` có `AI1_COST_MODE=budget`; không đặt cứng trong `environment:` của compose vì sẽ đè `.env` (nếu cần mặc định thì dùng `${AI1_COST_MODE:-budget}`) |
| E6 | C4 | Test end-to-end với PDF khoảng 200 trang, khoảng 48 MiB; đo thời gian và số lần 429, chốt `AI1_WORKER_REPLICAS` và `AI1_MAX_PAGES_IN_FLIGHT`; ghi số đo vào DOC-11 |
| E7 | C9 | Gửi `ai1.ocr.inspect` trước khi chia cụm, lưu kết quả trên run (mang sang run mới khi chạy lại phần lỗi), đặt `chunk.low_quality_pages` cho từng cụm |

## Thứ tự triển khai

1. ~~Hai bên duyệt DEC này.~~ Xong 01/10: AI1 trả lời Q1–Q7, DEC sửa theo, hai bên duyệt.
2. AI1 deploy K1–K5. Lệnh không có `chunk` vẫn chạy như cũ, nên Backend cũ không bị ảnh hưởng.
3. Backend deploy E1–E5 và E7 với `AI1_OCR_CHUNK_PAGES=0` (tắt): hành vi chưa đổi.
4. Bật `AI1_OCR_CHUNK_PAGES=20` trên máy test, chạy E6 và ghi số đo.
5. Đặt 20 làm mặc định, chép quy tắc vào DOC-05d §9.

## Lịch sử thay đổi

| Ngày | Thay đổi | Người |
|---|---|---|
| 2026-10-01 | Bản đề xuất đầu tiên | Chương |
| 2026-10-01 | Thêm Q7: kiểm tra chất lượng trang (#47) khi chia cụm | Chương |
| 2026-10-01 | Chốt Q7 theo trả lời của Đức Dũng: phương án (a). Thêm C9 (`ai1.ocr.inspect` / `ai1.ocr.inspected`, `chunk.low_quality_pages`), K5, E7 | Chương |
| 2026-10-01 | Theo trả lời Q1–Q6 của Đức Dũng: C1 chuyển `mark_duplicate_pages` sang pha assemble; C3 lệnh assemble bắt buộc có `source_blob_get_url`; C4 tính trần provider theo số request, compose đặt rõ `AI1_COST_MODE`, E6 chốt số replica. Đánh dấu Q1–Q6 đã trả lời | Chương |
| 2026-10-01 | `accepted`: Đức Dũng approve PR #48 (`04f0def`), đánh dấu ô duyệt C1–C9. Việc chép vào DOC-05d dời về bước 5 của thứ tự triển khai. C4/E5 sửa nguồn của `AI1_COST_MODE` (`ai-service/.env`), chốt bản online chạy `budget` | Chương |
