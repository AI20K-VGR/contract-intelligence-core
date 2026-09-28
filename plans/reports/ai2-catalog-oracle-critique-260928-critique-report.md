# Critique hợp nhất — eval oracle (advisory)

**Scope:** `ai-service/fixtures/catalog.py` (`expected_state`, `expected_no_claims`) được chấm bởi `ai-service/scripts/live_eval.py` `_evaluate_case`. Câu hỏi: điểm xanh có chứng minh case khớp hợp đồng sản phẩm hay không.
**Lenses:** red-teamer · code-reviewer · independent-revalidator (không thiếu lens; không lens nào trả `[]`).
**Path stamp:** inline-Task fallback. Planner chọn Workflow (`confirm_required`, ultracode tắt). Người dùng duyệt chạy Task.
**Mode:** advisory. Không ghi `critique-consensus.json`.

## Bảng đếm

`blocker 2 · major 2 · minor 2`

## Top findings

**1. blocker, proven.** Gate `expected_no_claims` không bắt hành vi. `ai-service/scripts/live_eval.py:275-276` so token snake_case (`legal_winner`, `full_pdf_dump`) như substring của `json.dumps(answer)`. `ai-service/fixtures/catalog.py:251` khai `["legal_winner", "full_pdf_dump"]`. Câu trả lời tiếng Việt không chứa các token đó. Case không query có `answer` null, nên `answer_text` là chuỗi `null`. `forbidden_hits` rỗng theo cách viết scorer.
Hệ quả: sản phẩm có thể làm đúng việc bị cấm mà cổng forbidden-claim vẫn báo 0.
Fix: mỗi token phải thành một kiểm tra trên trường có cấu trúc (`answer`, `citations`, `handoff_issues`). Khi `expected_no_claims` khác rỗng mà answer null, case phải fail.

**2. blocker, proven.** Nhánh `else` không so `expected_state`. `ai-service/scripts/live_eval.py:299-300` chấp nhận `actual_state` thuộc `{PASS, NEEDS_REVIEW, SUCCEEDED, REVIEW}`.
Hệ quả: case khai `REVIEW` (EC-020, EC-027, EC-029, SALE-BRD-07) vẫn xanh khi sản phẩm trả `PASS`. Khoảng một nửa catalog mất nghĩa của `expected_state`.
Fix: `PASS` chỉ khớp `PASS`. `REVIEW` chỉ khớp `NEEDS_REVIEW`. Bỏ `SUCCEEDED` khỏi tập review state.

**3. major, proven.** Case `BLOCKED` xanh khi extract HTTP lỗi. `ai-service/scripts/live_eval.py:290` là `actual_state == "BLOCKED" or not extract_ok`.
Hệ quả: EC-045, EC-049, EC-053, EC-054, EC-056, HAPPY-006 có thể xanh vì HTTP 500, không phải vì policy chặn đúng.
Fix: bắt `actual_state == "BLOCKED"`. HTTP lỗi là một loại fail riêng.
Mức major, không phải blocker: chỉ kích hoạt khi extract lỗi, không sai trên mọi lần chạy thành công.

Finding major còn lại, không nằm top 3: case `INSUFFICIENT` không có query rút về `extract_ok`. `ai-service/scripts/live_eval.py:294-297`. EC-022 xanh trên mọi HTTP 200, không kiểm “không bịa mốc lịch”.

Minor: token chết `SUCCEEDED` trong accept-set (gộp vào finding 2); `citation_valid` thành true khi không có query vì `ask_payload` rỗng (`live_eval.py:265-274`); rủi ro substring false-positive nếu sau này match trên văn bản tự do (suspected).

## Per-lens

Ba lens cùng chỉ vào hai root cause: substring `expected_no_claims`, và accept-set không phân biệt PASS với REVIEW. Independent-revalidator chạy sealed-room, phân loại claim “oracle đúng” là OVERTURN, và CONFIRM riêng EC-050/EC-055 tại `live_eval.py:282-288` khớp `tests/test_ec_policy_block.py` (job `SUCCEEDED`, review `BLOCKED`). Phần CONFIRM đó không phải finding.

## Repeat-offense

Không có báo cáo critique trước đó về lỗ scorer này. Fingerprint: null.

## DEC-worthy

Không. Việc siết scorer nằm trong oracle eval, không mở ranh giới kiến trúc mới của sản phẩm.

## Verdict: BLOCKED

Hai blocker proven còn lại sau khi gộp. Điểm xanh của `live_eval.py` không chứng minh case trong `catalog.py` khớp hợp đồng. Cổng câu bị cấm rỗng theo cách viết. Nhánh còn lại không phân biệt PASS với REVIEW. Hai major (HTTP 500 tính là BLOCKED; INSUFFICIENT không query chỉ cần HTTP 200) làm nặng thêm và không đổi verdict.

Không sửa code trong lượt này.
