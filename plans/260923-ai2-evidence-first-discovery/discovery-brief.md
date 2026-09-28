# Discovery Brief — hướng hoàn thiện AI2

**Date:** 2026-09-23  
**Status:** finalized — direction recommendation, chưa phải implementation plan

---

## 1. Problem framing

AI2 cần biến snapshot AI1 thành một semantic dossier có cây cấu trúc contract/annex, facts,
field theo loại hợp đồng, relation, comparison và câu trả lời tự do có citation. Vấn đề chính
không phải thiếu một prompt tổng quát, mà là phải giữ đúng scope, provenance và trạng thái chưa
chắc chắn khi mở rộng qua nhiều loại hợp đồng. AI2 cần mở rộng dần nhưng không được đánh đổi
evidence integrity để tăng tỷ lệ trả lời.

**Root cause (if known):** scope hiện đã rộng hơn extraction engine đơn lẻ; profile, structure,
relation, comparison và Q&A cần dùng chung một semantic/evidence spine.

**Current impact:** nếu làm profile hoặc Q&A trước evidence spine, output có thể đúng hình thức
nhưng sai member/scope, không truy nguyên được hoặc suy diễn quan hệ contract–annex.

**Deadline / urgency:** hoàn thiện AI2 wave đầu; chưa có golden set nên phải ưu tiên safety,
schema, citation và regression trước business accuracy.

---

## 2. Hard constraints

| Constraint | Type | Notes |
|---|---|---|
| AI2-only | scope | Không mở rộng sang OCR, Backend, frontend hoặc production publish |
| Evidence-first | safety | Fact/relation/comparison/answer phải có citation hoặc safe state |
| Immutable source | data integrity | Không sửa raw AI1 snapshot; raw và normalized value tách nhau |
| Bounded query | security | Q&A chỉ đọc selected members trong tenant/dossier scope |
| No legal winner | policy | Không tự sinh precedence hoặc `LEGAL_WINNER` |
| Versioned profiles | extensibility | Core fields nhỏ; type-specific fields và annex extensions có version |
| Unverified corpus | evaluation | 95 case là candidate; manifest hiện có 65 records; chưa claim accuracy |

---

## 3. Evidence summary

**Research report:** `C:/Users/dungs/OneDrive/Documents/VSF/plans/reports/ai2-evidence-first-direction-research-260923.md`

**Brainstorm report:** `C:/Users/dungs/OneDrive/Documents/VSF/plans/reports/ai2-evidence-first-brainstorm-report.md`

Key findings:

- Hướng phù hợp nhất là **evidence-first semantic dossier + bounded query**.
- Phụ lục nên là member/scope trong dossier khi có evidence membership; không phải schema hợp
  đồng độc lập suy ra từ tên file hoặc `dossier_id`.
- Profile-first chỉ nên là kỹ thuật trong từng vertical slice; Q&A/RAG-first và universal
  ontology-first không phù hợp làm đường chính của wave đầu.
- Code hiện có đã có các điểm neo cho structure, comparison, relations, query routing, L0–L3
  và citation/review models; cần hoàn thiện theo một semantic spine thống nhất.
- NIST/JSON Schema/W3C PROV/OWASP đều củng cố các yêu cầu về versioning, provenance, validation,
  giới hạn vận hành và safe failure; chi tiết nằm trong research report.

---

## 4. Option space

| # | Approach | Pros | Cons | Complexity |
|---|---|---|---|---|
| A | Evidence-first semantic dossier, triển khai vertical slice | An toàn, truy nguyên, tái dùng cho mọi profile và Q&A | Q&A hoàn chỉnh xuất hiện sau evidence spine | medium/high |
| B | Profile-first extraction | Demo field theo loại nhanh | Dễ phình schema và sai scope/citation | medium |
| C | Q&A/RAG-first | Demo nhanh, dễ thấy UX | Scope leakage, citation yếu, prompt/tool risk | high/risky |
| D | Universal ontology/graph-first | Có tham vọng mở rộng dài hạn | Over-modeling khi chưa có corpus/golden | high |

---

## 5. Chosen direction + rationale

**Chosen direction:** Option A — Evidence-first semantic dossier + bounded free-form query.

**Why:**

1. Structure, citation, provenance và scope là nền dùng chung cho facts, relations, comparison
   và Q&A; làm một lần sẽ giảm việc mỗi profile tự giải quyết evidence theo cách khác nhau.
2. Hướng này cho phép phát hành safe state trước khi có golden set, phù hợp với điều kiện hiện
   tại của corpus.
3. Nó tận dụng được code hiện có thay vì thay toàn bộ pipeline bằng agent hoặc ontology mới.
4. Q&A được giữ read-only và bounded; câu trả lời là consumer của semantic dossier, không phải
   nguồn tạo truth.

**Accepted trade-off:**

- Chấp nhận Q&A ít “thông minh” hơn ở giai đoạn đầu để đổi lấy citation, scope và khả năng review.
- Chấp nhận triển khai profile theo từng vertical slice thay vì tuyên bố sáu profile hoàn thiện
  cùng lúc.

**Recommended product shape:**

```text
AI1 snapshot
  → boundary validation
  → dossier members + structure tree
  → citation/provenance gate
  → typed facts by profile
  → relation graph
  → comparison candidates
  → bounded free-form Q&A
  → safe state / review evidence
```

**Recommended expansion order:** foundation → semantic spine → 1–2 profile vertical slice →
profile expansion → annex extensions → release/evaluation.

**DEC recorded:** none — đây là direction recommendation; architecture decision sẽ được ghi khi
user xác nhận và chuyển sang `hs:plan`.

---

## 6. Open questions

> Các câu hỏi này không làm thay đổi direction; cần chốt trước hoặc trong planning.

- [ ] Vertical slice đầu có chốt `SALES` + `SUPPLY_SERVICE` không, hay chọn theo corpus thực tế
  sau khi reviewer xác nhận mapping của hai JSON đầu vào?
- [ ] Profile contract v1 sẽ có chính xác những core fields nào dùng chung cho cả sáu profile?
- [ ] Relation tối thiểu wave đầu có giới hạn ở `PARENT_OF`, `REFERENCES`, `AMENDS`, `PART_LINK`
  và `CONTEXT_GAP` không?
- [ ] Ai sẽ xác nhận một phần candidate corpus để tạo golden set, và nguồn 95 case nào là
  denominator chính thức?
- [ ] Q&A v1 chỉ trả câu trả lời có citation hay cho phép summary có điều kiện với trạng thái
  `NEEDS_REVIEW`?

---

## 7. Risks

| Risk | Likelihood | Impact | Mitigation |
|---|---|---|---|
| Profile sprawl | high | high | Versioned registry, core nhỏ, extension có owner/evidence |
| Relation contract–annex sai | medium | high | Member/scope bắt buộc; không suy từ tên file/dossier id |
| Citation không resolve | medium | high | Authoritative resolver; hạ review/safe state |
| Q&A vượt scope | medium | high | Query envelope pin tenant/dossier/member; read-only tools |
| Corpus candidate chứa expected sai | high | high | Tách candidate/golden; không claim accuracy |
| LLM/provider nondeterminism | medium | medium | Deterministic-first; LLM/vector optional, bounded và fail-closed |
| Làm quá nhiều loại cùng lúc | high | medium | Vertical slice 1–2 profile trước, mở rộng sau khi gate xanh |

---

## 8. Explicitly OUT of scope

- Xây chatbot tổng quát ngoài dossier hoặc agent có tool/file/URL tùy ý.
- Tự kết luận điều khoản nào có ưu tiên pháp lý hoặc bên nào “thắng”.
- Dựng universal ontology cho mọi loại hợp đồng trong wave đầu.
- Claim business accuracy khi chưa có golden set được reviewer xác nhận.
- Thay đổi AI1/OCR, Backend ACL/queue/lifecycle, frontend HITL hoặc production vector platform.
- Đưa toàn bộ sáu profile vào một vertical slice duy nhất.

---

## Handoff → hs:plan

Direction này đủ rõ để chuyển thành implementation plan sau khi người dùng xác nhận thứ tự
vertical slice và bộ core fields. Khi chuyển sang planning, dùng `/clear` trước để tách context,
sau đó chạy `hs:plan` với đường dẫn tuyệt đối của brief này.

