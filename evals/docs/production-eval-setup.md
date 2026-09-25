# AI2 evaluation guide

Ngày cập nhật: 2026-09-23

Bộ đánh giá này chỉ kiểm tra AI2 sau khi đã nhận handoff JSON từ AI1. Upload,
PDF parsing và OCR không thuộc phạm vi của bộ này.

## Phạm vi

Có hai domain độc lập:

- `ai2_contract_package`: trích xuất structure/fact/field, relation và trạng thái review của contract/annex.
- `ai2_grounded_query`: trả lời câu hỏi tự do có citation, so sánh body-annex, relation/cascade, fail-closed và scope/policy safety.

Ground truth nằm ở:

- `evals/eval_types/ai2_contract_package/tests/production_fixtures/ground_truth.json`
- `evals/eval_types/ai2_grounded_query/tests/production_fixtures/ground_truth.json`

Các sample hiện tại là invariant do con người viết. Chúng chưa đủ để tuyên bố
độ chính xác nghiệp vụ cuối cùng; cần bổ sung payload AI1 thật có `snapshot_id`
để parity với production được thực thi thay vì skip.

## Chạy local

```powershell
$env:PYTHONIOENCODING = "utf-8"
& .\ai-service\.venv\Scripts\python.exe -m pytest -q evals\eval_types\ai2_contract_package\tests
& .\ai-service\.venv\Scripts\python.exe -m pytest -q evals\eval_types\ai2_grounded_query\tests
& .\ai-service\.venv\Scripts\python.exe evals\scripts\run_production_evals.py `
  --sample-dir evals\data\samples\ai2_contract_package `
  --ground-truth evals\eval_types\ai2_contract_package\tests\production_fixtures\ground_truth.json
& .\ai-service\.venv\Scripts\python.exe evals\scripts\run_grounded_query_evals.py `
  --sample-dir evals\data\samples\ai2_grounded_query `
  --ground-truth evals\eval_types\ai2_grounded_query\tests\production_fixtures\ground_truth.json
```

## Quy tắc chấm

Mỗi field được so sánh thành `MATCH`, `MISMATCH`, `MISS`, `EXTRA` hoặc `SKIP`.
Scorer dùng trọng số trong strategy card đã hash; P0 failure luôn block overall
pass dù maturity score đạt threshold.

Các P0 quan trọng của query gồm citation cho claim, trạng thái
`INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW`, so sánh phải giữ hai phía và không chọn
legal winner, block scope/egress/lifecycle, relation edge hợp lệ và giữ nguyên
dấu tiếng Việt.

## CI

Workflow [production-evals.yml](../ci/production-evals.yml) chạy service tests,
eval contract tests và hai production eval domain. LLM judge nếu được bật chỉ
mang tính advisory, không thay thế deterministic scorer.

## Mở rộng ground truth

Khi thêm case:

1. Thêm JSON handoff AI1 vào thư mục sample tương ứng.
2. Ghi expected output và lý do nghiệp vụ trong `ground_truth.json`.
3. Nếu case có `snapshot_id`, parity test sẽ đối chiếu mirror với entry production.
4. Chạy cả contract tests và production evals trước khi merge.

Không sửa expected chỉ để làm xanh test. Nếu quy tắc nghiệp vụ thay đổi, cập
nhật strategy card, hash và ghi lại quyết định phê duyệt.

## Giới hạn post-audit hiện tại

Mutation generator của harness chưa chạy được với strategy card hiện tại vì
card khai báo `p0_rules[].target_axis` theo tên dimension, còn generator yêu cầu
đó là tên field trong `case_matrix[].expect`. Đây là lỗi cấu hình coverage của
eval gate, không phải bằng chứng AI2 đúng. Cần một lần cập nhật strategy card
được phê duyệt để map từng P0 rule vào field cụ thể trước khi tuyên bố mutation
coverage đầy đủ.
