---
phase: 6
title: "Integrated Verification"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 6 — Integrated Verification

## Overview

Chạy kiểm chứng cuối cho auth/ACL, persistence/completeness, query/state, dynamic citation/finding, restart recovery và legacy guard. Phase chỉ tạo test harness/report artifact nếu cần; không dùng report để che lỗi và không coi authenticated E2E là PASS khi thiếu Keycloak token/stack.

Dependencies: phases 1–5 phải có verification artifact PASS hoặc explicit blocker.

## Files

- Create: `backend/tests/integration/test_ai2_review_fixes_flow.py` using safe dependency overrides for snapshot → AI2 result → read model → query/review.
- Create: `frontend/tests/ai2-review-fixes-flow.test.tsx` for state/citation/finding composition.
- Create only if repeatable orchestration is needed: `scripts/verify-ai2-review-fixes.ps1`, with no secrets and gate exit codes.
- Create plan-owned verification/report artifacts under `plans/260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238/artifacts/` when cook runs.
- Modify: no product code; a missing seam returns to its owning phase before this gate.

## Tests Before (RED)

- [ ] Compose body + annex, chunks/context/evidence issue, four states, review action and stale version in one fixture; it fails until phase contracts are wired.
- [ ] Negative flow covers anonymous/cross-tenant/legacy stub/duplicate recovery.
- [ ] FE composition proves zero facts/findings does not hide context/evidence and server `BLOCKED` is not `ANSWERED`.
- [ ] Run targeted integration/UI tests and capture first failure as the red baseline artifact.

## Implement

1. Freeze fixture IDs/digests and expected projections; do not use live dossier data or secrets.
2. Run targeted backend/AI2/FE gates in dependency order and collect phase verification JSONs.
3. Run full offline regression, lint/build/format and `git diff --check` locally.
4. Attempt authenticated E2E only with documented Keycloak credential/stack; otherwise record `NOT_RUN`, missing dependency and exact command.
5. Produce a final report separating PASS, NOT_RUN, environment warnings and limitations; do not write an approval verdict.

## Tests After (GREEN)

- [ ] Integration flow proves source scope, state, evidence fields, ACL, review version conflict and one-time recovery submit.
- [ ] FE composition/build/lint/format pass.
- [ ] Full offline AI2/Backend suites pass or list exact pre-existing/environment blockers without false green.
- [ ] `git diff --check` has no new whitespace error and planning has not modified product code.

## Regression Gate

`python -m pytest backend/tests/integration/test_ai2_review_fixes_flow.py backend/tests -q --basetemp tmp/plan-ai2-review-final-backend`; `python -m pytest ai-service/tests -q --basetemp tmp/plan-ai2-review-final-ai`; `npm --prefix frontend test -- --run`; `npm --prefix frontend run build`; `npm --prefix frontend run lint`; `npm --prefix frontend run format:check`; `git diff --check`.

## Success / Acceptance

- [ ] All phase verification artifacts are present; offline gates and every warning/limitation are explicit.
- [ ] Plan frontmatter remains `status: pending` and no approval artifact exists.
- [ ] Authenticated E2E is evidenced PASS with valid token/stack or honestly marked NOT_RUN; it is never inferred from unit tests.

## Risks

- Full suite may hit existing temp permission or missing optional dependency issues; use workspace `--basetemp`, preserve output and classify blockers.
- Fixtures may accidentally rely on mock route; assert Phase 1 route/ACL registration.
- Offline pass does not prove deployment/live recovery; keep P9/live limitations visible and stop before ship approval.

## Rollback

No product rollback occurs in this phase. Remove only plan-owned harness/report artifacts if abandoned; preserve test failures and user worktree changes.
