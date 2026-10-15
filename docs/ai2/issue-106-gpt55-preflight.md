# Issue #106: readiness GPT-5.5

Probe giới hạn 1 completion token có thể bị GPT-5.5 từ chối với HTTP 400:
`Could not finish the message because max_tokens or model output limit was reached.`
Đây là lỗi request kiểm tra; nó có thể chặn deploy dù inference hoạt động.

## Bản sửa

- GPT-5 (kể cả prefix provider) dùng `max_completion_tokens`, bỏ `temperature`.
- Probe mặc định 64 token / 15 giây cho GPT-5; model khác giữ 1 token / 3 giây.
- `AI2_LLM_PROBE_MAX_TOKENS`, `AI2_LLM_PROBE_TIMEOUT_SECONDS` ghi đè mặc định.
  Để trống hoặc giá trị không hợp lệ dùng mặc định. Compose local/production đều forward hai biến.
- HTTP thành công xác nhận model sẵn sàng, kể cả `finish_reason=length` và content rỗng.
  Inference vẫn từ chối content rỗng.
- `/readyz` kiểm tra embedding đã cấu hình khi full AI2 bật, kể cả cờ chẩn đoán discovery tắt.
  Cache kết quả lỗi embedding chỉ 10 giây để tự phục hồi; kết quả READY vẫn được giữ lại
  để tránh gọi API trả phí mỗi lần poll.
- Log probe gồm model, HTTP status, loại exception và identifier `code`/`param` đã lọc;
  không ghi message, body hay key. Trace inference có `finish_reason`, `truncated`,
  `reasoning_tokens`; `truncated_by_reasoning` chỉ được ghi khi content rỗng và hết output cap.
- Caller `/readyz` trong deploy/E2E chờ tối đa 90 giây, đủ cho mặc định probe LLM và embedding.
  Khi tùy chỉnh timeout vượt mức này, người vận hành cần điều chỉnh cả caller.
- Giữ nguyên hard cap `max_output_tokens` của inference và semantic profile;
  không tự cộng token reasoning hoặc thêm retry ngầm.
- BE worker truyền lại consent của đúng hồ sơ ở lần dựng request có semantic profile.
  Consent true/false được giữ nguyên qua cả hai lần dựng request và retry;
  hồ sơ chưa đồng ý tiếp tục bị chặn. Bản sửa tránh consent rơi về mặc định false
  trước lúc submit và gây `RULE_ONLY_NO_CONSENT` ngoài ý muốn.

## BE triển khai

1. Nhận bản sửa vào `develop`; deploy với model đang chạy để xác nhận tương thích.
2. Kiểm tra giới hạn chi phí 30 USD/tháng theo D6 trên tài khoản provider.
3. Đặt trong `deploy/.env.prod`:

   ```dotenv
   AI2_LLM_MODEL=gpt-5.5
   AI2_LLM_STRONG_MODEL=gpt-5.5
   AI2_LLM_PROBE_MAX_TOKENS=64
   AI2_LLM_PROBE_TIMEOUT_SECONDS=15
   ```

4. Deploy. Preflight phải báo `llm=ready embedding=READY`; `/readyz` trả 200.
5. Chạy một query và một hồ sơ có pair classifier; xem trace `served_model`,
   `response_chars > 0` và không có `LLM_UNAVAILABLE`/lỗi parse.
6. Nếu preflight thất bại, đọc `ai2.llm_probe_failed`; stack cũ vẫn phục vụ vì preflight
   chạy trước bước thay container. Khôi phục biến model hoạt động trước lần deploy tiếp theo.

Xác nhận local chỉ chứng minh cấu hình/provider local. Việc đổi `.env.prod`, xác nhận
ngân sách tài khoản và quan sát trace production do người vận hành thực hiện trước khi đóng issue.
