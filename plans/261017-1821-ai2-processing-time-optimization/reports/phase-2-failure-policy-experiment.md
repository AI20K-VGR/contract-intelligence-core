# P2 — Thí nghiệm chính sách khi batch lỗi (D4/D14)

Quyết định: **prefix** (user chọn 2026-10-18 qua AskUserQuestion). Mặc định ship vẫn là `prefix` (tương đương tuần tự). `keep_successful` chỉ tồn tại
cho thí nghiệm này (`classify_pairs(..., failure_policy="keep_successful")`, không đọc env, `build_pair_relations`
không truyền tham số); nếu user bác bỏ thì xoá trong follow-up.

## Cách đo

- `pairs_replay record --runs 3 --label d4` (router local, concurrency 5, hồ sơ tham chiếu, 40 cặp, 5 batch):
  3/3 lượt `batches_completed=5`, `stopped_reason=None`, wall pairs 6676 / 6300 / 6506 ms. `calls=18` (15 batch + 3
  lời gọi extraction để capture cặp). File ghi ở `/root/.ai2-perf/pairs-rec-d4-{0,1,2}.json` trong container (ngoài
  repo).
- `pairs_replay simulate` (offline, `calls=0`): với mỗi `k ∈ 0..4` × kind {provider_error, deadline,
  served_model_rejected, quota} × policy {prefix, keep_successful}, cộng một lượt không lỗi. Mỗi ô là **median qua 3
  bản ghi**. Câu trả lời phát lại chờ `latency_ms × 0.002` để thứ tự hoàn tất bám theo bản ghi.
- Định nghĩa:
  - `calls_wasted`: HTTP của các batch có kết quả bị bỏ (chỉ prefix; batch chỉ số > batch lỗi đầu tiên).
  - `http_calls_spent` = `runtime.llm_calls_used`.
  - `relations_total` = số decision được nhận (trước bước citation của `build_pair_relations`).
  - `accepted_after_rejected` = số batch được nhận sau batch lỗi `k` (= `batches_completed − k`, vì chỉ một lỗi).
  - `partial_means_rest_unclassified` = đúng khi không batch nào sau `k` được nhận.
  - `reason_code` theo `ai-service/app/pipeline/idp.py:721-728` (`PARTIAL_<stopped_reason>`);
    `pair_relations_ran` theo `idp.py:643-649` (mode `llm` và `batches_completed ≥ 1`); issue
    `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` chỉ phát ở mode `rule_only`, nên luôn **không** có ở cả hai policy.
- Giới hạn của mô phỏng:
  - kind `deadline` ném `ProcessingTimeout` ngay, trước HTTP, nên ở `prefix` các batch sau thường bị gate chặn trước
    khi reserve (`calls_wasted=0`). Ngoài thực tế deadline thật làm mọi batch cùng hết giờ.
  - Lỗi `provider_error`/`quota` trả về sau latency đã ghi, nên các batch khác thường đã xong: đây là trường hợp xấu
    nhất của KD1/KD4 (lãng phí tối đa).

## Bảng metric (median qua 3 bản ghi)

Lượt không lỗi: 5 HTTP, 10 relation (`CONFLICT` 1, `DUPLICATE` 1, `GENERAL_SPECIFIC` 2, `REFERENCE` 5),
`pairs_unclassified=0`. Relation dồn vào batch đầu (ứng viên xếp theo điểm): batch 0 ≈ 6, batch 1 ≈ 3, batch 2 ≈ 1,
batch 3–4 ≈ 0.

| k | kind | policy | calls_wasted | http_calls_spent | relations_total | relations_delta | pairs_unclassified | batches_completed | accepted_after_rejected | stopped_reason | reason_code | pair_relations_ran | partial_means_rest_unclassified | relations_by_label |
|---|---|---|---|---|---|---|---|---|---|---|---|---|---|---|
| None | None | prefix | 0 | 5 | 10 | 0 | 0 | 5 | 0 | None | None | True | None | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| None | None | keep_successful | 0 | 5 | 10 | 0 | 0 | 5 | 0 | None | None | True | None | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 0 | provider_error | prefix | 4 | 5 | 0 | -10 | 40 | 0 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | False | True | {} |
| 0 | provider_error | keep_successful | 0 | 5 | 4 | -6 | 8 | 4 | 4 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'DUPLICATE': 0, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 1} |
| 0 | deadline | prefix | 0 | 0 | 0 | -10 | 40 | 0 | 0 | DEADLINE | PARTIAL_DEADLINE | False | True | {} |
| 0 | deadline | keep_successful | 0 | 4 | 4 | -6 | 8 | 4 | 4 | DEADLINE | PARTIAL_DEADLINE | True | False | {'DUPLICATE': 0, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 1} |
| 0 | served_model_rejected | prefix | 4 | 5 | 0 | -10 | 40 | 0 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | False | True | {} |
| 0 | served_model_rejected | keep_successful | 0 | 5 | 4 | -6 | 8 | 4 | 4 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'DUPLICATE': 0, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 1} |
| 0 | quota | prefix | 4 | 5 | 0 | -10 | 40 | 0 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | False | True | {} |
| 0 | quota | keep_successful | 0 | 5 | 4 | -6 | 8 | 4 | 4 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'DUPLICATE': 0, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 1} |
| 1 | provider_error | prefix | 3 | 5 | 6 | -4 | 32 | 1 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 4} |
| 1 | provider_error | keep_successful | 0 | 5 | 7 | -3 | 8 | 4 | 3 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 5} |
| 1 | deadline | prefix | 0 | 1 | 6 | -4 | 32 | 1 | 0 | DEADLINE | PARTIAL_DEADLINE | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 4} |
| 1 | deadline | keep_successful | 0 | 4 | 7 | -3 | 8 | 4 | 3 | DEADLINE | PARTIAL_DEADLINE | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 5} |
| 1 | served_model_rejected | prefix | 3 | 5 | 6 | -4 | 32 | 1 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 4} |
| 1 | served_model_rejected | keep_successful | 0 | 5 | 7 | -3 | 8 | 4 | 3 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 5} |
| 1 | quota | prefix | 3 | 5 | 6 | -4 | 32 | 1 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 4} |
| 1 | quota | keep_successful | 0 | 5 | 7 | -3 | 8 | 4 | 3 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'REFERENCE': 5} |
| 2 | provider_error | prefix | 2 | 5 | 9 | -1 | 24 | 2 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | provider_error | keep_successful | 0 | 5 | 9 | -1 | 8 | 4 | 2 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | deadline | prefix | 0 | 2 | 9 | -1 | 24 | 2 | 0 | DEADLINE | PARTIAL_DEADLINE | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | deadline | keep_successful | 0 | 4 | 9 | -1 | 8 | 4 | 2 | DEADLINE | PARTIAL_DEADLINE | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | served_model_rejected | prefix | 2 | 5 | 9 | -1 | 24 | 2 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | served_model_rejected | keep_successful | 0 | 5 | 9 | -1 | 8 | 4 | 2 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | quota | prefix | 2 | 5 | 9 | -1 | 24 | 2 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 2 | quota | keep_successful | 0 | 5 | 9 | -1 | 8 | 4 | 2 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | provider_error | prefix | 1 | 5 | 10 | 0 | 16 | 3 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | provider_error | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 1 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | deadline | prefix | 0 | 3 | 10 | 0 | 16 | 3 | 0 | DEADLINE | PARTIAL_DEADLINE | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | deadline | keep_successful | 0 | 4 | 10 | 0 | 8 | 4 | 1 | DEADLINE | PARTIAL_DEADLINE | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | served_model_rejected | prefix | 1 | 5 | 10 | 0 | 16 | 3 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | served_model_rejected | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 1 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | quota | prefix | 1 | 5 | 10 | 0 | 16 | 3 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 3 | quota | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 1 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | False | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | provider_error | prefix | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | provider_error | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | deadline | prefix | 0 | 4 | 10 | 0 | 8 | 4 | 0 | DEADLINE | PARTIAL_DEADLINE | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | deadline | keep_successful | 0 | 4 | 10 | 0 | 8 | 4 | 0 | DEADLINE | PARTIAL_DEADLINE | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | served_model_rejected | prefix | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | served_model_rejected | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | quota | prefix | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |
| 4 | quota | keep_successful | 0 | 5 | 10 | 0 | 8 | 4 | 0 | LLM_FALLBACK | PARTIAL_LLM_FALLBACK | True | True | {'CONFLICT': 1, 'DUPLICATE': 1, 'GENERAL_SPECIFIC': 2, 'REFERENCE': 5} |

## Nhóm metric bắt buộc

**Lời gọi lãng phí.** `prefix`: `calls_wasted = 4 − k` cho provider_error / served_model_rejected / quota (mọi batch
sau `k` đã bay xong rồi mới bị bỏ: KD1/KD4); `http_calls_spent = 5` ở cả hai policy (trừ deadline). `keep_successful`:
`calls_wasted = 0` (mọi HTTP đã chi đều được dùng).

**Relation giữ được.** Tại `k=0`: `prefix` 0 relation (Δ −10, `pairs_unclassified=40`, `batches_completed=0`);
`keep_successful` 4 relation (Δ −6, `pairs_unclassified=8`, `batches_completed=4`). Tại `k=1`: 6 so với 7. Tại
`k=2`: 9 so với 9 (Δ −1 ở cả hai). Tại `k ≥ 3`: 10 so với 10 (batch 3–4 không có relation trong hồ sơ này). Chỉ
`pairs_unclassified` khác (prefix `8·(5−k)`, keep luôn 8).

**Cổng họ model (K-a).** Với `served_model_rejected` ở `keep_successful`: số batch được nhận sau batch bị K-a chặn =
`4 − k` (k=0: 4 batch). Mỗi batch được nhận vẫn tự qua K-a theo `served_model` của chính nó, nhưng tín hiệu "router đã
phục vụ bằng model ngoài họ classifier trong job này" bị bỏ qua cho phần còn lại của job
(`research/02-determinism-and-failure.md` §3 coi đây là tín hiệu toàn job).

**Ngữ nghĩa `PARTIAL_*`.** `stopped_reason`/`reason_code` giống nhau ở hai policy (`PARTIAL_LLM_FALLBACK` hoặc
`PARTIAL_DEADLINE`). `pair_relations_ran` khác tại `k=0` (prefix `False`, keep `True`). Issue `LIMITED_COVERAGE`:
không có ở cả hai (mode `llm`). Câu hỏi "PARTIAL còn nghĩa là phần còn lại chưa được phân loại không?":
- `prefix`: **có**, mọi ô (`partial_means_rest_unclassified=True`).
- `keep_successful`: **không**, với mọi `k < 4` (batch sau `k` đã được phân loại); chỉ đúng khi `k=4`.

## Tần suất thật

SQL của phase trên `ai2.jobs` local (2026-10-18): `4|28`. 11 trong 28 job là replay `perf-*` của P1/P2 (đều thành
công). Bỏ replay (`request_id not like 'perf-%'`): **4/17 = 23.5%** job ở mode `llm` có
`stopped_reason=LLM_FALLBACK`, khớp giá trị tham chiếu của red-team. Cả 4 đều `batches_completed=0` (lỗi ở `k=0`):
3 job có `pairs.llm_calls=1` (một request, lỗi không retry, trả về nhanh), 1 job có `pairs.llm_calls=3` (hết
attempts). Phân bố khác (job llm): `null`/5 batch: 11, `null`/1 batch: 2.

## KD1/KD4 quy đổi theo tần suất (F11)

- **KD1 (HTTP thêm)**, `prefix`, lỗi ở `k=0`: tối đa +4 HTTP mỗi job lỗi (4 batch còn lại đã bay). Bình quân trên
  job mode `llm`: `4 × 4/17 ≈ 0.94` HTTP/job. Không vượt budget (INV-5; `llm_calls_used ≤ max_llm_calls` được test
  khoá).
- **KD4 (thời gian chờ join)**: bản tuần tự trả về ngay khi batch 0 lỗi; bản song song chờ batch đang bay xong.
  - 3/4 job lỗi nhanh (một request): chờ thêm ≈ latency lớn nhất của batch khác ≈ `llm_ms_max` của `p2-parallel`
    = 5.9–8.5s (median 6.6s).
  - 1/4 job lỗi sau retry: batch 0 chậm hơn các batch khác, chờ thêm ≈ 0.
  - Bình quân trên job mode `llm`: `3/17 × 6.6s ≈ 1.2s`/job. So với lợi ích happy path (pairs p50 25.9s → 6.7s,
    tức ≈ −19s ở 11/17 job đủ 5 batch), chi phí này nhỏ.
- `keep_successful` không đổi KD1 về số HTTP (vẫn chi 5), nhưng dùng hết; KD4 như prefix (vẫn phải chờ mọi batch).

## Phạm vi tất định (F6/D14)

- **INV-2 đúng** (test `tests/test_contract_graph_pairs_parallel.py::test_parallel_equals_sequential_with_failure`,
  12 ô `k ∈ {0,2,4}` × {provider/None, `ProcessingTimeout` ném trong batch, K-a, quota khi `j<k` thành công lần đầu}):
  song song `prefix` = tuần tự ở decisions, chuỗi event, stats (trừ `llm_calls`/token), `stopped_reason`,
  `batches_completed`, issues, `fallback_count`; trace của các batch đã nhận là tiền tố của trace song song.
- **Không tất định / khác tuần tự**, nêu thẳng:
  - KD2 (`test_kd2_budget_contention_invariants`): tranh slot budget cuối khi có retry. Tuần tự dừng
    `BUDGET_EXHAUSTED` không issue; song song ra `LLM_FALLBACK` + một issue (`LLM_BUDGET_EXCEEDED` hoặc
    `LLM_UNAVAILABLE`), batch nào thua phụ thuộc thứ tự thức dậy. Test chỉ khoá bất biến, không khoá batch thua.
  - KD3 (`test_kd3_deadline_checked_at_submit`): deadline kiểm một lần lúc submit; song song hoàn tất 5 batch khi
    tuần tự cắt ở batch 2.
  - KD6 (`test_quota_during_lower_batch_backoff[retry_ok|retry_quota]`): quota lật trong lúc batch nhỏ hơn đang
    backoff; batch đó vẫn retry tới provider và có thể thành `k` mới (mất relation của nó), issue
    `LLM_QUOTA_EXHAUSTED` vẫn có.
- `keep_successful` **không** tương đương tuần tự theo thiết kế (nhiều relation hơn, `pairs_unclassified` khác,
  `PARTIAL_*` đổi nghĩa).

## Khuyến nghị

Giữ `prefix` làm mặc định (đúng D4). Lý do bằng số:
- Ở dữ liệu thật, mọi lỗi đều ở `k=0`; `keep_successful` khi đó lấy lại 4/10 relation, nhưng đổi nghĩa
  `PARTIAL_*` (phần còn lại không còn là "chưa phân loại") và nhận 4 batch sau một lần K-a bị chặn.
- Chi phí của `prefix` so với tuần tự là ≈ 0.94 HTTP và ≈ 1.2s mỗi job mode `llm` (bình quân), nhỏ so với ≈ 19s lợi
  ích mỗi job đủ batch.

Nếu user muốn giữ phần thành công, phương án hẹp hơn đáng cân nhắc ở follow-up: chỉ giữ batch sau `k` khi lỗi là
provider/deadline (không áp cho K-a và quota), kèm reason code riêng thay cho `PARTIAL_*`. Việc đó ngoài phạm vi P2.

**Quyết định của user: prefix** (2026-10-18, AskUserQuestion ở cổng cuối P2; probe bước 1 lệch ngưỡng 2× cũng được user chấp nhận).
