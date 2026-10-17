# R5 — Các guard chất lượng hiện có và lệnh chạy chính xác

Tất cả lệnh chạy từ `ai-service/`. Lệnh test đã được document là `uv run pytest -q` (`ai-service/pyproject.toml:60-67`). Trên Windows, nếu không dùng uv thì chạy `.venv/Scripts/python -m pytest`.

## 1. Bảng guard

| Guard | Lệnh | Chứng minh được gì | Có chạm LLM? | Bắt được hồi quy P1/P2? |
|---|---|---|---|---|
| Unit classifier | `uv run pytest -q tests/test_contract_graph_pair_classifier.py` | batch/stop/validator/events/cổng K-a (vd `:154-160`, `:383-462`) | Không (fake `Runtime`, `:38-69`) | **P1: có**, sau khi thêm test so sánh output giữa concurrency 1 và 4 |
| Builder/consent/integration của pairs | `uv run pytest -q tests/test_contract_graph_pair_builder.py tests/test_contract_graph_pairs_consent.py tests/test_contract_graph_pairs_idp_integration.py tests/test_contract_graph_pair_projection.py tests/test_contract_graph_pairs_wire.py` | gate, thứ tự relation, coverage, wire | Không | Có (thứ tự decision → relation) |
| Runtime/budget/retry | `uv run pytest -q tests/test_st067_bounded_jobs.py tests/test_frame_context_runtime.py tests/test_context_budget_fairness.py` | 429/5xx/quota/deadline/budget | Không (lỗi giả lập, `test_st067_bounded_jobs.py:42-50`) | Có, cho phần sửa runtime (lock, kiểm tra trong reserve) |
| Độ bền trace | `uv run pytest -q tests/test_contract_graph_trace_durability.py` | fence/append/projection | Không | P0 |
| Golden flag-off | `uv run pytest -q tests/test_contract_graph_flag_off_regression.py tests/test_contract_graph_pairs_flag_regression.py` | sha256 của result/wire/record (`scripts/capture_idp_golden.py:1-12`) | Không | **P0**: sẽ đỏ nếu thêm key vào `runtime.snapshot()` (R4 mục 2) |
| Chụp lại golden (chỉ khi cố ý) | `PYTHONHASHSEED=0 python scripts/capture_idp_golden.py` | ghi lại golden | Không | Phải ghi kèm lý do diff |
| Điểm seeded offline | `python -m fixtures.seeded.score` (`--json` để xem chi tiết) | dòng cuối `SCORE <dev>`, tất định với `llm=None` (`fixtures/seeded/score.py:1-8`) | **Không**: pairs gate trả `LLM_UNAVAILABLE`, classifier **không chạy** | **Không** bắt được P1/P2. Chỉ chứng minh candidates/extraction không đổi |
| Cổng seeded live | `python -m fixtures.seeded.run_live --repeats 3` | exit 1 nếu thiếu `must` hoặc xuất hiện `forbidden` (`fixtures/seeded/run_live.py:1-9`, `:73`, `:93`) | **Có, gọi trả phí** | **P2: có** (chất lượng nhãn). P1: có, nếu chạy với concurrency 5 |
| Probe chi phí | `python -m fixtures.seeded.cost` | số lời gọi/token theo stage, `COST_CALLS <total>` (`fixtures/seeded/cost.py:1-6`) | Có | P2 (số lời gọi khi batch 8→N) |
| Lint | `uv run ruff check . && uv run ruff format --check .` | | | |

Ràng buộc vận hành (từ memory của user):
- Local dùng router model `cx/gpt-5.6-luna`.
- **Không gọi OpenAI từ local nếu chưa hỏi.**
- `run_live`/`cost` tự đọc `AI2_LLM_*`. Cần đảm bảo env đang trỏ vào router trước khi chạy, và hỏi user trước khi chạy với key OpenAI.

## 2. Lỗ hổng đo lường cần lấp cho plan

1. **Thiếu test bằng nhau giữa tuần tự và song song**. Đề xuất test RED cho P1:
   - Fake client có độ trễ khác nhau theo batch, hoàn tất theo thứ tự ngược.
   - Assert `decisions`, `stats`, chuỗi `event_sink` và `batches_completed` bằng nhau giữa `concurrency=1` và `concurrency=5`.
   - Assert wall time < 2 × độ trễ của một batch. Đây là benchmark mà debug report đề xuất (`plans/reports/perf-261017-1821-ai2-processing-time-debug-report.md`, mục 5).
2. **Seeded dossier nhỏ** nên không đo được speedup. Debug report cho thấy job nhỏ có 7 ứng viên, tức 1 batch. Muốn đo p90 thật cần job lớn với 468/762 ứng viên. Đề xuất harness replay:
   - Dump `ClassifierPair[]` (40 cặp) từ một job lớn.
   - Chạy `classify_pairs` trên router N lần với concurrency 1 và 5.
   - So `latency_ms` từng lời gọi (lấy từ P0) và tập relation.
3. **Chất lượng P2 (batch 12–16, model nhỏ, reasoning thấp)**:
   - Cổng là `run_live --repeats 3`, với điều kiện must ⊆ produced và forbidden ∩ produced = ∅.
   - Đây là cổng tập hợp, không đếm cạnh. Nó không phát hiện chuyện recall giảm trên các cặp không có trong gold. Nên bổ sung so sánh `relations_by_label` cùng tỉ lệ `rejected.*` (đặc biệt `ungrounded_span`, `no_answer`) giữa các biến thể.

## Kết luận xếp hạng

1. P1: test bằng nhau concurrency 1 và 5 trên fake client (bắt buộc, offline), cộng toàn bộ suite pairs/runtime/golden.
2. P0: chạy golden flag-off. Đỏ nghĩa là đã lỡ thêm key vô điều kiện vào `runtime.snapshot()`.
3. P2: `run_live --repeats 3` trên router là cổng chất lượng. `cost` dùng để đếm lời gọi. Cả hai cần user cho phép nếu chạm OpenAI.
4. `fixtures.seeded.score` chỉ là guard phụ, vì không chạy classifier.
