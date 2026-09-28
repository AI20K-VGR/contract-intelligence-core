# Báo cáo developer P4 — execution adapters

## Kết quả

Phase P4 đã hoàn tất ở mức `PASS_WITH_LIMITATIONS`. Fixture P4 đã được sửa để dùng `ExecutionContext` đầy đủ `actor_id` và `generation_id`, cùng `DossierRecord`/`ToolEnvelope` hợp lệ; không làm yếu contract runtime.

## File đã đổi

- `ai-service/app/pipeline/execution.py` — boundary typed, scope/cancellation/lease/error mapping và tool-result validation (đã có trong workspace từ đầu phase).
- `ai-service/app/pipeline/adk_adapter.py` — optional ADK contract/adapter dependency-free (đã có trong workspace từ đầu phase).
- `ai-service/tests/test_p4_execution_adapters.py` — fixture hợp lệ và acceptance tests P4.
- `plans/260923-1023-ai2-long-running-architecture/artifacts/p4-adapter-contract.json` — verification artifact.
- `plans/260923-1023-ai2-long-running-architecture/reports/developer-P4.md` — báo cáo này.

## Lệnh và kết quả test

```text
ai-service/.venv/Scripts/python.exe -m pytest tests/test_p4_execution_adapters.py tests/test_p0_contract_baseline.py tests/test_p1_canonical_model.py tests/test_p2_hitl_state.py tests/test_p3_persistence_events.py -q --basetemp=.pytest-p4-final
41 passed, 1 warning
```

Focused P4 riêng cũng đã đạt `8 passed`. Warning duy nhất là pytest không ghi được một số cache entry do quyền thư mục; không có test failure.

## Coverage acceptance

Đã có test cho pipeline success, tenant scope mismatch, timeout, cancellation, lease fencing trước/sau execution, callback duplicate/out-of-order, ADK version mismatch, artifact mapping, citation bắt buộc và side-effect approval. P0–P3 regression liên quan đạt xanh trong cùng lệnh trên.

Coverage gap được ghi nhận: chưa có test trực tiếp cho nhánh ADK thiếu artifact hoặc exception bất ngờ từ runtime ADK; cũng chưa có provider ADK thật.

## Limitation

ADK vẫn là interface optional, chưa thêm dependency `google.adk` hoặc provider integration. Chưa có production worker restart/external-tool integration test; A2A và P5 không nằm trong phase này. `hs-run.cmd` không chạy được trên Windows hiện tại do launcher bị lỗi encoding, nên verification dùng trực tiếp `.venv` của repo.
