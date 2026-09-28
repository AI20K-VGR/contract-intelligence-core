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

## 6. Delivery semantics

- AI1 consumer: `enable_auto_commit=false`; commit offset **after** publishing a result (at-least-once).
- Transient errors (MinIO timeout): do not commit → Kafka redelivery.
- Permanent OCR failures: publish `ai1.ocr.failed`, then commit.
- Backend results consumer: idempotent on `(document_id, task_id, attempt_id)` / `job_id`.
- No dedicated DLQ in this phase; failed events + logs are enough for integration tests.
- Message size: broker + AI1 producer allow **10 MiB** (`message.max.bytes` /
  `max_request_size=10485760`) so OCR snapshot results (~1.6MB+) fit. Backend
  results consumer uses matching `max_partition_fetch_bytes` / `fetch_max_bytes`.

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
