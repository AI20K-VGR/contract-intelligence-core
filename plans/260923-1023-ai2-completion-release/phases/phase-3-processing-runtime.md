---
phase: 3
title: "Processing Runtime"
status: pending
plan: 260923-1023-ai2-completion-release
created: 2026-09-23
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Processing Runtime

## Overview

Đảm bảo xử lý AI2 có giới hạn và an toàn khi LLM/vector/provider lỗi hoặc chạy lại:
budget thời gian/call/token, egress fail-closed, retry có kiểm soát,
lease/idempotency đúng tenant/dossier/attempt, persist review overlay không sửa raw
và chỉ trả proposal/review evidence cho tới khi gate publish authoritative ngoài
AI2 cho phép.

## Context links

- `docs/ai2/AI2-00-pipeline-overview.vi.md:11-29`
- `docs/reviews/AI2-REVIEW-2026-09-22.vi.md:60-86`
- `ai-service/app/pipeline/idp.py:39-423`
- `ai-service/app/pipeline/runtime.py`
- `ai-service/app/tools/store.py:24-80`
- `ai-service/app/tools/persist.py`
- `ai-service/app/api/main.py`
- `ai-service/tests/test_processing_wire_contract.py:203-313`
- `ai-service/tests/test_job_store.py:23-133`
- `ai-service/tests/test_persist.py:7-42`

## Files

**Modify:** `ai-service/app/pipeline/idp.py`, `runtime.py`, `tools/store.py`,
`tools/persist.py`, `api/main.py`, `reasoning/vector_recall.py`, `pipeline/index.py`.
`tools/gateway.py`, `sandbox/__init__.py`, `reasoning/l2_plan.py` và `llm/client.py`
chỉ được chạm để deny/disable `run_code`, enforce egress hoặc ngăn source text điều
khiển tool; không xây hard process isolation trong phase này.

**Create or extend tests:** `test_processing_wire_contract.py`, `test_job_store.py`,
`test_persist.py`, `test_hybrid_retrieval.py`, `test_api.py`,
`test_service_envelope.py`.

## Tests Before (regression coverage written BEFORE refactoring)

- [ ] Khóa retry/fallback/egress denial/budget tại
  `test_processing_wire_contract.py:242-313`.
- [ ] Khóa SQLite tenant/idempotency/lease/terminal state tại
  `test_job_store.py:23-133`.
- [ ] Khóa session roundtrip và vector snapshot/citation checks tại
  `test_persist.py` và `test_hybrid_retrieval.py:50-76`.

## Implement

1. Truyền budget/policy từ request tới runtime bằng một object/version pin duy nhất;
   phân biệt processing budget với embedding budget và ghi issue có mã khi chạm trần.
2. Retry provider chỉ cho lỗi retryable, bounded theo budget; timeout/failure trả
   partial deterministic hoặc `NEEDS_REVIEW`/`BLOCKED`, không mất unit đã xong.
3. Egress denial chặn provider trước khi gọi; vector chỉ bổ sung recall, phải filter
   snapshot/model/dimension và citation-validate lại.
4. Bảo toàn tenant+dossier+attempt trong job store; cùng idempotency key chỉ trả lại
   job tương ứng, khác dossier/tenant/payload bị từ chối; claim lease chỉ một lần.
5. Persist raw input/result/review overlay tách nhau; re-run đổi fingerprint/profile
   làm review cũ stale và không sửa raw hoặc tự mở publish.
6. Giữ API polling/envelope strict; late completion hoặc sai scope không ghi result
   terminal vào job khác.
7. Dossier/member mismatch phải bị reject trước retrieval/provider call; không xử lý
   tiếp rồi mới gắn `NEEDS_REVIEW`. Egress thiếu approval phải deny-by-default; raw PII
   chỉ được lưu/trả theo policy retention/redaction đã khai báo.
8. AI2 path không cho phép `run_code`/arbitrary `compile`/`exec`; nếu chưa có process
   và resource isolation thật thì tool phải disabled hoặc trả `BLOCKED` có mã ổn định.
9. Đo workload large dossier theo budget đã khóa: latency p95/p99, peak RSS,
   token/call, số chunk/candidate/edge/citation. Trước khi benchmark phải pin numeric
   quota cho pages/members/chunks/edges/citations/seconds/provider calls/tokens/RSS;
   vượt budget phải dừng an toàn và giữ partial result hoặc `BLOCKED` theo nguyên nhân.

## Tests After (new behavior)

- [ ] Test timeout/rate-limit liên tiếp, max calls, max seconds và partial success;
  assert no unbounded retry/no dropped successful unit.
- [ ] Test cross-tenant, cross-dossier, attempt replay, payload mismatch và double
  claim; assert stable error code và không rò job/result.
- [ ] Test rerun sau fingerprint/profile đổi làm review stale, proposal không thành
  authoritative publish và vector miss không phá local query.
- [ ] Test source prompt-injection, missing egress approval, raw PII policy và
  `run_code` deny-by-default; dossier mismatch không tạo provider call.
- [ ] Benchmark dossier lớn và assert p95/p99, peak RSS, token/call, candidate/edge
  count cùng trạng thái khi chạm budget.

## Regression Gate

`Set-Location ai-service; .venv\Scripts\python.exe -m pytest tests/test_processing_wire_contract.py tests/test_job_store.py tests/test_persist.py tests/test_hybrid_retrieval.py tests/test_api.py tests/test_service_envelope.py -q --basetemp ..\tmp\ai2-phase3-basetemp`

## Post artifact

Ghi `plans/260923-1023-ai2-completion-release/artifacts/verification-P3.json`
với exact commands, budget/egress/lease/idempotency checks, raw immutability,
review-staleness và verdict. Không ghi hoặc kiểm thử một AI2-owned authoritative
publish action; đó là boundary của Backend ngoài scope.

## Success

- [ ] Runtime kết thúc trong budget hoặc trả trạng thái/error có mã, không treo hay
  gọi provider ngoài policy.
- [ ] Job store chứng minh tenant isolation, idempotency, lease và terminal persistence.
- [ ] Rerun/review/vector không thay raw snapshot và không vượt publish gate.

## Risks

Runtime dễ tạo race hoặc làm khác semantics API. Giữ thay đổi nhỏ, kiểm tra SQLite
thật trong test và không mở rộng sang queue Backend.
