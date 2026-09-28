# Red-team report — full-chain plan amendment review

Ngày: 2026-09-23  
Phạm vi: phần bổ sung từ `hs:eval-bootstrap` và `hs:predict`, đối chiếu với
`understand → docs → discover → research → scenario`.

## Verdict

**REVISE đã xử lý trong plan hiện tại.** Baseline `10/10`, `20/20` và maturity
`100%` chỉ là mirror/synthetic evidence; chưa đủ điều kiện release readiness.

## Findings và disposition

| ID | Severity | Finding | Disposition trong plan |
|---|---|---|---|
| EVAL-RT-01 | BLOCKER | Production eval mặc định có thể chạy mirror; parity thiếu `snapshot_id` bị skip. | P4 bắt buộc tracked handoff fixture, exact production entry, `parity_executed > 0`; zero parity/skip là `BLOCKED`. |
| EVAL-RT-02 | MAJOR | Ground truth rỗng/expected rỗng và `SKIP` có thể tạo vacuous PASS. | P4 reject config thiếu expected assertion; `SKIP` không vào denominator/maturity. |
| EVAL-RT-03 | BLOCKER | `target_axis` dimension không map tới control field; mutation chưa chứng minh production control bị kill. | P4 khóa mapping `rule_id → production control → negative fixture → mutation`; thiếu kill evidence là `BLOCKED`. |
| EVID-RT-01 | BLOCKER | Marker `citations: required` chưa chứng minh claim-level citation usable. | P2 thêm `claims[]`, citation IDs và resolver kiểm tra node/page/revision/scope/quote hash. |
| PERF-RT-01 | MAJOR | Large dossier chưa có quota numeric, workload fixture và oracle khi vượt budget. | P3/P4 pin các `max_*` budget, fixture, p95/p99/RSS/token/call và partial/blocked oracle. |
| SCOPE-RT-01 | MAJOR | Graph và phase ownership lệch; hard process isolation nằm ngoài AI2 scope. | Eval files gom về P4; P3 chỉ deny/disable `run_code`, không xây process isolation; `files_to_create` dùng list hợp lệ. |
| DOC-RT-01 | MAJOR | Chưa có UTF-8/NFC/NFD/control-char round-trip gate cho raw/citation/report. | P2/P4 thêm deterministic UTF-8 fixture và raw-preservation/citation/report encoding assertions. |

## Evidence reviewed

- `evals/eval_types/ai2_contract_package/runner.py`
- `evals/eval_types/ai2_grounded_query/scorer.py`
- `evals/eval_config.json`
- `.github/workflows/production-evals.yml`
- `plans/reports/ai2-predict-20260923-predict-report.md`
- `plans/260923-1023-ai2-completion-release/plan.md`
- `plans/260923-1023-ai2-completion-release/phases/phase-2-evidence-pipeline.md`
- `plans/260923-1023-ai2-completion-release/phases/phase-3-processing-runtime.md`
- `plans/260923-1023-ai2-completion-release/phases/phase-4-release-verification.md`

## Residual human gates

Không claim business accuracy khi chưa có human-reviewed golden set; không claim
production readiness khi parity/mutation/performance evidence chưa đạt các gate trên.
