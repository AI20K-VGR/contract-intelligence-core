# AI1 → AI2 OCR Snapshot Handoff v2.0

**Trạng thái:** Proposed contract — cần AI1, AI2, Backend và Frontend xác nhận trước khi code cứng.
**Thay thế:** [AI1-OCR-SNAPSHOT-HANDOFF.md](AI1-OCR-SNAPSHOT-HANDOFF.md) khi v2 được accept.
**Mục tiêu:** Một AI2 finding phải truy ngược được từ fact về `snapshot → document → page → line/word → Unicode span → bbox → page render → source digest`.

Từ khóa **MUST**, **MUST NOT**, **SHOULD**, **MAY** mang nghĩa bắt buộc, cấm, nên có và tùy chọn. Bản này là contract bàn giao OCR/layout/provenance; AI1 không phát hiện xung đột hay quyết định pháp lý.

## 1. Điều kiện bàn giao và đơn vị package

Một package tối thiểu MUST có một dossier gồm **một contract và một annex**. Nếu không có đủ cặp, package có thể bàn giao để test OCR nhưng MUST có `package_status: "incomplete_dossier"` và AI2 MUST NOT chạy comparison contract–annex trên package đó.

```text
<package-root>/
  dossier_manifest.json
  snapshots/<snapshot_id>.json                 # một file / document snapshot
  renders/<snapshot_id>/page-001.png           # access-controlled, không commit PII
  source/<document_id>.pdf                     # access-controlled, không commit PII
  audit/run-metadata.json                       # optional, không thay snapshot
```

AI1 MUST cung cấp URI truy cập PDF/render cho AI2 audit. URI có thể là `storage://` hoặc signed HTTPS URI; repository chỉ giữ metadata hoặc fixture synthetic không chứa PII.

## 2. Versioning, encoding và quy ước chung

- `schema_version` MUST bằng `ai1.snapshot.v1` cho v1. Sửa field bắt buộc, enum hoặc semantics tạo version major mới.
- JSON MUST là UTF-8. Text MUST giữ nguyên raw OCR text; không Unicode-normalize, trim, sửa dấu, thay line break hoặc format số trước khi tính offset.
- Các offset MUST là **Unicode code point**, 0-based, end-exclusive. JavaScript consumer MUST dùng `Array.from(text).slice(start, end)`.
- `source_digest` MUST là SHA-256 của bytes PDF nguồn, dạng `sha256:` + 64 hex lowercase.
- ID MUST duy nhất trong snapshot/package. Re-OCR MUST sinh `snapshot_id` mới; snapshot cũ và evidence cũ MUST tiếp tục truy vấn được.
- `null` chỉ dùng khi field cho phép nullable; array không có phần tử MUST là `[]`, không bỏ field bắt buộc.

## 3. Dossier manifest bắt buộc

File `dossier_manifest.json` MUST validate theo shape sau:

```json
{
  "schema_version": "ai1.dossier-manifest.v1",
  "dossier_id": "dossier-20260916-001",
  "package_status": "complete",
  "created_at": "2026-09-16T09:00:00+07:00",
  "documents": [
    {
      "document_id": "contract-001",
      "document_role": "contract",
      "snapshot_id": "ocr-20260916-001-contract",
      "source_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef"
    },
    {
      "document_id": "annex-001",
      "document_role": "annex",
      "snapshot_id": "ocr-20260916-001-annex",
      "source_digest": "sha256:abcdef0123456789abcdef0123456789abcdef0123456789abcdef0123456789"
    }
  ],
  "relationships": [
    {
      "relationship_type": "annex_to_contract",
      "from_document_id": "annex-001",
      "to_document_id": "contract-001",
      "declared_by": "intake",
      "evidence_status": "declared"
    }
  ]
}
```

### 3.1 Required fields và enum

| Field | Rule |
|---|---|
| `dossier_id` | Non-empty, immutable for one intake dossier. |
| `package_status` | `complete` / `incomplete_dossier` / `invalid`. |
| `documents` | `complete` MUST có ít nhất một `contract` và một `annex`. |
| `document_role` | `contract` / `annex` / `amendment` / `other`; role do intake/BE/leader xác nhận, không suy từ filename. |
| `relationships` | Annex/amendment dùng cho comparison MUST liên kết tới contract cụ thể. AI2 không được suy diễn quan hệ chỉ từ tên file. |
| `snapshot_id`, `source_digest` | MUST khớp chính xác snapshot document tương ứng. |

## 4. Document snapshot bắt buộc

Mỗi document có đúng một file snapshot cho một lần OCR:

```json
{
  "schema_version": "ai1.snapshot.v1",
  "snapshot_id": "ocr-20260916-001-contract",
  "dossier_id": "dossier-20260916-001",
  "document_id": "contract-001",
  "filename": "hop-dong.pdf",
  "document_role": "contract",
  "source_digest": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
  "input_type": "SCANNED_OCR",
  "engine": { "name": "paddle_ocr", "version": "3.1.0" },
  "processing_started_at": "2026-09-16T09:00:00+07:00",
  "processing_ms": 220,
  "page_count": 1,
  "pages": []
}
```

| Field | Required | Rule |
|---|---:|---|
| `schema_version`, `snapshot_id`, `dossier_id`, `document_id`, `filename` | Yes | String, non-empty. |
| `document_role` | Yes | MUST equal manifest role. |
| `source_digest` | Yes for real source | `null` only when `example_only: true` and `source_digest_reason` is non-empty. |
| `input_type` | Yes | `TEXT_LAYER` / `SCANNED_OCR` / `MIXED`. A page may differ only if envelope is `MIXED`. `SCANNED` is invalid. |
| `engine` | Yes | `name` and `version` non-empty. A page MAY add an engine override only when it differs. |
| `processing_started_at`, `processing_ms` | Yes | ISO-8601 with timezone; non-negative number of milliseconds. |
| `page_count`, `pages` | Yes | `page_count === pages.length`; page numbers unique and 1-based. |
| `example_only` | No | `true` only for explicitly synthetic fixture; these outputs MUST NOT be counted as production audit evidence. |

## 5. Page contract và geometry

Mỗi page MUST have:

```json
{
  "page_number": 1,
  "status": "SUCCESS",
  "input_type": "SCANNED_OCR",
  "source_page_width": 595.0,
  "source_page_height": 842.0,
  "rotation_degrees": 0,
  "page_image_ref": {
    "uri": "storage://ocr/ocr-20260916-001-contract/page-001.png",
    "sha256": "sha256:0123456789abcdef0123456789abcdef0123456789abcdef0123456789abcdef",
    "width_px": 1785,
    "height_px": 2526
  },
  "text": "Điều 1. ...",
  "lines": [],
  "words": [],
  "blocks": [],
  "tables": [],
  "warnings": [],
  "error": null
}
```

### 5.1 Page status, warning và error

| Status | Điều kiện | AI2 xử lý |
|---|---|---|
| `SUCCESS` | Text và geometry cần thiết cho content đó đầy đủ. | Có thể bind citation. |
| `PARTIAL` | Có text nhưng thiếu geometry, confidence thấp, hoặc OCR chỉ đọc một phần. | AI2 chỉ tạo fact `insufficient_evidence` nếu citation đầy đủ không thể tạo. |
| `FAILED` | Không tạo được OCR page. | Không suy đoán text/fact; lưu error. |

`warnings[]` là array object `{ "code", "message", "affected_line_ids" }`. `error` là `null` hoặc `{ "code", "message", "retryable" }`.

Minimum warning codes: `blank_page`, `missing_line_geometry`, `missing_word_geometry`, `low_confidence_lines`, `render_unavailable`, `table_structure_unavailable`. Một page có `geometry_available=false` MUST là `PARTIAL`, không được báo `SUCCESS` thuần text.

### 5.2 Bbox và frame

- `bbox_normalized` MUST là `[x0, y0, x1, y1]`, với `0 ≤ x0 < x1 ≤ 1` và `0 ≤ y0 < y1 ≤ 1`.
- Origin là góc trên-trái của **upright rendered page** sau khi áp dụng `rotation_degrees` đúng một lần.
- Bbox MUST được chuẩn hóa theo `page_image_ref.width_px/height_px`. UI nhân bbox với chính kích thước image render này; không dùng trực tiếp kích thước PDF source nếu frame khác.
- `rotation_degrees` MUST là `0`, `90`, `180` hoặc `270`; document/page có xoay MUST vẫn trả bbox trên upright frame.
- Nếu không có PDF/render URI hoặc digest ảnh, `render_unavailable` MUST được ghi và page không thể pass overlay audit.

### 5.3 Lines, words và offset

```json
{
  "line_id": "contract-001:s1:p001:l001",
  "text": "Điều 1. Giá trị hợp đồng",
  "page_char_start": 0,
  "page_char_end": 25,
  "bbox_normalized": [0.10, 0.20, 0.62, 0.23],
  "word_ids": ["contract-001:s1:p001:w0001"]
}
```

```json
{
  "word_id": "contract-001:s1:p001:w0001",
  "line_id": "contract-001:s1:p001:l001",
  "text": "Điều",
  "line_char_start": 0,
  "line_char_end": 4,
  "bbox_normalized": [0.10, 0.20, 0.17, 0.23],
  "confidence": 0.98
}
```

Invariants:

1. `line_id` và `word_id` unique trong snapshot; every `word.line_id` and `line.word_ids[]` MUST resolve mutually.
2. `page_char_start/end` MUST select exactly `line.text` from `page.text`; `line_char_start/end` MUST select exactly `word.text` from `line.text`.
3. `confidence` is `null` when engine does not provide it; otherwise number in `[0,1]`. AI1 MUST NOT invent confidence.
4. `lines[]`/`words[]` MAY be empty only with a warning and `PARTIAL`/`FAILED`. Raw text alone is not geometry evidence.

## 6. Blocks, clauses và tables

`blocks[]` SHOULD be emitted where available. Each block MUST have `block_id`, `block_type` (`heading`/`paragraph`/`table`), `line_ids`, `reading_order`, `bbox_normalized`. AI2 MAY construct temporary clause regions from line bboxes, but MUST mark the derived region `origin: "ai2_derived"`.

`tables[]` MUST NOT be represented solely by text blob when table structure is available. A table has `table_id`, `bbox_normalized`, `rows[]`; each row has `row_id`, `row_index`, `cells[]`; each cell has `cell_id`, `column_index`, `row_span`, `column_span`, `text`, `bbox_normalized`. If structure is unavailable, return `tables: []` plus warning `table_structure_unavailable`; do not invent cells.

## 7. URI, security và retention

- `page_image_ref.uri` and source PDF URI MUST be accessible to authorized AI2/FE reviewers until the audit decision is recorded.
- URI MUST identify exact immutable content by digest. Access token/query-string MUST NOT be stored in Git.
- The package MUST state `data_classification` (`synthetic` / `internal` / `restricted`) and `retention_until` in manifest.
- AI2 logs citations and IDs, not raw PDF or unnecessary PII.

## 8. Validation before handoff

AI1 MUST ship `ai1.snapshot.v1.schema.json` and `ai1.dossier-manifest.v1.schema.json`, generated or maintained with the implementation. Before delivery AI1 MUST run and report:

1. JSON Schema validation of every manifest/snapshot.
2. Referential integrity: manifest → snapshot → page → line → word.
3. Offset round-trip using Unicode code points, including `A😀B` and combining accents.
4. Bbox range and upright-frame validation.
5. Digest match of PDF and page render file.
6. At least one text-layer and one scanned page with the same snapshot shape.
7. Re-OCR test: old snapshot bytes remain unchanged and new `snapshot_id` is generated.

## 9. AI2 acceptance and ST-020 audit

AI2 only marks a run auditable when every selected evidence side has source PDF/render, digest, snapshot ID, page/line/span and bbox. The audit record MUST contain `audit_run_id`, snapshot IDs, schema version, engine/version, auditor, timestamp, selected case/side and pass/fail evidence URI.

| Gate | Pass condition |
|---|---|
| Source provenance | PDF/render is reachable and digest matches snapshot. |
| Metadata | All required envelope/document/page fields validate. |
| Geometry | Selected line/word bbox exists, is in range and uses upright rendered frame. |
| Span | Unicode offset selects the exact raw text value. |
| Overlay | Highlight aligns with the selected source text on render. |
| Cross-document | Contract and related annex have manifest relationship and independent citations. |

One failed citation MUST be logged as `fail` for that binding, not erased. Missing source/geometry makes that binding `unverifiable`; it MUST NOT be reported as `pass`. A synthetic fixture can validate integration but MUST NOT be reported as real OCR quality evidence.

## 10. Compatibility decision for existing outputs

The file `690758295-Scan-HỢP-ĐỒNG-Feddy.ocr.json` is a legacy OCR result, **not** `ai1.snapshot.v1`: it lacks envelope provenance, `lines[]`, `words[]`, bbox, render reference and uses `SCANNED` instead of `SCANNED_OCR`. AI1 MUST either regenerate it in v1 shape or wrap/rebuild it from source PDF; AI2 MUST NOT fabricate missing geometry.

## 11. Sign-off

| Role | Decision required |
|---|---|
| AI1 | Can emit v1 snapshots, schema, render URI and required warnings. |
| AI2 | Confirms fact/citation binding, fallback to `insufficient_evidence`, and audit gates. |
| Backend | Confirms URI authorization, storage lifecycle, manifest persistence and immutable IDs. |
| Frontend | Confirms coordinate transform and overlay behavior on the rendered page frame. |
| Leader | Accepts scope, risk and readiness criteria for ST-020. |
