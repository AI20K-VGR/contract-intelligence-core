# Báo cáo developer P7 — evaluation và regression gate

## Kết quả

P7 hoàn tất ở mức `PASS_WITH_LIMITATIONS`. Module `evals/workflow_gate.py` bổ sung scorer deterministic cho ground truth và các invariant workflow. Evaluation không tự nhận độ chính xác nghiệp vụ nếu nhãn chưa được phê duyệt.

## Contract đã triển khai

- `GroundTruthRecord` yêu cầu `case_id`, `source`, `approved` và `labels`;
- case scorer tách rõ `denominator`, `covered`, `passed`, `score`;
- unapproved/thiếu ground truth trả `business_accuracy = UNAVAILABLE`;
- workflow scorer có metric cho ordering, replay, idempotency, recovery và security;
- report ghi rõ claims và giới hạn dữ liệu;
- không dùng LLM judge để thay thế deterministic gate.

## Kiểm thử

- focused P7: `5 passed`;
- regression P0-P6: `55 passed, 1 warning`;
- `compileall`: PASS.

Warning duy nhất là pytest không ghi được `.pytest_cache` do quyền thư mục Windows.

## Giới hạn

Scorer hiện là deterministic contract checker, chưa phải load/soak runner production. Ground truth cần được human adjudication trước khi dùng làm publish gate; các case chưa được phê duyệt chỉ có thể dùng để kiểm tra schema/workflow, không dùng để tuyên bố business accuracy.
