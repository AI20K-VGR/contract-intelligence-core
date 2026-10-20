# Đánh giá clause-frame độc lập và quyết định release

Runner `evals.clause_frame_release` chạy tại checkout candidate đã freeze. Kết quả thống kê không cấp quyền release: `release_status` luôn `BLOCKED`, người dùng duyệt các bằng chứng cuối và quyết định riêng. Fixture tổng hợp chỉ chứng minh cơ chế; không thay gold trên hồ sơ thật.

## Người phụ trách và dữ liệu

Người dùng đã nhận vai trò reviewer/evaluator cuối. Cần thêm adjudicator độc lập với người chuẩn bị nhãn và reviewer. Gold có `producer`, `reviewer`, `adjudicator` khác nhau; nhãn nháp không được đổi thành approved bằng quyền tiếp tục triển khai.

Evaluator giữ manifest, gold, matched baseline và source OCR trong thư mục riêng ngoài Git. Không dùng `tmp/ai2-public-corpus` hoặc thư mục shared làm holdout mù. Có hồ sơ chính/phụ lục thực sự sửa đổi, dẫn chiếu và thời điểm hiệu lực được duyệt. Ba hợp đồng không liên quan không tạo thành chuỗi AMENDS.

Không cho người chỉnh AI2 xem chi tiết nhãn, lỗi hoặc output heldout. Khi deblind, đánh dấu holdout retired; lần cải thiện sau dùng holdout mới. Bản shared chỉ chứa hash, thống kê và lý do gate, không chứa đường dẫn, ID hồ sơ, raw text hoặc labels.

## Cách ly quyền truy cập thật

CLI hiện hỗ trợ kiểm chứng Windows bằng tài khoản OS riêng. `evaluator` trong receipt phải khớp `GetUserNameW`; `tuner` là tài khoản thật dùng để phát triển/chỉnh AI2, khác evaluator. Không dùng một account phụ không liên quan để giả cách ly trong khi agent phát triển vẫn đọc được holdout. Tài khoản tuner không được có quyền đọc manifest, matched baseline, source hoặc output riêng. Cần người vận hành tạo account/ACL thật, giữ mật khẩu trong biến môi trường `AI2_EVAL_TUNER_PASSWORD` của evaluator; không ghi mật khẩu vào receipt, lệnh hoặc Git.

Runner gọi `LogonUserW`, impersonate tài khoản tuner và thử mở file. Chỉ `PermissionError` mới chứng minh read-denied; file không tồn tại, đăng nhập thất bại hoặc khai báo JSON `denied: true` đều chặn đo. Token được đóng và impersonation được revert trước khi đọc dữ liệu. Linux chưa có adapter kiểm chứng quyền tương ứng, nên chặn đo.

Đây là bằng chứng read-denied tại lần chạy. Người dùng vẫn cần duyệt receipt ACL, tài khoản không có quyền quản trị và quy trình giữ holdout trước đó; không suy ra độc lập lịch sử chỉ từ ACL hiện tại.

## Freeze trước khi đo

Giữ Plan A nguyên trạng. Policy đầy đủ từ P1 có human approval/ref, timestamp có timezone và các pin dev baseline/dev gold/scorer/split/Plan A. Mỗi metric có unit, eligibility, predicate, strata, direction, threshold source, ngưỡng và minimum units do người dùng freeze. Runner chỉ hỗ trợ predicate `exact`, đủ sáu profile `SALES`, `SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA`.

Ngưỡng metric lỗi dùng direction `max`: `key_wrong_definite`, `pair_false_duplicate`, `citation_extra`, `value_fabricated`. Các metric đúng/coverage dùng `min`. False-DUPLICATE, extra citation và fabricated value có zero-error tripwire; citation validity và certainty safety phải đúng toàn bộ. Có precision spec cho từng disposition. Minimum Plan A 60 units/metric không bị hạ; DEC-3 yêu cầu ít nhất 120 eligible intra-dossier pair units tổng, phân tầng theo dossier, không phải 120 mỗi dossier. Policy cần `stratum_minimum_units` do người dùng freeze cho profile/dossier; runner không tự lấy minimum tổng làm minimum mỗi tầng. Mẫu ít hoặc thiếu metric không PASS. `NEEDS_REVIEW` chỉ là trạng thái, không tự tạo nhãn đúng.

Receipt `ai2.clause-frame.candidate-freeze.v1` do evaluator chuẩn bị sau khi người dùng duyệt:

- `approved_by: user`, `approval_ref`, `evaluator`, `tuner`.
- `frozen_at`, `tuning_started_at`, `holdout_first_visible_at`, `measurement_started_at`: timestamp có timezone, policy trước tuning, candidate trước visibility/measurement.
- `retired: false`, `deblinded: false` cho holdout đang mù.
- `gold_hash`, `policy_hash`, `baseline_hash`, `candidate_code_hash`: SHA-256 của bytes/input thực tế. `code_digest()` bao gồm cả file Python chưa commit, không chỉ HEAD.
- Các pin P1 `dev_baseline_hash`, `dev_gold_hash`, `split_hash`, `historical_plan_a_card_hash` khớp policy.
- `runtime_pins`: provider/model và SHA-256 prompt implementation, budget, profile. `prompt_hash` là hash file `app/pipeline/frame_context.py`; `profile_hash` là canonical hash map dossier→semantic profile digest; `budget_hash` là canonical hash map dossier→`{context: context_bounds, job: budget_limits}`.
- `private_outputs`: map `local-only`/`enriched` tới hai file output riêng đã có ACL đúng. Evaluator tạo mỗi file với đúng bytes `{}` (không newline) trước freeze. Runner kiểm read-denied, khóa file và chỉ dùng placeholder một lần; file đã có kết quả bị từ chối, không overwrite labels/input.

Canonical hash dùng JSON UTF-8 `ensure_ascii=False`, `sort_keys=True`, `separators=(',', ':')`. Freeze không phải file mẫu đã approved; thiếu giá trị thật thì giữ BLOCKED.

## Matched baseline và eligibility

Baseline dev P1 chỉ là calibration. Numeric comparator cho heldout phải được evaluator chạy trên cùng protected gold với baseline code đã freeze, giữ model/prompt/policy/budget/source/profile giống candidate. Artifact riêng có schema `ai2.clause-frame.matched-baseline.v1`, split `heldout`, `gold_hash`, `policy_hash`, `baseline_code_hash`, `runtime_pins`, `units` theo `UnitRecord`.

Gold giữ schema P1 `ai2.clause-frame.gold.v1`, split `heldout`, approval/consent refs và nhãn `exact` có identity binding. Dossier source là canonical `be.ai2.processing.request.v1` chứa snapshot chính/phụ lục, semantic profile và budget đã pin; file source hash khớp manifest. Mỗi unit có metric/item/unit identity ổn định, dossier/profile, evidence ref, `path`, `identity_path`, `identity_expected`, `expected`.

Danh sách eligible units phải do reviewer xác định trước output. Baseline units phải khớp toàn bộ eligibility và cluster, không lọc denominator theo key candidate tìm được. Mỗi ordinary slot, PARAMETER slot, timeline target/date-role/date-value/trigger/value là gate riêng. Tripwire extra citations/fabrication cần nhãn kiểm tra toàn bộ output liên quan, không chỉ một citation tình cờ hợp lệ.

## Chạy tại account evaluator

Thiết lập producer/caps đã duyệt; mặc định producer vẫn OFF. Đặt `AI2_SEMANTIC_ENABLED=true` và `AI2_SEMANTIC_CONTEXT_CAPS` đầy đủ bằng caps đã freeze. Source policy và context bounds giữ cố định; không chỉnh cap sau khi xem lỗi.

```powershell
& ai-service/.venv-ai2-frame/Scripts/python.exe -m evals.clause_frame_release measure --manifest $privateGold --split heldout --baseline $privateMatchedBaseline --thresholds $frozenPolicy --freeze $candidateFreeze --mode local-only --private-out $privateLocalOutput --out $sanitizedLocalReport
& ai-service/.venv-ai2-frame/Scripts/python.exe -m evals.clause_frame_release measure --manifest $privateGold --split heldout --baseline $privateMatchedBaseline --thresholds $frozenPolicy --freeze $candidateFreeze --mode enriched --private-out $privateEnrichedOutput --out $sanitizedEnrichedReport
```

Local-only gọi adapter→`run_idp`→wire serializer thật, không LLM/vector. Enriched chỉ nhận source có verified anonymization/ref và provider đã freeze `http://localhost:20128/v1`; đọc `/models` trước và yêu cầu model hiện có đúng pin. Key lấy từ environment, không tự lấy OpenAI fallback hoặc đổi model khi heldout đang đo. Provider unavailable thì chặn; muốn dùng provider khác cần probe dev, matched baseline và policy freeze mới trước một holdout mù mới.

Output exclusive-create, không overwrite gold/baseline/policy/source. Runtime/source/manifest/policy/receipt hash đổi trong replay thì BLOCKED. Chưa có isolation/approved gold/freeze thì CLI dừng trước khi nạp nhãn hoặc gọi pipeline. Báo cáo đủ x/n, Wilson, cluster interval và zero-error bound; không kết luận bảo đảm độ đúng của toàn bộ quần thể từ mẫu không lỗi.

Raw output và scored units nằm trong `ai2.clause-frame.private-result.v1` của evaluator để review lỗi và paired ablation. Shared report không chứa các dữ liệu này. Recheck quyền read-denied trước ghi output; isolation drift phải retire holdout. Usage chỉ MEASURED khi có đủ counter/token/time thực tế; retry/fallback không có token metadata đầy đủ khiến cost NOT_MEASURED, không tự xem unknown token cost là0.

## Nghiệm thu cuối và rollback

Giữ riêng technical test evidence, measured quality và manual release evidence. Human reviewer kiểm tra nguồn/citation, PARAMETER và AMENDS thật, policy/holdout receipt, UI keyboard/mobile, provider/budget, workload alias và rollback drill. Dùng `manual_test_anchor.py` cho session thật, không tự viết receipt PASS.

Query Plan A `used_llm=true`, n≥60, p95<20s và các gate lịch sử còn phải đo độc lập; runner clause-frame không thay query benchmark. Không đổi ngưỡng lịch sử để hợp thức hóa candidate. Khi thiếu bằng chứng này, quality diagnostics có thể PASS(point) nhưng release vẫn BLOCKED.

Rollback tắt semantic producer/enrichment và alias activation, replay run/profile đã pin trước đó; giữ lịch sử alias/read model/audit. Không xoá migration history, sửa raw OCR, relabel holdout hoặc dùng overlay HITL để tự đổi alias rules. Chạy lại HTTP/PostgreSQL restart/retry/409/tenant-denial và query/review smoke sau rollback thật.
