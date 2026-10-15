# Probe và ràng buộc lập kế hoạch

Ngày: 2026-10-10. Worktree `feature/ai2-contract-graph`; HEAD `681ff4ca300b1d03c131453d5290f8bba1d9bc8f`.

## Bằng chứng đã chạy

- [OBSERVED] Đọc `l2-p6-bakeoff.json`: approved gold `UNRELATED=554`, `CONFLICT=30`, `DUPLICATE=29`, `GENERAL_SPECIFIC=34`, `REFERENCE=8`.
- [OBSERVED] Đọc `l2-p6-classifier-calibration.json/current_reviewed_run`: `n_gold=4`, false DUPLICATE `observed=0, unreviewed=1`, P3 gate `PASS`. Gate hiện hành chỉ yêu cầu C/D nonzero; chưa chứng minh generalization hoặc tính an toàn của prediction chưa duyệt.
- [OBSERVED] Gọi scorer thực `score_relations` bằng Python trong `ai-service/.venv`: gold GS hướng A, prediction GS hướng B cho cùng pair. `precision_conservative=1/1`, `recall_observed=1/1`, `direction_accuracy=0/1`. Metric hiện tại đếm đúng nhãn dù sai hướng; giữ metric legacy và bổ sung metric hướng đúng, không đổi lịch sử.
- [OBSERVED] Probe REFERENCE với gold/prediction đều thiếu direction được scorer đếm direction `1/1`. Metric mới phải yêu cầu rõ A/B và fail closed khi thiếu hướng.
- [OBSERVED] Gọi `bakeoff.wilson`: 56/60 lower `0.8407442010623228`; 57/60 lower `0.8629926537490016`; 60/60 lower `0.9398260695220669`. Đây là số production implementation; báo cáo research dùng z làm tròn nên có chênh lệch thập phân nhỏ, không dùng con số research thay kết quả scorer.
- [OBSERVED phép tính, nguy cơ giả thuyết] Gọi Wilson production: 53/60 lower `0.7782097940014187`; thêm40 positives chỉ từ candidate union được53+40/60+40=93/100, lower `0.8625032899347025`. Chưa có implementation mới để khẳng định bug đang xảy ra; minh họa vì sao recall membership phải khóa độc lập trước candidate generation, union-only rows chỉ dùng precision/safety.
- [OBSERVED, phạm vi hẹp] Gọi `bakeoff.decide()` với `_checked_trials` được inject các trial đã có precision 60/60 và cluster lower 1.0, recall 0/60, false duplicate 0 và trong budget. Hàm trả `ENABLE_CANDIDATE`. Probe kiểm riêng nhánh quyết định; không chứng minh fixture này vượt toàn bộ preflight/provenance. Cần regression end-to-end cho thiếu/below-floor recall trước sửa.
- [DERIVED] Cross-join candidate metadata diagnostic trước với final predictions: C1 `27/56/13/1/4`, C2 `27/62/8/1/3`, B1 `24/66/11/0/0`, B2 `24/63/10/1/3` theo thứ tự candidate_miss/no_accepted_prediction/wrong_label/wrong_direction/correct. Candidate SHA của hai artifact khớp và positive ID khớp. SHA current raw bytes khác vì CRLF; sau dùng đúng `dataset.file_digest` normalize LF thì candidate SHA khớp frozen. P1 phải replay toàn bộ frozen source/context vì builder/resolver và dependency có dirty edits, không kết luận từ candidate SHA một mình.
- [OBSERVED] Probe `predictor.candidate_set` thực với tất cả docs `split=heldout` trong P5 report (không gọi model, không tune): current runtime C có174 candidates, covered74/101 positives; B có165 candidates, covered77/101; missing docs0. Kết quả tái hiện ceiling lịch sử trên current runtime cho dữ liệu này, vẫn không chứng minh toàn bộ runtime/config P5 identical. Lỗi probe ban đầu thiếu doc do lặp cả dev manifest entries đã được sửa bằng filter split; không có data thực sự thiếu ở heldout.
- [OBSERVED] Chạy bằng Python hệ thống thiếu dependency; probe thành công bằng `.venv` của worktree. Mọi command plan phải dùng interpreter này và PYTHONPATH chính xác.

## Năm điều đã chốt

1. Output: kế hoạch, phase files, graph, research, phản biện và receipt validation dưới `plans/261010-2022-contract-graph-quality-recovery/`; triển khai sau approval.
2. Acceptance sản phẩm: recall Wilson lower >=0.85 theo từng scored label, precision gate hiện hành MIN_N60/Wilson>=0.85, đúng hướng cho directed labels, false DUPLICATE observed/unreviewed đều0 trước enable recommendation, trong budget.
3. Scope: scorer/gates, diagnostic telemetry, corpus/rubric/review, candidate/classifier, evaluation. BE/UI/schema business/storage/migration và tự bật runtime ngoài scope.
4. Ràng buộc: `cx/gpt-5.5`, requested/served provenance, consent, grounding, review locks, 550s/500000 tokens, không tune heldout hoặc hạ floor. Raw corpus/payload/secret chỉ local ignored state.
5. Touchpoints: `evals/contract_graph/pairs/{score,bakeoff,predictor,recall_diagnostic,manifest,review}.py`, classifier/candidate/builder và tests tương ứng; file list cuối do planner định nghĩa.

Scope posture: HOLD, giữ mục tiêu đã được người dùng chấp thuận. Complexity: complex, khoảng 5 phases; risk: evaluation leakage, rubric mismatch, gate bypass. Không dùng grid vì pipeline tuyến tính, không có đủ trục UI/API/infra độc lập.

## Constraint scan

- Main `CLAUDE.md` áp dụng; worktree không có bản riêng. Skill `hs:plan` chỉ ghi dưới plans; không sửa source trong lượt này.
- Worktree có nhiều thay đổi chưa commit từ công việc khác, gồm candidate/builder và contract models. Cook phải chụp diff inventory, đối chiếu ownership rồi tích hợp đúng chức năng; không reset/stash/revert chúng.
- `docs/standards/` chưa có ở main hoặc worktree; `docs/code-standards.md` và `docs/system-architecture.md` có trong worktree, planner đã đọc. Dùng các chuẩn dự án này, shared harness rules TDD/verification/operational discipline và chuẩn bổ sung trong chính plan.
- CLI Windows launcher hiện lỗi khi thực thi; gọi Python entrypoint của harness main với HARNESS_BIN_ROOT main và HARNESS_DATA_ROOT worktree/.harness. Luôn chỉ định absolute plan path để tránh chọn nhầm plan.
- HG-1/HG-2 hiện tại là evidence lịch sử đã mở. Được audit nhưng không được dùng lại làm heldout mới sau tuning. Dữ liệu mới phải tách theo document/cluster, review trước đo, có manifest/version và protocol lock riêng.
- User approval cũ áp dụng HG1/HG2 cũ; không tự gán human-approved cho corpus mới. Chuẩn bị draft để người dùng review sau khi có đủ packet.

## Chuẩn nghiệm thu bổ sung

- Phân biệt technical PASS, measurement readiness và product gate PASS trong report và plan status; completed không có nghĩa enablement.
- Precision và recall phải có denominator riêng; mẫu positive và prediction đủ mỗi label, không lấy tổng655 thay MIN_N mỗi label.
- Candidate coverage engineering target >=95% mỗi label trên dev; target không bảo đảm end-to-end recall pass. Mọi accepted prediction và reject có pair_id và reason, không suy từ counters.
- Dataset review độc lập khỏi model suggestion khi khả thi; disagreements adjudicated, nhãn mơ hồ được reject với receipt. Không bịa nhãn để đạt quota.
- Không tạo/chạy test implementation trong planning. Chỉ ghi Tests Before/After và lệnh cần chạy lúc cook; probes đã chạy không sửa code.
