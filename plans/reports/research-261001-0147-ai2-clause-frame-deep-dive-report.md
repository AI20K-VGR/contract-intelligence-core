# Research — AI2 clause frame: cơ sở lý thuyết, luật nền, thiết kế chi tiết, giao thức spike

Ngày: 2026-10-01 · Tiếp nối: `plans/reports/brainstorm-261001-0147-ai2-clause-frame-redirection-report.md` · Quyết định liên quan: DEC-dungskbg2004-1, DEC-dungskbg2004-2

Nhãn bằng chứng: **OBSERVED** (đã đọc nguồn/code), `[ASSUMED]` (chưa kiểm), `[PRIOR]` (kiến thức nền chưa kiểm lại).

---

## 1. Những gì nghiên cứu đã làm và rút ra

| # | Nguồn | Điều rút ra cho AI2 | Nhãn |
|---|---|---|---|
| 1 | Aires, Lima, Meneguzzi — *Identifying Potential Conflicts between Norms in Contracts* (COIN 2015) | Pipeline 3 bước giống hướng ta: nhận diện câu norm → tách bên → gán deontic (modal verb) → so **cặp cùng bên** bằng độ tương đồng ngữ nghĩa ngưỡng 0,7 (WordNet WUP). Nhận diện câu norm bằng luật modal verb: P 79% / R 98%. Không có số đo cho bước phát hiện conflict ("still creating a gold standard") | OBSERVED (đọc PDF) |
| 2 | Aires & Meneguzzi — Norm Conflict Dataset (2017, 2018) | Có typology conflict: *deontic-modality*, *deontic-structure*, *deontic-object*, *object-conditional* | OBSERVED (tóm tắt tìm kiếm) |
| 3 | OASIS LegalRuleML Core 1.0 | Có sẵn đúng các khái niệm ta cần: `PrescriptiveStatement` (nghĩa vụ/quyền/cấm), `PenaltyStatement`, `Reparation` (nối chế tài → nghĩa vụ bị vi phạm), `SuborderList` (chế tài bậc thang: phần tử sau áp dụng khi mọi phần tử trước bị vi phạm), `Override` (quan hệ ưu thế giữa 2 điều), `TemporalCharacteristic` (InForce / Efficacious / Applicable × Starts / Ends / Modifies) | OBSERVED (đọc spec) |
| 4 | *Better Call CLAUSE* (arXiv 2511.00340) | 7.500+ hợp đồng gây nhiễu từ CUAD/ContractNLI, 10 loại bất thường. LLM "often miss subtle errors and struggle even more to justify them legally" | OBSERVED (abstract) |
| 5 | *A Few Good Clauses* (arXiv 2605.05532) | Trích 26 field có chuẩn hóa + span nguyên văn. Mô hình tốt nhất macro F1 ≈ 0,81; **mọi mô hình yếu nhất ở field cần chuẩn hóa** (tiền, tần suất, gia hạn) | OBSERVED (tóm tắt HTML) |
| 6 | *Detecting Logical Relation in Contract Clauses* (arXiv 2111.01856) | Coi quan hệ giữa 2 điều là bài toán NLI (entailment/contradiction) | OBSERVED (abstract) |
| 7 | BLDS 2015 Điều 403, 404; LTM 2005 Điều 301, 307 | Xem mục 2 | OBSERVED (nguồn luật thứ cấp) |

### Kết luận từ nghiên cứu

1. **Hướng đi không mới về lý thuyết — đây là điểm tốt.** LegalRuleML đã chuẩn hóa đúng mô hình "nghĩa vụ → vi phạm → chế tài bậc thang → ưu thế → thời gian". AI2 nên **mượn từ vựng khái niệm** của LegalRuleML (không cần dùng XML của nó) để khỏi tự phát minh và để có tài liệu tham chiếu.
2. **Chỗ prior art yếu chính là chỗ ta định làm khác.** Aires et al. quyết cặp so sánh bằng ngưỡng similarity 0,7 — cách này gom nhầm "chậm giao hàng" với "chậm thanh toán". Thiết kế của ta (lexicon + enum, embedding chỉ đề xuất) đi đúng hướng khắc phục, nhưng **chưa được ai chứng minh trên tiếng Việt** → phải spike.
3. **Chuẩn hóa là nút cổ chai, kể cả với LLM mạnh nhất** (nguồn 5). Không nên kỳ vọng bước 4 (normalize) đạt 95% ngay; kiến trúc phải chịu được `UNMAPPED` nhiều ở vòng đầu.
4. **LLM tự do phát hiện conflict là yếu** (nguồn 4). Củng cố quyết định: LLM chỉ chép span + chọn enum; phát hiện conflict là tất định trên frame.

---

## 2. Luật nền ảnh hưởng tới thiết kế (không phải tính năng kiểm tra luật — DEC-dungskbg2004-1)

| Quy định | Nội dung | Hệ quả thiết kế |
|---|---|---|
| BLDS 2015 Điều 403 | Phụ lục có hiệu lực như hợp đồng. Điều khoản phụ lục **trái** hợp đồng thì **không có hiệu lực**, trừ khi có thỏa thuận khác; nếu các bên **chấp nhận** phụ lục có điều khoản trái thì **coi như điều khoản hợp đồng đã được sửa đổi** | Timeline không được mặc định "phụ lục sau thắng". Cần slot `acceptance_evidence` (chữ ký hai bên, câu "các bên thống nhất sửa đổi"). Thiếu bằng chứng chấp nhận → `CANDIDATE_AMENDMENT`, không vào timeline chính. Khẳng định lại DEC-1: luôn `NEEDS_REVIEW` |
| BLDS 2015 Điều 404 khoản 4 | Các điều khoản phải được giải thích trong mối liên hệ với nhau, phù hợp toàn bộ nội dung hợp đồng | Cơ sở để **không** gắn "conflict" cho các cặp có thể dung hòa (bậc thang, chung–riêng, ngoại lệ). Mặc định là "cần xem", không phải "mâu thuẫn" |
| LTM 2005 Điều 307 | Có thỏa thuận phạt vi phạm thì bên bị vi phạm được áp dụng **cả** phạt vi phạm **và** bồi thường thiệt hại | `PENALTY` + `DAMAGES` cùng key → `CUMULATIVE`, không phải conflict |
| LTM 2005 Điều 301 | Mức phạt không quá 8% giá trị phần nghĩa vụ bị vi phạm (trừ Điều 266) | Ngoài scope (DEC-1). Nhưng schema vẫn nên giữ `basis` của mức phạt ("% giá trị phần nghĩa vụ bị vi phạm" vs "% giá trị hợp đồng") vì hai frame khác `basis` là `NOT_COMPARABLE` |

---

## 3. Thiết kế chi tiết

### 3.1 Ánh xạ frame của AI2 ↔ LegalRuleML

| AI2 | LegalRuleML | Ghi chú |
|---|---|---|
| `OBLIGATION` / `RIGHT` / `PROHIBITION` | `PrescriptiveStatement` với Obligation / Permission / Prohibition | |
| `REMEDY` | `PenaltyStatement` | |
| cạnh `BREACHES` | `Reparation` | nối chế tài → nghĩa vụ |
| chuỗi `GRADUATED` | `SuborderList` | bậc thang chế tài |
| cạnh `EXCEPTION_OF` / `GENERAL_VS_SPECIFIC` | `Override` | AI2 chỉ ghi nhận **tín hiệu** ưu thế trong văn bản, không tự quyết |
| `AMENDS` + `effective_from` | `TemporalCharacteristic` (Modifies/Starts/Ends) | |
| `PARAMETER`, `DEFINITION` | ConstitutiveStatement / FactualStatement | |

### 3.2 Schema frame (bản đề xuất cho spike)

```json
{
  "frame_id": "fr_...",
  "frame_type": "REMEDY",
  "profile": "SALES@v1",
  "bearer":    {"norm": "SELLER", "span": "Bên Bán", "method": "PARTY_TABLE"},
  "action":    {"norm": "DELIVER", "span": "giao hàng", "method": "LEXICON|ENUM_LLM|UNMAPPED"},
  "qualifier": {"norm": "LATE", "span": "chậm", "method": "LEXICON"},
  "object":    {"norm": "item:A", "span": "hàng hóa A", "method": "ITEM_KEY"},
  "condition": [{"dim": "days_late", "op": "gt", "value": 15, "span": "quá 15 ngày"}],
  "consequence": {
    "type": "PENALTY_FIXED|PENALTY_RATE|INTEREST|DAMAGES|TERMINATION|SUSPENSION|WITHHOLD",
    "value": "10000000", "unit": "VND",
    "basis": null, "span": "phạt 10.000.000 đồng"
  },
  "breaches_ref": null,
  "exclusivity_cue": null,
  "validity": {"effective_from": "SIGNING", "effective_to": null},
  "source": {"node_id": "...", "scope": "BODY|ANNEX:2", "citation": {}},
  "review_state": "NEEDS_REVIEW"
}
```

Mỗi slot mang `span` + `method`: người review thấy ngay key được sinh bằng cách nào (lexicon tất định hay LLM chọn enum). `method` cũng là trục phân tích lỗi của spike.

### 3.3 Từ tín hiệu deontic tiếng Việt — bẫy riêng của tiếng Việt

| Tín hiệu | Frame thường gặp | Bẫy |
|---|---|---|
| "phải", "có nghĩa vụ", "có trách nhiệm", "cam kết", "bảo đảm" | `OBLIGATION` | "chịu trách nhiệm bồi thường" là `REMEDY`, không phải `OBLIGATION` |
| "có quyền", "được phép" | `RIGHT` | |
| **"được"** | `RIGHT` **hoặc bị động** | "Bên B **được** thanh toán trong 30 ngày" = bị động (nghĩa vụ của Bên A), **không** phải quyền của B → bearer đảo |
| "bị" | bị động, thường trong `REMEDY` | "bị phạt" → consequence; bearer là chủ ngữ |
| "không được", "cấm", "nghiêm cấm", "không có quyền" | `PROHIBITION` | "không được chậm hơn ngày X" = `OBLIGATION` có hạn, không phải cấm |
| "có thể" | mơ hồ (quyền / khả năng) | → enum LLM, không luật |
| "nếu / trường hợp / khi … thì" | `REMEDY` hoặc điều kiện của frame khác | cần mệnh đề hậu quả mới là `REMEDY` |

Prior art tiếng Anh (Aires et al.) chỉ cần 6 modal verb; tiếng Việt cần **cue + kiểm tra bị động**. Đây là lý do bước 2 phải có tầng enum LLM, không chỉ regex. `[ASSUMED]` tỉ lệ câu bị động "được/bị" trong hợp đồng VN đủ lớn để ảnh hưởng — spike đo.

### 3.4 Đại số điều kiện (condition algebra)

Mỗi `condition` là tập khoảng trên một **chiều** (`days_late`, `amount`, `percent`, `qty`, `date`). So 2 frame cùng key:

| Quan hệ khoảng | Ví dụ | Kết quả |
|---|---|---|
| `IDENTICAL` | >15 ngày vs >15 ngày | so consequence (bảng 3.5) |
| `DISJOINT` | ≤15 vs >15 | `GRADUATED` |
| `NESTED` | >15 vs >30 | `GRADUATED` (dạng SuborderList) nếu khác loại hậu quả; `COMPARABLE_DIFFERENCE` nếu cùng loại mà khác giá trị |
| `OVERLAP` | 10–20 vs 15–30 | xét consequence; vùng chồng có 2 hậu quả cùng loại khác giá trị → `CONFLICT_CANDIDATE` |
| `DIFFERENT_DIM` | >15 ngày vs >10% giá trị | `NOT_COMPARABLE` |
| `UNPARSED` | "chậm đáng kể", "trong thời gian hợp lý" | `NEEDS_REVIEW`, không so |

Tất định, không cần LLM. Tỷ lệ `UNPARSED` là chỉ số spike quan trọng.

### 3.5 Bảng quyết định conflict (cùng key, sau bước 3.4)

| Consequence trái | Consequence phải | Không có từ loại trừ | Có từ loại trừ ("chỉ", "duy nhất", "thay cho") |
|---|---|---|---|
| cùng loại, cùng giá trị | | `DUPLICATE` (không báo) | `DUPLICATE` |
| cùng loại, khác giá trị | | `COMPARABLE_DIFFERENCE` | `COMPARABLE_DIFFERENCE` |
| `PENALTY_*` | `DAMAGES` | `CUMULATIVE` (LTM Điều 307) | `CONFLICT_CANDIDATE` |
| `PENALTY_*` | `TERMINATION` | `GRADUATED`/`CUMULATIVE` | `CONFLICT_CANDIDATE` |
| khác `basis` (% phần vi phạm vs % hợp đồng) | | `NOT_COMPARABLE` | `NOT_COMPARABLE` |
| một frame là `ANY_BREACH` | frame cụ thể | `GENERAL_VS_SPECIFIC` | `GENERAL_VS_SPECIFIC` |

Mọi kết quả trừ `DUPLICATE` đều `NEEDS_REVIEW`. Không kết quả nào là kết luận pháp lý.

### 3.6 Thuật toán timeline phụ lục

Cho mỗi key `PARAMETER` (vd. `(—, PRICE, —, item:A)`):

1. Thu mọi frame cùng key từ `BODY` và `ANNEX:*`.
2. Với mỗi frame phụ lục, xác định:
   - `amend_signal`: có câu sửa/thay/bổ sung trỏ về điều cụ thể? (mở rộng `AMEND_RE` hiện tại — `ai-service/app/pipeline/compare.py:20`)
   - `target`: điều bị sửa đã resolve được trong cùng snapshot? (quy tắc `ANNEX_OF` của AI2-15 §3.3)
   - `effective_from`: ngày tuyệt đối / tương đối theo sự kiện ("kể từ ngày ký phụ lục") / không có
   - `acceptance_evidence`: chữ ký hai bên, câu "hai bên thống nhất" (BLDS Điều 403)
   - `partial_scope`: chỉ sửa cho item/khu vực/đợt nào
3. Dựng timeline:

| Tín hiệu | Vào timeline chính? | Trạng thái |
|---|---|---|
| `amend_signal` + `target` + `effective_from` + `acceptance_evidence` | Có | `PROPOSED_EFFECTIVE`, `NEEDS_REVIEW` |
| thiếu `acceptance_evidence` | Có, đánh dấu | `PROPOSED_EFFECTIVE_UNACCEPTED`, `NEEDS_REVIEW` |
| thiếu `effective_from` | Không (nhánh phụ) | `CANDIDATE_AMENDMENT` |
| không `amend_signal` | Không | `COMPARABLE_DIFFERENCE` (như hiện tại) |
| `effective_from` < ngày phụ lục | Có, cờ | `RETROACTIVE`, `NEEDS_REVIEW` |
| 2 phụ lục cùng khoảng hiệu lực, khác giá trị | Có, cờ | `OVERLAPPING_AMENDMENT` (đã có mutation trong `evals/golden/spec.py`) |

Chuỗi phụ lục (PL2 sửa PL1) xử lý bằng chính cạnh `AMENDS` giữa frame phụ lục với nhau.

---

## 4. Giao thức spike — sửa lại cỡ mẫu

Brainstorm trước đề xuất "~30 điều khoản, precision ≥ 95%". **Cỡ mẫu này không đủ để chứng minh ngưỡng đó:**

- Precision đo trên **quyết định gom cặp**, không trên số điều khoản.
- Nếu đúng hết n/n, cận dưới Wilson 95% ≈ n / (n + 3,84): n = 30 → **88,6%**; n = 60 → 94,0%; n = 75 → **95,1%** (DERIVED).
- Muốn khẳng định precision ≥ 95% với 1 lỗi cho phép cần n ≈ 120+ cặp `[ASSUMED — tính lại khi chốt]`.

### Đề xuất

| Hạng mục | Giá trị |
|---|---|
| Điều khoản | ~80 (`REMEDY` + `PARAMETER`), rải 6 profile, ≥ 30% từ hợp đồng thật ẩn danh |
| Cặp đánh giá precision | ≥ 120 cặp được hệ thống gom cùng key (cả paraphrase và near-miss) |
| Cặp đánh giá recall | ≥ 60 cặp paraphrase do người gán nhãn |
| Chỉ số phụ | slot accuracy theo `method`; tỷ lệ `UNMAPPED`; tỷ lệ `UNPARSED` condition; tỷ lệ lỗi bị động "được/bị"; số action/alias sau bootstrap |
| Báo cáo | `x/n` + Wilson CI (đúng D-A9 của plan A) |
| Cổng | cận dưới Wilson precision ≥ 95% → phương án 3; điểm ước lượng ≥ 95% nhưng cận dưới thấp hơn → mở rộng mẫu; < 90% → phương án 1 |

### Thứ tự spike (không đụng code production)

1. Gán nhãn tay 80 điều khoản theo schema 3.2 (người duyệt: Văn Dũng — D-A10).
2. Bước 3 (trích span) chạy trên toàn bộ → đo slot accuracy.
3. Bootstrap lexicon từ `action_text` (cluster embedding → duyệt).
4. Bước 4 (normalize) → đo precision/recall gom key.
5. Bước 3.4 + 3.5 trên các cặp → so với nhãn conflict typology.
6. Báo cáo + quyết định phương án (ghi DEC mới supersede một phần DEC-dungskbg2004-2).

---

## 5. Rủi ro mới phát hiện qua nghiên cứu

| Rủi ro | Mức | Giảm thiểu |
|---|---|---|
| "được" bị động đảo bearer → gom sai bên | Cao | enum LLM cho mọi câu chứa "được"; mutation golden riêng |
| Điều 403: timeline sai nếu coi phụ lục chưa được chấp nhận là hiệu lực | Cao | slot `acceptance_evidence`, trạng thái `UNACCEPTED` |
| Cỡ mẫu spike quá nhỏ → kết luận sai phương án | Cao | mục 4 |
| `basis` của mức phạt bị bỏ qua → so sánh sai | Trung bình | slot `basis`, `NOT_COMPARABLE` |
| Lexicon 6 profile phình to | Trung bình | đo ở bước bootstrap; lõi chung + mở rộng profile |
| Chuẩn hóa tiền/tỷ lệ vẫn là điểm yếu chung của mọi model | Trung bình | tái dùng `money_decimal` tất định; LLM không chuẩn hóa số |

## 6. Câu hỏi mở cho người dùng

1. Chấp nhận nâng cỡ spike lên ~80 điều khoản / ≥ 120 cặp?
2. Có muốn giữ tên khái niệm theo LegalRuleML trong docs AI2 (dễ tra cứu) hay giữ tên Việt hóa?
3. `acceptance_evidence` lấy từ đâu — AI1 có trả vùng chữ ký/đóng dấu không?

## Nguồn

- [Identifying Potential Conflicts between Norms in Contracts (Aires, Lima, Meneguzzi)](https://www.meneguzzi.eu/felipe/pubs/coin-nlp-norm-conflicts-2015.pdf)
- [Norm conflict identification in contracts (2017)](https://www.researchgate.net/publication/319274102_Norm_conflict_identification_in_contracts)
- [Norm Conflict Identification using Vector Space Offsets](https://www.meneguzzi.eu/felipe/pubs/ijcnn-contract-conflicts-2018.pdf)
- [LegalRuleML Core Specification 1.0](https://docs.oasis-open.org/legalruleml/legalruleml-core-spec/v1.0/legalruleml-core-spec-v1.0.html)
- [Better Call CLAUSE (arXiv 2511.00340)](https://arxiv.org/abs/2511.00340)
- [A Few Good Clauses (arXiv 2605.05532)](https://arxiv.org/html/2605.05532v1)
- [Detecting Logical Relation In Contract Clauses (arXiv 2111.01856)](https://arxiv.org/pdf/2111.01856)
- [Điều 301 LTM 2005 — Thư viện Pháp luật](https://thuvienphapluat.vn/cong-dong-dan-luat/cach-hieu-dieu-301-luat-thuong-mai-190327.html)
- [Mức phạt vi phạm và quan hệ với chế tài khác — Thái Sơn](https://thaison.vn/tin-tuc/muc-phat-vi-pham-hop-dong-thuong-mai-va-moi-quan-he-voi-cac-che-tai-khac)
- [Phụ lục hợp đồng (BLDS Điều 403) — Thái Sơn](https://thaison.vn/tin-tuc/phu-luc-hop-dong-la-gi)
- [Điều 404 BLDS 2015](https://hethongphapluat.com/bo-luat-dan-su-2015/dieu-404)
