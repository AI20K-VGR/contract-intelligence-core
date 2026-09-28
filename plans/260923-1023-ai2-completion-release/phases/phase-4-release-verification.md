---
phase: 4
title: "Release Verification"
status: pending
plan: 260923-1023-ai2-completion-release
created: 2026-09-23
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 4 — Release Verification

## Overview

Đưa ba phase trước vào boundary có thể review: package `ai2.package.v1`, CLI replay
AI1 snapshot, hai domain evaluator (`ai2_contract_package`, `ai2_grounded_query`),
deterministic/live evaluation, contract registry, CI và docs. Phase này
không tự claim production readiness; nó tạo evidence để approve, defer hoặc reject.

Phase này cũng phải tách rõ candidate corpus khỏi golden evidence. 95 case người
dùng nhắc tới được ghi như `UNVERIFIED` cho tới khi có human review; manifest hiện
trong repo và các report lịch sử phải được reconcile trước khi ghi denominator.
Baseline hiện tại 10/10 contract và 20/20 query, cùng maturity 100, chỉ là
evaluator/mirror baseline vì parity còn skip và mutation generator đang blocked; không
được dùng làm release PASS.

## Context links

- `docs/ai2/AI2-12-review-and-release-gate.md`
- `docs/ai2/AI2-13-contract-context-and-independent-samples.vi.md`
- `docs/reviews/AI2-REVIEW-2026-09-22.vi.md:60-105`
- `ai-service/app/ai2/v1/__init__.py:11-80`
- `ai-service/app/pipeline/ai2_batch.py:39-201`
- `ai-service/scripts/run_ai2_ai1_files.py:21-47`
- `ai-service/scripts/live_eval.py:344-595`
- `.github/workflows/ai-service.yml`
- `package.json` và `scripts/check-contract-registry.mjs`
- `evals/eval_config.json`, `evals/eval_config.sha256`,
  `evals/cards/ai2_contract_package.json`, `evals/cards/ai2_grounded_query.json`
- `evals/eval_types/ai2_contract_package/`, `evals/eval_types/ai2_grounded_query/`
- `evals/scripts/run_production_evals.py`, `evals/scripts/run_grounded_query_evals.py`,
  `evals/scripts/mutation_matrix.py`, `evals/ci/production-evals.yml`,
  `.github/workflows/production-evals.yml`

## Files

**Modify:** `ai-service/app/ai2/v1/__init__.py`, `ai-service/app/pipeline/ai2_batch.py`,
`ai-service/scripts/run_ai2_ai1_files.py`, `ai-service/scripts/live_eval.py`,
`.github/workflows/ai-service.yml`, `ai-service/README.md`, `docs/ai2/README.md`,
`docs/ai2/AI2-12-review-and-release-gate.md`.

**Create or extend tests/artifacts:** `test_ai2_package.py`,
`test_ai1_ocr_lab_integration.py`, `test_demo_contract.py`, `test_eval_contract.py`,
`test_happy_ai2_contract.py`; local evidence dưới `ai-service/artifacts/` nhưng không
commit raw contract/PDF.

**Create or extend candidate/gold tooling:** `ai-service/scripts/audit_candidate_corpus.py`,
`ai-service/fixtures/gold/contract_type_profiles.json` và
`ai-service/tests/test_candidate_corpus_policy.py`.

**Create or extend eval integrity tests/artifacts:** tracked production parity fixture
có `snapshot_id`, large-dossier workload fixture và UTF-8 round-trip fixture; production
entry enforcement; test collection/import isolation;
scorer/P0 config validation; mutation matrix; large-dossier performance report; và
report phân biệt `PASS`, `FAIL`, `BLOCKED`, `NOT_RUN`, `SKIPPED`.

Replay hai absolute paths Downloads là evidence có điều kiện của môi trường local.
Nếu một path không tồn tại, report phải ghi `NOT_RUN` và lý do; không được biến
absence thành pass. Deterministic fixtures tracked trong repo là gate bắt buộc.

## Tests Before (regression coverage written BEFORE refactoring)

- [ ] Khóa API export/version, file/payload processing, independent result và
  `cross_document_findings=[]` tại `test_ai2_package.py:15-60`.
- [ ] Khóa deterministic evaluator, strict failure detection và citation scoring
  tại `test_eval_contract.py`, `test_demo_contract.py` và `scripts/live_eval.py`.
- [ ] Chạy registry và workflow-equivalent commands trước thay đổi; lưu stdout đầy
  đủ vào `tmp/`, không claim CI Linux từ local run.

## Implement

1. Làm rõ public entry point package v1; file API và in-memory API dùng cùng
   validation/lineage semantics, compatibility adapter là path khác.
2. Chuẩn hóa CLI flags/output: input paths, `--strict`, `--use-llm`, vector mode,
   report output và exit code phản ánh machine failure/review/not-run.
3. Tạo deterministic corpus/replay report có số mẫu, expected/actual state,
   citation valid rate, forbidden claims, blocked/insufficient và p95 nếu có. Không
   cho mirror-only output được tính là production result; parity thiếu payload thật
   phải là `NOT_RUN`/`BLOCKED`, không phải skip được cộng vào maturity.
   Release parity phải có tracked handoff fixture với `snapshot_id`, gọi đúng production
   entry, ghi `parity_executed` và yêu cầu giá trị > 0; zero parity hoặc parity skip
   làm verdict `BLOCKED`.
4. Giữ live gate opt-in; thiếu credential/provider là `NOT_RUN`/blocked có lý do,
   không tính là pass. Khi chạy thật, tách manual review khỏi machine score.
5. Đồng bộ workflow với command local: synthetic PDF từ tracked Markdown, offline
   pytest, schema registry; không đưa user PDF/JSON/credential vào repo.
6. Cập nhật README/docs để phân biệt canonical processing, compatibility result,
   `NEEDS_REVIEW`, local evidence và gap ngoài scope.
7. Ghi report riêng cho candidate corpus: case count/source/version, expected state
   provenance, reviewed/unreviewed denominator, promotion history và accuracy claim
   eligibility. Khi chưa có reviewed golden set, report chỉ cho phép claims về
   schema/citation/safety/regression.
8. Sửa contract strategy card ↔ mutation generator: P0 rule phải map được tới control
   field thật trong case matrix/production path; mismatch hiện tại giữa `target_axis`
   dimension và `expect` field phải fail loud, sau đó tạo mutation matrix và kill
   evidence cho mọi P0. Mỗi rule phải có `rule_id → production control → negative
   fixture → mutation`; mutation chỉ được tính khi kill trên production entry/scorer.
   Ground-truth rỗng, expected field rỗng hoặc P0 case bị skip phải fail config/blocked;
   `SKIP` không được tính vào denominator.
9. Chạy hai evaluator dưới cùng một pytest invocation mà không `import file mismatch`;
   khóa package/module namespace hoặc import mode trong CI.
10. Thêm production parity cho contract/query với payload AI1 thật hoặc deterministic
    handoff fixture có `snapshot_id`; mirror chỉ là oracle phụ trợ, không phải fallback
    release.
11. Khóa workload fixture và numeric budget cho large dossier trước benchmark:
    `max_pages`, `max_members`, `max_chunks`, `max_edges`, `max_citations`,
    `max_seconds`, `max_provider_calls`, `max_tokens`, `max_rss_mb`; report p95/p99
    và oracle partial/blocked khi vượt ngưỡng.

## Tests After (new behavior)

- [ ] Test strict CLI exit code khi batch input lỗi, citation invalid, forbidden
  claim, provider unavailable và live gate chưa chạy.
- [ ] Test package file/payload parity trên cùng fixture và deterministic report
  schema/denominator.
- [ ] Test cả hai eval domain trong cùng CI invocation không collection error; parity
  skip không được tính pass; config hash/card drift và P0 target mapping fail loud.
- [ ] Mutation matrix chạy được với control baseline và có kill evidence cho mọi P0;
  nếu không chạy được, verdict là `BLOCKED`, không phải maturity 100%.
- [ ] Production parity contract/query chạy trên payload AI1 thật hoặc deterministic
  handoff fixture có `snapshot_id`; mirror-only run không đủ.
- [ ] Ground truth không rỗng, mọi case P0 có expected assertion thật; `SKIP`/empty
  không làm tăng maturity hoặc denominator.
- [ ] UTF-8/NFC/NFD/control-char round-trip và raw/citation/report encoding đều có
  deterministic evidence.
- [ ] Test synthetic PDF generation + full offline suite + registry theo thứ tự CI.
- [ ] Nếu có credential, chạy live corpus riêng; nếu không, lưu `NOT_RUN` với lý do,
  không đánh dấu release pass.
- [ ] Candidate corpus policy test chứng minh case `UNVERIFIED` không được dùng làm
  ground truth; golden promotion cần reviewer evidence và không sửa raw input.

## Regression Gate

`Set-Location ai-service; .venv\Scripts\python.exe scripts/make_sample_pdf.py; .venv\Scripts\python.exe -m pytest -q -m "not live" --basetemp ..\tmp\ai2-release-basetemp; Set-Location ..; node scripts/check-contract-registry.mjs; .venv\Scripts\python.exe -m pytest -q evals\eval_types\ai2_contract_package\tests evals\eval_types\ai2_grounded_query\tests`

Optional live gate, chỉ khi credential đã được phê duyệt:
`Set-Location ai-service; .venv\Scripts\python.exe scripts/live_eval.py --mode live --vector-mode off --strict --review-output --output artifacts/ai2-live-audit`

Exact two-file replay, nếu hai path còn tồn tại:
`Set-Location ai-service; .venv\Scripts\python.exe scripts/run_ai2_ai1_files.py --input "C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json" --input "C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json" --strict --output artifacts/ai2-two-input-replay-20260923.json`

## Post artifacts

Ghi `plans/260923-1023-ai2-completion-release/artifacts/verification-P4.json`
với exact commands, denominator, pass/review/fail/not-run/skipped/blocked, replay presence,
parity source, evaluator mode, collection status, mutation coverage, p95/p99/RSS/token/call,
registry result, live credential state và verdict. Sau đó tạo
`plans/260923-1023-ai2-completion-release/artifacts/review-decision.json` chỉ
sau human review; không coi `198 passed` baseline là evidence post-cook.

## Success

- [ ] Package/CLI/docs/CI nói cùng một contract và command.
- [ ] Offline release gate xanh với evidence artifact; skipped/not-run được ghi rõ.
- [ ] Hai eval domain chạy được cùng CI, không collection mismatch; parity/mutation và
  performance evidence có trạng thái trung thực, không dùng maturity 100% thay cho
  production correctness.
- [ ] Live result, nếu có, không machine failure/forbidden claim/invalid citation;
  `NEEDS_REVIEW` của input không bị hạ thành PASS.
- [ ] Có quyết định human review: approve release gate, defer vì gap ngoài scope,
  hoặc reject kèm finding có reproduction.

## Risks

Live provider và user OCR-lab có thể không tái lập do rate limit/credential. Không
đưa live vào offline gate; tách evidence và giữ release decision phụ thuộc gate thực
đã chạy.
