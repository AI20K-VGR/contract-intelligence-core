# Contract AI1 ↔ AI2

**Trạng thái:** Canonical contract baseline  
**Phiên bản:** 1.0  
**Phạm vi:** Payload OCR/layout evidence do AI1 phát hành để AI2 tiêu thụ

## 1. Phạm vi hiện tại

Contract này chỉ chốt boundary dữ liệu giữa AI1 và AI2:

```text
AI1 phát hành ai1.snapshot.v1 → AI2 nhận và diễn giải snapshot đó
```

Backend hoặc một transport layer có thể chuyển payload giữa hai bên, nhưng transport layer không được làm thay đổi payload. Chi tiết API, job, retry, lưu trữ, body/annex manifest và envelope vận chuyển chưa thuộc contract AI1–AI2 này.

Chưa thuộc phase hiện tại:

- quarantine và vận hành validation phía producer;
- re-OCR và child snapshot;
- accuracy benchmark;
- contract output của AI2;
- publish, review workflow hoặc legal decision.

Không dùng output AI1 cũ, result envelope cũ hoặc tài liệu legacy làm contract mới.

## 2. Authority

| Artefact | Vai trò |
|---|---|
| [ai1.snapshot.v1.schema.json](ai1.snapshot.v1.schema.json) | JSON Schema canonical cho payload AI1 |
| [registry.json](../../packages/contracts/schemas/registry.json) | Registry schema/version machine-readable |
| Tài liệu này | Semantics, ownership và quy tắc AI2 tiêu thụ |

Nếu tài liệu và schema khác nhau về shape, JSON Schema là nguồn quyết định shape. Nếu schema không thể hiện đầy đủ semantics, tài liệu này quyết định semantics của boundary.

## 3. Nguyên tắc bất biến

1. AI1 là owner của OCR/layout evidence trong snapshot.
2. AI2 được phép đọc, lập chỉ mục và dựng model nội bộ; không được sửa snapshot gốc.
3. `raw_text`, line, word, table, bbox, quality, coverage và warning phải được giữ nguyên qua boundary.
4. Thiếu geometry hoặc table structure là trạng thái evidence, không được AI2 tự bịa.
5. `source_digest` định danh nguồn đầu vào của AI1; không được diễn giải thành digest của JSON snapshot.
6. AI2 không tự OCR và không phụ thuộc PDF bytes để hiểu evidence trong contract này.
7. Runtime canonical của AI2 kiểm tra JSON Schema và ràng buộc semantic trước khi xử lý; payload sai shape/identity bị từ chối. Evidence hợp lệ về shape nhưng thiếu chất lượng được xử lý degraded/review. Không sửa payload để vượt validation. Contract processing và manifest được định nghĩa riêng tại `BE-AI2-PROCESSING-CONTRACT.vi.md`.

## 4. Canonical payload: `ai1.snapshot.v1`

Payload root phải khớp [JSON Schema](ai1.snapshot.v1.schema.json):

```json
{
  "schema_version": "ai1.snapshot.v1",
  "snapshot_id": "snap-001",
  "dossier_id": "dossier-001",
  "document_id": "doc-001",
  "run_id": "ocr-run-001",
  "source_digest": "64-hex-sha256-of-source",
  "created_at": "2026-09-22T10:00:00Z",
  "execution": {
    "execution_manifest_id": "exec-001",
    "config_digest": "64-hex-sha256",
    "policy_digest": "64-hex-sha256",
    "source_version_digest": "64-hex-sha256",
    "replay": false
  },
  "producer": {
    "engine_name": "ai1-ocr",
    "engine_version": "1.0.0",
    "model_version": "model-001",
    "preprocess_version": "preprocess-001",
    "code_image_digest": "64-hex-sha256"
  },
  "language": {
    "declared_scope": "vi",
    "detected_profile": "vi",
    "detector": {"name": "language-detector", "version": "1.0.0"}
  },
  "status": "SUCCESS",
  "pages": []
}
```

Không thêm `nodes`, `source_files`, `profile`, AI2 facts, findings hoặc legal conclusion vào snapshot v1. Các dữ liệu đó thuộc model/output của tầng khác.

## 5. Field semantics

### 5.1 Identity và provenance

| Field | Owner | Ý nghĩa |
|---|---|---|
| `snapshot_id` | AI1 | Identity bất biến của lần phát hành snapshot |
| `document_id` | AI1 | Identity document được OCR |
| `run_id` | AI1 | Identity execution/run tạo snapshot |
| `dossier_id` | AI1 | Context dossier mà document thuộc về; không tự suy ra role body/annex |
| `source_digest` | AI1 | SHA-256 của nguồn đầu vào theo quy ước AI1 |
| `created_at` | AI1 | Thời điểm snapshot được phát hành |
| `execution`, `producer`, `language` | AI1 | Provenance để AI2 đánh giá nguồn và khả năng replay |

### 5.2 Page, text và geometry

Mỗi `page` giữ `page_no`, `page_revision_id`, `input_type`, `status`, `raw_text_digest`, `transform`, `quality`, `table_coverage`, `lines`, `tables` và `warnings`.

- `raw_text` là text gốc AI1 bàn giao.
- `line_id` và `word_id` phải ổn định trong page snapshot.
- Word offsets là code-point offsets trong `raw_text`.
- Bbox dùng `[x0, y0, x1, y1]`, chuẩn hóa trong `[0,1]`.
- `geometry_status` phân biệt `measured`, `derived`, `line_only`, `absent`.
- `bbox_source` phải phản ánh nguồn geometry, không được gắn `measured` cho bbox suy diễn.
- AI2 không tự tạo word bbox hoặc gộp bbox qua page.

### 5.3 Quality và degradation

| Trạng thái | Cách AI2 hiểu |
|---|---|
| Page `SUCCESS` + coverage `COMPLETE` | Có thể xử lý bình thường |
| `PARTIAL` hoặc `NEEDS_REVIEW` | Có thể xử lý phần evidence đủ; kết quả phụ thuộc phần lỗi phải được đánh dấu review |
| `BLANK_VERIFIED` | Trang trắng đã được xác minh, không tự coi là OCR failure |
| `FAILED` | Không dùng page làm business evidence |

### 5.4 Table coverage

| `table_coverage.status` | Ý nghĩa |
|---|---|
| `NOT_PRESENT` | AI1 đã kiểm tra và xác nhận không có bảng |
| `DETECTED` | Có tín hiệu bảng và có thể có `tables[]` |
| `UNKNOWN` | Chưa đủ cơ sở kết luận |
| `UNAVAILABLE` | Có tín hiệu bảng nhưng chưa lấy được cấu trúc |
| `FAILED` | Table detection/structure thất bại |

`UNKNOWN`, `UNAVAILABLE` và `FAILED` không có nghĩa là không có bảng. Cell giữ `cell_id`, row/column index, text, `bbox_fragments` và `line_ids` nếu có grounding. Cell rỗng, `-` hoặc `N/A` không được đổi thành số 0.

## 6. Trách nhiệm hai phía

### AI1 phải

- phát payload đúng `ai1.snapshot.v1`;
- giữ raw text, line, word, table và provenance;
- phát quality, table coverage, geometry status và warnings trung thực;
- giữ identity ổn định trong cùng snapshot;
- không đưa AI2 facts, findings hoặc legal conclusion vào payload.

### AI2 phải

- nhận đúng payload `ai1.snapshot.v1`;
- giữ reference về `snapshot_id`, `document_id`, page và line khi tạo dữ liệu nội bộ;
- coi quality/coverage/warning là một phần evidence, không bỏ qua âm thầm;
- phân biệt evidence thiếu với evidence phủ định;
- không sửa raw snapshot và không biến output nội bộ thành thay đổi ngược vào AI1.

## 7. Pass-through và lỗi trong phase hiện tại

Contract hiện tại không yêu cầu một bước validate AI1 → AI2 trước khi AI2 nhận dữ liệu. Tầng vận chuyển chỉ cần chuyển đúng payload và không sửa semantic.

| Tình huống | Quy tắc AI2 |
|---|---|
| Thiếu field hoặc unknown field | Giữ raw payload; xử lý theo khả năng của AI2 và ghi issue ở output AI2 nếu cần |
| Sai hoặc không kiểm chứng được digest | Giữ giá trị gốc; không tự sửa hoặc tự tính lại để thay thế |
| Duplicate ID | Không dùng object mơ hồ; giữ raw input để trace |
| Thiếu geometry | Giữ text/line; không bịa bbox |
| Page `PARTIAL` | Xử lý degraded, không nâng thành complete |
| Page `FAILED` | Không dùng làm business evidence |
| Table coverage `UNKNOWN` | Không kết luận không có bảng |

Quarantine vận hành, digest verification đầy đủ và semantic referential-integrity mở rộng là future phase; schema và semantic validation cơ bản đã là gate hiện tại.

## 8. Những phần để sau

- Transport/API envelope giữa AI1 và AI2.
- Dossier-level grouping, body/annex manifest và role mapping.
- JSON Schema gate và semantic validation tại Backend.
- Snapshot quarantine, automatic rejection và retry policy.
- Re-OCR, child snapshot và lifecycle thay thế snapshot.
- Contract output của AI2: facts, findings, citations, review và publish.

## 9. Fixture và Definition of Done

Fixture phải synthetic, sanitized và chỉ kiểm tra `ai1.snapshot.v1`; không dùng output AI1 cũ làm fixture canonical. Có thể tham khảo:

- [body snapshot example](examples/ai1.snapshot.v1.body.example.json)
- [annex snapshot example](examples/ai1.snapshot.v1.annex.example.json)

Phase contract AI1–AI2 được coi là đủ khi:

- `ai1.snapshot.v1` có schema và đã đăng ký trong registry;
- AI1 và AI2 cùng dùng schema/version này;
- raw evidence và quality status không bị biến đổi qua boundary;
- semantics của geometry, table coverage và degraded page được thống nhất;
- không có dependency bắt buộc vào re-OCR hoặc output cũ; canonical runtime vẫn bắt buộc schema/semantic validation.
