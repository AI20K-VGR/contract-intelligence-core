# Red-team: AI2 clause key (spike v0 → v2)

Ngày: 2026-10-01 · Lens: red-teamer · Đối tượng: `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md` + `evals/spikes/clause_key/` · Chế độ: chỉ đọc (không gọi LLM, không sửa file repo).

**Claim bị tấn công:** "giữ nguyên tắc an toàn; ship key graph như lớp gợi ý độ chính xác cao + hàng đợi UNMAPPED + vòng tăng trưởng lexicon; không kỳ vọng recall ≥ 80%".

**Kết luận ngắn:** Hướng "lớp gợi ý + hàng đợi review" vẫn hợp lý. Nhưng hai tiền đề của claim chưa được chứng minh. (1) "Không chắc thì không gom" hiện **không được code thực thi**: có ít nhất 4 đường biến sự không chắc chắn thành key xác định, gom được. Trên held-out 2, 5/19 key xác định bị sai; 0 false merge chỉ vì dữ liệu thưa. (2) `decide()` trả `DUPLICATE` khi cả hai giá trị đều không đọc được (`None == None`), và chưa hề được đo trên dữ liệu thật (`decision_end_to_end.n = 0` ở mọi lần chạy held-out). Ngoài ra, cách chấm cặp (pair) làm phồng precision và coverage.

---

## 1. Bảng phát hiện (xếp theo mức độ)

| ID | Mức | Trạng thái | Anchor | Cách sửa rẻ nhất |
|---|---|---|---|---|
| RT-01 | blocker | proven | `mechanism.py:529`, `:153`, `:205-206` | `DUPLICATE` chỉ khi cả hai `value` khác None và bằng nhau (cùng unit/base); còn lại → `NEEDS_REVIEW_UNPARSED`; frame PARAMETER dùng bộ so giá trị riêng |
| RT-02 | blocker | proven | `mechanism.py:397-405`, `:384-388`, `:413`; `lexicon_v2.json:76`, `:186` | Back-off thắng quét câu; bên có tên mà không resolve được → marker không gom; bỏ "không được" khỏi luật lật bên; chặn "giao" ghép, bỏ alias "thực hiện" |
| RT-03 | major | proven | report:248 vs `results/llm-full-v1-heldout-20261001-032856.json` | Sửa câu "19/19"; báo `accuracy_when_mapped` tách khỏi `key_accuracy` |
| RT-04 | major | proven | `run_spike.py:243`; `mechanism.py:500-502` | Tách coverage 3 lớp: key xác định / `?` / UNMAPPED; đưa `?` vào hàng đợi review |
| RT-05 | major | proven | `run_spike.py:172-186`, `:250-258`; `mechanism.py:52-59` | Căn 1-1 (Hungarian); chấm cả frame dự đoán thừa; bootstrap theo khoản/tài liệu; cổng theo frame/nhóm, không theo cặp |
| RT-06 | major | proven | report:316-323 | Báo riêng cặp trong-cùng-khoản và cặp khác-khoản |
| RT-07 | major | proven | `heldout2_sources.json`; report:312-317 | Held-out theo **bộ hồ sơ** (HĐ + phụ lục); chỉ chấm cặp trong cùng hồ sơ |
| RT-08 | major | proven | `import_heldout.py:83-89`; key = `(bearer, action, qualifier)` | Gold cho phép "obligation id"/object tự do; người thứ hai gán nhãn |
| RT-09 | major | proven | `mechanism.py:75`, `:102-104` | "ngày làm việc" là dim riêng; "trong vòng N" trong vế vi phạm → UNPARSED |
| RT-10 | major | proven | `docs/decisions.md:40` vs report:340-347 | Ghi DEC mới với cổng mới trước khi viết lại plan B/C |
| RT-11 | minor | proven | `git status` (`?? evals/spikes/`); `results/*.sha256`; `run_spike.py:168` | Commit nhãn + freeze trước mỗi lần chạy; nhúng hash + model id vào result JSON |
| RT-12 | minor | proven | K10 (`clauses_heldout2.jsonl`) ≈ H35 (`clauses_heldout.jsonl`) | Khử trùng lặp theo n-gram giữa các tập |
| RT-13 | minor | suspected `[ASSUMED]` | mtime `heldout2.csv` 03:37:01 < `mechanism.py`/`lexicon_v2.json` 03:42:04 | Người gán nhãn tách biệt, hoặc commit held-out sau khi đã freeze |
| RT-14 | minor | proven | `run_spike.py:164`, `:269`; `mechanism.py:153`; `lexicon_v2.json:49` | Ép kiểu span sang str; parse "10.5"; so sánh theo frame chứ không theo khoản; chặn "bên nhận" ghép |

---

## 2. Chi tiết và cách tái hiện

Mọi lệnh chạy từ repo root với tiền tố:
`PYTHONIOENCODING=utf-8 ai-service/.venv/Scripts/python.exe -c "from evals.spikes.clause_key.mechanism import *; ..."`

### RT-01 (blocker, proven): `decide()` báo `DUPLICATE` khi cả hai giá trị đều không đọc được

`mechanism.py:529`: `if ca["value"] == cb["value"] and rel == "IDENTICAL" and ca["period"] == cb["period"]: return "DUPLICATE"`. Khi parser trả `value=None` ở cả hai frame, `None == None` thành đúng, nên hai mức phạt **khác nhau** bị báo là trùng.

Kết quả probe với cùng key `("SELLER","DELIVER","LATE")` và điều kiện rỗng:

| Hậu quả A | Hậu quả B | `decide` |
|---|---|---|
| `phạt 5.000.000đ` | `phạt 10.000.000đ` | `DUPLICATE` (`_MONEY` không nhận hậu tố "đ" → value None) |
| `phạt tương đương 1 tháng tiền thuê` | `... 3 tháng tiền thuê` | `DUPLICATE` |
| `phạt gấp đôi` | `phạt gấp ba` | `DUPLICATE` |
| `phạt 1.000 USD` | `phạt 5.000 USD` | `DUPLICATE` |
| `chịu mọi trách nhiệm trước pháp luật` | `phải khắc phục toàn bộ hậu quả` | `DUPLICATE` (type None cả hai) |
| `None` | `None` (LLM bỏ sót consequence) | `DUPLICATE` |
| PARAMETER `Đơn giá: 12.000.000 đồng` | PARAMETER `Đơn giá: 15.000.000 đồng` | `DUPLICATE` (decide không đọc `value_text`) |

**Có xảy ra trên dữ liệu thật không:** có. Hậu tố "đ" xuất hiện 4 lần trong `clauses_heldout2.jsonl` (ví dụ K16 "10.000.000đ"). "tương đương với 02 tháng tiền thuê" có ở H06. Test hiện chỉ khẳng định trường hợp tốt (`test_clause_key_spike.py:224`: "10.000.000 đồng" vs "10 triệu đồng").

**Chưa từng được đo trên dữ liệu thật:** cả 4 lần chạy trong `results/claude-sonnet-4-6/` đều có `decision_end_to_end.n = 0`, vì held-out không có file comparisons. Bảng quyết định chỉ được kiểm trên 15 + 10 cặp giả lập.

**Tại sao nghiêm trọng:** với công cụ review, `DUPLICATE` nghĩa là "không cần nhìn". Đây là lỗi âm tính giả: một mức phạt bị phụ lục sửa lại có thể lọt qua review.

**Sửa:** `DUPLICATE` chỉ khi `type`, `value` (khác None), `unit`, `base`, `period` đều bằng nhau; nếu có value None → `NEEDS_REVIEW_UNPARSED`. Thêm `đ|usd` vào `_MONEY`. PARAMETER không đi qua `decide()` mà dùng bộ so `value_text` riêng. Thêm test âm cho từng dòng trong bảng trên.

### RT-02 (blocker, proven): "không chắc thì không gom" không được thực thi

Báo cáo (report:272, :345) nêu đây là "thuộc tính quan trọng nhất". Nhưng code có 4 đường biến sự không chắc chắn thành key xác định, gom được:

**(a) Quét cả câu chạy trước back-off** (`mechanism.py:397-405`): qualifier được tìm theo thứ tự `qualifier_text → action_text → scan`, và chỉ rơi về `?` khi quét cả câu không thấy gì. Vì vậy một qualifier của **bên khác** trong cùng câu có thể thay cho qualifier chưa biết:
```
t = "Bên Mua chậm thanh toán thì chịu lãi 0,05%/ngày; Bên Bán giao hàng sai chủng loại thì phải bồi thường."
frame = bearer "Bên Bán", action "giao hàng", qualifier "sai chủng loại"
→ ('SELLER','DELIVER','LATE')        # cùng frame nhưng câu đứng riêng → ('SELLER','DELIVER','?')
```

**(b) Bên có tên nhưng không resolve được** (`mechanism.py:384-388`) được thay bằng `default_bearer` của profile, hoặc `ANY_PARTY`. Comment trong code nói "No party named", nhưng code áp dụng cả khi câu **có** nêu tên bên:
```
LEASE, "Bên A chậm hoàn trả tiền đặt cọc quá 10 ngày thì phải chịu lãi 0,05%/ngày." (không có ctx)
→ ('LESSEE','PAY','LATE')   # trùng hệt key "bên thuê chậm trả tiền thuê" → gom sai
"Bên X ..." → ('ANY_PARTY','WARRANT',None) == key của "mỗi bên ..." (bên tương hỗ tường minh)
```
Test `test_clause_key_spike.py:464-466` ("Bên nào" → `ANY_PARTY`) khóa chặt hành vi này.

**(c) Câu cấm "X không được \<action\>" bị đọc thành bị động** (`mechanism.py:413`, và test `:271-274` khẳng định điều này):
```
"Bên Bán không được giao hàng trước thời hạn khi chưa có sự đồng ý của Bên Mua; ..." → ('BUYER','DELIVER','UNAUTHORIZED')
LEASE "Bên cho thuê không được bàn giao mặt bằng cho bên thứ ba; ..." → ('LESSEE','HANDOVER_ASSET',None)
```
Trong hợp đồng, "không được" thường là **câu cấm**, không phải bị động.

**(d) Alias quá ngắn/quá chung** vẫn khớp ngay trong ô action (layer 2), không cần bước quét câu. Vì vậy cách sửa mà báo cáo đề xuất (bỏ/giới hạn quét câu, report:348) không đóng được lỗ này:
```
"giao kết hợp đồng" / "chuyển giao công nghệ" / "giao dịch với bên thứ ba" / "giao nhiệm vụ" → ('SELLER','DELIVER',None)   # lexicon_v2.json:76 "giao"
"thực hiện công việc" / "thực hiện bảo trì định kỳ" / "thực hiện đào tạo" + "không đúng quy cách" → ('SUPPLIER','ANY_OBLIGATION','DEFECTIVE')   # lexicon_v2.json:186
```
Key generic chỉ được chặn khi gặp key **cụ thể** (`mechanism.py:504-506`). Generic gặp generic vẫn gom: "bảo trì" và "đào tạo" sẽ bị so như cùng một nghĩa vụ.

**Bằng chứng trên dữ liệu thật:** `results/claude-sonnet-4-6/llm-full-v2-heldout2-20261001-040925.json` có 25 key map được; 6 trong số đó là `?`. Trong 19 key xác định, **5 key sai**: `K06#0` (gold None → `OWNER, ANY_OBLIGATION, DEFECTIVE`), `K07#1`, `K16#0`, `K16#1`, `K21#0` (`ANY_PARTY, ANY_OBLIGATION, DEFECTIVE` qua alias "thực hiện" + quét câu). Chúng chưa tạo false merge khác khoản chỉ vì nhóm lớn nhất có 5 frame. Trên một corpus lớn, key sai sẽ gặp đúng "tên trùng" của nó và bị gom.

**Sửa:** (a) chỉ quét câu khi cả `qualifier_text` lẫn `action_text` đều rỗng, và chỉ quét trong vế của chính frame; ô qualifier có chữ mà không nhận ra thì luôn là `?`. (b) Tên bên có mà không resolve được → marker `UNRESOLVED`, không bao giờ gom; phân biệt với `ANY_PARTY` tường minh. (c) Chỉ lật bên khi sau "được" có tác nhân, hoặc bỏ "không được" khỏi regex. (d) Thêm `compounds_block` cho "giao" (kết, dịch, nhiệm vụ, chuyển giao…), bỏ alias "thực hiện". (e) Đưa **tỷ lệ key xác định bị sai** vào cổng, thay cho việc dựa vào đếm false merge.

### RT-03 (major, proven): báo cáo ghi sai "19/19 map đúng"

Report:248 viết: "Mọi frame được map đều map đúng (19/19). Mọi lỗi đều rơi vào `UNMAPPED` hoặc `?`". Trong khi `results/llm-full-v1-heldout-20261001-032856.json` ghi `accuracy_when_mapped = 15/19`, `wrong_mapped_ids = [H12#0, H24#0, H25#0, H30#0]`. Trong đó H24, H25, H30 là key **xác định** với bên sai (`ANY_PARTY` thay cho `SUPPLIER`/`OWNER`), đúng cơ chế RT-02(b). Số 19 trong "Key đúng 19/44" đã tính cả 4 frame UNMAPPED đúng. Kết luận an toàn của mục held-out dựa một phần vào câu sai này.

### RT-04 (major, proven): coverage tính `?` là "đã map"

`run_spike.py:243` định nghĩa `mapped = pred_key is not None`, nên key có `?` cũng được tính. Held-out 2 v2 báo coverage 80,6% (25/31), nhưng 6 frame là `?` và không bao giờ được gom, nên coverage dùng được là **19/31 = 61,3%**. `accuracy_when_mapped` thực tế là 14/25 = 56%. Thêm nữa, frame `?` gặp frame có head khác thì `decide()` trả `None` (`mechanism.py:500-502`). Theo code spike, frame đó không được gom, cũng không có hàng đợi nào nhận. `[ASSUMED]` thiết kế "UNMAPPED queue" chưa nói `?` đi về đâu.

### RT-05 (major, proven): cách chấm cặp làm phồng precision

1. **Chỉ chấm frame đã căn với gold.** Frame dự đoán thừa không bao giờ vào `pred_same`. Held-out 1 v2 (Claude): `frames_returned = 70` so với 44 dòng gold. Held-out 2 v2: 37 so với 31. Khi chạy thật, mọi frame đều được gom, nên false merge từ phần thừa này hoàn toàn không được đo.
2. **Căn nhiều-một** (`run_spike.py:172-186`, dùng `max` theo độ trùng từ, không ràng buộc 1-1): hai frame gold cùng khoản có thể lấy **cùng một** frame dự đoán, và cặp đó tự động tính là gom đúng. Held-out 2 v1: 4 cặp như vậy, 3 cặp được tính là gom đúng (3/15 số cặp đúng).
3. **Wilson trên cặp giả định các cặp độc lập**, nhưng số cặp tăng theo bình phương cỡ nhóm. Test v1 `llm-full` có 70/70 cặp, đến từ 9 nhóm; riêng nhóm 9 frame đã chiếm 36 cặp (51%). Bootstrap theo khoản trên held-out 2 v2 cho precision 95% CI **[0,63; 1,00]**, so với Wilson [0,73; 0,99] trong báo cáo. Cổng "≥ 120 cặp" có thể đạt chỉ bằng cách thêm 7 frame vào một nhóm có sẵn.

### RT-06 (major, proven): v2 không cải thiện cặp khác-khoản trên dữ liệu mới

Tách held-out 2 theo cặp:

| | v1 (Claude) | v2 (Claude) |
|---|---|---|
| Cặp trong cùng khoản (đúng/dự đoán/gold) | 5/6/7 | 6/7/7 |
| Cặp khác khoản (đúng/dự đoán/gold) | 10/10/22 | 10/10/22 |
| Cặp khác tài liệu | 9/9/21 | 9/9/21 |

Report:316-323 viết recall "52 → 55%". Thực tế toàn bộ phần tăng là **một cặp trong cùng khoản** (tách hậu quả kép). Việc gom giữa các khoản khác nhau, đúng là mục đích của key graph, **không đổi**. Cặp trong-cùng-khoản cũng là nơi duy nhất có false merge (K16).

### RT-07 (major, proven): eval không đo đúng điều kiện triển khai

Held-out 2 có 29 cặp gold: 7 cặp trong cùng khoản, **1** cặp khác khoản trong cùng tài liệu, và 21 cặp khác tài liệu (13 URL, trộn nhiều profile). Nhóm gold `('ANY_PARTY','ANY_OBLIGATION',None)` ở held-out 1 gom H06/H34/H35 (LEASE) với H17/H18 (SUPPLY_SERVICE). Recall/precision vì vậy đo "key nhất quán giữa các mẫu công khai". Đây là proxy chấp nhận được cho chất lượng chuẩn hóa. Nhưng trường hợp gây hại khi triển khai, tức gom sai **trong một bộ hồ sơ** (thân HĐ và phụ lục) dẫn tới conflict giả trước mặt người review, chỉ có n ≈ 1.

### RT-08 (major, proven): schema gold trùng schema dự đoán, nên lỗi schema không nhìn thấy được

`import_heldout.py:83-89` từ chối mọi nhãn ngoài enum lexicon. Key không có object. Probe: LEASE "Bên thuê chậm thanh toán tiền thuê" và "Bên thuê chậm thanh toán tiền điện, nước" đều ra `('LESSEE','PAY','LATE')`, và `decide` sẽ so hai mức chế tài của hai nghĩa vụ khác nhau. Người gán nhãn (cũng là người thiết kế) sẽ gán cùng key đó, nên cặp này được tính là **gom đúng**. Metric không thể phát hiện key quá thô.

### RT-09 (major, proven): đại số điều kiện có tương đương sai

- `parse_condition("quá 15 ngày làm việc") == parse_condition("quá 15 ngày")`, cả hai là `Interval(days, lo=16)` nên `decide` trả `DUPLICATE`. Ngày làm việc không phải ngày lịch. Dữ liệu thật: "ngày làm việc" 3 lần ở held-out 1 (H01, H02, H03).
- `"không khắc phục trong vòng 14 ngày"` được parse thành `hi=14` (≤14), trong khi vi phạm thực ra xảy ra **sau** 14 ngày. Đem so với `"quá 30 ngày"` thì được `GRADUATED` (sai; đúng ra là lồng/chồng). "trong vòng N" có 3 lần trong held-out (H02, H03, K16).

### RT-10 (major, proven): đổi cổng mà không ghi quyết định

`docs/decisions.md:40` (DEC-dungskbg2004-2) chốt: chọn kiến trúc **sau** spike, với cổng precision ≥ 95%, recall ≥ 80%, dữ liệu "synthetic + real anonymized". Mọi lần chạy trên dữ liệu thật đều trượt cả hai cổng (held-out 2 v2: cận dưới 73,0%, recall 55,2%). Dữ liệu dùng là mẫu công khai, không phải HĐ dự án đã ẩn danh. Report:345-347 vẫn khuyến nghị triển khai, dưới dạng lớp gợi ý. Đây là đổi cổng ngầm. Cần một DEC mới với cổng mới đo được (ví dụ tỷ lệ key xác định sai, false-DUPLICATE = 0 trên bộ hồ sơ thật) trước khi viết lại plan B/C.

### RT-11 (minor, proven): kỷ luật freeze dựa vào tự khai

- `evals/spikes/` chưa được track (`git status`: `?? evals/spikes/`). Các file `results/*.sha256` sửa được và không có dấu thời gian đáng tin; mtime trên OneDrive cũng không chắc chắn.
- Result JSON không ghi model id, cũng không ghi hash của mechanism/prompt (chỉ có tag `lexicon`/`prompt`). Các lần chạy gpt-4o ở `results/` gốc không có dấu model nào.
- Dòng "v1" trên Claude (04:04–04:08) chạy với `mechanism.py` hash `8218658…` (= `v2-freeze.sha256`), không phải `84fc85…` (`v1.1-freeze.sha256`). Nó còn dùng `split_consequences` của v2 trong `run_spike.py:168`. Vì vậy chênh lệch "v1 → v2" chỉ phản ánh lexicon + prompt, không phải toàn bộ v2.
- `heldout-labels.sha256` không khóa `clauses_heldout.jsonl`. Tôi đã kiểm: import lại `heldout.csv`/`heldout2.csv` cho kết quả **trùng khớp** với jsonl, nên hiện tại không có drift.

### RT-12 (minor, proven): trùng lặp gần giữa hai held-out

K10 (held-out 2) và H35 (held-out 1, tập dev của v2) trùng 66% 4-gram ("vi phạm nghiêm trọng nghĩa vụ thì Bên còn lại có quyền đơn phương chấm dứt thực hiện hợp đồng và yêu cầu bồi thường thiệt hại"). Trường hợp này không làm phồng điểm vì K10 ra `?`, nhưng mẫu công khai hay chép nhau, nên cần khử trùng lặp.

### RT-13 (minor, suspected `[ASSUMED]`)

Held-out 2 được ghi lúc 03:37:01. `mechanism.py` và `lexicon_v2.json` được sửa lần cuối lúc 03:42:04, bởi cùng tác nhân đã đọc cả 22 khoản. Tôi không tìm thấy alias v2 nào chỉ xuất hiện ở held-out 2: mọi alias mới đều có trong H1. Vì vậy chưa chứng minh được rò rỉ; đây chỉ là rủi ro quy trình.

### RT-14 (minor, proven): độ bền

- `llm_extract` gọi `fold(v)` trên span không phải chuỗi. LLM trả `"value_text": 12000000` là `TypeError: normalize() argument 2 must be str, not int`, làm hỏng cả lần chạy (`run_spike.py:164`).
- `parse_consequence("phạt 10.5 triệu đồng")` cho value `5000000`.
- `by_clause = {r["clause"]: r ...}` (`run_spike.py:269`) chỉ giữ frame **cuối** của mỗi khoản. Hiện vô hại vì test/dev có 1 frame/khoản, nhưng sẽ sai lặng lẽ nếu thêm comparisons cho held-out.
- Cổng "nguyên văn" chỉ kiểm chuỗi con: span một từ ("giao", "chậm", "phạt") lấy từ vế của bên khác vẫn qua. Cổng này không kiểm việc span thuộc về frame nào.
- `_role`: "Bên nhận hàng" / "Bên nhận tiền" → `RECIPIENT` (vai trò NDA) vì chứa "bên nhận" (`lexicon_v2.json:49`).

---

## 3. Các đường không đảo ngược được (xếp trước)

1. **False `DUPLICATE`** (RT-01, RT-09). Người review tin "trùng" và bỏ qua, nên một chế tài bị phụ lục sửa không bị bắt trước khi ký. Đây là lỗi âm tính giả duy nhất trong thiết kế có thể dẫn tới hậu quả pháp lý thật, trong khi báo cáo chưa từng đo `decide()` trên dữ liệu thật.
2. **Gán nhầm bên** (RT-02b/c). Chế tài của Bên Bán hiển thị như của Bên Mua. Vẫn phục hồi được nếu người review đọc trích dẫn, nhưng lỗi này làm giảm niềm tin vào lớp gợi ý.
3. False merge thường (RT-02a/d) sinh conflict giả. Phục hồi được (tốn công review), nhưng số lượng sẽ tăng theo kích thước corpus, và metric hiện tại không thấy được.

## 4. Rủi ro còn lại (chấp nhận có điều kiện)

- **Oracle `context_parties`:** held-out cung cấp vai trò của bên do người gán nhãn nhập. Khi chạy lại normalize trên span đã lưu của held-out 2 v2 mà bỏ ctx, số key đúng vẫn là **16/31** (tái hiện 30/31 dòng). Oracle không làm phồng kết quả ở tập này, nên chấp nhận được, với điều kiện đo lại khi có bộ resolve bên thật.
- **Độ nhạy theo model** (gpt-4o 43,2% vs Claude 34,1% trên cùng tập): chấp nhận được nếu mỗi phiên bản lexicon được đo lại khi đổi model, và ghi model id vào kết quả.
- **Tương tác với `clause_compare.py`** `[ASSUMED]`: module này căn theo "Điều N" giữa thân HĐ và phụ lục, và tự sinh `COMPARABLE_DIFFERENCE`. Báo cáo chưa nói gì khi cả hai lớp cùng ra kết luận khác nhau cho một cặp; parser số lượng cũng khác nhau (`QUANTITY_RE` nhận "(mười lăm)", USD; `_MONEY`/`_UNIT` thì không). Chấp nhận nếu có quy tắc gộp/ưu tiên rõ ràng.
- **Vòng tăng trưởng lexicon:** mỗi alias thêm vào có thể đưa lại lỗi kiểu "giao"/"thực hiện". Chấp nhận nếu mỗi lần thêm alias phải qua hồi quy tỷ lệ key xác định sai trên một tập đóng băng.
- **OCR, câu dài nhiều mệnh đề:** chưa được kiểm.

## 5. Bổ sung (vòng probe thêm)

### RT-15 (minor, proven): `CONFLICT_CANDIDATE` bật theo từ khóa ở bất kỳ đâu trong khoản

`mechanism.py:522` tìm `_EXCLUSIVE` ("chỉ được", "duy nhất"…) trên **toàn bộ** `text` của khoản, không giới hạn ở vế chế tài. Ví dụ: "Bên Bán **chỉ được** giao hàng sau khi Bên Mua thanh toán đợt 1; nếu giao chậm phải bồi thường thiệt hại." đặt cạnh một khoản "…có quyền chấm dứt hợp đồng" cho ra `CONFLICT_CANDIDATE`. Lỗi này là dương tính giả: tạo nhiễu cho người review nhưng phục hồi được. **Sửa:** chỉ tìm cue loại trừ trong `consequence_text` hoặc trong mệnh đề chứa hậu quả.

### RT-16 (minor, proven): `split_consequences` bỏ sót danh sách dấu phẩy và "hoặc"

`mechanism.py:469` chỉ tách theo "và"/"đồng thời". Hai trường hợp không tách đúng:
- "chịu phạt 8% giá trị hợp đồng, bồi thường thiệt hại và chấm dứt hợp đồng" chỉ ra 2 phần, trong đó "phạt 8%…, bồi thường…" vẫn dính nhau.
- "chịu phạt 8% … **hoặc** bồi thường thiệt hại" (lựa chọn thay thế, không cộng dồn) giữ nguyên một frame.

Với frame dính, `parse_consequence` lấy cue đầu tiên theo thứ tự `_TYPE_CUES`, nên có thể ra `DAMAGES` kèm value 8%: sai cả loại lẫn giá trị. Đây đúng là nhóm lỗi 3 mà held-out 1 đã nêu, nhưng mới được vá một phần. **Sửa:** tách thêm theo dấu phẩy khi mỗi phần có cue riêng. Với "hoặc", giữ quan hệ lựa chọn (không coi là `CUMULATIVE`).
