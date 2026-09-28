---
id: 260925-0238-ai1-ai2-be-fe-review-fixes-260925-0238
title: "Implement fixes from AI1 AI2 Backend Frontend full review"
status: completed
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-25
author: user:dungskbg2004@gmail.com
decisions:
  - "Giữ một master plan cho bảy lỗi liên thông; scope-sizing ghi nhận multi nhưng proceed vì tất cả nằm trên một contract flow AI1 snapshot → AI2 → Backend → FE và được chia thành sáu phase tuần tự có gate riêng."
  - "Giữ canonical contracts và fail-closed review states; không biến `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE` hoặc `BLOCKED` thành `PASS`/`ANSWERED`."
  - "Dùng ACL service chung cho query/search và mutation; route mô phỏng không được đăng ký trong production path."
  - "Legacy OCR/stub vẫn có thể tồn tại cho fixture/compatibility nhưng phải tách khỏi canonical production execution path bằng cấu hình và test guard rõ ràng."
risks:
  - "C: auth route shadowing hoặc same-tenant ACL bypass làm mutation/read sai scope; mitigate trong phase-1 bằng route enumeration và ACL matrix."
  - "H: AI2 nested evidence bị drop hoặc job SUCCEEDED bị hiểu thành evidence-ready; mitigate trong phase-2 bằng round-trip completeness và reason codes."
  - "H: query fallback/FE DTO làm rơi review state hoặc gọi LLM ngoài policy; mitigate trong phase-3 bằng policy matrix và discriminated DTO."
  - "H: restart reconcile duplicate/skip snapshot; mitigate trong phase-5 bằng digest, lease, idempotency receipt và crash replay."
  - "H: offline gate bị báo nhầm authenticated E2E PASS; mitigate trong phase-6 bằng token/stack evidence hoặc NOT_RUN."
phases:
  - phases/phase-1-auth-acl.md
  - phases/phase-2-ai2-persistence-coverage.md
  - phases/phase-3-query-grounding-state.md
  - phases/phase-4-citation-finding-ui.md
  - phases/phase-5-snapshot-recovery-legacy.md
  - phases/phase-6-integrated-verification.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: Implement fixes from AI1 AI2 Backend Frontend full review

> Đây là hợp đồng implementation cho hs:cook; mọi claim không hiển nhiên phải có evidence (file:line / ID) hoặc tag `[ASSUMED]`/`[PRIOR]`.

## Tổng quan

Kế hoạch này sửa đúng bảy nhóm lỗi trong `plans/reports/ai1-ai2-be-fe-full-review-20260925.md`: route auth bị shadow, mất dữ liệu AI2 khi persist, query không grounding và làm rơi state, citation/finding UI còn static, ACL query/search không thống nhất, snapshot cache không tự phục hồi sau restart, và legacy stub/OCR path dễ chạy nhầm. Output của plan là một flow canonical có boundary rõ: AI2 giữ đủ result/evidence/coverage, Backend lưu và phục vụ đúng state, FE render dữ liệu dossier thật, còn mọi đường không có evidence hoặc không có quyền đều fail closed.

Current-state evidence: C1 tại `backend/src/contract_intelligence/main.py:325-332`; I1 tại `backend/src/contract_intelligence/shared/ai/persistence.py:667-799`; I2 tại `backend/src/contract_intelligence/shared/ai/canonical_processing.py:348-355` và `ai-service/app/reasoning/l0_rules.py:227-237`; I3 tại `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:617-622,710-717`; I4 tại `frontend/src/pages/CitationComparePage.tsx:10-50` và `frontend/src/pages/CitationSplitViewPage.tsx:168-223`; I6 tại `backend/src/contract_intelligence/worker.py:65,401-417`; I7 tại `backend/src/contract_intelligence/api/v1/dossiers.py:74-102,184-191`; I8 tại `docker-compose.yml:323-327` và `backend/src/contract_intelligence/shared/ai/client.py:323,407-415`.

complexity: complex · 6 phases · risk: contract drift, authorization, evidence integrity, restart recovery, and UI false-success states.

## Quyết định đã khoá

- Chỉ lập kế hoạch; turn này không sửa product code, không commit, không push và không tạo approval artifact.
- Scope chỉ gồm bảy nhóm trong review report; không mở rộng thành redesign toàn bộ backend, live event transport, provider/model, hay production HA.
- `ai2.be.processing.result.v1`, `ai1.snapshot.v1`, service envelope, tenant/dossier identity, citation provenance và review-state semantics là contract bắt buộc.
- Mọi phase phải có Tests Before (RED), Implement, Tests After (GREEN), regression gate và verification artifact.
- Full authenticated E2E bằng Keycloak hiện là NOT_RUN theo report; kế hoạch chỉ thêm harness/gate để chạy khi có credential hợp lệ, không tuyên bố PASS từ offline tests.

## Ràng buộc (constraint-scan)

- Python backend/AI2: `>=3.11`/`>=3.12` theo module, FastAPI/Pydantic/pytest; frontend React/TypeScript với JSON contracts dưới `docs/contracts/` và `packages/contracts/src/index.ts` chỉ là consumer type.
- AI2 chỉ nhận `ai1.snapshot.v1`; `ai1.result.v0.1` và `ocr.json` là compatibility lanes. Adapter không sửa raw source và không suy luận body/annex/legal winner khi thiếu evidence (`docs/code-standards.md`, `docs/system-architecture.md`).
- Backend là owner của public API, ACL, durable lifecycle và authoritative publish; các primitive P2–P9 hiện có chưa tự trở thành HTTP/SSE production wiring (`docs/system-architecture.md`).
- Authz phải bind trusted `Principal` với tenant/dossier/actor/role/action; cross-scope, unknown role/action và command thiếu idempotency bị deny. Cùng policy phải áp dụng cho query/search/mutation.
- `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED` không phải success; `SUCCEEDED` của job không đồng nghĩa read model đủ evidence. Citation unresolved phải hiện là gap, không render thành nguồn hợp lệ.
- Không dùng cache/in-memory registry làm nguồn sự thật cho restart hoặc nhiều worker; snapshot recovery phải hydrate/reconcile từ DB và giữ lease/idempotency semantics.
- Verification phải dùng pytest với `--basetemp` writable dưới workspace khi cần; report hiện có warning PermissionError ở temp roots và security scan bị self-match, nên các warning phải được ghi riêng.

## Features

1. **Auth route không bị shadow:** review/approve chỉ đi qua route có auth, RBAC, transaction và dossier ACL; caller không token không thể mutate state.
2. **AI2 result/evidence được persist đầy đủ:** facts, findings, context findings, events, chunks, citations, evidence issues, annex links và coverage đi xuyên qua Backend read model; zero-output được phân loại trung thực.
3. **Query grounding và state được giữ nguyên:** câu hỏi ngoài intent đi qua bounded lexical/vector/semantic fallback theo policy; response giữ `state`, `retrieval_layer`, `reasoning_trace`, `used_llm` và evidence issues.
4. **Citation/finding UI động:** màn hình đọc dossier/document/citation/finding thật, mở được body/annex theo source scope và hiển thị review state, coverage, evidence gaps, severity, revision/version conflict.
5. **ACL query/search thống nhất:** cùng một dossier sharing policy được áp dụng cho query trực tiếp, search, citation/finding read và mutation.
6. **Snapshot cache phục hồi được:** worker hydrate snapshot từ durable DB sau restart và reconcile các manifest-confirmed run chưa submit AI2 với retry bounded, không duplicate.
7. **Legacy path bị cô lập:** stub/legacy OCR compatibility không thể được chọn ngầm bởi production canonical flow; mode, endpoint và client guard phân biệt rõ AI1 OCR với AI2 processing.

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Auth và ACL | none | L | route resolution, unauthenticated mutation, shared dossier policy |
| 2 | AI2 persistence và coverage | 1 | XL | canonical result đầy đủ và zero-output classification |
| 3 | Query grounding và state | 2 | L | fallback có evidence, state không bị rơi |
| 4 | Citation và finding UI | 2, 3 | XL | dữ liệu thật, body/annex, finding queue và gap state |
| 5 | Snapshot recovery và legacy separation | 2 | L | restart hydrate/reconcile và production path guard |
| 6 | Integrated verification | 1–5 | L | targeted/full offline gates, smoke checklist, explicit live E2E status |

## Out of scope

- Không đổi model/provider, không huấn luyện model, không dựng vector database mới và không bật LLM khi policy/egress không cho phép.
- Không biến P2/P3/P5/P6 primitives thành HA queue, external exactly-once, HTTP/SSE production transport hoặc approval ledger mới.
- Không xoá toàn bộ compatibility endpoint; chỉ cô lập/đánh dấu/guard để không chạy nhầm canonical production path.
- Không sửa raw OCR, không tự suy luận body–annex/legal winner, không promote `PASS` từ `SUCCEEDED` hoặc từ dữ liệu không có citation.
- Không redesign mobile/visual system, không cross-dossier search và không tuyên bố full authenticated E2E PASS khi thiếu token/infra.

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; test suite của project xanh sau mỗi phase (dùng lệnh test thật của repo).
- [ ] Lint + type-check + build của project sạch (theo lệnh thật của repo).
- [ ] Unauthenticated review/approve mutation nhận `401/403`; route production có RBAC/ACL và route mô phỏng không được resolve trước route thật.
- [ ] Một result có chunks/events/context findings/evidence issues/annex links/coverage nhưng zero facts/findings vẫn được persist, hiển thị đúng gap/review state và không bị ghi nhận là evidence-ready.
- [ ] Query response bảo toàn bốn review states, retrieval layer, trace và `used_llm`; unscoped query không kết thúc ở hint nếu lexical fallback còn dữ liệu trong dossier.
- [ ] Citation click mở đúng `dossier_id`/`document_id`/page/line/bbox, cho phép chuyển body/annex; unresolved citation không có affordance như nguồn hợp lệ. Finding UI hiển thị severity, hai phía evidence, action, version conflict và audit revision từ DB.
- [ ] Query/search/citation/finding read cùng deny cross-tenant và deny same-tenant dossier chưa được share; authorized shared read vẫn hoạt động.
- [ ] Restart worker với snapshot chỉ còn trong DB vẫn hydrate và submit/reconcile một lần; retry/collision không tạo duplicate.
- [ ] `AI_SERVICE_MODE=stub` và legacy OCR client không được chọn từ canonical production config; compatibility calls chỉ chạy qua explicit opt-in/fixture lane và có test guard.
- [ ] Verification report tách `PASS`, `NOT_RUN`, warning môi trường và limitation; không dùng self-report/readiness `PASS` làm bằng chứng deployment/live recovery.

## Rollback

Mỗi phase là một change set độc lập và chỉ được commit sau verification artifact PASS. Khi gate fail, dừng tại phase đó, giữ test/evidence và revert đúng change set bằng `git revert <phase-commit-range>` sau khi xác nhận target; không dùng `git reset --hard` và không đụng thay đổi có sẵn trong working tree. Route canonical có thể được bảo vệ bằng feature/config flag trong thời gian rollout; legacy compatibility chỉ tắt sau khi parity/rollback gate xanh.

## Risks

- **Contract drift:** Backend/AI2/FE mỗi nơi tự thêm default khác nhau. Mitigation: một fixture canonical theo schema, runtime validation ở boundary, contract test trước khi nối UI.
- **Auth bypass còn sót:** router registration hoặc dependency override khiến route mock vẫn được chọn. Mitigation: route table test + unauthenticated HTTP tests + import/registration assertion.
- **False success:** pipeline job xanh nhưng read model rỗng. Mitigation: persist completeness metrics, explicit evidence-ready predicate và state mapping test.
- **Data duplication khi recovery:** hydrate/reconcile chạy lại sau lease loss. Mitigation: snapshot digest, idempotency key, lease fencing, atomic receipt và replay test.
- **UI overclaims:** FE suy ra `ANSWERED` từ answer/hit. Mitigation: discriminated DTO lấy server `review_state`, unresolved citation/gap rendering test.
- **Security scan noise:** scanner hiện self-match `basic-auth-url`; giữ kết quả NOT_PASS và tách khỏi product evidence, không whitelist tuỳ tiện.
- **Scope creep:** semantic/LLM behavior dễ lan sang provider redesign. Mitigation: bounded fallback, explicit policy and `used_llm`, mọi mở rộng phải ngoài scope này.

## Dependencies

- Phase 1 tạo ACL/route invariant cho các phase đọc/mutate sau.
- Phase 2 phải chốt read model và completeness semantics trước Phase 3/4.
- Phase 3 phụ thuộc result/context/citation persistence của Phase 2; Phase 4 dùng DTO/state/query contract của Phase 3.
- Phase 5 dùng durable snapshot/result boundaries của Phase 2 nhưng có thể chạy song song với Phase 3 sau khi contract IDs được khóa; graph vẫn xếp tuần tự để giảm merge risk.
- Phase 6 chỉ chạy sau toàn bộ targeted gates; live Keycloak E2E phụ thuộc credential và stack ngoài repository, không phải điều kiện để giả PASS.

## Verification commands

- Backend targeted: `python -m pytest backend/tests/unit/test_auth_dependencies.py backend/tests/unit/test_review_router.py backend/tests/unit/test_approval_router.py backend/tests/unit/test_contract_router.py backend/tests/unit/test_worker_pipeline_run.py -q --basetemp tmp/plan-ai2-review-backend`
- AI2 targeted: `python -m pytest ai-service/tests/test_processing_wire_contract.py ai-service/tests/test_contract_context.py ai-service/tests/test_result_regressions.py ai-service/tests/test_st046_query_grounding.py ai-service/tests/test_legacy_compat.py ai-service/tests/test_p3_persistence_events.py -q --basetemp tmp/plan-ai2-review-ai`
- Frontend: `npm --prefix frontend test -- --run`; `npm --prefix frontend run build`; `npm --prefix frontend run lint`; `npm --prefix frontend run format:check`
- Full offline regression: `python -m pytest ai-service/tests backend/tests -q --basetemp tmp/plan-ai2-review-full`
- Contract/static checks: `git diff --check`; `rg -n "sampleSearchQuery|splitCitations|setTimeout|AI_SERVICE_MODE: stub|/api/v1/jobs/ocr" frontend backend ai-service docker-compose.yml`
- Authenticated E2E, only when Keycloak token/stack is available: run the repository's documented upload → OCR → AI1 → AI2 → query → review → approve smoke flow and record `PASS`/`NOT_RUN` with token/infra evidence; never substitute this with an unauthenticated probe.

## Research and review artifacts

- `research/current-state-contract-map.md`
- `artifacts/scope-sizing.json`
- `reports/from-code-reviewer-to-planner-red-team-security-failure-operator-plan-review-report.md`

## Validation Log

- `VL-1 | complexity=complex | mode=hard | 6 phases | risk=contract/auth/evidence/recovery/UI | scope accepted as user-requested seven review fixes.`
- `VL-2 | sizing=multi | cells=756 | threshold=60 | decision=proceed | reason=single AI1 snapshot → AI2 → Backend → FE contract flow, split into six gated phases.`
- `VL-3 | tdd=true | red-green pair required in every phase | regression gates are command-specific.`
- `VL-4 | approval=not-run | plan status remains pending | no plan-approval artifact is written.`

### Whole-Plan Consistency Sweep

- Files reread: `plan.md`, `phases/phase-1-auth-acl.md`, `phases/phase-2-ai2-persistence-coverage.md`, `phases/phase-3-query-grounding-state.md`, `phases/phase-4-citation-finding-ui.md`, `phases/phase-5-snapshot-recovery-legacy.md`, `phases/phase-6-integrated-verification.md`, `plan-graph.yaml`, research and red-team reports.
- Decision deltas checked: 4 locked decisions, 7 feature boundaries, 6 phase dependencies.
- Reconciled stale references: 1 red-team filename reference corrected to the canonical harness pattern.
- Unresolved contradictions: 0.
- `OBSERVED`: placeholder scan over the plan directory returned no matches; `hs-run plan graph --require` returned exit `0`; `hs-run plan next --plan ...` reached `needs_model_attestation` with approval still pending.
