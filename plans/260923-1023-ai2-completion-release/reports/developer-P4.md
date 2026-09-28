# Báo cáo developer — P4 Release Verification

## Implementation

- Bổ sung release evidence deterministic, candidate/golden separation, production replay có `snapshot_id`, scorer schema/citation và UTF-8 checks.
- Candidate corpus được audit thành `95 UNVERIFIED`; golden manifest rỗng nên denominator accuracy là `0` và accuracy claim là `UNVERIFIED`.
- Thêm mutation mapping explicit và fixture/scorer executor; không tính scorer-fixture observation là production mutation kill.
- Bổ sung large-dossier workload với numeric quota và p95/p99/RSS/token/call; fixture hiện dưới 50 pages nên trạng thái là `UNVERIFIED` smoke-only.
- Live provider gate giữ `NOT_RUN` khi chưa có credential/run được phê duyệt.

## TDD evidence

- Intentional RED: collection ban đầu gặp `import file mismatch`; sau đó mutation no-op test đỏ vì implementation cũ trả `PASS`.
- GREEN targeted P4 sau sửa: `42 passed, 1 warning`.
- Full offline gate: `222 passed, 6 deselected, 1 warning`.
- Exact release verifier exit `1` vì `release_verdict=BLOCKED`, đúng kỳ vọng khi production mutation adapter chưa được nối.
- Contract registry: `Contract registry OK (5 schemas)`.
- `git diff --check`: PASS.
- UTF-8/U+FFFD scan: PASS.

## Main review

- Xác nhận mutation matrix không còn tự tạo mismatch để tạo kill giả; no-op bị `BLOCKED`.
- Xác nhận scorer-fixture observations chỉ là non-release evidence; mutation release status là `BLOCKED`.
- Xác nhận production replay chạy trên fixture có `snapshot_id` và giữ `cross_document_findings=[]`.
- Xác nhận không claim accuracy nghiệp vụ: golden `0`, candidate `95 UNVERIFIED`, large dossier `UNVERIFIED`, live `NOT_RUN`.

## Replay hai input OCR-lab người dùng cung cấp

- Lệnh exact đã chạy với `--strict` và output được lưu tại
  `ai-service/artifacts/ai2-two-input-replay-20260923.json`.
- `doc-001` và `doc-002` đều xử lý được ở trạng thái `SUCCEEDED` nhưng giữ
  `NEEDS_REVIEW` do evidence/structure issues của input; không hạ review state
  thành pass.
- `cross_document_findings=[]`, `relation_policy=INDEPENDENT`, `batch_issues=[]`.
- `doc-002` giữ được hai part trong cùng snapshot (`BODY`, `ANNEX`), annex
  `Phụ lục 01`, 34 facts và 20 events; các continuity conflict của upstream
  được ghi thành issue, không bị nuốt hoặc tự resolve.
- Output round-trip UTF-8 không có U+FFFD.

## Release disposition

- Implementation/evaluator tests xanh nhưng release verdict hiện là `BLOCKED`, chưa được xem là release-ready.
- Residual cần backlog/gate riêng: nối production mutation adapter thật và bổ sung human-reviewed golden set; mở rộng workload tối thiểu 50 pages trước khi claim performance.

## Files

- Thay đổi nằm trong evaluator/replay/corpus/mutation tooling, tests, docs/workflow và artifact P4; không sửa `plan.md`/phase file và không commit.
