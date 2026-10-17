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

## Vòng 2: tập lớn hơn và bật luật (cách 1)
- Thêm 6 hồ sơ tổng hợp `fixtures/seeded/pruning_set.py`: phần mềm, thi công, thuê văn phòng, vận chuyển (dev); tư vấn thuế, suất ăn (held-out). Tổng 37 quan hệ gold, viết trước khi chỉnh luật.
- Luật vòng 1 (Jaccard ≥ 0,15, độ dài ≤ 40) làm **mất 5 quan hệ gold trên dev**, xác nhận đã overfit vào 4 hồ sơ cũ. Các cặp bị mất đều là tham chiếu nội bộ "tại khoản 4.2".
- Luật đã bật (`pair_candidates._same_article_related`): giữ cặp chỉ-SAME_ARTICLE khi một bên nhắc số hiệu bên kia ("khoản X.Y"), một bên kết thúc bằng ":", một bên ≤ 30 ký tự, cả hai có giá trị kèm đơn vị, hoặc Jaccard từ nội dung ≥ 0,2.

| Tập | Gold mất | Cặp | Lời gọi pairs (ước tính) |
|---|---|---|---|
| dev (4 hồ sơ mới) | 0 | 131 → 99 | 17 → 14 |
| held-out (2 hồ sơ mới) | 0 | 52 → 29 | 8 → 4 |

- 4 hồ sơ seeded cũ, luna: gate live `--repeats 2` đạt (must 2/2, forbidden 0); `COST_CALLS` 22 → 19 (pairs 18 → 15). Seeded offline dev 42/42, held-out 20/21; 1958 test pass.
- Gate hồi quy: `python -m fixtures.seeded.pruning_eval` (chạy trong `tests/test_seeded_pruning_set.py`).
- Phát hiện phụ: 4 quan hệ gold (tiêu đề phụ lục ngắn như "2. Hiệu lực" với nội dung của nó) chưa bao giờ thành ứng viên vì node < 25 ký tự bị loại (`MIN_CLAUSE_CHARS`). Đây là khoảng trống recall có sẵn từ trước, không do luật mới gây ra.
- Giới hạn: khi hồ sơ chạm trần top-K 40, chỗ trống được cặp khác lấp lại, nên lợi ích là chất lượng tốt hơn chứ không phải ít lời gọi hơn.
