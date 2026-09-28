---
phase: 3
task: ST-046
title: "L0→L3 query reasoning + grounding"
status: pending
plan: 260924-2201-260924-ai2-epic11-gap-closure
created: 2026-09-24
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — ST-046: Query L0→L3 + grounding

## Mục tiêu

Đóng riêng ST-046: nối Backend dossier query vào evidence projection/context có composite key `(tenant_id, dossier_id, snapshot_digest)`, giữ FourLayerReasoner L0→L3, grounding bắt buộc trước `ANSWERED`, và fail-closed khi thiếu/stale/cross-tenant evidence. Đây là commit bằng chứng C3.

## Files / ownership

- **AI2:** `ai-service/app/api/main.py`, `ai-service/app/reasoning/stack.py`, `ai-service/app/reasoning/l1_retrieval.py`, `ai-service/app/reasoning/l3_ground.py`, `ai-service/app/reasoning/vector_recall.py`.
- **Backend:** `backend/src/contract_intelligence/api/v1/dossiers.py`, `backend/src/contract_intelligence/infrastructure/ai_adapters.py`, query DTO/context serializer.
- **Tests:** tạo `ai-service/tests/test_st046_query_grounding.py` và Backend query contract/E2E test nếu thiếu.
- Không sửa IndexContribution/reviewer trong commit này.

## TDD

- **RED:** valid evidence phải đi L0→L3; metadata-only, missing/stale digest, khác tenant/dossier, invalid citation, unsupported planner và embedding failure phải trả state an toàn.
- **Implement:** thêm projection lookup/serialization và Backend forwarding; scope filter trước retrieval; bounded evidence, redacted logs; giữ retrieval exact→structured→BM25 và vector policy.
- **GREEN:** ST-046 targeted suite và C1/C2 regression.

## Success / evidence

- [ ] Backend→AI2 contract/E2E payload có tenant+dossier+digest và evidence context.
- [ ] `ANSWERED` chỉ sau L3 grounding; missing/stale/cross-tenant trả state an toàn.
- [ ] Không raw PDF/full dossier leak; embedding disabled/budget/egress/provider failure không phá deterministic path.
- [ ] Tạo `verification-ST-046.json` gồm payload/trace, commands, test count, exit code.
- [ ] Commit duy nhất của task: `feat(ai2): complete ST-046`; kiểm tra `git show --stat --check <C3>`.

## Lệnh kiểm tra

```powershell
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_l0.py tests/test_hybrid_retrieval.py tests/test_citations.py tests/test_st046_query_grounding.py
cd ..\backend
uv run pytest -q tests -k "query or dossier or ai2" --maxfail=1
```

## Rollback

`git revert <C3>` rồi chạy lại C1/C2 regression; giữ metadata-only caller fail-closed.
