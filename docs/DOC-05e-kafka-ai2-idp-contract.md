# DOC-05e — Kafka contract: Backend ↔ AI2 IDP (MVP body-only)

| Field | Value |
|---|---|
| Status | Active (integration) |
| Owner | Backend Lead / AI2 Lead |
| Companion | [BE-AI2-PROCESSING-CONTRACT.vi.md](contracts/BE-AI2-PROCESSING-CONTRACT.vi.md), [DOC-05d](DOC-05d-kafka-ai1-ocr-contract.md) |

## 1. Goal

Event-driven IDP without HTTP as the **runtime** integration path:

- **Backend worker** publishes IDP commands after AI1 OCR persist (body/CONTRACT only).
- **AI2 worker** consumes commands, runs the IDP pipeline, publishes results.
- **Backend worker** consumes results and advances the dossier to `PENDING_REVIEW`.
- HTTP `POST /jobs/idp` + `GET /jobs/{job_id}` remains for local/manual demos only.

MVP scope: **one** `ai1.snapshot.v1` with dossier member role `body` (CONTRACT document). Annex / full-dossier processing is a later phase.

## 2. Topics and consumer groups

| Topic | Direction | Message key | Consumer group | Retention |
|---|---|---|---|---|
| `ci.ai2.idp.commands` | Backend → AI2 | `dossier_id` | `ci-ai2-idp` | 7d |
| `ci.ai2.idp.results` | AI2 → Backend | `dossier_id` | `ci-backend-ai2-results` | 7d |

AI2 **must not** consume `dossier_events` or `ci.ai1.ocr.results`. Only the Backend orchestrator decides when to trigger IDP and which snapshot to send.

## 3. Shared envelope (`schema_version: ci.kafka.v1`)

Same envelope as DOC-05d:

```json
{
  "schema_version": "ci.kafka.v1",
  "event_id": "evt_01J...",
  "event_type": "ai2.idp.command",
  "occurred_at": "2026-09-24T10:00:00Z",
  "trace_id": "run_...",
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
| `ai2.idp.command` | `ci.ai2.idp.commands` | Backend worker |
| `ai2.idp.completed` | `ci.ai2.idp.results` | AI2 worker |
| `ai2.idp.failed` | `ci.ai2.idp.results` | AI2 worker |

## 4. Command payload (`ai2.idp.command`)

`payload` is the canonical wire body [`be.ai2.processing.request.v1`](contracts/be.ai2.processing.request.v1.schema.json) (MVP body-only):

- `snapshots[]`: exactly **1** `ai1.snapshot.v1`
- `dossier_members[]`: exactly **1** member with `role: "body"`
- `role_relation_map[]`: `MEMBER_OF` only (no `ANNEX_OF` in MVP)
- `policy_flags`: authoritative from Backend
- `service_envelope`: present for schema compatibility; **HMAC verification is not required** on the Kafka path (trust the internal cluster). HTTP demo path still verifies HMAC.

Message size: broker allows **10 MiB**. One body snapshot fits MVP; annex phase may move snapshots to MinIO + URL refs.

## 5. Result payload

### `ai2.idp.completed`

`payload` is [`ai2.be.processing.result.v1`](contracts/ai2.be.processing.result.v1.schema.json) with `status: "SUCCEEDED"` (or terminal success equivalent). Facts/findings must have resolvable citations; AI2 must not invent bbox geometry; `index_contribution.state` remains `propose`.

### `ai2.idp.failed`

```json
{
  "schema_version": "ai2.be.processing.result.v1",
  "request_id": "req_...",
  "idempotency_key": "idem_...",
  "attempt": 1,
  "job_id": "job_...",
  "status": "FAILED",
  "review_state": "BLOCKED",
  "input_snapshots": [],
  "result": null,
  "errors": [
    {
      "code": "AI2_IDP_FAILED",
      "message": "...",
      "retryable": false
    }
  ]
}
```

Minimal fail shape (also accepted by Backend):

```json
{
  "error": {
    "code": "AI2_IDP_FAILED",
    "message": "...",
    "retryable": false
  }
}
```

## 6. Delivery semantics

- AI2 consumer: `enable_auto_commit=false`; commit offset **after** publishing a result (at-least-once).
- Transient errors: do not commit → Kafka redelivery.
- Permanent validation / pipeline failures: publish `ai2.idp.failed`, then commit.
- Backend results consumer: idempotent on `event_id` / `job_id`.
- Backend still advances to `PENDING_REVIEW` on failed IDP so HITL is not stuck on `EXTRACTED`.
- No dedicated DLQ in this phase.

## 7. Flow

1. Client uploads PDF → Backend API `202` → `dossier.uploaded` (DOC-05d).
2. Backend → AI1 OCR → Backend persists snapshot → status `EXTRACTED`.
3. If `AI2_WIRE_ENABLED=true`, Backend publishes `ai2.idp.command` (body-only request) to `ci.ai2.idp.commands`.
4. AI2 worker validates + runs IDP → publishes completed/failed to `ci.ai2.idp.results`.
5. Backend results consumer persists facts/findings and sets `PENDING_REVIEW`.

## 8. Environment variables

| Variable | Default | Used by |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9093` | Backend + AI2 |
| `KAFKA_AI2_IDP_COMMANDS_TOPIC` | `ci.ai2.idp.commands` | Backend + AI2 |
| `KAFKA_AI2_IDP_RESULTS_TOPIC` | `ci.ai2.idp.results` | Backend + AI2 |
| `KAFKA_AI2_IDP_GROUP_ID` | `ci-ai2-idp` | AI2 worker |
| `KAFKA_BACKEND_AI2_RESULTS_GROUP_ID` | `ci-backend-ai2-results` | Backend worker |
| `AI2_WIRE_ENABLED` | `false` | Backend (gate publish after OCR) |
| `AI2_CONTRACT_ROOT` | `docs/contracts` | AI2 schema validation |

## 9. Ownership

| Party | Owns |
|---|---|
| Backend | Snapshot selection (body), request build, command publish, result consume, persist, HITL, retry policy |
| AI2 | Kafka worker, schema/semantic validate, IDP pipeline, result publish; must not mutate snapshots or re-OCR |
| AI1 | OCR only; unaware of AI2 |

## 10. Out of scope (MVP)

- Full dossier body + annex on Kafka
- AI2 consuming AI1 result topics directly
- Changing wire JSON Schemas (transport only: HTTP → Kafka)
- Product frontend upload UI
