# Plan: AI2 không được PASS im khi ma trận yêu cầu review

Probe 2026-09-27: `run_idp` trên 56 fixture EC, 0 exception, 35 khớp `expected_state`.
Năm case không có query, expected REVIEW, kết quả PASS và `handoff_issues` rỗng:

- EC-005 nhảy số Điều 1, 2, 4
- EC-007 header xen giữa hai đoạn
- EC-031 Art 19 và Điều 19 lệch nghĩa
- EC-033 định nghĩa bị sửa rồi được dùng lại
- EC-047 `processing_budget_exceeded` khi không có LLM

Hướng: gắn issue và `NEEDS_REVIEW`. Không tạo node mới, không chọn ngôn ngữ, không chọn legal winner.

Ngoài đợt này: case expected PASS nhưng pipeline trả NEEDS_REVIEW (thắt chặt hơn, không bịa). EC-050 và EC-055 expected BLOCKED nhưng ra NEEDS_REVIEW. OCR, ACL backend, pgvector.
