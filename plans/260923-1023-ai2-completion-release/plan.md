---
id: 260923-1023-ai2-completion-release
title: "Hoàn thiện AI2 đến release gate"
status: completed
mode: hard
tdd: true
branch: TBD
created: 2026-09-23
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-contract-boundaries.md
  - phases/phase-2-evidence-pipeline.md
  - phases/phase-3-processing-runtime.md
  - phases/phase-4-release-verification.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: Hoàn thiện AI2 đến release gate

## Tổng quan

Hoàn thiện lane AI2 hiện có thành package xử lý snapshot AI1 có contract rõ,
evidence truy nguyên được, xử lý bị giới hạn và kết quả chỉ được đánh dấu đủ điều
kiện cho authoritative publish sau review gate bên ngoài AI2. Plan này tiếp tục hiện trạng trong `ai-service`, không viết lại pipeline
đã chạy được và không biến `NEEDS_REVIEW` thành `PASS` bằng heuristic.

[OBSERVED 2026-09-23] Hai acceptance inputs do người dùng cung cấp là:

- `C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json` — producer profile
  `ai1.snapshot.v1/ocr-lab`, `dossier-001/doc-001`, `TEXT_LAYER`, 8 pages, 69 root
  nodes, 1 table dưới `pages[*].tables`, không có table continuation.
- `C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json` — producer profile
  `ai1.snapshot.v1/ocr-lab`, `dossier-001/doc-002`, `SCANNED_OCR`, 4 pages, 7 root
  nodes, 3 tables dưới `pages[*].tables`, 2 continuity records; đây là
  hợp đồng loại khác và có phụ lục nhúng trong cùng snapshot, không phải annex của
  `doc-001`.

[OBSERVED 2026-09-23] Suite offline chạy với `--basetemp` trong workspace đạt
`198 passed, 6 deselected`; lần chạy mặc định có `6 errors` do quyền truy cập
`C:\Users\dungs\AppData\Local\Temp\pytest-of-dungs`, không phải assertion failure.

## Goal warmup contract [LOCKED 2026-09-23]

Plan này chỉ làm AI2. AI2 phải tổng quát hóa producer profile hiện tại cho một
nhóm hợp đồng cơ bản, trích xuất cây cấu trúc/fact/trường đặc thù, mô hình hóa
quan hệ hợp đồng–phụ lục, so sánh bất đồng và trả lời câu hỏi tự do trong một
hồ sơ hợp đồng. Thiếu evidence, mâu thuẫn hoặc quan hệ không resolve được phải
trả citation + lý do + `NEEDS_REVIEW`; không suy diễn, không chọn legal winner.

Phạm vi loại hợp đồng wave đầu: mua bán hàng hóa; cung cấp thiết bị/dịch vụ;
thuê tài sản/dịch vụ; thi công/xây dựng hoặc hợp đồng công việc; lao động; NDA;
và phụ lục về giá/số lượng/phạm vi kỹ thuật/tiến độ/SLA/thanh toán/nghiệm thu/
điều chỉnh. 95 case hiện có chỉ là corpus ứng viên `UNVERIFIED`; chỉ case được
người duyệt xác nhận mới trở thành golden evidence và được dùng đo accuracy.

AI2 mặc định chỉ hỏi/so sánh trong một hồ sơ gồm contract + annex liên quan.
So sánh hồ sơ độc lập chỉ thực hiện khi caller chỉ rõ scope.

## Outcome contract

- **Expected output:** một implementation plan được duyệt, dẫn tới package AI2 v1,
  request/result contract hợp lệ, report release offline và replay đúng hai OCR-lab
  inputs trên; plan này không tự viết code.
- **Acceptance:** payload sai bị từ chối; payload đúng giữ nguyên raw evidence;
  mọi fact/finding/event xuất ra có citation kiểm tra được hoặc bị hạ review;
  `doc-001` và `doc-002` không tạo cross-document finding; annex nhúng trong
  `doc-002` được xử lý trong đúng snapshot; budget/egress/lease/idempotency không
  cho phép xử lý vượt ranh giới; report ghi rõ `n`, trạng thái, lỗi và phần chưa chạy.
- **Scope boundary:** chỉ `ai-service`, `docs/contracts`, package contract và
  workflow/release evidence cần cho AI2. Không bao gồm triển khai BE ACL/lifecycle
  production, OCR provider production, pgvector production, cost ledger, process
  isolation, hay giao diện HITL đầy đủ.
- **Non-negotiable constraints:** canonical handoff contract là `ai1.snapshot.v1`
  và `be.ai2.processing.request.v1`; hai file OCR-lab hiện tại đi vào qua
  producer adapter và không được gọi là canonical backend snapshot; snapshot/raw node không bị sửa; không tự tạo
  geometry/citation; không kết luận `LEGAL_WINNER`; LLM/vector là tùy chọn và
  fail-closed; giữ tương thích legacy qua adapter riêng.
- **Touchpoints:** `ai-service/app/contracts/`, `ai-service/app/pipeline/`,
  `ai-service/app/reasoning/`, `ai-service/app/tools/`, `ai-service/app/ai2/v1/`,
  `ai-service/tests/`, `ai-service/scripts/`, `docs/contracts/`, `evals/`,
  `packages/contracts/` và `.github/workflows/ai-service.yml`.

## Quyết định đã khóa

- Canonical backend input vẫn là `ai1.snapshot.v1`; hai file hiện tại là
  `ai1.snapshot.v1/ocr-lab` producer profile và phải qua adapter/validation.
  `ai1.result.v0.1` và legacy OCR chỉ là compatibility path, không được nhận như
  canonical snapshot.
- Scope mặc định là `INDEPENDENT`: cùng `dossier_id` không đủ để suy ra quan hệ
  giữa hai file; quan hệ body–annex chỉ được nhận diện trong cùng snapshot khi có
  evidence/citation. Vì vậy `doc-002` có thể có embedded annex, nhưng không được
  ghép với `doc-001`.
- `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE` và `BLOCKED` là trạng thái an toàn có chủ ý.
  `propose` không phải publish authoritative; AI2 chỉ trả proposal/review evidence,
  không sở hữu hành động publish.
- Không bật live provider trong offline gate; live LLM/embedding là gate riêng,
  chỉ báo pass khi credential và sample thực sự có mặt.

## Tổng hợp kết quả các bước đã chạy

Plan này hợp nhất các artifact sau, theo đúng thứ tự discovery → implementation evidence →
adversarial review:

1. `hs:understand`/scout: đã xác định các điểm neo thật trong `ai-service`, baseline
   `198 passed, 6 deselected` khi pin `--basetemp`, và contract registry hiện có.
2. `hs:docs`: đã bổ sung tài liệu AI2-only, sáu contract profiles, semantic dossier,
   relation/comparison và bounded free-form query; docs không được kéo AI1/OCR/BE/FE vào.
3. `hs:discover`: đã khóa hướng **evidence-first semantic dossier + bounded query**,
   không chọn profile-first đơn lẻ, RAG-first hoặc universal ontology-first.
4. `hs:research`: đã xác định semantic/evidence spine, canonical handoff, raw immutable,
   safe states, tenant/dossier isolation, budget/egress/idempotency và blocker golden set.
5. `hs:scenario`: đã bao phủ edge/operational cases cho scan-quality input, bảng nhiều
   trang, missing/malformed/conflict, nhiều party, scope, concurrency, large dossier,
   prompt injection, stale review và provider failure; các bước OCR/upload vẫn ngoài AI2.
6. `hs:eval-bootstrap`: đã tạo hai eval domain, ground truth/schema/citation scorer,
   production runner, CI wiring và baseline evidence; các skip/parity/mutation gap vẫn
   là unresolved và phải được xử lý ở P4.
7. `hs:predict`: verdict **STOP** do citation/grounding state không nhất quán, source
   prompt injection, PII/egress, dossier mismatch, unsafe `run_code`, mirror-induced
   PASS, parity skip, mutation target mismatch và thiếu performance budget.

Các kết quả PASS ở trên là baseline hoặc regression signal, không phải giấy phép release.
Mọi finding chưa có evidence production thật phải được ghi `NOT_RUN`, `BLOCKED` hoặc
`UNVERIFIED` đúng nguyên nhân.

## Ràng buộc (constraint-scan)

- `docs/code-standards.md` và `docs/system-architecture.md` đã được bổ sung theo
  thực tế repo; phase cook phải giữ chúng đồng bộ nếu touchpoint thay đổi.
- `ai-service/pyproject.toml` dùng Python `>=3.12`, pytest và marker `live`, `llm`,
  `integration`, `e2e`; CI hiện chạy offline pytest và contract registry.
- Contract registry phải qua `node scripts/check-contract-registry.mjs`.
- Giữ thay đổi AI2 đang có trong working tree; không reset, checkout hoặc xóa file
  không thuộc plan. Không commit hai JSON OCR-lab ngoài repo; chỉ đọc theo absolute path.

## Features

1. **Canonical AI1-to-AI2 handoff** — nhận đúng snapshot/request, giữ identity,
   membership, digest, role và version, trả lỗi có mã ổn định.
2. **Source-grounded contract analysis** — tạo clause/table/fact/event/context/
   party answer với citation page/line/node/table/cell hợp lệ và review issue khi
   thiếu hoặc mơ hồ.
3. **Bounded and review-safe processing** — giới hạn thời gian/call/token,
   fallback deterministic, egress fail-closed, lease/idempotency tenant-safe,
   review stale-safe và index chỉ ở trạng thái đề xuất.
4. **Release evidence and package boundary** — package v1, script replay/eval,
   schema registry, deterministic corpus và report đủ denominator để người duyệt
   quyết định release.
5. **Contract-type profiles** — bộ field/fact theo từng loại hợp đồng, có profile
   version và extension path; field không nhận diện được giữ raw/evidence hoặc
   `NEEDS_REVIEW`, không ép vào field sai loại.
6. **Structure, relation and free-form query** — cây body/annex/clause/table có
   parent/order/scope; relation graph và comparison có hai phía evidence; free-form
   Q&A route bounded retrieval rồi grounding trong đúng hồ sơ.

## Phases

| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Contract Boundaries | none | standard |
| 2 | Evidence Pipeline | 1 | complex |
| 3 | Processing Runtime | 1, 2 | complex |
| 4 | Release Verification | 1, 2, 3 | standard |

## Out of scope

- Xây hoặc thay queue/worker/ACL/lifecycle production của Backend.
- Gọi hoặc tối ưu Paddle/Tesseract/Mistral/OpenAI/Gemini như production OCR service;
  AI2 chỉ kiểm tra handoff và fail-safe khi upstream thiếu/không chắc.
- Chọn hoặc triển khai pgvector/vector index production, cost ledger, encrypted
  intake, hard process isolation hoặc memory/CPU sandbox.
- Xây UI review đầy đủ, audit user/time production, frontend build flow hoặc quyết
  định pháp lý/precedence/`LEGAL_WINNER`.
- Đo accuracy/IoU/CER/SLA nếu chưa có ground truth và mẫu số độc lập.

## Acceptance (toàn plan)

- [ ] Mọi request/result canonical được validate bằng JSON Schema và semantic checks;
  unknown field, membership mismatch, digest mismatch, duplicate identity và legacy
  shape sai bị reject với error code ổn định.
- [ ] Raw snapshot, page/node/table evidence không bị mutate; citation nào không
  resolve được đều bị đánh dấu `UNVERIFIED`/`NEEDS_REVIEW` và không được đánh dấu
  eligible/authoritative trong AI2 result.
- [ ] Table continuation, sparse/claimed geometry, missing context, failed page và
  party chỉ có role mention đều tạo trạng thái an toàn, không bịa value/geometry.
- [ ] Với hai input trên, `cross_document_findings=[]`; `doc-002` giữ được annex
  inventory/continuity trong cùng scope; body–annex chỉ link khi có evidence.
- [ ] Mỗi loại hợp đồng wave đầu có profile versioned cho field/fact đặc thù; output
  giữ raw value, normalized value nếu có, source scope, provenance, citation và
  review state. Profile mới có thể thêm mà không đổi semantics profile cũ.
- [ ] Cây cấu trúc giữ được body/annex/clause/table, parent/order/page/source scope;
  relation không resolve được không bị biến thành `ANNEX_OF` chắc chắn.
- [ ] Comparison hỗ trợ `WITHIN_DOCUMENT`, `CONTRACT_ANNEX`, `ANNEX_ANNEX`, có
  evidence hai phía, `NOT_COMPARABLE` khi khác scope/unit/currency và không tạo
  `LEGAL_WINNER`.
- [ ] Free-form question bị giới hạn trong dossier scope mặc định, trả lời có
  citation/trace, và trả `INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW` khi không đủ source;
  query không mở sang hồ sơ độc lập chỉ vì trùng `dossier_id`.
- [ ] 95 case tham khảo được đánh dấu `UNVERIFIED`; report tách candidate corpus,
  human-reviewed golden set và accuracy claim. Không có golden set thì chỉ claim
  schema/citation/safety/regression, không claim nghiệp vụ.
- [ ] Processing tôn trọng time/LLM/embedding budget, egress policy, tenant/dossier
  scope, lease và idempotency; retry/fallback không làm mất unit thành công.
- [ ] Package v1 và CLI replay trả report deterministic; release report ghi `n`,
  denominator, sample/version, pass/review/fail/not-run và không claim live khi chưa
  chạy provider thật.
- [ ] Mỗi phase có test-before/test-after, verification artifact và regression gate;
  suite repo xanh bằng command thật:
  `Set-Location ai-service; .venv\Scripts\python.exe -m pytest -q -m "not live" --basetemp ..\tmp\ai2-plan-basetemp`.
- [ ] Contract registry xanh bằng `node scripts/check-contract-registry.mjs`.

## Rollback

Mỗi phase là một commit riêng sau khi gate xanh. Nếu phase làm hỏng contract hoặc
regression, dừng tại phase đó, giữ artifact/report để chẩn đoán và `git revert` đúng
commit phase; không reset toàn working tree vì hiện trạng trước plan có thay đổi của
người dùng.

## Risks

- **Contract drift:** schema/docs/code lệch nhau → test schema + semantic và registry
  ở phase 1, không chấp nhận đổi tên field chỉ ở adapter.
- **Evidence overclaim:** heuristic nhận nhầm table/party/annex → giữ raw, gắn
  citation và hạ `NEEDS_REVIEW`; không dùng confidence thay verification.
- **Provider/budget nondeterminism:** LLM/vector timeout hoặc rate limit → default
  offline, bounded retry, fallback local, report rõ `not-run`/`blocked`.
- **Scope phình thành production platform:** BE/FE/OCR/infra bị kéo vào → giữ danh
  sách out-of-scope và tách backlog sau release gate.
- **Dirty tree contamination:** file tạm/generated bị lẫn vào change → kiểm tra
  `git status --short`, chỉ stage touchpoints của phase và không xóa artifact của user.
- **Type-profile sprawl:** sáu loại hợp đồng làm schema phình → profile registry
  versioned, field core nhỏ, extension theo type; không tạo union field không có
  owner/evidence.
- **Free-form overreach:** câu hỏi tự do làm LLM đọc ngoài scope → query envelope
  pin dossier/member scope, retrieval bounded, L3 grounding bắt buộc, thiếu source
  trả safe state.
- **Unverified corpus:** 95 case có thể chứa expected sai → dùng candidate để tìm
  regression, chỉ promote sau human review; current repo manifest phải được đối chiếu
  với claim 95 trước khi ghi denominator.
- **Eval false confidence:** 10/10 và 20/20 baseline, maturity 100 hoặc mirror PASS
  không chứng minh production parity; release gate phải gọi production entry, tách skip
  khỏi pass, yêu cầu `parity_executed > 0`, và fail loud khi P0/mutation config không
  map được. Ground-truth rỗng hoặc case không có expected field cũng là config error,
  không phải case đạt.
- **Unsafe query/runtime:** `ANSWERED` không được đi cùng `grounded=false`/citation
  invalid; source text là untrusted data, egress/PII default-deny, dossier mismatch
  fail-closed và `run_code` không được chạy trong AI2 path.
- **Large dossier resource blow-up:** phải đo p95/p99, peak RSS, token/call và
  candidate/chunk/edge/citation counts theo các quota numeric đã pin (`max_pages`,
  `max_members`, `max_chunks`, `max_edges`, `max_citations`, `max_seconds`,
  `max_provider_calls`, `max_tokens`, `max_rss_mb`); vượt budget trả partial/safe state.

## Validation Log

- `VL-1 | complexity=complex | mode=hard | 4 phases because contract, evidence, runtime, and release have ordered dependencies.`
- `VL-2 | corpus=doc-001/doc-002 | producer_profile=ai1.snapshot.v1/ocr-lab | nested_tables=1+3 | continuity=0+2 | dossier_id=dossier-001 | relation_policy=INDEPENDENT | OBSERVED 2026-09-23.`
- `VL-3 | suite=198 passed, 6 deselected | command=pytest -q -m "not live" --basetemp <workspace> | OBSERVED 2026-09-23.`
- `VL-4 | default pytest=6 errors | cause=WinError 5 on pytest temp root | rerun with workspace basetemp passed.`
- `VL-5 | candidate corpus probe=repo manifest 65 cases; historical/user statement=95 cases; disposition=UNVERIFIED until source/version reconciliation | OBSERVED 2026-09-23.`
- `VL-6 | eval baseline=contract 10/10, query 20/20; tests=16+24 skipped and 18+20 skipped; parity skips are not coverage | OBSERVED 2026-09-23.`
- `VL-7 | mutation probe=blocked: p0_rules.target_axis dimension names do not map to case_matrix.expect fields; no mutation PASS claim | OBSERVED 2026-09-23.`
- `VL-8 | predict verdict=STOP: citation/state, prompt injection, privacy/egress, scope fail-closed, unsafe execution and performance evidence require closure | OBSERVED 2026-09-23.`

## Contract traceability

| Phase | Contract items | Acceptance signals | Facts / assumptions / prereqs / user decisions |
|---|---|---|---|
| P1 | AI1 producer adapter, type-profile registry, canonical wire | profile/version validation; unknown type/field safe state; raw immutable | Verified: current producer shape and core `Fact` model. User decision: wave đầu gồm 6 loại + annex groups. |
| P2 | structure tree, relation graph, facts, comparisons, citations, free-form Q&A | parent/order/scope; two-sided citations; bounded dossier Q&A; safe states | Verified: `contract_context`, `compare`, `query`, `L0–L3` exist. Assumption: profile-specific extraction can reuse core fact/candidate model. |
| P3 | bounded execution, tenant/dossier scope, egress, stale review, unsafe tool boundary | no cross-dossier leakage; no unbounded provider; raw/review separation; `run_code` denied | Verified: runtime/store tests exist. Prereq: query scope must be carried in request/envelope. |
| P4 | candidate corpus, golden promotion, production parity, mutation/performance evidence, release evidence | 95 candidate vs reviewed denominator separated; no accuracy claim without gold; no mirror-only release | Verified: repo has 65 manifest cases and historical reports mention 95; parity and mutation mapping are unresolved. |

## Goal-warmup contract-preserving review

| Finding | Class | Disposition |
|---|---|---|
| Type-specific profile registry could expand schema uncontrollably | `mitigation-within-contract` | Keep a small versioned core plus six explicit wave profiles and extensions; no union-field sprawl. |
| Free-form Q&A could retrieve outside the selected contract package | `mitigation-within-contract` | Pin tenant/dossier/member scope in the query envelope and require L3 grounding; out-of-scope query is safe state. |
| User mentions 95 cases but current repo manifest contains 65 case records | `preflight-required` | Reconcile source/version/denominator; until then mark all candidate cases `UNVERIFIED`. Not a blocker for safety/schema implementation. |
| No human-reviewed golden set exists | `blocker` for accuracy claim only | Do not claim business accuracy or promote golden evidence until reviewer confirmation exists. Initial AI2 build may proceed with safety/schema/regression claims only. |
| Need to add AI1/OCR/BE/FE work to achieve generality | `outcome-change-request` | Rejected by locked contract; AI2 consumes the producer profile and remains within `ai-service`. |

## Goal-warmup preflight matrix

| Phase | Requirement | Check method | Status | Owner / unblock action | Blocking? |
|---|---|---|---|---|---|
| P1 | AI2-only scope and six contract types approved | Locked Outcome Contract above | available | user approved | no |
| P1 | Producer profile/schema available | `docs/contracts/ai1.snapshot.v1.ocr-lab.schema.json` + current replay | available | AI2 adapter work | no |
| P1 | Offline execution environment | existing workspace venv + baseline `198 passed` with pinned basetemp | available | rerun after each phase | no |
| P2 | Structure/relation/query implementation points | `contract_context`, `compare`, `query`, `stack`, `L0–L3` inspected | available | targeted tests before edit | no |
| P3 | No provider credential required for safety gate | offline deterministic path | available | live remains opt-in | no |
| P4 | 95 candidate corpus source/version | manifest/report/source reconciliation | unknown | owner: user/reviewer; record exact corpus before accuracy report | yes for accuracy claim, no for initial build |
| P4 | Human reviewer for golden promotion | reviewer confirmation artifact | missing | owner: user/reviewer; promote selected cases only after review | yes for accuracy claim, no for initial build |

### Preflight disposition

The long-run may implement and verify AI2 safety/schema/evidence behavior without
claiming business accuracy. It must stop before any accuracy claim or golden-set
promotion if the 95-case source and human review evidence remain unresolved.

## Red-team disposition

- RT-01: đã sửa ranh giới publish; AI2 không publish authoritative.
- RT-02/RT-07: replay Downloads là evidence có điều kiện; thiếu file/provider phải
  ghi `NOT_RUN`, còn deterministic fixture là gate bắt buộc; live failure là
  `BLOCKED`/`FAIL`, không hạ xuống `NOT_RUN`.
- RT-03/RT-04: giữ bốn phase tuần tự, không mở rộng sang BE/FE/OCR/infra; reasoning
  chỉ được sửa khi targeted test chứng minh gap.
- RT-05/RT-06: post-artifact và baseline-only sẽ được ghi rõ trong từng phase và
  không dùng baseline dirty tree làm release evidence.
- RT-08: giữ hai `document_id` độc lập dù cùng `dossier_id`, đồng thời assert
  `cross_document_findings=[]` trên replay.
- RT-09: bổ sung kiểm tra topology table nested dưới page và phân biệt table-level
  `MEASURED` với cell-level `CLAIMED`; không suy ra thiếu text từ `word_count=0`.
- PRED-UX-01/PRED-SEC-01: `ANSWERED` không còn là success badge độc lập; phase 2
  bắt buộc claim-level citation và grounding precedence.
- PRED-SEC-02/PRED-SEC-03: source prompt injection là data-only; egress/PII
  deny-by-default và dossier mismatch fail trước retrieval/provider call ở phase 3.
- PRED-SEC-04: `run_code` arbitrary execution không nằm trong AI2 release path; nếu
  chưa có isolation thì disabled/`BLOCKED`, không gọi AST check là sandbox đủ.
- PRED-EVAL-01/PRED-EVAL-02: mirror-only PASS và parity skip bị loại khỏi release
  evidence; evaluator phải đối chiếu production entry trên payload có `snapshot_id`.
- PRED-EVAL-03: strategy card và mutation generator phải dùng cùng control-field
  vocabulary; mapping không hợp lệ làm release `BLOCKED`.
- PRED-PERF-01: large dossier phải có p95/p99/RSS/token/call budget và evidence,
  không chỉ có case logic PASS.
- PRED-EVAL-04: ground truth rỗng, expected field rỗng hoặc case P0 bị `SKIP` không
  được tạo denominator giả; phải fail config hoặc ghi `BLOCKED`.
- PRED-EVIDENCE-01: output query phải có `claims[]` và citation IDs kiểm tra được
  node/page/revision/scope/quote hash, không chỉ marker `citations: required`.
- PRED-DOC-01: raw UTF-8/NFC/NFD/control-char round-trip và report encoding phải là
  regression gate, không chỉ đọc file bằng UTF-8.

### Whole-Plan Consistency Sweep

- Files reread: `plan.md`, `phases/phase-1-contract-boundaries.md`,
  `phases/phase-2-evidence-pipeline.md`, `phases/phase-3-processing-runtime.md`,
  `phases/phase-4-release-verification.md`, `plan-graph.yaml`, research và
  red-team reports, và `reports/from-plan-reviewer-to-planner-red-team-eval-predict-amendments.md`.
- Decision deltas checked: 16 (producer-profile boundary, nested-table topology,
  independent relation, conditional replay/live, AI2 publish boundary, full-chain
  evidence spine, eval baseline status, parity enforcement, mutation vocabulary,
  citation/grounding precedence, prompt-injection/privacy boundary, performance
  budget and `run_code` denial, machine-checkable claim citations, eval ownership and
  UTF-8 round-trip).
- Reconciled stale references: 10 (table counts, old publish wording, old baseline
  release numbers, canonical-vs-producer terminology, evaluator maturity claims,
  parity skip semantics, mutation/performance gate semantics, phase ownership, empty
  ground-truth semantics, and citation/encoding verification semantics).
- Unresolved contradictions: 0.
- Phase graph check: `plan_graph.py` returned serial batches `P1 → P2 → P3 → P4`;
  no cycle or shared-batch conflict.

## Addenda bắt buộc sau eval-bootstrap và predict

- `ANSWERED` là trạng thái đã grounding, không phải chỉ có text answer. Invariant bắt
  buộc: `ANSWERED => grounded=true => mọi substantive claim có citation usable`; nếu
  không thì trả `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE`.
- Source text/metadata từ snapshot là untrusted data-only input; không được thay đổi
  system/developer policy, tool allowlist, scope hay output state.
- Dossier/member mismatch bị reject trước retrieval/provider call; egress/privacy
  thiếu approval là deny; `run_code`/arbitrary `compile`/`exec` bị disable hoặc
  `BLOCKED` trong AI2 path.
- Eval production không được dùng mirror-only fallback. Parity test phải có payload
  AI1 thật hoặc deterministic handoff fixture có `snapshot_id`; thiếu thì `NOT_RUN`/
  `BLOCKED`, không tính là pass.
- Sửa contract giữa strategy card và mutation generator: P0 rule phải trỏ tới control
  field có thật; mutation matrix phải tạo được và có kill evidence, nếu không release
  bị `BLOCKED`.
- CI phải chạy hai domain eval cùng invocation mà không `import file mismatch`; report
  phải phân biệt pass/fail/blocked/not-run/skipped và có p95/p99/RSS/token/call cho
  large dossier.
