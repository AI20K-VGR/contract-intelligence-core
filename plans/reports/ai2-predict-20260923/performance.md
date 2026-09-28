# Performance / Reliability review — AI2 proposal

## Trạng thái sơ bộ

Phạm vi review là proposal `plans/260923-1023-ai2-completion-release/` và các đường
chạy AI2 hiện có trong `ai-service/`, `evals/`, `docs/ai2/`. Đây là review chỉ đọc
đối với production; file này là artifact duy nhất được tạo trong lượt này.

Mức độ sơ bộ: **MAJOR — chưa đủ bằng chứng để coi proposal là release-ready ở
performance/reliability**.

### Findings đã ghi sớm

1. **MAJOR — budget được yêu cầu về mặt hành vi nhưng chưa có envelope đo được.**
   Proposal yêu cầu budget thời gian/call/token và retry bounded, nhưng chưa định
   nghĩa giá trị mặc định/tối đa, p95/p99, công thức chi phí hay tiêu chí fail CI.
   Evidence: `plans/260923-1023-ai2-completion-release/phases/phase-3-processing-runtime.md:12-18,55-62`;
   `plans/260923-1023-ai2-completion-release/phases/phase-4-release-verification.md:60-73`.

2. **MAJOR — xử lý dossier lớn và đồ thị citation/relation chưa có complexity hoặc
   memory bound.** Proposal yêu cầu bounded retrieval/Q&A và grounded relation graph,
   nhưng không khóa số candidate/chunk/edge/citation, peak RSS, hay chiến lược
   spill/streaming. Dossier lớn có thể làm tăng context, duplicate validation và
   serialization theo cấp số nhân ở các đường compare/cascade.
   Evidence: `plans/260923-1023-ai2-completion-release/phases/phase-2-evidence-pipeline.md:75-95`;
   `evals/cards/ai2_grounded_query.json:1` (case `large_dossier`, `relation_graph`).

3. **MAJOR — CI runtime chưa được chứng minh là bounded/deterministic ở mức pipeline.**
   Có deterministic gate và `--basetemp`, nhưng chưa có benchmark hoặc budget cho
   toàn bộ suite, test fixtures lớn, retry/timeout path, hay cache-hit/miss. Baseline
   hiện ghi `198 passed, 6 deselected`; đó là correctness count, không phải runtime
   evidence.
   Evidence: `plans/260923-1023-ai2-completion-release/plan.md:...` (baseline/validation log);
   `evals/scripts/run_production_evals.py:9-10,86`.

4. **MAJOR — cache mới được mô tả theo key-safety, chưa có policy hiệu năng và
   invalidation hoàn chỉnh.** Snapshot/model/dimension và ACL revision được nêu như
   điều kiện lọc; chưa có TTL, capacity, eviction, negative-cache, stampede control,
   hit-rate target hoặc đo chi phí revalidation citation/ACL.
   Evidence: `docs/ai2/AI2-04-edge-case-test-matrix.vi.md:67-74`;
   `plans/260923-1023-ai2-completion-release/phases/phase-3-processing-runtime.md:59-63`.

## Việc còn lại trước verdict cuối

- lấy line-level evidence trong runtime/reasoning/retrieval/store và các eval artifacts;
- chạy offline eval / targeted tests chỉ để đo và quan sát, không sửa production;
- phân loại từng finding theo `blocker | major | minor`, tách `proven` và `suspected`;
- ghi command, exit code, thời gian nếu đo được, cùng các giới hạn không đo được.

