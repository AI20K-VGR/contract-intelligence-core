# Phản biện kế hoạch khôi phục chất lượng contract graph

| ID | Severity | Proven / suspected | Anchor | Sửa rẻ nhất |
|---|---|---|---|---|
| RT-QR-01 | High | Proven: thứ tự phase không khép kín với fingerprint gate hiện hữu | `phases/phase-4-bounded-development-experiments.md:44`; `phases/phase-5-fresh-heldout-and-product-verdict.md:23`, `:43`; `evals/contract_graph/pairs/predictor.py:69`; `bakeoff.py:481`; `run.py:256` | Sau mọi thay đổi P5, chạy hai confirmation dev trên winner đã khóa, tính trong ledger; tạo phiên bản report/manifest và supersession receipt mới trước held-out. Không sửa SHA báo cáo cũ hoặc bỏ fingerprint check. |
| RT-QR-02 | High | Proven: đường dẫn và reader mới chưa được nối đầy đủ trong inventory | `phases/phase-4-bounded-development-experiments.md:43`; `evals/contract_graph/pairs/run.py:241`; `bakeoff.py:465`; `predictor.py:501`; `phases/phase-5-fresh-heldout-and-product-verdict.md:22` | Đưa plumbing đường dẫn dev/report lock vào P2; tách data-review lock khỏi classifier PASS; chỉ rõ dispatch schema mới trong predictor/CLI và test ownership. Giữ legacy readers historical-only. |
| RT-QR-03 | High | Suspected `[ASSUMED]`: recall frame có thể bị pha với candidate-union | `plan.md`, bảng Contract metric: recall trên toàn approved positives; `phases/phase-5-fresh-heldout-and-product-verdict.md:10`, `:42`; `evals/contract_graph/pairs/score.py:44` | Khóa riêng recall-frame membership trước candidate generation; union-only rows chỉ dùng precision/safety. MIN_N=60 từng nhãn recall áp dụng riêng frame độc lập. Test augmentation không được nâng recall/gate. |

**Verdict vòng đầu: BLOCKED** bởi RT-QR-01 và RT-QR-02. RT-QR-03 là nghĩa vụ validation, chưa chứng minh bypass runtime trên implementation tương lai. Đây là review readiness của kế hoạch; không phải product verdict. Product lịch sử vẫn `KEEP_OFF_FALSE_DUPLICATE`, runtime OFF.

Ngày: 2026-10-10. Worktree `C:/Users/dungs/OneDrive/Documents/VSF-ai2-contract-graph`, branch `feature/ai2-contract-graph`. Đã đọc plan, năm phase, graph, research, local probes và các reader/scorer/gate liên quan. Các `phases/...` anchor trong báo cáo tương đối với plan này; các source anchor tương đối với worktree. Chỉ viết báo cáo này, không sửa source/plan. Không gọi live model hoặc chạy implementation tests.

## Các đường dẫn lỗi có thể làm mất giá trị bằng chứng

Không tìm thấy hành động xóa dữ liệu hoặc tự bật runtime trong kế hoạch. Rủi ro không thể thu hồi là sử dụng held-out mới trước khi protocol/dev evidence đủ hợp lệ: sau khi xem kết quả để sửa mã, bộ đó không còn độc lập cho lần đánh giá tiếp theo. Kế hoạch đã yêu cầu fresh evaluation sau retune và giữ artifact immutable; các fix dưới phải giữ điều kiện này.

### RT-QR-01 — Code thay sau dev freeze làm lock không hợp lệ

P4 yêu cầu khóa winner/source fingerprint và báo cáo dev. P5 vẫn có bước sửa `bakeoff.py`; chính file đó nằm trong `predictor.code_fingerprints()` (`predictor.py:66`). `bakeoff.preconditions()` đối chiếu toàn fingerprint báo cáo dev với mã hiện tại và chặn khi khác (`bakeoff.py:481`). Nếu đo lại dev, `_review_dev_lock()` từ chối ghi đè một lock khác (`run.py:256`).

Chuỗi cụ thể: dev report hợp lệ với fingerprint h1 → P5 sửa `bakeoff.py`, fingerprint h2 → preflight báo `dev report code fingerprint is stale` → báo cáo dev đo lại có SHA mới → lock cũ không cho replacement. Kế hoạch vòng đầu không chỉ rõ workflow tạo phiên bản/supersession và confirmation sau thay đổi mã.

Sửa ít nhất: dành hai repeat confirmation dev trong ledger tổng, chạy sau code P5 đã freeze, dùng cùng winner/model/rubric/dev/order và không tune. Nếu một confirmation fail, P5 dừng trước held-out. Lock phiên bản mới có receipt liên kết phiên bản cũ; không biến báo cáo h1 thành bằng chứng của h2 bằng cách thay SHA. Hoặc chuyển toàn plumbing P5 lên trước dev freeze.

### RT-QR-02 — Báo cáo mới và corpus mới gặp hardcode lịch sử

Command P4 ghi `evals/contract_graph/reports/quality-recovery-p4-development.json`. Nhưng `_review_dev_lock()` đọc đúng `bakeoff.DEV_REPORT_PATH`, hiện là `l2-p3-classifier-dev.json` (`run.py:241`, `bakeoff.py:53`). `preconditions()` yêu cầu path lock bằng chính hằng lịch sử (`bakeoff.py:465`). Vì vậy có thể tồn tại báo cáo mới hoàn toàn hợp lệ mà CLI vẫn đọc báo cáo cũ hoặc không khóa được báo cáo mới.

Reader held-out `predictor._read_reviewed_gold()` hiện chỉ xây block HG-1/HG-2 và hai bộ tên file lịch sử (`predictor.py:501`). Inventory P5 vòng đầu không có predictor.py hoặc test predictor, trong khi đề xuất HG-QR2/schema/dataset riêng. Cụm “orchestration as needed” chưa cung cấp handoff rõ để bảo đảm reader mới được gọi và reader cũ không giả đủ approval.

Sửa ít nhất: lock đường dẫn report theo schema/dataset/version với resolver giới hạn repo/local roots phù hợp; P3 được khóa data review trước classification, không cần classifier PASS. P5 bổ sung ownership reader/schema dispatch cần thiết, integration fixture đọc chính HG-QR2 và report mới. Không copy báo cáo mới đè file lịch sử để né hardcode.

### RT-QR-03 — Thêm union-only positives có thể che candidate miss

Vòng đầu vừa yêu cầu frame candidate-independent vừa review toàn candidate-union B/C. Gate recall lấy toàn approved positive gold; chưa định nghĩa row membership tách frame recall với union-only bổ sung để chấm precision/safety. Nếu tất cả đều nhập chung, positive có sẵn trong candidate sẽ được lấy nhiều hơn positive bị candidate bỏ sót.

Concrete input cho scorer mới cần chặn: frame độc lập có 60 positive của một nhãn, classifier hit 53; bổ sung 40 positive union-only mà classifier đều hit. Mô hình và 60 cặp gốc không đổi, nhưng recall pooled biến từ 53/60 thành 93/100.

Arithmetic probe bằng production helper đã chạy, exit 0:

```powershell
@'
from evals.contract_graph.score import wilson
print('independent_frame', 53, 60, wilson(53,60))
print('frame_plus_candidate_union', 93, 100, wilson(93,100))
'@ | .\ai-service\.venv\Scripts\python.exe -
```

```text
independent_frame 53 60 (0.7782097940014187, 0.9423235259654995)
frame_plus_candidate_union 93 100 (0.8625032899347025, 0.965681175635936)
```

Wilson95 lower chuyển từ dưới .85 sang trên .85 chỉ do mẫu thêm phụ thuộc candidate. Đây là counterexample về định nghĩa denominator, không phải đã khai thác code mới. Cần `recall_frame_member` hoặc contract tương đương được hash-lock, row được phép thuộc cả hai frame; union-only không vào numerator/denominator recall. Quota recall không được lấy positives của union-only để bù. Đánh giá precision dùng toàn predictions với approved review phù hợp và không bỏ dự đoán ngoài frame.

## Scenario pass và phạm vi còn lại

Áp dụng phân rã một lượt theo `hs:scenario`: input extremes, timing, scale, state transitions, environment, error cascades, authorization, data integrity, integration, contract-delta/callers, stakeholder và lifecycle. Không mở persona fan-out `hs:predict`: review đã được tách độc lập bởi parent và slot delegation hữu hạn; không tuyên bố có năm persona độc lập. User Types/Business Logic không có nhánh riêng ngoài reviewer/approval; Compliance xử lý tại data-local/consent boundary, không giả audit pháp lý.

Các scenario đã đối chiếu: thiếu direction A/B; n0/n59; precision/recall khác denominator; missing/NaN/bool counters; unreviewed DUPLICATE; nguồn cũ/exposed cluster; human receipt stale; provider alias; one bad repeat; hết budget; flag OFF và consent denied; legacy schema; dirty shared files; raw payload leak. Kế hoạch đã có fail-closed và test obligation cho các điểm này, nên không lặp chúng thành findings mới.

Không tái khẳng định conditional historical join là confirmed runtime cause; prompt override vẫn là hypothesis. `MIN_N=60` cho precision và recall độc lập; Wilson .85 không được waived. Hiện chưa có dữ liệu/reviewer/budget sizing đủ để hứa product PASS.

## Probes và giới hạn bằng chứng

- Interpreter `.\ai-service\.venv\Scripts\python.exe` tồn tại.
- `predict --help` và `bakeoff run --help` bằng interpreter đó, `PYTHONPATH='ai-service;.'`, đều exit 0; mọi flag trong command hai phase có trong parser hiện hữu.
- Toàn bộ test file được phase commands tham chiếu tồn tại qua `rg --files`; chưa chạy tests.
- Chưa chạy full valid integration fixtures; đây là nghĩa vụ cook trước claim gate fix PASS.
- Budget corpus400 positives, đủ independent clusters và yield REFERENCE chưa đo. Chấp nhận chỉ khi preflight sizing đủ và fail closed nếu thiếu; giữ550s/500000 tokens mỗi run.
- Naive Wilson không tự chứng minh independence; plan giữ cluster precision gate và báo cluster recall/direction intervals. Không suy estimate trên enriched frame thành production prevalence/precision.

## Dấu vết bản đã review vòng đầu

Raw-byte SHA256 chụp trước planner sửa, không dùng thay LF-normalized digest của application:

| File | SHA256 |
|---|---|
| plan.md | `6f5e00a089c0d10370090f41e42a7735c43db1293a50420a11621bb64c6d8e25` |
| phase-2-direction-aware-quality-gates.md | `0904f3d77e8084ea42b84858f227fca1764965d1554959cfb646d99655f86c1c` |
| phase-3-rubric-and-reviewed-development-corpus.md | `7448003f956955efae114e4bdd595e0192b7637b09303738c38a983a3cc71ccb` |
| phase-4-bounded-development-experiments.md | `ae2f8d52f5b67e01dab8714b527ac8e2ce901aea18c306569a35b89f688840b5` |
| phase-5-fresh-heldout-and-product-verdict.md | `31f2177808a3d17b1daea709714c95ee2eb961085644de41c574ac1436d05f82` |

Final verdict chỉ được cập nhật sau đọc lại bản planner đã sửa; không xem narration “đã fix” là bằng chứng.

## Recheck bản sửa — final verdict PASS cho kế hoạch

Đã đọc lại đầy đủ nội dung sửa của plan, năm phase và graph; đối chiếu riêng source boundaries của ba findings. Không còn unresolved Critical/High finding trong **thiết kế kế hoạch được review**. PASS này cho phép trình kế hoạch/cook theo approval; không chứng nhận implementation, dataset readiness, measured quality hay activation. Historical product verdict và runtime OFF giữ nguyên.

| Finding | Disposition | Bằng chứng sửa trong packet hiện tại | Điều kiện cook còn phải chứng minh |
|---|---|---|---|
| RT-QR-01 | RESOLVED_IN_PLAN | `plan.md:138`, `:140`; `phases/phase-4-bounded-development-experiments.md:10`, `:14`; `phases/phase-5-fresh-heldout-and-product-verdict.md:13`, `:14`, `:15`, `:46`, `:47`, `:49` | Hoàn tất code/tests/review trước source freeze; hai same-winner confirmation PASS trên final code; summary bind cả hai report, immutable v2 predecessor audit và reject drift. Không third confirmation/tuning khi fail. |
| RT-QR-02 | RESOLVED_IN_PLAN | `phases/phase-2-direction-aware-quality-gates.md:25`, `:29`, `:41`, `:45`, `:46`; `phases/phase-3-rubric-and-reviewed-development-corpus.md:44`; `phases/phase-5-fresh-heldout-and-product-verdict.md:27`, `:31`, `:32`, `:46`, `:50`; graph P2/P5 inventories | New report-path CLI→API đúng schema/dataset, gold review-only lock trước measurement, reader dispatch không legacy fallback; offline integration/help kiểm arguments mới trước live. `test_cg_pairs_run.py` được khai báo Create ở P2 rồi Modify ở P5, chưa có lúc planning là đúng lifecycle. |
| RT-QR-03 | RESOLVED_IN_PLAN / validation obligation retained | `plan.md:126`, `:136`; `phases/phase-2-direction-aware-quality-gates.md:11`, `:35`, `:48`; `phases/phase-3-rubric-and-reviewed-development-corpus.md:13`; `phases/phase-5-fresh-heldout-and-product-verdict.md:9`, `:48`, `:62` | Membership hash-lock trước candidate generation; riêng MIN_N recall; fixture 53/60 +40 union-only vẫn 53/60 và FAIL; false DUPLICATE xét mọi output và precision giữ toàn prediction. |

Ledger đã khép kín: tối đa4 P4 tuning runs +2 final dev confirmations +1 oracle20pairs =7 dev runs, tối đa3500000 tokens, từng run550s/500000 tokens. Hai repeats mỗi B/C held-out riêng, cùng floor/model đã khóa; không dùng scope/budget tăng ngầm để cứu gate. Source/test inventory P5 là10 files được khai báo, graph phản ánh predictor/test/CLI handoff và manifest v1/v2; không còn ép bỏ caller khỏi inventory vì cap8 tùy ý.

Các điều kiện dữ liệu/independence vẫn là gate chưa chạy: fresh template clusters, independent reviewers, ≥60 positive từng nhãn trong recall frame, precision prediction counts và corpus sizing. Thiếu điều kiện nào phải report blocker giữ OFF; không gọi plan PASS là product PASS. Mã hiện hữu vẫn có các legacy giới hạn; chúng sẽ được sửa và kiểm trong cook, không được tuyên bố đã fix bởi lượt review này.

Raw-byte SHA256 của packet recheck:

| File | SHA256 |
|---|---|
| plan.md | `eaaf6abd793a5f54560dbbc4c61d896256b2ab8d530948cb5d073b5c1f4ba040` |
| plan-graph.yaml | `acf9cd3f333742344520cadf91d1d121a529d2b0d871dba85864df08b734f24b` |
| phase-1-evidence-and-pair-telemetry.md | `5185bea5ee618c6e22c28139251ce5c3417846615b253bf8102e37c0290d0794` |
| phase-2-direction-aware-quality-gates.md | `f524b0b62f77968e1f76f1650efaad9b89fdbc4d1532f2cb2b45a7c57fc1db19` |
| phase-3-rubric-and-reviewed-development-corpus.md | `8810423590d6803263c7156278d2ede77feee32eedcc8102b1f872f9b82d7bd0` |
| phase-4-bounded-development-experiments.md | `2e8b3d62665c4ef2f67ae8870581865cb59b251a1de9a19329753d57438956a9` |
| phase-5-fresh-heldout-and-product-verdict.md | `a701cfa1def9ea300206ac6fedfc383e09c15122cf8a8617f06d95ad33648e0e` |

Không thêm model calls hoặc implementation tests trong recheck. Chỉ append báo cáo được giao; không sửa code/plan/artifact khác.

## Freeze sau sửa attribution Wilson ở P2

Đã đọc lại `phases/phase-2-direction-aware-quality-gates.md:43`: evaluation dùng `bakeoff.wilson`/scorer; runtime `review_policy.wilson_lower` hiện dùng cùng arithmetic/default z=1.96, giữ thresholds và historical semantics. Không có khác biệt exact-z/rounded-z giữa hai helper hiện hữu.

Probe arithmetic hai helper thực, exit 0, không implementation tests hoặc provider calls:

```text
56 60 0.8407442010623228 0.8407442010623228 True
57 60 0.8629926537490016 0.8629926537490016 True
```

P2 raw-byte SHA256 cuối: `3388ff10e7314a98ec3fbc44fb9db19e6ee564a1a1bc1d739aabebc1adecb29c`. SHA P2 `f524b0...` trong bảng recheck trước chỉ bản trước sửa attribution; giữ làm lịch sử. Các disposition và **final verdict PASS cho kế hoạch** giữ nguyên; không thêm finding/blocker mới. Freeze review trên packet này; product vẫn chưa được đo/đạt và runtime OFF.
