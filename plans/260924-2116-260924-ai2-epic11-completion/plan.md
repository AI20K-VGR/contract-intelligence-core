---
id: 260924-2116-260924-ai2-epic11-completion
title: "EPIC-11 AI2 semantics and reasoning pipeline completion"
status: in_progress
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-24
author: user:dungskbg2004@gmail.com
decisions:
  - "Giữ canonical processing contract be.ai2.processing.request.v1 với ai1.snapshot.v1 cho Sprint 2; ai1.snapshot.v3 chỉ là legacy/backend adapter cho đến khi có quyết định contract mới."
  - "Proceed một plan tuần tự dù scope-split trả multi, vì sáu capability dùng chung contract, provenance, result mapping và phải ship như một vertical slice của EPIC-11."
  - "IndexContribution chỉ ở trạng thái propose; Backend/reviewer mới được phép quyết định publish active."
phases:
  - phases/phase-1-baseline-contract.md
  - phases/phase-2-handoff-relation.md
  - phases/phase-3-facts-findings.md
  - phases/phase-4-query-grounding.md
  - phases/phase-5-backend-integration-verification.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: EPIC-11 AI2 — hoàn thiện semantics và reasoning pipeline

## Tổng quan

Hoàn thiện ST-044–ST-047 thành một luồng dọc có thể kiểm chứng: Backend gửi handoff snapshot đầy đủ; AI2 validate schema/digest/provenance, dựng relation graph, extract typed facts và finding có citation, pair body–annex, chạy query reasoning L0→L3 có grounding bắt buộc, rồi đề xuất `IndexContribution` ở trạng thái `propose`. Backend nhận result có chữ ký, persist/audit/review; AI2 không nhận raw PDF, không OCR, không tự publish active index và không kết luận pháp lý.

Evidence hiện có: canonical endpoint `/jobs/idp` tại `ai-service/app/api/main.py:1419`; adapter snapshot tại `ai-service/app/pipeline/ai1_snapshot_adapter.py:275`; handoff gate tại `ai-service/app/pipeline/handoff.py:26`; relation graph tại `ai-service/app/reasoning/relations.py:128`; pipeline IDP tại `ai-service/app/pipeline/idp.py:39`; four-layer reasoner tại `ai-service/app/reasoning/stack.py:15`; Backend submit/poll tại `backend/src/contract_intelligence/infrastructure/ai_adapters.py:163`; persistence tại `backend/src/contract_intelligence/shared/ai/persistence.py:659`.

## Contract delta và quyết định

### Trước khi làm

- Canonical AI2 processing đã có `be.ai2.processing.request.v1` + `ai1.snapshot.v1`, nhưng một số Backend adapter/endpoint cũ vẫn gửi metadata-only vào `/process`, `/query`, hoặc dùng `ai2.extraction.v2`/`ai2.comparison.v2`.
- `/process` và `/query` fail-closed khi không có evidence content/canonical context; đây là đúng về an toàn nhưng chưa hoàn thành vertical flow.
- Tài liệu/backend legacy vẫn tham chiếu `ai1.snapshot.v3` (`docs/DOC-04-architecture.md:96`, `docs/DOC-05c-backend-ai-service-contract.md:351`). Adapter canonical hiện đã ghi rõ AI1 phát `ai1.snapshot.v1` (`backend/src/contract_intelligence/shared/ai/canonical_processing.py:204`).

### Sau khi hoàn thành

- Một đường processing chuẩn duy nhất: Backend validate/chọn snapshot → submit `be.ai2.processing.request.v1` tới `/jobs/idp` → AI2 trả `ai2.be.processing.result.v1` có facts/findings/citations/evidence issues/index proposal → Backend persist và mở review gate.
- Query chỉ chạy trên evidence projection đã được xác định bởi `tenant_id`, `dossier_id`, `snapshot_digest` và ACL/policy. Nếu projection không tồn tại, stale hoặc không đủ citation thì trả `INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW`, không đoán.
- Giữ endpoint/shape legacy để compatibility và fail-closed; không dùng chúng làm đường hoàn thành ST-044–ST-047.

### Bên bị ảnh hưởng và migration

- AI2: `app/api/main.py`, wire schemas, query context/index store và result mapping.
- Backend: canonical adapter/orchestrator, query forwarding, persistence/review/audit, test fixtures.
- FE chỉ nhận thêm result state/citation/finding đã được Backend persist; không đổi UI trong scope này.
- Migration: route processing mới qua `/jobs/idp`; thêm adapter/contract test cho legacy `v3` nhưng không âm thầm đổi canonical version. Nếu mentor yêu cầu `v3` là canonical, phải mở contract decision riêng trước khi cook phase 1.

## Ràng buộc (constraint-scan)

- AI2 không nhận raw PDF và không gọi OCR/re-OCR; `/api/v1/jobs/ocr` và `/reocr` vẫn là boundary bị chặn.
- Mọi output claim phải trỏ tới citation hợp lệ; citation phải tồn tại trong snapshot và đúng node/page/offset/span.
- L2 planner chỉ được lập plan `compare`/`cascade`; mọi output phải đi qua L3 grounding trước khi công bố.
- Tenant/dossier/snapshot digest, ACL, egress và budget là hard gate; không leak raw contract vào telemetry/prompt ngoài bounded evidence unit.
- `IndexContribution.publish` luôn là `propose`; không mutation active pointer trong AI2.
- Không được giả định full suite xanh: `ai-service/fixtures` thiếu một số source fixture/catalog đang được test import; phase 1 phải khôi phục hoặc xác định cách cung cấp fixture trước khi dùng full-suite gate.
- Shared standards `docs/code-standards.md` và `docs/system-architecture.md` đang thiếu; plan dùng các tài liệu hiện có (`docs/DOC-04-architecture.md`, `docs/DOC-07-khung-project.md`, `docs/contracts/*`) và phải bổ sung/chuẩn hóa standards trước cook nếu harness yêu cầu.

## Features

- `canonical_handoff_relation` — nhận handoff snapshot hợp lệ, reject raw PDF, tạo relation graph deterministic và có provenance.
- `citation_grounded_facts` — extract typed fact với raw/normalized/context/citation và grounding gate.
- `body_annex_findings` — pair body–annex theo context/relation, phát finding có đúng một `model_disposition`.
- `l0_l3_query_grounding` — route L0 deterministic → L1 exact/structured/BM25 hoặc vector tùy policy → L2 compare/cascade → L3 grounding; trả state an toàn.
- `propose_index_contribution` — tạo contribution đề xuất, không publish active, chịu egress/budget/reviewer gate.
- `backend_e2e_persistence` — Backend submit/poll/persist/audit result canonical và query đúng evidence context.

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Baseline & Contract Gate | Không | M |
| 2 | Handoff & Relation Graph | 1 | M |
| 3 | Facts, Findings & Index Proposal | 2 | L |
| 4 | Query L0→L3 & Grounding | 3 | L |
| 5 | Backend E2E & Verification Gate | 4 | L |

## Out of scope

- OCR, re-OCR, PDF parsing hoặc sửa chất lượng AI1.
- Chọn nhà cung cấp/model LLM hoặc embedding production; embedding chỉ là nhánh retrieval có policy, fallback deterministic phải hoạt động.
- Kết luận bên thắng về pháp lý, tự sửa contract, tự kích hoạt index.
- Production vector database/infra migration nếu chưa có quyết định vận hành.
- Redesign FE, thay đổi ACL business policy ngoài việc truyền và kiểm tra policy context.
- Dọn toàn bộ dirty workspace/untracked artifacts không thuộc EPIC-11.

## Acceptance (toàn plan)

- [ ] ST-044: valid canonical handoff qua schema/digest/provenance/lifecycle gate; raw PDF, pin sai, digest sai, page failed/encrypted và membership sai bị từ chối hoặc chuyển state có mã ổn định.
- [ ] ST-044: relation graph có `PARENT_OF`, source-role, explicit reference/amendment, citation-linked edges; graph deterministic, bounded và có issue cho reference thiếu/mơ hồ.
- [ ] ST-045: typed fact lưu raw value, normalized value, context/subject, citation và provenance; body–annex pairing không suy diễn khi thiếu context.
- [ ] ST-045: mỗi finding có đúng một `model_disposition`; citation invalid/thiếu evidence chuyển `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE`, không đưa legal winner.
- [ ] ST-046: L0/L1/L2/L3 được trace; L2 chỉ compare/cascade; `ANSWERED` chỉ được trả sau L3 grounding; các state còn lại là explicit và fail-closed.
- [ ] ST-046: exact → structured → BM25 là đường mặc định; embedding optional có budget/egress/model-dimension gate và fallback an toàn.
- [ ] ST-047: result có `IndexContribution.publish=propose`, không đổi active pointer; Backend/reviewer gate và audit trace tồn tại.
- [ ] E2E: Backend submit/poll/persist được canonical result, query có ACL/evidence context, idempotency và stale digest được kiểm tra.
- [ ] TDD: mỗi phase có RED → implement → regression; cuối plan chạy test/lint/type-check/build bằng command thật của cả `ai-service` và `backend`, sau khi xử lý fixture blocker.

## Rollback

Mỗi phase commit riêng; rollback bằng `git revert <phase-commit>` theo thứ tự ngược, sau đó chạy lại contract tests và integration gate. Không rollback bằng reset/checkout destructive. Nếu contract mới không tương thích, giữ legacy endpoint ở fail-closed và bật lại canonical route cũ bằng cấu hình/feature flag trong lúc sửa adapter.

## Risk pre-mortem

- **Technical:** v1/v3 hoặc result v2/v1 bị trộn; mitigation là contract registry test, adapter explicit và một canonical route.
- **UX:** UI nhận finding nhưng thiếu citation/state; mitigation là Backend chỉ expose finding đã persist đủ citation và state.
- **Adoption:** mentor/Backend không biết query cần evidence projection; mitigation là sequence diagram, sample request/result và ownership table trong phase 1/5.
- **Organizational:** AI2 bị kỳ vọng tự quyết legal winner/active index; mitigation là disposition/propose/reviewer gate được test như invariant.
- **External:** provider embedding/LLM chậm hoặc lỗi; mitigation là deterministic L0/L1 fallback, budget/egress gate và không block exact retrieval.
- **Security:** cross-tenant retrieval hoặc raw evidence leak; mitigation là scope filter trước retrieval, citation validation sau retrieval, redacted logs và negative tests.

## Human gate

Plan này đang `pending`. Cần mentor/owner duyệt hai quyết định: canonical `ai1.snapshot.v1` cho Sprint 2 và mô hình evidence projection cho query. Chỉ sau khi duyệt mới chuyển sang `hs:cook`.

## Red-team disposition

| Finding | Quyết định | Cách xử lý |
|---|---|---|
| RT-01 | Accept | Phase 5 route-selection test bắt buộc canonical `/jobs/idp`; legacy fail-closed. |
| RT-02 | Accept | Phase 4 dùng composite `(tenant_id, dossier_id, snapshot_digest)` và negative scope tests. |
| RT-03 | Accept | Phase 4/5 test reprocess digest và QueryTrace snapshot binding. |
| RT-04 | Accept | Phase 3/5 invariant test retry/duplicate không đổi active pointer. |
| RT-05 | Accept | Phase 1 fixture inventory; phase 5 cấm claim full PASS nếu blocker chưa được xử lý/mentor chấp nhận. |
| RT-06 | Accept | Phase 1 compatibility table và mentor contract gate trước cook. |

## Validation Log

| ID | Topic | Suggested default | Owner / when |
|---|---|---|---|
| VL-1 | Canonical snapshot version | `ai1.snapshot.v1` + `be.ai2.processing.request.v1` cho Sprint 2 | Mentor + Backend owner trước phase 1 lock |
| VL-2 | Query evidence handoff | AI2 evidence projection keyed by `(tenant_id, dossier_id, snapshot_digest)`; stale/missing thì fail-closed | Mentor + Backend owner trước phase 4 |
| VL-3 | Query result schema | Giữ state/citation contract hiện tại nếu đủ; nếu thiếu thì tạo versioned `ai2.query.result.v1` | AI2/Backend owner trong phase 4 |
| VL-4 | Missing fixtures/standards | Không claim full PASS; owner phải khôi phục hoặc mentor ghi nhận blocker | Tech lead trước phase 5 |

### Whole-Plan Consistency Sweep

- Files reread: `plan.md`, `plan-graph.yaml`, `phases/phase-1-baseline-contract.md` đến `phase-5-backend-integration-verification.md`, research report và red-team report.
- Decision deltas checked: 3 canonical/projection/index decisions và 6 red-team dispositions.
- Reconciled stale references: 0; `ai1.snapshot.v3` chỉ còn ở compatibility/legacy context.
- Unresolved contradictions: 0.
