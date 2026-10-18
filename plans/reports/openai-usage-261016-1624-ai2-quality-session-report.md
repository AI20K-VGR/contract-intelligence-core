# Báo cáo sử dụng OpenAI: phiên đánh giá và cải tiến chất lượng AI2 (2026-10-16)

Phạm vi: các lời gọi OpenAI (model `gpt-5.5`, phục vụ là `gpt-5.5-2026-04-23`) phát sinh trong phiên làm việc ngày 2026-10-16 trên stack local `ai2-graph-full`, gồm lượt chạy do agent kích hoạt và job do người dùng chạy từ UI.

> **Số tiền chính xác không có trong báo cáo này.** Agent không có quyền đọc billing/usage của tài khoản OpenAI (không có admin key) và tài khoản đã **hết credit** trong phiên (`429 code=credit_balance_exhausted`, khoảng 16:15). Báo cáo ghi số lời gọi và số token **đo được**, tách riêng phần **ước lượng**. Số tiền thực cần đối chiếu tại OpenAI Platform → Usage, lọc ngày 2026-10-16 và project/key của AI2 local.

## 1. Tổng hợp

| Hạng mục | Giá trị | Nguồn |
|---|---|---|
| Lượt chạy pipeline đầy đủ (≈ 20 request mỗi lượt, đúng trần budget) | **19 lượt** | log phiên + DB |
| Lượt chạy một phần (job lỗi, replay trước khi sửa, probe) | 6 lượt | log phiên + DB |
| Tổng HTTP request tới OpenAI | **≈ 470** (cận trên) | đếm theo lượt |
| Token đo được của một lượt đầy đủ, phần pairs + chuẩn hóa fact | 13.384 input / 9.064 output | trace replay `job_1c92…` |
| Token pairs trong job lưu DB | 12.829 input / 7.746–8.351 output mỗi job | `ai2.jobs.result_json` |
| Token ước lượng của toàn phiên | **≈ 0,4 triệu input, 0,3–0,55 triệu output** | ước lượng (mục 4) |

Token output của `gpt-5.5` **đã gồm reasoning tokens** (ví dụ một batch pairs: 2.622 completion, trong đó 2.048 reasoning), và chiếm phần lớn chi phí.

## 2. Đo được

**Một lượt replay đầy đủ** (job `job_1c92385ed2f64cba9c1e7e670745991f`, trước khi sửa lỗi JSON mode):

| Nhóm lời gọi | Số lời gọi | Input | Output (gồm reasoning) |
|---|---|---|---|
| Chuẩn hóa fact | 3 | 555 | 596 |
| Phân loại pairs (5 batch × 8 cặp) | 5 | 12.829 | 8.468 |
| Điền slot / alias (bị OpenAI từ chối 400 do thiếu chữ "json") | 12 | 0 | 0 |
| **Cộng** | 20 | 13.384 | 9.064 |

Request bị từ chối 400 không sinh token. Sau khi sửa (commit `9a750d55`), 12 lời gọi này chạy thật và **có tính phí**: đây là lý do một lượt sau khi sửa đắt hơn lượt trước khi sửa.

**Job lưu trong DB local** (tầng pairs):

| Job | Giờ (VN) | Ghi chú | Lời gọi pairs | Input | Output |
|---|---|---|---|---|---|
| `job_1c92385ed2f64cba9c1e7e670745991f` | 13:22 | lỗi kết nối, 0 token | 3 | 0 | 0 |
| `job_0358311f9f8948fd8775d367b5c37733` | 13:57 | reindex, không có semantic | 5 | 12.829 | 8.351 |
| `job_5c1e31557b9143b5a4374f876028eb01` | 14:16 | bị ngắt do restart AI2 | không lưu | — | — |
| `job_dbf4b391b4334b85bb849487d2302c15` | 14:20 | đầy đủ | 5 | 12.829 | 7.746 |

## 3. Danh sách lượt chạy

| # | Lượt chạy | Lượt pipeline | Request (≈) | Ghi chú |
|---|---|---|---|---|
| 1 | Probe classifier (`probe_pairs_llm`) | — | 3 | request rất nhỏ |
| 2 | Replay job 13:22, trước khi sửa JSON | 1 phần | 20 | 8 có phí, 12 lỗi 400 |
| 3 | Replay tìm lỗi 400 (`replay_badrequest`) | 1 phần | 20 | 8 có phí, 12 lỗi 400 |
| 4 | Replay sau khi sửa JSON | 1 | 20 | |
| 5 | Lý do chặn DUPLICATE (`dup_reason`) | 1 | 20 | |
| 6 | Funnel pairs (`pair_funnel`, tắt semantic) | 1 phần | ≈ 8 | |
| 7 | Live gate lần 1 (×3) | 3 | 60 | có timeout |
| 8 | Live gate lần 2 (×3) | 3 | 60 | |
| 9 | Live gate sau khi ghép đoạn văn (×3) | 3 | 60 | 7 timeout |
| 10 | Live gate hai hồ sơ (×2 mỗi hồ sơ) | 4 | 80 | 6 timeout |
| 11 | Probe timeout (`timeout_probe` ×2) | 2 | 40 | |
| 12 | Probe budget (`budget_probe`) | 1 + 1 phần | ≈ 25 | **hết credit giữa lượt** |
| 13 | Job UI 13:22 / 13:57 / 14:16 / 14:20 | 1 + 3 phần | ≈ 50 | xem mục 2 |
| 14 | `/readyz` sau mỗi lần restart AI2 | — | vài | ping 64 token |

Timeout (`LLM_TIMEOUT`) và lỗi 429 hết credit có thể vẫn tính phí phần đã sinh ở phía nhà cung cấp; không đo được từ phía AI2.

## 4. Ước lượng (giả định nêu rõ)

- Pairs + fact: dùng số đo ở mục 2, khoảng 13,4 nghìn input và 9 nghìn output mỗi lượt.
- Điền slot ngữ nghĩa (12 lời gọi mỗi lượt, không lưu token): input ≈ 400 token mỗi lời gọi (prompt khoảng 330–530 ký tự cộng ngữ cảnh). Output 300–1.500 token mỗi lời gọi tùy lượng reasoning. **Đây là giả định, không phải số đo.**
- Mỗi lượt đầy đủ: ≈ 18 nghìn input, 13–27 nghìn output. 19 lượt đầy đủ cộng khoảng 6 lượt một phần cho ra **≈ 0,4 triệu input và 0,3–0,55 triệu output**.

Quy ra tiền: `chi phí ≈ input_triệu × giá_input + output_triệu × giá_output` theo bảng giá `gpt-5.5` hiện hành trên trang pricing của OpenAI. Agent không có bảng giá đó nên không điền số.

## 5. Nhận xét chi phí và đề xuất

1. **Mỗi hồ sơ dùng hết 20/20 lời gọi**: pairs khoảng 5, semantic khoảng 12, fact khoảng 3. Budget dùng chung khiến semantic bị `LLM_BUDGET_EXCEEDED`. Cần quyết định budget riêng cho từng tầng (xem `plans/261016-1624-ai2-measure-classify-optimize/plan.md`, mục 4).
2. **Reasoning tokens chiếm phần lớn output.** Lời gọi điền slot nhỏ không cần nhiều reasoning: cân nhắc model nhỏ hơn hoặc giới hạn effort riêng cho tác vụ này, đo bằng seeded gate trước khi đổi.
3. **Chạy live gate tốn khoảng 20 request mỗi lượt, mỗi hồ sơ.** Live gate chỉ nên chạy khi đổi prompt/model và hằng đêm. Vòng tối ưu nên dùng scorer offline (miễn phí).
4. **Hết credit trước đây bị coi là rate limit** và retry 3 lần mỗi lời gọi. Đã sửa (`LLM_QUOTA_EXHAUSTED`, commit `9a750d55`): AI2 giờ dừng sau 1 request.
5. Nên ghi `prompt_tokens`/`completion_tokens` cho **mọi** tầng (hiện chỉ pairs lưu vào kết quả job) để báo cáo chi phí sau này là số đo, không phải ước lượng.
