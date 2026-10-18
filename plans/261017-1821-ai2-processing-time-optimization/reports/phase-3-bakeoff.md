# P3 — Bake-off lời gọi pairs (router local, 2026-10-18)

Mọi lần chạy: in-process trong `ai2-graph-full-ai2-service`, provider in ra stderr
`host=host.docker.internal:20128` cho cả `AI2_LLM_BASE_URL` và `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL`; model
`cx/gpt-5.6-luna`. Hồ sơ tham chiếu `/tmp/ai2-perf/ref-request.json`, `InMemorySnapshotStore` (không ghi DB).
Không lời gọi OpenAI.

## Cổng chất lượng dry-run (bước 4)

`pairs_bakeoff gate --candidate C0` → `gate candidate=C0 exit=0 gate_sha=e94a1ad9af2fcaa3`, `calls=69`. 5 hồ sơ ×
`--repeats 3`: 11 must đều `hits: 3`, `forbidden_hits: 0` cả 5. `gate_sha` không đổi tới cuối phase (kiểm lại
trong container: `e94a1ad9af2fcaa3`), nên G1 dùng lại.

## Stage 1 — {C0, C1 `reasoning_effort=low`}, run `p3-s1`

`bakeoff_rank.py preflight --candidate C0 --candidate C1 --budget-seconds 300` → `{"ok": true, "reasons": []}`.
10 trial xen kẽ, mỗi trial `record` vào ledger `p3-s1`. 20/20 `SUCCEEDED`, `batches_completed=5`,
`pairs_per_call_observed=8`, 8 lời gọi/job. `prompt_version`: C0 `pairs-v13`, C1 `pairs-v13+effort-low` (F7 xác
nhận trên dữ liệu thật).

| ứng viên | wall 10 trial (s) | p90 | median latency/lời gọi pairs (50 lời gọi) | median completion_tokens | calls/job |
|---|---|---|---|---|---|
| C0 | 17.69, 22.475, 17.788, 14.994, 21.469, 21.266, 17.943, 15.307, 14.847, 14.886 | **21.469** | 7020 ms | 2712.5 | 8 |
| C1 | 19.535, 17.64, 18.59, 26.704, 21.288, 19.473, 18.469, 18.661, 15.544, 15.376 | **21.288** | 6608.5 ms | 2594.5 | 8 |

- `pairs_bakeoff rank` (quyết định, F3.6): `C1 vs C0: {"verdict": "TIE", "p90_incumbent": 21.469,
  "p90_candidate": 21.288, "delta": 0.181, "ci_low": -5.438, "ci_high": 2.94}` → **`verdict=TIE`**.
- `bakeoff_rank.py rank --direction lower --noise high` (thông tin phụ): `tie_within_noise`, gap 0.8865 ≤ band
  11.33, winner null. Verdict ghi vào plan dir.
- `drift --candidate C1`: `{"flags": ["label:REFERENCE 7.5->5.5"], "relations_total": [11.0, 10.0]}` →
  **`drift=FLAG`** (REFERENCE median giảm đúng 2, chạm ngưỡng F3.7). `relations_total` −9% (< 20%),
  `ungrounded_span+no_answer` 0 → 0.
- `gate` cho C1: **NOT_RUN** (phase chỉ chạy gate khi WIN).
- Bằng chứng phụ: latency/lời gọi −5.9%, completion_tokens −4.3%: khác biệt nhỏ, cùng bậc nhiễu giữa các trial.
  Theo bước 5 đây là ứng viên cho nhãn **`NOT_EFFECTIVE_ON_ROUTER`** (wall không khác ngoài nhiễu, phụ cũng gần
  như không khác) — cần người xác nhận vì "không khác" của phụ là phán đoán.
- **Quyết định của người cho TIE + drift: CHƯA CÓ** (developer không có TTY để AskUserQuestion). Mặc định an toàn
  đang áp dụng: giữ C0.

## Điều kiện dừng F3.8

`p90(trial wall C0) + p90(wall_ms − pipeline_ms của p2-parallel)` = 21.469 + 3.6 = **25.07s ≤ 38s** → đạt.

- Stage 2 (C2 batch 10): **NOT_RUN** — điều kiện dừng đạt.
- Stage 3 (C3 `gh/gpt-5-mini`): **NOT_RUN** — điều kiện dừng đạt.

## Ship (F3.9)

- Incumbent cuối = C0 → không đổi default local (`docker-compose.yml` giữ `${AI2_PAIRS_REASONING_EFFORT:-}`).
- Default production: **`PROD_UNCHANGED`** — lý do: không có ứng viên đề xuất (stage 1 TIE, chưa có quyết định
  người; stage 2 không chạy nên không có C2). `confirm-openai` không chạy.

## Lời gọi router

gate C0 69 + smoke trial 8 + stage 1 160 (20 × 8) + `p3-final` 80 = **317** (ngân sách stage 1: 420–1200; ngưỡng
dừng 1.5× = 1800). preflight của `bakeoff_rank` không gửi lời gọi (không có file jsonl `p3-preflight`).
