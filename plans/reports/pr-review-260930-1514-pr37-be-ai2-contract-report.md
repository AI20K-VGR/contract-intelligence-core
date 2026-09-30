@Chuongpham2004 @channie111105 cảm ơn em. Anh trả lời theo từng mục.

**1. Duyệt.** Anh submit review **Approve** trên `4ae9e6e` ngay trong review này, để gỡ Request changes cũ. PR #42 anh cũng đồng ý: sửa đúng các câu đã nêu. Dòng lịch sử 08:45 ở DEC (dòng 422) vẫn ghi "`FAILED` luôn mang `BLOCKED`". Lịch sử chỉ ghi thêm, không sửa dòng cũ, nên em để nguyên cũng được; dòng mới của #42 đã đính chính.

**2. `PROCESSING_TIMEOUT`:** xác nhận `retryable=true` trong A2. Mã này đã nằm trong nhóm lỗi tạm ở `wire.py:318`. Retry dùng cùng ngân sách, nên nếu hồ sơ quá lớn thì có thể timeout lại; giới hạn 3 attempt của D7 chặn được vòng lặp.

**3. Người giữ key.** DOC-12 §7 có ghi, ở bảng "ai giữ gì" dòng 223: "Key AI2 | Văn Dũng / người Lead chỉ định". Nhưng em nói đúng là dòng 85 và §5.0 D1 để Lead chốt, nên đây là đề xuất để Trang chốt.

**4. D6: cập nhật đề xuất, thay cho bản anh gửi trước.** AI2 đề nghị bản online chạy **LLM thật** cho cả xử lý hồ sơ và `/query`, cùng **embedding thật**, cho demo 04/10:
- **Provider:** OpenAI, gọi thẳng `https://api.openai.com/v1` (không qua proxy 9router).
  - LLM: `gpt-4o-mini` cho bước thường, `<model mạnh>` cho bước suy luận khó (`AI2_LLM_STRONG_MODEL`).
  - Embedding: `text-embedding-3-small`.
- **Người giữ key:** đề xuất Văn Dũng, key riêng cho bản online; Trang chốt.
- **Dữ liệu:** đoạn văn bản hồ sơ và câu hỏi, **gồm cả hồ sơ thật**. Trang xác nhận nhóm chấp nhận gửi dữ liệu khách hàng sang OpenAI.
- **Trần:** `max_llm_calls=20` mỗi hồ sơ; embedding tối đa 100.000 token mỗi hồ sơ (`AI2_QUERY_MAX_EMBEDDING_TOKENS`); hard limit tài khoản hàng tháng do Trang chốt.
- **Backend thêm B9:** gửi `use_llm` cho `/query` từ env `AI2_QUERY_USE_LLM`. Hiện `query_policy.py:134-139` chỉ gửi `egress_allowed` và `use_vector`, nên LLM ở `/query` không bao giờ chạy.
- **Timeout `/query`:** Backend chờ 20 giây, còn một lời gọi LLM có thể mất tới 45 giây (`AI2_LLM_TIMEOUT_SECONDS`). AI2 giới hạn LLM trong `/query` ở 15 giây, quá thì trả kết quả truy xuất có citation (`NEEDS_REVIEW`); Backend nâng timeout `/query` lên 30 giây.
- **Env online khi Trang duyệt:**
  - `ai2-service`: `AI2_LLM_BASE_URL=https://api.openai.com/v1`, `AI2_LLM_API_KEY`, `AI2_LLM_MODEL=gpt-4o-mini`, `AI2_LLM_STRONG_MODEL=<model mạnh>`, `AI2_EMBEDDING_BASE_URL=https://api.openai.com/v1`, `AI2_EMBEDDING_MODEL=text-embedding-3-small`, `AI2_EMBEDDING_DIMENSIONS=1536`, `AI2_VECTOR_RECALL_ENABLED=true`, `AI2_QUERY_MAX_EMBEDDING_TOKENS=100000`;
  - `backend`, `backend-worker`: `AI2_PROCESSING_EGRESS_ALLOWED=true`, `AI2_QUERY_EGRESS_ALLOWED=true`, `AI2_QUERY_USE_LLM=true`, `AI2_QUERY_USE_VECTOR=true`.

Code làm sẵn, có duyệt là bật bằng env, không phải deploy lại.

**5. Lịch, nhờ @channie111105 chốt:**
- **Demo 04/10**, deploy online 03/10. Nhờ Trang xác nhận với mentor và sửa DOC-12 (§9 mục 1 còn ghi 02/10).
- **Đóng băng code:** DOC-11 dòng 154 ghi tối 02/10. Đề nghị lùi sang **tối 03/10, sau khi deploy và smoke test**.
  - 01–02/10: AI2 làm A1, A2, A4, A7; Backend làm B1, B2, B6 phần DB, B8, B9.
  - 03/10: A3, A6, B3, B4, B5, B7, B6 phần compose, deploy, smoke test, rồi bật env D6 nếu đã duyệt.
- Nếu Trang giữ đóng băng 02/10: đưa A3, B3, B6 compose và B9 lên 02/10, còn A6, B4, B5, B7 để sau demo.
