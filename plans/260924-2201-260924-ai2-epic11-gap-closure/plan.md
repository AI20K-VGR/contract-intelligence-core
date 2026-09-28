---
id: 260924-2201-260924-ai2-epic11-gap-closure
title: "EPIC-11 AI2 gap closure for ST-044 to ST-047"
status: completed
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-24
author: user:dungskbg2004@gmail.com
decisions:
  - "Giữ nguyên logic đã có; chỉ bổ sung phần còn thiếu và test/gate chứng minh vertical flow."
  - "Giữ canonical be.ai2.processing.request.v1 + ai1.snapshot.v1; legacy path chỉ compatibility/fail-closed."
  - "Query dùng evidence projection/context có composite key tenant_id + dossier_id + snapshot_digest; thiếu hoặc stale thì fail-closed."
  - "AI2 chỉ propose IndexContribution; Backend/reviewer mới được publish active index."
  - "Mỗi ST task có đúng một phase và một commit bằng chứng riêng; không squash/gộp task và không tạo commit verification ngoài 4 commit task."
phases:
  - phases/phase-1-handoff-facts-verification.md
  - phases/phase-2-query-evidence-wiring.md
  - phases/phase-3-index-review-gate.md
  - phases/phase-4-full-e2e-verification.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: EPIC-11 AI2 — đóng phần còn thiếu của ST-044 đến ST-047

## Tổng quan

Audit hiện trạng cho thấy phần lớn lõi AI2 đã tồn tại: handoff/relation graph, typed fact/finding, FourLayerReasoner và IndexContribution propose-only. Phần còn thiếu là chứng minh và nối các lõi này thành luồng Backend → AI2 → Backend hoàn chỉnh, đặc biệt query `/query` hiện vẫn trả `INSUFFICIENT_EVIDENCE` khi chỉ nhận metadata (`ai-service/app/api/main.py:669-696`) và Backend dossier query chưa cấp evidence context (`backend/src/contract_intelligence/api/v1/dossiers.py:184-222`). Kế hoạch này chỉ đóng các gap đó, không thay thế hoặc đổi semantics đang chạy.

Evidence audit: `plans/reports/ai2-epic11-current-state.md`.

## Ràng buộc không đổi logic

- AI2 không nhận raw PDF; handoff phải là canonical snapshot có schema/digest/provenance (`ai-service/app/pipeline/handoff.py:26-124`).
- L0 → L1 → L2 chỉ `compare/cascade` → L3 grounding bắt buộc; `ANSWERED` không được phát nếu thiếu citation hợp lệ (`ai-service/app/reasoning/stack.py:15-189`, `ai-service/app/reasoning/l3_ground.py:13-236`).
- Không tạo legal winner; mỗi finding có đúng một `model_disposition` (`ai-service/app/contracts/models.py:438-477`).
- AI2 không publish active index; `IndexContribution.publish` vẫn là `propose` (`ai-service/app/pipeline/index.py:6-45`).
- Không claim full PASS khi còn lỗi môi trường pytest temp-dir, thiếu fixture/import hoặc Backend interpreter chưa chạy được.

## Features / deliverables

- `handoff_relation_graph`: hoàn thiện và chứng minh ST-044 độc lập bằng một commit.
- `facts_findings_pairing`: hoàn thiện và chứng minh ST-045 độc lập bằng một commit.
- `query_evidence_projection`: nối Backend dossier query vào evidence projection/context đúng scope; giữ FourLayerReasoner hiện tại và fail-closed khi thiếu/stale/khác tenant.
- `reviewer_publish_gate`: hoàn thiện và chứng minh ST-047 độc lập bằng một commit; AI2 không tự publish.

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | ST-044 — Handoff + relation graph | Không | M |
| 2 | ST-045 — Facts/findings + body–annex | 1 | M |
| 3 | ST-046 — Query L0→L3 + grounding | 2 | L |
| 4 | ST-047 — IndexContribution + reviewer gate + final E2E | 3 | L |

## Out of scope

- OCR, PDF parsing, re-OCR, thay đổi AI1.
- Đổi version canonical contract nếu chưa có quyết định riêng của mentor/Backend.
- Thay model LLM/embedding hoặc triển khai vector database production.
- FE redesign, legal conclusion, active-index mutation trong AI2.
- Dọn các dirty/untracked file không thuộc EPIC-11.

## Quy ước commit bằng chứng

Cook phải tạo đúng 4 commit theo thứ tự sau; mỗi commit chỉ chứa file/code/test của một task và artifact verification tương ứng:

| Commit | Task | Nội dung bắt buộc | Artifact |
|---|---|---|---|
| C1 | ST-044 | handoff schema/digest/provenance + relation graph + tests | `verification-ST-044.json` |
| C2 | ST-045 | typed facts + citation + body–annex finding + tests | `verification-ST-045.json` |
| C3 | ST-046 | Backend evidence query wiring + L0→L3 grounding + tests | `verification-ST-046.json` |
| C4 | ST-047 | propose-only index + reviewer/Backend gate + final E2E/regression evidence | `verification-ST-047.json` |

Mỗi commit phải có message `feat(ai2): complete ST-044` … `feat(ai2): complete ST-047`, command/output hoặc verification artifact, và được kiểm tra bằng `git show --stat --check <commit>`. Không squash, không commit placeholder, không trộn task khác vào commit.

## Acceptance toàn plan

- [ ] ST-044: canonical snapshot được validate schema/digest/provenance/lifecycle; raw PDF và snapshot sai bị reject; relation graph deterministic có parent/source-role/explicit-reference edges.
- [ ] ST-045: fact giữ raw + normalized + context + citation; body–annex pairing có context/relation; finding có đúng một `model_disposition`; Backend persist được result/citation.
- [ ] ST-046: Backend query truyền đúng `(tenant_id, dossier_id, snapshot_digest)` và evidence context; L0→L3 chạy đúng trace; chỉ L3-grounded answer mới là `ANSWERED`; missing/stale/cross-tenant trả state an toàn.
- [ ] ST-047: AI2 chỉ trả `propose`; reviewer/Backend gate publish active có audit/idempotency; retry không làm đổi active pointer ngoài gate.
- [ ] Regression: targeted suite xanh; full suite/build/type-check/lint được chạy hoặc ghi blocker có owner, không dùng workaround làm yếu test.
- [ ] Có đúng 4 commit bằng chứng C1–C4, mỗi commit map một-một với ST-044–ST-047; final E2E chỉ là evidence trong C4, không tạo commit thứ 5.

## Rollback

Mỗi phase là một commit riêng; rollback bằng `git revert C4`, rồi `C3`, `C2`, `C1` nếu cần và chạy lại contract/regression gate. Không dùng reset/checkout destructive. Giữ legacy route fail-closed nếu canonical integration chưa sẵn sàng.

## Rủi ro và giảm thiểu

- Contract drift v1/v3: khóa canonical contract bằng contract tests và compatibility matrix.
- Query stale/cross-tenant: composite scope key, digest check trước retrieval, negative tests.
- Reviewer gate chưa có API/storage rõ: phase 4 phải chốt owner/interface trước khi code; nếu chưa chốt thì chỉ hoàn thiện proposal/audit contract, không giả lập publish.
- Môi trường không chạy full suite: tách lỗi môi trường khỏi assertion; giữ evidence command/output và không đánh dấu PASS giả.

## Human gate

Kế hoạch này đang `pending` vì kế hoạch cũ đã bị BLOCKED ở P1. Mentor cần duyệt lại scope evidence projection/query handoff và reviewer publish gate trước khi chạy `hs:cook`.

## Validation log

| ID | Câu hỏi cần chốt | Owner |
|---|---|---|
| VL-1 | Evidence projection thuộc AI2 hay Backend persistence? | Mentor + Backend |
| VL-2 | Reviewer publish được gọi qua API/command nào, và active pointer nằm ở đâu? | Backend owner |
| VL-3 | Cách cung cấp fixture/temp-dir/interpreter để full suite chạy reproducibly? | Tech lead |

## Red-team readiness

Các rủi ro phải được kiểm tra trong phase 4: legacy route bypass canonical, stale digest, cross-tenant retrieval, duplicate processing làm mutation active, raw evidence leak và claim full PASS khi environment blocker chưa được xử lý.

## Red-team disposition

| Finding | Quyết định | Cách xử lý |
|---|---|---|
| RT-01 | Accept | Phase 3 bắt buộc Backend→AI2 contract/E2E payload; phase 4 chỉ PASS khi có vertical evidence. |
| RT-02 | Accept | Phase 3 lookup/filter theo đủ tenant+dossier+digest và negative tests trước retrieval. |
| RT-03 | Accept | Phase 4 yêu cầu owner/interface/persistence anchor; thiếu thì BLOCKED/NEEDS_REVIEW, không fake approve. |
| RT-04 | Accept | Phase 4 test idempotency theo scope/digest/contribution và active-pointer invariant. |
| RT-05 | Accept | Phase 4 lưu command/exit code/test count/blocker owner; cấm skip silent hoặc hạ assertion. |
| RT-06 | Accept | Phase 3/4 test bounded evidence, redacted telemetry và không gửi raw/full dossier. |
