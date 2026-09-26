# AI2 — mốc nghiên cứu đầu (chưa phải plan)

**Ngày:** 2026-09-26
**Trạng thái:** đang mở. Chưa lập plan, chưa cook.

## Việc đã thấy trên code hôm nay

- Runtime nằm ở `ai-service/app/` (pipeline, reasoning L0–L3, tools, API). Gói public: `app/ai2/__init__.py` (`process_files`, `process_payloads`, `process_payloads_full`).
- Tài liệu gap `docs/ai2/AI2-06-implementation-gap.vi.md` (20–23/09) ghi FR-PROFILE là Partial, "registry sáu profile chưa khóa trong code". Code hiện tại đã có enum và registry đủ sáu loại trong `ai-service/app/contracts/contract_profiles.py` (`SALES` từ dòng 119, `SUPPLY_SERVICE` từ dòng 133, và các loại còn lại trong cùng dict `_PROFILES`). Gap doc này **không còn là bản đồ trạng thái**.
- Câu hỏi tự do: `app/reasoning/stack.py` khoảng dòng 221 vẫn hạ `unscoped` kiểu "ổn không / is this valid" về `INSUFFICIENT_EVIDENCE` và xóa citation. Đó là chốt an toàn, chưa phải trả lời tự do có grounding.
- Ma trận EC-001..EC-056 trong `docs/ai2/AI2-04-edge-case-test-matrix.vi.md` và cột Done/Mock của AI2-06 là tài liệu 20/09. Chưa chạy lại fixture trong phiên này, nên trạng thái từng EC vẫn là giả thuyết cho đến khi có lệnh test.

## Hướng hoàn thiện đang được kiểm, chưa chốt

Giữ pipeline deterministic (L0 luật, L3 extractive, không chọn bản đúng pháp lý). Không đổi sang agent tự do viết câu trả lời. Việc còn lại là đóng các ô Mock của ma trận bằng test thật, không bằng cách nới gate.

## Probe 2026-09-27

`uv run python` gọi `run_idp` cho 56 fixture `EC-*`: 0 exception, 35 khớp `expected_state`, 21 lệch. Lệch nguy hiểm (expected REVIEW, job PASS, không issue, không có query): EC-005, EC-007, EC-031, EC-033, EC-047. Các lệch còn lại chủ yếu là pipeline trả `NEEDS_REVIEW` khi catalog ghi PASS, tức thắt chặt hơn chứ không bịa kết quả.

`tests/test_catalog.py`, `test_l0.py`, `test_reasoning.py`: 61 passed, 3 skipped. Catalog chỉ kiểm hình dạng fixture, không chạy `run_idp` cho từng EC.

## Đã sửa trong phiên này

`app/pipeline/edge_flags.py` gắn issue và `NEEDS_REVIEW` cho năm case im lặng. Budget hết vẫn chạy extraction local nhưng không còn PASS khi không có LLM (`idp.py`). Test `tests/test_ec_silent_pass.py` đỏ trước khi sửa, xanh sau. Cùng `test_catalog`, `test_l0`, `test_reasoning`, `test_result_regressions`: 85 passed.

## Đã sửa thêm

EC-050 (`embedding_budget_exceeded`) và EC-055 (`egress_approved` false) trước đó ra `NEEDS_REVIEW` với `handoff_issues` rỗng. `run_idp` giờ ghi `EMBEDDING_BUDGET_EXCEEDED` và `EGRESS_DENIED` ở trạng thái `BLOCKED`, job vẫn `SUCCEEDED` để extraction cục bộ không bị cắt. Test `tests/test_ec_policy_block.py`. Suite liên quan: 47 passed.

## Hướng đã chốt

Giữ pipeline deterministic và cổng citation. Không ép catalog `PASS` khi fixture không có `source_hash` (`app/pipeline/citations.py` dòng 86–88). Câu tiếng Anh "seller tax code" được map sang `mst_seller` trong `app/reasoning/query.py`.

Plan: `plans/260927-ai2-completion/plan.md`.

