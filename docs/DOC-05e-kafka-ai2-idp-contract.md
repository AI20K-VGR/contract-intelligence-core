# DOC-05e — Kafka contract: Backend ↔ AI2 IDP

| Field | Value |
|---|---|
| Status | **Accepted direction, not yet running** — decided 2026-09-30: Backend ↔ AI2 processing moves to event-driven Kafka. **Runtime today is still HTTP** submit + poll (`docker-compose.yml`, no AI2 worker service, no Backend AI2 consumer). This contract becomes the runtime path after §12 step 3 is green and `AI2_TRANSPORT` defaults to `kafka`. Rules in §4–§9 are proposed by Backend and need AI2 sign-off (§13). |
| Version | 2 (replaces the MVP body-only draft, which was never wired on the Backend side) |
| Owner | Backend Lead / AI2 Lead |
| Companion | [BE-AI2-PROCESSING-CONTRACT.vi.md](contracts/BE-AI2-PROCESSING-CONTRACT.vi.md) (payload rules), [DOC-05d](DOC-05d-kafka-ai1-ocr-contract.md) (same envelope and by-reference pattern), backend plan [`plans/260930-be-ai2-kafka/plan.md`](../plans/260930-be-ai2-kafka/plan.md) |

## 1. Goal and scope

- **Backend worker** publishes one IDP command per `(run, attempt)` once every document of the run has an AI1 snapshot and the manifest is confirmed.
- **AI2 worker** consumes commands, runs IDP on the **full dossier**, publishes `started` then `completed` / `failed`.
- **Backend worker** consumes results, persists facts/findings as proposals and moves the dossier to `PENDING_REVIEW` (or fails the run).

Changes from HTTP submit + poll:

| Topic | HTTP (Sprint 2) | Kafka (this contract) |
|---|---|---|
| Submit | `POST /jobs/idp` | `ai2.idp.command` on `ci.ai2.idp.commands` |
| Progress / result | Backend polls `GET /jobs/{job_id}` | AI2 pushes `ai2.idp.started`, `ai2.idp.completed`, `ai2.idp.failed` |
| Timeout | Poll deadline inside the worker task | Backend watchdog on the run (§8) |
| Large payloads | Whole request in the HTTP body | Request and result go through MinIO by reference above a size threshold (§6) |

**Unchanged:**

- Wire payload schemas `be.ai2.processing.request.v1` and `ai2.be.processing.result.v1`. Everything Kafka-specific lives in the envelope, not in the payload.
- `/query` stays **synchronous HTTP** (a user is waiting, 20 s budget). Kafka is only for dossier processing.
- `POST /jobs/idp` + `GET /jobs/{job_id}` stay in AI2 for local/manual demos and as the Backend fallback while `AI2_TRANSPORT=http` (§12).

## 2. Topics and consumer groups

| Topic | Direction | Message key | Consumer group | Partitions | Retention |
|---|---|---|---|---|---|
| `ci.ai2.idp.commands` | Backend → AI2 | `dossier_id` | `ci-ai2-idp` | 3 | 7d |
| `ci.ai2.idp.results` | AI2 → Backend | `dossier_id` | `ci-backend-ai2-results` | 3 | 7d |
| `ci.ai2.idp.commands.dlq` | AI2 internal | `dossier_id` | — (operator) | 1 | 14d |
| `ci.ai2.idp.results.dlq` | Backend internal | `dossier_id` | — (operator) | 1 | 14d |

- Keying by `dossier_id` keeps `started` before `completed` for one dossier and lets several AI2 workers share the load (at most one worker per partition).
- Topics are created explicitly (compose init / deploy script) with the partition counts above; broker auto-create gives one partition only.
- AI2 **must not** consume `dossier_events` or `ci.ai1.ocr.*`. Only the Backend decides when to run IDP and which snapshots to send.

## 3. Envelope (`schema_version: ci.kafka.v1`)

Same envelope as DOC-05d, plus the AI2-specific fields marked *(AI2)*.

```json
{
  "schema_version": "ci.kafka.v1",
  "event_id": "01J9ZK3Q7T5W8M2N4P6R8S0V1X",
  "event_type": "ai2.idp.command",
  "occurred_at": "2026-10-06T03:00:00Z",
  "trace_id": "4bf92f3577b34da6a3ce929d0e0e4736",
  "tenant_id": "tenant_vgr_01",
  "correlation": {
    "dossier_id": "dos_01J9X1AB",
    "run_id": "run_01J9X1CD",
    "attempt": 1,
    "request_id": "run_01J9X1CD:ai2",
    "idempotency_key": "run_01J9X1CD:ai2"
  },
  "causation_id": null,
  "payload": {},
  "payload_ref": null,
  "result_target": {}
}
```

| Field | Rules |
|---|---|
| `event_id` | ULID, unique per published event. A result has its **own** `event_id`; it never reuses the command's. Consumers dedupe on it. |
| `causation_id` *(AI2)* | `null` on a command. On `started` / `completed` / `failed`: the `event_id` of the command that caused it. |
| `correlation` | Built by Backend, echoed **unchanged** by AI2 on every result. `attempt`, `request_id` and `idempotency_key` equal the same fields in the payload. |
| `payload` / `payload_ref` | Exactly one is non-null (§6). |
| `result_target` *(AI2)* | Command only. Where AI2 uploads a large result (§6). |
| Kafka headers | `ce_type` = `event_type`, `tenant_id`, `trace_id` (recommended, not relied on). |
| Encoding | UTF-8 JSON, no `\uXXXX` escapes (`ensure_ascii=False`). |

### Event types

| `event_type` | Topic | Producer | Payload |
|---|---|---|---|
| `ai2.idp.command` | `ci.ai2.idp.commands` | Backend worker | `be.ai2.processing.request.v1` |
| `ai2.idp.started` | `ci.ai2.idp.results` | AI2 worker | `{job_id, started_at}` (§5.1) |
| `ai2.idp.completed` | `ci.ai2.idp.results` | AI2 worker | `ai2.be.processing.result.v1`, `status: SUCCEEDED` |
| `ai2.idp.failed` | `ci.ai2.idp.results` | AI2 worker | `ai2.be.processing.result.v1`, `status: FAILED` |

## 4. Command (`ai2.idp.command`)

`payload` is the canonical [`be.ai2.processing.request.v1`](contracts/be.ai2.processing.request.v1.schema.json), built the same way as for HTTP today (`canonical_processing.build_processing_request`):

- `snapshots[]`: **every** selected `ai1.snapshot.v1` of the dossier (body and annexes). The MVP body-only limit of the previous draft is dropped; AI2 must accept N members.
- `dossier_members[]`: exactly one `role: "body"`; the others `annex`. Backend refuses to dispatch a dossier with zero or several bodies.
- `role_relation_map[]`: relations stored by Backend (`ANNEX_OF`, `MEMBER_OF`). AI2 does not infer or change them.
- `policy_flags`: authoritative from Backend (egress, vector, budget). `budget_limits.max_processing_seconds` is also the base of the Backend deadline (§8).
- `idempotency_key` = `<run_id>:ai2`, fixed for the run. `attempt` starts at 1 and is bumped by every Backend retry.
- `service_envelope`: Backend signs it exactly as for HTTP (`ai2.service-envelope.v1`, scope `ai2.jobs.submit`).

### Service envelope on Kafka

| Check | AI2 on Kafka |
|---|---|
| `signature` (HMAC-SHA256, same secret as HTTP) | **Must** verify |
| `payload_sha256` over the payload without `service_envelope` | **Must** verify (after downloading `payload_ref`, if used) |
| `audience`, `tenant_id`, `dossier_id` match envelope / correlation | **Must** verify |
| `expires_at`, `nonce` replay | **Must not** enforce. A command can wait in the topic or be redelivered after a restart well past 300 s. Replay protection is the `(idempotency_key, attempt)` dedupe in §7. |

A command that fails these checks → `ai2.idp.failed` with `AI2_ENVELOPE_INVALID`, `retryable: false`.

This replaces the v1 rule "no HMAC on Kafka, trust the internal cluster". The HMAC is kept because the broker has no authentication in this phase (below), so any process on the Docker network can publish to `ci.ai2.idp.commands`.

### Security decisions (deliberate, reviewed by AI2 in §13)

| Topic | Decision | Accepted risk / compensating control |
|---|---|---|
| Broker connection | PLAINTEXT listener on the internal Docker network only. `deploy/compose.prod.yml` publishes no Kafka port and only Caddy is reachable from outside. No TLS or SASL in this phase. | Anyone who gets a shell on the host or a container can read and write every topic. The signed envelope stops forged commands; results from AI2 are not signed and are trusted on this network. |
| Topic ACLs | None in this phase. | Same as above. SASL + per-service ACLs (Backend produces commands, AI2 produces results) are the first step if the broker ever leaves the single host. |
| HMAC key | One `AI2_SERVICE_HMAC_SECRET` per environment, shared by Backend API, Backend worker and AI2 (HTTP and worker). `deploy/bootstrap.sh` generates it; it is never committed. Both sides fail closed when it is empty; with PR #38 the backend also refuses to start in staging/prod on an empty or placeholder value. `key_id` in the envelope is `default` today and is the hook for rotation (accept old and new id during a switch). | Rotation is manual: set the new secret on all three services and restart them together. |
| `expires_at` / `nonce` not enforced on Kafka | A command may legitimately sit in the topic or be redelivered long after the 300 s envelope lifetime, so expiry checks would reject valid work. | A replayed command cannot do new work: AI2 dedupes on `(idempotency_key, attempt)` and answers with the stored result; Backend applies a result only to the current run and attempt (§7). HTTP keeps both checks. |

## 5. Results

### 5.1 `ai2.idp.started`

Published once AI2 has validated the command and is about to run the pipeline. Backend uses it to split queue time from processing time (§8).

```json
"payload": { "job_id": "job_4f1c...", "started_at": "2026-10-06T03:00:05Z" }
```

A redelivered command that AI2 already finished does **not** publish `started` again; it republishes the stored terminal result (§7).

### 5.2 `ai2.idp.completed`

`payload` (or the object behind `result_ref`) is [`ai2.be.processing.result.v1`](contracts/ai2.be.processing.result.v1.schema.json) with `status: "SUCCEEDED"`. All rules of BE-AI2-PROCESSING-CONTRACT §4 apply: `input_snapshots[]` equals the sent identities, every citation id resolves, no invented bbox, `index_contribution.state = "propose"`.

Optional envelope field *(AI2)*, until the query digest decision is settled:

```json
"query_binding": { "snapshot_digest": "<64 hex>", "snapshot_id": "snap-..." }
```

When present, Backend stores it as the digest `/query` must send, instead of recomputing AI2's internal hash.

### 5.3 `ai2.idp.failed`

Always the full result shape — the bare `{"error": {...}}` form of the previous draft is no longer accepted:

```json
{
  "schema_version": "ai2.be.processing.result.v1",
  "request_id": "run_01J9X1CD:ai2",
  "idempotency_key": "run_01J9X1CD:ai2",
  "attempt": 1,
  "job_id": "job_4f1c...",
  "status": "FAILED",
  "review_state": "BLOCKED",
  "input_snapshots": [],
  "result": null,
  "errors": [{ "code": "LLM_RATE_LIMITED", "message": "...", "retryable": true }]
}
```

`errors[0].retryable` drives the Backend retry button: `true` → the user (or a policy) may start the next attempt; `false` → the run stays failed until the input changes.

| `errors[0].code` | `retryable` | Meaning |
|---|---|---|
| `AI2_ENVELOPE_INVALID` | false | §4 checks failed |
| `AI2_REQUEST_INVALID` / contract codes from the adapter | false | Schema or semantic validation failed |
| `AI2_REQUEST_UNREADABLE` | true | `payload_ref` missing, expired or sha256 mismatch |
| `AI2_IDEMPOTENCY_CONFLICT` | false | Same `(idempotency_key, attempt)` with a different `payload_sha256` |
| `LLM_RATE_LIMITED` / `LLM_UNAVAILABLE` | true | 429 / 529 after AI2's own bounded retries (DOC-11 §2) |
| `AI2_BUDGET_EXCEEDED` | true | `max_processing_seconds` hit |
| `AI2_RESULT_UPLOAD_FAILED` | true | Result too large to inline and the upload failed |
| `AI2_WORKER_FAILED` | false | Unexpected pipeline exception |

## 6. Large payloads: MinIO by reference

Measured AI1 snapshots are ~71 KiB per page, so a dossier past ~140 pages does not fit the 10 MiB message limit. Same pattern as DOC-05d.

**Command.** Backend serialises the payload. If it is larger than `KAFKA_AI2_INLINE_MAX_BYTES` (default 1 MiB) it uploads it and sends a reference instead:

```json
"payload": null,
"payload_ref": {
  "get_url": "http://minio:9000/ci-render/dos_01J9X1AB/ai2/run_01J9X1CD/attempt-1/request.json?X-Amz-...",
  "uri": "s3://ci-render/dos_01J9X1AB/ai2/run_01J9X1CD/attempt-1/request.json",
  "sha256": "<hex of the uploaded bytes>",
  "bytes": 14312345,
  "content_type": "application/json"
}
```

**Result.** Every command carries an upload target:

```json
"result_target": {
  "put_url": "http://minio:9000/ci-render/dos_01J9X1AB/ai2/run_01J9X1CD/attempt-1/result.json?X-Amz-...",
  "uri": "s3://ci-render/dos_01J9X1AB/ai2/run_01J9X1CD/attempt-1/result.json",
  "content_type": "application/json"
}
```

AI2 inlines a result up to `KAFKA_AI2_INLINE_MAX_BYTES`; above that it PUTs the result JSON and publishes `payload: null` with:

```json
"result_ref": { "uri": "s3://ci-render/.../result.json", "sha256": "<hex>", "bytes": 2345678 }
```

Rules (both sides):

- Presigned URLs live `deadline (§8) + 10 min`. AI2 hitting an expired URL → `AI2_REQUEST_UNREADABLE` / `AI2_RESULT_UPLOAD_FAILED`, `retryable: true`.
- Backend reads only the exact `uri` it issued for that `(run, attempt)`; any other `uri` fails the run with `AI2_RESULT_UNREADABLE`. Size ≤ `AI2_RESULT_MAX_BYTES` (64 MiB), sha256 must match, body must be a JSON object.
- MinIO URLs use the Docker DNS name (`http://minio:9000`) so the AI2 worker can reach them.
- Dossier purge deletes `{dossier_id}/ai2/` in `ci-render`.

## 7. Delivery semantics and idempotency

**AI2 worker**

- `enable_auto_commit=false`; commit the command offset **after** the terminal result is published (at-least-once).
- `max_poll_interval_ms` must be larger than the longest budget it can receive (recommended 1 800 000 ms), or the consumer must pause the partition while a job runs. Otherwise a long IDP run causes a rebalance and a second worker processes the same command.
- Dedupe on `(idempotency_key, attempt)`, not only on `event_id`. Same key and same `payload_sha256` → republish the stored terminal result, do not rerun. Different `payload_sha256` → `AI2_IDEMPOTENCY_CONFLICT`. The dedupe store must survive a restart; the in-memory `_processed` dict in today's worker is acceptable only in local dev. Ownership:
  - **Settled:** AI2 owns and operates the store. Backend never reads or writes it, and AI2 never reads or writes Backend tables; the only interface between them is this contract.
  - **Not settled — where it lives waits for the Lead (DEC-BE-AI2-01 D11, PR #37).** Option A (proposed, ADR-14): the shared PostgreSQL server (DOC-11 §3) in AI2's own schema `ai2`, created by AI2's migrations and reached with its own role (`ai2_app`) that has no grant on Backend tables. Option B: keep ADR-02 as it is. This section is updated once D11 is decided.
  - Minimum columns: `idempotency_key`, `attempt`, `payload_sha256`, `job_id`, terminal result (or its `result_ref`), `created_at`. Unique on `(idempotency_key, attempt)`.
  - Retention: at least the topic retention (7 days), so any redelivery still finds its row.
- Transient errors (LLM 429/529, timeouts): bounded retries **inside** AI2, then publish `ai2.idp.failed` with `retryable: true` and commit. AI2 must not "skip and continue": an uncommitted offset followed by a commit of a later offset silently drops the command.
- A record that is not JSON or has no usable `correlation` → park on `ci.ai2.idp.commands.dlq` and commit. Anything with a usable `correlation` gets an `ai2.idp.failed` instead, so the Backend run does not wait for the watchdog.

**Backend results consumer**

- Same delivery loop as the AI1 results consumer: manual commit, handler retry with backoff, then `ci.ai2.idp.results.dlq`; `processed_event` dedupe on `event_id`.
- A result is applied only when `correlation.run_id` is the job's current run **and** `correlation.attempt` is the run's current AI2 attempt. Otherwise it is audited as `ai2.result_late` and dropped.
- `payload.idempotency_key`, `payload.attempt` and `input_snapshots[]` must match what was sent; a mismatch fails the run with `AI2_RESULT_MISMATCH`.
- Persisting is idempotent on the run (`pipeline_run.ai2_result_digest`), so a replayed `completed` is a no-op.

## 8. Deadlines (Backend watchdog)

No polling means Backend owns the timeout.

| Phase | Starts at | Deadline | On expiry |
|---|---|---|---|
| Queued | command published | `KAFKA_AI2_QUEUE_TIMEOUT_SECONDS` (default 900 s) | `AI2_TIMEOUT` (retryable) |
| Running | `ai2.idp.started` received | `max_processing_seconds + AI2_RESULT_GRACE_SECONDS` | `AI2_TIMEOUT` (retryable) |

`max_processing_seconds` = `AI2_DEADLINE_BASE_SECONDS + AI2_DEADLINE_PER_PAGE_SECONDS × pages` (today 300 s + 2 s/page). AI2 must stop by itself at that budget and publish `AI2_BUDGET_EXCEEDED`; the grace only covers publish latency.

A result that arrives after the watchdog failed the run is dropped (job already `FAILED`) and audited. A retry sends `attempt + 1`, so a late result of the old attempt can never be persisted.

## 9. Flow

1. Upload → AI1 OCR over Kafka (DOC-05d) → every document persisted → job `EXTRACTED`.
2. Manifest confirmed → Backend builds the request, signs it, uploads it if large, records `ai2_dispatch` on the run (attempt, event id, deadline), commits, publishes `ai2.idp.command`. Step S4 = `queued`.
3. AI2 validates → publishes `ai2.idp.started` → Backend sets S4 `running` and the running deadline.
4. AI2 publishes `completed` → Backend validates, persists proposals, job `PENDING_REVIEW`.
   AI2 publishes `failed` → Backend fails the run with `AI2_PROCESSING_FAILED` (retryable) or `AI2_REQUEST_REJECTED` (`retryable: false`), AI2's code in the detail.
5. Retry (`dossier.ai2.retry`) → run back to `EXTRACTED` with `attempt + 1` → step 2 again. No re-OCR.

## 10. Environment variables

| Variable | Default | Used by |
|---|---|---|
| `KAFKA_BOOTSTRAP_SERVERS` | `localhost:9093` | Backend + AI2 |
| `KAFKA_AI2_IDP_COMMANDS_TOPIC` | `ci.ai2.idp.commands` | Backend + AI2 |
| `KAFKA_AI2_IDP_RESULTS_TOPIC` | `ci.ai2.idp.results` | Backend + AI2 |
| `KAFKA_AI2_IDP_GROUP_ID` | `ci-ai2-idp` | AI2 worker |
| `KAFKA_BACKEND_AI2_RESULTS_GROUP_ID` | `ci-backend-ai2-results` | Backend worker |
| `KAFKA_AI2_INLINE_MAX_BYTES` | `1048576` | Backend + AI2 |
| `KAFKA_AI2_QUEUE_TIMEOUT_SECONDS` | `900` | Backend |
| `AI2_RESULT_GRACE_SECONDS` | `120` (replaces `AI2_POLL_GRACE_SECONDS`) | Backend |
| `AI2_RESULT_MAX_BYTES` | `67108864` | Backend |
| `AI2_TRANSPORT` | `http` until §12 step 3 is green, then `kafka` | Backend |
| `AI2_SERVICE_HMAC_SECRET` | — (required, fail-closed) | Backend + AI2 worker + AI2 HTTP |
| `AI2_CONTRACT_ROOT` | `docs/contracts` | AI2 schema validation |

## 11. Ownership

| Party | Owns |
|---|---|
| Backend | When to run IDP, snapshot and member selection, request build and signing, MinIO objects and presigned URLs, command publish, deadlines, result validation and persistence, retry policy, HITL |
| AI2 | Kafka worker, envelope and schema/semantic validation, `(idempotency_key, attempt)` dedupe, IDP pipeline within `policy_flags`, `started` / terminal result publish, result upload; must not mutate snapshots or re-OCR |
| AI1 | OCR only; unaware of AI2 |

## 12. Rollout

1. Backend ships the Kafka path behind `AI2_TRANSPORT` (default `http`); HTTP submit/poll stays as fallback.
2. AI2 ships the worker changes in §13 and a compose service `ai2-worker` (same image, `python -m app.transport.kafka_idp_worker`).
3. E2E green on: a 20-page dossier, a body + annex dossier, a ~200-page dossier (by-reference path), and an AI2 worker killed mid-job (watchdog → retry).
4. Switch the default to `kafka`. Remove HTTP submit/poll from the Backend worker one sprint later.

## 13. Sign-off checklist

| # | Point | Backend | AI2 |
|---|---|---|---|
| 1 | Full dossier on Kafka (drop the body-only limit) | [x] | [ ] |
| 2 | Envelope: `causation_id`, new `event_id` per result, `correlation` with `attempt` | [x] | [ ] |
| 3 | `payload_ref` / `result_target` / `result_ref` (§6) | [x] | [ ] |
| 4 | HMAC on Kafka: verify signature and hash, not expiry/nonce (§4) | [x] | [ ] |
| 5 | `ai2.idp.started` event | [x] | [ ] |
| 6 | Dedupe on `(idempotency_key, attempt)`, durable, owned by AI2 (§7). Location waits for Lead decision D11 (PR #37) | [x] | [ ] |
| 7 | Transient errors → `failed` with `retryable: true`, never skip-and-continue | [x] | [ ] |
| 8 | Error code table (§5.3) | [x] | [ ] |
| 9 | `query_binding` in the completed envelope | [x] | [ ] |
| 10 | `max_poll_interval_ms` ≥ max budget | — | [ ] |
| 11 | Security decisions: PLAINTEXT internal broker, no ACLs, shared HMAC key, no expiry/nonce on Kafka (§4) | [x] | [ ] |

## History

| Date | Change |
|---|---|
| 2026-09-24 | v1 draft: MVP body-only; marked "not used" in Sprint 2 (HTTP chosen, SAD D4) |
| 2026-09-30 | v2: Kafka chosen as the runtime path; full dossier, by-reference payloads, `started` event, attempt-scoped dedupe, Backend watchdog |
| 2026-09-30 | v2.1 after AI2 review: status says the runtime is still HTTP; security decisions written out (§4); AI2 owns the dedupe store (§7) |
| 2026-09-30 | v2.2: where the dedupe store lives is the Lead's decision D11 (PR #37), not settled here; schema `ai2` is only option A (§7) |
