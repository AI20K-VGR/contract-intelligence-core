# P1 — Đo lại `p1-baseline` (2026-10-17)

Môi trường: local, container `ai2-graph-full-ai2-service`, `AI2_JOB_ISOLATION=process`, cả hai base URL =
`http://host.docker.internal:20128/v1`, model pairs `cx/gpt-5.6-luna` (router local, KHÔNG phải `gpt-5.5` của prod).
Không có lời gọi OpenAI trực tiếp.

## Probe `cached_tokens` (bước 1)

Một lời gọi router (script tạm `/tmp/probe_cached.py` trong container, không commit). OBSERVED:

```text
usage_keys ['completion_tokens', 'completion_tokens_details', 'prompt_tokens', 'prompt_tokens_details', 'total_tokens']
prompt_tokens_details None
```

Field `usage.prompt_tokens_details.cached_tokens` đúng tên, nhưng router local trả `prompt_tokens_details=None`.
Vì vậy mọi replay có `cached_tokens: null`. Code vẫn đúng: không ghi số 0 giả.

## Backup (F14, trước replay đầu tiên)

`$HOME/.ai2-perf/backup-ref/` (dossier `dos_01M4ZMW1F0MCE95QGPF04Y7MYM`). Số dòng là `wc -l` của file CSV, gồm cả
header; CSV có thể chứa xuống dòng trong field.

| Bảng | `wc -l` | bytes |
|---|---|---|
| jobs | 2 | 7923379 |
| ai2_processing_trace_events | 5 | 1129 |
| contract_edges | 6 | 16544 |
| contract_graph_write_receipts | 3 | 504 |
| contract_pair_relations | 17 | 51659 |
| dossier_query_snapshots | 2 | 4262341 |

Request export: `$HOME/.ai2-perf/ref-request.json` (448363 byte), copy vào `/tmp/ai2-perf/ref-request.json`.

## Kết quả `p1-baseline` (N=5, 5/5 SUCCEEDED)

| Tập | n | wall p50 | wall p90 | pairs p50 | pairs p90 |
|---|---|---|---|---|---|
| Baseline plan.md — nhóm hồ sơ tham chiếu (prod model) | 5 | 112.3s | 156.4s | 96.9s | 100.7s |
| **`p1-baseline` (router local, luna)** | 5 | **38.2s** | **41.6s** | **25.9s** | **29.9s** |

Ngoài pairs: `wall − pairs` p50/p90 = 11.7s / 14.0s; `wall_ms − pipeline_ms` p50/p90 = 4.1s / 4.5s.

Lưu ý: model router local nhanh hơn nhiều so với prod, nên số tuyệt đối KHÔNG so được với baseline prod. So sánh hợp lệ
cho P2/P3 là so với chính `p1-baseline` này.

## Phân rã theo job (ms)

Nguồn: `summarize` (DB) + `docker logs ... | grep ai2.job_timing` (10 dòng: 5 `scope=worker`, 5 `scope=dispatch`, khớp
job id).

| job | wall | slot_wait | run | snapshot_load | claim | pipeline | persist | spawn/import = run − Σ | wall − (slot_wait+run) | extraction | pairs | semantic | graph_op | pipeline − stages |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| job_05577a02… | 41616 | 0 | 42596 | 836 | 21 | 37274 | 267 | 4198 | −980 | 6617 | 29912 | 315 | 83 | 347 |
| job_bfa0114e… | 37820 | 0 | 38724 | 895 | 20 | 33370 | 235 | 4204 | −904 | 6007 | 26653 | 263 | 116 | 331 |
| job_3c1ae938… | 34977 | 0 | 35783 | 752 | 21 | 31082 | 246 | 3682 | −806 | 6878 | 23298 | 425 | 96 | 385 |
| job_a854bed4… | 39010 | 0 | 39748 | 741 | 17 | 34958 | 230 | 3802 | −738 | 8316 | 25858 | 284 | 133 | 367 |
| job_0ee45b24… | 38167 | 0 | 39024 | 751 | 18 | 34141 | 256 | 3858 | −857 | 9187 | 24174 | 320 | 138 | 322 |

- `wall − (slot_wait + run)` âm khoảng 0.7–1.0s: `run_ms` còn gồm phần sau persist (`updated_ms` đã chốt) — process con
  thoát, `release_memory`. Điều kiện `≤ 2000` đạt cho cả 5 job.
- Spawn/import process con ≈ 3.7–4.2s/job: phần lớn nhất của `wall − pipeline`.
- `llm_timing.by_operation.pairs`: `llm_calls=5` mỗi job; `llm_ms_max` 5645–9616ms; `llm_ms_total` ≈ pairs stage
  (sai khác < 100ms) → pairs gần như toàn bộ là chờ LLM tuần tự.
- `batches_completed=5`, `stopped_reason=null` cả 5 job. `llm_timing.llm_calls=8`/job.

## Kết luận về khoảng 59.5s ngoài pairs

- **Không tái hiện** trên 5 replay: `wall − pairs` chỉ 11.2–14.0s, giải thích được bởi extraction (6–9s) + spawn/import
  (~4s) + snapshot_load (~0.8s) + semantic/persist (~0.5s).
- Job gốc `job_dbf4b391…` thuộc dossier khác (`dos_01M51S2GT5YQDRC9JGK1C9V3X5`, không phải hồ sơ tham chiếu), chạy
  trước khi có instrumentation. Trace của nó: pairs bắt đầu ở +10.9s, kéo dài 96.9s (kết thúc ~+107.8s), còn
  `updated_ms` ở +156.4s → khoảng ~48.6s nằm **sau** khi pairs xong (semantic/propose/persist, hoặc chờ không có
  trace). Job đó không có `extraction`/`semantic` event nên không phân rã sâu hơn được từ dữ liệu cũ. Từ giờ
  `job_timing` + dòng `scope=worker` sẽ phân rã được nếu nó lặp lại.

## Ngân sách lời gọi

Probe 1 + replay `calls=40` = **41** lời gọi router (ngân sách P1: 41–101).
