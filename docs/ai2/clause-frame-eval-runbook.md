# P1: dev baseline và independent evaluation

## Trạng thái

Scorer exact-unit và CLI dev calibration đã có. P1 chưa hoàn tất: chưa có reviewer/adjudicator/evaluator độc lập, approved dev gold, bằng chứng ACL holdout hoặc metric policy được user freeze. CLI không phát hành quality PASS. Chưa đo accuracy trên hợp đồng thật; không dùng tests synthetic thay business gold.

## Entry points

Cwd source worktree `tmp/ai2-golive-261002`. Interpreter riêng: `ai-service/.venv-ai2-frame/Scripts/python.exe` sau khi cài extras dev/web và kiểm `pip check`.

`python -m evals.clause_frame_baseline readiness --manifest <approved-dev-manifest.json> --split dev --out <gold-readiness.json>`

`python -m evals.clause_frame_baseline baseline --manifest <approved-dev-manifest.json> --split dev --out <baseline.json>`

Exit2: BLOCKED. Exit0 readiness: READY_FOR_CALIBRATION; baseline: CALIBRATION_ONLY. Không đồng nghĩa quality-ready. Manifest mixed/heldout bị từ chối trước replay, report không echo ID/path/nhãn của holdout. Output phải là file mới; dùng tên run mới khi chạy lại, CLI từ chối ghi đè gold/source/policy hoặc report có sẵn. Manifest hash/HEAD pin trước replay, drift sau replay bị reject; source hash cũng kiểm lại. Readiness kiểm thêm source hash đúng định dạng, file thật không phải symlink, profile dossier/unit và metric thuộc danh sách đóng. Khi truyền `--policy`, CLI đối chiếu `dev_gold_hash`, `scorer_hash`, canonical `split_hash` và hash Plan A hiện tại; mismatch bị BLOCKED. Baseline hiện chỉ chạy production `evals.real_pipeline.run_processing` local/no-egress. Live matched-provider/prompt experiment và full frozen policy validation chưa có; không dùng local/no-egress receipt để so với historical live Plan A.

## Dev manifest v1

CLI pin hash runner/scorer/policy trước replay, đọc policy trước khi chạy và kiểm lại các hash khi kết thúc. Nếu file đổi hoặc biến mất, receipt trả `RUNTIME_INPUT_DRIFT`, bỏ units và diagnostic metrics; pins giữ giá trị trước chạy. Kiểm tra này phát hiện drift giữa hai thời điểm, không thay môi trường immutable hoặc full dependency/source-tree pin.

Schema `ai2.clause-frame.gold.v1`; `split=dev`; `approved=true`; producer/reviewer/adjudicator là ba người khác nhau; `approval_ref`, `consent_ref`. Holdout receipt gồm approved/evaluator/isolation_ref/split_hash. Đây là reference để người phụ trách kiểm chứng, không tự chứng minh ACL hay phê duyệt thật chỉ bằng JSON.

`dossiers`: id, split=dev, profile, source_kind=real, path đến immutable AI1 snapshot, sha256, amendment_chain_verified. Body/annex/variants cùng dossier và split. Có real chain được người duyệt xác nhận; đừng ghép hai hợp đồng độc lập thành AMENDS.

`units`: metric, item_id, unit_id, dossier_id, profile, path (list JSON keys/indices vào production output), expected, predicate=exact, evidence_ref. `identity_path` và `identity_expected` bind frame/edge với stable source reference đã annotator chọn; cùng actor ở frame khác không được PASS chỉ vì vị trí row giống nhau. IDs và denominator lấy từ nhãn trước khi xem output. Path/identity thiếu là FAIL/missing, không lọc khỏi denominator. `expected` chỉ nằm trong dữ liệu gold local; production replay không nhận expected labels. So sánh JSON kiểm type đệ quy để true không được coi bằng1 kể cả trong object/list.

Không commit PDF/raw snapshot/gold/keys. CLI output chỉ units passed/detail và pins/hash, không actual/expected raw text. Profile/provider/prompt/policy pins bổ sung và frozen metric strategy card vẫn là việc phải hoàn tất trước P1 PASS.

## Scorer và regression

Policy được kiểm tra trước production replay. Policy không hợp lệ không chạy baseline; report trả `BLOCKED`. Năm pin bắt buộc phải là SHA-256 lowercase 64 ký tự; cả thời điểm freeze và tuning (nếu có) phải có múi giờ, freeze phải trước tuning. Readiness và policy chỉ nhận metric trong danh sách đóng, gồm precision của semantic disposition đã định nghĩa; suffix tùy ý không được nhận. Kiểm tra định dạng hash không chứng minh nội dung hoặc approval; runtime chỉ đối chiếu các pin có nguồn hiện tại.

`compare_units` so `(metric,item_id,unit_id)`: baseline PASS thành FAIL/mất unit/mất item đều regression. New failing tripwire cũng chặn. Duplicate identities là setup error. Giữ `unit_metrics.py` read-only; chỉ dùng `evaluate_metric` cho point/Wilson/cluster. `score_units` yêu cầu specs, mỗi metric riêng; NOT_MEASURED/UNDERPOWERED/FAIL không PASS. Threshold mới không tự đặt95%; user freeze sau dev error-review.

P1 strategy card phải định nghĩa đủ metric ordinary/PARAMETER/timeline, denominator, predicate, strata, minimum-unit count, quality threshold, citation/value safety và timestamp trước tuning. `--policy <file>` gọi structural validator để chặn card thiếu/invalid; đây không xác minh approval thật, pin hashes/strata đầy đủ hay source citation extras. Tests/scorer hiện tại không đủ để coi card hoàn chỉnh; full strategy audit vẫn blocking debt trước P1 PASS.

## Holdout

Chưa có evaluator. Khi được chỉ định, giữ manifest/labels/results ở tài khoản hoặc máy riêng; chứng minh tuner read-denied thật, không chỉ đổi tên thư mục. Tuner chỉ dev labels và sanitized split readiness/hash. Evaluator chạy baseline/candidate frozen cùng holdout sau candidate freeze. Khi deblind, retire holdout; lần tuning tiếp theo cần holdout mới.

## Kiểm chứng

`python -m pytest evals/tests/test_clause_frame_baseline.py evals/tests/test_clause_frame_scoring.py -q -p no:cacheprovider`

Full suites theo P1 phải thực chạy và báo tất cả failures/skips. Có thể xanh focused tests nhưng P1 BLOCKED. Không viết verification PASS hoặc tiến P2 khi gold/policy/isolation còn thiếu. Dừng P1 để user tìm reviewer; giữ dữ liệu local và báo dependency môi trường chính xác.
