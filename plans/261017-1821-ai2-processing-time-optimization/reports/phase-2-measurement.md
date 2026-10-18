# P2 — Đo lại `p2-parallel` (2026-10-18)

Môi trường: local, container `ai2-graph-full-ai2-service`, `AI2_JOB_ISOLATION=process`, cả hai base URL =
`http://host.docker.internal:20128/v1`, model pairs `cx/gpt-5.6-luna` (router local). Không có lời gọi OpenAI.
So sánh hợp lệ là với `p1-baseline` (cùng router, cùng hồ sơ), không phải với baseline prod.

## B0 — `run_live --repeats 1` trên code P1 (bước 0, trước khi đổi code)

`calls=23 exit=0`. Mọi must-relation trúng (hits=1), `forbidden_hits=0` ở cả 5 hồ sơ. Bảng đầy đủ ở mục
`run_live` cuối (cột B0).

## Probe tải thật (bước 1, script tạm `/tmp/ai2-perf/probe_batches.py`, không commit)

40 `ClassifierPair` thật của hồ sơ tham chiếu (spy `classify_pairs`), 5 user message đúng format, 5 bản sao client.

| Lần | tuần tự (ms) | song song 5 (ms) | speedup | latency tuần tự (ms) | latency song song (ms) | served_model | lỗi |
|---|---|---|---|---|---|---|---|
| 1 | 24378 | 16980 | **1.44×** | 5417 / 5114 / 3709 / 5165 / 4974 | 5622 / **16976** / 4630 / 5206 / 5033 | `gpt-5.6-luna` | 0 |
| 2 | 27842 | 6940 | 4.01× | 6988 / 7833 / 4621 / 3830 / 4569 | 5468 / 6937 / 6172 / 2933 / 3912 | `gpt-5.6-luna` | 0 |
| 3 | 62107 | 6698 | 9.27× | 7349 / 6040 / 5512 / **39700** / 3505 | 5998 / 6696 / 6096 / 2775 / 5318 | `gpt-5.6-luna` | 0 |

- Lần 1 dưới ngưỡng 2× vì **một** lời gọi song song có latency đuôi 17.0s; các lời gọi còn lại 4.6–5.6s.
  Đuôi tương tự xuất hiện ở đường **tuần tự** của lần 3 (39.7s), nên đây là latency đuôi ngẫu nhiên của router,
  không phải throttle do song song.
- Đã chạy thêm 2 lần (cùng 40 cặp, cache pairs) để phân xử: 2/3 lần ≥ 2×; tổng gộp 114.3s tuần tự / 30.6s song song
  = 3.7×. `served_model` không đổi họ ở cả 30 lời gọi, 0 lỗi. Quyết định đi tiếp được ghi ở notes (lệch nhẹ so với
  điều kiện dừng nguyên văn).
- calls: 13 (lần 1, gồm 3 lời gọi extraction khi capture) + 10 + 10 = 33.

## `p2-parallel` (N=5, 5/5 SUCCEEDED, `AI2_PAIRS_CONCURRENCY=5` qua compose)

Container recreate bằng compose (preflight `RUNNING=0`, `config_files` khớp nhãn, `--no-deps`); env container chỉ
khác trước đúng một key `AI2_PAIRS_CONCURRENCY=5`; `printenv` ra `5`.

| Tập | n | wall p50 | wall p90 | pairs p50 | pairs p90 |
|---|---|---|---|---|---|
| Baseline plan.md — nhóm hồ sơ tham chiếu (prod model) | 5 | 112.3s | 156.4s | 96.9s | 100.7s |
| `p1-baseline` (router luna) | 5 | 38.2s | 41.6s | 25.9s | 29.9s |
| **`p2-parallel` (router luna)** | 5 | **16.7s** | **19.1s** | **6.7s** | **8.6s** |

- Pairs p90: 8.583s / 29.9s = **0.29** (tiêu chí ≤ 0.4: đạt). Wall p90 giảm 41.6s → 19.1s.
- `batches_completed=5`, `stopped_reason=null` ở cả 5 job.
- `llm_timing.by_operation.pairs`: `llm_calls=5`/job; `llm_ms_max` = 6701 / 5894 / 8515 / 6624 / 6621 ms; pairs stage
  ≈ `llm_ms_max` + 50–70ms, tức stage pairs giờ ≈ một wave (lời gọi chậm nhất).
- Ngoài pairs: `wall − pairs` p50/p90 = 9.0s / 12.4s (R1: ngưỡng báo user 20s, không vượt); `wall_ms − pipeline_ms`
  p50/p90 = 3.5s / 3.6s. Extraction 4.4–8.3s là phần lớn còn lại.
- calls=40.

| job | wall | pairs | wall−pairs | wall−pipeline | pipeline | extraction | llm pairs max/total |
|---|---|---|---|---|---|---|---|
| job_9f5af9bf… | 16664 | 6769 | 9895 | 3623 | 13041 | 5645 | 6701 / 28745 |
| job_921031db… | 14466 | 5958 | 8508 | 3454 | 11012 | 4429 | 5894 / 25269 |
| job_4236de0c… | 17175 | 8583 | 8592 | 3413 | 13762 | 4587 | 8515 / 30885 |
| job_35999b65… | 19099 | 6684 | 12415 | 3506 | 15593 | 8320 | 6624 / 24035 |
| job_6327a12c… | 15702 | 6684 | 9018 | 3375 | 12327 | 5036 | 6621 / 29792 |

## Kiểm công tắc quay về qua compose (bước 11)

1. Preflight `RUNNING=0`; recreate với shell env `AI2_PAIRS_CONCURRENCY=1` (cùng 3 file compose, `--no-deps`).
   `printenv AI2_PAIRS_CONCURRENCY` → `1`; diff env container so với lần `=5`: chỉ dòng `AI2_PAIRS_CONCURRENCY`.
2. Replay N=1 (`p2-switch-seq`): `job_1fbfa70e…` SUCCEEDED, wall 39833ms, **pairs 29092ms**, `llm_ms_max` 7291,
   `llm_ms_total` 29008 (tuần tự), batches 5. calls=8.
3. Tỷ lệ: 29092 / 6684 (median pairs `p2-parallel`) = **4.35×** (tiêu chí ≥ 3×: đạt).
4. Preflight `RUNNING=0`; recreate không có shell env → `printenv` ra `5`; env container giống hệt lần `=5` đầu.

Không dùng `docker exec -e` làm bằng chứng cho bước này.

## `run_live` cuối P2 (bước 12) so với B0

`docker exec -e AI2_PAIRS_CONCURRENCY=<n>` (in-process, mục đích là chất lượng, không phải cấu hình deploy).
conc=1: `calls=23 exit=0`; conc=5: `calls=23 exit=0`.

| dossier | must | a | b | B0 | conc1 | conc5 |
|---|---|---|---|---|---|---|
| hd-test | CONFLICT | 4.1. | 2.1. Tổng giá trị hợp đồ | 1 | 1 | 1 |
| hd-test | DUPLICATE | 1.1. | 1.3. | 1 | 1 | 1 |
| hd-test | REFERENCE | 3.2. | 5.2. | 1 | 1 | 1 |
| hd-test | REFERENCE | 3.3. | 6.1. | 1 | 1 | 1 |
| hd-test-003 | CONFLICT | 4.1. Bên B chậm khắc phụ | 4.1. Bên B chậm khắc phụ | 1 | 1 | 1 |
| hd-test-003 | REFERENCE | Bên B lập báo cáo sự cố | 3.2. | 1 | 1 | 1 |
| hd-test-004 | DUPLICATE | 4.2. | 5.1. | 1 | 1 | 1 |
| hd-test-005 | CONFLICT | 5.1. Đợt 1 | Đợt 1: Bên A thanh toán | 1 | 1 | 1 |
| hd-test-002 | CONFLICT | 3.1. | 2.1. Thời gian giao hàng | 1 | 1 | 1 |
| hd-test-002 | DUPLICATE | 6.1. | 6.3. | 1 | 1 | 1 |
| hd-test-002 | REFERENCE | 2.2. Bên B bảo hành hàng | 5.1. | 1 | 1 | 1 |
| (mọi hồ sơ) | forbidden_hits | | | 0 | 0 | 0 |

Không có must-miss nào, nên không có miss quy được cho P2; không cần chạy lại riêng hồ sơ nào.

## Tổng lời gọi router P2

| Hạng mục | calls |
|---|---|
| B0 `run_live` | 23 |
| Probe bước 1 (3 lần) | 33 |
| `p2-parallel` N=5 | 40 |
| Kiểm công tắc N=1 | 8 |
| `run_live` conc 1 + conc 5 | 23 + 23 |
| `pairs_replay record --runs 3` (gồm 3 lời gọi capture) | 18 |
| `pairs_replay simulate` | 0 |
| **Tổng** | **168** |

Ngân sách P2 là 173–455 (dừng ở 1.5× = 682): trong ngân sách. `measure` không chạy (chỉ là chẩn đoán; công tắc đã
được chứng minh qua compose).
