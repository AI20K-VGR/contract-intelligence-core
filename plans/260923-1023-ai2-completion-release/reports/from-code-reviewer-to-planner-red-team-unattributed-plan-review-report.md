# Red-team report — inline plan review

Ngày: 2026-09-23  
Personas: Security Adversary, Failure Mode Analyst, Maintainer 6-months-later,
Bad-day Operator.

## Findings

| ID | Sev | Finding | Suggested fix |
|---|---|---|---|
| RT-01 | H | Plan nói citation invalid “không được publish” nhưng authoritative publish nằm ngoài AI2; wording hiện tại có thể khiến cook xây nhầm publish service trong scope (`plan.md:45-56,123-137`, `docs/system-architecture.md:25-29`). | Đổi acceptance thành “không được đánh dấu eligible/authoritative trong AI2 result”; phase 3 chỉ tạo proposal/review gate và ghi rõ BE publish ngoài scope. |
| RT-02 | H | Replay inputs nằm ở `C:\Users\dungs\Downloads\...` ngoài repo; test integration hiện skip nếu file không có (`ai-service/tests/test_ai1_ocr_lab_integration.py:19-20,36-38`), nên một green offline suite không chứng minh hai corpus thật đã chạy. | Ghi replay là conditional local evidence; acceptance bắt buộc report `NOT_RUN` khi thiếu path, còn deterministic fixture phải là gate bắt buộc. Không copy raw JSON/PDF vào repo. |
| RT-03 | H | Phase P2/P4 sở hữu nhiều file và P2 chạm cả pipeline lẫn reasoning; plan decomposition quy định >8 files phải challenge/split (`plan-graph.yaml:22-40,58-74`, `phase-decomposition.md`), dễ tạo phase commit khó review và conflict khi cook. | Giữ execution tuần tự nhưng giới hạn file modify thực tế; các reasoning/docs chỉ là read/verification trừ khi test chứng minh gap, hoặc tách thành sub-step rõ trong phase. |
| RT-04 | H | `scope-sizing.json` đo `multi` với 432 cells/8 sub-plans nhưng plan chỉ có 4 phase và quyết định `proceed`; nếu không có exit criteria, scope sẽ phình thành platform (`artifacts/scope-sizing.json`, `plan.md:112-121,158-160`). | Giữ một plan vì shared contract, nhưng thêm hard stop: không thêm BE/FE/OCR/infra; nếu phase vượt touchpoints hoặc đổi contract ngoài P1 thì mở plan mới. |
| RT-05 | M | Các `post` artifact trong graph (`verification-P1..P4.json`, `review-decision.json`) chưa được chỉ rõ actor, command, path và check types trong phase; presence gate có thể thấy file nhưng không chứng minh nội dung (`plan-graph.yaml:21,41,57,74`, `artifact-verification.json:3-7`). | Mỗi phase phải ghi post artifact dưới `plans/<id>/artifacts/`, chứa `phase`, exact command, checks và verdict; P4 thêm human review decision sau khi verification xong. |
| RT-06 | M | `198 passed` là baseline của dirty tree hiện tại, không phải proof sau cook; nếu đưa vào summary như acceptance sẽ che regression (`research/repo-evidence.md` probe và `plan.md:39-40,168`). | Gắn nhãn baseline-only; chỉ verification artifacts sau từng phase mới được dùng làm release evidence. |
| RT-07 | M | Nếu provider/live credential thiếu, `--strict`/live gate có thể bị hiểu là release fail hoặc pass không rõ; current docs tách live nhưng plan chưa định nghĩa verdict cho `NOT_RUN` (`phase-4-release-verification.md:64-78`, `scripts/live_eval.py:450-586`). | Quy định offline release có thể PASS với live=`NOT_RUN` chỉ khi human chấp nhận phạm vi; live nếu đã bắt đầu mà machine failure/citation invalid thì BLOCKED/FAIL, không downgrade. |
| RT-08 | M | Hai file có cùng `dossier_id` nhưng khác contract type; nếu batch logic sau này thay `INDEPENDENT` hoặc dùng dossier làm key, có thể tạo false relation (`research/repo-evidence.md`, `app/pipeline/ai2_batch.py:67-123`). | Giữ `relation_policy=INDEPENDENT` immutable cho package v1, thêm regression assert trên đúng hai IDs và reject unsupported relation policy. |
| RT-09 | H | Hai JSON hiện tại là producer profile có table nested dưới `pages[*].tables`; `doc-002` còn có cell `CLAIMED` dù table `MEASURED`. Nếu plan chỉ nói root `tables` hoặc table-level geometry, AI2 có thể bỏ qua evidence thật hoặc nâng cấp provenance sai. | Bổ sung topology assertions, phân biệt table/cell provenance và dùng đúng counts 1 + 3 tables, 0 + 2 continuity records trong docs/phase gate. |
| RT-10 | M | Một số tài liệu release cũ ghi số liệu lịch sử (`196 passed`, live score cũ) như gate hiện tại, dễ tạo false confidence sau khi input AI1 đã thay đổi. | Đánh dấu baseline-only, ghi replay 2026-09-23 riêng và cấm dùng số liệu cũ làm release evidence nếu chưa rerun. |

## Pre-mortem lenses

- Technical: P2/P3 dễ làm mất raw unit hoặc hạ citation gate; đã khóa bằng targeted
  tests và partial/fail-safe acceptance.
- UX: `NEEDS_REVIEW` có thể bị hiểu là lỗi; report/README phải nêu reason và evidence,
  không đổi state cho đẹp.
- Adoption: live provider không sẵn sàng; offline package vẫn usable nhưng live score
  phải `NOT_RUN`, không giả pass.
- Organizational: BE/FE/OCR owners bị kéo vào; out-of-scope và hard stop RT-04 ngăn
  scope drift.
- External: provider rate limit/credential thay đổi; retry bounded và live gate tách
  khỏi offline.
- Security: local paths/raw inputs/egress có nguy cơ lộ dữ liệu; không commit raw,
  service envelope/tenant scope và egress fail-closed là điều kiện bắt buộc.

## Verdict

**REVISE THEN RE-REVIEW.** Plan direction đúng. RT-01/02/05/06/07/08/09/10 đã
được propagate vào plan/phase/docs; RT-03/04 được giữ như hard scope controls,
không để cook tự diễn giải. Cần chạy lại harness validation trước human approval.
