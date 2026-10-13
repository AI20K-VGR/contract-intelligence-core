# Runbook đánh giá độc lập cho sửa conflict AI2

Runbook này mô tả cách biến regression của kế hoạch `261004-0346-ai2-conflict-repair` thành một phép đo có thể kiểm toán. Bộ dữ liệu tổng hợp chỉ kiểm tra cơ chế. Không dùng chúng để kết luận AI2 đúng trên hợp đồng thật. Người dùng là reviewer/evaluator cuối; cook plan không phê duyệt gold, holdout, policy hay phát hành.

## Trạng thái hiện tại

Quality release đang **BLOCKED** cho tới khi có đủ ba bằng chứng thật và được reviewer duyệt: gold trên hồ sơ thật đã adjudicate độc lập; holdout được cách ly khỏi người chỉnh AI2; policy metric đã freeze trước khi candidate/holdout lộ. Không tạo dữ liệu hoặc approval giả để làm xanh gate. Báo cáo chia riêng `quality_status` (kết quả đo), `release_status` (luôn cần duyệt thủ công), số eligible, sổ loại trừ và khoảng bất định.

## Vai trò và chuẩn bị dữ liệu

- Người gán nhãn tạo bản nháp với citation tới trang/đoạn/bảng và nhãn theo schema clause-frame.
- Reviewer hợp đồng duyệt nhãn mà không xem output candidate. Adjudicator độc lập xử lý bất đồng. Producer, reviewer, adjudicator phải là ba người khác nhau.
- Evaluator giữ source OCR, manifest gold, baseline matched và output riêng ngoài Git. Người chỉnh AI2 không có quyền đọc chúng; receipt phải phản ánh ACL/account thật, không dựa trên cờ JSON tự khai.
- Chia theo dossier/package để cùng hợp đồng, phụ lục và amendment không rơi vào các split khác nhau. Holdout từng được xem phải retire; đánh giá lần sửa sau cần holdout mới.
- Đưa cả ca consistent/inconsistent, schedule, số tiền/đơn vị/thuế, amendment, dẫn chiếu và layout khác nhau. Kiểm chứng chuỗi amendment từ source; ba hợp đồng rời nhau không thay thế một chuỗi sửa đổi.
- Trong manifest gold, mỗi eligible unit giữ metric/item/unit identity, dossier/profile, evidence ref, exact predicate, đường dẫn giá trị và identity binding. `exclusions` là danh sách đã review; mỗi phần tử trong manifest riêng phải có đúng `metric`, `item_id`, `unit_id`, `dossier_id`, `category`, `reason`. Identity dùng để kiểm tra loại trừ duy nhất và không giao với eligible units; identity luôn ở khu vực private. `category` chỉ nhận `PAIR`, `CLAUSE`, `CITATION`, `TIMELINE`, `DOCUMENT`; `reason` chỉ nhận `OUT_OF_SCOPE`, `SOURCE_AMBIGUOUS`, `OCR_UNREADABLE`, `NOT_APPLICABLE`, `DUPLICATE_SOURCE`, `MISSING_SOURCE`, `INSUFFICIENT_EVIDENCE`. Chỉ số đếm gộp theo category/reason được phép ra report chung; ID, path và free-form text không được đưa ra.

## Freeze trước khi mở candidate

Reviewer freeze Plan A, định nghĩa metric, eligibility, strata, hướng/ngưỡng, minimum tổng/từng tầng, workload/cost/latency policy và timestamp trước tuning. Giữ các pin dev baseline/gold, scorer, split, Plan A và runtime. DEC-3 yêu cầu ít nhất 120 eligible pair units tổng cùng zero observed false-DUPLICATE; báo denominator và uncertainty, không diễn giải thành xác suất lỗi tổng thể bằng 0. Các giới hạn Plan A hiện có không tự được sửa theo kết quả candidate.

Evaluator tạo matched baseline trên cùng holdout và đúng model/prompt/policy/budget/profile/source pins. Sau đó đóng băng candidate code digest và runtime. Receipt phải chứng minh holdout chưa bị deblind và tuner bị từ chối đọc bằng account thật. Thiếu pin, receipt, approval hoặc source thật thì dừng ở `BLOCKED`.

## Chạy phép đo

Trước hết chạy regression scorer với fixture tổng hợp:

```powershell
ai-service/.venv-ai2-frame/Scripts/python.exe -m pytest evals/tests/test_conflict_repair_eval.py evals/tests/test_clause_frame_release.py -q
```

Khi và chỉ khi reviewer đã duyệt hồ sơ, gold, policy, matched baseline và receipt thật, evaluator chạy CLI theo hướng dẫn chi tiết trong [clause-frame-release-runbook.md](clause-frame-release-runbook.md). Dùng thư mục private của evaluator cho manifest, source, baseline, freeze và output thô; output tổng hợp dùng chung chỉ giữ hash, số liệu và gate reason. Không commit hợp đồng, nhãn, private result, token/provider key hoặc đường dẫn nhạy cảm.

Report cần cho mỗi metric và strata: `passed`, `failed`, `n`, point estimate, Wilson interval, cluster interval; với zero-error metric, báo upper bound. `eligibility.eligible_pair_units` đếm eligible pair cố định trong gold; `eligibility` cũng ghi tổng eligible units và exclusion counts theo category/reason. Nếu sổ loại trừ chưa được cung cấp, số loại trừ là `null` với trạng thái `NOT_REPORTED`, không được hiển thị thành 0. Runner từ chối row sai schema, code ngoài danh sách, identity trùng hoặc giao với eligible set. ID hồ sơ và identity unit không xuất hiện trong report.

## Đọc kết quả và quyết định

- `PASS(point)` chỉ là ước lượng điểm trên mẫu eligible; không tự cấp release.
- `UNDERPOWERED`, `NOT_MEASURED`, `FAIL`, thiếu metric/strata, drift pin, exclusion ledger chưa báo hoặc zero-error tripwire bị vi phạm đều giữ release **BLOCKED**.
- `release_status` vẫn `BLOCKED` trong runner. Reviewer kiểm nguồn/citation, PARAMETER, timeline, amendment, workload và các guardrail sau khi đọc gói kết quả trong khu vực được phép.
- Không dùng cặp nghi vấn làm xung đột đã xác nhận. `NEEDS_REVIEW` là trạng thái chờ người quyết định.
- Nếu holdout bị lộ, ACL drift hoặc input/candidate thay đổi trong lúc replay, retire bộ holdout và thu thập/freeze lại; không sửa nhãn để khớp output.

## Gate hiện tại và điều còn thiếu

Các test của P6 chỉ xác nhận scorer báo mẫu/khoảng bất định, tổng hợp exclusion không định danh và giữ trạng thái release fail-closed. Chúng không tạo approved gold hay chứng minh ACL trên dữ liệu thật. Chưa có reviewer label packet được duyệt, receipt cách ly holdout hoặc metric-policy freeze thật trong artifact của plan; vì vậy chưa đo accuracy release và không thể tuyên bố AI2 đã hết lỗi trên hợp đồng khác.
