# Cắt cặp SAME_ARTICLE trước khi gửi LLM: đo và kết luận (261017)

## Đo
4 hồ sơ seeded (tổng hợp), model router `cx/gpt-5.6-luna` chạy 2 lần; nhãn luna dùng làm đáp án tạm.
- 256 cặp gửi LLM; 140 cặp chỉ có nguồn `SAME_ARTICLE`, trong đó 22 cặp luna gán quan hệ (chủ yếu GENERAL_SPECIFIC heading→nội dung, câu dẫn "như sau:"→các điểm a/b, REFERENCE "khoản 1.1").
- Luật thử: giữ cặp SAME_ARTICLE-only khi có một trong các dấu hiệu: Jaccard từ nội dung ≥ 0,15, một bên kết thúc bằng ":", cả hai có giá trị kèm đơn vị, hoặc một bên ≤ 40 ký tự (heading/mảnh câu).

| Hồ sơ | Cặp gửi | Lời gọi pairs | Quan hệ mất |
|---|---|---|---|
| HD-TEST-001 | 40 → 34 | 5 → 5 | 0 |
| HD-TEST-003 | 18 → 13 | 3 → 2 | 0 |
| HD-TEST-004 | 36 → 33 | 5 → 5 | 0 |
| HD-TEST-002 | 34 → 32 | 5 → 4 | 0 |

## Kết luận: chưa bật
- Chỉ tiết kiệm 2/18 lời gọi pairs (~11%). HD-TEST-001 chạm trần top-K 40 nên chỗ trống được cặp khác lấp lại.
- Ngưỡng được chỉnh trên đúng 4 hồ sơ dùng để đánh giá, không có tập kiểm tra riêng. 22 quan hệ là quá ít để tin "mất 0". Các ngưỡng thấp hơn đã làm mất 1–7 quan hệ, nên lề an toàn rất mỏng.
- Lần chạy trên các job thật trong DB local bị chặn vì dữ liệu có thể chứa thông tin cá nhân (PII). Tập lớn hơn cần người dùng cho phép, hoặc phải tạo thêm hồ sơ tổng hợp.

## Bước tiếp theo đề xuất
1. Tạo thêm 4–6 hồ sơ seeded tổng hợp, nhiều điều khoản cạnh nhau khác chủ đề và nhiều cặp heading/điểm a-b. Giữ 2 hồ sơ làm held-out.
2. Chạy lại phép đo; chỉ bật luật nếu held-out mất 0 quan hệ và tiết kiệm ≥ 20% lời gọi pairs.
