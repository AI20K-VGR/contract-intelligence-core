# P3 — Developer notes (Pairs Call Tuning)

Trạng thái: phần code + bake-off router xong, chưa commit. **Hai điểm chờ user** (xem cuối file): quyết định TIE/drift
của stage 1, và (chỉ khi user chọn C1 cho prod) lần chạy `confirm-openai`. Không gọi OpenAI. Không đụng
`ai-service/.env`, backend, FE (kể cả `ProcessingTimeline.tsx`), migration. Không đổi default nào (local lẫn prod).

## File thay đổi

| File | Thay đổi |
|---|---|
| `ai-service/app/pipeline/runtime.py` | +knob `AI2_PAIRS_REASONING_EFFORT`, `pairs_reasoning_effort()` (`:154-183`), `_reasoning_effort` nhánh `pairs` (`:187`) |
| `ai-service/app/pipeline/contract_graph/pair_classifier.py` | `PAIRS_PER_CALL_BASELINE`, `effective_prompt_version()` (`:198`), dùng ở `classify_pairs` (`:466`) |
| `ai-service/app/pipeline/contract_graph/pair_builder.py` | relation/result dùng `stats["prompt_version"]` (`:182`, `:232`, `:247`); rule-only giữ `PROMPT_VERSION` (`:157`) |
| `docker-compose.yml` `:595`, `deploy/compose.prod.yml` `:172` | `AI2_PAIRS_REASONING_EFFORT: ${AI2_PAIRS_REASONING_EFFORT:-}` |
| `deploy/.env.prod.example` `:82`, `ai-service/.env.example` `:138` | key rỗng + comment |
| `deploy/tests/test_ai2_pairs_env_passthrough.py` | +D4/D5/D6 (8 test) |
| `docs/ai2/AI2-20-contract-graph-pairs.vi.md` | dòng env + mục "Tinh chỉnh lời gọi phân loại (P3)" |
| `ai-service/fixtures/perf/pairs_bakeoff.py` | mới (harness: trial/rank/drift/gate/confirm-openai) |
| `ai-service/tests/test_pairs_call_config.py` | mới, 27 test |
| `ai-service/tests/test_pairs_bakeoff_harness.py` | mới, 45 test |
| `reports/phase-3-bakeoff.md`, `reports/phase-3-measurement.md` | mới |

`tests/test_contract_graph_pair_classifier.py` **không** sửa (C2 không ship).

## Red → green

- `test_pairs_call_config.py`: 27 errors — `AttributeError: _warned_pairs_efforts` (knob chưa có) → 27 passed.
- `test_pairs_bakeoff_harness.py`: `ImportError: cannot import name 'pairs_bakeoff'` → 45 passed.
- `deploy/tests`: 8 failed `KeyError: 'AI2_PAIRS_REASONING_EFFORT'` (6 cũ pass) → 48 passed.
- TB3.1/TB3.2 (LIGHT + classifier/parallel/builder/projection) xanh trước và sau: 524 passed cùng file mới.
- Lần suite đầu: 2 failed `test_relations_carry_effective_prompt_version` — env pairs base URL rò từ test khác làm
  build gọi endpoint thật. Sửa: test thêm autouse delenv giống `test_contract_graph_pair_builder.py`; tái hiện bằng
  env giả `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL=127.0.0.1:9` → 27 passed.

## Regression gate (cuối)

- `pytest -m "not live"`: **2450 passed, 3 skipped, 6 deselected** (P2: 2375).
- Golden flag_off + pairs_flag: **21 passed**. `deploy/tests`: **48 passed**.
- ruff check: `All checks passed!`; format: `9 files already formatted`.
- `SCORE 1.0000` (bước 0 và cuối giống nhau; dòng `FAIL [heldout] ... semantic_difference` có sẵn ở cả hai lần).
- basetemp `C:\Users\dungs\.claude\jobs\ad849255\tmp\p3-*`.

## Acceptance → evidence

- F3.1: `runtime.py:154-183`, `:187`; R3.1–R3.5. Default code `None`; chỉ GPT-5 nhờ `client.py:178-181`.
- F3.2: `pair_classifier.py:198`, `:466`; `pair_builder.py:182,232,247`; R3.6. Dữ liệu thật: C1 trial `pairs-v13+effort-low`, C0 `pairs-v13`.
- F3.3: compose/env ở trên; D4–D6 + `test_compose_render_prod_effort_empty_when_unset_even_if_local_differs`. Container sau recreate: `EFFORT=[]` (có đặt, rỗng).
- F3.4: `pairs_bakeoff.py` — `check_router` `:75`, `validate_c3_model` `:81`, `applied` `:87`, `check_batch` `:131`, `run_job` `:154`, `trial` `:210`, `decide` `:237`, `rank` `:280`, `drift` `:315`, `gate` `:403`, `confirm_guard` `:412`.
- F3.5–F3.8, F3.10: `reports/phase-3-bakeoff.md`, `reports/phase-3-measurement.md`.

## Bake-off

| stage | ứng viên | p90 (s) | Δ / CI 90% | verdict | phụ (latency/lời gọi, tokens) | drift | gate |
|---|---|---|---|---|---|---|---|
| 1 | C0 | 21.469 | — | — | 7020 ms, 2712.5 | — | exit 0, sha `e94a1ad9af2fcaa3` |
| 1 | C1 low | 21.288 | 0.181 / [-5.438, 2.94] | **TIE** (bakeoff_rank: tie_within_noise) | 6608.5 ms, 2594.5 | **FLAG** REFERENCE 7.5→5.5 | NOT_RUN (không WIN) |
| 2 | C2 | — | — | NOT_RUN (F3.8 đạt: 21.469+3.6=25.07 ≤ 38) | | | |
| 3 | C3 | — | — | NOT_RUN (F3.8 đạt) | | | |

`p3-final` N=10: wall p50/p90 **24.1s / 26.8s** (< 40s: MET), pairs 7.7s/10.2s, 10/10 SUCCEEDED,
`prompt_version=pairs-v13`. Chậm hơn `p2-parallel` (19.1s) vì extraction và `wall−pipeline` tăng, không phải pairs.

## Lời gọi router

69 (gate C0) + 8 (smoke) + 160 (stage 1) + 80 (`p3-final`) = **317**. Ngân sách stage 1 420–1200 (ngưỡng 1.5× =
1800). OpenAI: 0.

## Chờ user

1. **TIE + drift stage 1** (F3.6/F3.7 yêu cầu người quyết; không có TTY). Lựa chọn:
   (a) giữ C0, ghi `NOT_EFFECTIVE_ON_ROUTER` (khuyến nghị: wall hoà, phụ chỉ −4..6%, REFERENCE giảm 2);
   (b) chọn C1 → chạy `gate --candidate C1` (~69 lời gọi router), nếu xanh thì đổi `docker-compose.yml` thành
   `${AI2_PAIRS_REASONING_EFFORT:-low}`, D6 assert local `low` / prod rỗng.
   Hiện áp dụng (a) mặc định → `PROD_UNCHANGED` (không có đề xuất).
2. **`confirm-openai`** — BLOCKED, chỉ cần nếu user chọn (b) và muốn đổi default prod. Lệnh sẽ chạy (user cấp env
   OpenAI qua `docker exec -e`, không log):
   `MSYS_NO_PATHCONV=1 docker exec -e AI2_PERF_PROVIDER=openai -e AI2_LLM_BASE_URL=https://api.openai.com/v1 -e AI2_CONTRACT_GRAPH_PAIRS_BASE_URL=https://api.openai.com/v1 -e AI2_LLM_MODEL=gpt-5.5 -e AI2_CONTRACT_GRAPH_PAIRS_MODEL=gpt-5.5 -e <keys> -w /app ai2-graph-full-ai2-service uv run --no-sync python -m fixtures.perf.pairs_bakeoff confirm-openai --candidate C1 --user-permission <YYYY-MM-DD hôm nay> --dossier <seeded có ~40 ứng viên>`
   — (a) 3+3 trial xen kẽ C0/C1 trên hồ sơ seeded (synthetic, không hồ sơ thật), (b) `run_live --repeats 1` cho C0 và
   C1 (5 hồ sơ seeded). Ước lượng plan: 96–320 lời gọi `gpt-5.5`; theo số đo router (≈8 lời gọi/job, 23 lời gọi/vòng
   run_live) thực tế ≈ 6×8 + 2×23 ≈ 95–100. Đạt khi median và max wall C1 < C0 và run_live C1 exit 0.

## Lệch / ghi chú

- `served_model` trong jsonl trial là `None` (coverage pairs không mang key này); không ảnh hưởng quyết định.
- `bakeoff_rank.py preflight` không thực sự chạy metric-cmd (không sinh jsonl); trial smoke chạy riêng.
- `confirm-openai` cần thêm `--dossier` (plan không nêu tên hồ sơ 40 ứng viên).
- Bước 10 (`hs:code-review`, `review-decision.json`) chưa làm — thuộc lead.

## Quyết định của user (2026-10-18)

TIE/drift → **(a) giữ C0**, ghi `NOT_EFFECTIVE_ON_ROUTER`, prod `PROD_UNCHANGED`. Không chạy confirm-openai, không có lời gọi OpenAI nào. Knob `AI2_PAIRS_REASONING_EFFORT` vẫn ship với default rỗng (`provider_default`), để sau này có thể thử trên gpt-5.5.
