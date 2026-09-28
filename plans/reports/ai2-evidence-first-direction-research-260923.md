# Research: AI2 nên hoàn thiện theo hướng kiến trúc nào?

**Mode**: breadth  
**Date**: 2026-09-23  
**Sources reviewed**: 7 nguồn ngoài repo + các điểm neo code/tài liệu trong repo

## Central question

AI2 cần hỗ trợ nhiều loại hợp đồng và phụ lục, trích xuất structure/fact/field,
quan hệ, so sánh và câu hỏi tự do. Hướng hoàn thiện nào cho độ tin cậy cao nhất
trong khi vẫn mở rộng được sau wave đầu và chưa có golden set nghiệp vụ?

Tiêu chí: evidence/citation, giới hạn scope, khả năng mở rộng profile, khả năng kiểm thử,
chi phí thay đổi và mức phù hợp với code hiện có.

## Summary

Khuyến nghị **evidence-first, vertical-slice**: khóa dossier/scope/structure/citation/provenance
trước, rồi xây typed facts và comparison trên nền đó; free-form Q&A chỉ là consumer ở lớp cuối.
Profile nên là registry versioned nhỏ, có core fields + extension theo loại, không phải union schema
khổng lồ. Hướng này phù hợp với `query.py`, `compare.py`, `relations.py`, `outline.py` và model
`Fact`/`Candidate` hiện có, đồng thời giữ được safe state khi chưa có golden set.

## Evidence summary

1. JSON Schema khuyến nghị khai báo `$schema` để cố định dialect; custom vocabulary có thể mở rộng
   nhưng mọi validator phải hiểu semantics riêng. Điều này ủng hộ profile versioning và hạn chế
   custom keyword ngoài phần cần thiết. [1]
2. W3C PROV coi provenance là thông tin về entity, activity và agent dùng để đánh giá chất lượng,
   độ tin cậy; mô hình cũng nhấn mạnh reproducibility, versioning và derivation. Đây là cơ sở cho
   citation/provenance của fact, relation và answer. [2]
3. NIST AI RMF yêu cầu xác định context/knowledge limits, kiểm thử trước triển khai, ghi test set
   và metrics, chứng minh validity/reliability trong điều kiện triển khai, và ghi giới hạn
   generalization. Điều này củng cố policy `UNVERIFIED`/golden set của repo. [3]
4. OWASP cảnh báo RAG không tự loại bỏ prompt injection và excessive agency; extension nên tối
   thiểu, granular, ít quyền và tránh open-ended tool. Vì vậy Q&A phải bounded, read-only và không
   biến câu hỏi tự do thành tool execution tùy ý. [4][5]
5. Repo đã có các mảnh evidence pipeline: `ai-service/app/pipeline/outline.py`,
   `ai-service/app/pipeline/compare.py`, `ai-service/app/reasoning/relations.py`,
   `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/stack.py` và các model
   citation/review trong `ai-service/app/contracts/models.py`. Đây là quan sát trực tiếp từ code,
   không phải giả định.

## Option space

| Option | Mô tả | Ưu điểm | Nhược điểm | Project fit |
|---|---|---|---|---|
| A. Evidence-first dossier core | Khóa identity/scope, structure tree, citation/provenance, relation graph; facts/comparison/Q&A dùng cùng nền | An toàn, debug được, tái dùng cho mọi profile, Q&A không tự tạo truth | Giá trị Q&A nhìn thấy muộn hơn; cần làm evidence contract kỹ | **+ cao nhất** |
| B. Profile-first extraction | Làm sáu profile và field đặc thù trước, sau đó mới nối relation/comparison/Q&A | Dễ trình diễn field theo loại; schema rõ sớm | Dễ phình schema; field có thể đúng hình thức nhưng sai scope/citation; relation bị làm sau | + vừa |
| C. Q&A/RAG-first | Tập trung router, retrieval, prompt và trả lời tự do trước | Demo nhanh; cảm giác sản phẩm rõ | Scope leakage, prompt injection, citation yếu; không giải quyết extraction nền | - thấp |
| D. Universal ontology/graph-first | Dựng ontology tổng quát cho mọi hợp đồng và phụ lục trước | Có tham vọng mở rộng dài hạn | Over-modeling khi chưa có corpus/golden; semantics pháp lý dễ bị đóng cứng sai | - vừa/thấp |

## Probe result and confidence

- `query.py:16-171` đã có route typed intent và `unscoped`; chưa đủ để coi câu hỏi tự do
  là bounded dossier Q&A hoàn chỉnh.
- `compare.py:42-361` đã có comparison scopes, `NOT_COMPARABLE` và hai phía evidence;
  cần làm rõ input profile/scope thay vì thay bằng agent tổng quát.
- `relations.py:128-386` đã có graph edges và explicit-text support; đây là điểm neo tự nhiên
  cho body-annex, reference và amendment candidate.
- `result_structure.py:1-87` và `outline.py:9-227` đã có derived hierarchy, parent/order/scope
  và citation resolver node-first; cần giữ raw AI1 bất biến.
- `models.py:435-470` đã có `Fact` và `Candidate` với citation/review state; profile registry
  nên bổ sung semantics thay vì tạo model song song.

## Recommendation

**Priority 1: Option A — Evidence-first dossier core, triển khai theo vertical slice.**

Thứ tự sản phẩm nên là:

1. Contract boundary + profile registry versioned: field core nhỏ, sáu profile wave đầu và
   extension cho phụ lục; unknown field/type giữ raw + `UNMAPPED`/`NEEDS_REVIEW`.
2. Dossier evidence layer: structure tree, member/scope, immutable raw snapshot, citation
   resolver, provenance và relation graph.
3. Typed facts + comparison: chỉ pair khi key/subject/unit/currency/validity/scope tương thích;
   mọi claim có evidence hai phía.
4. Bounded free-form Q&A: exact/structured trước, semantic recall tùy chọn, metadata filter,
   relation traversal và L3 grounding; ngoài dossier hoặc thiếu evidence thì safe state.
5. Evaluation/release: candidate corpus tách khỏi golden set; chỉ claim schema/citation/safety/
   regression cho đến khi có human-reviewed golden set.

**Fallback:** Option B cho một vertical slice nhỏ nếu cần demo field sớm, nhưng vẫn phải xây
`Fact`/citation/scope trước khi gọi đó là extraction đáng tin cậy. Không chọn C hoặc D làm đường
chính ở wave này.

## Open questions

- [ASSUMED] Hai profile nên làm vertical slice đầu là `SALES` và `SUPPLY_SERVICE` vì gần nhóm
  field giá/số lượng/phạm vi/phụ lục hiện có; cần xác nhận bằng corpus và reviewer trước khi
  khóa thứ tự profile.
- Cần chốt contract output cho `profile_type`, `profile_version`, `field_key`, `raw_value`,
  `normalized_value`, `source_scope`, `citation` và `review_state` trước khi cook phase 1.
- Cần chốt danh sách relation tối thiểu của wave đầu: `PARENT_OF`, `REFERENCES`, `AMENDS`,
  `PART_LINK`, `CONTEXT_GAP`; các relation suy luận sâu hơn có thể để backlog.
- Cần reconcile nguồn claim 95 case với manifest 65 records hiện có trước accuracy report.

## References

[1] https://json-schema.org/understanding-json-schema/reference/schema | JSON Schema official documentation | accessed 2026-09-23 | VERIFIED

[2] https://www.w3.org/TR/prov-overview/ | W3C PROV-Overview | accessed 2026-09-23 | VERIFIED

[3] https://airc.nist.gov/airmf-resources/airmf/5-sec-core/ | NIST AI RMF Core | accessed 2026-09-23 | VERIFIED

[4] https://genai.owasp.org/llmrisk/llm01-prompt-injection/ | OWASP LLM01:2025 Prompt Injection | accessed 2026-09-23 | VERIFIED

[5] https://genai.owasp.org/llmrisk/llm062025-excessive-agency/ | OWASP LLM06:2025 Excessive Agency | accessed 2026-09-23 | VERIFIED

