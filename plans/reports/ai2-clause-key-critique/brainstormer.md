# Critique lens: brainstormer (phương án thay thế) — AI2 clause key graph

Ngày: 2026-10-01 · Lens: brainstormer (adversarial alternatives) · Chế độ: chỉ đọc, không gọi LLM API.
Đối tượng: đề xuất "giữ nguyên tắc (LLM chép span + chọn enum đóng; code dựng key; không chắc thì không gom); ship key graph như lớp gợi ý precision cao + hàng đợi `UNMAPPED` + vòng tăng trưởng lexicon; recall trên điều khoản thật chưa thấy ~50–55%" — `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md:343-348`.

Nhãn: **PROVEN** = tôi tính lại từ file kết quả/mã hoặc chạy hàm tất định trong repo; **[ASSUMED]** = chưa kiểm; **[PRIOR]** = kiến thức nền chưa kiểm lại.
Script tính lại (không nằm trong repo): scratchpad `pairs.py`, `same.py`; chỉ đọc `evals/spikes/clause_key/results/**`.

---

## 1. Steelman — vì sao đề xuất hợp lý

1. **Tính an toàn đã được đo trên văn bản thật**: 0 gom sai trên held-out 1 (13/13, `gh/gpt-4o`, v1) và 1 gom sai trên held-out 2 (16/17, Sonnet, v2). Gộp hai lần đo sạch: 29/30 = 96,7% [83,3; 99,4] (PROVEN, Wilson).
2. **Kiểm toán được**: mỗi slot mang `span` + `method`; người review thấy vì sao hai frame được gom. Khớp DEC-1 ("không dùng embedding để quyết định quan hệ") và kết quả nghiên cứu cho thấy LLM tự do phát hiện conflict là yếu (`research-…-deep-dive-report.md:16,26`).
3. **Suy giảm an toàn**: lỗi rơi vào `UNMAPPED`/`?`/`NEEDS_REVIEW_UNPARSED` thay vì conflict giả.
4. **Trung thực về recall**: báo cáo tự hạ kỳ vọng từ 80% xuống ~50%, tự nêu "đuôi dài", không che giấu.

Nếu mục tiêu là "một lớp tín hiệu gọn, không gây nhiễu", đề xuất đáp ứng phần *không gây nhiễu*. Phần dưới kiểm tra xem nó có đáp ứng phần *tín hiệu* không.

---

## 2. Các giả định bị thách thức

### G1. Đơn vị đo sai: recall "~50–55%" là recall **giữa các hợp đồng khác nhau**, không phải recall **trong một hồ sơ** (PROVEN)

`run_spike.py:250` ghép cặp `itertools.combinations(rows, 2)` trên **toàn bộ** tập held-out, gồm điều khoản từ 13–18 hợp đồng mẫu không liên quan nhau. Sản phẩm chỉ so sánh **trong một hồ sơ** (thân + phụ lục). Phân rã cặp gold theo vị trí (dùng `heldout_sources.json`, `heldout2_sources.json`):

| Tập | Cặp gold | Khác hợp đồng (vô giá trị với sản phẩm) | Cùng câu (người review đã thấy cạnh nhau) | **Cùng hợp đồng, khác khoản** (giá trị thật) |
|---|---|---|---|---|
| Held-out 1 (18 hợp đồng) | 51 | 29 (57%) | 7 | **15** |
| Held-out 2 (13 hợp đồng) | 29 | 21 (72%) | 7 | **1** |

Recall trên nhóm có giá trị thật:

| Lần chạy | Cùng hợp đồng, khác khoản | Ghi chú |
|---|---|---|
| v1 trên held-out 1 (Sonnet, sạch) | **1/15 = 6,7%** [1,2; 29,8] | v1 đóng băng trước khi thấy held-out 1 |
| v1 trên held-out 1 (`gh/gpt-4o`, sạch) | 1/15 | cùng kết quả |
| v2 trên held-out 1 (**đã tinh chỉnh trên chính tập này**) | 3/15 = 20% | lạc quan |
| v2 trên held-out 2 (sạch) | 1/1 | n quá nhỏ |
| **Gộp các lần sạch** | **2/16 = 12,5%** [3,5; 36,0] | |

Con số "~50–55%" chủ yếu đến từ cặp **khác hợp đồng**. Nó không mô tả việc sản phẩm cần làm. Recall trong hồ sơ gần như chưa được đo (n = 16). Các lần đo sạch cho thấy ~7–13%.

### G2. Độ hạt của key: precision trên "key bằng nhau" ≠ precision trên **finding** (PROVEN)

Key REMEDY chỉ có `(bearer, action, qualifier)`, không có object/phạm vi (`mechanism.py:406`). Tôi chạy `decide()` với **key gold** trên Điều 5 của fixture demo `HD-TONG-HOP.vi.md:112-117`:

| Cặp | `decide()` trả về | Fixture nói gì |
|---|---|---|
| 5.2 (xây lắp 0,1%/ngày) ~ 5.3 (thiết bị 0,05%/ngày) | `COMPARABLE_DIFFERENCE` | "Hai khoản 5.2 và 5.3 **khác phạm vi**, không gộp thành một mức" (dòng 114) |
| 5.1 (phạt chậm **chung**) ~ 5.2 | `COMPARABLE_DIFFERENCE` | chung–riêng, lẽ ra là `GENERAL_VS_SPECIFIC` |
| 5.4 dưới 10 ngày ~ 5.4 từ 10 ngày | `GRADUATED` | đúng |

Nhãn gold dùng cùng độ hạt thô, nên chỉ số pair precision không thể phát hiện lỗi này. Ngay cả khi recall đạt 100%, fixture của chính sản phẩm vẫn sinh 2–3 "khác biệt" sai loại. Mọi kết quả đều là `NEEDS_REVIEW` nên đây không phải lỗi pháp lý, nhưng là nhiễu nằm đúng trên ca demo.

### G3. "Vòng tăng trưởng lexicon" giả định lỗi là do thiếu từ vựng; bằng chứng cho thấy lỗi chủ yếu do cấu trúc (PROVEN)

- Từ v0 sang v2: số action giữ nguyên **12**, alias tăng 29 → 45, nhưng **số loại luật trong lexicon tăng 8 → 18** khóa cấp cao (`default_bearer`, `profile_default_action`, `qualifier_bare`, `bare_generic_action`, `action_patterns`, `compounds_block`, …). Cơ chế cũng cần thêm tính năng code (`split_consequences`, lật bị động, `_head_free`, back-off `?`).
- Held-out 1: cả 5 nhóm lỗi (32 frame) cần sửa code hoặc taxonomy, không nhóm nào sửa được chỉ bằng alias (`spike-…:252-258`). Held-out 2: khoảng 5/15 frame lỗi sửa được bằng alias ("mất mát, hư hỏng tài sản"), phần còn lại cần sửa code (`spike-…:325-331`).
- Hệ quả: một vòng lặp mà người review thêm alias từ `UNMAPPED` chỉ xử lý được phần thiểu số. Phần đa số cần một phiên bản mechanism mới **cộng một tập held-out mới** (tập nào cũng chỉ dùng được một lần). Chi phí mỗi vòng là developer + người gán nhãn, không phải người review.

### G4. "Blocking theo key để tránh N²" (`brainstorm-…:71`) — trong một hồ sơ, N nhỏ (suspected)

Các fixture có 4–14 dòng chế tài: `HD-TONG-HOP.vi.md` 14, `AI2-TEST-MASTER.body.md` 4 (đếm thô bằng regex, PROVEN). Với N = 16 frame thì có 120 cặp; với N = 40 thì 780 cặp [ASSUMED N cho hợp đồng thật]. Vì vậy vét cạn theo cặp, có lọc thô, vẫn nằm trong ngân sách. Lý do chính để cần một **từ vựng chuẩn toàn cục** không đứng vững nếu mục tiêu chỉ là tương đương **cục bộ trong hồ sơ**. Key toàn cục chỉ cần cho phân tích xuyên hồ sơ, mà mục tiêu sản phẩm chưa yêu cầu điều đó (YAGNI).

### G5. PARAMETER và timeline phụ lục chưa được đo trên văn bản thật (PROVEN)

`clauses_heldout.jsonl` có 44/44 frame `REMEDY`, `clauses_heldout2.jsonl` có 31/31 frame `REMEDY`, và **0 frame `PARAMETER`**. Trong khi đó timeline giá trị theo phụ lục (DEC-dungskbg2004-1) và phần lớn "điều khoản bị thay đổi" giữa thân và phụ lục là tham số (giá, tạm ứng, thời hạn). Phần quan trọng nhất cho sản phẩm là phần chưa có bằng chứng trên dữ liệu thật.

### G6. "Phần chưa map dùng `clause_compare.py` làm dự phòng" — không có dự phòng trong thân hợp đồng (PROVEN)

`clause_compare.py:132-136` trả `[]` khi hồ sơ không có file phụ lục, và chỉ so cặp thân ↔ phụ lục đã căn theo tiêu đề/số Điều. Frame `UNMAPPED` nằm trong thân (vd. Điều 9 với Điều 12, hoặc 5.1 với 5.2) không có đường so sánh nào khác. Hàng đợi `UNMAPPED` liệt kê **frame**, không liệt kê **cặp**: người review phải tự tìm đối tác, tức là làm lại chính công việc gốc.

### G7. "Precision cao" chưa đạt cổng, và tầng quyết định chưa đo trên dữ liệu thật (PROVEN)

- Cận dưới precision gộp các lần sạch là 83,3% (29/30), thấp hơn cổng 95% đã đặt (`research-…:167`).
- Đọc hậu quả trên held-out 2 chỉ đạt 22/31 = 71% [53,4; 83,9] ở cả v1 lẫn v2. Nếu hai phía độc lập, một cặp được gom đúng có khoảng 0,71² ≈ 50% khả năng đọc đúng loại hậu quả cả hai bên (DERIVED, [ASSUMED] độc lập). Bảng quyết định end-to-end chỉ được đo trên dữ liệu giả lập (93,3%); held-out không có file `comparisons`.

---

## 3. Ba phương án thực sự khác nhau

### PA-A — Ứng viên theo cấu trúc + trọng tài theo cặp có quyền từ chối (tương đương cục bộ, bỏ từ vựng toàn cục)

**Cơ chế**
1. Sinh ứng viên tất định trong hồ sơ, gồm:
   - khoản anh em cùng Điều (outline sẵn có trong `clause_compare.py`);
   - tham chiếu tường minh "Điều N / khoản N.M / sửa Điều 5" (đã có `_REF` trong `mechanism.py:221`, `ANNEX_REF_RE` trong `compare.py:21`);
   - căn tiêu đề (đã có);
   - top-k theo trùng từ vựng trong cùng họ hậu quả, chỉ để đề xuất (không vi phạm DEC-1).
2. LLM trả lời **enum quan hệ đóng** cho từng cặp: `SAME_BREACH_SAME_SCOPE | SAME_BREACH_DIFFERENT_SCOPE | GENERAL_VS_SPECIFIC | UNRELATED | UNSURE`. Mỗi bên phải kèm span nguyên văn chỉ hành vi và phạm vi. Code kiểm verbatim; 2 phiếu phải trùng, nếu không thì `UNSURE`. Cơ chế 2 phiếu đã có ở `run_spike.py:70-86`.
3. Code giữ nguyên đại số điều kiện và `decide()`. LLM **không** phán conflict.

**Giả định nó phơi ra**: "muốn gom phải có key chuẩn toàn cục". Nguyên tắc "LLM chép span + chọn enum đóng" vẫn được giữ. Chỉ khác ở chỗ enum mô tả **quan hệ giữa hai khoản**, không mô tả **từ vựng hành vi**.

**Vì sao có thể vượt key graph**: ba nhóm lỗi lớn nhất của held-out 1 (vi phạm chung, câu không chủ ngữ, nghĩa vụ ngầm của NDA) đều do thiếu ngữ cảnh (`spike-…:274-277`). Trọng tài nhìn thấy cả hai khoản cùng tiêu đề Điều [ASSUMED sẽ giảm các lỗi này]. Ca 5.2 và 5.3 được xử lý qua lựa chọn `DIFFERENT_SCOPE`. Có tiền lệ gián tiếp: LLM so khớp thực thể theo cặp đạt mức ngang mô hình đã tinh chỉnh và bền hơn với loại thực thể chưa thấy (Peeters & Bizer, EDBT 2025) [PRIOR, miền khác: bản ghi tiếng Anh, không phải điều khoản tiếng Việt].

**Chi phí và rủi ro**
- Số lần gọi LLM cho một hồ sơ 40 frame: key graph cần ~40–80 lần; PA-A cần thêm 100–480 lần (DERIVED), tức gấp khoảng 3–6 lần.
- Độ trễ: 3,2 s/lần (`spike-…:296`) × 240 lần ÷ 8 luồng ≈ 96 s [ASSUMED mức song song].
- Rủi ro rate limit là có thật: `gh/gpt-4o` đã phải chờ 107 → 257 s trong spike.
- Kết quả phụ thuộc model: đổi model đã làm key accuracy lệch 43,2% so với 34,1% trên cùng dữ liệu (`spike-…:319`). Cần ghim model, cache theo `(quote_sha, quote_sha, model, prompt_version)` và giữ một bộ hồi quy.
- Quan hệ theo cặp không bắc cầu, nên UI phải hiển thị **cặp**, không hiển thị nhóm.
- Nếu chọn phương án này, cần một DEC làm rõ ranh giới với DEC-1: LLM chọn quan hệ, nhưng không có embedding và không có kết luận pháp lý.

**Đo được ngay**: nhãn held-out hiện có cho 946 + 465 = 1.411 cặp (80 cặp dương). Như vậy đủ để đạt ≥ 120 cặp dự đoán cho precision mà không cần gán nhãn thêm.

### PA-B — Nhãn mở theo từng hồ sơ, người review xác nhận cụm, lexicon học từ quyết định

**Cơ chế**
1. LLM chép span hành vi và viết một nhãn ngắn tự do (neo vào span).
2. Code gom cụm **trong hồ sơ**, dùng lexicon hiện có làm hạt giống.
3. Người review xác nhận hoặc tách cụm, mỗi cụm một thao tác.
4. Mỗi xác nhận ghi thành cặp `(span → cụm)`. Alias nào lặp lại ≥ k lần và được xác nhận thì tự động đề xuất đưa vào lexicon.

**Giả định nó phơi ra**: "lexicon phải do kỹ sư viết trước; người review chỉ là người dùng". Ở đây người review trở thành nguồn nhãn ngay trong luồng sản phẩm, và mỗi hồ sơ thật tự sinh dữ liệu gán nhãn. Đây chính là thứ báo cáo spike đánh giá là giá trị nhất (`spike-…:348`).

**Chi phí và rủi ro**
- Cần UI xác nhận cụm, telemetry và job đề xuất alias.
- Người review mất thêm khoảng 2–5 phút mỗi hồ sơ [ASSUMED].
- Chỉ có một người duyệt (D-A10), nên lexicon học được sẽ mang thiên lệch của một người.
- Có nguy cơ duyệt cho qua do mệt; cần đo tỷ lệ bị sửa lại.
- Lưu span hợp đồng để học cần chính sách ẩn danh.
- Không giải quyết được G3: lỗi cấu trúc (câu không chủ ngữ, hậu quả kép) vẫn cần code.

### PA-C — Thu hẹp phạm vi: PARAMETER + timeline theo tham chiếu tường minh + bảng tổng hợp chế tài theo Điều (không có key graph REMEDY ở v1)

Gần với "phương án 1 Fact++" (`brainstorm-…:97`), bổ sung phần cấu trúc.

**Cơ chế**
1. Key cho tham số `(PARAM, name, object)`. Phần này đã có trong `mechanism.py:417-434`.
2. Cạnh `AMENDS` lấy từ tham chiếu tường minh ("Phụ lục 1 — Sửa Điều 5", "khác Điều 7") để dựng timeline luôn `NEEDS_REVIEW` (DEC-dungskbg2004-1).
3. Với REMEDY: trích frame (span + điều kiện + hậu quả), hiển thị cạnh nhau **theo Điều** cùng các khoản phụ lục trỏ tới Điều đó. `decide()` chỉ chạy giữa các khoản anh em hoặc các khoản được tham chiếu tường minh, và cần thêm slot phạm vi/object (sửa G2).

**Giả định nó phơi ra**: "cặp có giá trị nằm ở những câu diễn đạt khác nhau giữa các Điều". Bằng chứng hiện có:
- Held-out 1: ít nhất **12/15** cặp trong cùng hợp đồng là **khoản anh em cùng Điều** theo số hiệu (PROVEN): H26–H29 thuộc Điều 5.x, H17/H18 thuộc 11.4/11.5, H20/H21 thuộc 5.1/5.2. Chỉ riêng tiêu chí "cùng Điều" đã bắt được 12/15 = 80% [54,8; 93,0] cặp ứng viên, so với 1/15 của key graph v1. Lưu ý: đây là recall của bước sinh ứng viên, chưa phải của finding.
- Fixture demo của sản phẩm: phụ lục trỏ đích danh "Sửa Điều 5" (`HD-TONG-HOP.vi.md:296-304`) và "khác Điều 7" (`AI2-TEST-MASTER.annexes.md:15-16`). Cả hai là tham chiếu tường minh. Tuy nhiên fixture do đội tự viết, nên chỉ nói lên ý định sản phẩm, không nói lên tần suất ngoài thực tế [ASSUMED].

**Chi phí và rủi ro**
- Ít code nhất: tái dùng outline `clause_compare.py`, `_REF`, `money_decimal`, `decide()`. Không cần lexicon hành vi.
- **Bỏ sót** cặp diễn đạt khác nhau giữa các Điều mà không có tham chiếu (ví dụ động lực ban đầu: Điều 9 với Điều 12, `brainstorm-…:15`). Tần suất của loại cặp này **chưa đo** và phải ghi rõ là giới hạn đã biết.

---

## 4. So sánh định lượng

| Tiêu chí | Đề xuất (key graph) | PA-A trọng tài theo cặp | PA-B cụm do người review xác nhận | PA-C thu hẹp (MVS) |
|---|---|---|---|---|
| Recall cặp trong hồ sơ (bằng chứng) | 2/16 sạch (12,5%); 3/15 khi đã tinh chỉnh | chưa đo; ứng viên tối đa ≥ 12/15 + tham chiếu [ASSUMED] | phụ thuộc người review [ASSUMED] | ứng viên cùng Điều 12/15 (PROVEN); bỏ sót cặp chỉ khác cách diễn đạt |
| Precision | key: 29/30 [83,3; 99,4]; finding: sai trên Điều 5 của fixture (G2) | chưa đo; đo được trên 1.411 cặp có sẵn | gần bằng độ chính xác của người review | cao nếu chỉ so khoản anh em/tham chiếu và có slot phạm vi [ASSUMED] |
| Số lần gọi LLM / hồ sơ 40 frame | ~40–80 | ~140–560 (gấp 3–6) | ~40 | ~40, hoặc ~0 nếu tham số chỉ dùng regex |
| Code và bảo trì | 538 dòng mechanism + 18 loại luật lexicon × 6 profile; mỗi nhóm lỗi mới cần một bản phát hành và một held-out mới | extraction + bộ sinh ứng viên + prompt/cache; dùng lại `decide()` | + UI + telemetry + job đề xuất alias | thấp nhất; dùng lại code sẵn có |
| Tất định / kiểm toán | cao | trung bình (phiếu + cache) | cao sau khi xác nhận | cao |
| Phủ timeline phụ lục (DEC-dungskbg2004-1) | chưa đo PARAMETER (G5) | như PA-C | như PA-C | trực tiếp |

---

## 5. Hệ quả bậc hai

- **Key graph**:
  - Taxonomy 12 action bị đóng băng vào schema của plan B/C. Mỗi profile hoặc nhóm lỗi mới cần một bản phát hành code + lexicon.
  - Con số "50–55%" dễ bị hiểu nhầm thành recall trong hồ sơ.
  - Nếu khoảng một nửa số frame nằm trong hàng đợi `UNMAPPED`, người review sẽ quen bỏ qua hàng đợi này.
  - Vòng lexicon không hội tụ nếu lỗi là cấu trúc (G3).
- **PA-A**:
  - Phụ thuộc nhà cung cấp LLM: rate limit, model trôi.
  - UI phải trình bày theo cặp.
  - Cần DEC mới về ranh giới "LLM chọn quan hệ".
  - Được lợi: dùng chung bộ sinh ứng viên với PA-C, nên không mất công nếu bắt đầu từ PA-C.
- **PA-B**:
  - Mỗi hồ sơ sinh ra dữ liệu thật (tài sản lâu dài).
  - Đổi lại là chi phí UI, thời gian của người review, rủi ro quyền riêng tư và thiên lệch của một người duyệt.
- **PA-C**:
  - Ship nhanh nhất và giao được timeline.
  - Nợ rõ ràng: cặp chỉ khác cách diễn đạt giữa các Điều.
  - Cấu trúc (outline, tham chiếu, slot phạm vi) là nền mà cả PA-A lẫn key graph đều cần. Bằng chứng: lỗi nhóm 1/2/5 của held-out 1 đều cần ngữ cảnh Điều (`spike-…:274-277`).

---

## 6. Phương án tối thiểu khả thi (MVS)

**PA-C** là phương án ít phức tạp nhất vẫn đáp ứng nhu cầu "giúp người review thấy điều khoản thay đổi hoặc mâu thuẫn trong hồ sơ, kèm trích dẫn":
- phụ lục sửa thân: tham số + tham chiếu tường minh;
- mâu thuẫn trong một Điều: khoản anh em + `decide()` có slot phạm vi.

Key graph (hoặc PA-A) chỉ nên được xây thêm **sau khi đo** được rằng cặp "chỉ khác diễn đạt, không tham chiếu, khác Điều" chiếm tỷ lệ đáng kể trong hồ sơ thật.

**Thí nghiệm quyết định (rẻ, nên làm trước khi viết lại plan B/C)**
1. Chấm lại các kết quả sẵn có theo vị trí cặp: báo cáo recall "trong hồ sơ" tách riêng (đã làm ở G1: 2/16).
2. Gán nhãn **5–10 hồ sơ thật đầy đủ** (thân + phụ lục) theo **cặp**. Mỗi cặp gắn một lớp: `SAME_SENTENCE | SAME_ARTICLE | EXPLICIT_REF | TITLE_ALIGNED | PARAPHRASE_ONLY`. Tỷ lệ `PARAPHRASE_ONLY` quyết định có cần key graph hay PA-A không. Đơn vị đo phải là hồ sơ, không phải tập câu rời.
3. Nếu `PARAPHRASE_ONLY` lớn hơn ngưỡng người dùng chốt (gợi ý ≥ 20% số cặp có giá trị [ASSUMED]): chạy `hs:bakeoff` giữa key graph v2 và PA-A trên đúng tập cặp đó, với cổng precision n ≥ 120.
4. Bất kể chọn phương án nào: thêm phạm vi/object vào key hoặc vào `decide()` (G2), và đo PARAMETER trên văn bản thật (G5).

---

## 7. Findings

```json
[
 {"lens":"brainstormer","anchor":"evals/spikes/clause_key/run_spike.py:250 + results/claude-sonnet-4-6/llm-full-v1-heldout-20261001-040427.json","finding":"Pair recall/precision gộp cặp trên toàn bộ tập held-out (13–18 hợp đồng khác nhau); 57% (HO1) và 72% (HO2) cặp gold là khác hợp đồng; recall cặp cùng hợp đồng khác khoản ở các lần chạy sạch là 2/16 = 12,5% [3,5; 36,0]","why_it_matters":"Con số '~50–55%' dùng để chọn kiến trúc (DEC-dungskbg2004-2) không đo việc sản phẩm làm (so trong một hồ sơ); recall có giá trị thực tế thấp hơn nhiều và gần như chưa được đo","fix":"Chấm lại theo vị trí cặp; gán nhãn 5–10 hồ sơ thật đầy đủ theo cặp với lớp SAME_ARTICLE/EXPLICIT_REF/TITLE_ALIGNED/PARAPHRASE_ONLY trước khi viết lại plan B/C","severity":"blocker","status":"proven"},
 {"lens":"brainstormer","anchor":"evals/spikes/clause_key/mechanism.py:406; ai-service/fixtures/contracts/HD-TONG-HOP.vi.md:112-114","finding":"Key REMEDY không có object/phạm vi; với key gold, decide() trả COMPARABLE_DIFFERENCE cho 5.2~5.3 (fixture ghi 'khác phạm vi, không gộp') và cho 5.1 chung~5.2 (lẽ ra GENERAL_VS_SPECIFIC)","why_it_matters":"Precision đo trên key bằng nhau không phản ánh precision của finding; nhãn gold cùng độ hạt nên chỉ số không thấy lỗi; nhiễu rơi đúng vào fixture demo","fix":"Thêm slot phạm vi/object vào key hoặc vào decide(); thêm mutation golden 'cùng hành vi, khác phạm vi' và 'chung vs riêng'","severity":"major","status":"proven"},
 {"lens":"brainstormer","anchor":"evals/spikes/clause_key/lexicon_v0.json vs lexicon_v2.json; spike-261001-0147-ai2-clause-key-rules-baseline-report.md:252-258,325-331","finding":"Từ v0→v2 số action giữ 12, alias 29→45, nhưng loại luật lexicon tăng 8→18 và mechanism thêm nhiều tính năng code; đa số nhóm lỗi held-out là lỗi cấu trúc, không sửa được bằng alias","why_it_matters":"'Vòng tăng trưởng lexicon' từ hàng đợi UNMAPPED chỉ xử lý phần thiểu số; mỗi vòng thực tế cần developer + một held-out mới dùng một lần","fix":"Tách hai vòng: alias (người review) và mechanism (release có held-out); hoặc chuyển nguồn ngữ cảnh sang cấu trúc Điều (PA-C/PA-A)","severity":"major","status":"proven"},
 {"lens":"brainstormer","anchor":"evals/spikes/clause_key/clauses_heldout.jsonl, clauses_heldout2.jsonl (44/44 và 31/31 REMEDY)","finding":"Không có frame PARAMETER nào trong hai tập held-out thật; key tham số và timeline phụ lục chưa được đo trên văn bản thật","why_it_matters":"Timeline giá trị theo phụ lục (DEC-dungskbg2004-1) và phần lớn 'điều khoản thay đổi' là tham số; phần quan trọng nhất cho sản phẩm là phần chưa có bằng chứng","fix":"Đo PARAMETER + tham chiếu AMENDS trên hồ sơ thật trước khi chốt kiến trúc","severity":"major","status":"proven"},
 {"lens":"brainstormer","anchor":"ai-service/app/pipeline/clause_compare.py:132-136","finding":"Dự phòng 'clause_compare.py cho phần chưa map' chỉ chạy thân↔phụ lục và trả [] khi không có phụ lục; frame UNMAPPED trong thân không có đường so sánh","why_it_matters":"Hàng đợi UNMAPPED liệt kê frame chứ không liệt kê cặp; người review phải tự tìm đối tác, tức là làm lại công việc gốc","fix":"Sinh ứng viên theo cấu trúc (khoản anh em cùng Điều, tham chiếu tường minh) cho frame UNMAPPED","severity":"major","status":"proven"},
 {"lens":"brainstormer","anchor":"results/llm-full-v1-heldout-20261001-032856.json (13/13) + results/claude-sonnet-4-6/llm-full-v2-heldout2-20261001-040925.json (16/17, cons 22/31)","finding":"Precision gộp các lần sạch là 29/30, cận dưới Wilson 83,3% < cổng 95%; đọc hậu quả trên HO2 là 22/31 = 71%; bảng quyết định end-to-end chưa đo trên dữ liệu thật","why_it_matters":"'Lớp gợi ý precision cao' chưa được chứng minh ở mức cổng đã đặt, và độ đúng của loại finding trên dữ liệu thật chưa rõ","fix":"Ghi rõ là suspected; đo decision e2e trên cặp trong hồ sơ thật với n ≥ 120","severity":"major","status":"proven"},
 {"lens":"brainstormer","anchor":"clauses_heldout.jsonl H26–H29 (Điều 5.x), H17/H18 (11.4/11.5), H20/H21 (5.1/5.2); HD-TONG-HOP.vi.md:296-304; AI2-TEST-MASTER.annexes.md:15-16","finding":"≥ 12/15 cặp cùng hợp đồng trong HO1 là khoản anh em cùng Điều; phụ lục trong fixture sửa Điều bằng tham chiếu tường minh; ứng viên theo cấu trúc bắt 12/15 so với key graph v1 bắt 1/15","why_it_matters":"Phương án tối thiểu (PA-C: PARAMETER + tham chiếu tường minh + so khoản anh em có slot phạm vi) có thể phủ phần lớn cặp có giá trị với ít code hơn; key graph chỉ đóng góp riêng ở cặp chỉ khác diễn đạt, và tần suất loại này chưa đo","fix":"Chọn PA-C làm MVS; chỉ xây key graph hoặc trọng tài theo cặp (PA-A) sau khi đo tỷ lệ PARAPHRASE_ONLY trên hồ sơ thật, dùng hs:bakeoff","severity":"major","status":"suspected"},
 {"lens":"brainstormer","anchor":"plans/reports/brainstorm-261001-0147-ai2-clause-frame-redirection-report.md:71; HD-TONG-HOP.vi.md (14 dòng chế tài)","finding":"Lý do 'blocking theo key để tránh N²' giả định N lớn; trong một hồ sơ N ≈ 15–40 frame (120–780 cặp), nên trọng tài theo cặp với enum quan hệ đóng + 2 phiếu + UNSURE là khả thi","why_it_matters":"Phương án không cần từ vựng toàn cục bị loại quá sớm; phương án này giữ nguyên tắc 'LLM chọn enum đóng', chỉ đổi đối tượng của enum","fix":"Đưa PA-A vào bake-off; tận dụng 1.411 cặp có nhãn sẵn trong HO1+HO2 để đo precision; nếu chọn thì cần DEC làm rõ ranh giới với DEC-1","severity":"minor","status":"suspected"}
]
```

## Nguồn ngoài

- [Entity Matching using Large Language Models — Peeters, Steiner, Bizer (EDBT 2025, arXiv 2310.11244)](https://arxiv.org/pdf/2310.11244)
- [Match, Compare, or Select? An Investigation of LLMs for Entity Matching (COLING 2025)](https://aclanthology.org/2025.coling-main.8.pdf)
- [Confidence Calibration in LLM-Based Entity Matching (arXiv 2509.19557)](https://arxiv.org/pdf/2509.19557)
