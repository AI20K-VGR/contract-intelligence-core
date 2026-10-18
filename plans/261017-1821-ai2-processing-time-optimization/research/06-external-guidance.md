# R6 — Hướng dẫn bên ngoài: song song, rate limit, prompt caching, reasoning effort

Độ tin cậy nguồn: docs chính thức của OpenAI > cookbook OpenAI > issue GitHub của SDK > trang bên thứ ba. Tất cả claim dưới đây đều **đọc từ tài liệu**, nên chỉ là giả thuyết cho tới khi có bake-off (hs:research probe-first).

## 1. Song song và rate limit (3 nguồn độc lập)

| Claim | Nguồn |
|---|---|
| Có limit theo RPM/RPD/TPM/TPD, chạm chiều nào trước thì bị chặn trước. TPM của một request = max(`max_tokens`, số token ước lượng) | [OpenAI Rate limits](https://developers.openai.com/api/docs/guides/rate-limits) |
| Request thất bại **vẫn tính** vào limit theo phút | Rate limits (như trên) + [Cookbook: How to handle rate limits](https://developers.openai.com/cookbook/examples/how_to_handle_rate_limits) |
| 429: coi `Retry-After` là thời gian chờ tối thiểu và **cộng jitter**. Nếu không có header thì backoff mũ có jitter, giới hạn số lần và tổng thời gian. Nếu tự retry thì **tắt retry SDK**. Không retry lỗi quota/billing | Rate limits + Cookbook |
| Không có trần concurrency công bố. Có thể nhận `slow_down` 429 khi lưu lượng **tăng quá nhanh**, kể cả khi còn dưới RPM/TPM | Rate limits |
| "If the steps are not strictly sequential, you can split them out into parallel calls." | [OpenAI Latency optimization](https://developers.openai.com/api/docs/guides/latency-optimization) |
| Cookbook có script xử lý song song, giới hạn cả request lẫn token mỗi phút | Cookbook |

Đối chiếu với code:
- SDK retry đã tắt (`client.py:148`). ✓
- Quota không retry (`runtime.py:370-373`). ✓
- `Retry-After` được tôn trọng (`runtime.py:388`). ✓
- **Thiếu jitter** (`runtime.py:390`). ✗
- 5 request song song mỗi job, với `AI2_MAX_CONCURRENT_JOBS=1`, là mức tải rất thấp so với tier thông thường [ASSUMED, chưa biết tier của tài khoản].

SDK/HTTP thread-safety:
- Không tìm thấy tuyên bố chính thức của openai-python. Có báo cáo `httpx.PoolTimeout` khi tải cao đa luồng ([openai-python#2539](https://github.com/openai/openai-python/issues/2539), [#2538](https://github.com/openai/openai-python/issues/2538)).
- httpcore mô tả pool "thread-safe and task-safe" ([httpcore2 connection pools](https://pydantic.dev/docs/httpx2/httpcore2/connection-pools/)).
- SDK cài trong venv (`openai 3.14.0`) đặt `max_connections=1000`. Với 5 lời gọi thì không chạm pool.
- Kết luận: dùng chung một instance `OpenAI` qua 5 thread là chấp nhận được (độ tin cậy trung bình).

Router 9router (`localhost:20128`):
- Chỉ có nguồn bên thứ ba ([cloudzy](https://cloudzy.com/marketplace/9router/), [viblo](https://viblo.asia/p/9router-la-gi-llm-gateway-hoan-hao-cho-ai-coding-tools-gjLN0MRW432)).
- Các nguồn này mô tả router tự **chuyển provider khi bị throttle hoặc hết quota**, nhưng không nói gì về trần concurrency.
- Độ tin cậy thấp. Cần đo thực tế.

## 2. Prompt caching (OpenAI, docs chính thức + đối chiếu latency guide)

[Prompt caching guide](https://developers.openai.com/api/docs/guides/prompt-caching):
- Chỉ trúng cache khi **toàn bộ prefix** khớp. Nên đặt phần tĩnh lên đầu và phần động ở cuối.
- GPT-5.6+ yêu cầu prefix tối thiểu 1.024 token hiển thị. Model cũ hơn thì ngưỡng "varies by request settings".
- Cache nằm trên từng máy. Trên khoảng 15 RPM cho mỗi prefix/key thì có thể bị "overflow routing", tức không trúng cache. `prompt_cache_key` có ảnh hưởng tới routing nhưng không đảm bảo trúng.
- Thời gian giữ: `in_memory` thường 5–10 phút (tối đa 1h). `24h` là mặc định cho org không dùng ZDR, áp dụng cho `gpt-5.5`. GPT-5.6+ có TTL 30 phút.
- Usage báo `cached_tokens`. Cached token **vẫn tính TPM**.
- Docs **không nói** các request cùng prefix chạy đồng thời có dùng chung cache đang ghi hay không.

Đối chiếu với code và độ trễ:
- `SYSTEM_PROMPT` dài 5.125 ký tự (đo: `len(SYSTEM_PROMPT)=5125`, 6.330 byte UTF-8), là message đầu và không đổi (`pair_classifier.py:29-93`). `_json_mode_messages` không sửa nó vì prompt đã chứa chữ "JSON" (`client.py:51-58`). Tiếng Việt thường trên 1.024 token [ASSUMED, chưa có tokenizer trong venv], nên **đủ điều kiện cache tự động** mà không cần sửa prompt.
- Wave đầu của các lời gọi song song trong cùng job nhiều khả năng **trượt cache cùng lúc** [ASSUMED, docs không nói]. Lợi ích chủ yếu đến **giữa các job** trong TTL.
- Latency guide: "cutting 50% of your prompt may only result in a 1–5% latency improvement", còn output mới là phần chậm nhất. Với một model reasoning, caching **giảm chi phí nhiều hơn giảm độ trễ**.
- Client hiện **không ghi** `cached_tokens` (`client.py:247-256`). P0 nên thêm để đo được, không đoán.

## 3. Reasoning effort, đòn bẩy lớn nhất mà P2 chưa nêu

- [OpenAI Reasoning guide](https://developers.openai.com/api/docs/guides/reasoning): `gpt-5.5` mặc định `medium`. "Lower effort favors speed and lower token usage". Reasoning token được tính như output token.
- Latency guide: "Generate fewer tokens", cắt 50% output có thể cắt khoảng 50% độ trễ.
- Code: `reasoning_effort` thấp chỉ áp cho `slot_context`/`alias` (`runtime.py:146-153`), **không áp cho `pairs`**. Pairs đang chạy ở mức mặc định (medium) trên `gpt-5.5` (`docker-compose.yml:591`). `_is_gpt5` nhận cả `cx/gpt-5.6-luna` (`client.py:61-64`), nên đòn bẩy này dùng được ở cả local lẫn prod.
- Ba nguồn cùng chỉ ra rằng trong P2, **`reasoning_effort=low` cho pairs** có khả năng giảm độ trễ mỗi lời gọi mạnh hơn cả tăng batch hay caching [ASSUMED về mức độ, cần bake-off]. Rủi ro là chất lượng nhãn CONFLICT/DUPLICATE, vốn cần suy luận nhiều bước theo prompt (`pair_classifier.py:31-63`).

## 4. Đề xuất bake-off cho P2 (hs:bakeoff)

Thiết kế:
- Metric chính: p90 `latency_ms` mỗi lời gọi pairs và wall time của stage, trên 40 cặp replay từ job lớn.
- Cổng phụ: `run_live --repeats 3` xanh, và `relations_by_label`/`rejected.*` lệch không quá ngưỡng.

| Ứng viên | Biến số |
|---|---|
| C0 | baseline: batch 8, medium, concurrency 5 |
| C1 | batch 8, `reasoning_effort=low` |
| C2 | batch 10 (4 batch, một wave với concurrency 4) |
| C3 | model nhỏ hơn cùng họ (phải qua `classifier_family_ok`, `model_family.py:35-36`) |

Prompt caching không cần là một ứng viên riêng: nó đã bật tự động. Chỉ cần đo `cached_tokens` sau khi có P0.

## Kết luận xếp hạng

1. Song song 5 lời gọi được docs ủng hộ cho các bước độc lập, rủi ro rate limit thấp ở mức tải này. Cần thêm jitter.
2. **Reasoning effort thấp cho pairs** là đòn bẩy P2 nên ưu tiên bake-off đầu tiên. Tăng batch xếp sau, vì top_k = 40 nên chỉ giảm số wave, không tăng độ phủ (R3 mục 4).
3. Prompt caching đã bật tự động, chỉ cần đo `cached_tokens`. Không kỳ vọng giảm nhiều độ trễ.
4. Router 9router: thiếu tài liệu, nên phải đo concurrency và `served_model` thực tế ở local.
