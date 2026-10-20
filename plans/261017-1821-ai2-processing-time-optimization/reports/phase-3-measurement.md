# P3 — Đo cuối `p3-final` (N=10, 2026-10-18)

Giao thức plan.md: preflight `RUNNING=0`; container recreate (3 file compose khớp nhãn `config_files`,
`--no-deps`), `AI2_PAIRS_REASONING_EFFORT=[]` (rỗng, có đặt), `AI2_PAIRS_CONCURRENCY=5`, URL `:20128`, model
`cx/gpt-5.6-luna`. Cấu hình áp dụng = C0 (không đổi default nào). Replay
`replay_job run --runs 10 --label p3-final` → 10/10 `SUCCEEDED`, `calls=80`. `prompt_version` trong
`result_json.contribution.coverage.contract_graph.pairs` = `pairs-v13` (khớp cấu hình).

| nhãn | N | wall p50 | wall p90 | pairs p50 | pairs p90 | wall−pipeline p90 |
|---|---|---|---|---|---|---|
| `p3-final` | 10 | 24.1s | **26.8s** | 7.7s | 10.2s | 7.6s |
| `p2-parallel` | 5 | 16.7s | 19.1s | 6.7s | 8.6s | 3.6s |
| `p1-baseline` | 5 | 38.2s | 41.6s | 25.9s | 29.9s | — |

(Baseline plan.md / debug report: wall ≈ 38–42s, pairs ≈ 26–30s — cùng bậc với `p1-baseline`.)

- Tiêu chí `wall p90 < 40s` (nearest-rank): **MET** (26.8s).
- `p3-final` chậm hơn `p2-parallel` dù code/config pairs giống nhau: phần tăng nằm ngoài pairs — extraction 5.2–14.1s
  (p2: 4.4–8.3s) và `wall−pipeline` 3.7–7.7s (p2: 3.5–3.6s; 5/10 job ≈ 7.2–7.7s, `snapshot_load_ms` 1.1–1.3s). Một
  job có lời gọi pairs đuôi 11.8s. Giải thích khả dĩ: latency router/DB dao động theo thời điểm; không quy cho P3
  (P3 không đổi hành vi mặc định — `prompt_version` vẫn `pairs-v13`).

| job | wall | pairs | wall−pipeline | extraction | llm pairs max |
|---|---|---|---|---|---|
| job_4e01943429fb4f159bb0048fd98d2976 | 29645 | 11955 | 7733 | 9054 | 11818 |
| job_0d964931749d42278ccebcc2f494fa0a | 20967 | 6675 | 3686 | 9968 | 6615 |
| job_b1a39ed7240840198bf5de2eaf129d57 | 21877 | 8245 | 3805 | 9181 | 8182 |
| job_302e25c035d1467c903673335d83f0fe | 26758 | 8070 | 3864 | 14134 | 8012 |
| job_8401dd658f6e4f49818b4e5aee0eda52 | 20127 | 7058 | 4135 | 8276 | 6998 |
| job_452de1dc38b4452baa77447db789e24f | 16047 | 6324 | 3919 | 5196 | 6265 |
| job_ba9cd1714c8a4a2c9bd8f48efbfc9882 | 24633 | 7434 | 7567 | 8283 | 7291 |
| job_cae100c7813c4fc5b043de6de57430ec | 24129 | 10244 | 7221 | 5463 | 10122 |
| job_bdd91598adfe46e6838448cac7ecc81a | 25374 | 7736 | 7226 | 9052 | 7587 |
| job_8434b54d47c344e68b5c1e000723554d | 26446 | 9861 | 7486 | 7775 | 9697 |
