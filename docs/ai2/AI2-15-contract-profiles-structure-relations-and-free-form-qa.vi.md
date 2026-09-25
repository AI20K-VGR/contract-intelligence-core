# AI2-15 — Contract profiles, structure, relations và free-form Q&A

**Ngày:** 23/09/2026
**Trạng thái:** mục tiêu AI2 đã được người dùng phê duyệt; chưa phải claim đã hoàn tất
**Phạm vi:** AI2 sau handoff AI1; không mở rộng sang OCR, Backend hoặc frontend

## 1. Mục tiêu hiện tại

AI2 cần tổng quát hóa producer profile `ai1.snapshot.v1/ocr-lab` cho nhiều loại
hợp đồng cơ bản. Kết quả phải giúp người rà soát:

- xem cây cấu trúc đầy đủ của thân hợp đồng và phụ lục;
- lấy fact và field đặc thù theo loại hợp đồng;
- hiểu quan hệ giữa hợp đồng, phụ lục, điều khoản, bảng và tham chiếu;
- so sánh các field/điều khoản trong cùng hồ sơ;
- đặt câu hỏi tự do nhưng vẫn nhận câu trả lời có nguồn;
- phân biệt chắc chắn, thiếu chứng cứ và mâu thuẫn.

AI2 không phải hệ thống tự quyết hiệu lực pháp lý. `LEGAL_WINNER` và precedence
không được sinh tự động.

## 2. Phạm vi loại hợp đồng wave đầu

| Profile | Field/fact đặc thù cần hỗ trợ trước |
|---|---|
| `SALES` | hàng hóa, số lượng, đơn giá, tổng giá, VAT, giao hàng, nghiệm thu, bảo hành |
| `SUPPLY_SERVICE` | phạm vi cung cấp, thông số, SLA, milestone, nghiệm thu, thanh toán, bảo hành |
| `LEASE` | tài sản, thời hạn thuê, bàn giao, tiền thuê, đặt cọc, bảo trì, hoàn trả |
| `CONSTRUCTION_WORK` | phạm vi công việc, BOQ/khối lượng, tiến độ, nghiệm thu, phạt, bảo hành, phát sinh |
| `EMPLOYMENT` | vị trí, địa điểm, thời hạn, lương, phụ cấp, giờ làm, nghỉ, chấm dứt |
| `NDA` | thông tin mật, mục đích sử dụng, bên nhận, ngoại lệ, thời hạn bảo mật, hoàn trả/hủy |

Các phụ lục về giá, số lượng, kỹ thuật, tiến độ, SLA, thanh toán, nghiệm thu và
điều chỉnh là profile extension, không phải một loại hợp đồng độc lập.

Profile phải có version, alias, field key, type/normalization rule và trạng thái
evidence. Không ép một field không rõ loại vào profile sai. Type không xác định
phải giữ raw evidence và trả `UNMAPPED`/`NEEDS_REVIEW`.

## 3. Output AI2

### 3.1 Cây cấu trúc

Mỗi node phải giữ tối thiểu:

```text
node_id
type
raw_label
parent_id
order
page_range
source_file_id
scope_id
status
provenance
source_line_ids / citation
```

Cây phải phân biệt `BODY`, `ANNEX`, clause/section, field và table. Trùng số
điều ở hai scope không được merge. Điều không đánh số, nhảy số, thiếu parent,
table continuation và node partial phải được giữ như trạng thái nguồn hoặc issue;
AI2 không bịa node cho đẹp.

### 3.2 Fact và field

Fact gồm raw value, normalized value nếu có, subject/role, unit/currency,
condition, scope, validity, profile key, provenance, citation và review state.
Fact chỉ được coi là đã xác minh khi citation resolve được về page/node/line/table/
cell tương ứng.

### 3.3 Relation graph

Relation graph có thể chứa `PARENT_OF`, `SAME_CLAUSE`, `REFERENCES`, `AMENDS`,
`DEFINES`, `USES_DEFINED_TERM`, `PART_LINK` và `CONTEXT_GAP`. Mỗi edge phải có
source scope, evidence/citation và review state.

`ANNEX_OF` chỉ được tạo chắc chắn khi membership hoặc evidence trong cùng snapshot
đủ rõ. Không suy quan hệ từ tên file hoặc chỉ từ `dossier_id`.

## 4. So sánh và bất đồng

Comparison hỗ trợ ba scope:

- `WITHIN_DOCUMENT`: hai nguồn trong cùng hợp đồng/phụ lục;
- `CONTRACT_ANNEX`: thân hợp đồng với phụ lục;
- `ANNEX_ANNEX`: hai phụ lục trong cùng hồ sơ.

Candidate phải có hai phía evidence, cùng `item_key`/scope phù hợp và giữ condition,
unit, currency, validity. Khác scope/unit/currency trả `NOT_COMPARABLE`, không gọi
là conflict. Khác giá trị hoặc điều khoản trả candidate phù hợp và `NEEDS_REVIEW`.

Chỉ ghi nhận `CANDIDATE_AMENDMENT` khi văn bản có tín hiệu sửa/thay/bổ sung đủ rõ.
Nếu văn bản có điều khoản ưu tiên rõ ràng, AI2 trích xuất điều khoản đó; AI2 không
tự kết luận bên nào có hiệu lực cao hơn.

## 5. Free-form Q&A

Người dùng được đặt câu hỏi tự do về một hồ sơ hợp đồng. Mặc định query scope là:

```text
tenant → dossier → selected contract/annex members → bounded evidence → L3 grounding
```

Các câu hỏi quan hệ nhiều bước như “Phụ lục này thay đổi điều khoản nào của hợp
đồng?” được route qua structure/relation graph và comparison. Q&A không được mở
sang hồ sơ độc lập chỉ vì trùng `dossier_id`.

Mọi câu trả lời phải có citation/trace. Nếu không đủ source, relation hoặc context,
trả `INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW`; không dump toàn văn, không tự điền giá
trị còn thiếu và không biến câu hỏi tự do thành quyền gọi tool tùy ý.

## 6. Evaluation và accuracy

95 case hiện được coi là candidate corpus `UNVERIFIED`. Chúng có thể dùng để:

- kiểm tra không crash, schema, citation, scope, safe state và regression;
- tìm các nhóm lỗi cần bổ sung fixture;
- chọn mẫu đại diện để human review.

Chỉ case có reviewer evidence mới được promote thành golden set. Report phải tách:

```text
candidate corpus
reviewed golden set
unreviewed / missing / failed / not-run
accuracy claims
```

Khi chưa có golden set, chỉ được claim schema/citation/safety/regression; không
được claim accuracy nghiệp vụ.

## 7. Ranh giới implementation hiện tại

Đường code nền đã có:

- `app/pipeline/contract_context.py` cho parts/findings trong một source document;
- `app/pipeline/compare.py` cho candidate comparison và ba comparison scope;
- `app/reasoning/query.py` và `app/reasoning/stack.py` cho query routing và L0–L3;
- `app/reasoning/relations.py` cho relation-backed answer;
- `app/pipeline/outline.py` cho structure tree;
- `app/contracts/models.py` cho `Fact`, `Candidate`, `ContractContext`, citation và review state.

Các điểm trên là nền hiện có, không đồng nghĩa mọi profile và mọi free-form query
đã đạt acceptance. Việc hoàn thiện nằm trong plan:
`plans/260923-1023-ai2-completion-release/plan.md`.

## 8. Điều kiện không đạt

AI2 phải dừng ở safe state nếu:

- citation không resolve được;
- relation body–annex thiếu target hoặc thiếu evidence;
- field không đủ context để normalize;
- hai nguồn khác scope/unit/currency;
- câu hỏi yêu cầu dữ liệu ngoài dossier scope;
- provider/LLM/vector không khả dụng;
- corpus chưa được human review nhưng có người yêu cầu claim accuracy.
