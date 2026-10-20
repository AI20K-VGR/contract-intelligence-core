# DOC-01 — Tầm nhìn sản phẩm (phần AI2)

**Phiên bản:** v1.1 · **Ngày:** 20/09/2026 · **Phạm vi:** thành phần AI2 (trích xuất, so hai nguồn, hỏi có biên).  
**Nguồn:** [DOC-01](../DOC-01-product-vision.md), [AI2-01](AI2-01-business-policy-perspective.vi.md).  
**Không thay:** BRD / PRD / kiến trúc. Không claim độ chính xác hay sản phẩm đã nghiệm thu.

## 1. Tầm nhìn

Biến một hồ sơ (hợp đồng + phụ lục) thành bản đồ sự kiện và phát hiện **hai nguồn** có thể mở lại trang gốc. Người rà soát tìm đúng chỗ khác biệt hoặc thiếu chứng, không đọc hết từng file. Máy **không** thay quyết định pháp lý.

## 2. Người dùng

| Nhóm | Việc | Kết quả cần |
|---|---|---|
| Chuyên viên mua hàng / rà hợp đồng | So giá, MST, phạt, thanh toán giữa thân và phụ lục | Cặp nguồn, ngữ cảnh, trạng thái cần rà |
| Người nhận bàn giao | Xem đã rà và còn thiếu | Xuất kèm nguồn; không mất khi tắt máy (phiên local) |

Một người trên một máy thí điểm. Backend cấp quyền / nhiều tenant là đích sản phẩm, không phải lời hứa bản demo AI2.

## 3. Nhu cầu

- Định vị điều, bảng, giá trị: file / trang / hộp chữ.
- Chỉ so khi **cùng đối tượng và phạm vi**.
- Phân biệt khớp, khác, ứng viên sửa đổi, không so được, thiếu chứng.
- Xác nhận / sửa lớp người / từ chối — không ghi đè chữ máy.
- Hỏi hẹp có trích dẫn; từ chối “tóm tắt toàn bộ hồ sơ”.

## 4. AI2 làm gì / không làm gì

**Làm:** nhận snapshot AI1 đã ghim phiên bản; định tuyến trường / bảng / điều; trích sự kiện; sandbox bảng (ô trống ≠ 0); so hai nguồn; đề xuất chỉ mục; hỏi L0–L3; lớp rà trên phát hiện.

**Không làm:** OCR/layout (AI1); đăng nhập, ACL, công bố chỉ mục thật (BE); chatbot mở; kết luận bên thắng; gửi nguyên PDF vào mô hình.

## 5. Mục tiêu nghiệp vụ

- Giảm thời gian tìm cặp nội dung cần đối chiếu.
- Không biến thiếu phụ lục thành “không có rủi ro”.
- Mọi cảnh báo mở được nguồn.
- Có số liệu phủ (số sự kiện, số phát hiện), không dùng độ tin mô hình làm chứng.

## 6. Phạm vi

**Trong:** 1 hợp đồng + 0..n phụ lục PDF; tiếng Việt (Anh là lớp kiểm tra); so thân↔phụ lục và trong một tài liệu; demo FastAPI trên máy.

**Ngoài:** DMS, email, DOCX, chữ ký số, hợp đồng hợp nhất có hiệu lực, học từ một lần sửa của người dùng.

## 7. Giả thuyết (chưa phỏng vấn user)

H1: bảng hai nguồn hữu ích hơn tóm tắt dài. H2: tách sửa đổi / khác / thiếu chứng giảm cảnh báo sai. H3: lớp rà có lịch sử đủ để bàn giao thí điểm.

## 8. Trạng thái đã kiểm tra

Đây là tài liệu bổ sung AI2, không phải tuyên bố nghiệm thu sản phẩm. Code hiện chạy theo snapshot/fixture, AI1 upload trong demo vẫn là lớp giả lập; các fixture EC-001..EC-056 là danh mục kiểm thử, không phải 56 case đã pass end-to-end.

| Nhóm | Hiện xử lý được | Cách xử lý hiện tại |
|---|---|---|
| Case thực/gold | `HD-TONG-HOP`, `SALE-BRD-07`, `SERVICE-BRD-08` | Trích fact có citation, ghép theo `item_key`/scope, không chọn `LEGAL_WINNER` |
| Edge deterministic | thiếu annex, khác currency/scope, ô thiếu, query quá rộng, prompt injection, ACL/lifecycle | `EvidenceIssue`, `NOT_COMPARABLE`, `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE`, hoặc `BLOCKED` |
| Partial/mock | bảng nhiều trang/merged, số bằng chữ, ngày tương đối, bilingual, scan mờ, re-OCR/version | Giữ raw, hạ trạng thái review hoặc ghi gap; chưa claim độ chính xác |
| Ngoài AI2 | OCR thật, worker/lease, Postgres/RLS, vector/cost/egress/purge | BE/AI1 sở hữu; AI2 chỉ nhận snapshot đã ghim |

Nguyên tắc sản phẩm: một finding chỉ có giá trị khi mở được nguồn; thiếu nguồn hoặc ngữ cảnh thì nêu thiếu, không suy đoán.
