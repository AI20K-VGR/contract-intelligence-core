# Fixture manifest — thiết kế v0.2

Owner Trần Văn Dũng; fixture_id=dossier-v0; source_version=v0.2-draft; nguồn tự soạn, không dùng tài liệu mentor. Trạng thái: nội dung tình huống đã thiết kế trong CASE-CATALOG.vi.md; chưa tạo PDF, chưa có digest/snapshot thật.

| Document | Nội dung dự kiến | Ngôn ngữ | Case liên quan |
|---|---|---|---|
| contract-01 | HD-01, Điều/Khoản/Điểm, bảng giá, party | Việt | C01 trong document; phía trái C02–04,C09–11,C13–15 |
| annex-01 | PL-01 liên quan HD-01, giá/quantity, trang song ngữ | Việt–Anh | Phía phải contract_annex; phía trái C05–08,C12 |
| annex-02 | PL-02, duration/party/MST/reference và kỳ áp dụng khác | Việt | Phía phải C05–08,C12 |

Mỗi case dùng subject/clause riêng khi ghép fixture để tránh tác động chéo. C08 cố ý tham chiếu HD-02 ở annex-02 để kiểm tra nộp nhầm. Ngôn ngữ Anh ở trang song ngữ là bản tương đương cần reviewer đối chiếu; chưa tuyên bố đã kiểm thử tiếng Anh độc lập.

Hai representation types của cùng ba documents: text_layer và scanned. Có thể là 6 file document-representation; nếu đóng gói PDF chung phải có mapping document boundary rõ. Ghi path, source digest, page count, representation, engine, snapshot IDs sau tạo thật. Các trường chưa tạo để null kèm status, không dùng ID/bbox JSON mẫu thay bằng chứng.

Thiết kế yêu cầu ít nhất một bảng có row/cell và một trang song ngữ; bao phủ 15 case, 30 tổ hợp mỗi round. Scan-like là bản render ảnh cùng nội dung, ghi rõ synthetic scan nếu dùng; không suy ra đại diện scan thực tế đa chất lượng.

Phạm vi chia sẻ nội bộ nhóm/mentor. Tài liệu mentor không commit hoặc gửi external service. Export và thực nghiệm là B-01–04 trong TASK-PLAN.vi.md, sau review design.
