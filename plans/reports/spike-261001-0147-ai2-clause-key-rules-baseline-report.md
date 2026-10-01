# Spike — AI2 clause key: baseline chế độ `rules` (lexicon v0)

Ngày: 2026-10-01 · Code: `evals/spikes/clause_key/` · Test: `evals/tests/test_clause_key_spike.py` (41 pass) · Kết quả thô: `evals/spikes/clause_key/results/rules-20261001-024412.json`

## Cách chạy

```bash
ai-service/.venv/Scripts/python.exe -m pytest evals/tests/test_clause_key_spike.py -q -p no:cacheprovider
ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.run_spike --mode rules      # offline
ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.run_spike --mode llm-enum   # cần 9Router
ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.run_spike --mode llm-full   # cần 9Router
```

## Dữ liệu và hạn chế

- 60 điều khoản / 60 frame, 6 profile, **giả lập**; 15 cặp so sánh gán nhãn. `gold_span_errors = []`.
- Lexicon v0 viết **trước** bộ test. Nhưng cùng một tác giả (Claude) viết cả hai → vẫn thiên lệch; cần hợp đồng thật ẩn danh để kết luận.
- Chưa có tập dev → kết quả này là **baseline mù**, chưa được tinh chỉnh.
- Cỡ mẫu nhỏ: mọi con số kèm Wilson 95%.

## Kết quả (OBSERVED)

| Chỉ số | Kết quả | Wilson 95% |
|---|---|---|
| Key đúng (tính cả `UNMAPPED` đúng) | 42/60 = 70,0% | [57,5%; 80,1%] |
| Tỷ lệ map được (coverage) | 48/60 = 80,0% | [68,2%; 88,2%] |
| Key đúng khi đã map | 37/48 = 77,1% | [63,5%; 86,7%] |
| **Pair precision (gom đúng)** | **31/34 = 91,2%** | [77,0%; 97,0%] |
| **Pair recall (gom đủ)** | **31/87 = 35,6%** | [26,4%; 46,1%] |
| Đọc hậu quả (loại + giá trị) | 43/49 = 87,8% | [75,8%; 94,3%] |
| Bảng quyết định (key gold) | 10/15 = 66,7% | [41,7%; 84,8%] |
| Bảng quyết định (end-to-end) | 9/15 = 60,0% | [35,7%; 80,2%] |

Phân bố bậc: L1 = 29 (đúng 93,1%), L2 = 13 (61,5%), L3 = 1, L6 = 5 (20%), L7 = 12 (5 đúng là "không có key", 7 cần LLM).

## Phân tích lỗi

### 1. Qualifier `LATE` là nguyên nhân chính của recall thấp (9/18 key sai)

Action đúng nhưng mất `LATE`: T09 "không … đúng hạn", T20, T22, T24 "vi phạm tiến độ", T49 "không được giao đúng thời hạn", T50 "muộn", T52 "trễ", T55 "quá thời hạn". Tiếng Việt diễn đạt "chậm" bằng **phủ định + đúng hạn** và nhiều từ đồng nghĩa; lexicon alias liền mạch không bắt được.

### 2. Bẫy bị động "không được" (T10)

"Bên Bán **không được** thanh toán" → bearer vẫn là `SELLER` (đúng phải là `BUYER`). Luật lật bị động chỉ bắt "X được"; chèn "không" là trượt.

### 3. Near-miss gom nhầm action (T25, T47)

- T25 "bàn giao" (công trình) → `DELIVER` thay vì `COMPLETE_WORK`: alias "giao" quá ngắn.
- T47 "Giá trị bảo lãnh thực hiện hợp đồng" → `PRICE` vì chứa "giá".

Lần này chưa gây gom nhầm cặp, nhưng là rủi ro precision.

### 4. False merge đến từ key lùi về cha (3/3 false merge)

T49/T50/T52 lùi về `(SELLER, DELIVER, None)` và bị gom với T18 (vốn đúng là key cha). **Frame lùi về key cha không được coi là cùng nhóm** với frame khác; phải so theo kiểu `GENERAL_VS_SPECIFIC`.

### 5. Lexicon thiếu alias thường gặp

"trả lương" (T34, T60), "để lộ" (T38), "nghỉ việc" (T35), "bảo hành trong thời gian" (T43). T59 ("vi phạm" trỏ về câu trước) cần ngữ cảnh câu, không phải lexicon.

### 6. Bảng quyết định: 4 lỗi thiết kế

| Cặp | Kỳ vọng | Nhận được | Nguyên nhân |
|---|---|---|---|
| T01~T03, T03~T53 | CUMULATIVE / DUPLICATE | GRADUATED | "quá 15 ngày" và "từ 16 ngày trở lên" là cùng ngưỡng với **ngày nguyên**; code coi là số thực |
| T01~T04 | COMPARABLE_DIFFERENCE | CUMULATIVE | `PENALTY_FIXED` và `PENALTY_RATE` cùng họ "phạt"; không được coi là cộng dồn |
| T02~T51 | COMPARABLE_DIFFERENCE | GRADUATED | Hai mức phạt phẳng lồng nhau đều áp dụng khi quá 15 ngày → chồng, không phải bậc thang |
| T23~T58 | COMPARABLE_DIFFERENCE | NOT_COMPARABLE | `basis` trộn "chu kỳ" (/ngày, /tuần) với "cơ sở" (giá trị hợp đồng) |

### 7. Loại hậu quả thiếu

`WITHHOLD` ("khấu trừ", "giảm … phí"), phạt không có số ("tương đương 1 tháng tiền thuê", "gấp đôi"), chi phí ("chi phí lưu kho"), "tạm hoãn".

## Kết luận tạm

- **Precision của phần luật tất định khá tốt** (91,2%, nhưng cận dưới chỉ 77%) và cả 3 false merge có chung một nguyên nhân sửa được (mục 4).
- **Recall rất thấp (35,6%)**: chỉ dùng luật thì không đủ. Chưa đạt cổng 80% đề xuất. Qualifier cần tầng LLM enum (như action) hoặc luật phủ định "không … đúng hạn".
- **Bảng quyết định cần sửa 4 luật** trước khi đáng tin.
- Chưa đủ dữ liệu để chọn phương án 1/2/3 — cần chạy `llm-enum`/`llm-full` và có dữ liệu thật.

## Bước tiếp theo đề xuất

1. Bật 9Router → chạy `llm-enum` và `llm-full` trên cùng bộ test (không sửa gì) để có baseline LLM.
2. Tạo **tập dev riêng** (~30 điều khoản mới) → sửa lexicon/luật (mục 1–7) **chỉ dựa trên dev** → đo lại trên test. Không sửa theo lỗi của test để tránh "học vẹt".
3. Bổ sung điều khoản thật ẩn danh do người dùng cung cấp.

---

## Bổ sung: chạy có LLM (9Router `gh/gpt-4o`, qua `127.0.0.1`)

Kết quả thô: `results/llm-enum-20261001-024831.json`, `results/llm-full-20261001-025416.json` (llm-full chấm lại sau khi đổi cách ghép frame từ theo-thứ-tự sang theo-nội-dung; lần chạy index-based `llm-full-20261001-025105.json` cho kết quả tương tự: key 38,3%, precision 62,5%).

| Chỉ số | `rules` | `llm-enum` (+bậc 5) | `llm-full` (LLM tự chép span) |
|---|---|---|---|
| Key đúng | 42/60 = 70,0% | 43/60 = 71,7% | 21/60 = 35,0% |
| Coverage (map được) | 80,0% | 93,3% | 91,7% |
| Key đúng khi map | 77,1% | 71,4% | 34,5% |
| **Pair precision** | **91,2%** [77,0; 97,0] | **89,2%** [75,3; 95,7] | **53,3%** [39,1; 67,1] |
| **Pair recall** | 35,6% | 37,9% | 27,6% |
| Đọc hậu quả | 87,8% | 87,8% | 63,3% |
| Bảng quyết định (e2e) | 60,0% | 60,0% | 33,3% |

### `llm-enum`: bậc 5 đúng 3/8

- Đúng: "trả lương" → `PAY` (T34, T60), "nghỉ việc không báo trước" → `TERMINATE_EARLY` (T35).
- **LLM dùng `ANY_OBLIGATION` làm lối thoát** thay vì `NONE` (T05, T39, T59) → sinh false merge mới T39~T59. Cách sửa: loại `ANY_OBLIGATION` khỏi enum; key chung chỉ được sinh bằng alias tường minh.
- Near-miss sai: "nhận hàng" → `ACCEPT` (T40). Định nghĩa enum cần phân biệt "nhận hàng" với "nghiệm thu".

### `llm-full`: lỗi chủ yếu do prompt, không phải do khả năng chép

LLM chép **nguyên văn** tốt (1 span bị loại / 63 frame), nhưng **đặt sai vai trò của span**:

| Kiểu lỗi | Số frame | Ví dụ |
|---|---|---|
| Gộp qualifier vào action, dồn điều kiện vào qualifier | ~17 | T01: action "chậm giao hàng", qualifier "quá 15 ngày" |
| Lấy **hậu quả** làm action | ~9 | T02 "bị phạt", T37 "chịu phạt 10%…", T59 "bồi thường 300.000.000 đồng" |
| Lấy biện pháp khắc phục làm action | 3 | T26 "sửa chữa…", T32 "thay thế" |
| Object tham số là "hợp đồng" | 2 | T14/T15 → key thêm `'hợp đồng'` |

Hệ quả: false merge tăng lên 21 (chủ yếu qua `ANY_OBLIGATION` và key cha), precision rơi xuống 53%.

### Kết luận sau 3 lần chạy

1. **Phần tất định + span chuẩn đạt precision ~90%**; muốn vượt 95% cần sửa 3 nguyên nhân false merge đã biết (key cha gom chung, `ANY_OBLIGATION` trong enum, alias quá ngắn "giao"/"giá").
2. **Nút cổ chai thực sự là bước chép span (bước A)**: prompt v0 không định nghĩa rõ "action = hành vi vi phạm, không phải hậu quả", không có ví dụ. Chưa được đo công bằng.
3. **Code chuẩn hóa cần chịu được span lệch vai**: tìm qualifier trong cả action_text; bỏ điều kiện số khỏi qualifier; object "hợp đồng" → None.
4. **Recall < 40% ở mọi chế độ**: chưa đạt cổng 80%. Nguyên nhân lớn nhất vẫn là qualifier `LATE`.

### Bước tiếp theo (thứ tự đề xuất)

1. Viết **tập dev** (~30 điều khoản mới) — mọi sửa đổi dưới đây chỉ được kiểm trên dev.
2. Prompt v1: định nghĩa từng trường + 2 ví dụ; enum bỏ `ANY_OBLIGATION`, thêm định nghĩa tách "nhận hàng"/"nghiệm thu".
3. Code: qualifier tìm trong action_text; luật phủ định "không … đúng hạn/thời hạn" → `LATE`; key cha không gom nhóm; ngày nguyên (>15 ≡ ≥16); họ "phạt"; tách `basis` thành chu kỳ + cơ sở.
4. Đo lại một lần trên test (không sửa theo test), báo cáo so sánh v0 → v1.

---

## Vòng v1 (2026-10-01): dev → đóng băng → test một lần

### Quy trình

1. Viết `clauses_dev.jsonl` (34 điều khoản mới, không trùng câu với test) + `comparisons_dev.jsonl` (10 cặp).
2. Đo v0 trên dev: key 58,8%, precision 71,4%, quyết định e2e 40%.
3. Viết test trước (TDD), sửa code + `lexicon_v1.json` + prompt v1 — chỉ kiểm trên dev. 81 unit test pass.
4. Đóng băng v1: `results/v1-freeze.sha256`. Chạy test **một lần** cho cả 3 chế độ.

### Thay đổi trong v1

| Nhóm | Thay đổi |
|---|---|
| Qualifier | Luật phủ định "không … đúng hạn/thời hạn/tiến độ", "quá (thời) hạn" → `LATE`; tìm qualifier trong ô qualifier → ô action → cả câu (trừ hậu quả); ô qualifier chứa con số thì coi là điều kiện |
| Back-off | Qualifier không nhận ra → key đánh dấu `?`, **không bao giờ gom nhóm** (hết false merge kiểu T18) |
| Bị động | "X không/chưa được \<action\>" cũng lật bên; "được X \<action\>" (X là tác nhân) không lật |
| Action | Ô action chứa hậu quả ("bị phạt") → quét câu; alias theo profile ("bàn giao" trong xây dựng = `COMPLETE_WORK`); tham chiếu "khoản 3.2" và tìm tham chiếu cả ngoài ô action |
| LLM enum | Bỏ `ANY_OBLIGATION` khỏi danh sách; định nghĩa phân biệt "nhận hàng"/"nghiệm thu"/"giao hàng" |
| Tham số | Chặn từ ghép ("giá" ≠ "giá trị"); bỏ stopword; khớp theo tập từ; ghép `param + object` khi LLM tách đôi tên; object "hợp đồng" → None |
| Điều kiện | Ngày/giờ nguyên: "quá 15 ngày" ≡ "từ 16 ngày trở lên" |
| Hậu quả | Tách `base` (phần vi phạm / giá trị hợp đồng / khác) và `period` (/ngày, /tuần…); thêm `WITHHOLD`, "tạm dừng/tạm hoãn", "sa thải", phạt không có số |
| Quyết định | Họ "phạt" (cố định vs %): khác chế độ → `COMPARABLE_DIFFERENCE`; cùng loại lồng nhau → `COMPARABLE_DIFFERENCE` (chỉ tách rời mới là `GRADUATED`) |
| Prompt v1 | Định nghĩa từng ô ("action KHÔNG chứa hậu quả, KHÔNG chứa chậm/thiếu"), 2 ví dụ lấy từ dev |
| Bug | `fold()` đổi nhầm "khoản" → "khỏan"; nay chỉ đổi âm tiết mở ("hoá" → "hóa") |

### Kết quả test v0 → v1 (Wilson 95%)

| Chỉ số | rules v0 → v1 | llm-enum v0 → v1 | llm-full v0 → v1 |
|---|---|---|---|
| Key đúng | 70,0% → **91,7%** [81,9; 96,4] | 71,7% → **90,0%** [79,9; 95,3] | 35,0% → **83,3%** [72,0; 90,7] |
| Pair precision | 91,2% → **97,1%** (68/70) [90,2; 99,2] | 89,2% → **95,8%** (68/71) [88,3; 98,6] | 53,3% → **100%** (70/70) [94,8; 100] |
| Pair recall | 35,6% → **78,2%** [68,4; 85,5] | 37,9% → **78,2%** [68,4; 85,5] | 27,6% → **80,5%** [70,9; 87,4] |
| Đọc hậu quả | 87,8% → 98,0% | 87,8% → 98,0% | 63,3% → 95,9% |
| Quyết định e2e | 60,0% → 93,3% | 60,0% → 93,3% | 33,3% → 66,7% |

### Lỗi còn lại trên test

| Lỗi | Chế độ | Ghi chú |
|---|---|---|
| **T47 "Giá trị bảo lãnh thực hiện hợp đồng" → `CONTRACT_VALUE`** (2 false merge) | cả 3 | **Hồi quy do chính v1 gây ra**: khớp theo tập từ quá lỏng ({giá, trị, hợp, đồng} ⊂ câu). Cũng đã lộ ra trên dev (D12~D13) ở lần xác nhận chạy cùng lệnh với test, nên chưa kịp sửa trước khi chạy test |
| T10 "Bên Bán **không được** thanh toán **đầy đủ trong thời hạn**" | cả 3 | Lật bên đúng (BUYER), nhưng "trong thời hạn" không có "đúng" → mất `LATE` |
| T05 "cung ứng hàng hóa đúng tiến độ" | cả 3 | LLM chọn đúng `DELIVER` nhưng qualifier nằm ngoài ô |
| T33/T35 "trái pháp luật", "không báo trước" | rules, llm-full | Qualifier chưa có trong taxonomy → `?` (an toàn: không gom) |
| T30 "khắc phục sự cố" → `WARRANT` | llm-enum, llm-full | LLM enum chọn gần nghĩa; gold là "chưa có key" |
| T59 "vi phạm" trỏ về câu trước | rules, llm-enum | Cần ngữ cảnh câu trước trong cùng khoản |
| 4 cặp quyết định → `NEEDS_REVIEW_UNPARSED` | llm-full | LLM đưa chữ không có số ("so với thời hạn…", "mỗi ngày giao hàng chậm") vào ô điều kiện → an toàn nhưng mất kết luận |

### Đánh giá so với cổng spike

| Cổng đề xuất | Kết quả v1 | Đạt? |
|---|---|---|
| Precision: cận dưới Wilson ≥ 95% | rules 90,2% · llm-enum 88,3% · llm-full 94,8% | **Chưa** (llm-full sát ngưỡng) |
| Recall ≥ 80% | 78,2% · 78,2% · 80,5% | Sát ngưỡng |
| Số cặp precision ≥ 120 | 70 | **Chưa đủ mẫu** |

### Cảnh báo về độ tin cậy (quan trọng)

1. **Kết quả test v1 lạc quan hơn thực tế.** Các nhóm lỗi sửa trong v1 được nhận ra từ lỗi test v0; dù chỉ tinh chỉnh trên dev, người sửa đã biết test có gì. Test giờ đã "bị nhìn".
2. **Cùng một tác giả** (Claude) viết lexicon, dev, test và gold. Chưa có người thứ hai gán nhãn.
3. **Dữ liệu giả lập**, câu ngắn, một mệnh đề. Hợp đồng thật dài hơn, nhiều mệnh đề lồng nhau, OCR nhiễu.
4. Muốn con số không thiên lệch cần **một tập held-out mới** (lý tưởng là điều khoản thật ẩn danh do người dùng cung cấp), đo v1 đúng một lần.

### Kết luận v1

- Cơ chế **khả thi về hướng**: sau một vòng sửa, cả 3 chế độ đạt ~96–100% precision điểm và ~80% recall trên test; lỗi còn lại phần lớn **an toàn** (`?`, `UNMAPPED`, `NEEDS_REVIEW_UNPARSED`) thay vì gom sai.
- **`llm-full` (LLM chép span + code chuẩn hóa) là chế độ mạnh nhất về precision** khi prompt định nghĩa rõ từng ô — thay đổi lớn nhất v0 → v1 đến từ prompt, không phải lexicon.
- Chưa đủ để chọn phương án cuối (cổng precision chưa đạt cận dưới, cỡ mẫu 70 < 120, test đã bị nhìn).

### Bước tiếp theo đề xuất

1. Sửa hồi quy T47 (khớp tập từ chỉ khi alias ≥ 3 từ **và** phần dư không chứa danh từ đại lượng khác) — kiểm trên dev.
2. Người dùng cung cấp **20–40 điều khoản thật ẩn danh** làm held-out mới; gán nhãn gold độc lập (người dùng hoặc người thứ hai).
3. Mở rộng lên ≥ 120 cặp precision (thêm hợp đồng dài nhiều mệnh đề).
4. Nếu held-out mới đạt cận dưới precision ≥ 95% → chọn phương án 3 (frame phân tầng) và viết lại plan B/C.

---

## v1.1 (2026-10-01): sửa hồi quy tham số, chuẩn bị held-out

- **Nguyên nhân hồi quy T47/D12** (xác nhận qua span LLM): (a) ghép `param + object` cả khi tên đại lượng đã đầy đủ ("Giá trị tạm ứng" + "giá trị hợp đồng" lấy từ phần giá trị); (b) khớp theo tập từ bỏ qua cấu trúc cụm danh từ đầu-trước ("giá trị **bảo lãnh** … hợp đồng").
- **Sửa**: chỉ ghép khi ô param là danh từ trần (≤ 2 âm tiết), thử cả hai thứ tự; khớp tập từ yêu cầu đầu tố của alias không bị một danh từ lạ bổ nghĩa. Test viết bằng câu dev + câu mới, không dùng câu test.
- **Dev v1.1**: `rules` 34/34, `llm-full` 34/34, 0 false merge. **Không chạy lại test** (đã bị nhìn).
- Đóng băng: `results/v1.1-freeze.sha256`. Unit test: 94 pass (85 spike + 9 import).
- **Held-out**: `heldout_template.csv`, `heldout_example.csv`, `import_heldout.py`; `run_spike --mode llm-full` chấm frame theo anchor (không cần span tay). Hướng dẫn: `plans/reports/guide-261001-0147-ai2-clause-key-heldout-labeling-report.md`. Smoke test trên ví dụ 3 khoản/4 frame: đúng 4/4, `rules` từ chối dữ liệu không span như thiết kế.

---

## Held-out thật (2026-10-01): 36 khoản / 44 frame, chạy một lần

### Dữ liệu

- **Nguồn**: mẫu hợp đồng công khai trên web (mua bán, thuê nhà xưởng/mặt bằng, phần mềm, dịch vụ kế toán, NDA; 14 trang) + fixture repo `HD-TONG-HOP.vi.md`, `AI2-TEST-MASTER.body.md`. Danh sách URL từng khoản: `evals/spikes/clause_key/heldout_sources.json`.
- **Trích nguyên văn bằng script** (`build_heldout.py`, tìm dòng theo đoạn nhận diện trong HTML/MD đã tải), chỉ bỏ ký tự đầu dòng/ngoặc kép; khoản H29 ghép 3 dòng liệt kê.
- **5/6 profile** (không có EMPLOYMENT: mẫu công khai hầu như không có điều khoản chế tài riêng cho hợp đồng lao động).
- **Nhãn do Claude gán theo nghĩa, trước khi chạy**, khóa bằng `results/heldout-labels.sha256`. Vẫn là cùng một người gán nhãn với người thiết kế cơ chế → cần người thứ hai kiểm lại.
- **Mã băm**: `mechanism.py` và `lexicon_v1.json` khớp `v1.1-freeze.sha256`; `run_spike.py` **không khớp** vì đã sửa sau đóng băng để hỗ trợ held-out (ghép frame theo anchor, comparisons tùy chọn) — chỉ phần chấm điểm.

### Kết quả (`llm-full`, `gh/gpt-4o`, Wilson 95%)

| Chỉ số | Held-out thật | So với test giả lập v1 |
|---|---|---|
| Key đúng | 19/44 = **43,2%** [29,7; 57,8] | 83,3% |
| Coverage (map được) | 19/44 = **43,2%** | 90,0% |
| **Pair precision** | **13/13 = 100%** [77,2; 100] | 100% |
| **Pair recall** | **13/51 = 25,5%** [15,5; 38,9] | 80,5% |
| Đọc hậu quả | 31/44 = 70,5% | 95,9% |
| False merge | **0** | 0 |

### Đọc kết quả

**Điểm tốt: không có gom sai nào trên văn bản thật.** Mọi frame được map đều map đúng (19/19). Mọi lỗi đều rơi vào `UNMAPPED` hoặc `?` — người review thấy "chưa so được", không thấy conflict giả.

**Điểm xấu: cơ chế theo-từng-câu chỉ phủ được ~43% điều khoản thật.** Lỗi gom thành 5 nhóm, **đều là nhóm cấu trúc, không chỉ thiếu từ vựng**:

| Nhóm | Frame | Ví dụ | Nguyên nhân |
|---|---|---|---|
| 1. Điều khoản vi phạm **chung** | 13 | "vi phạm bất kỳ điều khoản, điều kiện nào", "vi phạm nghiêm trọng nghĩa vụ", "không thực hiện nghĩa vụ", "việc thực hiện hợp đồng … bị chậm trễ" | Alias `ANY_OBLIGATION` quá hẹp, và v1 đã **bỏ `ANY_OBLIGATION` khỏi enum LLM** (quyết định dựa trên test giả lập) → hợp đồng thật dùng rất nhiều câu chung, nên quyết định này tốn recall |
| 2. **Không có chủ ngữ** / câu danh từ hóa | 8 | "5.1. Phạt chậm tiến độ chung …: 0,2%/ngày", "Chậm giao thiết bị bị phạt 0,2%…" | Bên vi phạm và hành vi nằm ở **tiêu đề Điều / ngữ cảnh hợp đồng**, không nằm trong câu. Cơ chế đọc từng câu nên không thấy |
| 3. Nhiều hậu quả trong một câu | 6 (hậu quả) | "chịu phạt 8% … **và** bồi thường toàn bộ thiệt hại" | LLM trả **một** frame gộp hai hậu quả → đọc hậu quả sai loại |
| 4. Qualifier tách rời | 3 | qualifier = "không" | "không" + action = `NOT_PERFORMED` chưa có luật |
| 5. Nghĩa vụ ngầm theo loại hợp đồng | 2 | NDA: "Bên vi phạm nghĩa vụ bảo mật", "bên vi phạm còn phải chịu phạt" | Cần biết đây là NDA → vi phạm mặc định = tiết lộ trái phép |

### Đánh giá theo cổng

| Cổng | Kết quả | Đạt? |
|---|---|---|
| Cận dưới precision ≥ 95% | 77,2% (chỉ 13 cặp) | **Chưa** — mẫu quá nhỏ để kết luận |
| Recall ≥ 80% | 25,5% | **Không đạt, xa ngưỡng** |
| ≥ 120 cặp | 51 cặp gold (13 cặp dự đoán) | **Không đạt** — mẫu công khai ít điều khoản chế tài và phần lớn là câu chung |

Theo bảng quyết định trong hướng dẫn: precision điểm đạt nhưng cận dưới chưa đủ → *mở rộng mẫu*; nhưng recall 25,5% cho thấy **v1.1 chưa đủ để chọn phương án 3 dưới dạng "đọc từng câu"**.

### Kết luận sau held-out

1. **Nguyên tắc an toàn đứng vững trên dữ liệu thật**: LLM chỉ chép + code chuẩn hóa + không gom khi không chắc → 0 gom sai. Đây là thuộc tính quan trọng nhất cho người review.
2. **Con số trên dữ liệu giả lập (80% recall) không chuyển sang dữ liệu thật (25%)** — đúng như cảnh báo về thiên lệch cùng-tác-giả. Câu thật dài, chung chung, thiếu chủ ngữ, nhiều hậu quả trong một câu.
3. Ba nhóm lỗi lớn nhất (1, 2, 5) cần **ngữ cảnh cấp tài liệu**, không phải thêm alias:
   - vai trò các bên từ phần đầu hợp đồng + loại hợp đồng (profile) để suy bên vi phạm mặc định;
   - tiêu đề Điều/khoản ("Điều 5. Phạt vi phạm", "Phạt chậm tiến độ") làm ngữ cảnh cho câu danh từ hóa;
   - vi phạm chung phải là key hợp lệ (`ANY_OBLIGATION` với qualifier), so theo kiểu `GENERAL_VS_SPECIFIC`.
4. Nhóm 3 cần **tách frame theo hậu quả** ("A và B" → 2 frame) — sửa được ở prompt/code.

### Đề xuất tiếp

1. **Không sửa rồi đo lại trên held-out này** (đã bị nhìn). Dùng lỗi held-out làm *dev v2*.
2. v2 = thêm **ngữ cảnh tài liệu** vào mỗi câu (bên + profile + tiêu đề Điều) — đây chính là phần "graph cấu trúc" của phương án 3 (node Điều/khoản cha cung cấp ngữ cảnh), cho thấy phương án 3 cần đầy đủ hơn, không chỉ đọc câu đơn.
3. Tách hậu quả kép; cho `ANY_OBLIGATION` + qualifier (`NOT_PERFORMED`, `LATE`) vào lại enum nhưng **đánh dấu là key chung** để không gom với key cụ thể.
4. Cần tập held-out **mới** (lý tưởng: hợp đồng thật, người thứ hai gán nhãn) để đo v2.

---

## v2 — ngữ cảnh tài liệu, đo trên held-out 2 (2026-10-01)

### Quy trình (sạch nhất đến nay)

1. **Held-out 2 gán nhãn và khóa trước khi viết v2**: 22 khoản / 31 frame từ 13 trang mẫu mới (thi công nhà ở, vận chuyển, bảo vệ, vệ sinh, bảo trì, thuê kho/xe, mua bán) — `heldout2.csv`, `heldout2_sources.json`, `results/heldout2-labels.sha256`. Không chạy hệ thống trên tập này cho tới khi v2 đóng băng.
2. v2 phát triển **chỉ trên held-out 1** (làm dev), TDD: 111 unit test pass.
3. Đóng băng `results/v2-freeze.sha256`; `v2.1-freeze.sha256` chỉ thêm retry khi timeout trong `run_spike.py` (mechanism/lexicon không đổi, đã đối chiếu).
4. **Đổi model**: `gh/gpt-4o` bị GitHub Models giới hạn (chờ tăng dần 107 s → 257 s); `gemini/gemini-3-flash-preview` timeout. Thử 8 lần gọi liên tiếp cho 7 model qua 9Router → chọn `ag/claude-sonnet-4-6` (8/8, 3,2 s). Vì đổi model, chạy lại v1 làm mốc trên cùng model.

### Thay đổi v2

| Nhóm lỗi held-out 1 | Sửa v2 |
|---|---|
| Vi phạm chung | Alias + pattern `vi phạm … (điều khoản|nghĩa vụ|hợp đồng|thỏa thuận)` → `ANY_OBLIGATION` (đánh dấu `generic`); **hành vi cụ thể thắng cụm chung** ("vi phạm nghĩa vụ thanh toán" → `PAY`) |
| Không có chủ ngữ | `default_bearer` theo profile × action (xây dựng: `COMPLETE_WORK` → `CONTRACTOR`, `PAY` → `OWNER`…); không đè "bên vi phạm" tường minh |
| Câu danh từ hóa | Alias profile xây dựng "tiến độ", "xây lắp"; quét câu khi ô action trống |
| Hai hậu quả một câu | `split_consequences()` + prompt v2 "mỗi hậu quả một frame" |
| "không" tách rời | qualifier chỉ "không" → `NOT_PERFORMED`; "không thực hiện" → vi phạm chung |
| NDA ngầm | profile NDA: "bảo mật" → `DISCLOSE`; action trống/chỉ "vi phạm" → `DISCLOSE` |
| Tỷ lệ trần "0,2%/ngày" | → `PENALTY_RATE` |

### Kết quả (`llm-full`, `ag/claude-sonnet-4-6`, Wilson 95%)

| Tập | Bản | Key đúng | Coverage | Pair precision | Pair recall | False merge |
|---|---|---|---|---|---|---|
| Held-out 1 (dev v2) | v1 | 15/44 = 34,1% | 47,7% | 12/12 = 100% | 12/51 = 23,5% | 0 |
| Held-out 1 (dev v2) | v2 | 33/44 = **75,0%** | 84,1% | 22/22 = 100% | 22/51 = **43,1%** | 0 |
| **Held-out 2 (mới)** | v1 | 14/31 = 45,2% [29,2; 62,2] | 67,7% | 15/16 = 93,8% | 15/29 = 51,7% | 1 |
| **Held-out 2 (mới)** | v2 | 16/31 = **51,6%** [34,8; 68,0] | 80,6% | 16/17 = **94,1%** [73,0; 99,0] | 16/29 = **55,2%** [37,5; 71,6] | 1 |

Ghi chú: với `gh/gpt-4o`, v1 trên held-out 1 là 43,2% (so với 34,1% với Claude) → **model ảnh hưởng đáng kể**, chỉ so trong cùng model.

### Đọc kết quả

1. **v2 cải thiện mạnh trên dev (34 → 75%) nhưng chỉ nhích trên dữ liệu mới (45 → 52%, recall 52 → 55%)** — chênh lệch nằm trong khoảng tin cậy. Phần lớn cải thiện v2 **không chuyển sang** held-out 2, vì held-out 2 lộ ra **các nhóm lỗi mới**:

| Nhóm lỗi mới (held-out 2) | Frame | Ví dụ |
|---|---|---|
| Mất/hư hỏng tài sản khi cung cấp dịch vụ | 5 | "Bên B để mất mát, hư hỏng tài sản do lỗi của mình", "hàng gửi bị mất" — lexicon không có |
| Từ nhiễu trong ô qualifier → back-off `?` | 5 | qualifier = "vi phạm nghĩa vụ", "nghiêm trọng", "cố tình" |
| Quét câu bắt nhầm → **false merge** | 2 | K16: ô action = "bồi thường" (hậu quả) → quét câu → gặp "Bên A **giao** bảo vệ" → `DELIVER` |
| Vi phạm chất lượng dạng danh từ | 2 | "vi phạm về chất lượng hàng hóa", "đưa vật tư không đúng chủng loại" |
| Nhãn tranh cãi | 1–2 | "hết hạn mà vẫn không trả tiền" = `LATE` hay `NOT_PERFORMED`? |

2. **Tính an toàn gần như giữ được**: 1 false merge / 17 cặp dự đoán trên dữ liệu mới, và nguyên nhân cụ thể: **bước "quét cả câu" khi ô action chứa hậu quả** — đúng loại rủi ro đã thấy trên dev (D26), sửa được bằng cách chỉ quét phần trước hậu quả hoặc bỏ bước này.
3. **Đuôi dài (long tail)**: mỗi tập dữ liệu thật mới mở ra nhóm lỗi mới. Sau hai vòng, recall trên dữ liệu chưa thấy ~50–55%. Không thấy dấu hiệu hội tụ nhanh tới 80% chỉ bằng thêm luật.

### Đánh giá cổng

| Cổng | v2 trên held-out 2 | Đạt? |
|---|---|---|
| Cận dưới precision ≥ 95% | 73,0% (17 cặp) | Không (mẫu nhỏ; điểm 94,1%) |
| Recall ≥ 80% | 55,2% | **Không** |

### Kết luận cho định hướng AI2

- **Giữ**: nguyên tắc "LLM chỉ chép + chọn danh sách đóng; code tạo key; không chắc thì không gom". Trên dữ liệu thật, gom sai hiếm (1/17 và có nguyên nhân sửa được) — đủ an toàn để hiển thị cho người review.
- **Không nên** đặt kỳ vọng "tự gom đủ ≥ 80% điều khoản bằng lexicon/luật" cho bản đầu. Recall thực tế ~50%.
- **Hướng khả thi**: triển khai key graph như **lớp gợi ý độ chính xác cao** + **hàng đợi `UNMAPPED` cho người review** + **vòng tăng trưởng lexicon theo dữ liệu thật** (đúng cơ chế đã thiết kế ở bậc 7). Đo recall theo version lexicon trên hợp đồng thật của dự án thay vì mẫu công khai. Phần chưa map vẫn dùng so sánh văn bản hiện có (`clause_compare.py`) làm dự phòng.
- Việc tiếp theo có giá trị nhất **không phải thêm luật**, mà là: (1) dữ liệu hợp đồng thật của dự án, (2) người thứ hai gán nhãn, (3) bỏ/giới hạn bước quét cả câu để giữ precision.
