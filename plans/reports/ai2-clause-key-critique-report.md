# Critique — Cơ chế AI2 clause key (frame → key → graph → so sánh)

Ngày: 2026-10-01 · Chế độ: advisory (không ghi `critique-consensus.json`) · Đường chạy: `inline-Task fallback` (route `light`, lượt ≤ 2 lens)
Đối tượng: `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md`, `evals/spikes/clause_key/`, DEC-dungskbg2004-1/-2
Lens (5/5, chạy độc lập, không thấy output của nhau): red-teamer, independent-revalidator, brainstormer, product-value-critic, market-fit-critic
Báo cáo từng lens: `plans/reports/ai2-clause-key-critique/{red-teamer,independent-revalidator,brainstormer,product-value-critic,market-fit-critic}.md`

**Verdict đề xuất: BLOCKED (advisory)** — giữ nguyên tắc thiết kế, nhưng claim "lớp gợi ý precision cao, recall ~50–55%" chưa đứng được; không viết lại plan B/C trước khi gỡ 4 blocker và ghi DEC mới.

---

# Tổng hợp critique — AI2 clause frame → canonical key → graph → so sánh tất định

Ngày: 2026-10-01 · Chế độ: advisory (chỉ đọc; file này là output duy nhất) · Người tổng hợp: `hs:critique-consolidator`

**Phạm vi:** claim "giữ nguyên tắc an toàn (LLM chép span nguyên văn + enum đóng; code dựng key; không chắc thì không gom); ship key graph như lớp gợi ý precision cao + hàng đợi `UNMAPPED` + vòng tăng trưởng lexicon; recall trên điều khoản thật chưa thấy ~50–55%".
Artifact: `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md` (viết tắt `RPT`) + `evals/spikes/clause_key/`. Quyết định trong phạm vi: DEC-dungskbg2004-1, DEC-dungskbg2004-2 (`docs/decisions.md`).

**Lenses:** red-teamer (RT) · independent-revalidator (RV) · brainstormer (BS) · product-value-critic (PV) · market-fit-critic (MF). **Thiếu: không có.**
Ghi chú input: chỉ `brainstormer.md` kết thúc bằng mảng JSON; bốn lens còn lại trả bảng phát hiện. Tôi chuẩn hóa từ bảng + phần chi tiết của từng lens (anchor, mức, trạng thái, cách sửa giữ nguyên văn). Các mục CONFIRM của RV không phải phát hiện; chúng được đưa vào mục "Phần đứng vững".

**Kiểm chứng neo (spot-check, không critique lại):** `RPT:248` ("19/19"), `RPT:333-348`, `mechanism.py:529`, `run_spike.py:243,250-253`, `docs/decisions.md:40` đều khớp với trích dẫn của các lens.

---

## Tổng số theo mức độ

**blocker 4 · major 13 · minor 6** (23 phát hiện sau dedup, từ ~52 phát hiện thô của 5 lens; 0 phát hiện bị loại vì thiếu `why_it_matters`/`fix` — MF-1 không có cách sửa riêng nên được gộp vào C-14, nơi PV-3 cung cấp cách sửa).

## Đề xuất verdict: **BLOCKED** (advisory)

Lý do (một đoạn): Hai blocker `proven` có repro trên code và mẫu văn bản thật vẫn còn sau tổng hợp. **C-01**: `decide()` trả `DUPLICATE` khi cả hai giá trị đều không đọc được (`None == None`, `mechanism.py:529`). Đây là âm tính giả duy nhất có thể làm người review bỏ qua một chế tài bị phụ lục sửa, và tầng này có `decision_end_to_end.n = 0` trên mọi lần chạy thật. **C-02**: thuộc tính mà `RPT:345` gọi là quan trọng nhất ("không chắc thì không gom") không được code thực thi. Có 4 đường biến sự không chắc chắn thành key xác định; trên held-out 2 v2, 5/19 key tự tin bị sai; gộp H1+H2 cho 3 false merge và 16–58 liên kết `GENERAL_VS_SPECIFIC` giả. Ngoài ra còn hai blocker ở bước *ra quyết định*: **C-03**, con số "recall ~50–55%" đo trên cặp khác hợp đồng, còn recall trong một hồ sơ ở các lần chạy sạch là 2/16; và **C-04**, bằng chứng 100% `REMEDY` được dùng cho một lựa chọn kiến trúc toàn AI2 theo DEC-dungskbg2004-2. Cả năm lens đều giữ *hướng* "lớp gợi ý + hàng đợi review" và *nguyên tắc* thiết kế. Vì vậy verdict chặn **claim ở dạng hiện tại** và việc **viết lại plan B/C dựa trên nó**, không bác bỏ hướng đi. Điều kiện gỡ chặn: sửa C-01/C-02 (rẻ, thuần code), chấm lại theo đúng đơn vị hồ sơ, và ghi DEC mới thay cổng của DEC-dungskbg2004-2 trước khi viết lại plan B/C.

---

## Ba phát hiện đe dọa nhất

1. **C-01 · blocker · proven · RT (RV xác nhận n=0)** — `evals/spikes/clause_key/mechanism.py:529`
   `decide()` trả `DUPLICATE` cho "phạt 5.000.000đ" vs "phạt 10.000.000đ", "1 tháng" vs "3 tháng tiền thuê", "gấp đôi" vs "gấp ba", hai hậu quả `None`, và hai PARAMETER đơn giá khác nhau.
   *Hậu quả:* `DUPLICATE` = "không cần nhìn". Mức phạt bị phụ lục sửa có thể lọt review. Mẫu kích hoạt có trong dữ liệu thật (hậu tố "đ" 4 lần ở `clauses_heldout2.jsonl`, "tương đương với 02 tháng tiền thuê" ở H06).
   *Sửa:* `DUPLICATE` chỉ khi `type`, `value` (khác None), `unit`, `base`, `period` đều bằng nhau; có value None → `NEEDS_REVIEW_UNPARSED`; thêm `đ|usd` vào `_MONEY`; PARAMETER dùng bộ so `value_text` riêng; thêm test âm cho từng dòng trong bảng RT-01.

2. **C-02 · blocker · proven · RT, RV** — `mechanism.py:397-405`, `:384-388`, `:413`; `lexicon_v2.json:76`, `:186`
   "Không chắc thì không gom" không được thực thi: (a) quét cả câu chạy trước back-off `?`; (b) bên có tên mà không resolve được → `default_bearer`/`ANY_PARTY`; (c) "X không được \<action\>" bị đọc thành bị động; (d) alias quá chung ("giao", "thực hiện") khớp ngay ở layer 2.
   *Hậu quả:* 5/19 key tự tin sai trên held-out 2 v2 (≈26%; v1 là 4/16). Pair metric không thấy vì đa số là singleton. Khi gộp H1+H2, false merge tăng 1 → 3; lexicon v2 sinh 16 liên kết `GENERAL_VS_SPECIFIC` giả (58 khi gộp). Số lỗi tăng theo cỡ corpus.
   *Sửa:* RT-02 (a)–(e): chỉ quét trong vế của chính frame khi cả hai ô rỗng; marker `UNRESOLVED` không bao giờ gom, tách khỏi `ANY_PARTY` tường minh; bỏ "không được" khỏi luật lật bên; `compounds_block` cho "giao", bỏ alias "thực hiện"; đưa **tỷ lệ key xác định bị sai** vào cổng.

3. **C-03 · blocker · proven · BS (blocker), PV (major), RT (major)** — `evals/spikes/clause_key/run_spike.py:250`
   Pair metric ghép `itertools.combinations` trên toàn tập. 57% (HO1) và 72% (HO2) cặp gold là khác hợp đồng; HO2 chỉ có **1** cặp khác điều trong cùng tài liệu. Recall cặp cùng hợp đồng, khác khoản ở các lần sạch là **2/16 = 12,5% [3,5; 36,0]**.
   *Hậu quả:* con số "~50–55%" dùng để chọn kiến trúc (DEC-dungskbg2004-2) không đo việc sản phẩm làm, vốn là so sánh trong một hồ sơ (`AI2-DOC-01:43`).
   *Sửa:* chấm lại theo vị trí cặp; gán nhãn 5–10 hồ sơ thật đầy đủ (thân + phụ lục) theo cặp, với lớp `SAME_SENTENCE | SAME_ARTICLE | EXPLICIT_REF | TITLE_ALIGNED | PARAPHRASE_ONLY`; chỉ số chính là recall trong hồ sơ.
   *Ghi chú mức độ:* giữ mức blocker (theo BS) vì con số này chính là claim, và nó là căn cứ của bước viết lại plan B/C; PV/RT xếp major.

---

## Bảng phát hiện sau dedup (xếp hạng)

| ID | Mức | Trạng thái | Lenses | Phát hiện (một dòng) | Cách sửa rẻ nhất | Fingerprint |
|---|---|---|---|---|---|---|
| C-01 | blocker | proven | RT, RV | `decide()` báo `DUPLICATE` khi cả hai value là None; PARAMETER không so `value_text`; chưa đo trên dữ liệu thật (n=0) | `DUPLICATE` chỉ khi mọi trường khác None và bằng nhau; None → `NEEDS_REVIEW_UNPARSED`; test âm | `114e00ad4f7674db` |
| C-02 | blocker | proven | RT, RV | "Không chắc thì không gom" không được code thực thi (4 đường); 5/19 key tự tin sai; gộp H1+H2 → 3 false merge, 16/58 link giả | RT-02 (a)–(e); cổng "tỷ lệ key xác định sai" | `ecaf54e014bea23e` |
| C-03 | blocker | proven | BS, PV, RT | Recall ~50–55% là recall khác hợp đồng; recall trong hồ sơ (lần sạch) 2/16 = 12,5% | Chấm theo vị trí cặp; gold mức hồ sơ có lớp vị trí | `d163b7a22332c8ac` |
| C-04 | blocker | proven | PV (blocker), BS (major) | Held-out 44/44 + 31/31 frame là `REMEDY`, 0 `PARAMETER`, 0 câu nhắc "phụ lục"; việc must-have (so giá trị thân↔phụ lục, timeline theo DEC-dungskbg2004-1) chưa có bằng chứng, trong khi DEC-dungskbg2004-2 dùng spike này để chọn kiến trúc toàn AI2 | Tách quyết định: (a) PARAMETER + timeline đo riêng trên hồ sơ có phụ lục; (b) REMEDY key graph là lớp bổ sung | `e1c58ff6c5546392` |
| C-05 | major | proven | RT | Đại số điều kiện: "15 ngày làm việc" == "15 ngày" → `DUPLICATE`; "không khắc phục trong vòng 14 ngày" → `hi=14` (sai chiều) → `GRADUATED` sai | "ngày làm việc" là dim riêng; "trong vòng N" trong vế vi phạm → UNPARSED | `1a0dc42a90b98287` |
| C-06 | major | proven | RV, PV, BS, RT | Tầng disposition chưa đo trên dữ liệu thật (`decision_end_to_end {k:0,n:0}`); nhãn làm ẩn cặp (`GRADUATED`/`DUPLICATE`/`NOT_COMPARABLE`) không có ngưỡng riêng; đọc hậu quả HO2 22/31 = 71% | Gán nhãn comparisons trên hồ sơ thật; precision theo disposition; nhãn giảm cảnh báo cần ngưỡng cao hơn hoặc vẫn hiện "đã phân loại, bấm để xem" | null (anchor là result JSON) |
| C-07 | major | proven | RT, RV, BS, MF, PV | "Precision cao / đủ an toàn" chưa được chứng minh: n=17, cận dưới Wilson 73,0%; gộp sạch 29/30, cận dưới 83,3% < 95%; cặp không độc lập (bootstrap theo khoản [0,63; 1,00]); căn nhiều-một `_best_match`; frame dự đoán thừa không được chấm (70 vs 44, 37 vs 31); 10 cặp liên-clause đều là PAY/LATE; chỉ một model | Căn 1-1 (Hungarian); chấm frame thừa; bootstrap theo khoản/hồ sơ; metric theo frame/cụm; ngưỡng dạng "≤ N cảnh báo sai/hồ sơ"; n ≥ 120; ghi model id | `9661f79191f82fbb` |
| C-08 | major | proven (code) / suspected (hành vi người rà) | RT, BS, PV, MF | Coverage tính `?` là "đã map" (80,6% → dùng được 19/31 = 61,3%); `?` gặp head khác → `decide()` None, không vào hàng đợi nào; hàng đợi liệt kê frame chứ không liệt kê cặp; `clause_compare.py:132-136` trả `[]` khi không có phụ lục; không có dòng độ phủ nên im lặng dễ bị đọc là "không có mâu thuẫn" | Coverage 3 lớp; `?` vào hàng đợi; sinh ứng viên cặp theo cấu trúc cho frame UNMAPPED; bắt buộc dòng "đã so X/Y; Z chưa so được"; không có trạng thái rỗng | `8067b72f5a673b72` |
| C-09 | major | proven | BS, PV, MF, RV, RT | Trụ "vòng tăng trưởng lexicon" thiếu cơ sở: lỗi chủ yếu do cấu trúc (loại luật 8 → 18; 5/5 nhóm lỗi H1 cần sửa code); lexicon v2 đóng góp ròng 0/−1 trên H2 và sinh key sai; không có người vận hành (`AI2-DOC-01:45`, `AI2-DOC-02:78`); `POL:102` chặn tích lũy xuyên tenant | Tách vòng alias (người review) khỏi vòng mechanism (release + held-out mới); đặt tên vai trò biên tập lexicon + SLA; hồi quy tỷ lệ key sai cho mỗi alias; chưa có người nhận thì ghi recall là tĩnh | `50a766bc6a55f252` |
| C-10 | major | proven | BS, RT, RV | Key REMEDY không có object/phạm vi: fixture 5.2~5.3 → `COMPARABLE_DIFFERENCE` (nguồn ghi "khác phạm vi, không gộp"); 5.1 chung~5.2 lẽ ra là `GENERAL_VS_SPECIFIC`; tiền thuê vs tiền điện nước cùng `('LESSEE','PAY','LATE')`; gold cùng schema nên metric không thấy; H28 bị gán trùng H27 | Thêm slot phạm vi/object vào key hoặc vào `decide()`; mutation golden "cùng hành vi, khác phạm vi" và "chung vs riêng" | `e136a71cc5fc28f0` |
| C-11 | major | proven | RV, RT, MF | "Bão hòa ~50–55%" và "v1 → v2 cải thiện" không vững: v1 trên H1 (lúc đó chưa thấy) 23,5%; liên-clause H2 10/22 = 45% ở cả v1 và v2; toàn bộ phần tăng là 1 cặp trong cùng khoản; McNemar p = 0,625; đổi nhãn K12 → 62,5%/66,7% | Báo tách liên-clause/nội-clause; chạy lặp ≥ 3 lần mỗi cấu hình để có dải nhiễu; diễn đạt là "một điểm dữ liệu, CI rộng" | `448ecf1f3626a0c1` |
| C-12 | major | proven | RT, BS, MF | Đổi cổng ngầm: DEC-dungskbg2004-2 chốt precision ≥ 95%, recall ≥ 80%, dữ liệu "synthetic + real anonymized"; mọi lần chạy thật trượt cả hai cổng, dữ liệu là mẫu công khai, nhưng RPT vẫn khuyến nghị triển khai | Ghi DEC mới với cổng đo được trước khi viết lại plan B/C | `a97b7c8a4c52dcb9` |
| C-13 | major | proven | RV, RT, MF, PV | Gold do một người gán (cũng là người phát triển), chưa đo IAA; nhãn không nhất quán (K02 vs K12; K07#1 vs H12); nhãn bị ép bởi enum v1 (K09/K14/K16#0/K21, chiếm 6/29 cặp gold) | Người thứ hai gán mù (danh sách RV B3); đo IAA; gold mức hồ sơ do người rà mục tiêu đánh dấu | `32f6e0b62d715b8b` |
| C-14 | major | proven | PV, MF | Chưa có bằng chứng từ người dùng ("chưa phỏng vấn user"), chưa có mốc thời gian rà, chưa nêu phương án thay thế/đối thủ | 3–5 hồ sơ thật ẩn danh + think-aloud; ghi mốc thời gian; liệt kê phương án thay thế | `abf2271fb4f9007b` |
| C-15 | major | proven | RT, RV | RPT ghi sai "Mọi frame được map đều map đúng (19/19)"; JSON ghi `accuracy_when_mapped` = 15/19 (H24/H25/H30 sai bên, `ANY_PARTY`) | Sửa câu; báo `accuracy_when_mapped` tách khỏi `key_accuracy` | `0d38d859e249656e` |
| C-16 | major | suspected | MF, BS | Chưa đo đối đầu với phương án khác: baseline LLM trần + ràng buộc trích dẫn (MF-5); trọng tài theo cặp với enum quan hệ đóng + 2 phiếu + `UNSURE` (BS PA-A; trong một hồ sơ N ≈ 15–40 frame, tức 120–780 cặp) | Bake-off trên cùng held-out, cùng mức abstain; dùng 1.411 cặp có nhãn sẵn | `7a2456209e28bd6e` |
| C-17 | major | suspected | BS, PV | Giá trị biên của key graph so với cấu trúc chưa đo: ≥ 12/15 cặp cùng hợp đồng ở HO1 là khoản anh em cùng Điều (ứng viên cấu trúc bắt 12/15, key graph v1 bắt 1/15); chế tài thường gom dưới một Điều nên công sức ròng có thể âm | Đo tỷ lệ `PARAPHRASE_ONLY` trên hồ sơ thật; A/B rà tay vs có gợi ý; nếu chênh lệch nằm trong nhiễu, hạ REMEDY key graph xuống vòng 2 | `805b98626deb8ba0` |
| C-18 | minor | proven | RT, RV | Freeze/provenance dựa vào tự khai: `evals/spikes/` chưa track; freeze v1/v1.1 FAILED; `run_spike.py` đổi sau v2-freeze (`176d…` → `a7b9…`); result JSON không có model id/hash; "khóa trước khi viết v2" sai thời gian (03:37:01 vs 03:42:04) — không có bằng chứng rò rỉ | Commit nhãn + code ở mỗi freeze; nhúng hash + model id vào result JSON; sửa câu `RPT:293` | `6ade4a397de37d3d` |
| C-19 | minor | proven | RT | Độ bền: span kiểu int gây `TypeError` làm hỏng cả lần chạy; "10.5 triệu" → 5000000; `by_clause` chỉ giữ frame cuối (`run_spike.py:269`); cổng nguyên văn chỉ kiểm chuỗi con; "Bên nhận hàng" → `RECIPIENT` (`lexicon_v2.json:49`) | Ép span sang str; parse "10.5"; so theo frame; kiểm span thuộc vế của frame; chặn "bên nhận" ghép | `a8469e21496523e7` |
| C-20 | minor | proven | RT | Trùng lặp gần giữa hai held-out (K10 ≈ H35, 66% 4-gram) | Khử trùng lặp theo n-gram giữa các tập | null (anchor là cặp ID dữ liệu) |
| C-21 | minor | suspected | PV (MF §5.2 cùng hướng) | Dàn trải 6 profile (EMPLOYMENT 0 frame, NDA 3) trước khi biết hồ sơ thí điểm thuộc profile nào | Làm sâu 1–2 profile theo tần suất hồ sơ thí điểm | `ce9202252eadc483` |
| C-22 | minor (lens: major) | proven | MF | Chưa có đường thu giá trị / chi phí phục vụ; chi phí LLM trả cho mọi điều khoản trong khi ~một nửa hưởng lợi; người duyệt lexicon là chi phí nhân công tuyến tính | Định giá theo hồ sơ cho nêm hẹp `[ASSUMED]`; LLM đề xuất alias để giảm công duyệt | `f8ec4b5af07be402` |
| C-23 | minor | proven (MF-9) / suspected (MF-8) | MF | Cơ chế key không tạo lợi thế phòng thủ (hướng không mới, LegalRuleML là chuẩn mở); CLM Việt có phân phối sẵn | Tách giá trị bán (trích dẫn neo nguồn + không phán hiệu lực + lịch sử rà) khỏi cơ chế; chọn nêm hẹp | `8fd1baff5f4dbc7d` |

Ghi chú xếp hạng:
- **C-05** đứng đầu nhóm major vì cùng loại lỗi không đảo ngược được với C-01 (nhãn làm ẩn cặp bị gán sai); mẫu kích hoạt có trong dữ liệu thật ("ngày làm việc" ở H01–H03, "trong vòng N" ở H02/H03/K16).
- **C-22** hạ từ major xuống minor *trong phạm vi này*: thiếu mô hình thu phí là vấn đề cấp sản phẩm, không làm sai claim về cơ chế. Nó vẫn là major ở phạm vi chiến lược sản phẩm.
- **C-04** giữ mức blocker (theo PV) chứ không phải major (theo BS): DEC-dungskbg2004-2 nói rõ kiến trúc toàn AI2 ("for all 6 profiles") được chọn bằng spike này, nên khoảng trống PARAMETER nằm đúng trên đường ra quyết định. Nếu phạm vi quyết định được thu về chỉ REMEDY, C-04 giảm xuống major.

---

## Theo từng lens (ánh xạ phát hiện gốc → ID tổng hợp)

| Lens | Phát hiện gốc → ID | Đóng góp riêng |
|---|---|---|
| red-teamer | RT-01→C-01 · RT-02→C-02 · RT-03→C-15 · RT-04→C-08 · RT-05→C-07 · RT-06→C-11 · RT-07→C-03 · RT-08→C-10, C-13 · RT-09→C-05 · RT-10→C-12 · RT-11→C-18 · RT-12→C-20 · RT-13→C-18 · RT-14→C-19 | Repro tất định cho C-01/C-02/C-05; nguồn duy nhất của C-01, C-05, C-19, C-20 |
| independent-revalidator | 1b/1c, 3a/3b→C-11 (và C-09: lexicon v2 ròng ≤ 0) · 2b/2c→C-02 · A2.4/A5.3→C-06, C-01 · 5a→C-07 · 5b→C-13, C-10 (H28) · 6→C-15 · 4b/4e→C-18 | Replay giai thừa (spans × lexicon), pooling H1+H2 (3 false merge), đếm link giả 16/58; CONFIRM các số liệu gốc |
| brainstormer | G1→C-03 · G2→C-10 · G3→C-09 · G5→C-04 · G6→C-08 · G7→C-07, C-06, C-12 · #7 (PA-C)→C-17 · #8 (PA-A)→C-16 | Phân rã cặp theo vị trí (2/16); ba phương án thay thế; thí nghiệm quyết định `PARAPHRASE_ONLY` |
| product-value-critic | PV-1→C-04 · PV-2→C-03 · PV-3→C-14, C-13 · PV-4→C-08 · PV-5→C-09 · PV-6→C-06 · PV-7→C-17 · PV-8→C-21 · PV-9→C-07 | JTBD thân↔phụ lục; dòng độ phủ; lát cắt nhỏ nhất có giá trị |
| market-fit-critic | MF-1→C-14 · MF-2→C-22 · MF-3→C-09, C-11 · MF-4→C-09 · MF-5→C-16 · MF-6→C-07, C-13, C-12 · MF-7→C-08 · MF-8, MF-9→C-23 | Xung đột `POL:102` với vòng lexicon; baseline LLM trần; "lexicon là liability ở trạng thái hiện tại" |

**Điểm đồng thuận mạnh nhất (≥ 4 lens):** C-07 (5 lens), C-09 (5 lens), C-06, C-08, C-13 (4 lens mỗi mục). Ba lens độc lập (BS, PV, RT) cùng chỉ ra đơn vị đo sai ở C-03.

---

## Phần đứng vững (đa số hoặc tất cả lens đồng ý)

| # | Điểm mạnh | Lens | Bằng chứng |
|---|---|---|---|
| S1 | **Nguyên tắc thiết kế** (span nguyên văn + enum đóng; code dựng key; bỏ trống thì rơi về `UNMAPPED`/`?`/`NEEDS_REVIEW_UNPARSED`) là đúng hướng và nên giữ bất kể chọn kiến trúc nào. Lưu ý: *nguyên tắc* đứng vững, *việc thực thi* thì không (C-02) | cả 5 | RT kết luận ngắn; RV B2 ("khuyến nghị `RPT:348` được củng cố"); BS steelman 1–3; PV §4; MF §3 |
| S2 | Số liệu tái hiện được, không có dấu hiệu rò rỉ nhãn | RV, RT | Replay khớp 100% trừ các dòng L5; `heldout2-labels.sha256` 4/4 OK; JSONL = `import_csv(CSV)`; không có run H2 trước 04:08:05; 0 alias v2 chỉ khớp H2 |
| S3 | "Không hội tụ tới 80% chỉ bằng thêm luật" và "lợi ích dev không chuyển giao": CONFIRM, bằng chứng còn mạnh hơn RPT nêu | RV, BS, MF | Lexicon v2: +15/+17 trên H1, 0/−1 trên H2 |
| S4 | Chẩn đoán K16 do bước quét cả câu là đúng; hướng "bỏ/giới hạn quét câu" đúng (dù chưa đủ, xem C-02d) | RV, RT | `trace.py`; `RPT:348` |
| S5 | RPT trung thực về cổng trượt và đuôi dài recall | BS | Bảng "Đánh giá cổng" `RPT:338-341` |
| S6 | Kiểm toán được: mỗi slot mang `span` + `method` | BS | — |
| S7 | Oracle `context_parties` không làm phồng kết quả ở held-out 2 | RT | Normalize lại không có ctx: 16/31 (tái hiện 30/31 dòng) |
| S8 | Khác biệt thật của sản phẩm nằm ở trích dẫn neo nguồn + không phán hiệu lực, không nằm ở cơ chế key | MF | `VIS:62`, `BRD:33` |

## Rủi ro còn lại các lens đã chấp nhận có điều kiện (không phải phát hiện)

- Oracle `context_parties`: chấp nhận; đo lại khi có bộ resolve bên thật (RT).
- Độ nhạy theo model (gpt-4o 43,2% vs Claude 34,1%): chấp nhận nếu đo lại mỗi phiên bản lexicon khi đổi model và ghi model id (RT, MF).
- Tương tác với `clause_compare.py` khi hai lớp cho kết luận khác nhau `[ASSUMED]`: chấp nhận nếu có quy tắc gộp/ưu tiên rõ ràng (RT).

## Khoảng trống phủ (không lens nào phủ; không phải phát hiện mới)

- Nhiễu LLM giữa các lần chạy lặp cùng cấu hình: chưa đo (RV B3 để UNDETERMINED). Cần có trước khi đọc chênh lệch 1–2 frame.
- OCR, câu dài nhiều mệnh đề: RT ghi "chưa được kiểm" nhưng không có anchor hay cách sửa.
- Quyền riêng tư/bảo mật khi lưu span hợp đồng để học lexicon: chỉ BS PA-B nhắc qua; chưa có lens security.
- Chi phí/độ trễ chỉ có số liệu giai thoại (3,2 s/lần; rate limit 107 → 257 s); chưa đo ở quy mô hồ sơ.

## Repeat-offense

Không có báo cáo critique trước cho artifact này, nên không có phát hiện lặp. Fingerprint ở bảng trên là khóa để đối chiếu các lần critique sau.

---

## Mục đáng ghi DEC (chỉ gắn cờ; skill điều khiển hỏi user và ghi qua `decision_register.py`)

| # | Nội dung đề xuất | Ảnh hưởng tới | Nguồn |
|---|---|---|---|
| D1 | **Thay cổng của DEC-dungskbg2004-2** bằng cổng đo được ở mức hồ sơ: false-`DUPLICATE` = 0; tỷ lệ key xác định bị sai ≤ ngưỡng do user chốt; recall trong hồ sơ (không phải khác hợp đồng); precision theo disposition; dữ liệu là hồ sơ thật ẩn danh, n ≥ 120 cặp. Phải ghi **trước** khi viết lại plan B/C | DEC-dungskbg2004-2 (sửa/thay) | C-12, C-03, C-07, C-02, C-01 |
| D2 | **Tách hướng AI2**: PARAMETER + timeline thân↔phụ lục (DEC-dungskbg2004-1) là lát must-have; REMEDY key graph là lớp bổ sung có điều kiện (theo tỷ lệ `PARAPHRASE_ONLY`); xem lại phạm vi "for all 6 profiles" | DEC-dungskbg2004-2 (phạm vi) | C-04, C-17, C-21 |
| D3 | Schema key thêm chiều phạm vi/object (hoặc `decide()` nhận slot phạm vi) | Schema plan B/C, `evals/golden/spec.py` | C-10 |
| D4 | Quản trị lexicon: ai vận hành, SLA, và chính sách dữ liệu xuyên tenant (xung đột với `AI2-DOC-02:78`, `POL:102`) | DEC mới | C-09 |
| D5 | Quy tắc hiển thị: nhãn làm giảm cảnh báo luôn hiện ở dạng "đã phân loại"; bắt buộc dòng độ phủ; không có trạng thái rỗng "không có mâu thuẫn" | DEC mới (chính sách sản phẩm) | C-06, C-08 |
| D6 | *(Có điều kiện)* Nếu bake-off chọn trọng tài theo cặp (PA-A): DEC làm rõ ranh giới với DEC-1 (LLM chọn enum quan hệ; không dùng embedding; không kết luận pháp lý) | DEC-1 | C-16 |

---

## Việc tiếp theo theo thứ tự ưu tiên

1. **Sửa C-01 + C-05** (thuần code, rẻ): điều kiện `DUPLICATE`, `_MONEY` nhận `đ|usd`, bộ so riêng cho PARAMETER, dim "ngày làm việc", "trong vòng N" → UNPARSED; thêm test âm cho từng dòng trong bảng RT-01/RT-09.
2. **Sửa C-02 (a)–(e)**, sau đó replay tất định trên spans đã lưu (không gọi LLM) để đo **tỷ lệ key xác định bị sai** và số link `GENERAL_VS_SPECIFIC` giả, trên H2 riêng và trên H1+H2 gộp.
3. **Sửa bộ chấm + RPT** (C-07, C-08, C-11, C-15, C-18): căn 1-1; chấm frame thừa; tách cặp nội-clause / liên-clause / cùng hồ sơ / khác hợp đồng; coverage 3 lớp; bootstrap theo khoản; sửa các câu `RPT:248`, `RPT:293`, `RPT:334/346`, `RPT:345`.
4. **Hỏi user và ghi D1 (+ D2)** trước mọi việc viết lại plan B/C.
5. **Dữ liệu mức hồ sơ**: 3–5 (tối đa 5–10) hồ sơ thật ẩn danh (thân + phụ lục); người rà mục tiêu đánh dấu cặp theo lớp vị trí; đo cùng lúc PARAMETER/timeline (C-04), tỷ lệ `PARAPHRASE_ONLY` (C-17), mốc thời gian + A/B rà tay (C-14); người gán nhãn thứ hai + IAA (C-13).
6. Nếu `PARAPHRASE_ONLY` đáng kể: **bake-off** key graph v2 (đã sửa) vs PA-A vs baseline LLM trần, cùng mức abstain, n ≥ 120 (C-16).
7. Thiết kế lại trụ hàng đợi + lexicon (C-08, C-09): `?` vào hàng đợi; ứng viên cặp theo cấu trúc; dòng độ phủ; đặt tên người vận hành lexicon (D4). Chưa có người nhận thì ghi recall là tĩnh.
8. Minor: slot phạm vi (C-10, sau D3), độ bền (C-19), khử trùng lặp held-out (C-20), provenance (C-18).

---

*Output của consolidator là đề xuất (dữ liệu). File gate `critique-consensus.json` (nếu dùng ở chế độ gate) do skill điều khiển ghi, không phải file này.*

---

## Bổ sung sau tổng hợp (red-teamer, vòng probe thứ hai)

| ID | Mức | Trạng thái | Phát hiện | Cách sửa |
|---|---|---|---|---|
| C-24 (RT-15) | minor | proven | `decide()` (`mechanism.py:522`) bắt cụm loại trừ "chỉ được" ở bất kỳ đâu trong khoản → `CONFLICT_CANDIDATE` giả | Chỉ tìm `_EXCLUSIVE` trong `consequence_text` hoặc vế chứa hậu quả |
| C-25 (RT-16) | minor | proven | `split_consequences` (`mechanism.py:469`) không tách danh sách có dấu phẩy, không xử lý "hoặc" → hậu quả gộp bị gán loại/giá trị sai | Tách theo dấu phẩy khi mỗi vế có cue riêng; biểu diễn "hoặc" là quan hệ thay thế |

## Quyết định sau critique (bước 7)

| Mục | Lựa chọn của người dùng | Ghi nhận |
|---|---|---|
| D1 — Cổng | Cổng mức hồ sơ | **DEC-dungskbg2004-3** (supersede DEC-dungskbg2004-2) |
| D2 — Hướng | Giữ key graph làm lõi (khác đề xuất PA-C của critique) | **DEC-dungskbg2004-3** |
| D3 — Schema phạm vi | B: phạm vi là thuộc tính so sánh trong `decide()`, không nằm trong key | **DEC-dungskbg2004-4** · `plans/reports/research-261001-0147-ai2-key-scope-and-lexicon-governance-report.md` |
| D4 — Quản trị lexicon | G3 ngay: LLM đề xuất alias, biên tập lexicon tenant duyệt, version theo tenant | **DEC-dungskbg2004-5** · cùng báo cáo |
