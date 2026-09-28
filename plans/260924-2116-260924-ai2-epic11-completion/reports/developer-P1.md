# Developer report — P1 Baseline Contract

## Trạng thái

`BLOCKED` ở phase gate. Canonical targeted gate xanh; full suite và Backend gate chưa thể chạy do blocker môi trường/fixture có sẵn ngoài ownership P1. Không commit.

## Files changed

- `ai-service/app/contracts/wire.py:123` — thêm invariant boundary để DTO canonical từ chối mọi snapshot không phải `ai1.snapshot.v1`.
- `ai-service/tests/test_processing_wire_contract.py:239` — regression test cho version drift `ai1.snapshot.v3` sau khi digest đã được cập nhật.
- `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:22,106-121` — ghi rõ HMAC/idempotency, compatibility boundary v1/v3/v2 và fixture inventory/blocker.
- `plans/260924-2116-260924-ai2-epic11-completion/reports/developer-P1.md` — report này.

Không sửa `backend/src/contract_intelligence/shared/ai/canonical_processing.py` hoặc `backend/src/contract_intelligence/shared/ai/ai1_adapter.py`; code hiện có đã tạo `be.ai2.processing.request.v1`/`ai1.snapshot.v1` và giữ `ai1.snapshot.v3` ở compatibility boundary (`canonical_processing.py:204,252,278,338`; `ai1_adapter.py:21-34,194`). Không mở rộng logic hiện tại ngoài invariant RED đã chứng minh.

## TDD evidence

### RED

Command:

```text
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_processing_wire_contract.py::test_processing_request_dto_rejects_noncanonical_snapshot_version
```

Result: `1 failed`; `Failed: DID NOT RAISE ValueError` tại `tests/test_processing_wire_contract.py:248`. DTO đã nhận `ai1.snapshot.v3` khi snapshot digest được cập nhật khớp.

### Implement

Thay đổi tối thiểu tại `ai-service/app/contracts/wire.py:123`: `BeAi2ProcessingRequest.validate_membership` từ chối snapshot version khác `ai1.snapshot.v1`.

### GREEN / targeted regression

Command:

```text
cd ai-service
$env:PYTHONPATH=(Get-Location).Path
.\.venv\Scripts\python.exe -m pytest -q tests/test_processing_wire_contract.py tests/test_canonical_contract.py tests/test_happy_ai2_contract.py
```

Result: `34 passed` (2 pytest cache warnings do not affect assertions).

Additional legacy/HMAC regression probe: `15 passed, 1 error`; the error is pytest temp-directory permission (`WinError 5`), not an assertion failure.

## Remaining failures / blockers

- Backend phase command `cd backend; uv run pytest tests -q` — blocked before collection: `Failed to query Python interpreter` / `Access is denied (os error 5)`. A direct backend venv probe hit the same uv trampoline permission issue; no Backend code was changed to work around it.
- AI service full collection — `487 tests collected, 27 errors`; blockers are outside P1, including missing `scripts.validate_input_coverage` imported by `tests/test_input_coverage.py` and missing optional/runtime dependency `langfuse` in unrelated test modules. Do not claim full-suite green.
- `docs/code-standards.md` and `docs/system-architecture.md` are missing; implementation followed existing `docs/contracts` and code/test patterns. This limitation remains recorded, not silently resolved.
- Existing workspace is broadly dirty/untracked; no unrelated dirty file was modified by this phase.

## Acceptance mapping

| P1 acceptance | Evidence | Verdict |
|---|---|---|
| Mentor-approved canonical version | `plans/260924-2116-260924-ai2-epic11-completion/artifacts/plan-approval.yaml:1-8`; `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:106-116` | PASS |
| AI2 request boundary asserts `be.ai2.processing.request.v1` + `ai1.snapshot.v1` | `ai-service/app/contracts/wire.py:107,123`; `backend/src/contract_intelligence/shared/ai/canonical_processing.py:204,278,338`; targeted `34 passed` | PASS |
| Digest, idempotency, HMAC envelope and result contract tests remain covered | `ai-service/tests/test_processing_wire_contract.py:218-237,239-250,328-409`; `ai-service/tests/test_service_envelope.py`; `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:22` | PASS for targeted AI2 gate; Backend/full gate BLOCKED |
| `ai1.snapshot.v3` / legacy v2 are compatibility-only | `backend/src/contract_intelligence/shared/ai/ai1_adapter.py:21-34,194`; `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:106-116`; `ai-service/tests/test_legacy_compat.py` | PASS (boundary/documentation); parity/full regression BLOCKED |
| Fixture inventory and owner/action for missing support | `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:118-121`; this report's blockers | BLOCKED until owner restores missing support/dependencies |

P1 should not advance to later phases until the Backend interpreter/test command and the acknowledged full-suite fixture/dependency blockers have an owner disposition.
