# R3 — Budget LLM theo job và xử lý retry/429/quota khi chạy song song

## 1. Budget hiện tại

- Backend gửi `max_llm_calls` với điều kiện `le=20` (`backend/src/contract_intelligence/shared/ai/schemas.py:468`), mặc định 20 (`backend/.../canonical_processing.py:388`). Worker truyền giá trị này vào `ProcessingRuntime` (`ai-service/app/api/main.py:465`). Đường cục bộ cũng mặc định 20 (`idp.py:66-69`).
- Đơn vị tính là **HTTP request**, gồm cả retry và request fallback khi `response_format` bị từ chối (`runtime.py:198-201`, `client.py:221-233`).
- pairs và semantic dùng chung một budget, và chạy **nối tiếp**: pairs ở `idp.py:512`, semantic ở `idp.py:592`. Plan 261016 đã ghi rằng mỗi lượt chạy dùng hết 20/20 và semantic báo `LLM_BUDGET_EXCEEDED` (`plans/261016-1624-ai2-measure-classify-optimize/plan.md:47`), quyết định chính sách còn treo (`:81`).

## 2. Song song có làm vượt budget không?

**Không vượt được trần cứng.** Mọi request đều phải qua `_reserve_http_request` dưới `_request_lock`: kiểm tra `llm_calls_used >= max_llm_calls` rồi tăng (`runtime.py:411-421`). Hook được gọi ngay trước mỗi `chat.completions.create` (`client.py:200-201`, `:224-225`). Test double đi qua `reserve()` ở `runtime.py:450`. Các bước kiểm tra trước không có lock (`runtime.py:343`, `:386`, `pair_classifier.py:377`) chỉ có thể cũ, không thể làm vượt trần.

**Rủi ro thật là phân bổ budget khi lỗi**, không phải vượt trần:

| Kịch bản | Tuần tự (HTTP pairs dùng) | Song song 5 (HTTP pairs dùng) |
|---|---|---|
| Happy path | 5 | 5 (như nhau) |
| Provider chết hẳn (5xx/timeout liên tục) | 3. Batch 1 hết `max_attempts=3` (`runtime.py:209`) rồi dừng (`pair_classifier.py:418-426`) | tối đa **15** (5 batch × 3 lần), vì mọi batch đã bay trước khi batch 1 báo lỗi |
| Lý thuyết xấu nhất (có cả fallback format) | 5 × 3 × 2 = 30, bị cắt ở 20 | như nhau |

Hệ quả: khi provider lỗi, semantic có thể chỉ còn **5 hoặc 0** lời gọi thay vì 17, và kết quả bị gắn `LLM_BUDGET_EXCEEDED` thay vì đúng mã lỗi.

Biện pháp, xếp theo mức đáng làm:
1. Có cờ abort dùng chung. Batch đầu tiên trả `None` hoặc ném `ProcessingTimeout` thì set cờ. `_reserve_http_request` thấy cờ thì từ chối request mới, kể cả retry đang chờ backoff. Kết hợp `cancel_futures=True` (R2 mục 3).
2. Trần riêng cho pairs: ví dụ `pairs_http_cap = max_calls + 2`, kiểm tra trong reserve thông qua một runtime con hoặc một bộ đếm theo operation. Mục đích là semantic luôn còn tối thiểu `20 - pairs_http_cap`. Đây là quyết định chính sách (type-3) và **cần user chốt**.
3. Backoff có jitter (R1, R6).

## 3. Retry / 429 / quota khi nhiều lời gọi cùng bay

- Phân loại lỗi: `classify_provider_error` (`runtime.py:99-121`). Quota (`credit_balance_exhausted`, `insufficient_quota`, …) được nhận ra ở `runtime.py:67-88`. Khi gặp quota thì set `provider_exhausted` và fallback `LLM_QUOTA_EXHAUSTED`, không retry (`runtime.py:370-373`).
- Lỗ hổng khi chạy song song:
  - `provider_exhausted` chỉ được kiểm tra ở **đầu** `complete_json` (`runtime.py:332`).
  - Thread nào đang ngủ backoff vì 429/5xx (`runtime.py:396`) sẽ thức dậy và gửi tiếp, vì `_reserve_http_request` không kiểm tra cờ này (`runtime.py:411-421`). Mỗi thread như vậy đốt thêm tối đa 1–2 request và nhận thêm một 429 quota.
  - Chi phí nhỏ nhưng sai tinh thần "các lời gọi sau trong job không gửi gì" (`plan 261016:46`). Sửa bằng cách cho reserve kiểm tra `provider_exhausted`.
- `Retry-After` được tôn trọng (`runtime.py:175-183`, `:388`). Nếu không có header thì backoff `min(8, 0.5·2^attempt)` **không có jitter** (`runtime.py:390`). Với N thread nhận 429 cùng lúc, chúng sẽ retry cùng lúc.
- SDK retry đã tắt (`client.py:148`, `max_retries=0`), nên không bị nhân đôi số retry. Điều này khớp khuyến nghị của OpenAI là tắt retry SDK khi tự quản lý retry (R6).
- Request thất bại **vẫn tính** vào RPM/TPM của OpenAI (R6). Vì vậy retry đồng loạt dễ làm 429 tệ hơn.
- Router local (9router, `localhost:20128`, `client.py:135`): không tìm thấy tài liệu về giới hạn concurrency. Một số nguồn mô tả router **tự chuyển provider** khi bị throttle (R6). Nếu nó chuyển sang model khác họ, cổng K-a sẽ chặn (`model_family.py:35-36`, `pair_classifier.py:432`) và dẫn tới `LLM_FALLBACK`. Khi chạy song song, xác suất bị throttle tăng [ASSUMED], nên cần quan sát `served_model` theo từng batch sau khi có P0.

## 4. Ghi chú về `stopped_reason MAX_CALLS` (sửa giả định trong scope P0)

Debug report thấy `stopped_reason = null` dù có 468–762 ứng viên. Code cho thấy điều này **đúng như thiết kế**, không phải thiếu ghi:
- Ứng viên bị cắt ở `PAIRS_TOP_K = 40` **trước** classifier (`pair_candidates.py:28`, `:564-569`).
- Phần bị cắt được ghi ở `candidates_capped = len(candidates) - len(kept)` (`pair_candidates.py:583`), và đi vào coverage (`pair_projection.py:43`).
- Classifier nhận đúng 40 = 8 × 5 cặp, nên vòng lặp hết cặp sau 5 batch và **không bao giờ** chạm `MAX_CALLS` (`pair_classifier.py:379-380`).
- `MAX_CALLS` chỉ xuất hiện khi số cặp > 40, như trong test 43 cặp (`tests/test_contract_graph_pair_classifier.py:154-160`).

Vì vậy mục "record stopped_reason MAX_CALLS" trong P0 **không cần sửa code**. Nếu muốn chỉ ra nút thắt về độ phủ thì nên báo `candidates_capped`/`candidates_total`, vốn đã có trong `result_json`. Lưu ý thêm cho P2: tăng batch lên 12–16 **không tăng độ phủ** khi top_k vẫn là 40, chỉ giảm số lời gọi xuống 3–4. Muốn tăng độ phủ thì phải nâng `PAIRS_TOP_K`, nhưng giá trị này bị đóng băng theo `CANDIDATES_VERSION` (`pair_candidates.py:10`, `:33`) và ảnh hưởng chất lượng.

## Kết luận xếp hạng

1. Trần budget **an toàn** khi chạy song song nhờ reserve có lock. Không cần thêm cơ chế chống vượt.
2. **Phải** thêm abort dùng chung và cho reserve kiểm tra `provider_exhausted`. Nếu không, lỗi provider sẽ đốt tới 15/20 lời gọi và làm semantic bị đói.
3. **Nên** có trần pairs riêng. Đây là quyết định chính sách cần user chốt, liên quan tới quyết định budget còn treo từ plan 261016.
4. **Nên** thêm jitter cho backoff.
5. Bỏ mục `MAX_CALLS` khỏi P0 vì không phải lỗi. Thay bằng hiển thị `candidates_capped`.
