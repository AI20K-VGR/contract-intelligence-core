# P4 — Enforce consent trên processing và query

## Overview

Đưa consent đã lưu vào mọi request egress Backend → AI2, rồi giữ AI2 làm điểm thực thi cuối: service cap AND request consent. Xử lý hai đường query Backend khác nhau và canonical processing; không có route hợp lệ nào tự cho phép LLM/vector nếu dossier opt-out (`contract_router.py:1615-1667`; `api/v1/dossiers.py:107-135`).

## Requirements

- **Functional:** Backend query runtime defaults/cap ON theo profile nhưng policy payload gồm consent per dossier; AI2 chỉ cho outbound khi global cap AND signed dossier consent AND capability flag AND budget. Processing giữ HMAC; request egress field không thể nới server cap. Query không consent vẫn chạy deterministic retrieval/local evidence, bỏ LLM + embedding/vector. Invalid/missing signature fail closed.
- **Compatibility:** wire schema version/HMAC/body digest giữ tương thích hoặc có versioned additive field; các client cũ thiếu consent không được tự cấp quyền, phải fail closed egress; read-only persisted graphs/citations vẫn dùng được.
- **TDD:** red trước cho cả hai query routes, processing job, consent false/default missing, cap false, true+cap true, signed payload tamper và deterministic fallback; sau đó integration.

## Related Code Files

**Create:**

- `backend/tests/unit/test_ai2_query_consent_policy.py`

**Modify (ownership chỉ P4):**

- `backend/src/contract_intelligence/config/settings.py`
- `backend/src/contract_intelligence/shared/query_policy.py`
- `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py`
- `backend/src/contract_intelligence/api/v1/dossiers.py`
- `backend/src/contract_intelligence/shared/ai/canonical_processing.py`
- `backend/tests/unit/shared/ai/test_canonical_processing.py`

**Delete:** —

`ai-service/app/api/main.py`/processing adapters are owned by P2; P4 tests them via signed contract/integration and does not edit those files.

## Implementation Steps

1. Add red integration/unit coverage for both backend query routes and canonical processing, mocking AI2 transport; assert signed payload includes boolean consent from dossier metadata and backend cap separately.
2. Set Backend `ai2_query_egress_allowed`/`ai2_query_use_vector` defaults ON for full product configuration; explicit operator false remains a narrowing cap. Review `server_query_policy_flags()` (`shared/query_policy.py:133-139`) so it emits only server-controlled flags, not a user-supplied value.
3. In `contract_router.search_dossier`, use the already ACL-checked dossier to read `ai2_content_sharing_consent`; merge it into signed query `policy_flags`. Repeat in API v1 `_run_dossier_query`, which already has dossier and metadata (`dossiers.py:107-135`). Both must treat absent field by the centralized consent default from P1/P3 and explicit false as false.
4. Preserve the canonical processing mapper’s consent field (`canonical_processing.py:376-384`) and ensure budget, runtime config, and consent remain separate. Do not derive consent from `AI2_PROCESSING_EGRESS_ALLOWED`; do not let end-user request fields replace operator cap.
5. Confirm `ai-service/app/api/main.py` from P2 consumes signed `content_sharing_consent`, ANDs it with local AI2 env cap, and gates LLM/vector at `:959-983`; if contract test reveals missing coverage, route finding to P2 owner before editing their owned file. Keep signature enforcement at `:878-885`.
6. Run red→green for all conditions and regression test deterministic output. Verify two route families, POST processing egress, pair classifier, query LLM, vector embedding/recall; run backend unit/architecture/PostgreSQL integration and AI-service wire/query tests.

## Success Criteria

- [ ] Both Backend query APIs carry correct signed dossier consent and explicit runtime cap; no untested caller path (only these two were found by scoped search; code.callers codemap is absent).
- [ ] Opt-out causes zero LLM/provider/embedding calls in next query and processing run; deterministic graph and local evidence remain available.
- [ ] Global AI2 cap false blocks all dossiers; true plus dossier false remains blocked; true + true + flag/budget/key available permits eligible egress.
- [ ] Missing consent in old/unsigned payload is fail-closed; modified body or missing HMAC is rejected; valid signatures and current snapshot binding still pass.
- [ ] Tests assert vector path and pair path separately, avoiding false inference from query LLM-only success.

## Risk Assessment

**Cao × Rất cao:** one path forgets to attach consent or AI2 ignores narrowed field. **Mitigation:** endpoint-by-endpoint inventory, signed payload tests on both backend routes, service-boundary tests with provider call counters; missing/old consent fails closed.

**Trung bình × Cao:** additive contract field invalidates strict schema/old clients. **Mitigation:** versioned schema compatibility test, signed payload regeneration, retain signature requirement; no raw unsigned escape.

**Rollback:** immediately set global egress flags false if any opt-out egress is seen; revert backend mapping only with AI2 service still fail-closed. Keep audit/consent values intact.
