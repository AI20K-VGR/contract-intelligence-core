# Developer P1 — Pair Label Dataset

- Commit: `474cfdd` (tooling + 51 test), `0f499b4` (manifest + báo cáo l2-p1). Chưa push.
- RED: 6 file test, `6 errors during collection` (`ModuleNotFoundError: evals.contract_graph.pairs`).
- Probe OBSERVED: requested `gpt-4o-mini`, served `gpt-4o-mini-2024-07-18`, family `openai`, 187 token, 3687.8 ms.
- Test: evals 128 passed (77 + 51; main chạy lại OBSERVED 128 passed); ai-service 13 failed / 1290 passed / 44 skipped = VL-2.
- Dataset: 21 nguồn (SALES 10, SUPPLY_SERVICE 11), heldout 14 / dev 7, nhiễm bẩn 0; pool 1021 (S1 287, S2 22, S3 712), sha `7ff65050…6d005b` ổn định qua 2 hash seed; nhãn 1021/1021, invalid 0; HG-1 ước 216 ≤ 380; manifest sha `8d39b774…fe45ce`, `verify` exit 0.
- Mối lo:
  1. `html_to_text` giữ phần sau hợp đồng (bình luận/FAQ/footer) trên 14/15 nguồn web ⇒ 114/1021 cặp dính node cuối > 2000 ký tự. Chưa sửa (ngoài spec).
  2. `family()` dùng `o\d+` thay `o\d*` (tránh fail-open "openchat"/"olmo").
  3. ruff I001 ở 2 file test có sẵn (`test_cg_pipeline_predictor.py`, `test_cg_resolver_eval.py`), không do P1.
