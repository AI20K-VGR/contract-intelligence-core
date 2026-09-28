---
phase: 1
title: "Auth Acl"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 1 — Auth Acl

## Overview

Đóng route shadowing của C1 và tạo policy decision dùng chung cho query/search/read/mutation theo tenant, dossier sharing, role và actor. Phase không đổi business workflow; nó bảo đảm mọi review/approve mutation đi qua trusted principal, RBAC, ACL và transaction thật.

Dependencies: none. Downstream: phases 2–6.

## Files

- Modify: `backend/src/contract_intelligence/main.py`, `backend/src/contract_intelligence/api/v1/reviews.py`, `backend/src/contract_intelligence/api/v1/dossiers.py`, `backend/src/contract_intelligence/review/interfaces/api/routers/review_full_router.py`, `backend/src/contract_intelligence/approval/interfaces/api/routers/approval_router.py`, `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py`.
- Create or extend the existing `backend/src/contract_intelligence/shared/` ACL seam only if current `_acl_check_dossier_access` and `_require_readable` cannot share a policy without cyclic imports.
- Create: `backend/tests/unit/test_route_registration_authz.py`, `backend/tests/unit/test_dossier_acl_consistency.py`.
- Modify: `backend/tests/unit/test_review_router.py`, `backend/tests/unit/test_approval_router.py`, `backend/tests/unit/test_contract_router.py`.

## Tests Before (RED)

- [ ] Enumerate `app.routes` and assert canonical `review_full_router`/`approval_router` resolve; simulated `_REVIEW_STORE` routes are not registered under production prefixes.
- [ ] Anonymous and wrong-role POST approve/review-action return `401/403`, with no in-memory or DB side effect.
- [ ] ACL matrix covers cross-tenant, same-tenant-unshared, shared-reader, reviewer and administrator for query/search/mutation.
- [ ] Run `python -m pytest backend/tests/unit/test_route_registration_authz.py backend/tests/unit/test_dossier_acl_consistency.py backend/tests/unit/test_review_router.py backend/tests/unit/test_approval_router.py -q --basetemp tmp/plan-ai2-p1-red`; new tests intentionally fail on C1/I7.

## Implement

1. Make canonical route prefixes unique; remove simulated HITL registration from production or move it to an explicit demo namespace.
2. Attach `get_current_user` and role dependencies to every review/approve mutation and use the existing DB transaction/service path.
3. Extract one ACL decision seam from `_acl_check_dossier_access` and `_require_readable`, binding trusted principal, tenant, dossier, sharing policy and action.
4. Apply that seam to direct query, search, citation/finding read and review/approve mutation; preserve the existing error envelope.
5. Add route/principal/share fixtures and an import/registration assertion.

## Tests After (GREEN)

- [ ] Production-prefix route resolution cannot reach a mock mutation.
- [ ] Anonymous, wrong role, unshared, cross-tenant and allowed shared cases produce the expected `401/403/200` outcomes.
- [ ] Denial creates no side effect; allowed mutation writes the DB transaction/audit path.

## Regression Gate

`python -m pytest backend/tests/unit/test_auth_dependencies.py backend/tests/unit/test_route_registration_authz.py backend/tests/unit/test_dossier_acl_consistency.py backend/tests/unit/test_review_router.py backend/tests/unit/test_approval_router.py backend/tests/unit/test_contract_router.py -q --basetemp tmp/plan-ai2-p1-regression`; then `ruff check backend/src backend/tests`.

## Success / Acceptance

- [ ] No unauthenticated review/approve mutation returns `200` or mock `409`.
- [ ] Query and search return the same ACL decision; same tenant alone is not readable.
- [ ] Simulated mutation routes are absent from canonical production registration.

## Risks

- Old fixtures may depend on the mock route; move them to an explicit demo prefix, never reopen the canonical bypass.
- ACL extraction can create circular imports; depend on a protocol/primitive at the application boundary and run import checks.
- Correct RBAC with partial transaction writes would still corrupt state; assert rollback and side-effect count.

## Rollback

Revert only this phase change set if its gate fails; keep red tests as evidence. A rollout flag may disable the canonical route temporarily, but mock routes must not re-register under the production prefix.
