# AI2-16 — Clause key graph (AI2 v2): cơ chế, quyết định, bằng chứng và lộ trình

**Trạng thái:** ĐỀ XUẤT — chưa triển khai vào `ai-service`. Đã có spike đo được (`evals/spikes/clause_key/`), đã qua critique 5 góc nhìn (verdict **BLOCKED**, advisory).
**Ngày:** 2026-10-01
**Quyết định ràng buộc:** DEC-dungskbg2004-1, DEC-dungskbg2004-3, DEC-dungskbg2004-4, DEC-dungskbg2004-5 (`docs/decisions.md`)
**Đọc trước:** [AI2-15](AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md) (profile, cây cấu trúc, relation graph), [AI2-01](AI2-01-business-policy-perspective.vi.md) (tenant, dữ liệu), [AI2-10](AI2-10-current-flow.vi.md) (luồng hiện tại).

Nhãn bằng chứng: **OBSERVED** (đã đo/đọc), `[ASSUMED]` (chưa kiểm).

---

## 1. Bài toán

Người rà hồ sơ hợp đồng (thân + phụ lục) cần thấy **các điều khoản nói về cùng một việc nhưng khác nhau** — giá thay đổi qua phụ lục, hai mức phạt cho cùng một vi phạm, điều khoản chung và riêng — kèm trích dẫn hai phía. AI2 v1 chỉ ghép theo `item_key` sinh từ ký hiệu (`pipeline/fact.py:31,53`, `pipeline/table.py:168`) và so điều khoản bằng trùng token (`pipeline/clause_compare.py:297`), nên "giao hàng chậm" (Điều 9) và "chậm trễ bàn giao" (Điều 12) không bao giờ gặp nhau.

**Ý tưởng v2:** tách mỗi điều/khoản thành **frame** có cấu trúc → chuẩn hóa thành **key** → các frame cùng key (hoặc có quan hệ cấu trúc) thành **cặp ứng viên** → **code tất định** phân loại khác biệt.

**Không làm (non-goals):**
- Không kết luận hiệu lực pháp lý, không chọn bên thắng (AI2-15 §1, DEC-dungskbg2004-1).
- Không kiểm điều khoản so với luật (vd trần phạt 8% LTM 301) — DEC-dungskbg2004-1.
- Không dùng dữ liệu tenant này để cải thiện cho tenant khác khi chưa opt-in (AI2-01:102).

## 2. Nguyên tắc (giữ nguyên qua mọi phiên bản)

1. **LLM chỉ chép nguyên văn và chọn trong danh sách đóng.** Không để LLM tự đặt key hoặc tự viết định nghĩa làm căn cứ.
2. **Code tạo key và so sánh** — tất định, tái lập được, pin theo version.
3. **Không chắc thì không gom** — nhưng vẫn **hiển thị** (không biến thiếu thành không rủi ro).
4. **Mọi kết quả NEEDS_REVIEW**, mọi kết quả có trích dẫn hai phía.
5. **Đo trên hồ sơ thật**, không trên cặp gộp từ các hợp đồng không liên quan (DEC-dungskbg2004-3).

## 3. Mô hình dữ liệu

### 3.1 Frame

| Loại | Ý nghĩa | Ô (span nguyên văn) |
|---|---|---|
| `REMEDY` | vi phạm → hậu quả | `bearer_text`, `action_text`, `qualifier_text`, `condition_text`, `consequence_text`, `scope_text` |
| `PARAMETER` | một đại lượng có giá trị | `param_text`, `object_text`, `value_text`, `effective_from` |
| (vòng sau) `OBLIGATION`, `RIGHT`, `PROHIBITION`, `DEFINITION` | — | — |

Mỗi frame mang: span gốc, citation (node/page/bbox của AI1), `layer` (bậc chuẩn hóa nào quyết định), `method` (`LEXICON` / `ENUM_LLM` / `TENANT_ALIAS` / …), `frame_class` (§3.4).

Ánh xạ khái niệm sang LegalRuleML (chuẩn OASIS): `REMEDY` ≈ `PenaltyStatement` + `Reparation`; bậc thang ≈ `SuborderList`; chung–riêng ≈ `Override`; timeline ≈ `TemporalCharacteristic`.

### 3.2 Key

| Loại frame | Key | Ví dụ |
|---|---|---|
| `REMEDY` | `(bearer, action, qualifier)` | `(SELLER, DELIVER, LATE)` |
| `PARAMETER` | `("PARAM", param, object)` | `("PARAM", PRICE, "máy m1")` |

- `bearer`: vai trò (`SELLER`, `BUYER`, `SUPPLIER`, `CUSTOMER`, `LESSOR`, `LESSEE`, `CONTRACTOR`, `OWNER`, `EMPLOYER`, `EMPLOYEE`, `DISCLOSER`, `RECIPIENT`, `ANY_PARTY`).
- `action`: tập đóng theo lexicon (hiện 12: `DELIVER`, `PAY`, `ACCEPT`, `WARRANT`, `HANDOVER_ASSET`, `RETURN_ASSET`, `COMPLETE_WORK`, `PROVIDE_SERVICE`, `DISCLOSE`, `WORK`, `TERMINATE_EARLY`, `ANY_OBLIGATION`).
- `qualifier`: `LATE`, `NOT_PERFORMED`, `DEFECTIVE`, `WRONG_QTY`, `UNAUTHORIZED`, hoặc trống; `?` = back-off.
- **Phạm vi KHÔNG nằm trong key** — là thuộc tính so sánh (DEC-dungskbg2004-4, §6.2).

### 3.3 Điều kiện và hậu quả

- **Điều kiện** → khoảng đóng trên đơn vị nguyên: "quá 15 ngày" ≡ "từ 16 ngày trở lên" → `[16, ∞)`. Chiều: `days`, `hours`, `months`; cần tách `working_days` (lỗi C-05).
- **Hậu quả** → `type` (`PENALTY_FIXED`, `PENALTY_RATE`, `INTEREST`, `DAMAGES`, `TERMINATION`, `SUSPENSION`, `WITHHOLD`), `value`, `unit`, `base` (`VIOLATED_PART` / `CONTRACT_VALUE` / `OTHER`), `period` (`PER_DAY`/`WEEK`/`MONTH`/`YEAR`). `PENALTY_FIXED` và `PENALTY_RATE` cùng **họ phạt**.

### 3.4 Ba lớp frame sau chuẩn hóa

| Lớp | Nghĩa | Được gom theo key? | Được so theo cấu trúc? |
|---|---|---|---|
| `DEFINITE` | key chắc chắn | Có | Có |
| `BACKOFF` | key có `?` hoặc bên `UNRESOLVED` | **Không** | Có |
| `UNMAPPED` | không ra hành vi | Không | Có |

Coverage luôn báo **ba lớp riêng** (không tính `?` là "đã map").

## 4. Luồng v2 (A → G)

```
Hồ sơ (thân + phụ lục, snapshot AI1)
 A. Ngữ cảnh hồ sơ   cây Điều/khoản, bảng các bên, profile, mục định nghĩa, cạnh REFERENCES/AMENDS
 B. Trích frame      LLM chép span (theo khoản, kèm tiêu đề Điều cha) → kiểm nguyên văn → tách hậu quả kép
 C. Chuẩn hóa → key  thang bậc (§5) → frame_class DEFINITE | BACKOFF | UNMAPPED
 D. Cặp ứng viên     TRONG HỒ SƠ: cùng key · tham chiếu/AMENDS · khoản anh em cùng Điều
 E. So sánh          decide() (§6) + timeline PARAMETER (DEC-dungskbg2004-1)
 F. Hiển thị         cần xem / đã phân loại / chưa so được + dòng độ phủ
 G. Vòng lexicon     LLM đề xuất → kiểm tự động → biên tập tenant duyệt → tenant_profile_version (§8)
```

Key graph là **lõi** (DEC-dungskbg2004-3) nhưng **không phải nguồn cặp duy nhất**: cấu trúc hồ sơ bắt rẻ và chắc phần lớn cặp có giá trị (spike: "cùng Điều" bắt 12/15 cặp cùng hợp đồng trên held-out 1, key graph v1 bắt 1/15); key graph lo cặp **khác Điều, khác cách viết**.

Pin version bổ sung vào bộ pin của AI2-01 §2: `extraction_prompt_version`, `lexicon_version` (toàn cục), `tenant_profile_version` (chứa lớp alias tenant), `llm_model`.

## 5. Thang chuẩn hóa

### 5.1 Hành vi (action)

| Bậc | Tên | Quy tắc |
|---|---|---|
| 1 | Tra đúng | cả cụm khớp alias |
| 2 | Từ lõi | bỏ stopword; alias dài nhất chứa trong cụm; ưu tiên: alias theo profile → hành vi cụ thể → hành vi chung (`generic`) → mẫu regex chung |
| 3 | Tham chiếu | "tại Điều 5 / khoản 3.2" → mượn hành vi của điều được trỏ; thắng `ANY_OBLIGATION` |
| 4 | Định nghĩa | thuật ngữ trong mục "Giải thích từ ngữ" → chuẩn hóa định nghĩa |
| 2' | Quét câu | **chỉ** khi ô action trống hoặc chứa hậu quả, **chỉ trong vế của chính frame** (sửa C-02) |
| 5 | LLM chọn enum | gửi cụm + danh sách hành vi có định nghĩa (bỏ `ANY_OBLIGATION`); 2 phiếu, chỉ nhận khi trùng và thuộc danh sách; `NONE` → bậc 7 |
| 6' | Mặc định profile | ô action trống hoặc chỉ "vi phạm" → hành vi mặc định của profile (vd NDA → `DISCLOSE`) |
| 7 | `UNMAPPED` | lưu, hiển thị, so theo cấu trúc; vào vòng lexicon |

LLM **không bao giờ tự sinh key** — key tự sinh không nhất quán giữa các khoản ("CHẬM_GIAO_HÀNG" vs "GIAO_HÀNG_TRỄ_HẠN"), không tất định, không đo được. Khả năng sinh của LLM chỉ dùng để **đề xuất** vào vòng lexicon (§8).

### 5.2 Bên (bearer)

1. Bảng các bên của hồ sơ ("Bên B" → `SELLER`).
2. Alias vai trò chung.
3. Lật bên **chỉ khi** "X (không) được + tác nhân + hành vi" (bị động); câu cấm "không được làm X" **không** lật (sửa C-02).
4. Câu không nêu bên nào → bên mặc định theo profile × hành vi (xây dựng: `COMPLETE_WORK` → `CONTRACTOR`).
5. Có tên nhưng không nhận ra → `UNRESOLVED` (lớp `BACKOFF`), **không** mặc định (sửa C-02).
6. "bên vi phạm", "mỗi bên" → `ANY_PARTY`.

### 5.3 Cách vi phạm (qualifier)

Thứ tự: ô chứa số → chuyển sang điều kiện · ô chỉ "không" → `NOT_PERFORMED` · mẫu phủ định ("không … đúng hạn", "quá hạn") → `LATE` · alias trong ô qualifier → ô action → vế của frame · qualifier mặc định của hành vi (`DISCLOSE` → `UNAUTHORIZED`) · có chữ mà không nhận ra → `?` (**back-off thắng quét câu**, sửa C-02).

### 5.4 Tham số (PARAMETER)

Tra đúng → bỏ stopword → chứa alias (chặn từ ghép: "giá" ≠ "giá trị") → khớp tập từ **chỉ khi đầu tố alias không bị danh từ lạ bổ nghĩa** ("giá trị **bảo lãnh** … hợp đồng" ≠ giá trị hợp đồng) → ghép `param + object` **chỉ khi** ô param là danh từ trần (≤ 2 âm tiết). Object "hợp đồng" → trống.

## 6. So sánh

### 6.1 Nguồn cặp (bước D)

Chỉ trong một hồ sơ. Ba nguồn, gắn nhãn nguồn vào cặp để đo đóng góp:
1. `SAME_KEY` — cùng key `DEFINITE`.
2. `EXPLICIT_REF` — cạnh REFERENCES/AMENDS ("Sửa đổi khoản 9.1").
3. `SAME_ARTICLE` — khoản anh em trong cùng Điều (bắt cả `BACKOFF`/`UNMAPPED`).

### 6.2 `decide()` — thứ tự quy tắc

| # | Điều kiện | Kết quả |
|---|---|---|
| 1 | Một key là `ANY_OBLIGATION`, cùng bên (hoặc `ANY_PARTY`) | `GENERAL_VS_SPECIFIC` |
| 2 | Có `?`/`UNRESOLVED`, cùng (bên, hành vi) | `NEEDS_REVIEW_BACKOFF` |
| 3 | Hai phạm vi chắc chắn và khác | `SCOPE_DIFFERS` (hiển thị, không so giá trị) — DEC-dungskbg2004-4 |
| 4 | Một bên có phạm vi, bên kia không | `GENERAL_VS_SPECIFIC` |
| 5 | Điều kiện không đọc được | `NEEDS_REVIEW_UNPARSED` |
| 6 | Điều kiện khác chiều (ngày vs giờ) | `NOT_COMPARABLE` |
| 7 | Cùng loại hậu quả, `base` khác (cả hai có) | `NOT_COMPARABLE` |
| 8 | Cùng loại, điều kiện tách rời | `GRADUATED` |
| 9 | Cùng loại, **mọi trường type/value/unit/base/period có giá trị và bằng nhau**, điều kiện trùng | `DUPLICATE` (sửa C-01: `None == None` **không** là trùng) |
| 10 | Cùng loại, còn lại | `COMPARABLE_DIFFERENCE` |
| 11 | Cùng họ phạt (cố định vs %) | tách rời → `GRADUATED`; còn lại → `COMPARABLE_DIFFERENCE` |
| 12 | Khác loại, có từ loại trừ **trong vế hậu quả** ("chỉ được", "duy nhất", "thay cho") | `CONFLICT_CANDIDATE` (sửa C-24) |
| 13 | Khác loại, cả hai thuộc nhóm cộng được (phạt, bồi thường, lãi) | `CUMULATIVE` (LTM 307) |
| 14 | Khác loại khác | lồng/tách rời → `GRADUATED`; còn lại → `CUMULATIVE` |
| — | Giá trị hoặc phạm vi không chắc ở bất kỳ bước nào | **không bao giờ** `DUPLICATE` → `NEEDS_REVIEW_UNPARSED` |

### 6.3 Timeline tham số (DEC-dungskbg2004-1)

PARAMETER cùng key + cạnh `AMENDS` + `effective_from` + bằng chứng chấp nhận (chữ ký hai bên — BLDS 2015 Điều 403) → `PROPOSED_EFFECTIVE` (luôn NEEDS_REVIEW). Thiếu bằng chứng chấp nhận → `PROPOSED_EFFECTIVE_UNACCEPTED`; thiếu `effective_from` → `CANDIDATE_AMENDMENT`; hồi tố / hai phụ lục chồng khoảng → cờ riêng.

## 7. Hiển thị (bước F)

```
Hồ sơ … — đã so X/Y frame · Z chưa so được (vẫn so theo cấu trúc)

⚠ CẦN XEM        COMPARABLE_DIFFERENCE, CANDIDATE_AMENDMENT, CONFLICT_CANDIDATE, timeline,
                  SCOPE_DIFFERS, GENERAL_VS_SPECIFIC, NEEDS_REVIEW_*
ℹ ĐÃ PHÂN LOẠI   GRADUATED, CUMULATIVE, DUPLICATE (bấm để xem — không ẩn)
○ CHƯA SO ĐƯỢC   frame UNMAPPED/BACKOFF không có cặp nào
```

Không bao giờ hiển thị "không có mâu thuẫn" khi còn frame chưa map. Mỗi dòng mở ra hai trích dẫn (trang/bbox AI1).

## 8. Vòng lexicon (DEC-dungskbg2004-5, G3)

### 8.1 Hai vòng tách biệt

| Vòng | Ai | Thay đổi gì | Kiểm soát |
|---|---|---|---|
| Mechanism / lexicon toàn cục | Dev | luật, cấu trúc, alias toàn cục | cổng DEC-dungskbg2004-3 trên held-out mới |
| Alias tenant | LLM đề xuất, **biên tập lexicon tenant** duyệt | alias trong `tenant_profile_version` | kiểm tự động + duyệt + đo theo nguồn |

### 8.2 Luồng alias tenant

```
frame UNMAPPED/BACKOFF → (bậc 5 trả NONE) → LLM đề xuất alias (chọn hành vi có sẵn) hoặc hành vi mới + định nghĩa + câu nguồn
 → kiểm tự động: không va chạm alias khác, không thuộc stoplist ("thực hiện", "giao", …), ≥ 2 âm tiết
 → hỏi người dùng (§8.3) → duyệt → tenant_profile_version mới → chạy lại tạo run mới, giữ kết quả cũ (AI2-01:38)
 → key từ alias tenant mang method=TENANT_ALIAS; theo dõi tỷ lệ key sai theo alias; vượt ngưỡng → thu hồi
 → đưa lên toàn cục chỉ khi tenant opt-in, chỉ chuỗi alias, không văn bản hợp đồng (AI2-01:102, BR-A10)
```

Một lần sửa của người dùng **không tự đổi rule** (AI2-DOC-02-brd:78) — mọi alias qua bước duyệt có version.

### 8.3 Thiết kế cho người dùng thật `[ASSUMED]` — cần thử trước khi xây

- **Hỏi bằng nghiệp vụ, không bằng thuật ngữ**: "Hai điều khoản này có nói về CÙNG MỘT VIỆC không?" + hai câu thật cạnh nhau; nút *Cùng một việc / Khác nhau / Không chắc*.
- **Xem trước tác động**: số điều khoản/hồ sơ bị ảnh hưởng; phạm vi mặc định **"chỉ hồ sơ này"**, "toàn tổ chức" phải chọn chủ động; hoàn tác được.
- **Lồng vào lúc rà**, tối đa 1–2 câu mỗi hồ sơ, ưu tiên cụm lặp nhiều; không có trang "hàng đợi lexicon" riêng.
- **Bỏ qua là an toàn**: không trả lời → không đổi gì, frame vẫn so theo cấu trúc.
- **Chống duyệt cho có**: 2 người cho phạm vi toàn tổ chức hoặc tác động lớn; đo thời gian/quyết định và tỷ lệ thu hồi theo người duyệt; lấy mẫu kiểm tra hằng tuần; cặp bẫy khi thử nghiệm.
- **Dự phòng G1**: hệ thống chạy đủ khi không ai tham gia (dev xử lý thống kê UNMAPPED theo chu kỳ; recall tĩnh).

**Điều kiện lùi về G1 (đề xuất, chưa ghi DEC):** thử với 3–5 người rà thật; nếu họ không hiểu câu hỏi, tỷ lệ trả lời thấp, hoặc đồng ý cặp bẫy → bỏ UI duyệt tenant, giữ G1.

## 9. Đánh giá

### 9.1 Cổng (DEC-dungskbg2004-3)

Đo trên **hồ sơ thật ẩn danh (thân + phụ lục)**, cặp **trong hồ sơ**:

| Chỉ số | Ngưỡng |
|---|---|
| False `DUPLICATE` | **= 0** |
| Tỷ lệ key `DEFINITE` sai | ≤ ngưỡng (chưa chốt) |
| Recall cặp trong hồ sơ | báo theo nguồn cặp (`SAME_KEY` / `EXPLICIT_REF` / `SAME_ARTICLE`) và theo lớp vị trí |
| Precision theo disposition | báo riêng từng nhãn của §6.2 |
| Cỡ mẫu | ≥ 120 cặp |

### 9.2 Cách đo (rút kinh nghiệm từ critique)

- Ghép frame dự đoán ↔ gold **1-1** (Hungarian theo độ trùng từ); frame dự đoán thừa vẫn được chấm.
- Tách cặp theo vị trí: cùng câu / cùng Điều / tham chiếu tường minh / chỉ khác cách viết (`PARAPHRASE_ONLY`) / khác hồ sơ (bỏ).
- Coverage ba lớp; báo `accuracy_when_mapped` riêng với `key_accuracy`.
- Khoảng tin cậy **bootstrap theo khoản/hồ sơ** (cặp không độc lập — Wilson trên cặp quá lạc quan).
- Chạy lặp ≥ 3 lần cùng cấu hình để có dải nhiễu LLM; chỉ so trong cùng model (đổi model lệch ~9 điểm key).

### 9.3 Quy trình dữ liệu

- **Khóa held-out trước khi bắt đầu phát triển**, commit nhãn + mã băm; một held-out chỉ dùng một lần.
- **Người thứ hai gán nhãn mù**, đo đồng thuận (IAA); ghi quy ước nhãn vào hướng dẫn (`plans/reports/guide-261001-0147-ai2-clause-key-heldout-labeling-report.md`).
- Khử trùng lặp dev/test theo n-gram (mẫu công khai chép nhau).
- Nhãn gold cho phép object/nghĩa vụ tự do — không bó theo enum lexicon (tránh che lỗi key quá thô).
- Kết quả JSON ghi model id + mã băm code/prompt/lexicon.

## 10. Bằng chứng spike (OBSERVED)

| Vòng | Dữ liệu | Model | Key đúng | Pair precision | Pair recall |
|---|---|---|---|---|---|
| v0 rules | test giả lập 60 | — | 70,0% | 91,2% | 35,6% |
| v1 llm-full | test giả lập 60 | gh/gpt-4o | 83,3% | 100% (70/70) | 80,5% |
| v1 llm-full | held-out 1 thật (36 khoản/44 frame) | gh/gpt-4o | 43,2% | 100% (13/13) | 25,5% |
| v1 llm-full | held-out 2 thật (22/31) | claude-sonnet-4-6 | 45,2% | 93,8% | 51,7% |
| v2 llm-full | held-out 2 thật | claude-sonnet-4-6 | 51,6% | 94,1% (16/17) | 55,2% |

Đọc lại theo critique (independent-revalidator, brainstormer):
- Recall trên là **cặp gộp toàn tập** (đa số cặp khác hợp đồng). Recall **trong hồ sơ, khác khoản**: **2/16 = 12,5%** [3,5; 36,0].
- `accuracy_when_mapped` held-out 1 (gpt-4o) = **15/19**, không phải 19/19.
- Lexicon v2 đóng góp ròng **0 / −1** frame trên held-out 2; cải thiện trên dev không chuyển sang dữ liệu mới.
- 5/19 key `DEFINITE` sai trên held-out 2 v2; gộp held-out 1+2: 3 false merge.
- Không có frame `PARAMETER` nào trên dữ liệu thật (75/75 là `REMEDY`).
- Bài học chung: dữ liệu giả lập do cùng một tác giả viết thổi phồng mạnh; đuôi dài trên dữ liệu thật không hội tụ chỉ bằng thêm alias/luật.

## 11. Việc tồn đọng đã biết (từ critique)

| ID | Mức | Việc | Trạng thái |
|---|---|---|---|
| C-01 | blocker | `DUPLICATE` khi giá trị `None`; `_MONEY` thiếu `đ`/`usd`; PARAMETER chưa so `value_text` | mở |
| C-02 | blocker | 4 đường biến "không chắc" thành key xác định (§5.1 2', §5.2, §5.3) | mở |
| C-03 | blocker | Chấm điểm theo hồ sơ, theo vị trí cặp | mở |
| C-04 | blocker | Đo PARAMETER + timeline trên hồ sơ thật | mở |
| C-05 | major | `ngày làm việc` ≠ `ngày`; "trong vòng N" sai chiều | mở |
| C-06 | major | Đo precision theo disposition trên dữ liệu thật | mở |
| C-07 | major | Ghép 1-1, chấm frame thừa, bootstrap, n ≥ 120 | mở |
| C-08 | major | Coverage 3 lớp; `?` vào luồng; dòng độ phủ | mở |
| C-10 | major | Phạm vi trong `decide()` | quyết định: DEC-dungskbg2004-4 |
| C-13 | major | Người gán nhãn thứ hai, IAA | mở |
| C-14 | major | Bằng chứng người dùng (3–5 hồ sơ thật, thời gian rà hiện tại) | mở |
| C-16/17 | major | Bake-off key graph vs LLM trọng tài theo cặp (PA-A) vs LLM trần; đo tỷ lệ `PARAPHRASE_ONLY` | mở |
| C-19 | minor | Span không phải chuỗi gây crash; "10.5 triệu"; `by_clause` chỉ giữ frame cuối | mở |
| C-24 | minor | Từ loại trừ chỉ xét trong vế hậu quả | mở |
| C-25 | minor | Tách hậu quả theo dấu phẩy; "hoặc" = quan hệ thay thế | mở |

Danh sách đầy đủ (C-01…C-25, fingerprint): `plans/reports/ai2-clause-key-critique-report.md`.

## 12. Lộ trình đề xuất

| Giai đoạn | Nội dung | Điều kiện qua |
|---|---|---|
| **P0 — Sửa spike** | C-01, C-02, C-05, C-24, C-25, C-19; bộ chấm mới (§9.2); replay trên span đã lưu (không gọi LLM) | test pass; tỷ lệ key `DEFINITE` sai giảm; false `DUPLICATE` = 0 trên dữ liệu đã có |
| **P1 — Luồng hồ sơ trong spike** | bước A (ngữ cảnh), D (3 nguồn cặp), §6.2 phạm vi, PARAMETER + timeline | chạy được trên fixture `HD-TONG-HOP`, `AI2-TEST-MASTER` |
| **P2 — Dữ liệu thật** | 3–5 hồ sơ thật (thân + phụ lục), nhãn cặp theo vị trí, người gán nhãn thứ hai; thử UI duyệt §8.3 bằng mockup | đạt cổng DEC-dungskbg2004-3; đo tỷ lệ `PARAPHRASE_ONLY` |
| **P3 — Quyết định kiến trúc cuối** | nếu `PARAPHRASE_ONLY` đáng kể: `/hs:bakeoff` key graph vs PA-A vs LLM trần | số liệu, không lập luận |
| **P4 — Tích hợp** | viết lại plan B/C (`/hs:plan`): schema `ai2` (frames, keys, pairs, timelines, lexicon, tenant alias), API version mới, UI hàng đợi + độ phủ | plan được duyệt |

## 13. Câu hỏi mở

1. Ngưỡng "tỷ lệ key `DEFINITE` sai" cho cổng.
2. Ai giữ vai trò **biên tập lexicon tenant** (vision chưa có vai trò này); ngưỡng thu hồi alias; điều khoản opt-in (pháp chế).
3. Có ghi điều kiện **lùi G3 → G1** vào DEC-dungskbg2004-5 không (§8.3).
4. Profile ưu tiên cho thí điểm (critique: làm sâu 1–2 profile trước thay vì dàn 6).
5. Baseline đối đầu: LLM trần "so hai điều khoản" có đạt "không gom sai" ở cùng mức bỏ trống không (C-16).
6. Chi phí và độ trễ ở quy mô một hồ sơ (số lần gọi LLM/khoản); xử lý OCR nhiễu và câu nhiều mệnh đề.

## 14. Quyết định liên quan

| DEC | Nội dung |
|---|---|
| DEC-dungskbg2004-1 | Timeline phụ lục chỉ để review; không kiểm trần luật |
| DEC-dungskbg2004-2 | *(đã bị thay)* hướng clause frame, cổng 95/80 trên cặp gộp |
| DEC-dungskbg2004-3 | Key graph là lõi; cổng đo theo hồ sơ; sửa C-01/C-02 trước khi viết lại B/C |
| DEC-dungskbg2004-4 | Phạm vi là thuộc tính so sánh, không trong key |
| DEC-dungskbg2004-5 | Lexicon G3: LLM đề xuất, biên tập tenant duyệt, version theo tenant, opt-in mới dùng chéo |

## 15. Artefact tham chiếu

| Loại | Đường dẫn |
|---|---|
| Code spike | `evals/spikes/clause_key/mechanism.py`, `run_spike.py`, `import_heldout.py`, `build_heldout*.py` |
| Lexicon | `evals/spikes/clause_key/lexicon_v0.json`, `lexicon_v1.json`, `lexicon_v2.json` |
| Dữ liệu | `clauses_dev.jsonl`, `clauses_test.jsonl` (giả lập); `heldout.csv`, `heldout2.csv` + `*_sources.json` (mẫu công khai, đã bị nhìn — chỉ dùng làm dev) |
| Kết quả + freeze | `evals/spikes/clause_key/results/` (`*.sha256`, `claude-sonnet-4-6/`) |
| Test | `evals/tests/test_clause_key_spike.py`, `evals/tests/test_clause_key_heldout_import.py` |
| Brainstorm / nghiên cứu | `plans/reports/brainstorm-261001-0147-ai2-clause-frame-redirection-report.md`, `research-261001-0147-ai2-clause-frame-deep-dive-report.md`, `research-261001-0147-ai2-key-scope-and-lexicon-governance-report.md` |
| Spike report | `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md` |
| Critique | `plans/reports/ai2-clause-key-critique-report.md`, `plans/reports/ai2-clause-key-critique/` |
| Hướng dẫn gán nhãn | `plans/reports/guide-261001-0147-ai2-clause-key-heldout-labeling-report.md` |
| Sơ đồ + vấn đề đang gặp | `plans/reports/status-261001-0915-ai2-clause-key-graph-diagrams-and-issues-report.md` |
