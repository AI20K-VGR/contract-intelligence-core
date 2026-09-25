# Kết luận nghiên cứu: `ai1.result.v0.1` và `ai1.snapshot.v1`

**Phạm vi:** Đánh giá lựa chọn contract AI1–AI2 dựa trên output thực tế `ocr-result.json`.

**Kết luận ngắn:** `ai1.snapshot.v1` nên là canonical contract chính thức giữa AI1 và AI2. `ai1.result.v0.1` chỉ nên được giữ như compatibility adapter tạm thời để AI2 xử lý output hiện tại.

## 1. Vấn đề hiện tại

File output hiện tại là result envelope với:

```text
machine/effective.schema_version = "0.1"
status = "pending_review"
review.blocked = true
```

Đây không phải payload `ai1.snapshot.v1`. Vì vậy không nên đưa trực tiếp file này vào canonical flow dành cho snapshot v1 hoặc chỉ đổi tên `schema_version` để giả lập snapshot v1.

Audit offline cho thấy dữ liệu không bị hỏng:

- 6 trang, coverage hoàn tất;
- 6 bảng với 258 cells;
- 47 citation gốc từ AI1;
- pipeline AI2 tạo được 44 facts;
- pipeline hoàn tất ở trạng thái `NEEDS_REVIEW`;
- 292 citation nội bộ hợp lệ và 18 citation `INVALID`/`UNVERIFIED`;
- 14 evidence issues;
- 0 findings không có nghĩa là các bảng đã được xác nhận nhất quán.

Các vấn đề chính là lệch contract, provenance chưa thống nhất, table grounding chưa đầy đủ và AI1 đang ở trạng thái pending review.

## 2. Nếu sử dụng `ai1.result.v0.1`

### Ưu điểm

- Dùng được ngay với `ocr-result.json` hiện tại.
- Đã có sẵn clauses, tables, citations và review status.
- AI2 không cần dựng lại toàn bộ cấu trúc ban đầu.
- Phù hợp cho compatibility testing và regression trên output thực tế.

### Nhược điểm

- Đây là output đã qua xử lý, không còn là raw OCR snapshot thuần túy.
- Ownership bị trộn: AI1 có thể gửi sẵn clauses, facts và findings, trong khi AI2 tiếp tục tạo facts/findings.
- AI2 bị phụ thuộc chặt vào cấu trúc riêng của result envelope AI1.
- Provenance cho replay/audit chưa đầy đủ như `execution`, `producer` và `language` của snapshot v1.
- `pending_review` và `review.blocked` khiến AI2 chỉ được tạo kết quả `NEEDS_REVIEW`, không được publish authoritative.
- Một số table cells không có line grounding hoặc có text rỗng, dẫn đến citation `INVALID`/`UNVERIFIED`.
- Không nên dùng compatibility endpoint làm contract production dài hạn.

### Luồng phù hợp

```text
ocr-result.json
    → adapter ai1.result.v0.1
    → AI2 deterministic processing
    → NEEDS_REVIEW nếu còn evidence issue
```

Khi dùng flow này, mọi fact do AI2 suy ra phải được ghi nhận là AI2-derived; không được coi chúng là facts do AI1 phát hành.

## 3. Nếu sử dụng `ai1.snapshot.v1`

### Ưu điểm

- AI1 chỉ sở hữu OCR/layout evidence.
- AI2 sở hữu facts, findings, retrieval và reasoning.
- Có JSON Schema canonical và identity rõ ràng.
- Có provenance cho execution, producer, language, source digest và page revision.
- Phù hợp cho replay, audit, indexing và kiểm soát version.
- Phân biệt được evidence thiếu, evidence không chắc chắn và evidence thất bại.
- Giảm coupling giữa AI1 và pipeline nội bộ của AI2.

### Nhược điểm

- AI1 phải thay đổi output để phát đúng contract.
- Output hiện tại không thể chuyển thành snapshot v1 chỉ bằng cách đổi tên version.
- Cần bổ sung hoặc chuẩn hóa các field như:

  - `snapshot_id`, `created_at`;
  - `execution`, `producer`, `language`;
  - `page_revision_id`, `raw_text_digest`;
  - `quality`, `table_coverage`;
  - `geometry_status`, `bbox_source`;
  - `line_ids` cho table cells khi có grounding.

- AI2 phải tự dựng clauses, facts và findings từ evidence.

### Luồng chuẩn

```text
AI1 phát ai1.snapshot.v1
    → Backend/transport giữ nguyên payload
    → AI2 validate và adapt
    → AI2 tạo facts/findings/reasoning
```

## 4. So sánh

| Tiêu chí | `ai1.result.v0.1` | `ai1.snapshot.v1` |
|---|---|---|
| Dùng với file hiện tại | Có | Không trực tiếp |
| Contract dài hạn | Không nên | Nên dùng |
| Evidence ownership | Trộn với extraction | Rõ ràng |
| Replay/audit | Hạn chế | Tốt |
| AI2 phụ thuộc AI1 | Cao | Thấp |
| Schema ổn định | Chưa đủ | Có |
| Facts/findings | AI1 có thể đã tạo | AI2 tạo |
| Production integration | Compatibility | Canonical |

## 5. Quyết định được đề xuất

Sử dụng mô hình hai tầng:

1. `ai1.snapshot.v1` là contract canonical chính thức giữa AI1 và AI2.
2. `ai1.result.v0.1` là compatibility input tạm thời cho test và migration.

Không chọn `ai1.result.v0.1` làm contract chính chỉ vì nó đang chạy được. Result envelope phù hợp để tiếp tục nghiên cứu AI2 trên output hiện tại, nhưng sẽ tạo technical debt và làm mờ trách nhiệm giữa AI1 và AI2.

## 6. Việc cần làm tiếp theo

### Giai đoạn hiện tại: tiếp tục test AI2

- Giữ adapter `ai1.result.v0.1` để xử lý `ocr-result.json`.
- Giữ rõ metadata `source = ai1.result.v0.1`.
- Giữ trạng thái `NEEDS_REVIEW` khi AI1 pending hoặc citation chưa xác minh.
- Không cho phép publish authoritative từ result đang bị block.
- Phân biệt input facts của AI1 với facts do AI2-derived.

### Giai đoạn canonical migration

- Yêu cầu AI1 phát một sample thực theo `ai1.snapshot.v1`.
- Kiểm tra đầy đủ raw text, line, word, table, bbox, quality, warning và digest.
- Chạy cùng một bộ acceptance test AI2 trên `result.v0.1` và `snapshot.v1`.
- Kiểm tra AI2 không tự tạo geometry hoặc thay đổi raw evidence.
- Chỉ xem snapshot v1 là integration baseline sau khi schema và provenance được xác nhận.

### Nguyên tắc không được vi phạm

- Không đổi tên `schema_version` của result envelope để giả lập snapshot v1.
- Không dùng `effective_result_hash` thay cho `source_digest` nếu semantics không tương đương.
- Không coi `findings = 0` là bằng chứng rằng dữ liệu nhất quán.
- Không coi citation có bbox hợp lệ là đã được con người xác minh trên PDF.
- Không publish khi AI1 vẫn ở trạng thái `pending_review` hoặc còn evidence issue chưa được xử lý.

## 7. Tài liệu liên quan

- [Contract AI1–AI2](../contracts/AI1-AI2-CONTRACT.vi.md)
- [Canonical schema `ai1.snapshot.v1`](../contracts/ai1.snapshot.v1.schema.json)
- [Handoff AI1 snapshot](AI2-09-ai1-snapshot-handoff.vi.md)
- [Review output AI1 thực tế](../reviews/AI2-REVIEW-2026-09-22.vi.md)
