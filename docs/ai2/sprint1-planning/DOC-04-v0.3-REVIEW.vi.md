# Report review DOC-04 v0.3 — Contract Intelligence

| Thuộc tính | Nội dung |
|---|---|
| **Tài liệu review** | `DOC-04-v0.3-system-design.md` |
| **Căn cứ** | `assignment.pdf`, `AI1-OCR-SNAPSHOT-HANDOFF.md`, `ST-017-DATA-CONTRACT.vi.md` |
| **Kết luận** | **Chưa đạt điều kiện gửi Mentor duyệt nguyên trạng.** |
| **Phạm vi** | Review thiết kế; không khẳng định đã có OCR run, quality, cost hoặc production readiness. |

## 1. Tóm tắt

DOC-04 v0.3 đã cải thiện rõ rệt so với bản trước: dùng `Dossier` làm aggregate, thêm pipeline/job lifecycle, phân biệt structured và semantic finding, và đưa immutable review history vào thiết kế. Tuy vậy, tài liệu tự nhận đã giải quyết toàn bộ P0/P1 là chưa đúng. Một số contract lõi vẫn không biểu diễn được provenance theo đề bài, hoặc mâu thuẫn với scope Sprint 2–3.

## 2. Phát hiện P0

### P0-01 — Citation không biểu diễn evidence nhiều thành phần

**Hiện trạng:** §2.3 chỉ cho một `page_no`, `line_id`, `char_start/end`; finding giữ hai danh sách citation nhưng từng citation vẫn một dòng duy nhất.

**Tác động:** Một value kéo qua nhiều dòng/trang, ngữ cảnh ở dòng khác, hoặc một cell bảng không thể truy vết chính xác. Điều này không đạt chuỗi bắt buộc `document → page → OCR line(s) → character span → bbox`.

**Yêu cầu sửa:** `Citation.components[]`; mỗi component có `page_no`, `line_id`, Unicode span, word IDs và bbox refs. Cần cho phép ref `table_cell` và không union bbox qua các trang.

### P0-02 — Page/render provenance chưa bất biến

**Hiện trạng:** `PageFrame` không gắn `snapshot_id`, `page_image_ref`, render digest, renderer/profile, crop/transform. Kích thước được mô tả là trước chuẩn hóa trong khi bbox thuộc upright frame.

**Tác động:** Không chứng minh được overlay đang hiển thị đúng render mà OCR/bbox đã dùng; re-render có thể làm citation lệch mà không phát hiện.

**Yêu cầu sửa:** mỗi render artifact thuộc một snapshot/page và có URI, SHA-256 digest, upright width/height, renderer/render profile, source page index và transform spec.

### P0-03 — Bbox/table schema mâu thuẫn contract AI1

**Hiện trạng:** DOC-04 dùng `(x,y,w,h)` nhưng handoff AI1 dùng `[x0,y0,x1,y1]`. `TableCell` giữ `citation_id` nhưng `Citation.bbox_refs` không có `table_cell`.

**Tác động:** BE/FE/AI1 không thể cùng implement một coordinate contract; table source tạo vòng tham chiếu hoặc không highlight được.

**Yêu cầu sửa:** dùng độc nhất `[x0,y0,x1,y1]`, origin top-left trong upright render; table/cell có source components riêng và citation được phép ref cell.

### P0-04 — Review model không hỗ trợ review fact và mâu thuẫn immutable rule

**Hiện trạng:** `ReviewRevision.target_type` không có `FACT`; `Finding` có `review_status` nhưng Finding lại được tuyên bố immutable.

**Tác động:** Không thực hiện được yêu cầu reviewer correct value; current review status có nguy cơ update machine output.

**Yêu cầu sửa:** target type gồm `FACT`, `FINDING`, `CLAUSE`, `EVIDENCE_SELECTION`; mọi current state được dựng từ revision chain/materialized read model, không ghi lên machine entity.

### P0-05 — Precedence rule quá mạnh và có thể biến thành kết luận pháp lý

**Hiện trạng:** annex có effective date muộn hơn được coi precedence evidence mặc định.

**Tác động:** Ngày hiệu lực muộn không chứng minh văn bản đó sửa đúng subject/điều khoản đang so sánh.

**Yêu cầu sửa:** chỉ tạo `candidate_amendment` khi có reference base, wording sửa đổi, scope tương thích và effective date muộn hơn. Không tự quyết document nào thắng; reviewer/adjudicator xác nhận.

### P0-06 — Pipeline tiếp tục sau OCR fail mà chưa có partial policy

**Hiện trạng:** completion barrier cho structuring chạy khi OCR terminal, kể cả `FAILED`.

**Tác động:** finding cross-document có thể được tạo khi thiếu contract hoặc annex nguồn; vi phạm nguyên tắc insufficient evidence.

**Yêu cầu sửa:** mọi input required failed/partial phải đưa run vào `PARTIAL` hoặc `BLOCKED`; chỉ xuất partial facts có reason, không xuất comparative alert khẳng định.

## 3. Phát hiện P1

- `OcrSnapshot` thiếu source digest, page status/input type, raw page text, warning/error và processing metadata cần cho audit.
- Semantic conflict chưa có `SemanticClaim`/`ClauseAssertion`; bảy fact structured không đủ biểu diễn action, modality, polarity, exception và condition.
- `relationship_evidence` là text tự do; cần manifest versioned, actor, timestamp, source evidence và trạng thái xác nhận.
- Language chỉ ở document/page và enum không chuẩn; cần BCP-47 và language ở block/line cho trang song ngữ.
- Cache `dossier_scope` chưa định nghĩa; retention “N ngày” chưa là policy có owner/giá trị.
- Claim Luna “đã benchmark/rẻ nhất” phải có run/sample/n; nếu chưa có phải ghi candidate/pending benchmark.
- Security thiếu policy external service, retention/deletion, object-storage authorization và audit access.

## 4. Mâu thuẫn với đề bài ở phạm vi Sprint

§11 cho phép hoãn word bbox, multilingual, dead-letter/quarantine và review revision. Điều này không phù hợp với đề bài:

- Word, line, clause-region bbox là capability fixed.
- Thiết kế Việt/Anh và trang song ngữ là fixed.
- Batch cần retry/crash handling và job không biến mất.
- Sprint 2 yêu cầu HITL cơ bản có thể correct; không thể hoãn immutable correction semantics sang Sprint 3.

Phần có thể hoãn chỉ là **polish/coverage mở rộng**, không phải bỏ contract hoặc behavior bắt buộc.

## 5. Khuyến nghị trạng thái

Không ghi “giải quyết toàn bộ P0/P1”. Nên thay bằng: “Đã xử lý một phần finding của v0.1; v0.4 chờ team/mentor review các contract và open decision.”

DOC-04 v0.4 được tạo song song với report này để giải quyết các vấn đề trên mà vẫn giữ v0.3 làm lịch sử review.
