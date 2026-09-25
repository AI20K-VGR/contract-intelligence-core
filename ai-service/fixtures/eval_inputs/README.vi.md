# Bộ input coverage cho AI2

Thư mục này chứa input biên giới AI1 → AI2 và manifest bao phủ các nhóm case thực tế. Các input mới không được tự động đưa thành case trong giao diện Lab.

## Phân biệt schema

- `ai1.snapshot.v1`: payload bàn giao canonical cho AI2.
- Snapshot version khác v1 bị từ chối ở canonical boundary; `ai1.result.v0.1` và legacy OCR JSON chỉ là compatibility input riêng.
- legacy OCR JSON: được chấp nhận ở chế độ text-only và phải degraded/review.
- `ai2.ocr_edge_cases.v1`: catalog chính sách/test, không phải document snapshot; nạp vào endpoint snapshot phải bị từ chối.

## Cách kiểm tra

```powershell
cd C:\Users\dungs\OneDrive\Documents\VSF\ai-service
.\.venv\Scripts\python.exe scripts\validate_input_coverage.py
```

Validator không gọi network/LLM. Nó kiểm tra file tồn tại, snapshot hợp lệ, payload invalid bị từ chối đúng mã lỗi và catalog runtime đủ 95 case.

## Nhóm coverage

- topology: body, annex, missing annex, nhiều nguồn;
- tài liệu dài và clause dài;
- OCR thấp, page failed, rotation, duplicate lineage, legacy text-only;
- không có bảng, thiếu geometry, continuation, merged cell, subtotal, locale và bảng lớn;
- relation trực tiếp, multi-hop, vòng tham chiếu, amendment;
- facts mâu thuẫn, ngày, tiền tệ, song ngữ;
- prompt injection, malformed snapshot, digest/ID sai;
- provider fault, stale vector, dimension mismatch, budget, egress và index lease.

Mỗi nhóm được chạy theo mode phù hợp trong full-flow report: deterministic, live LLM và hybrid vector recall khi embedding khả dụng.
