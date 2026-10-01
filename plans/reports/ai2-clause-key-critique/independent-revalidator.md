# Independent Revalidator — AI2 clause-key spike (held-out 1 / held-out 2)

Lens: `independent-revalidator` · Ngày: 2026-10-01 · Chế độ: read-only (không gọi LLM, không sửa code/plan)

> Thứ tự: Phần A được viết **trước** khi mở báo cáo của tác giả
> (`plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md`). Phần B viết sau.

Script tạm dùng để tính lại (scratchpad, không thuộc repo):
`dup.py`, `replay.py`, `replay2.py`, `pool.py`, `trace.py`, `lexdiff.py`, `consist.py`, `links.py`, `h1.py`
trong `C:\Users\dungs\AppData\Local\Temp\claude\...\scratchpad\`. Tất cả chỉ đọc JSON kết quả / CSV / JSONL và
gọi `Normalizer.normalize(..., chooser=None)` (thuần deterministic, không có L5 LLM).

---

## Phần A — Tự suy ra lại từ bằng chứng gốc (viết TRƯỚC khi đọc báo cáo tác giả)

### A0. Tính toàn vẹn của input

| Kiểm tra | Kết quả | Anchor |
|---|---|---|
| `heldout2-labels.sha256` | 4/4 OK (csv, sources, build_heldout2.py, clauses_heldout2.jsonl) | `sha256sum -c` |
| `heldout-labels.sha256` | 3/3 OK (không hash `clauses_heldout.jsonl`) | `sha256sum -c` |
| `v2-freeze` / `v2.1-freeze` | mechanism.py `8218658d…` và lexicon_v2.json `7c66dbaf…` OK ở cả hai; run_spike.py FAILED với v2 (`176d190c…`), OK với v2.1 (`a7b9dae2…`) | `sha256sum -c` |
| `v1-freeze` / `v1.1-freeze` | mechanism.py và run_spike.py FAILED (file đã bị thay thế); lexicon_v1.json OK | `sha256sum -c` |
| JSONL là dẫn xuất đúng của CSV | `import_csv(heldout*.csv) == clauses_heldout*.jsonl` → True cho cả hai tập | `consist.py` |
| Replay tái tạo kết quả đã lưu | Khớp 100% trừ các dòng dùng L5 chooser (K13#0 ở v1, K04#0 ở v2) | `replay.py` |
| Baseline "v1" trên H2 là proxy hợp lệ | mechanism hiện tại + lexicon_v1 tái tạo run gpt-4o v1.1 lúc 03:28 (`llm-full-v1-heldout-20261001-032856.json`), chỉ lệch ở 2 dòng L5 (H11#0, H25#0) | `consist.py` |

### A1. Kết luận (1): v1→v2 trên held-out 2

Số liệu thô (từ `results/claude-sonnet-4-6/llm-full-v{1,2}-heldout2-*.json`, tính lại bằng code độc lập, khớp JSON):

| | key_accuracy | pair_precision | pair_recall | false_merges |
|---|---|---|---|---|
| v1 (`…040805.json`) | 14/31 | 15/16 | 15/29 | K16#0~K16#1 |
| v2 (`…040925.json`) | 16/31 | 16/17 | 16/29 | K16#0~K16#1 |

Diễn giải độc lập:
- Chênh lệch theo từng dòng: +3 (K05#0, K05#1, K13#0) −1 (K06#0). Kiểm định McNemar chính xác với 3 vs 1 → p = 0.625. Không phân biệt được với nhiễu.
- **Phân rã giai thừa (replay, không L5)** — cùng spans, đổi lexicon:

  | spans \ lexicon | v1 | v2 |
  |---|---|---|
  | H2, spans prompt v1 | 15/31 | 15/31 |
  | H2, spans prompt v2 | **17/31** | 16/31 |
  | H1, spans prompt v1 | 15/44 | 30/44 |
  | H1, spans prompt v2 | 15/44 | 32/44 |

  → Lexicon v2 (artifact được tune trên H1) đóng góp **+15/+17 trên H1 nhưng 0 / −1 trên H2**. Phần tăng +1/+2 trên H2 đến từ prompt v2/biến thiên LLM, không đến từ lexicon.
- Cặp liên-clause (so sánh giữa các hợp đồng, use case thực): v1 = v2 = **10/10 precision, 10/22 recall**. Cặp tăng thêm duy nhất của v2 là cặp nội-clause K05#0~K05#1 (`h1.py`).

**Verdict độc lập (1):** số liệu đúng; "cải thiện nhỏ" đúng nhưng còn nói nhẹ. Chính xác hơn: không có cải thiện đo được trên H2, và phần được tune (lexicon v2) cho đóng góp ròng ≤ 0.

### A2. Kết luận (2): false merge hiếm, một nguyên nhân (K16, clause-scan fallback)

- Đúng: trong metric pair của `run_spike.py`, false merge duy nhất trên H2 là `K16#0~K16#1` ở cả hai phiên bản. Trace cho thấy key sai `('SUPPLIER','DELIVER','LATE')` đến từ nhánh clause-scan (`mechanism.py`, khối `if action is None and scan and … (not action_text or consequence_like)`): `action_text="bồi thường"` giống hậu quả, nên hệ thống quét cả clause và bắt alias `'giao'` trong cụm "do bên A **giao** bảo vệ" (`trace.py`, giống nhau ở lexicon v1 và v2).
- Không đúng ở phần "một nguyên nhân" / "hiếm":
  1. **Cặp K16 cũng là artifact của bộ chấm điểm.** `pred_spans` của K16#0 và K16#1 giống hệt nhau (cả v1 và v2): `_best_match` (`run_spike.py`) gán cùng một frame dự đoán cho hai frame gold (ghép nhiều-một). Cơ chế này cũng tạo ra các cặp "đúng" mà không cần dự đoán độc lập: v1 K03#0~#1~#2 (3 cặp), v2 K03#1~#2 (`dup.py`).
  2. **Clause-scan fallback gây sai nhiều hơn một lần** trên H2 v2: K16#0, K16#1 (`'giao'`), K21#0 (`'thực hiện'`, alias mới của v2 → `('ANY_PARTY','ANY_OBLIGATION','DEFECTIVE')`), K06#1 (`'thanh toán'` lấy từ câu khác → PAY, bị BACKOFF nên không nhóm).
  3. **"Hiếm" là hệ quả của độ thưa, không phải bằng chứng an toàn.** Trên H2 v2, 5/19 key "tự tin" (không BACKOFF) là sai: K06#0, K07#1, K16#0, K16#1, K21#0 (≈26%); v1 là 4/16. Phần lớn là singleton nên metric pair không nhìn thấy. Khi gộp H1+H2 (v2), false merge tăng từ 1 lên **3** (H24#0~K16#0, H24#0~K16#1, K16#0~K16#1) vì key sai của K16 va chạm với key đúng của H24 (`pool.py`).
  4. **Liên kết giả ở tầng `decide()` không được đo.** Key sai dạng ANY_OBLIGATION (K06#0, K21#0, cả hai sinh ra do lexicon v2) tạo **16 liên kết GENERAL_VS_SPECIFIC giả** trên H2 v2, v1 là 0; gộp H1+H2 v2 là 58 (`links.py`). Trên dữ liệu thật `decisions` có n=0 (`decision_end_to_end: {k:0,n:0}` trong cả hai JSON H2), nên loại lỗi này hoàn toàn vô hình với báo cáo.
  5. Lỗi bearer sai tồn tại: K06#0 v2 `('OWNER',…)` (LLM chọn "bên A" + alias v2 `'thực hiện hợp đồng'`), H13#0 v2 `('BUYER','DELIVER','LATE')` (gold SELLER).

**Verdict độc lập (2):** K16 đúng là do clause-scan fallback, nhưng "hiếm" và "một nguyên nhân" không đứng vững. Fallback là nguồn lỗi lặp lại. Cặp K16 một phần là artifact alignment. Rủi ro gộp sai ẩn (~1/4 key tự tin bị sai) và liên kết GENERAL_VS_SPECIFIC giả không được đo.

### A3. Kết luận (3): recall trên clause thật chưa thấy "bão hòa ~50–55%"; lợi ích dev không chuyển giao

- "Không chuyển giao": **đúng, và còn mạnh hơn**. Xem bảng giai thừa ở A1: lexicon v2 cho 0 / −1 key trên H2. Nó còn biến 2 trường hợp đang bỏ trống (K06#0 vốn đúng là UNMAPPED, K21#0) thành key sai tự tin.
- "Bão hòa ~50–55%": **không đứng vững như một đặc tính chung**.
  - v1 trên H1 (lúc đó cũng là dữ liệu chưa thấy với v1) chỉ có recall 12/51 = 23.5% (claude) và 13/51 = 25.5% (gpt-4o). Con số 52–55% là riêng của H2.
  - Recall trên H2 bị chi phối bởi thành phần tập: nhóm `CUSTOMER/PAY/LATE` (6 frame) chiếm 15/29 cặp gold; 7/29 cặp là nội-clause. Recall liên-clause là **10/22 = 45%** cho cả v1 và v2.
  - Rất nhạy với nhãn: chỉ cần đổi nhãn K12 thành `PAY/None` (theo quy ước của K02) là recall thành 15/24 = 62.5% và 16/24 = 66.7% (`pool.py`).
  - Wilson CI cho các metric pair giả định các cặp độc lập, nhưng thực tế các cặp chung frame (một frame sai trong nhóm 6 làm mất 5 cặp). CI in ra hẹp hơn thực tế.

**Verdict độc lập (3):** "không chuyển giao" → CONFIRM (có bằng chứng mạnh hơn). "Bão hòa 50–55%" → không được bằng chứng ủng hộ. Đó là một điểm dữ liệu từ một tập nặng PAY/LATE, không phải trần.

### A4. Kết luận (4): kỷ luật freeze / rò rỉ

Dòng thời gian (mtime, `stat -c '%y'`):

| Thời điểm | Sự kiện |
|---|---|
| 03:26:40 | heldout.csv / build_heldout.py / heldout-labels.sha256 |
| 03:28:56 | `llm-full-v1-heldout-…032856.json` (v1 trên H1; bắt đầu làm v2 sau mốc này) |
| **03:37:01** | heldout2.csv, build_heldout2.py, clauses_heldout2.jsonl, **heldout2-labels.sha256** |
| 03:39:31 | `rules-v2-dev-…033931.json` (v2 đang được phát triển) |
| 03:41:28 | `llm-full-v2-heldout-…034128.json` (gpt-4o, v2 **trước** lần sửa cuối) |
| **03:42:04.606464900** | lexicon_v2.json **và** mechanism.py (mtime giống nhau đến từng nano-giây) |
| 03:54:37 | v2-freeze.sha256 |
| 04:01:32 | run_spike.py + v2.1-freeze.sha256 ("retry on timeouts, infra only") |
| 04:08:05 / 04:09:25 | các run v1/v2 trên H2 (claude-sonnet-4-6) |

- Đúng: nhãn H2 không đổi kể từ 03:37 (hash OK). mechanism.py và lexicon_v2.json không đổi giữa lúc v2-freeze và lúc chạy H2 (hash v2 = v2.1 = hiện tại). Không có file kết quả nào trên H2 trước 04:08. Diff lexicon v1→v2 (36 mục thêm) **không có alias nào chỉ khớp văn bản H2**: mọi alias mới khớp H2 đều cũng khớp H1/test (`lexdiff.py`).
- Không đúng về mặt thời gian: "nhãn H2 được khóa **trước khi phát triển v2**" mâu thuẫn với mtime. H2 được khóa ở *giữa* quá trình phát triển v2, và lexicon_v2.json cùng mechanism.py được ghi lần cuối **5 phút sau** đó. Chính `lexicon_v2.json` `/note` có nhắc tới held-out 2, tức được viết sau 03:37. Văn bản và nhãn H2 nằm nguyên văn trong `build_heldout2.py` do chính tác nhân phát triển viết ra, nên người phát triển đã đọc H2 trước lần sửa cuối của v2. Không có bằng chứng rò rỉ ở mức alias. Nội dung thay đổi của mechanism.py lúc 03:42 thì không kiểm chứng được (không có bản trước đó; `evals/spikes/` chưa được git track).
- Hệ quả: nếu có nhiễm bẩn thì nó chỉ làm v2 trông tốt hơn. Vì v2 không tốt hơn trên H2, kết luận "không chuyển giao" vẫn vững trước rủi ro này.
- UNVERIFIABLE: run_spike.py (chứa `EXTRACT_SYSTEM_V2` và toàn bộ bộ chấm điểm) đổi sau v2-freeze (`176d…` → `a7b9…`). Nhận định "infra only" không có diff để kiểm chứng.
- Phụ: run gpt-4o v2 trên H1 (03:41:28) có trước lần sửa cuối (03:42:04), nên không phải v2 đã đóng băng.

**Verdict độc lập (4):** hash-lock của nhãn và freeze của mechanism/lexicon đứng vững. Cách diễn đạt "khóa trước khi phát triển v2" sai. Cách diễn đạt đúng: "khóa trước khi v2 được hoàn tất/đóng băng và trước mọi lần chạy hệ thống trên H2". Phần thay đổi của run_spike.py sau freeze không kiểm chứng được.

### A5. Metric có đo đúng điều được tuyên bố không

1. **Pair precision trên 16–17 cặp không mang tính đại diện.** Cặp liên-clause được dự đoán chỉ có 10, và cả 10 đều là PAY/LATE (9 `CUSTOMER/PAY/LATE` + 1 `OWNER/PAY/LATE`). 6–7 cặp còn lại là nội-clause, trong đó một phần "đúng do cấu trúc" vì ghép nhiều-một. Các cặp không độc lập, nên Wilson CI in trong JSON không hợp lệ.
2. **Pair precision chỉ thấy key sai khi chúng va chạm.** Key sai singleton và BACKOFF `?` bị loại, nên tỷ lệ gộp sai tăng theo kích thước corpus (A2.3).
3. **Không có metric quyết định trên dữ liệu thật** (`decisions: []`), nên GENERAL_VS_SPECIFIC giả không được đo (A2.4).
4. **key_accuracy tính UNMAPPED là đúng** cho 3 frame gold-None (K06#0, K13#0, K20#0). Trong 3 thay đổi của v2 có 2 thay đổi thuộc loại abstain: K13 (lợi) và K06#0 (hại).
5. **Nhất quán nhãn (một người gán nhãn, cũng là người phát triển; chưa đo inter-annotator agreement):**
   - K07#1 `BUYER/PAY/LATE` ("hết thanh toán mà bên mua vẫn **không trả tiền** … số tiền chậm trả") so với H12 `LESSEE/PAY/NOT_PERFORMED` ("**không trả tiền** trong ba kỳ liên tiếp"): cùng cụm kích hoạt nhưng qualifier khác nhau. Lexicon v2 học `'không trả'`→NOT_PERFORMED từ H12. Cả hai cách gán đều bảo vệ được; nếu chọn NOT_PERFORMED thì v2 = 17/31.
   - K02 `OWNER/PAY/None` so với K12 `CUSTOMER/PAY/LATE`: cùng trigger "vi phạm nghĩa vụ thanh toán". K12 suy ra LATE từ hậu quả ("lãi suất chậm trả"), K02 thì không. Quy ước không nhất quán, và K12 lại nằm trong nhóm chi phối recall (A3).
   - H28 `CONTRACTOR/COMPLETE_WORK/LATE`, trùng key với H27, trong khi văn bản nói rõ "Hai khoản 5.2 và 5.3 khác phạm vi, **không gộp** thành một mức". Schema key không có chiều phạm vi (scope), nên gold ép một phép gộp mà nguồn cấm. Ngoài ra "chậm … thiết bị" ở H24 được gán `DELIVER/LATE`.
   - K09/K14/K16#0/K21 = `SUPPLIER/PROVIDE_SERVICE/DEFECTIVE` (quy ước ở `build_heldout2.py` dòng 32–33, nhất quán với H23). Đây là quy ước được áp đặt: nhãn buộc phải nằm trong enum của lexicon v1 (`import_heldout.py` validate với `LEXICON_V1_PATH`), và enum không có hành vi "mất/hư hàng khi vận chuyển/giữ hộ". Nhóm này chiếm 6/29 cặp gold, và không phiên bản nào lấy được cặp nào trong số đó.

---

## Phần B — So sánh với báo cáo tác giả (viết SAU Phần A)

Báo cáo tác giả: `plans/reports/spike-261001-0147-ai2-clause-key-rules-baseline-report.md` (viết tắt `RPT`).

### B1. Bảng verdict

| # | Điểm | Kết quả độc lập | Kết quả vòng 1 (RPT) | Phân loại | Anchor |
|---|---|---|---|---|---|
| 1a | Số liệu H2 v1→v2 | 14→16/31; 15/16→16/17; 15/29→16/29 | như nhau (`RPT:316-317`) | **CONFIRM** | `…v1-heldout2-…040805.json`, `…v2-heldout2-…040925.json`; tính lại bằng `replay.py` |
| 1b | "chỉ nhích, trong khoảng tin cậy" | +3/−1, McNemar p=0.625; lexicon v2 đóng góp 0/−1 trên H2; cặp liên-clause y hệt (10/10, 10/22) | "chỉ nhích… trong khoảng tin cậy" (`RPT:323`) | **CONFIRM** (bằng chứng mạnh hơn) | `replay2.py`, `h1.py` |
| 1c | Vì sao không chuyển giao | Một phần do nhóm lỗi mới, một phần do **chính lexicon v2 sinh key sai trên H2** (K06#0: bỏ trống đúng → key sai; K21#0: bỏ trống → key sai) | chỉ do "held-out 2 lộ ra các nhóm lỗi mới" (`RPT:323-331`) | **OVERTURN (một phần)** | `replay2.py` (v2 spans: lex v1 17/31 vs lex v2 16/31); `trace.py` |
| 2a | Nguyên nhân K16 | clause-scan fallback bắt `'giao'` trong "bên A giao bảo vệ" | như nhau (`RPT:329`, `RPT:333`) | **CONFIRM** | `mechanism.py:361`; `trace.py` |
| 2b | "1 nguyên nhân" | Fallback còn gây K21#0 (`'thực hiện'`) và K06#1 (`'thanh toán'`); cặp K16 còn là artifact ghép nhiều-một của `_best_match` | "nguyên nhân cụ thể: bước quét cả câu" (`RPT:333`); bảng lỗi ghi "Quét câu bắt nhầm: 2 frame" (`RPT:329`) | **OVERTURN** | `run_spike.py:172-186`; `dup.py` (K16#0/K16#1 `pred_spans` giống hệt nhau ở v1 và v2) |
| 2c | "gom sai hiếm (1/17)… đủ an toàn" | 5/19 key tự tin trên H2 v2 bị sai (≈26%); gộp H1+H2 → 3 false merge; 16 liên kết GENERAL_VS_SPECIFIC giả (v1: 0); metric quyết định có n=0 trên dữ liệu thật | "gom sai hiếm… đủ an toàn để hiển thị cho người review" (`RPT:333`, `RPT:345`) | **OVERTURN** | `pool.py`, `links.py`; `run_spike.py:252`; `decision_end_to_end: {k:0,n:0}` trong cả hai JSON H2 |
| 3a | Lợi ích dev không chuyển giao | Lexicon v2: +15/+17 trên H1, 0/−1 trên H2 | "phần lớn cải thiện v2 không chuyển sang held-out 2" (`RPT:323`) | **CONFIRM** | `replay2.py` |
| 3b | "recall trên dữ liệu chưa thấy ~50–55%" | Riêng của H2: v1 trên H1 (lúc đó chưa thấy) = 23.5%; recall liên-clause trên H2 = 45% cho cả hai bản; đổi 1 nhãn (K12) là thành 62.5%/66.7% | "Sau hai vòng, recall trên dữ liệu chưa thấy ~50–55%" (`RPT:334`), "Recall thực tế ~50%" (`RPT:346`) | **OVERTURN** (cách mô tả, không phải hướng) | `h1.py`, `pool.py`; `…v1-heldout-…040427.json` pair_recall 12/51 |
| 3c | Không hội tụ tới 80% chỉ bằng thêm luật | được ủng hộ (lexicon v2 đóng góp 0 trên H2) | như nhau (`RPT:334`) | **CONFIRM** | `replay2.py` |
| 4a | Hash nhãn H2 | OK 4/4; jsonl = import_csv(csv) | "khóa… `heldout2-labels.sha256`" (`RPT:293`) | **CONFIRM** | `sha256sum -c`; `consist.py` |
| 4b | "gán nhãn và khóa **trước khi viết v2**" | Khóa lúc 03:37:01, *giữa* quá trình phát triển v2; lexicon_v2.json và mechanism.py ghi lần cuối lúc 03:42:04; `/note` trong lexicon nhắc tới H2 | "Held-out 2 gán nhãn và khóa trước khi viết v2" (`RPT:293`) | **OVERTURN** (cách diễn đạt; không có bằng chứng rò rỉ) | `stat` mtimes (bảng A4); `lexdiff.py` (0 alias chỉ khớp H2) |
| 4c | Không chạy trên H2 trước khi freeze | Không có file kết quả H2 trước 04:08:05 | như nhau (`RPT:293`) | **CONFIRM** [chỉ dựa trên việc không thấy file] | `ls results/` |
| 4d | mechanism/lexicon không đổi v2→v2.1→run | hash khớp | như nhau (`RPT:295`) | **CONFIRM** | `sha256sum -c` |
| 4e | v2.1 "chỉ thêm retry" trong run_spike.py | Không có bản trước để diff (`evals/spikes/` chưa được git track) | "chỉ thêm retry khi timeout" (`RPT:295`) | **UNDETERMINED** | `176d190c…` ≠ `a7b9dae2…` |
| 5a | Pair precision 16/17 có ý nghĩa? | Không đại diện: 10 cặp liên-clause đều là PAY/LATE; cặp không độc lập nên Wilson CI không hợp lệ | báo Wilson [73.0; 99.0] (`RPT:317`, `RPT:340`) | **OVERTURN** (tính hợp lệ của metric) | `h1.py`; `pool.py` (nhóm `CUSTOMER/PAY/LATE` = 15/29 cặp gold) |
| 5b | Nhãn tranh chấp | K07#1 tranh chấp; ngoài ra K02↔K12 không nhất quán; H28 trái với chính văn bản nguồn; quy ước K09/K14 bị ép bởi enum v1 | chỉ nêu K07#1 ("Nhãn tranh cãi 1–2", `RPT:331`) | **OVERTURN (một phần)**: RPT thiếu 3 mục | `heldout2.csv` (K02, K12), `heldout.csv` (H12, H27, H28, H24); `import_heldout.py:46`; `build_heldout2.py:33-34` |
| 6 | (mục H1) "Mọi frame được map đều map đúng (19/19)" | JSON: `accuracy_when_mapped` = 15/19; 4 frame map sai (H12 `?`, H24/H25/H30 bearer `ANY_PARTY`) | `RPT:248` | **OVERTURN** | `llm-full-v1-heldout-20261001-032856.json` → `wrong_mapped_ids` |

### B2. OVERTURN chi tiết

**2b/2c — "Gom sai hiếm, một nguyên nhân, đủ an toàn" (`RPT:333`, `RPT:345`).**
Bằng chứng buộc kết luận khác:
- `run_spike.py:252` chỉ đếm cặp khi hai key dự đoán *trùng nhau*. Key sai mà là singleton (K06#0, K07#1, K21#0 trên H2 v2) hoặc là BACKOFF thì vô hình. Trên H2 v2, 5/19 key tự tin bị sai. Khi gộp H1+H2 (đúng định nghĩa pool của `run_spike.run()`), key sai của K16 va chạm với H24#0 → **3** false merge, v1 vẫn 1.
- Hai key ANY_OBLIGATION sai (K06#0 `OWNER/ANY_OBLIGATION/DEFECTIVE`, K21#0 `ANY_PARTY/ANY_OBLIGATION/DEFECTIVE`) do lexicon v2 thêm alias `'thực hiện'`/`'thực hiện hợp đồng'` sinh ra, và mỗi key tạo liên kết `GENERAL_VS_SPECIFIC` qua `decide()`: 16 liên kết giả trên H2 v2, 58 khi gộp H1+H2. Metric quyết định không được đo trên dữ liệu thật (`decisions: []`).
- Cặp K16#0~K16#1 phụ thuộc vào `_best_match` (`run_spike.py:186`) chọn **cùng một** frame dự đoán cho hai frame gold; `pred_spans` giống hệt nhau. Metric vì vậy cũng cộng điểm "đúng do cấu trúc" cho K03 (v1: 3 cặp).
- Fallback quét-câu (`mechanism.py:361`) gây sai ở K16#0, K16#1, K21#0, K06#1, chứ không chỉ K16.

Khuyến nghị `RPT:348` ("bỏ/giới hạn bước quét cả câu") được bằng chứng này **củng cố**. Chỉ có câu "đủ an toàn để hiển thị" là chưa được chứng minh.

**1c — Nguyên nhân không chuyển giao.** Replay giai thừa cho thấy lexicon v2 không mang lại key đúng nào trên H2 và biến 2 trường hợp bỏ trống thành key sai tự tin. RPT chỉ quy cho "nhóm lỗi mới", nên bỏ sót việc chính artifact v2 gây thoái lui về precision.

**3b — "Recall ~50–55%".** Đây là một điểm dữ liệu trên một tập nặng PAY/LATE (20/29 cặp gold là PAY/LATE hoặc COMPLETE_WORK/LATE, 7/29 là nội-clause). v1 trên H1 (lúc đó chưa thấy) chỉ 23.5%. Cặp liên-clause trên H2 là 45% cho cả hai bản. Đổi một nhãn là recall lệch ±10 điểm. Không đủ cơ sở để gọi là "bão hòa" hay "thực tế ~50%".

**4b — Dòng thời gian freeze.** Theo `stat`: khóa H2 lúc 03:37:01, run v2-dev lúc 03:39:31, run v2-H1 lúc 03:41:28, **lexicon_v2.json + mechanism.py lúc 03:42:04**, v2-freeze lúc 03:54:37. Cách diễn đạt đúng: "khóa trước khi v2 được hoàn tất/đóng băng và trước mọi lần chạy trên H2". Không tìm thấy alias nào chỉ khớp H2, và nếu có nhiễm bẩn thì chỉ làm v2 trông tốt hơn (điều không xảy ra), nên các kết luận chính **không** bị ảnh hưởng. Đây là mức minor.

**5a — Tính hợp lệ của pair precision/recall.** Wilson CI trên cặp giả định cặp độc lập, nhưng một frame sai trong nhóm 6 làm mất 5 cặp. Nên báo thêm metric theo frame hoặc theo cụm, tách liên-clause/nội-clause, và loại các cặp mà cùng một frame dự đoán được gán cho nhiều frame gold.

**5b — Nhãn.** K07#1 (LATE) và H12 (NOT_PERFORMED) cùng cụm "không trả tiền". K02 (`PAY/None`) và K12 (`PAY/LATE`) cùng cụm "vi phạm nghĩa vụ thanh toán". H28 bị gán cùng key với H27 dù nguồn ghi "không gộp thành một mức". Nhóm K09/K14/K16#0/K21 là quy ước bị ép vì enum v1 thiếu hành vi "mất/hư hàng khi giữ/vận chuyển". Một người gán nhãn thứ hai độc lập có thể không đồng ý ở K07#1, K12 và H28. [ASSUMED] mức độ bất đồng: chưa đo IAA.

**6 — `RPT:248` "19/19".** JSON ghi 19 = `key_accuracy.k` (gồm 4 frame UNMAPPED-đúng) và 19 = `coverage_mapped.k`; `accuracy_when_mapped` = 15/19. Nhận định an toàn trên H1 vì vậy dựa trên một con số bị gộp nhầm, dù "0 false merge" vẫn đúng.

### B3. UNDETERMINED — cần gì để kết luận

| Điểm | Thiếu bằng chứng | Cách giải quyết |
|---|---|---|
| 4e run_spike.py v2→v2.1 "chỉ retry" | Không có ảnh trước (untracked) | Từ nay commit/lưu bản sao file tại mỗi freeze; hoặc chạy lại H2 bằng bản run_spike đã khóa (nếu còn) |
| Nhiễu LLM giữa các lần chạy | Không có lần chạy lặp cùng model + prompt + mechanism | Chạy lặp ≥3 lần mỗi cấu hình trên H2 (có gọi LLM, ngoài phạm vi lens này) để có dải nhiễu trước khi đọc chênh lệch 1–2 frame |
| Nội dung sửa mechanism.py lúc 03:42 | Không có diff | Như 4e |
| Mức đồng thuận nhãn | Chỉ có một người gán nhãn | Người thứ hai gán nhãn mù trên H2 (ít nhất K02, K07#1, K09, K12, K14, K16, K21) và trên H1 (H12, H24, H28) |

### B4. Checklist
- [x] Phần A được ghi vào file này trước khi mở `RPT` (ghi rõ ở đầu file).
- [x] Mọi điểm chịu tải đều được phân loại CONFIRM/OVERTURN/UNDETERMINED và có anchor.
- [x] Mỗi OVERTURN nêu rõ bằng chứng buộc kết luận khác.
- [x] Điểm không suy ra được từ bằng chứng được gắn [ASSUMED] (mức IAA) hoặc [chỉ dựa trên việc không thấy file] (4c).
- [x] Không sửa code, plan hay artifact; chỉ ghi file báo cáo này và các script trong scratchpad.
