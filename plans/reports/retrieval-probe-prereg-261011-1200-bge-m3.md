# Preregistration: BGE-M3 dense retrieval on locked dev

Ngày: 2026-10-11

## Mục tiêu và giả thuyết

Kiểm tra liệu retriever multilingual được huấn luyện cho dense retrieval có chọn được cặp bổ sung tốt hơn candidate generator hiện tại hay MiniLM đã thử. Đây là phép đo định hướng trên dev, không phải candidate version được duyệt.

## Khóa thí nghiệm

- Chỉ dùng đúng 32 tài liệu trong recall frame P3 đã khóa và 37 positive đã duyệt; không dùng tài liệu ngoài frame, held-out, nhãn do model sinh, hoặc API.
- Dùng cache local `BAAI/bge-m3` và dense embedding CLS + L2 normalization đúng pooling cấu hình trong `modules.json`/`1_Pooling/config.json`; batch encode văn bản khoản đủ điều kiện, truncate đầu vào ở 512 tokens.
- Chỉ đo hai đầu ra với quota 40/doc: (1) top-40 cosine cross-article, bỏ cặp Luong-1/ancestor; (2) blend cố định giữ C32, thêm tối đa 8 từ danh sách semantic, rồi backfill C40.
- Báo recall theo nhãn, reviewed-frame overlap, số candidates, thời gian. Không sweep ngưỡng/weight/quota và không thay runtime.

## Diễn giải đã định trước

So sánh với C40 11/37, semantic MiniLM top-40 7/37 và blend MiniLM 14/37 chỉ nhằm chọn hướng. Mức tăng trên cùng 37 nhãn dev là selection evidence, không phải xác nhận độc lập hay PASS. Nếu không tạo mức tăng có ý nghĩa, dừng dense retrieval và yêu cầu tranche dev sạch, độc lập đã adjudicate trước khi thiết kế hướng retrieval khác. Runtime OFF; P4/P5 khóa; không đọc held-out.

## Kết quả

Chạy xong ngày 2026-10-11 trên đúng frame đã khóa. BGE-M3 semantic top-40 đạt 8/37 (CONFLICT 1/1, DUPLICATE 0/2, GENERAL_SPECIFIC 5/27, REFERENCE 2/7), 1.197 candidates; giao frame review gồm 41 dòng đã review và 1.156 dòng chưa review. Blend C32 + semantic fill đạt 16/37 (CONFLICT 1/1, DUPLICATE 1/2, GENERAL_SPECIFIC 11/27, REFERENCE 3/7), 1.200 candidates; giao frame review gồm 79 đã review, 1.121 chưa review. CPU wall time 590,83 giây, working set quan sát gần 2,1 GB.

Blend hơn C/40 được 5 positives nhưng còn thiếu 21/37 và không đạt mục tiêu dev 36/37; DUPLICATE, GENERAL_SPECIFIC, REFERENCE đều hụt. Đây là kết quả chọn hướng trên cùng dev labels, không phải xác nhận độc lập. Chi phí gần 10 phút/32 tài liệu và ~2,1 GB RAM chưa phù hợp để đề xuất runtime. Không tích hợp model, không gọi API, không truy cập held-out; runtime vẫn OFF/P4-P5 khóa.
