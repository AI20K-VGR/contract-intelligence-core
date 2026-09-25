# Pipeline local - OCR, analysis và human review

LF-2.0 | 18/09/2026 | Tên file giữ để bảo toàn liên kết; không còn auto-optimization control plane

## 1. Ranh giới

Worker gọi OCR/structure/analysis modules trực tiếp qua Python ports. API sở hữu intake/review; worker dùng persistence port chung để đọc immutable inputs và commit validated artifacts. Không có HTTP job registry, dispatcher service, message bus hoặc vòng AI tự gọi lại AI vô hạn. [DOC-04](../DOC-04-architecture.md) là authority technical; [BRD](../DOC-02-brd.md) là authority business.

## 2. Luồng xuôi

Seal manifest -> enqueue run -> claim một run -> render/extract từng trang có giới hạn -> persist checkpoint -> assemble clause/table -> extract typed facts -> generate candidates -> compare -> validate evidence -> publish result. UI poll run/coverage, không wait HTTP request suốt pipeline.

Mỗi stage có input hash/config, output schema, warnings và checkpoint. Cloud submission được ghi trước/sau gửi với provider operation ID nếu có. Request timeout không xác định đã nhận phải chờ kiểm tra/explicit retry, không blind resend.

## 3. Luồng review và re-OCR

Human correction -> append overlay + audit -> effective review view; machine result không đổi. Người dùng yêu cầu PAGE re-OCR -> child run pin parent manifest/page revision -> thay OCR đúng trang -> reuse các trang còn lại -> dựng lại structure/extract/compare toàn hồ sơ -> publish child -> review cũ STALE. Không selective dependency graph hoặc auto carry confirmations.

AI phát hiện gap chỉ trả EvidenceIssue. UI đưa reviewer lựa chọn re-OCR hoặc ghi nhận cần tài liệu; không auto-purchase thêm provider calls.

## 4. Gate và lỗi

| Gate | Không đạt thì |
| --- | --- |
| Input inventory/consent/limits | Reject admission hoặc fail preflight với code |
| Page extraction/geometry | NEEDS_REVIEW/FAILED, giữ denominator và ảnh |
| Table continuation | PARTIAL table; block facts cần phần thiếu |
| Fact grounding/context | Không publish fact như validated; issue có nguồn |
| Comparison evidence | Chuyển insufficient hoặc quarantine artifact invalid |
| Current attempt/run generation | Không publish stale completion |
| Budget/provider ambiguity | Dừng submission mới; user thấy reason và unresolved cost |

BLANK_VERIFIED cần kiểm tra render, không chỉ text empty. Finding hai phía phải có hai sources đã resolve. Missing document là EvidenceIssue, không invented second citation.

## 5. Cache và phiên bản

Cache chỉ reuse khi input digest, page transform và OCR profile digest khớp; force re-OCR trang được chọn phải tạo revision dù output trùng. Analysis cache không được reuse khi input snapshot hoặc analysis profile đổi. Config/model/prompt ghi mỗi run, không floating profile silently.

Kết quả trước và review trước đọc được cho tới khi user xóa dossier. Deletion là thao tác riêng được xác nhận; không gọi mutation vào immutable source để “sửa OCR”.
