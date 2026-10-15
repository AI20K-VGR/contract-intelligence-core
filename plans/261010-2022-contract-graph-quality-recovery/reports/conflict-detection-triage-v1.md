# P3 conflict-detection triage — 2026-10-11

## Kết quả

- Quét 32 tài liệu fresh trong 31 cụm nguồn; không dùng candidate output AI2 để chọn cặp.
- Quy tắc chẩn đoán: hai vế đều có token số; tập token số khác nhau; có ít nhất 4 token nội dung chung; Jaccard token >= 0.12. Lấy toàn bộ cặp khớp trong pool fresh: 191 cặp, S1=62, S2=32, S3=97.
- Các strata chồng lấp theo cụm: S1 có 10 cụm, S2 có 1, S3 có 18; hợp là 24 cụm.
- Labeler gợi ý: CONFLICT=1, DUPLICATE=2, GENERAL_SPECIFIC=34, REFERENCE=2, UNRELATED=152. Đây là gợi ý AI chưa được user duyệt cho packet chẩn đoán.
- Candidate generator uncapped tạo 6.955 cặp trong các tài liệu chứa packet; 72/191 cặp triage có mặt, 119/191 không có.
- Cặp duy nhất được labeler gợi ý CONFLICT không nằm trong candidate set uncapped. Do đó pipeline hiện tại không thể phân loại cặp này end-to-end. Đây là tín hiệu cần người duyệt xác nhận, chưa phải bằng chứng gold về một false negative thật.

## Giới hạn và hành động

- Đây là tập được làm giàu theo khác biệt số liệu/chủ đề; không ước lượng prevalence và không thay recall frame đại diện.
- Không tune hoặc đổi candidate code chỉ dựa trên gợi ý AI chưa được duyệt. Người dùng đã miễn reviewer người thứ hai; nhãn packet này vẫn cần quyết định chính thức trước khi dùng làm gold.
- Nếu user xác nhận nhãn CONFLICT, bước sửa cần tăng candidate recall cho mâu thuẫn cùng-chủ đề/khác-giá-trị, giữ top-k/budget và đo mức tăng false candidates trên dev. Held-out vẫn khóa.

## Provenance

- Dataset: `quality-recovery-dev-20261011-v2`; fresh-pool SHA-256 `d989effb05941914b145046e1762f16aac20e91eb81deab08cf23505fbf48ef3`.
- Candidate code SHA-256: `24657b7707ad6371ccb4620256385121fecb9e04e284ee25977e867520667420`.
- Selection SHA-256: `be61754e13b84f2ea5b4cff4d59db908d4ae5c77b6f7f3b7d22976a953d5de51`; audit JSON SHA-256: `a93596b4948e79a6ae3b3e0174717ac2c486302355bcfd13e019edf2f851a57d`.
- Phiếu có văn bản hợp đồng và gợi ý riêng nằm trong `.harness/state/quality-recovery-p3-conflict-triage-20261011-v1/` (gitignored).
