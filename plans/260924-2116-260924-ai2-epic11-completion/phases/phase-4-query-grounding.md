---
phase: 4
title: "Query Grounding"
status: pending
plan: 260924-2116-260924-ai2-epic11-completion
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 4 — Query L0→L3 & Grounding

## Overview

Đóng ST-046: query đi qua L0 deterministic, L1 retrieval theo exact → structured → BM25; embedding chỉ là optional vector recall có gate; L2 chỉ được lập plan compare/cascade; L3 grounding bắt buộc trước output. Query không có evidence projection, citation hợp lệ hoặc scope hợp lệ phải fail-closed.

## Requirements

- Query phải có composite scope key `(tenant_id, dossier_id, snapshot_digest)` và evidence projection/context hợp lệ.
- `ANSWERED` chỉ hợp lệ sau L3; thiếu/invalid citation phải trả state an toàn.
- Embedding không được thay thế deterministic retrieval và phải chịu budget/egress/model gate.

## Implementation Steps

1. Viết RED matrix cho L0/L1/L2/L3, states, ACL, stale digest, cross-tenant và vector failures.
2. Thêm/siết evidence projection lookup theo composite scope key và scope filter trước retrieval.
3. Enforce L2 allowlist và L3 grounding trước serialization; giữ trace/budget/error state.
4. Chạy phase 1–3 regression, test reprocess v1→v2 khiến query v1 fail closed và ghi `verification-P4.json`.

## Files

**Modify:** `ai-service/app/api/main.py:669`, `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/stack.py:15`, `ai-service/app/reasoning/l1_retrieval.py`, `ai-service/app/reasoning/l2_plan.py`, `ai-service/app/reasoning/l3_ground.py`, `ai-service/app/reasoning/vector_recall.py:169`, query context/index persistence.

**Create/Modify tests:** `ai-service/tests/test_query*.py`, `test_hybrid_retrieval.py`, grounding/citation/state tests, vector budget/egress/provider failure tests.

## TDD (Tests Before → Implement → Tests After → Regression Gate)

- **Tests-before (RED):** exact lookup; structured lookup; BM25 fallback; compare/cascade planner; unsupported planner intent; L3 citation mismatch; no evidence; stale digest; ACL scope; embedding disabled/budget exceeded/egress denied/provider error; expected states `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`.
- **Implement:** thêm evidence projection keyed by tenant/dossier/digest hoặc explicit canonical query context; enforce L3 before `ANSWERED`; preserve retrieval trace and relation issues; vector recall chỉ bổ sung, không thay exact path.
- **Tests-after:** `cd ai-service; $env:PYTHONPATH=(Get-Location).Path; .\.venv\Scripts\python.exe -m pytest -q tests/test_query* tests/test_hybrid_retrieval.py tests/test_citations.py tests/test_contract_context.py`.
- **Regression gate:** phase 1–3 suites xanh; verify no raw PDF/full dossier leak vào prompt/logs; verify bounded retrieval and budget counters.

## Success

- [ ] Query trace chứng minh layers used và retrieval order.
- [ ] `ANSWERED` chỉ xuất hiện khi L3 validate claims/citations.
- [ ] Compare/cascade dùng relation/facts đúng scope; câu hỏi unsupported không bị planner tự mở rộng.
- [ ] Embedding failure/disabled không làm hỏng deterministic retrieval; budget/egress gate hoạt động.

## Risk Assessment

Evidence projection có thể stale sau snapshot mới. Mitigation: digest key bắt buộc, stale check trước retrieval, trả `INSUFFICIENT_EVIDENCE` và yêu cầu processing lại.
