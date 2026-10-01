# Document governance - LF-2.0

Ngày 18/09/2026 | Bộ tài liệu thiết kế local, không là runtime implementation

## 1. Authority và baseline

Assignment và quyết định trực tiếp mới nhất của user là nguồn yêu cầu. Nếu hai nguồn mâu thuẫn, ghi gap/decision và tác động, không tự đổi yêu cầu assignment. DOC-01..06 là các góc nhìn của cùng baseline LF-2.0; tài liệu cũ không phủ định local-first.

| Phạm vi | Authority |
| --- | --- |
| Value, audience, scope high-level | DOC-01 |
| Business rules và dispositions | DOC-02 |
| Product behavior, UX, acceptance | DOC-03 |
| Technical boundaries, data/runtime, ADR | DOC-04 |
| HTTP shape | DOC-05; shared JSON schemas là authority cho payload dùng chung |
| Metrics, test protocol, actual evidence | DOC-06 |
| Decisions, defaults, deferred work | Sẽ được chuẩn hóa trong governance pass tiếp theo |
| Standards và output checklist | Sẽ được chuẩn hóa trong governance pass tiếp theo |

## 2. Metadata và evidence levels

Mỗi tài liệu nêu ID, baseline version, date, trạng thái, owner theo vai trò, upstream/downstream và phần bị thay thế. Author: Codex. Reviewer: self-review trong task tài liệu; không gán mentor/user đã sign-off. Owner vai trò là trách nhiệm đề xuất, không là cá nhân đã phê duyệt.

CONFIRMED = quyết định user; DESIGN_DEFAULT = lựa chọn có lý do; TARGET = chưa đo; OBSERVED_DOC = kiểm tra artifact; NOT_RUN = chưa thực hiện runtime/user study. Không đặt APPROVED chỉ vì tác giả đã review.

## 3. Change control

Một thay đổi scope ghi affected BR/FR/TC, decision, rationale, người quyết định và interface/version implications. Đồng bộ requirements tới contracts/eval trong cùng change set. Không buộc mỗi requirement phi-API có một endpoint giả.

Local-first schemas là breaking design baseline riêng. OpenAPI 3.1.1, API version 2.0.0-draft không tương thích ngầm với 0.6.0. Không claim database/source ứng dụng đã migrate hoặc runtime tests passed.

## 4. Archive và handoff

Bản trước chỉ còn trong Git history. Không dùng tài liệu legacy làm authority hoặc template cho implementation mới.

PDF bàn giao local trong output/pdf; Markdown/YAML/JSON/Mermaid/SVG là nguồn version-control theo policy repo. Review artifact hiện hành xem tại [reviews](../reviews/README.md). Traceability sẽ được chuẩn hóa ở change set riêng.

## 5. Ba mức acceptance

Document pass: nội dung nhất quán, scenarios có lời giải, schemas/examples/links hợp lệ, PDF đọc được. Local product pass: runtime tests và số đo thật. User validation pass: reviewer phù hợp hoàn thành tác vụ có evidence. Ba mức độc lập.
