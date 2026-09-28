# AI2 Epic 11 — chẩn đoán collection blockers

## Tóm tắt

- **Trạng thái:** Đã xác định nguyên nhân; chưa sửa mã nguồn.
- **Nguyên nhân đã xác nhận:** `HEAD=cb08add2c5b6ae19c84b814624fe1bc434edea44` không chứa ba module mà bộ test AI2 hiện tại import. Các test tương ứng đang có trong worktree dưới dạng untracked và khớp byte với bản ở `73f3cc0`.
- **Tác động:** Full suite dừng ở collection với exit code `2`; `671 tests collected`, `3 errors`, không có test nào được thực thi.

## Repro chính xác

Từ `ai-service`, lệnh đã chạy:

```text
.\.venv\Scripts\python.exe -m pytest -q
```

Kết quả quan sát được:

```text
ERROR tests/test_ai1_handoff_serializer.py
ERROR tests/test_ai2_hardening.py
ERROR tests/test_input_coverage.py
!!!!!!!!!!!!!!!!!!! Interrupted: 3 errors during collection !!!!!!!!!!!!!!!!!!!
26 warnings, 3 errors in 4.78s
EXIT_CODE=2
```

Probe cô lập bằng `--collect-only -q` cũng tái hiện ổn định: `671 tests collected, 3 errors in 3.28s`.

Lệnh chuẩn của project là `uv run --extra dev pytest` tại `ai-service/Makefile:10`. Probe `uv` bị chặn trước pytest bởi cache/network của môi trường này (`C:\tmp\uv-cache` access denied; cache tạm tiếp theo không tải được `ruff==0.16.7`). Local `.venv` đã chạy được pytest và cho đúng lỗi collection ở trên.

## Expected vs actual

| Import đang yêu cầu | Test gọi | Actual tại worktree |
|---|---|---|
| `contract_ocr.application.use_cases.ai2_snapshot_handoff.to_ai2_snapshot_v1` | `ai-service/tests/test_ai1_handoff_serializer.py:3` | `ai2_snapshot_handoff.py` không tồn tại; `ModuleNotFoundError` |
| `scripts.live_eval._citation_errors` | `ai-service/tests/test_ai2_hardening.py:8` | `scripts/live_eval.py` không tồn tại; `ModuleNotFoundError` |
| `scripts.validate_input_coverage.validate_manifest` | `ai-service/tests/test_input_coverage.py:8` | `scripts/validate_input_coverage.py` không tồn tại; `ModuleNotFoundError` |

`ai-service/pyproject.toml:66` đặt `pythonpath = ["."]`, nên khi file có mặt các import trên phải resolve từ chính checkout này; đây không phải lỗi package path suy đoán. Probe filesystem xác nhận cả ba path trả về `False`.

## Root cause và “why now”

### Bằng chứng trực tiếp

- Cây `HEAD` không có ba path; cây `origin/feature/ai2-integration` có đủ cả ba.
- `git merge-base --is-ancestor 73f3cc0 HEAD` trả exit `1`; merge-base là `81c55e4761a455120bb5959d481f33b352dba2a3`.
- `HEAD` là merge `cb08add` trên dòng `feature/code-full`; `73f3cc0` là `feat(ai2): add canonical pipeline and evaluation gates` trên dòng AI2 remote.
- `git log --diff-filter=D HEAD -- <ba path>` không trả commit delete nào. Vì vậy đây không phải bằng chứng của một commit hiện tại xóa file; là mismatch giữa dòng commit đang checkout và overlay test AI2.
- Ba test untracked trong worktree có Git blob hash trùng chính xác với `73f3cc0`:
  - `test_ai1_handoff_serializer.py` → `ed1f517a8c832d2b8eac93d4c9fa623aa4fc65b7`
  - `test_ai2_hardening.py` → `0e9d35bbe6e66d1a06d744d74ed3224207ce457e`
  - `test_input_coverage.py` → `5242e7a4e60a350d58bd93eb0d5ab899a57f42b9`

### Kết luận nhân quả

**[OBSERVED]** Suite đang collection các test AI2 giống commit `73f3cc0`, nhưng filesystem import lại là checkout `cb08add` cộng với overlay untracked; ba implementation module không có trong checkout đó.

**[DERIVED]** Khi pytest import module test, ba import đầu vào chạm ngay vào các path vắng nên collection bị fail trước execution. Đây giải thích đồng thời cả ba lỗi và lý do lỗi xuất hiện “bây giờ”: test/fixture AI2 đã hiện diện trong worktree, còn implementation commit `73f3cc0` chưa hiện diện trong `HEAD` đang chạy.

## Kiểm tra `73f3cc0`

Có: commit `73f3cc0` chứa đúng các phiên bản dự kiến.

- `ai-service/src/contract_ocr/application/use_cases/ai2_snapshot_handoff.py` có symbol `to_ai2_snapshot_v1`; blob `cd8c7758b9ca1e58a8d4a8c8fab8f677fb16eb83`.
- `ai-service/scripts/live_eval.py` có symbol `_citation_errors`; blob `e39dc17ff4458b1a065ae85a6f40ad841f8cd9e9`.
- `ai-service/scripts/validate_input_coverage.py` có symbol `validate_manifest`; blob `60ad9e85cc2b46d9cbd1acb2ca4bab51add4031b`.

Lịch sử cũng khớp mục đích: `6319bc5` thêm hai script; `73f3cc0` cập nhật `live_eval.py` và thêm `ai2_snapshot_handoff.py`, đồng thời vẫn giữ `validate_input_coverage.py` trong tree.

## Blast radius

1. Full `ai-service` pytest gate bị chặn ở collection; 671 node được discover nhưng không test nào chạy.
2. Ba test module nêu trên không thể collect.
3. Các entrypoint/importer dùng `live_eval.py` hoặc `validate_input_coverage.py` sẽ không khởi động trong checkout hiện tại; handoff serializer AI1→AI2 cũng không import được.
4. Không có bằng chứng từ probe này rằng các test không phụ thuộc ba module đã fail runtime; lỗi hiện tại xảy ra sớm hơn, tại collection.

## Failing repro test

Không tạo test mới theo yêu cầu “Do not modify files”. Lệnh full-suite ở trên là failing repro trực tiếp, với exit code và traceback đầy đủ; bước sửa thuộc phạm vi `hs:fix`, không nằm trong chẩn đoán này.
