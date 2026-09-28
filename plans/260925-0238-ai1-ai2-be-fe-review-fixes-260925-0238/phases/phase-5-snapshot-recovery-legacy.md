---
phase: 5
title: "Snapshot Recovery Legacy"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 5 — Snapshot Recovery Legacy

## Overview

Đảm bảo worker không phụ thuộc `_snapshot_cache` sau restart và canonical production flow không tự chọn stub/legacy OCR. Worker hydrate/reconcile snapshot đã manifest-confirm từ durable DB, giữ digest/lease/idempotency và phân ranh AI1 OCR compatibility với AI2 processing.

Dependencies: Phase 2 result/idempotency boundary and Phase 1 owner scope. Design may be considered alongside phases 3–4, but graph places it after them to reduce merge risk.

## Files

- Modify: `backend/src/contract_intelligence/worker.py`, durable snapshot/repository module and manifest reconciliation seam.
- Modify: `backend/src/contract_intelligence/shared/ai/client.py`, canonical processing config and `docker-compose.yml` only for default/guard (no secrets).
- Modify only when guard requires it: `ai-service/app/api/main.py` legacy `/process` and `/api/v1/jobs/ocr` marker/response.
- Create: `backend/tests/unit/test_snapshot_recovery.py`, `backend/tests/unit/test_legacy_path_guard.py`, `ai-service/tests/test_canonical_legacy_separation.py`.
- Modify: `backend/tests/unit/test_worker_pipeline_run.py`, `ai-service/tests/test_legacy_compat.py`.

## Tests Before (RED)

- [ ] Clear `_snapshot_cache` while DB snapshot + confirmed manifest remain; current worker must reproduce `waiting_for_snapshots` as the red baseline.
- [ ] Reconcile same manifest twice and assert one AI2 submit receipt; digest conflict/stale lease is rejected.
- [ ] Canonical config fails when `AI_SERVICE_MODE=stub` is the default production mode or canonical worker calls `/api/v1/jobs/ocr`.
- [ ] Explicit legacy fixture remains callable but is marked compatibility and cannot be treated as an AI2 result.
- [ ] Run `python -m pytest backend/tests/unit/test_snapshot_recovery.py backend/tests/unit/test_legacy_path_guard.py ai-service/tests/test_canonical_legacy_separation.py ai-service/tests/test_legacy_compat.py -q --basetemp tmp/plan-ai2-p5-red`.

## Implement

1. Hydrate manifest-confirmed snapshots from durable storage keyed by tenant/dossier/manifest/digest; cache is an optimization only.
2. Add bounded reconcile for confirmed snapshots not submitted to AI2, using lease fencing, idempotency key and durable receipt/outbox primitives.
3. Emit stable reason codes for waiting, retryable failure, digest conflict, scope mismatch and terminal blocked; no unbounded loop.
4. Make canonical config reject implicit stub mode and keep AI1 OCR ownership in AI1; legacy client/endpoint requires explicit compatibility profile.
5. Add static/runtime guard that canonical worker cannot call OCR and `/process` metadata-only lane cannot masquerade as an AI2 result.

## Tests After (GREEN)

- [ ] Restart + hydrate submits a confirmed snapshot once and matches uninterrupted-path result.
- [ ] Retry, crash after submit, lease expiry and digest conflict have deterministic receipts/outcomes.
- [ ] Canonical production config chooses AI2; compatibility fixture remains explicit and testable.
- [ ] `rg`/import guard classifies every legacy endpoint reference as canonical guard or explicit compatibility lane.

## Regression Gate

`python -m pytest backend/tests/unit/test_snapshot_recovery.py backend/tests/unit/test_legacy_path_guard.py backend/tests/unit/test_worker_pipeline_run.py ai-service/tests/test_canonical_legacy_separation.py ai-service/tests/test_legacy_compat.py ai-service/tests/test_p3_persistence_events.py -q --basetemp tmp/plan-ai2-p5-regression`; `ruff check backend/src backend/tests ai-service/app ai-service/tests`; `rg -n "AI_SERVICE_MODE: stub|/api/v1/jobs/ocr|_snapshot_cache" backend ai-service docker-compose.yml` with each match classified.

## Success / Acceptance

- [ ] Restart cannot lose a durable snapshot; confirmed run is hydrated/reconciled with one idempotent submit.
- [ ] Cache miss, scope mismatch, digest conflict and lease conflict are observable stable outcomes.
- [ ] Stub/legacy OCR requires explicit opt-in and cannot masquerade as canonical AI2.

## Risks

- Large hydration may increase startup memory; load only pending confirmed records in bounded batches.
- Reconciler can race with BackgroundTasks; lease and receipt must cover both paths.
- Config default change may affect local demo; document an explicit demo profile without leaking it to production.

## Rollback

Disable reconciler while retaining durable snapshots/receipts; revert client/config guard separately from hydration. Keep legacy compatibility opt-in for diagnostics, never restore implicit production stub selection.
