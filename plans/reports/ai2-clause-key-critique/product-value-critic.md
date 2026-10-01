# Lens: product-value-critic — AI2 clause key → graph → so sánh tất định

Ngày: 2026-10-01 · Chế độ: read-only, advisory · Artifact: định hướng "lớp gợi ý độ chính xác cao + hàng đợi `UNMAPPED` + vòng tăng trưởng lexicon" (`plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md:343-348`).

Câu hỏi của lens: định hướng này có làm ra thứ người rà soát thật sự cần không, và nó có biết vì sao không? Không đánh giá tính khả thi kỹ thuật (lens tech) hay thị trường (lens market).

## 0. Việc người dùng cần làm (JTBD) theo tài liệu sản phẩm

| Nguồn | Nội dung |
|---|---|
| `docs/ai2/AI2-DOC-01-product-vision.vi.md:15` | Người dùng chính: "Chuyên viên mua hàng / rà hợp đồng", việc cần làm: "So giá, MST, phạt, thanh toán **giữa thân và phụ lục**" |
| `AI2-DOC-01:9` | "Người rà soát tìm đúng chỗ khác biệt hoặc thiếu chứng, không đọc hết từng file" |
| `AI2-DOC-01:36-37` | Mục tiêu: "Giảm thời gian tìm cặp nội dung cần đối chiếu"; "Không biến thiếu phụ lục thành 'không có rủi ro'" |
| `AI2-DOC-01:43` | Phạm vi: "1 hợp đồng + 0..n phụ lục", so thân↔phụ lục và trong một tài liệu |
| `AI2-DOC-01:47-49` | "Giả thuyết (**chưa phỏng vấn user**)" H1–H3 |
| `brainstorm…:15` | Vấn đề gốc: "giao hàng chậm" (Điều 9) và "chậm trễ bàn giao" (Điều 12) không được ghép; "không có timeline giá trị theo phụ lục" |

JTBD rút ra: *"Khi nhận một hồ sơ gồm hợp đồng và nhiều phụ lục, tôi muốn biết nhanh giá trị/điều khoản nào đã bị đổi hoặc mâu thuẫn giữa các file, kèm nguồn mở được, để tôi không phải đọc hết mà vẫn không bỏ sót."* Trọng tâm là **thân↔phụ lục** và **trong một hồ sơ**.

## 1. Bảng phát hiện (xếp theo mức độ)

| ID | Mức độ | Trạng thái | Neo | Giá trị bị đe dọa |
|---|---|---|---|---|
| PV-1 | blocker | proven | `AI2-DOC-01:15`; `heldout.csv`/`heldout2.csv` (75/75 frame là `REMEDY`, 0 câu nhắc "phụ lục"); `brainstorm…:97` | Việc must-have (so giá trị thân↔phụ lục, timeline) không có trong bằng chứng dẫn tới định hướng |
| PV-2 | major | proven (đếm) / suspected (suy tỷ lệ) | `run_spike.py:247-258`; held-out 2: 29 cặp gold → 21 khác hợp đồng, 7 cùng một câu, **1** khác điều trong cùng tài liệu | Con số "~94% precision / ~50–55% recall" đo tính nhất quán key trên cả kho mẫu, không đo số cặp người rà sẽ thấy trong một hồ sơ |
| PV-3 | major | proven | `AI2-DOC-01:47`; `AI2-DOC-01:36`; `spike…:195-196, 232` | Không có bằng chứng từ người dùng; không có chỉ số giá trị ở mức người rà (thời gian, phát hiện bị bỏ sót) |
| PV-4 | major | proven (thiếu đặc tả) / suspected (rủi ro hành vi) | `spike…:341` (recall 55,2% [37,5; 71,6]); `spike…:347`; `AI2-DOC-01:37`; `AI2-DOC-03:42` | Cảm giác "đã rà đủ": danh sách cảnh báo chỉ phủ khoảng một nửa, không có chỉ số độ phủ theo hồ sơ |
| PV-5 | major | proven | `spike…:347` ("vòng tăng trưởng lexicon"); `AI2-DOC-01:13-16`; `AI2-DOC-01:45`; `AI2-DOC-02:78`; `brainstorm…:123` | Một trong ba trụ của định hướng không có người thực hiện trong mô hình người dùng |
| PV-6 | major | proven | `brainstorm…:50`; `spike…:171, 195`; bảng held-out `spike…:237-244, 312-317` (không có dòng "quyết định") | Nhãn `GRADUATED`/`DIFFERENT_REMEDY` ẩn một cặp khỏi hàng cảnh báo; độ đúng của nhãn này chưa đo trên dữ liệu thật |
| PV-7 | major | suspected `[ASSUMED]` | `spike…:255` (nhóm 2: chế tài nằm dưới "Điều 5. Phạt vi phạm"); `spike…:334` | Tổng công sức có thể tăng: người rà vẫn đọc hàng đợi `UNMAPPED` + xem gợi ý, trong khi việc so chế tài trong một Điều vốn đã rẻ |
| PV-8 | minor | suspected `[ASSUMED]` | `brainstorm…:25` (R3 phủ 6 profile); `AI2-DOC-01:15`; `spike…:231` (0 frame `EMPLOYMENT`) | Dàn trải 6 profile trước khi biết hồ sơ thí điểm thuộc profile nào |
| PV-9 | minor | proven | `spike…:345` ("đủ an toàn để hiển thị"); `spike…:347` ("độ chính xác cao"); `spike…:340` (cận dưới 73,0%, n=17) | Tính từ không có ngưỡng: "cao", "đủ an toàn" chưa quy về số lỗi chấp nhận được trên mỗi hồ sơ |

### PV-1 — Việc must-have không được kiểm chứng (blocker, proven)

- Người dùng chính theo `AI2-DOC-01:15` cần so "giá, MST, phạt, thanh toán giữa thân và phụ lục". Brainstorm cũng nêu thiếu "timeline giá trị theo phụ lục" là một vấn đề gốc (`brainstorm…:15`), và vòng 1 của phương án 3 gồm `PARAMETER` + `REMEDY` + timeline (`brainstorm…:97`).
- Toàn bộ held-out mà định hướng dựa vào chỉ có `REMEDY`: held-out 1 có 44/44 frame `REMEDY`, held-out 2 có 31/31; không câu nào nhắc "phụ lục" (đếm trực tiếp trong `evals/spikes/clause_key/heldout*.csv`). Nguồn là mẫu hợp đồng đơn lẻ trên web (`spike…:229, 293`), không phải hồ sơ có phụ lục.
- Hệ quả: định hướng ở `spike…:347` là kết luận về **chế tài trong văn bản mẫu**, không phải về việc người dùng thuê AI2 để làm. Theo Kano, so giá trị thân↔phụ lục là must-have; gom chế tài giữa các Điều là performance; phân loại `GRADUATED`/`CONFLICT_CANDIDATE` là delighter. Công sức đang dồn vào hai lớp sau trong khi lớp đầu chưa có số đo.
- Sửa: tách định hướng thành hai quyết định. (a) `PARAMETER` + timeline thân↔phụ lục cần spike/đo riêng trên hồ sơ có phụ lục. (b) Key graph cho `REMEDY` chỉ là lớp bổ sung. Không coi kết quả spike là đã chọn xong hướng cho AI2.

### PV-2 — Chỉ số spike không phải chỉ số người rà thấy (major)

- `run_spike.py:247-258` tính cặp trên **mọi tổ hợp của cả tập**, tức là ghép điều khoản của các hợp đồng khác nhau. Người rà chỉ làm việc trong một hồ sơ (`AI2-DOC-01:43`; `AI2-15:83-87`; `AI2-15:106-107` "không mở sang hồ sơ độc lập").
- Đếm lại gold theo nguồn (`heldout*_sources.json`):
  - Held-out 2 (13 tài liệu): 29 cặp gold = **21 khác hợp đồng**, 7 là hai hậu quả trong **cùng một câu** (ví dụ K03 "chậm 10 ngày phạt 5tr; quá 10 ngày thanh lý"), và chỉ **1** cặp nằm ở hai điều khác nhau trong cùng tài liệu. Đây mới là trường hợp của bài toán gốc (Điều 9 vs Điều 12).
  - Held-out 1 (18 tài liệu): 52 cặp gold = 29 khác hợp đồng, 8 cùng câu, 15 khác điều cùng tài liệu.
- Hai cặp cùng câu thì người rà vốn đã đọc chung. Như vậy trên 31 tài liệu thật, chỉ có khoảng 16 cặp mà việc gom key tạo ra giá trị mới. `[ASSUMED]`: held-out chỉ lấy một phần điều khoản của mỗi hợp đồng nên con số này thấp hơn thực tế. Chính điều đó cho thấy **tỷ lệ gặp bài toán trong một hồ sơ chưa được đo**.
- Sửa: định nghĩa lại chỉ số chính là "số cặp liên quan trong một hồ sơ được gợi ý / tổng số cặp liên quan trong hồ sơ đó", đo trên hồ sơ trọn vẹn (thân + phụ lục), và báo thêm số cặp liên quan trung bình trên mỗi hồ sơ.

### PV-3 — Không có bằng chứng từ người dùng, không có chỉ số giá trị (major, proven)

- `AI2-DOC-01:47`: các giả thuyết sản phẩm "chưa phỏng vấn user". Mục tiêu "Giảm thời gian tìm cặp" (`AI2-DOC-01:36`) chưa có mốc hiện tại và chưa có đích.
- Mọi số trong spike đều là số kỹ thuật (key/pair/consequence). Nhãn gold do cùng một tác giả gán (`spike…:196, 232`). D-A10 là một người duyệt, và người đó là chủ dự án, chưa phải người rà mục tiêu.
- Bằng chứng còn thiếu (phải lấy từ người dùng, spike không trả lời được):
  1. Một hồ sơ thực tế có bao nhiêu phụ lục, phụ lục thường đổi gì (giá, số lượng, tiến độ, chế tài).
  2. Người rà đã từng bỏ sót hoặc phải leo thang loại khác biệt nào, xếp theo tần suất và thiệt hại.
  3. Người rà chịu được bao nhiêu cảnh báo sai trên mỗi hồ sơ; có chấp nhận độ phủ một phần không nếu được công khai.
  4. Thời gian rà một hồ sơ hiện nay (mốc cho mục tiêu `AI2-DOC-01:36`).
  5. Phân bố profile trong hồ sơ thí điểm.
- Sửa: 3–5 hồ sơ thật ẩn danh của người dùng thí điểm, kèm một buổi think-aloud: người rà đánh dấu tay các cặp cần đối chiếu. Dùng đó làm gold mức hồ sơ và làm mốc thời gian.

### PV-4 — Rủi ro "tưởng đã đủ" (major)

- Recall trên dữ liệu mới là 55,2% [37,5; 71,6] (`spike…:341`). Định hướng gồm ba phần (`spike…:347`) nhưng không có phần nào công khai **độ phủ theo hồ sơ**.
- Nguyên tắc sản phẩm yêu cầu điều ngược lại: "Không biến thiếu phụ lục thành 'không có rủi ro'" (`AI2-DOC-01:37`), "Thành công **không** nghĩa người đã rà xong" (`AI2-DOC-03:42`).
- `[ASSUMED]`: khi thấy danh sách "3 cặp cần rà", người rà có xu hướng coi phần còn lại là sạch. Hàng đợi `UNMAPPED` chỉ bù được nếu nó hiện ngang hàng với cảnh báo, không nằm ở tab phụ.
- Sửa: bắt buộc hiện dòng độ phủ trên mỗi hồ sơ, ví dụ "đã so X/Y frame chế tài; Z chưa so được (xem hàng đợi)". Không bao giờ hiện trạng thái rỗng kiểu "không có mâu thuẫn". Frame `UNMAPPED` và frame back-off `?` được tính là một evidence issue loại "chưa so được", không phải im lặng.

### PV-5 — Vòng tăng trưởng lexicon không có người vận hành (major, proven)

- Người dùng trong `AI2-DOC-01:13-16` chỉ gồm người rà và người nhận bàn giao. Phạm vi loại trừ "học từ một lần sửa của người dùng" (`AI2-DOC-01:45`). BRD cấm "Một lần sửa người dùng tự đổi rule/gold" (`AI2-DOC-02:78`). Câu hỏi "Ai duyệt lexicon" vẫn còn mở (`brainstorm…:123`).
- Định hướng lại dựa vào vòng này để recall tăng từ ~50% (`spike…:347-348`), và chính spike cũng nói mỗi tập dữ liệu mới mở ra nhóm lỗi mới (`spike…:334`). Không có người vận hành thì recall đứng yên, và hàng đợi `UNMAPPED` trở thành chi phí cố định của người rà.
- Sửa: đặt tên vai trò "người biên tập lexicon", nêu tần suất và SLA, và chỉ đưa vòng này vào phạm vi khi đã có người nhận. Nếu chưa có, ghi rõ recall là tĩnh ở mức ~50% và đánh giá giá trị với con số đó.

### PV-6 — Nhãn làm ẩn cặp khỏi người rà chưa được đo trên dữ liệu thật (major, proven)

- Typology quy định "`GRADUATED` / `DIFFERENT_REMEDY` — **không phải conflict**" (`brainstorm…:50`). Nghĩa là một cặp bị gắn nhãn này sẽ không vào hàng cảnh báo. Gắn sai `GRADUATED` thì cặp đó bị bỏ lỡ mà vẫn mang nhãn trông rất chắc chắn.
- Bảng quyết định end-to-end chỉ được đo trên 15 cặp giả lập: 93,3% (`spike…:171`), và tập test đó "đã bị nhìn" (`spike…:195`). Các bảng held-out thật (`spike…:237-244, 312-317`) không có dòng quyết định. Lỗi v0 cho thấy chính loại nhãn này dễ sai: 4/15 cặp bị gắn nhầm `GRADUATED`/`CUMULATIVE` (`spike…:65-68`).
- Sửa: với người rà, precision cần đo trên **disposition** chứ không chỉ trên cặp key. Nhãn làm giảm cảnh báo (`GRADUATED`, `DUPLICATE`, `NOT_COMPARABLE`) cần ngưỡng cao hơn nhãn làm tăng cảnh báo, hoặc vẫn phải hiện cặp đó ở dạng "đã phân loại, bấm để xem".

### PV-7 — Công sức ròng có thể âm (major, suspected `[ASSUMED]`)

- Spike cho thấy hợp đồng thật thường gom chế tài dưới một Điều ("Điều 5. Phạt vi phạm", `spike…:255`). Nếu đúng như vậy, người rà so chế tài trong một hồ sơ chỉ bằng cách đọc một Điều, nên phần việc tiết kiệm được là nhỏ.
- Với recall ~50%, người rà vẫn phải đọc (a) các gợi ý, (b) hàng đợi `UNMAPPED`/`?`, và (c) chính Điều chế tài để kiểm tra phần không được gợi ý. Đây là ba bề mặt thay cho một.
- Hàng đợi có thể không quá dài ở quy mô thí điểm (vài chục frame `REMEDY`/hồ sơ, `[ASSUMED]`). Rủi ro chính vì thế không phải "mỏi vì hàng đợi" mà là "không bớt được việc".
- Sửa: đo A/B trên 3–5 hồ sơ thật (rà tay so với rà có gợi ý), ghi thời gian và số cặp bỏ sót. Nếu chênh lệch nằm trong nhiễu thì hạ `REMEDY` key graph xuống vòng 2.

### PV-8 — Dàn trải 6 profile (minor, suspected `[ASSUMED]`)

- R3 "Phủ cả 6 profile" (`brainstorm…:25`) đi cùng người dùng là chuyên viên mua hàng (`AI2-DOC-01:15`). `EMPLOYMENT` có 0 frame held-out (`spike…:231`), `NDA` có 3. `EMPLOYMENT` và `NDA` ít liên quan tới việc mua hàng `[ASSUMED]`.
- Sửa: xếp profile theo tần suất trong hồ sơ thí điểm và làm sâu 1–2 profile (có thể là `SALES`/`SUPPLY_SERVICE` hoặc `CONSTRUCTION_WORK`) trước khi làm rộng.

### PV-9 — Tính từ thay cho ngưỡng (minor, proven)

- "lớp gợi ý **độ chính xác cao**" (`spike…:347`) và "**đủ an toàn** để hiển thị" (`spike…:345`) dựa trên 16/17 cặp; cận dưới Wilson là 73,0% (`spike…:340`).
- Sửa: quy đổi sang ngưỡng người rà cảm nhận được, ví dụ "≤ 1 cảnh báo sai trên mỗi hồ sơ, đo trên N hồ sơ". Tránh dùng tỷ lệ cặp trên cả kho mẫu.

## 2. Giả định rủi ro nhất

> **Trong một hồ sơ, các cặp điều khoản cùng nghĩa vụ mà người rà cần đối chiếu nằm rải rác ở những Điều hoặc file khác nhau, đủ thường xuyên và đủ khó tìm tay, để một lớp gợi ý phủ ~50% (kèm hàng đợi phần còn lại) giúp giảm thời gian rà mà không làm người rà bớt cẩn thận.**

- Bằng chứng hiện có: không có bằng chứng từ người dùng (`AI2-DOC-01:47`). Bằng chứng gián tiếp nghiêng về phía giả định **sai** đối với phần trong-một-tài-liệu: 1/29 cặp gold ở held-out 2 là khác điều cùng tài liệu, và chế tài thường gom trong một Điều (`spike…:255`). Kết luận này chỉ là `[ASSUMED]` vì held-out lấy mẫu một phần.
- Nếu giả định sai: AI2 thêm ba bề mặt (gợi ý, hàng đợi, vòng lexicon) cho một việc người rà làm nhanh bằng tay. Trong lúc đó việc must-have (giá trị thân↔phụ lục, timeline theo DEC-dungskbg2004-1) bị lùi lại, và recall ~50% có thể tạo cảm giác đã rà đủ, trái với `AI2-DOC-01:37`.
- Kiểm tra rẻ nhất: 3–5 hồ sơ thật (thân + phụ lục) của người dùng thí điểm; người rà đánh dấu tay mọi cặp cần đối chiếu; đếm xem bao nhiêu cặp là (a) giá trị thân↔phụ lục, (b) chế tài khác Điều, (c) chế tài cùng Điều. Tỷ lệ (b) sẽ quyết định key graph có đáng làm ở vòng 1 hay không.

## 3. Lát cắt nhỏ nhất có giá trị

1. **Thân↔phụ lục, `PARAMETER` + timeline** (giá, số lượng, thanh toán, mức phạt dạng số) cho 1–2 profile phổ biến nhất trong hồ sơ thí điểm. Luôn để `NEEDS_REVIEW` (DEC-dungskbg2004-1). Đây là must-have trực tiếp theo `AI2-DOC-01:15`.
2. **Dòng độ phủ trên mỗi hồ sơ** (PV-4). Chi phí thấp, và chính nó hiện thực hóa nguyên tắc `AI2-DOC-01:37`.
3. **`REMEDY` key graph chỉ trong phạm vi một hồ sơ**, chỉ gợi ý khi cả hai phía đều map được, và nhãn làm giảm cảnh báo vẫn hiển thị (PV-6). Chỉ đưa vào khi bước kiểm tra ở §2 cho thấy cặp loại (b) chiếm tỷ lệ đáng kể.
4. **Vòng lexicon**: để ngoài phạm vi cho tới khi có người nhận vai trò (PV-5).

## 4. Phần giá trị đứng vững

- Nguyên tắc "không chắc thì không gom" giữ được trên dữ liệu thật: 0 và 1 lần gom sai (`spike…:244, 317`). Lỗi rơi vào trạng thái "chưa so được" thay vì thành mâu thuẫn giả, khớp với nguyên tắc sản phẩm "thiếu nguồn hoặc ngữ cảnh thì nêu thiếu, không suy đoán" (`AI2-DOC-01:62`). Đây là thuộc tính quan trọng nhất đối với niềm tin của người rà và nên được giữ bất kể chọn hướng nào.

## 5. Rủi ro còn lại có thể chấp nhận (kèm điều kiện)

| Rủi ro | Chấp nhận khi |
|---|---|
| Recall ~50% cho `REMEDY` | Độ phủ được hiện trên từng hồ sơ và phần chưa so có mặt ở cùng màn hình (PV-4) |
| Một người gán nhãn (D-A10) | Gold mức hồ sơ do người rà mục tiêu đánh dấu, không phải do tác giả cơ chế |
| Long tail lexicon | Có người biên tập được đặt tên; recall được theo dõi theo từng version lexicon trên hồ sơ thật |

Ngoài lens: độ khó kỹ thuật của việc tách span, chọn model và chi phí LLM để lens tech xử lý; khác biệt so với công cụ rà hợp đồng khác để lens market xử lý.
