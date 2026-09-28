# Red-team review — AI2 gap closure

Phạm vi persona: Security Adversary, Failure Mode Analyst, Maintainer 6-months-later, Bad-day Operator. Review dựa trên plan/phase files và audit code cục bộ; mỗi finding có anchor hoặc lệnh tái lập.

| ID | Sev | Failure scenario | Evidence | Suggested fix |
|---|---|---|---|---|
| RT-01 | H | Backend query vẫn gửi metadata-only nên phase 2 có thể “xanh” ở AI2 unit test nhưng E2E không có evidence. | `backend/src/contract_intelligence/api/v1/dossiers.py:184-222`; `ai-service/app/api/main.py:669-696` | Bắt buộc phase 2 có Backend→AI2 contract/E2E test với composite scope và projection payload; phase 4 không nhận unit-only PASS. |
| RT-02 | H | Projection lookup chỉ kiểm tra dossier mà bỏ tenant hoặc digest, gây cross-tenant/stale answer. | `plans/260924-2201-260924-ai2-epic11-gap-closure/phases/phase-2-query-evidence-wiring.md` yêu cầu composite key; `ai-service/app/reasoning/l3_ground.py:13-236` validate citation sau retrieval | Thêm negative tests khác tenant/dossier/digest trước retrieval và assert state fail-closed; ghi scope filter là precondition trong implementation. |
| RT-03 | H | Reviewer gate không có interface/storage thực tế, nhưng plan vẫn có thể bị đánh dấu hoàn tất bằng fake approve. | `backend/src/contract_intelligence/worker.py:382-410`; `backend/src/contract_intelligence/shared/ai/persistence.py:659-790`; phase 3 Risk | Phase 3 phải có owner + API/command + persistence anchor; nếu chưa có thì ghi BLOCKED/NEEDS_REVIEW, không tạo fake reviewer PASS. |
| RT-04 | M | Retry processing/query có thể tạo duplicate proposal hoặc đổi active pointer ngoài approval. | `ai-service/app/pipeline/index.py:6-45`; phase 3 TDD | Test idempotency key theo tenant/dossier/digest/contribution; assert duplicate không mutation active và audit giữ nguyên. |
| RT-05 | M | Full suite bị nhầm là code failure hoặc bị né bằng cách bỏ test do môi trường temp-dir/fixture/interpreter. | Repro: `cd ai-service; .\.venv\Scripts\python.exe -m pytest ...` hiện có `PermissionError` ở `C:\Users\dungs\AppData\Local\Temp\pytest-of-dungs`; Backend probe thiếu `.venv`/uv interpreter | Phase 4 bắt buộc lưu command, exit code, test count, blocker owner; không đổi assertion/skip silent; chỉ PASS sau khi environment gate xanh. |
| RT-06 | M | Thay đổi query boundary gửi quá nhiều raw evidence vào telemetry/prompt dù reasoner chỉ cần bounded context. | `ai-service/app/reasoning/vector_recall.py:169-304`; plan acceptance yêu cầu không leak raw/full dossier | Thêm test payload/log redaction và giới hạn evidence unit; audit serialized request trước khi gọi provider. |

## Verdict

REVISE-BEFORE-APPROVAL. Kế hoạch có hướng đúng nhưng chỉ được duyệt sau khi các finding RT-01…RT-06 được phản ánh trong phase acceptance và verification artifact.
