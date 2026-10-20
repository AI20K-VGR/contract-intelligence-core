# DOC-02 — Yêu cầu nghiệp vụ (phần AI2)

**Phiên bản:** v1.1 · **Ngày:** 20/09/2026  
**Nguồn:** [DOC-02](../DOC-02-brd.md), [AI2-01](AI2-01-business-policy-perspective.vi.md).  
**Việc của BRD:** quy tắc nghiệp vụ và bảng quyết định. Không chốt API, schema, SLA.

## 1. Mục tiêu

Giúp người rà soát thấy **ứng viên kỹ thuật** (khớp / khác / sửa / thiếu / không so). Người chịu trách nhiệm quyết định. Hệ thống không gắn hiệu lực, thứ tự ưu tiên tài liệu, hay `LEGAL_WINNER`.

## 2. Vai trò

| Vai trò | Làm | Không tự quyết |
|---|---|---|
| Người nạp hồ sơ | Xác nhận thân / phụ lục | Suy vai trò từ tên file |
| Người rà soát | Xem nguồn; xác nhận / sửa lớp / từ chối | Sửa chữ OCR; phán pháp lý |
| AI1 | Snapshot trang, nút, bảng, ghim | Kết quả nghiệp vụ |
| AI2 | Sự kiện, ghép cặp, so, hỏi có biên | Quyền truy cập, công bố |
| BE | ACL, vòng đời, cổng công bố | Ghi đè máy hoặc lịch sử rà |
| FE | Hiển thị nguồn và thao tác rà | Tự duyệt hợp đồng |

## 3. Yêu cầu nghiệp vụ

| ID | Yêu cầu | Dấu chấp nhận |
|---|---|---|
| BR-A01 | Không nhận `pdf_bytes`; thiếu ghim bắt buộc thì chặn, không đoán | Handoff `BLOCKED`; page thấp/trống hoặc node partial → `NEEDS_REVIEW` |
| BR-A02 | Mọi sự kiện giữ giá trị thô + trích dẫn; chuẩn hóa không bịa | `raw_value` khác rỗng; neo được trang |
| BR-A03 | Chỉ so cùng ngữ cảnh (mục, đơn vị, kỳ, bên) | Không ghép MST A với phạt B |
| BR-A04 | Năm disposition: khớp, khác, ứng viên sửa, không so, thiếu chứng | Bảng §5 |
| BR-A05 | Sửa đổi chỉ khi văn bản nói sửa/thay và xác định phần bị sửa | Không bắt “lại / phiên bản / quy trình” |
| BR-A06 | Ô bảng trống không thành 0 | EC-015 |
| BR-A07 | Lớp rà không sửa máy; trích lại thì lớp cũ hết hạn | confirm / correct / reject |
| BR-A08 | Chỉ mục AI2 chỉ **đề xuất**; BE mới công bố | `propose` |
| BR-A09 | Hỏi: ưu tiên quy tắc và khóa có cấu trúc trước mô hình; tối đa 8 đoạn | L0 → L1 k≤8 → L2 tùy chọn → L3 |
| BR-A10 | PDF không tin cậy; không train chéo tenant; không lộ ACL | Phong bì công cụ |

## 4. Thuật ngữ

| Từ | Nghĩa |
|---|---|
| Hồ sơ | Một hợp đồng và các phụ lục cùng lần rà |
| Sự kiện | Giá trị có ngữ cảnh và nguồn |
| Phát hiện | Cặp hai nguồn; không phải án |
| Sự cố chứng cứ | Thiếu tài liệu/trang/ngữ cảnh; có thể một phía |
| Ghim | Bộ phiên bản snapshot / profile / OCR / trích |

## 5. Bảng quyết định so sánh

Thứ tự: đủ nguồn? → cùng ngữ cảnh? → có câu sửa? → khớp hay khác. Không dùng giờ tải file làm ưu tiên.

| Điều kiện | Kết quả | Hiển thị |
|---|---|---|
| Thiếu file/trang được dẫn | Sự cố chứng cứ | Cần rà; không bịa nguồn kia |
| Có hai phía nhưng thiếu ngữ cảnh | `INSUFFICIENT_EVIDENCE` | Nêu thiếu gì |
| Khác đối tượng / không đổi đơn vị / ngoại tệ | `NOT_COMPARABLE` | Không cảnh báo xung đột |
| Có sửa/thay rõ phần bị sửa | Ứng viên sửa đổi | Trước/sau; không xác nhận hợp lệ |
| Cùng ngữ cảnh, số sau chuẩn hóa tương đương | Khớp | Có thể xem cặp, không hàng cảnh báo |
| Cùng ngữ cảnh, số hoặc nghĩa trái | Khác biệt | Ứng viên cần rà, không án |

Tiền: số thập phân chuỗi, không float. Phần trăm: `0,2%` là 0,2 không phải 2. VAT không hard-code. Bảng: khóa dòng = mục + đơn vị, không số thứ tự toàn cục.

## 6. Enum và trạng thái chuẩn

Các tên dưới đây là tên code/API; chữ “REVIEW” trong tên fixture chỉ là nhãn ngắn, không phải `ReviewState.REVIEW`.

| Lớp | Giá trị |
|---|---|
| `Disposition` | `NEEDS_EVIDENCE`, `NOT_COMPARABLE`, `CANDIDATE_AMENDMENT`, `COMPARABLE_MATCH`, `COMPARABLE_DIFFERENCE` |
| `ModelDisposition` | `CONSISTENT`, `CONFLICTING`, `INCOMPLETE`, `UNCLEAR` |
| `FindingType` | `MATCH`, `DIVERGENCE`, `GAP`, `AMBIGUITY`, cùng các loại comparable/amendment/evidence |
| `ReviewState` | `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`, `NOT_COMPARABLE`, `ANSWERED` |
| `ComparisonScope` | `WITHIN_DOCUMENT`, `CONTRACT_ANNEX`, `ANNEX_ANNEX` |

`EvidenceIssue` là thiếu tài liệu/ngữ cảnh và được lưu riêng; không biến nó thành một finding xung đột.

## 7. Cấm

Suy vai trò từ tên file. Công bố khi nguồn không resolve. Đổi `INSUFFICIENT` thành thành công. Ghi đè OCR. Một lần sửa người dùng tự đổi rule/gold.
