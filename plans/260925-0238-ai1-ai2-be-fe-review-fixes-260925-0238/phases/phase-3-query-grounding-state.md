---
phase: 3
title: "Query Grounding State"
status: pending
plan: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
created: 2026-09-25
---

# Phase 3 — Query Grounding State

## Overview

Khôi phục query semantics cho câu hỏi không khớp intent hẹp và giữ nguyên state từ AI2 qua Backend tới FE. Retrieval theo thứ tự bounded lexical → vector khi runtime policy/index cho phép → LLM chỉ khi egress policy cho phép; mọi nhánh phải có citation/evidence state, retrieval layer, reasoning trace và `used_llm` rõ ràng.

Dependencies: Phase 2 persistence of chunks/context/citations/coverage. Downstream: Phase 4.

## Files

- Modify: `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/l0_rules.py`, `ai-service/app/reasoning/vector_recall.py`, `ai-service/app/api/main.py`.
- Modify: `backend/src/contract_intelligence/shared/ai/canonical_processing.py`, `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py`.
- Modify: `frontend/src/api/ai2.ts` and the existing search API module; remove inferred `ANSWERED` from answer/hits.
- Create: `ai-service/tests/test_query_fallback_state.py`, `backend/tests/unit/test_query_state_passthrough.py`, `frontend/tests/ai2-query-state.test.ts`.
- Modify: `ai-service/tests/test_st046_query_grounding.py`, `ai-service/tests/test_result_regressions.py`, `frontend/tests/ai2-contract.test.ts`.

## Tests Before (RED)

- [ ] Questions about duties/payment/termination/body–annex first assert useful lexical evidence and trace, not hint-only output.
- [ ] `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED` round-trip without `connected=True` or `ANSWERED` overwrite.
- [ ] Vector-disabled avoids vector/LLM; vector-enabled records layer; egress-denied never calls LLM and returns a safe state.
- [ ] Run `python -m pytest ai-service/tests/test_query_fallback_state.py ai-service/tests/test_st046_query_grounding.py backend/tests/unit/test_query_state_passthrough.py -q --basetemp tmp/plan-ai2-p3-red`; tests fail on current unscoped/hardcoded DTO behavior.

## Implement

1. Extend intent handling only with routing metadata; it cannot infer a legal/business conclusion.
2. Add bounded lexical retrieval over persisted chunks/context/evidence scoped to dossier/document/ACL; vector is second only when capability and policy are valid.
3. Attach ordered trace entries, `retrieval_layer`, `used_llm` and reason code; validate citation before any LLM answer is exposed.
4. Preserve server state/trace/evidence issues in Backend DTO; do not default HTTP success to semantic success.
5. Use a discriminated FE union so rendering follows server state.

## Tests After (GREEN)

- [ ] Unscoped questions retrieve bounded evidence before hint and return citations or a safe insufficient state.
- [ ] All state/layer/trace/`used_llm` fields survive the service boundary.
- [ ] Vector/LLM policy matrix and no-evidence case are deterministic.

## Regression Gate

`python -m pytest ai-service/tests/test_query_fallback_state.py ai-service/tests/test_st046_query_grounding.py ai-service/tests/test_result_regressions.py ai-service/tests/test_contract_context.py backend/tests/unit/test_query_state_passthrough.py backend/tests/unit/test_contract_router.py -q --basetemp tmp/plan-ai2-p3-regression`; then `npm --prefix frontend test -- --run ai2-query-state.test.ts ai2-contract.test.ts`, `npm --prefix frontend run build`, and `ruff check backend/src backend/tests ai-service/app ai-service/tests`.

## Success / Acceptance

- [ ] Natural-language queries use bounded lexical fallback when evidence exists and do not stop at hint-only.
- [ ] FE/backend display the four review states, retrieval layer, trace and `used_llm`; no evidence is never called answered.
- [ ] No vector/LLM call occurs outside policy and every exposed answer/candidate passes citation checks.

## Risks

- Broad fallback could cross document scope; bind every retrieval to Phase 1 ACL and dossier/document IDs.
- Vector/LLM dependencies may be unavailable; deterministic fake gateways cover policy while live limitations remain explicit.
- Optional DTO fields may break old clients; add a versioned normalizer and old-payload fixture.

## Rollback

Disable the fallback feature flag while retaining state passthrough; fallback-off must return safe `INSUFFICIENT_EVIDENCE`, never the old inferred `ANSWERED` behavior.
