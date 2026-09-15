# DOC-01 · Product Vision

> **Contract Intelligence** — Hệ thống OCR/IDP xử lý hợp đồng thương mại tự động.

---

## 🎯 Problem (Vấn đề)

> *Mô tả bối cảnh: doanh nghiệp đang gặp khó khăn gì khi xử lý hợp đồng thương mại?*

<!--
Ví dụ:
- Doanh nghiệp ký hàng trăm hợp đồng/tháng, quy trình review thủ công tốn 2–5 ngày/hợp đồng.
- Nhân viên pháp lý phải đọc lại toàn bộ văn bản để tìm điều khoản rủi ro.
- Không có cách nào nhanh so sánh điều khoản giữa 2 hợp đồng.
- Các bên ký hợp đồng với nội dung không nhất quán (conflict clause) dẫn đến tranh chấp.
-->

---

## 👥 Users (Đối tượng người dùng)

> *Ai sẽ sử dụng hệ thống này? Mỗi người dùng có vai trò gì?*

<!--
| Persona | Vai trò | Pain point hiện tại |
|---------|---------|---------------------|
| Contract Manager | Upload & theo dõi hợp đồng | Không có dashboard tập trung |
| Legal Reviewer | Review điều khoản, phát hiện rủi ro | Đọc thủ công 50+ trang |
| Procurement | So sánh vendor contract | Không có tool so sánh |
| Compliance Officer | Duyệt cuối, audit trail | Thiếu log action |
-->

---

## 💡 Value (Giá trị mang lại)

> *Hệ thống mang lại lợi ích gì? Đo lường bằng số liệu cụ thể.*

<!--
| Benefit | Trước | Sau |
|---------|-------|-----|
| Thời gian review 1 hợp đồng | 3–5 ngày | 30–60 phút |
| Phát hiện conflict clause | Thủ công, dễ bỏ sót | Tự động, flag ngay |
| Tỷ lệ dispute do wording | 5–8% | < 1% |
| Compliance audit | Giấy tờ lộn xộn | Log đầy đủ trong DB |
-->

---

## 🚫 What is Out of Scope (Ngoài phạm vi)

> *Những gì hệ thống KHÔNG làm (v1 hoặc vĩnh viễn).*

<!--
### V1 Out of Scope
- Hợp đồng không phải Tiếng Việt / Tiếng Anh
- Hợp đồng scan mờ, chất lượng thấp dưới 150 DPI
- E-signature (tích hợp ký số)
- Hợp đồng dạng bảng (Excel-like) — chỉ xử lý văn bản
- Multi-language negotiation (so sánh clause giữa 2 bản dịch)

### Vĩnh viễn Out of Scope
- Tư vấn pháp lý (hệ thống chỉ trích xuất & flag, không thay thế luật sư)
- Quản lý workflow e-signature
- Kế toán / billing
-->

---

## 🎯 North Star Metric

> *Chỉ số quan trọng nhất để đo sự thành công của sản phẩm.*

<!--
Ví dụ: "Tổng số hợp đồng được duyệt (APPROVED) qua hệ thống mà không có conflict flag còn tồn đọng sau 30 ngày."

Target v1: 500 contracts/month, < 2% false positive rate trên conflict detection.
-->
