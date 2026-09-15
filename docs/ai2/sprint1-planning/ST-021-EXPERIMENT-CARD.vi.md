# Experiment card AI2 v0.2 — thiết kế

Owner Trần Văn Dũng; chưa chạy. Mục tiêu: kiểm tra tính khả thi extraction/context/comparison/evidence trên fixture tự soạn. Dữ liệu/case: CASE-CATALOG.vi.md; outcomes theo decision table DOC-02-BRD.vi.md.

## Baseline và nguồn context

| Entity | Pattern/nguồn nhận diện dự kiến | Context lấy từ đâu | Normalization/ambiguity/fallback |
|---|---|---|---|
| price | Số cạnh VND/USD và nhãn đơn giá/tổng giá; cell dưới header giá | Row subject, header đơn vị/VAT, clause scope/effective date | Decimal string; separator mơ hồ, VAT/currency thiếu cần cho so sánh → insufficient_evidence. |
| quantity | Số cạnh bộ/cái/lần dưới nhãn số lượng | Row item và clause ordered/delivered/location | Giữ unit; không tự đổi khác unit. |
| date | Nhãn ngày ký/hiệu lực/giao và ngày viết rõ | Clause role, subject, validity | ISO YYYY-MM-DD; 01/02 không có locale chắc chắn → null + reason. |
| duration | Số + ngày lịch/ngày làm việc/tháng | Clause thời hạn và mốc kể từ | Giữ unit và anchor; thiếu anchor → insufficient_evidence. |
| party | Sau Bên A/B, bên bán/mua hoặc ô thông tin bên | Cùng clause/table party header | Giữ raw name; chỉ normalize khoảng trắng/case để so tên, không tự hợp nhất pháp nhân. |
| tax_code | Nhãn MST/mã số thuế | Party role ở cùng block | Chuỗi giữ số 0; OCR O/0 mơ hồ → human evidence queue. |
| referenced_contract_number | Sau hợp đồng số/tham chiếu | Document role/dossier reference | Trim khoảng trắng, giữ nội dung mã; mã khác báo discrepancy trước ghép clauses. |

Trong feasibility có thể cung cấp context thủ công để thử riêng comparison. Mỗi field cần `context_origin=source_rule/manual`; manual context là input có khai báo, không được tính thành kết quả extraction tự động. Không lấy expected disposition làm input. Nếu rule không xác định được role/subject cần thiết thì dừng cặp ở insufficient_evidence.

Semantic dùng subject/action/object/recipient/time/condition/polarity; C04 cùng hành động trái polarity; C14 khác hành động; C15 thiếu ngoại lệ. Từ khóa phải/không được chỉ gợi ý, không đủ tạo difference.

## Pipeline và services

OCR/layout từ AI1 → extraction/raw evidence → normalizer → context gate → disposition → citation/HITL. AI1 công bố engine/version và measurement cost. AI2 baseline dùng local rules có version, external services=none. Service fee dự kiến 0; compute/labor/latency chưa đo. Thay provider cần quyết định mới về input data, retention, cost và phê duyệt trước gửi dữ liệu.

## Mẫu run record cần điền khi thực nghiệm

| Trường | Giá trị hiện tại / cần ghi |
|---|---|
| hypothesis | Local baseline có thể giữ provenance và tránh false positive do context ở catalog. |
| round_id/run_id, gold_version, rule_version | Chưa có run; điền IDs trước chạy. |
| input snapshots / source digests | Chờ AI1; không thay bằng bbox mẫu. |
| context_origin theo field | source_rule hoặc manual, ghi tỷ lệ/count thực tế. |
| prediction artifact / latency / hardware | Chưa đo. |
| counts và failures | Theo METRIC-PROTOCOL; ghi cả not_run/failed. |
| decision | Chưa đánh giá. |

Tiếp tục baseline nếu walkthrough evidence khép kín và controls không bị báo sai trong thử nghiệm có log; nếu context phải làm tay, giới hạn kết luận ở comparison trên input được hỗ trợ. Nếu citation không resolve, sửa mapping trước claim highlight. Không đạt giả thuyết thì ghi failure + thay đổi đề xuất, không bỏ case khỏi n. Fine-tune/API/UI ngoài nhiệm vụ planning hiện tại.

## Kế hoạch sprint tiếp theo để leader tổng hợp

Sprint 2 dự kiến: nhận snapshots, bind gold, chạy extraction/context baseline và audit, bàn giao facts có provenance cho BE. Sprint 3 dự kiến: tích hợp comparison/HITL, regression trên controls, mở rộng semantic khi có evidence. Đây là đề xuất sequencing AI2; ngày, capacity và milestone toàn nhóm cần leader xác nhận.
