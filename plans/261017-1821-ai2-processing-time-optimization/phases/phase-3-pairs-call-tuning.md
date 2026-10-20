---
phase: 3
title: "Pairs Call Tuning"
status: pending
plan: 261017-1821-ai2-processing-time-optimization
created: 2026-10-17
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 3 — Pairs Call Tuning

## Overview

Phase này giảm latency của lời gọi pairs bằng bake-off theo stage trên router local, theo đúng thứ tự D5:

| Ứng viên | Thay đổi |
|---|---|
| C1 | `reasoning_effort=low` |
| C2 | batch 10 |
| C3 | model nhỏ hơn: `gh/gpt-5-mini`, làm proxy local cho D10 |

Phase này chạy kể cả khi P2 đã đạt mục tiêu (D11).

Sản phẩm của phase:
- Knob `AI2_PAIRS_REASONING_EFFORT` đi qua compose (D9).
- Provenance cấu hình nằm trong `prompt_version` (F7).
- Quy tắc quyết định theo p90 wall từng job, đăng ký trước (F4/F5, VL-10).
- Cổng chất lượng.
- Lần chạy xác nhận trên OpenAI `gpt-5.5`, có cổng, cần user cho phép tường minh trước khi đổi bất kỳ default
  production nào (D10).
- Lần đo cuối N=10.

Phụ thuộc P2.

## Requirements

**Chức năng**

- F3.1 — **Knob** trong `ai-service/app/pipeline/runtime.py`, đặt cạnh `LIGHT_REASONING_*` (`:144-153`).
  - Env `AI2_PAIRS_REASONING_EFFORT`. Giá trị hợp lệ: `{"minimal","low","medium","high"}` (cùng tập với
    `ai-service/app/llm/client.py:67`) và sentinel `provider_default`.
  - Rỗng, không đặt, hoặc `provider_default` → `None`, tức không gửi effort, đúng hành vi hiện tại. Đây là đường quay
    về khi compose đặt default khác (F1).
  - Giá trị sai → `None`, kèm một warning.
  - Default trong code là `None` vĩnh viễn. Default theo môi trường nằm ở compose.
  - Chỉ áp cho `operation == "pairs"`; đường LIGHT giữ nguyên.
  - Effort chỉ tới provider khi dùng `NineRouterClient` (`runtime.py:436-449`) với model GPT-5 (`client.py:178-181`).
  - Thêm hàm public `pairs_reasoning_effort() -> str | None` để provenance dùng chung.
- F3.2 — **Provenance** (F7). Thêm `effective_prompt_version()` trong `pair_classifier.py`, trả về `PROMPT_VERSION`
  ghép thêm hậu tố, theo thứ tự cố định:
  - `+effort-<x>` khi `pairs_reasoning_effort()` khác `None`;
  - `+batch-<n>` khi `PAIRS_PER_CALL != 8`, đọc lúc gọi.

  Cấu hình mặc định → `pairs-v13`, không đổi, nên test và golden giữ nguyên.

  Nơi dùng:
  - `stats["prompt_version"]` của `classify_pairs` (`:326-328`);
  - `PairRelation.prompt_version` và `PairResult.prompt_version` ở `pair_builder.py:231`, `:246`.

  Đường rule-only (`pair_builder.py:157`) giữ `PROMPT_VERSION` vì không có lời gọi classifier.

  Cột `prompt_version` là `Text` (`ai-service/app/db/migrations/versions/0006_ai2_contract_pair_relations.py:24`), nên
  không cần migration. Sau rollback, lọc được bằng `prompt_version like 'pairs-v13+%'`.
- F3.3 — **Compose** (D9):
  - Thêm `AI2_PAIRS_REASONING_EFFORT` vào `environment:` của ai2-service trong `docker-compose.yml` và
    `deploy/compose.prod.yml`, đồng thời thêm vào `deploy/.env.prod.example`.
  - Default ban đầu ở **cả hai** là `${AI2_PAIRS_REASONING_EFFORT:-}`, tức không đổi hành vi.
  - Mở rộng `deploy/tests/test_ai2_pairs_env_passthrough.py`. Phần tĩnh kiểm key có mặt. Phần render kiểm subprocess
    đặt `medium` thì env container ra `medium`. Phần render cũng **kiểm prod ra rỗng khi không đặt**, cho tới khi
    default prod được đổi hợp lệ ở F3.9.
- F3.4 — **Harness** `ai-service/fixtures/perf/pairs_bakeoff.py`, chạy in-process trong container. Mọi subcommand trừ
  `confirm-openai` có guard router-only (D13): base URL phải chứa `:20128`. Mỗi lệnh in `calls=`.
  - Ứng viên là cấu hình áp lên incumbent:

    | Ứng viên | Cách áp |
    |---|---|
    | C0 | incumbent |
    | C1 | env `AI2_PAIRS_REASONING_EFFORT=low` |
    | C2 | patch `pair_classifier.PAIRS_PER_CALL = 10`, khôi phục trong `finally` |
    | C3 | env `AI2_CONTRACT_GRAPH_PAIRS_MODEL=gh/gpt-5-mini` |

    C3 bị từ chối nếu model là labeler `gpt-4o-mini-2024-07-18` (`docs/ai2/AI2-20-contract-graph-pairs.vi.md:201-202`)
    hoặc `classifier_family_ok` trả sai (`model_family.py:35-36`).
  - `trial --candidate Cx --request-file F`:
    - Chạy **một job đầy đủ** in-process bằng `run_idp` trên hồ sơ tham chiếu, dùng `InMemorySnapshotStore` (không
      ghi DB) và budget lấy từ request.
    - In ra **đúng một số**: wall của job tính bằng giây (`pipeline`).
    - Ghi kèm vào `/tmp/ai2-perf/bakeoff-<run>.jsonl`: `llm_timing` (latency từng lời gọi pairs), `relations_by_label`,
      `rejected.*`, `relations_total`, `completion_tokens`, `served_model`, `prompt_version`, `calls`, và
      `pairs_per_call_observed` (số cặp tối đa trong một request pairs).
    - Với C2: nếu `pairs_per_call_observed != 10` thì trial **lỗi** (exit ≠ 0), tức patch không có tác dụng (F12).
  - `rank --run R`: áp quy tắc ở F3.6 lên file jsonl, in verdict `WIN:<Cx>`, `KEEP:<incumbent>` hoặc `TIE`, kèm
    scoreboard.
  - `drift --run R --candidate Cx`: so median với incumbent theo band ở F3.7.
  - `gate --candidate Cx`: áp cấu hình rồi gọi `fixtures.seeded.run_live.main()` với argv `--repeats 3`
    (`ai-service/fixtures/seeded/run_live.py:40-94`). In ra `gate_sha` (SHA của `ai-service/app` và
    `ai-service/fixtures/seeded`) cùng `calls=`.
  - `confirm-openai --candidate Cw`: xem F3.9. Đây là đường **duy nhất** được nhắm tới host khác router (VL-11).
- F3.5 — **Bake-off theo stage**:

  | Stage | Cặp so | Khi nào chạy |
  |---|---|---|
  | 1 | {C0, C1} | luôn chạy (D11) |
  | 2 | {incumbent, C2} | chỉ khi điều kiện dừng F3.8 chưa đạt |
  | 3 | {incumbent, C3} | chỉ khi điều kiện dừng vẫn chưa đạt |

  - Mỗi ứng viên chạy **10 trial xen kẽ** (C0, Cx, C0, Cx, …) để chia đều nhiễu theo thời gian.
  - Ghi chú về C2 (F12): với `PAIRS_TOP_K=40`, cả C0 lẫn C2 đều chỉ có một wave
    (`ai-service/app/pipeline/contract_graph/pair_candidates.py:28`). Vì vậy kỳ vọng C2 không thắng về wall và chỉ
    tiết kiệm 1 lời gọi. Báo cáo ghi số lời gọi/job như thông tin phụ.
- F3.6 — **Quy tắc quyết định** (F4, đăng ký trước, VL-10):
  - Mỗi ứng viên lấy p90 nearest-rank của 10 wall.
  - Đặt `Δ = p90(incumbent) − p90(Cx)`. Band là CI bootstrap 90%: 2000 lần lấy mẫu lại cho mỗi ứng viên, seed 0.
  - Kết luận:
    - **WIN Cx**: `CI_low > 0` và `Δ ≥ 0.05 × p90(incumbent)`.
    - **KEEP incumbent**: `CI_high < 0`.
    - Các trường hợp còn lại là **TIE**. Giao cho người quyết (AskUserQuestion), kèm bằng chứng phụ: median latency
      từng lời gọi pairs trên khoảng 50 lời gọi của mỗi ứng viên, và median `completion_tokens`.
  - Song song đó vẫn chạy `bakeoff_rank.py preflight` (dry-run metric, budget) và `record` cho từng trial (giữ
    ledger), rồi `rank --direction lower --noise high --plan-dir <plan>`. Verdict của `bakeoff_rank` chỉ được báo cáo
    như thông tin phụ.
  - Ứng viên thắng chỉ thành incumbent sau khi qua `gate`. Gate đỏ thì ứng viên bị loại vì chất lượng.
- F3.7 — **Drift** (advisory; vượt band thì giao cho người quyết). So median của Cx với incumbent:
  - `relations_total` giảm quá 20%;
  - một nhãn bất kỳ giảm từ 2 trở lên;
  - `rejected.ungrounded_span + rejected.no_answer` tăng từ 3 trở lên.
- F3.8 — **Điều kiện dừng** (F5): `p90(trial wall của incumbent) + p90(wall_ms − pipeline_ms của p2-parallel) ≤ 38s`.
  Nếu đạt thì không chạy stage tiếp theo. Stage 1 luôn chạy.
- F3.9 — **Ship và xác nhận production** (D10):
  1. **Áp dụng ở local**. Áp cho incumbent cuối cùng, nếu nó khác C0 và đã qua `gate`:
     - C1: đổi default của `docker-compose.yml` thành `${AI2_PAIRS_REASONING_EFFORT:-low}`.
     - `deploy/compose.prod.yml` **giữ rỗng**. `deploy/tests` assert local render ra `low` và prod render ra rỗng.
     - C2 là hằng số trong code nên áp lên mọi môi trường. Chưa qua bước 2 của F3.9 thì **không áp**, kể cả ở local.
  2. **Xác nhận OpenAI**, chỉ chạy khi có ứng viên đề xuất làm default production (C1 hoặc C2):
     - Cook hỏi user bằng AskUserQuestion, nêu rõ:
       - model `gpt-5.5`;
       - ước lượng **96–320 lời gọi OpenAI**;
       - dữ liệu gửi đi chỉ là hồ sơ seeded (synthetic), **không** có hồ sơ tham chiếu thật;
       - các lệnh sẽ chạy.
     - Không có TTY hoặc user từ chối → ghi `PROD_UNCHANGED`, dừng nhánh này.
     - Được phép thì chạy `confirm-openai --candidate Cw --user-permission <YYYY-MM-DD hôm nay>` với
       `AI2_PERF_PROVIDER=openai`. Env OpenAI do user cung cấp qua `docker exec -e`, không ghi log. Lệnh gồm:
       - (a) 3+3 trial xen kẽ C0/Cw trên hồ sơ seeded có 40 ứng viên (5 batch);
       - (b) `run_live --repeats 1` cho C0 và cho Cw.
     - **Đạt** khi median và max wall của Cw đều thấp hơn C0 (chỉ kiểm hướng, không kiểm band), **và** `run_live` của
       Cw exit 0, không có must-miss nào mà C0 trúng.
  3. **Đổi default production**, chỉ khi bước 2 của F3.9 đạt:
     - C1: `deploy/compose.prod.yml` thành `${AI2_PAIRS_REASONING_EFFORT:-low}`, cập nhật `deploy/.env.prod.example`
       và `deploy/tests`.
     - C2: đổi `PAIRS_PER_CALL = 10` (`pair_classifier.py:23`), cập nhật `test_batches_of_eight_and_max_five_calls`
       (`tests/test_contract_graph_pair_classifier.py:154-160`): batch thành `[10,10,10,10,3]`, unclassified 0,
       `stopped_reason=None`.
  4. **C3** không bao giờ thành default. Nếu C3 thắng ở local, báo cáo ghi khuyến nghị "đổi model prod khỏi `gpt-5.5`
     là quyết định của user", kèm số liệu. Việc xác nhận và đổi thuộc một yêu cầu riêng của user.
- F3.10 — **Đo cuối** `p3-final`, N=10, theo giao thức của plan.md, với cấu hình local đã áp dụng. Kiểm `printenv
  AI2_PAIRS_REASONING_EFFORT` sau khi recreate.

**Phi chức năng**

- NF3.1 — Không gọi OpenAI ngoài `confirm-openai` đã được user cho phép (D6/D10). Các subcommand còn lại có guard
  router-only (D13) và in host base URL ra stderr.
- NF3.2 — Ngân sách (F9):
  - P3 chỉ stage 1: 420–1200 lời gọi router. Đủ 3 stage: 920–2600.
  - Đầu phase, cook trình bảng ngân sách và hỏi user xác nhận quota router. Vượt cận trên ×1.5 thì dừng và hỏi lại.
  - Kết quả `gate` được dùng lại khi `gate_sha` không đổi.
- NF3.3 — Không chạy bake-off song song với replay hay job khác (preflight `RUNNING=0`).
- NF3.4 — Không lưu output model hoặc span vào repo.

## Related Code Files

**Sửa**
- `ai-service/app/pipeline/runtime.py`
- `ai-service/app/pipeline/contract_graph/pair_classifier.py`: luôn sửa cho `effective_prompt_version`; đổi hằng số
  khi C2 được ship theo F3.9.
- `ai-service/app/pipeline/contract_graph/pair_builder.py`
- `docker-compose.yml`
- `deploy/compose.prod.yml`
- `deploy/.env.prod.example`
- `deploy/tests/test_ai2_pairs_env_passthrough.py`
- `ai-service/.env.example`
- `docs/ai2/AI2-20-contract-graph-pairs.vi.md`

**Sửa có điều kiện** (chỉ khi C2 được ship)
- `ai-service/tests/test_contract_graph_pair_classifier.py`

**Tạo**
- `ai-service/fixtures/perf/pairs_bakeoff.py`
- `ai-service/tests/test_pairs_call_config.py`
- `ai-service/tests/test_pairs_bakeoff_harness.py`

**Báo cáo** (trong thư mục plan)
- `reports/phase-3-bakeoff.md`
- `reports/phase-3-measurement.md`
- verdict do `bakeoff_rank.py rank --plan-dir plans/261017-1821-ai2-processing-time-optimization` sinh ra

**Xoá**: không có.

## File inventory (deep)

| Hành động | Path | Cỡ ước lượng | Ảnh hưởng test |
|---|---|---|---|
| Sửa | `ai-service/app/pipeline/runtime.py` | +25 | `test_llm_complete_json.py:344-360` (LIGHT) |
| Sửa | `.../contract_graph/pair_classifier.py` | +15 (thêm 1 dòng nếu C2) | test classifier và song song; `evals/contract_graph/pairs/bakeoff.py:634` so `PROMPT_VERSION`, nên eval từ chối chạy khi cấu hình không mặc định (đúng ý đồ) |
| Sửa | `.../contract_graph/pair_builder.py` | +2/−2 | test builder và projection |
| Sửa | `docker-compose.yml`, `deploy/compose.prod.yml` | mỗi file +1 (+1 khi đổi default) | `deploy/tests` |
| Sửa | `deploy/.env.prod.example`, `ai-service/.env.example` | mỗi file +3 | — |
| Sửa | `deploy/tests/test_ai2_pairs_env_passthrough.py` | +40 | — |
| Sửa | `docs/ai2/AI2-20-…` | +30 | — |
| Sửa nếu C2 | `ai-service/tests/test_contract_graph_pair_classifier.py` | ~6 | — |
| Tạo | `ai-service/fixtures/perf/pairs_bakeoff.py` | ~320 | `test_pairs_bakeoff_harness.py` |
| Tạo | `ai-service/tests/test_pairs_call_config.py` | ~130 | mới |
| Tạo | `ai-service/tests/test_pairs_bakeoff_harness.py` | ~160 | mới |

Phase có 13 file, vượt ngưỡng 8. Lý do giữ: 7 file chỉ sửa 1–40 dòng (compose, env example, docs, test). D1 giới
hạn 3 phase.

## Dependency map (deep)

- **Phụ thuộc vào**:
  - P2: đường song song; `pairs_replay`; `p2-parallel` (`wall_ms − pipeline_ms`); file test render;
    `_batch_messages` đọc `PAIRS_PER_CALL` lúc gọi.
  - P1: `replay_job`, `coverage.job_timing.pipeline_ms`.
- **Phase phụ thuộc vào P3**: không có. P3 phát `review-decision.json`.
- **Phụ thuộc ngoài**:
  - Router có `gh/gpt-5-mini` (OBSERVED) và có tôn trọng `reasoning_effort` hay không ([ASSUMED], stage 1 đo).
  - `fixtures.seeded` chạy được trong container ([ASSUMED], bước 4 dry-run kiểm).
  - OpenAI `gpt-5.5`: chỉ dùng khi có quyền của user (F3.9).

## Implementation Steps

0. **Chuẩn bị**:
   - Trình bảng ngân sách (NF3.2) cho user để xác nhận quota router.
   - `cd ai-service && python -m fixtures.seeded.score`: ghi lại dòng `SCORE`. Lệnh này không gọi LLM.
1. **Viết test trước** (Tests Before).
2. **Code**:
   - Knob và `pairs_reasoning_effort()` (F3.1).
   - `effective_prompt_version()` và chỗ dùng ở `pair_builder.py` (F3.2).
   - Compose, env example và `deploy/tests` (F3.3).
   - Harness (F3.4).

   Default chưa đổi ở bất kỳ chỗ nào.
3. **Gate offline**: regression gate cộng `deploy/tests`. Preflight `RUNNING=0`, recreate container, `printenv` ra
   `AI2_PAIRS_REASONING_EFFORT=` rỗng.
4. **Dry-run cổng chất lượng**: chạy `gate --candidate C0` trong container. Lệnh này vừa lấy baseline cổng, vừa kiểm
   `fixtures.seeded` chạy được trong container.
   - C0 đỏ → **dừng** và báo user. Đối chiếu với `run_live` cuối P2 để biết lỗi có sẵn từ trước hay mới phát sinh.
5. **Stage 1**: chạy `bakeoff_rank.py preflight --candidate C0 --candidate C1 --metric-cmd "<trial C0>" --budget-seconds 300`, rồi:
   - 10 trial xen kẽ, mỗi trial ghi `record`;
   - `pairs_bakeoff rank` (quyết định);
   - `bakeoff_rank.py rank` (thông tin phụ);
   - `drift`;
   - nếu ra WIN thì chạy `gate`.

   Nếu C1 không khác C0 ngoài nhiễu, đồng thời median latency từng lời gọi và `completion_tokens` cũng không khác,
   ghi `NOT_EFFECTIVE_ON_ROUTER`.
6. **Kiểm điều kiện dừng F3.8**. Chưa đạt thì chạy stage 2 (C2, kèm assert batch 10), rồi stage 3 (C3 =
   `gh/gpt-5-mini`) nếu vẫn cần.
7. **Ship theo F3.9**:
   - áp dụng ở local;
   - xin phép và chạy xác nhận OpenAI;
   - đổi default prod khi xác nhận đạt.

   Sau mỗi lần đổi default: chạy lại `deploy/tests` và regression gate. `gate` chỉ chạy lại khi `gate_sha` đổi.
8. **Cổng chất lượng** cho cấu hình đã áp dụng ở local:
   - `gate` exit 0 (dùng lại kết quả nếu `gate_sha` không đổi);
   - `SCORE` bằng bước 0;
   - regression gate.
9. **Đo cuối** `p3-final`, N=10, viết `reports/phase-3-measurement.md` với các bảng p50/p90:
    - `p3-final`, `p2-parallel`, `p1-baseline`;
    - bảng baseline trong plan.md;
    - bảng debug report.

    Nếu chưa đạt thì ghi `NOT_MET` cùng phân rã.
10. **`hs:code-review`** trên diff toàn nhánh của plan, phát `review-decision.json`.

## Test scenario matrix (deep)

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Đường LIGHT không đổi | TB3.1 |
| Critical | Cấu hình mặc định giữ `prompt_version == "pairs-v13"`; cấu hình C1/C2 có hậu tố trong stats, relation và result | R3.6 |
| Critical | `provider_default` hoặc rỗng → không gửi effort (đường quay về, F1) | R3.2 |
| Critical | Render compose: local và prod truyền `AI2_PAIRS_REASONING_EFFORT`; prod rỗng cho tới khi ship hợp lệ | D4–D6 |
| Critical | Guard: mọi subcommand trừ `confirm-openai` từ chối URL không phải router; `confirm-openai` từ chối khi thiếu hoặc sai `--user-permission`, `AI2_PERF_PROVIDER`, URL hoặc model | R3.7c, R3.7f |
| Critical | Cổng chất lượng của cấu hình được áp dụng | G1–G3 |
| High | Env `low` chỉ áp cho `pairs`; giá trị sai bị bỏ qua, có warning; chỉ áp cho GPT-5 | R3.1, R3.3, R3.4, R3.5 |
| High | Quy tắc p90/bootstrap: thắng rõ → WIN, chồng lấn → TIE, chậm hơn → KEEP; tất định với seed 0 | R3.7e |
| High | C2 assert batch quan sát được bằng 10; patch không tác dụng thì trial lỗi | R3.7g |
| High | C3 từ chối labeler hoặc model khác họ | R3.7d |
| Medium | Áp/khôi phục cấu hình không rò rỉ giữa các trial; `trial` in đúng một số; ngưỡng drift | R3.7a, R3.7b, R3.7h |

### Tests Before

Các test khoá, phải PASS trước và sau khi sửa:

- [ ] TB3.1 `tests/test_llm_complete_json.py::test_light_reasoning_effort_only_for_span_picking_on_gpt5` (`:344`),
  `::test_reasoning_effort_is_not_sent_when_unset` (`:354`).
- [ ] TB3.2 `tests/test_contract_graph_pair_classifier.py`, `test_contract_graph_pairs_parallel.py`,
  `test_contract_graph_pair_builder.py`, `test_contract_graph_pair_projection.py`. Khoá `prompt_version == "pairs-v13"`
  với cấu hình mặc định.
- [ ] TB3.3 Dòng `SCORE` ở bước 0. TB3.4 `deploy/tests` của P2.

Các test hành vi mới, phải FAIL lần đầu.

`tests/test_pairs_call_config.py`:
- [ ] R3.1 `test_pairs_effort_from_env`
- [ ] R3.2 `test_pairs_effort_unset_empty_or_provider_default_sends_nothing`
- [ ] R3.3 `test_pairs_effort_invalid_value_ignored_with_one_warning`
- [ ] R3.4 `test_pairs_effort_not_applied_to_other_operations`
- [ ] R3.5 `test_pairs_effort_only_sent_to_gpt5_models` (dùng `_client` giả)
- [ ] R3.6 `test_effective_prompt_version_suffixes[default|effort|batch|both]` và
  `test_relations_carry_effective_prompt_version`

`tests/test_pairs_bakeoff_harness.py`:
- [ ] R3.7a áp và khôi phục cấu hình C1/C2/C3
- [ ] R3.7b `trial` in một số
- [ ] R3.7c guard router-only
- [ ] R3.7d C3 từ chối `gpt-4o-mini-2024-07-18` và `unknown-model`
- [ ] R3.7e quy tắc quyết định trên dữ liệu tổng hợp
- [ ] R3.7f cổng của `confirm-openai`
- [ ] R3.7g assert batch 10 của C2
- [ ] R3.7h ngưỡng drift

`deploy/tests`:
- [ ] D4 tĩnh, có key effort ở local và prod
- [ ] D5 render prod truyền key
- [ ] D6 render local truyền key, và prod ra rỗng khi không đặt

### Implement

Làm theo bước 2, sau đó bước 7 khi ship.

### Tests After

- [ ] R3.x, D4–D6 xanh; TB3.x xanh.
- [ ] Sau khi áp dụng ở local (C1): D6 cập nhật thành local render ra `low`, prod render ra rỗng.
- [ ] Sau khi đổi default prod (chỉ khi xác nhận OpenAI đạt): D5/D6 cập nhật theo. Nếu C2 được ship: test 43 cặp và
  test song song xanh với batch mới.
- [ ] G1 `gate` exit 0. G2 `SCORE` bằng bước 0. G3 regression gate.
- [ ] E2E `p3-final` N=10: 10/10 SUCCEEDED; `prompt_version` trong coverage khớp cấu hình đã áp dụng.

### Regression Gate

```text
cd ai-service
AI2_REQUIRE_DATABASE=false uv run --no-sync pytest -q -p no:cacheprovider -m "not live" --basetemp="$TEMP/ai2-pytest-p3"
uv run --no-sync ruff check app/pipeline/runtime.py app/pipeline/contract_graph/pair_classifier.py app/pipeline/contract_graph/pair_builder.py fixtures/perf tests/test_pairs_call_config.py tests/test_pairs_bakeoff_harness.py
uv run --no-sync ruff format --check app/pipeline/runtime.py app/pipeline/contract_graph/pair_classifier.py app/pipeline/contract_graph/pair_builder.py fixtures/perf tests/test_pairs_call_config.py tests/test_pairs_bakeoff_harness.py
python -m fixtures.seeded.score
cd .. && python -m pytest deploy/tests -q
```

`gate` (`run_live --repeats 3`) **không** chạy lại ở đây khi `gate_sha` trùng với lần G1 đã xanh (F9). Nếu `gate_sha`
khác thì chạy:
`MSYS_NO_PATHCONV=1 docker exec -w /app ai2-graph-full-ai2-service uv run --no-sync python -m fixtures.perf.pairs_bakeoff gate --candidate <cấu hình đã áp dụng>`.

Nếu C2 được ship, thêm `tests/test_contract_graph_pair_classifier.py` vào danh sách ruff.

## Success Criteria

- [ ] `reports/phase-3-bakeoff.md` có, cho mỗi stage:
  - scoreboard đủ 10 trial của từng ứng viên, p90, Δ và CI;
  - verdict của `pairs_bakeoff rank` và của `bakeoff_rank.py` (thông tin phụ);
  - median latency từng lời gọi pairs, `drift`, `gate`, `calls=`;
  - lý do cho `NOT_RUN`/`NOT_EFFECTIVE_ON_ROUTER`;
  - quyết định của người cho mọi TIE hoặc drift.
- [ ] Cấu hình áp dụng ở local qua G1–G3.
- [ ] Default production: `PROD_UNCHANGED` kèm lý do (không có đề xuất, user từ chối, hoặc xác nhận không đạt), **hoặc**
  đã đổi sau khi xác nhận OpenAI đạt, có số liệu `confirm-openai` trong báo cáo. Không có trạng thái thứ ba.
- [ ] `p3-final` N=10 đạt **wall p90 < 40s** (nearest-rank); hoặc ghi `NOT_MET` cùng phân rã và follow-up.
- [ ] Mọi lần chạy không phải `confirm-openai` đều in host `host.docker.internal:20128`.
- [ ] `review-decision.json` có verdict PASS hoặc PASS_WITH_RISK, có lý do.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| `low` làm giảm chất lượng CONFLICT/DUPLICATE (`pair_classifier.py:31-63`) | TB × Cao | `gate`, `drift`, người quyết; prod cần xác nhận OpenAI |
| Kết quả router không chuyển sang `gpt-5.5` được (R5) | Cao × TB | F3.9: xác nhận OpenAI có cổng; C3 chỉ là khuyến nghị |
| Router bỏ qua effort (R6) | TB × TB | Stage 1 đo; bằng chứng phụ là latency từng lời gọi và `completion_tokens`; `NOT_EFFECTIVE_ON_ROUTER` |
| Trial in-process nhiễu vì extraction/semantic | Cao × TB | 10 trial xen kẽ; p90 với band bootstrap; TIE thì giao người (VL-10) |
| Default local rò sang prod | Thấp × Cao | Prod liệt kê key với default riêng; D6 assert prod ra rỗng |
| Không quay lại được hành vi "không gửi effort" | Thấp × TB | Sentinel `provider_default` (R3.2) |
| Mất provenance sau khi ship | Thấp × TB | `effective_prompt_version` có trước mọi lần đổi default (F7) |
| Gửi nội dung hợp đồng thật cho OpenAI khi xác nhận | Thấp × Cao | Xác nhận chỉ dùng hồ sơ seeded; câu hỏi xin phép nêu rõ dữ liệu gửi đi |
| Quota router hoặc chi phí OpenAI | TB × TB | Xác nhận quota đầu phase; dừng khi vượt ×1.5; OpenAI chỉ chạy khi có quyền |
| Cổng chất lượng không chạy được trong container | Thấp–TB × TB | Bước 5 dry-run; sửa harness hoặc dùng `docker exec -e AI2_REQUIRE_DATABASE=false` |
