# DOC-05d — Kafka contract: Backend ↔ AI1 OCR

| Field | Value |
|---|---|
| Status | Active (integration) |
| Owner | Backend Lead / AI1 Lead |
| Companion | [DOC-05c](DOC-05c-backend-ai-service-contract.md) (HTTP job shapes reused as Kafka payloads) |

## 1. Goal

Event-driven OCR without HTTP as the runtime integration path:

- **Backend FastAPI** produces OCR commands and consumes OCR results.
- **AI1** consumes commands, runs the existing OCR pipeline (`_run_backend_ocr`), and produces results.
- HTTP `POST /api/v1/jobs/ocr` remains for local/manual demos only.

## 2. Topics and consumer groups

| Topic | Direction | Message key | Consumer group | Retention |
|---|---|---|---|---|
| `dossier_events` | Backend internal | `dossier_id` | `ci-backend-orchestrator` | 7d |
| `ci.ai1.ocr.commands` | Backend → AI1 | `document_id` | `ci-ai1-ocr` | 7d |
| `ci.ai1.ocr.results` | AI1 → Backend | `document_id` | `ci-backend-ai1-results` | 7d |

AI1 **must not** consume `dossier_events`. Only the backend orchestrator builds
presigned URLs and DOC-05c fields.

## 3. Shared envelope (`schema_version: ci.kafka.v1`)

```json
{
  "schema_version": "ci.kafka.v1",
  "event_id": "evt_01J...",
  "event_type": "ai1.ocr.command",
  "occurred_at": "2026-09-23T03:00:00Z",
  "trace_id": "4bf92f35...",
  "tenant_id": "tenant_vgr_01",
  "correlation": {
    "dossier_id": "dos_...",
    "document_id": "doc_...",
    "task_id": 102938,
    "attempt_id": 1,
    "run_id": "run_..."
  },
  "payload": {}
}
```

| Field | Rules |
|---|---|
| `event_id` | ULID; idempotency key (dedupe within a short TTL) |
| `correlation` | Echoed unchanged from command → result |
| Kafka headers (recommended) | `ce_type`, `tenant_id`, `trace_id` |

### Event types

| `event_type` | Topic | Producer |
|---|---|---|
| `ai1.ocr.command` | `ci.ai1.ocr.commands` | Backend orchestrator |
| `ai1.ocr.completed` | `ci.ai1.ocr.results` | AI1 worker |
| `ai1.ocr.failed` | `ci.ai1.ocr.results` | AI1 worker |

## 4. Command payload (`ai1.ocr.command`)

Identical to DOC-05c §4.1 / `OcrJobRequest` / AI1 `BackendOcrJobRequest`:

```json
{
  "task_id": 102938,
  "attempt_id": 1,
  "tenant_id": "tenant_vgr_01",
  "document_id": "doc_01J9X1AB",
  "source_blob_get_url": "http://minio:9000/dossiers/...?X-Amz-...",
  "source_sha256": "a1b2c3...",
  "pages_to_process": [1, 2, 3],
  "render_target": {
    "dpi": 150,
    "format": "PNG",
    "presigned_put_urls": {
      "1": "http://minio:9000/ci-render/...?X-Amz-..."
    }
  },
  "options": {
    "engine": "pymupdf",
    "dpi": 150,
    "language": "vi",
    "document_role": "contract",
    "filename": "hop-dong.pdf"
  }
}
```

`source_blob_get_url` must be reachable from the AI1 worker network namespace
(use the MinIO Docker DNS name in compose: `http://minio:9000`).

## 5. Result payload

### `ai1.ocr.completed`

Matches the in-memory AI1 job record shape (pollable HTTP job status):

```json
{
  "job_id": "ai1_abc123",
  "kind": "ocr",
  "status": "completed",
  "progress_pct": 100,
  "current_stage": "completed",
  "created_at": "...",
  "updated_at": "...",
  "finished_at": "...",
  "result": {
    "schema_version": "ai1.snapshot.v1",
    "snapshot": {}
  },
  "error": null,
  "usage": {
    "engine": "pymupdf",
    "pages": 3
  }
}
```

Backend: `adapt_ai1_snapshot_result(payload["result"])` → `persist_ai1_snapshot`.

### Large results: upload to MinIO, send a reference (DOC-11 §2)

An inline result costs ~71 KiB per page, so past ~144 pages the message
exceeds the 10 MiB Kafka limit. Every command now carries an upload target in
`options` (an open dict, so the current `BackendOcrJobRequest` accepts it):

```json
"options": {
  "result_target": {
    "put_url": "http://minio:9000/ci-render/doc_01J9X1AB/ai1-result/run_01….json?X-Amz-…",
    "uri": "s3://ci-render/doc_01J9X1AB/ai1-result/run_01….json",
    "content_type": "application/json"
  }
}
```

**AI1 side (implemented, `kafka_worker._deliver_result`):** when `options.result_target` is present:

1. PUT the same JSON that would go in `payload.result` to `put_url` with
   `Content-Type: application/json`.
2. Publish `ai1.ocr.completed` with `result: null` and:

```json
"result_ref": {
  "uri": "s3://ci-render/doc_01J9X1AB/ai1-result/run_01….json",
  "sha256": "<hex of the uploaded bytes>",
  "bytes": 14312345
}
```

AI1 may keep inlining small results. The backend accepts either form.

AI1 uploads every completed result when a target is present, as UTF-8 JSON;
`sha256` and `bytes` describe exactly the uploaded body. Without a target it
inlines as before. If the upload fails, a result that still fits a Kafka
message (10 MiB less 64 KiB for the envelope) is inlined; a larger one is
published as `ai1.ocr.failed` with `error.code = AI1_RESULT_UPLOAD_FAILED`.
Kafka envelopes are published as UTF-8 JSON (no `\uXXXX` escapes).

**Backend checks (implemented):**

- It reads only the exact `uri` it issued for that run and document. Any
  other `uri` fails the run with `AI1_RESULT_UNREADABLE` and nothing is read.
- The object must be at most `AI1_RESULT_MAX_BYTES` (256 MiB), match `sha256`
  when AI1 sends one, and be a JSON object.
- A missing object fails the run (`AI1_RESULT_UNREADABLE`). A transient
  MinIO error is retried like any other handler error, without failing the run.
- The PUT URL lives as long as the other presigned URLs (the AI1 deadline +
  10 min).
- Dossier purge deletes `{document}/ai1-result/{run}.json` for every run.

### `ai1.ocr.failed`

```json
{
  "job_id": "ai1_abc123",
  "kind": "ocr",
  "status": "failed",
  "progress_pct": 100,
  "current_stage": "failed",
  "result": null,
  "error": {
    "code": "AI1_OCR_FAILED",
    "message": "..."
  }
}
```

`error.code = AI1_LOW_QUALITY_DOCUMENT`: AI1 refused the document before any
OCR call, because at least 3 of the pages it would OCR, and at least 30% of
them, are too poor to read (blur, low contrast, grain noise or speckle,
measured locally). A text-layer contract with one poor scanned page (say the
signed page) is therefore still read. No OCR was paid
for and a retry gives the same answer; the user should rescan. `error.pages`
maps each such page number to its reasons:

```json
"error": {
  "code": "AI1_LOW_QUALITY_DOCUMENT",
  "message": "4 of 6 scanned pages are too poor to read (p1:speckle, ...); rescan the document",
  "pages": {"1": ["speckle"], "2": ["blur", "low_contrast"]}
}
```

Otherwise the document is OCR'd; each poor page is read once only and
carries the page warning `low_quality_scan:<reasons>` in the snapshot.

## 6. Delivery semantics

- AI1 consumer: `enable_auto_commit=false`; commit offset **after** publishing a result (at-least-once).
- Transient errors (MinIO timeout): do not commit → Kafka redelivery.
- Permanent OCR failures: publish `ai1.ocr.failed`, then commit.
- Backend results consumer: idempotent on `(document_id, task_id, attempt_id)` / `job_id`.
- AI1: no dedicated DLQ in this phase; failed events + logs are enough for integration tests.
- Message size: broker + AI1 producer allow **10 MiB** (`message.max.bytes` /
  `max_request_size=10485760`). Backend results consumer uses matching
  `max_partition_fetch_bytes` / `fetch_max_bytes` (`KAFKA_MAX_MESSAGE_BYTES`).
  Measured OCR snapshot size is **~71 KiB per page** (202 pages → 14.3 MB), so an
  inline result fits only up to **~144 pages**. Larger dossiers fail with
  `MessageSizeTooLargeError` on the AI1 side until OCR results move to MinIO and
  Kafka carries only a URI (DOC-11 §2, §4.2 #2).
- Backend dead-letter topics (`<topic>.dlq`) copy a record's value only up to
  `KAFKA_DEAD_LETTER_MAX_VALUE_BYTES` (256 KiB); a larger record is parked as
  source topic/partition/offset + `value_bytes` + `value_sha256`.

## 7. Environment variables

| Variable | Default | Used by |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9093` | Backend + AI1 |
| `KAFKA_AI1_OCR_COMMANDS_TOPIC` | `ci.ai1.ocr.commands` | Backend + AI1 |
| `KAFKA_AI1_OCR_RESULTS_TOPIC` | `ci.ai1.ocr.results` | Backend + AI1 |
| `KAFKA_AI1_OCR_GROUP_ID` | `ci-ai1-ocr` | AI1 |
| `KAFKA_BACKEND_AI1_RESULTS_GROUP_ID` | `ci-backend-ai1-results` | Backend |

## 8. Flow

1. API uploads PDF → MinIO → publishes `dossier.uploaded` on `dossier_events`.
2. Backend orchestrator marks job PROCESSING, builds DOC-05c command, publishes to `ci.ai1.ocr.commands`.
3. AI1 worker runs existing OCR, publishes completed/failed to `ci.ai1.ocr.results`.
4. Backend results consumer adapts snapshot and persists; updates job/dossier status.
