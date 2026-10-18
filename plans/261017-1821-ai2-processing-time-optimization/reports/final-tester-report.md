# Final tester report - ai2-processing-time-optimization (uncommitted, feature/ai2-contract-graph)

Verdict: **PASS_WITH_RISK** (mọi gate chạy được đều xanh; 2 điểm cần lưu ý ở mục Rủi ro).

Basetemp: `C:\Users\dungs\.claude\jobs\ad849255\tmp\*` (không tạo .pytest-tmp-* mới trong repo). Không gọi LLM/OpenAI, không restart container, không sửa code.

## Kết quả

| # | Lệnh (cwd) | Kết quả |
|---|---|---|
| 1 | `AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live" --basetemp ...\tst-full` (ai-service) | `2450 passed, 3 skipped, 6 deselected, 25 warnings in 437.29s` - khớp kỳ vọng |
| 2a | Golden: `pytest -k golden` (ai-service/tests) | `14 passed, 2445 deselected in 59.71s` |
| 2b | Toàn bộ 6 file có "golden" (flag_off_regression, idp_integration, pairs_consent, pairs_flag_regression, pairs_idp_integration, pairs_wire) | `86 passed in 660.90s` |
| 3 | `uv run pytest -q deploy/tests` (repo root) | `48 passed in 8.75s` - khớp |
| 4 | Concurrency x3: `tests/test_contract_graph_pairs_parallel.py tests/test_runtime_concurrency.py` | Lần 1 `349 passed in 5.32s`; lần 2 `349 passed in 5.25s`; lần 3 `349 passed in 10.21s` - không flaky |
| 5 | ruff (xem dưới) | ai-service: sạch. deploy test: 1 lưu ý cấu hình |
| 6 | `PYTHONUTF8=1 python -m fixtures.seeded.score` | `dev: 46/46`, `heldout: 20/21`, `SCORE 1.0000` |

Ghi chú: "21 passed" trong ghi chú trước không tái hiện: marker/`-k golden` cho 14, cả 6 file golden cho 86. Không có marker `golden` đăng ký; số này phụ thuộc cách chọn test.

## Ruff (chỉ file bị đụng bởi plan)

- ai-service, 16 file .py (app/api/main.py, llm/client.py, pair_builder.py, pair_classifier.py, idp.py, runtime.py, 3 test sửa, 7 test mới):
  `ruff check` -> `All checks passed!`; `ruff format --check` -> `16 files already formatted`.
- `deploy/tests/test_ai2_pairs_env_passthrough.py` (file mới): ở repo root không có config ruff (line-length mặc định 88):
  `RUF100 Unused noqa directive (non-enabled: S506)` + `would be reformatted`. Với config của ai-service (`--config ai-service/pyproject.toml`, line-length 100): `check` sạch, `format --check` vẫn `1 file would be reformatted`. Các file deploy/tests có sẵn cũng không format sạch (3/4 file reformat) nên đây là quy ước chung, không phải hồi quy riêng; nhưng file mới chưa format theo ruff.
- Frontend `ProcessingTimeline.tsx` không thuộc phạm vi ruff/pytest (không chạy tsc/eslint trong lượt này).

## Rủi ro / lưu ý

1. `fixtures.seeded.score`: chạy thường (mặc định cp1252 trên Windows) **crash** `UnicodeEncodeError` khi in dòng FAIL có tiếng Việt; cần `PYTHONUTF8=1`. SCORE 1.0000 chỉ tính split `dev`; split `heldout` 20/21 có 1 FAIL:
   `FAIL [heldout] dossier-seeded-hd-test-002 semantic_difference @semantic_candidates: 3.1. <> 2.1. Thời gian giao hàng on deadline | []`
   Không có tài liệu nào ghi "20/21" nên chưa chứng minh là có sẵn từ trước. Thử đối chiếu baseline bằng worktree HEAD thất bại (không có venv, `ModuleNotFoundError: pydantic`); worktree tạm đã gỡ. Cần người xác nhận heldout 1 fail là pre-existing.
2. Format file deploy test mới (xem trên) - nên `ruff format` trước commit.

## Câu hỏi còn mở

- Heldout hd-test-002 fail có tồn tại trước thay đổi của plan không?
- Có muốn đăng ký marker `golden` để số "21" tái hiện được không?
