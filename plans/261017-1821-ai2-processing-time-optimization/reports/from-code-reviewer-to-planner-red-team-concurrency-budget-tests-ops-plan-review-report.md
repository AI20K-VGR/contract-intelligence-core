# Red-team plan review — 261017-1821-ai2-processing-time-optimization

Ngày 2026-10-17. Đối tượng: `plan.md`, `plan-graph.yaml`, `phases/phase-1..3`, `research/00..06`. Chỉ đọc; không sửa code/plan.
Mọi lệnh repro bên dưới đều chỉ-đọc (render compose, SQL select, Python thuần), không có lời gọi LLM.

**Verdict:** CHƯA sẵn sàng cook nguyên trạng. Không có đường mất dữ liệu production ngay, nhưng có 1 High (công tắc quay về ở
production vô hiệu) và 7 Medium phải sửa trong plan trước khi cook (rẻ, mỗi cái vài dòng plan).

## Persona

| Persona | Bề mặt tấn công |
|---|---|
| A — Concurrency/determinism engineer | `_AbortGate`, `provider_exhausted`, issue sink, `ThreadPoolExecutor`, INV-1..5, KD1..5 |
| B — LLM budget & provider-failure operator | budget 20 lời gọi, quota/429, chi phí bake-off, tần suất failure path thật |
| C — Test/golden integrity | golden, fake client dưới `copy.copy`, cơ chế ghim test, cổng `run_live`/`score`, quy tắc band của bake-off |
| D — Ops/deploy | rollback bằng env, compose prod, replay trên DB local, provenance của relation đã lưu |

## Bảng phát hiện (xếp theo mức độ)

| ID | Mức | Loại | Anchor | Cách sửa rẻ nhất |
|---|---|---|---|---|
| F1 | **High** | proven | `deploy/compose.prod.yml:151` (`env_file: !reset []`), `:152-180` (không có `AI2_PAIRS_*`); claim ở `plan.md:317-318`, `phase-2:354-356` | Thêm `AI2_PAIRS_CONCURRENCY: ${AI2_PAIRS_CONCURRENCY:-5}` và `AI2_PAIRS_REASONING_EFFORT: ${AI2_PAIRS_REASONING_EFFORT:-}` vào `environment:` của `deploy/compose.prod.yml` và `docker-compose.yml`, cộng `deploy/.env.prod.example` (cần user OK vì là file ops). Không thì sửa bảng Rollback thành "chỉ `git revert` + redeploy" |
| F2 | Medium | proven (trace qua plan + code) | `phase-2:81-83` (reserve chặn theo `provider_exhausted` toàn cục), `:64` (bỏ `sink_j`, `j>k`), `:265` (RC2 "không có issue thêm"), `runtime.py:332-333`, `:370-373` | Khi reserve từ chối vì `provider_exhausted` (không phải vì gate), ghi `LLM_QUOTA_EXHAUSTED` vào sink của **chính batch đó**; hoặc chỉ để gate theo chỉ số chặn batch pairs. Thêm biến thể R2.2 "batch 1 đang ngủ backoff 429, batch 3 nhận `insufficient_quota`" |
| F3 | Medium | proven | `phase-2:32` (`min(concurrency, n_planned)`), `pair_builder.py:57-72` (gate không kiểm số ứng viên), `pair_builder.py:172`; test `tests/test_contract_graph_pair_builder.py:137-140`; lối thoát `phase-2:224-225` | `n_planned == 0` → đi đường tuần tự, không tạo executor. Thêm R2 test `pairs=[]`. Cấm ghim `concurrency=1` cho test nào khi chưa có root cause ghi trong comment |
| F4 | Medium | proven | `harness/plugins/hs/skills/bakeoff/scripts/bakeoff_rank.py:104-105` (band = max(5%, **spread max−min**)); metric ở `phase-3:52-54`; spread lịch sử `perf-…-debug-report.md:28` (41.1–79.0s) | Đổi metric của `trial` sang đại lượng ít nhiễu: median latency **từng lời gọi** trên cả 25 lời gọi/ứng viên (hoặc `completion_tokens`), giữ wall làm drift. Ghi trước trong plan: tie mà C1 nhanh hơn ở median per-call → người quyết |
| F5 | Medium | proven | `phase-3:76-77` (median `trial` so với ngân sách tính bằng p90) | Dùng p90/max của 5 trial (nearest-rank) trong F3.4, không dùng median |
| F6 | Medium | proven | `plan.md:271-272` vs `phase-2:128` (KD2), `:129` (KD3), `:138-139` (INV-2), `:85-87` (jitter ngẫu nhiên), `:260` (R2.2) | Sửa `plan.md:272` và INV-2 để loại trừ KD2/KD3. Thêm test cho KD3. Ghi rõ KD2 là **không tất định** (batch nào giành slot budget cuối phụ thuộc thứ tự thức dậy có jitter). Báo cáo D4 phải nói điều này với user |
| F7 | Medium | proven | `phase-3:91-92` (`PROMPT_VERSION` vẫn `pairs-v13`), claim `plan.md:318`; `pair_builder.py` gán `classifier_model=decision.served_model or model`, `prompt_version=PROMPT_VERSION` | Ghi cấu hình vào provenance khi ship C1/C2: hậu tố `prompt_version` (ví dụ `pairs-v13+effort-low`) hoặc key `reasoning_effort`/`pairs_per_call` trong `coverage.contract_graph.pairs` (object mở) |
| F8 | Low | proven | `phase-2:206-210` (bước 1 dùng `pairs_replay record`), `:226` (file chỉ được tạo ở bước 7), `:107` (`record` chạy `build_pair_relations` với concurrency 5) | Bước 1 dùng script tạm `/tmp`: dựng 5 message batch thật bằng code hiện tại, dispatch bằng `ThreadPoolExecutor` trên bản sao client (giống P1 bước 1) |
| F9 | Low | proven | `phase-3:102-105` (ước 400–600) vs số lần chạy `gate` ở `phase-3:156`, `:73`, `:173`, `:245`; `fixtures/seeded/common.py:161` (`max_llm_calls` 20) | Gộp G1 với lệnh `gate` của Regression Gate; tái dùng kết quả gate nếu cấu hình không đổi; nêu lại ước lượng ≈1150–1850 lời gọi và hỏi user về quota router |
| F10 | Low | proven | `research/05-quality-guards.md:16` (khuyến nghị `run_live` cho đổi song song) vs P2 không có cổng live; `scripts/capture_idp_golden.py:291` (`egress_allowed=False`); `plan.md:298-299` | Cuối P2 chạy `run_live --repeats 1` với `AI2_PAIRS_CONCURRENCY=1` và `=5` để có baseline trước P3. Ghi trong plan rằng golden không phủ đường LLM của pairs |
| F11 | Low | proven | `plan.md:329` (R4 "Thấp") vs SQL của chính plan `phase-2:234` → `4|17` | Nâng R4/KD1 lên TB. Với `batches_completed=0`, mỗi job lỗi ở `k=0` sẽ trả thêm tới 4 HTTP dưới prefix + song song |
| F12 | Low | `[ASSUMED]` | `phase-3:48` (patch `pair_classifier.PAIRS_PER_CALL`), `phase-2:216-219` (tách `_plan_batches`/`_batch_messages`), `pair_candidates.py:28` (`PAIRS_TOP_K = 40`) | `trial` phải assert kích thước batch quan sát được (từ file drift) bằng 10. Cân nhắc bỏ C2 vì chỉ có một wave (xem chi tiết) |
| F13 | Low | proven | `fixtures/contract_graph_pair_records.py:47`, `:56` (`self.calls += 1` trên bản sao); `tests/test_contract_graph_pairs_idp_integration.py:34`, `:152` | Test "không gọi LLM" assert qua `runtime.llm_calls_used`, không qua bộ đếm của fake; ghi quy ước này trong P2 |
| F14 | Low | proven (đã chấp nhận) | `plan.md:252-254` | Trước replay đầu tiên, dump các dòng `ai2` của `dos_01M4ZMW1F0MCE95QGPF04Y7MYM` ra `$HOME/.ai2-perf/` để khôi phục được |

Các mục `proven` có anchor file:line và/hoặc lệnh repro bên dưới. F12 là `[ASSUMED]`: phụ thuộc cách implement, nên chuyển sang validation, không chặn.

## Chi tiết

### F1 — Công tắc quay về `AI2_PAIRS_CONCURRENCY=1` không có tác dụng ở production (High, persona D)

- Claim: `plan.md:317` nói "Operator thêm `AI2_PAIRS_CONCURRENCY=1` vào env của môi trường … rồi recreate container: về đường tuần
  tự, không cần build". `plan.md:318` claim tương tự cho `AI2_PAIRS_REASONING_EFFORT`.
- Thực tế:
  - `deploy/compose.prod.yml:151` reset `env_file` của `ai2-service` (`!reset []`). Container chỉ nhận các key được map trong
    `environment:` (`:152-180`), và không có key `AI2_PAIRS_*` nào ở đó.
  - `deploy/.env.prod.example:91-92` lại ghi rằng ai2-service đọc `ai-service/.env` qua `env_file`. Operator làm theo comment
    này sẽ sửa một file bị bỏ qua.
- Repro (chỉ render config, không chạy gì):
  ```text
  AI2_DB_PASSWORD=x AI2_LLM_BASE_URL=http://x AI2_LLM_API_KEY=x AI2_EMBEDDING_BASE_URL=http://x AI2_EMBEDDING_API_KEY=x \
    docker compose -f docker-compose.yml -f deploy/compose.prod.yml --env-file deploy/.env.prod.example config ai2-service | grep -c OPENAI_API_KEY
  # → 0  (bản render local `docker compose -f docker-compose.yml config ai2-service` có OPENAI_API_KEY từ ai-service/.env)
  ```
- Kiểm chứng của plan không phát hiện được lỗ hổng này. `phase-2:354-356` chỉ chứng minh bằng `docker exec -e AI2_PAIRS_CONCURRENCY=1 …
  pairs_replay measure`, tức đọc env trong một process in-process mới, không đi qua đường cấu hình deploy.
- Hệ quả: sự cố P2 đầu tiên ở production (router/OpenAI throttle, K-a chặn) chỉ có đường revert + redeploy. Không có "cách quay về
  nhanh". Với P3, khi `PAIRS_REASONING_DEFAULT="low"` được ship trong code (`phase-3:84-88`), env rỗng sẽ rơi về default "low".
  Vì vậy không có giá trị env nào khôi phục được trạng thái cũ "không gửi `reasoning_effort`"; `medium` tường minh chỉ tương
  đương nếu default của provider đúng là medium.
- Ràng buộc: user cấm đổi backend/FE, còn compose là file ops nên vẫn cần user cho phép. Nếu không được phép, phải hạ bảng
  Rollback xuống đúng sự thật.

### F2 — Cạn quota trong lúc song song làm mất `LLM_QUOTA_EXHAUSTED` và mất batch trước `k` (Medium, persona A+B)

Input kích hoạt (vector kết quả theo batch). Batch 0 thành công. Batch 1, lần thử 1, nhận 429 tạm thời rồi ngủ backoff khoảng
0.5s. Batch 3 nhận 429 với body `{"error":{"code":"insufficient_quota"}}` lúc t≈0.1s. Các batch khác thành công.

| | Tuần tự (hiện tại) | Song song theo plan |
|---|---|---|
| batch 1 | retry thành công | thức dậy → reserve thấy `provider_exhausted` (`phase-2:81-83`) → `LLMRequestCancelled` → `None`, **không issue** |
| `k` | 3 | 1 |
| issue | `LLM_QUOTA_EXHAUSTED` (`runtime.py:370-373`) | nằm trong `sink_3`, bị bỏ vì `3 > k` (`phase-2:64`) |
| stage sau | semantic trả `None` (`runtime.py:332-333`) | như bên trái, nhưng `runtime.issues` không có mã nào giải thích; `frame_context.py:986` mất reason |
| relation | batch 0–2 | chỉ batch 0 |

- Vi phạm INV-2 (`phase-2:138-139`) ở cả mức cặp lẫn issue.
- Đi ngược lý do của VL-6 (`plan.md:343`): gate theo chỉ số tồn tại để batch `j<k` giữ quyền retry, nhưng `provider_exhausted`
  là cờ toàn cục và đi vòng qua gate.
- RC2 (`phase-2:265`) đang mã hoá đúng hành vi sai này ("không có HTTP hay issue thêm").
- Khả năng xảy ra: thấp, cần 429 tạm thời và quota bị lật cùng lúc. Tác động: chẩn đoán sai (`stopped_reason=LLM_FALLBACK` thay vì
  quota) và mất relation có thể đã có.

### F3 — `ThreadPoolExecutor(max_workers=0)` khi không có ứng viên (Medium, persona A+C)

- Repro:
  ```text
  cd ai-service && uv run --no-sync python -c "from concurrent.futures import ThreadPoolExecutor; ThreadPoolExecutor(max_workers=min(5, 0))"
  # → ValueError: max_workers must be greater than 0   (CPython 3.12.13)
  ```
- Đường xảy ra: `gate()` (`pair_builder.py:57-72`) không kiểm số ứng viên, và `classify_pairs` vẫn được gọi với `pairs=[]`
  (`pair_builder.py:172`). Theo F2.1, đường song song tạo executor với `min(5, 0)` worker. ValueError được `idp.py:527-546` bắt,
  nên mọi job có consent mà 0 ứng viên đều nhận `CONTRACT_GRAPH_PAIRS_FAILED` cùng `NEEDS_REVIEW` giả.
- Test hiện có sẽ đỏ: `test_luong1_edges_excluded_from_candidates` (`tests/test_contract_graph_pair_builder.py:137-140`, 0 ứng
  viên, `ProcessingRuntime` thật, mặc định 5). Đây là điều tốt.
- Lỗ hổng nằm ở bước 6 (`phase-2:224-225`): plan cho phép "ghim `concurrency=1` riêng test đó" khi fake phụ thuộc thứ tự. Người
  implement thấy test này đỏ có thể ghim nó, và bug production bị che lại.

### F4 — Quy tắc band của bake-off gần như luôn ra hoà với metric này (Medium, persona C)

- Band là `max(rel_band·rep, max_c(max−min trial))` (`bakeoff_rank.py:104-105`). Metric `trial` là wall của
  `build_pair_relations` song song, tức **max của 5 latency**, một thống kê đuôi nhiều nhiễu. Họ hồ sơ 762 ứng viên đã dao động
  41.1–79.0s với cùng 5 lời gọi (`perf-…-debug-report.md:28`).
- Repro bằng số minh hoạ: C1 nhanh hơn C0 khoảng 24% ở median, spread mỗi ứng viên 7–9s.
  ```text
  python -c "import sys; sys.path.insert(0,'harness/plugins/hs/skills/bakeoff/scripts'); import bakeoff_rank as b; \
  print(b.compute_verdict({'C0':[20,24,18,27,21],'C1':[15,18,14,22,16]}, direction='lower', noise='high', rel_band=0.05)['rationale'])"
  # → gap 5 <= band 9 (max of 5% relative and observed spread 9) -> tie within noise
  ```
- Hệ quả: F3.3 "chọn theo số" thoái hoá thành AskUserQuestion ở mọi stage. Tốn 50 lời gọi/stage mà không có quyết định cơ học.

### F5 — Điều kiện dừng sớm F3.4 trộn median với p90 (Medium, persona C)

- `phase-3:76-77`: dừng khi `median(trial) ≤ 40 − p90(phần ngoài pairs) − 3`. Mục tiêu lại là **p90** wall (`plan.md:51`).
- Phản ví dụ: median pairs 22s, p90 phần ngoài pairs 12s → ngưỡng 25s → dừng. Nhưng p90 pairs có thể khoảng 30s, nên wall p90
  khoảng 42s. Kết cục là `NOT_MET` ở `p3-final`, trong khi C2/C3 chưa từng chạy.

### F6 — Claim "failure path giống hệt ở mức cặp" sai, và KD2 không tất định (Medium, persona A)

- `plan.md:271-272` claim "Trên failure path, output ở mức cặp vẫn giống hệt; chỉ bộ đếm chi tiêu khác". Chính phase 2 lại mô tả
  hai sai khác ở mức cặp: KD2 (`phase-2:128`, batch `k` mất kết quả vì reserve bị từ chối) và KD3 (`:129`, song song phủ nhiều
  hơn). INV-2 (`:138-139`) vẫn ghi "mọi vector kết quả có lỗi tại batch k: bằng nhau".
- KD2 dưới song song còn là ngẫu nhiên. Khi hai batch cùng retry mà chỉ còn một slot budget, batch thắng là batch thức dậy trước.
  Thời điểm thức dậy có `jitter = random.random` (`:85-87`). Tuần tự thì luôn ưu tiên chỉ số nhỏ.
- R2.2 (`:260`) chỉ tiêm DEADLINE dưới dạng `ProcessingTimeout` từ fake, nên predicate trước dispatch của KD3 không được test.
- User sẽ quyết D4 dựa trên claim sai này.

### F7 — Relation production sau khi ship C1/C2 mất provenance (Medium, persona D)

- `plan.md:318` nói relation đã lưu "vẫn mang `classifier_model`/`prompt_version`, không cần migrate". Nhưng C1 (effort) và C2
  (batch) không đổi trường nào trong hai trường này. `phase-3:91-92` còn chủ động giữ `pairs-v13`.
- Sau khi rollback, không phân biệt được relation nào sinh bởi `low` hay batch 10, nên không thể chạy lại hoặc dọn có chọn lọc.
  Chi tiết ở mục "Đường không đảo ngược".

### F8–F14 (Low)

- **F8.** Bước probe "dừng trước khi refactor" phụ thuộc chính bản refactor: `pairs_replay record` chạy
  `build_pair_relations` với concurrency 5 (`phase-2:107`), mà file này chỉ được tạo ở bước 7 (`:226`).
- **F9.** `gate` tốn tối đa 5×3×20 = 300 lời gọi mỗi lần và chạy ít nhất 3–4 lần: C0 ở bước 1, sau mỗi stage thắng, G1 ở bước 9,
  và dòng gate trong Regression Gate `:245`. Cộng 50 lời gọi/stage và 200 cho `p3-final`, tổng ≈1150–1850, gấp 2–3 lần NF3.3.
- **F10.** Golden không phủ đường LLM của pairs: `egress_allowed=False` ở `capture_idp_golden.py:291`, và phần lớn test chạy với
  `pairs=false`. Cổng live đầu tiên là `gate C0` ở P3, chạy trên code P2. Nếu C0 đỏ thì không quy được lỗi cho P2 hay cho trạng
  thái có sẵn từ trước.
- **F11.** SQL chỉ-đọc của chính plan (`phase-2:234`) trên DB local trả `4|17`. Các job đó có `stopped_reason=LLM_FALLBACK` và
  `batches_completed=0`, tức failure path ở `k=0` chiếm khoảng 24% số job LLM-mode local, chứ không "Thấp". Dưới prefix + song
  song, mỗi job như vậy trả thêm tới 4 HTTP (KD1) và chờ join tới một latency (KD4).
- **F12** `[ASSUMED]`.
  - Nếu `_batch_messages` bind `size=PAIRS_PER_CALL` làm default arg, patch thuộc tính ở `phase-3:48` không có tác dụng, và R3.6a
    chỉ kiểm việc set/restore.
  - Ngay cả khi patch có tác dụng: `PAIRS_TOP_K = 40` (`pair_candidates.py:28`) cho ra 4 batch × 10 trong **một** wave. Wall = max
    của các lời gọi lớn hơn, nên về cấu trúc C2 không nhanh hơn C0. Lợi ích duy nhất là tiết kiệm 1 lời gọi budget, mà metric
    không đo điều đó.
- **F13.** `copy.copy(FakePairLLM)` làm `self.calls += 1` tăng trên bản sao, nên `llm.calls` của bản gốc giữ 0. Các assert
  `llm.calls == 0` (`…idp_integration.py:34`, `:152`) hiện đúng, nhưng sau P2 sẽ không còn khả năng phát hiện regression "lỡ gọi
  LLM".
- **F14.** Xem mục "Đường không đảo ngược".

## Đường không đảo ngược

1. **Provenance relation production (F7).** Mỗi job production chạy sau khi ship C1 (`PAIRS_REASONING_DEFAULT="low"`) hoặc C2
   lưu relation với `prompt_version=pairs-v13` và `classifier_model=<served>`, giống hệt cấu hình cũ. Sau rollback, tập relation
   này không lọc ra được để chạy lại.
   - Điều kiện chấp nhận: ghi effort/batch vào provenance (hậu tố `prompt_version` hoặc key trong coverage pairs) **trước** khi
     default production đổi.
   - Mức: Medium, vì ghi vào dữ liệu bền production và không có migration nào phục hồi được.
2. **Snapshot AI2 của hồ sơ tham chiếu ở local (F14).**
   - Sự việc: mỗi replay gọi `complete_with_snapshot` trên `dos_01M4ZMW1F0MCE95QGPF04Y7MYM` (`plan.md:252-254`), tổng cộng ≥20
     lần qua P1/P2/P3. `/ask` và `/query` của backend đi qua AI2 snapshot (commit `1dfe2972`), nên câu trả lời cho hồ sơ này đổi
     theo cấu hình đo cuối cùng, dù bảng read model của backend không đổi.
   - Plan đã chấp nhận rủi ro này, nhưng không có bước backup.
   - Điều kiện chấp nhận: dump các dòng `ai2` của dossier trước replay đầu tiên, hoặc user xác nhận dữ liệu local đó là đồ bỏ
     được.
3. **Quota router (F9).** Khoảng 1150–1850 lời gọi là chi phí tiêu hao, không hoàn lại được. Rủi ro thấp, nhưng phải được user
   biết trước, vì ước lượng hiện tại thấp hơn 2–3 lần.

## Rủi ro còn lại chấp nhận được (kèm điều kiện)

| Rủi ro | Chấp nhận khi |
|---|---|
| KD1/KD4: tiền và thời gian chờ cho batch bị bỏ | Báo cáo D4 lượng hoá theo tần suất thật (F11) và user ký nhận |
| Container local có `AI2_EMBEDDING_BASE_URL=https://api.openai.com/v1` cùng key embedding (OBSERVED `printenv`, đã che giá trị). Guard của harness chỉ kiểm URL LLM | Job IDP không gọi embedding (embedding chỉ ở `/query`, `main.py:1251-1265`; `AI2_QUERY_USE_VECTOR=false`). Không gọi `/query` có vector và không gọi `/readyz` full-path trong lúc đo |
| Dòng `ai2.llm_call` (logger `app.pipeline.runtime`) vẫn vô hình trong `docker logs`, vì chỉ `ai2.timing` được gắn handler (F1.7) | Số liệu từng lời gọi lấy từ `coverage.llm_timing`. INV-4/R2.12 về log chỉ là bằng chứng ở mức test |
| Router throttle với batch thật [ASSUMED] | Probe ở P2 bước 1 chạy được trước refactor (sau khi sửa F8) |
| Thread daemon `call_with_timeout` sống sau join | `cancelled.set()` chặn reserve muộn (`runtime.py:399`, `:416`). Trace muộn chỉ rơi vào bản sao đã bỏ |
| R5: kết quả router không chuyển được sang `gpt-5.5` | Đổi default production chỉ khi user xác nhận (`phase-3:84-88`), như plan đã ghi |

## Đã kiểm, không phải finding

- Coverage là object mở. Không test, backend hay FE nào lặp hoặc so khớp tập key của coverage.
- Golden P1 an toàn, vì `llm_timing` chỉ có khi có lời gọi.
- Fixture integration của pairs có 11 ứng viên, tức 2 batch, nên đường song song có chạy thật ở TB2.2.
- Seeded dossier có 40/13/32/7/32 ứng viên, nên `run_live` phủ được nhiều batch.
- Jitter chỉ phá assert `sleeps` ở `test_st067_bounded_jobs.py:132`. Plan đã ghim chỗ đó.
- SQL tần suất ở `phase-2:234` chạy đúng trên Postgres local.
