# Brainstorm report — cách hoàn thiện AI2

**Ngày:** 2026-09-23  
**Câu hỏi:** AI2 nên được hoàn thiện theo cấu trúc và thứ tự nào để xử lý contract/annex nhiều loại nhưng không suy diễn?

## 1. Problem frame

AI2 không nên được xem là một chatbot đọc văn bản. Nó nên là một lớp semantic dossier:
biến snapshot AI1 thành cấu trúc, facts, relations, comparisons và câu trả lời có thể truy
ngược về evidence. Phụ lục là một member/scope của dossier khi có membership/evidence xác nhận;
không phải một hợp đồng độc lập chỉ vì tên file hoặc `dossier_id` trùng.

## 2. Ba hướng

### A — Evidence-first semantic dossier

```text
AI1 snapshot
  → boundary validator
  → dossier members + structure tree
  → citation/provenance gate
  → profile facts
  → relation graph
  → comparison findings
  → bounded free-form Q&A
```

Đây là hướng được đề xuất. Mỗi lớp chỉ được dùng output của lớp trước khi evidence đủ.

### B — Profile-first extraction

Làm sáu profile và các field đặc thù trước, sau đó mới chuẩn hóa structure/relations.

Ưu điểm: dễ demo các field theo loại hợp đồng. Nhược điểm: có thể tạo field đúng tên nhưng
sai scope, sai citation hoặc không biết field thuộc body hay annex nào.

### C — Q&A/RAG-first

Làm router, retrieval, prompt và câu trả lời tự do trước; extraction/relations bổ sung sau.

Ưu điểm: demo nhanh. Nhược điểm: câu trả lời có thể trông đúng nhưng thiếu evidence, dễ mở
ra ngoài dossier và khó phân biệt thiếu dữ liệu với model đoán.

## 3. Critique

### A — Adopt with guard

Rủi ro chính là người dùng chưa thấy Q&A hoàn chỉnh sớm. Guard bắt buộc: tạo một vertical slice
đủ dùng, trong đó câu hỏi chỉ được đọc semantic dossier đã có citation; không chờ toàn bộ sáu
profile mới demo được.

### B — Adopt only as a sub-slice

Profile-first có ích bên trong một vertical slice, nhưng không được là kiến trúc tổng thể. Nếu
làm cả sáu profile cùng lúc, registry dễ phình; nếu thiếu evidence layer, mọi lỗi extraction
khó phân biệt là lỗi profile hay lỗi nguồn.

### C — Reject as primary direction

Q&A-first tạo áp lực tối ưu tỷ lệ trả lời thay vì tỷ lệ câu trả lời có thể kiểm chứng. RAG cũng
không tự loại bỏ prompt injection; tool surface mở rộng sẽ làm tăng rủi ro scope leakage và
excessive agency. Q&A chỉ nên là consumer read-only của dossier.

## 4. Converged direction

### AI2 v1 = evidence-first semantic dossier + bounded query

AI2 nên có bốn lớp sản phẩm:

1. **Boundary layer** — xác thực snapshot AI1, identity, tenant/dossier, source member,
   version, digest và producer profile; không sửa raw snapshot.
2. **Semantic dossier layer** — tạo member contract/annex, structure tree, clause/table
   scope, typed facts, citation/provenance và relation graph.
3. **Analysis layer** — tạo comparison candidate, missing-context issue, amendment candidate
   và safe states; không tạo precedence hoặc `LEGAL_WINNER`.
4. **Query layer** — nhận câu hỏi tự do nhưng chỉ đọc trong selected dossier members, chạy
   exact/structured trước semantic recall, rồi grounding; thiếu evidence thì trả safe state.

### Nguyên tắc dữ liệu

- Raw AI1 snapshot là immutable source.
- Mọi `Fact`, `Candidate`, `Relation` và câu trả lời phải có citation hoặc review state.
- `raw_value` và `normalized_value` tách nhau; normalize không được xóa raw.
- `scope_id` là bắt buộc để phân biệt body, annex, clause, table và document member.
- Quan hệ không resolve được phải trở thành `CONTEXT_GAP`/`NEEDS_REVIEW`, không thành quan hệ chắc chắn.
- `NOT_COMPARABLE` là kết quả hợp lệ khi khác unit, currency, validity hoặc scope.

### Thứ tự hoàn thiện nên dùng

**Mốc 1 — Foundation:** boundary contract, profile registry versioned, core fields, member/scope,
citation resolver và safe-state taxonomy.

**Mốc 2 — Semantic spine:** structure tree đầy đủ, body/annex membership, relation graph tối
thiểu, fact model có provenance và issue model thống nhất.

**Mốc 3 — First vertical slice:** chọn 1–2 profile có corpus thực tế để chạy trọn đường từ
snapshot → structure → facts → comparison → Q&A. Khuyến nghị bắt đầu `SALES` và
`SUPPLY_SERVICE`, nhưng cần xác nhận mapping với corpus trước khi khóa.

**Mốc 4 — Profile expansion:** thêm `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`; chỉ
thêm field khi có evidence, alias hoặc reviewer requirement rõ.

**Mốc 5 — Annex expansion:** giá, số lượng, kỹ thuật, tiến độ, SLA, thanh toán, nghiệm thu,
điều chỉnh; extension dùng chung trên dossier member, không nhân bản toàn bộ schema.

**Mốc 6 — Release/evaluation:** candidate corpus 95 và manifest 65 phải được reconcile; chưa
có golden set thì chỉ công bố schema/citation/safety/regression, không công bố business accuracy.

## 5. Definition of done cho AI2 v1

AI2 v1 chỉ nên được coi là hoàn thiện khi:

- một dossier có thể trả ra đầy đủ tree của contract và annex mà không làm mất raw source;
- field/fact đặc thù có profile, raw/normalized value, scope, provenance, citation và review state;
- câu hỏi “phụ lục thay đổi điều khoản nào?” đi qua relation + comparison, không chỉ semantic search;
- comparison có evidence hai phía và phân biệt conflict với `NOT_COMPARABLE`;
- câu hỏi ngoài dossier, thiếu context, citation hỏng hoặc relation mơ hồ đều có safe state;
- Q&A không có quyền gọi tool/file/URL tùy ý và không tự tạo kết luận pháp lý;
- báo cáo release tách candidate, golden, not-run, failed và chưa đủ evidence.

## 6. Những việc chưa nên làm

- Không xây một ontology cho mọi loại hợp đồng ngay từ đầu.
- Không làm Q&A/RAG trước structure và citation.
- Không ép mọi field về một union schema lớn.
- Không dùng tên file hoặc `dossier_id` làm bằng chứng cho quan hệ contract–annex.
- Không dùng 95 case chưa review để claim accuracy.
- Không đưa OCR provider, backend ACL/queue, frontend HITL hoặc legal precedence vào AI2 wave này.

## Verdict

**Adopt A with the vertical-slice guard.** Đây là hướng ít rủi ro nhất và tận dụng được code
hiện có. B được dùng như kỹ thuật triển khai trong từng slice; C và D để backlog cho đến khi
semantic dossier, citation và golden evidence đủ mạnh.

