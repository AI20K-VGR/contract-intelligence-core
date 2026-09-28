## Prediction Report: AI2 contract-package và grounded-query release

Phạm vi: AI2 sau handoff JSON từ AI1; không bao gồm upload/OCR/PDF parsing.
Đường chạy: `inline-Task fallback`, 5 persona độc lập, 5 stages, sau đó hợp nhất
và kiểm chứng lại bằng code/test hiện có. Không persona nào sửa production.

## Verdict: STOP

Không nên coi AI2/operator-facing flow là production-ready. Bộ eval hiện tại
đã chứng minh deterministic mirror/scorer chạy được, nhưng chưa chứng minh
production grounding, citation usability, scope isolation và parity với entry
thật. Maturity 100% hiện là điểm trên synthetic invariant set, không phải độ
chính xác nghiệp vụ.

### Consensus points

- Synthetic ground truth và mirror hiện cho biết eval machinery nhất quán, nhưng
  chưa đại diện cho payload AI1 thật.
- Parity đang skip vì chưa có payload có `snapshot_id`; skip phải được đọc là
  chưa kiểm chứng, không phải PASS.
- Citation, relation body-annex, missing evidence và safe states là các control
  trung tâm; mọi câu trả lời substantive phải fail-closed nếu citation không
  dùng được.
- Strategy card hiện chưa chạy được mutation coverage: `target_axis` dùng tên
  dimension trong khi mutation generator yêu cầu tên field trong `expect`.
- Cần tách rõ `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`,
  `NOT_COMPARABLE` với `PASS` của processing/publish.

### Conflicts & resolutions

| Chủ đề | Architect | Security | Performance | UX | Devil's Advocate | Resolution |
|---|---|---|---|---|---|---|
| Có thể release không? | Caution, cần parity thật | Blocked vì fail-open paths | Chưa đủ budget evidence | Stop cho operator acceptance | Không tin maturity 100% | Security/UX thắng vì có failure mode trực tiếp; STOP |
| Mirror/eval xanh | Giảm drift nhưng đang copy thủ công | Có thể false assurance | Runtime chưa đo | Không đo navigation/recovery | Synthetic set có thể tự xác nhận | Giữ eval, nhưng không dùng làm release evidence duy nhất |
| State `ANSWERED` | Cần canonical contract | Phải gắn citation/grounding | Không có quan ngại chính | Có false reassurance đã quan sát | State có thể che lỗi | `ANSWERED` chỉ hợp lệ khi grounded và claim-level citations usable |
| Tối ưu lớn dossier/cache | Cần mở rộng sau | Không được đánh đổi scope/privacy | Thiếu bound p95/RSS/token | Cần bounded answer dễ hiểu | Chưa có benchmark | Định nghĩa quota và benchmark trước scale-out |

### Risk summary

| Risk | Severity | Mitigation |
|---|---|---|
| Free-form answer có thể không bắt buộc citation cho mọi claim | Critical | Ép citation theo claim; citation invalid/missing chuyển `NEEDS_REVIEW` hoặc `INSUFFICIENT_EVIDENCE` |
| Source text có prompt injection nhưng đi vào LLM prompt chưa có trust-boundary rõ | High | Taint/delimiter source content, instruction isolation, adversarial regression cases |
| `ANSWERED` có thể đi cùng `grounded=false` hoặc citation review lỗi | Critical | Canonical response contract; P0 invariant `ANSWERED => grounded=true && all citations usable` |
| Dossier mismatch vẫn tiếp tục adapt/process | High | Reject batch trước processing; không publish result gắn với dossier khác |
| Raw evidence/PII và egress flag thiếu có thể fail-open | High | Privacy classification, retention/redaction, egress deny-by-default |
| `compile/exec` sandbox thiếu CPU/memory/process isolation | High | Tắt capability hoặc chuyển sang process/container sandbox có timeout và quota |
| Production parity skip làm CI xanh giả | High | CI lane phải import `ai-service/app` đúng cách; production payload golden set phải chạy parity, skip là fail ở release lane |
| Mutation coverage không sinh được | High | Đổi `target_axis` thành field key, align case names với ground truth, chạy lại generate/run |
| Dossier lớn chưa có candidate/chunk/edge/citation/RSS bounds | Major | Quota, p95/p99 latency, peak RSS, token/call budget và timeout regression |
| Hai nguồn card/hash theo domain chưa có registry invariant chung | Medium | Một card registry có domain id, hash và loader contract duy nhất |
| CI dependency range mở, thiếu hash verification | Medium | Lockfile/hash-pinned install hoặc dependency review gate |

### Evidence checked

- Eval query: 20/20 sample PASS, maturity 100%, P0 PASS.
- Eval contract tests: `16 passed, 24 skipped`.
- Eval query tests: `18 passed, 20 skipped`.
- `ci_wiring_check.py --strict`: `WIRED`.
- Mutation generation hiện fail với các P0 rule vì `target_axis` không xuất
  hiện trong `case_matrix[].expect`; limitation này đã ghi trong
  `evals/docs/production-eval-setup.md`.
- Production code evidence reviewed by personas includes:
  `ai-service/app/reasoning/query.py`, `ai-service/app/reasoning/l3_ground.py`,
  `ai-service/app/reasoning/l2_plan.py`, `ai-service/app/pipeline/ai2_batch.py`,
  `ai-service/app/tools/persist.py`, `ai-service/app/sandbox/__init__.py`.

### Recommendations

1. Chốt canonical answer/evidence state contract trước mọi UI/operator release;
   không để `ANSWERED` đồng nghĩa với “đã được xác minh”.
2. Đóng các security P0: citation bắt buộc, source-text isolation, batch
   dossier fail-closed, PII/egress deny-by-default và process isolation cho
   `run_code`.
3. Tạo golden set AI1 thật có `snapshot_id`, gồm body/annex, conflict, missing
   annex, multi-party, số tiền/ngày/đơn vị và Unicode; expected do reviewer
   viết độc lập với mirror.
4. Sửa mutation card mapping và bắt buộc mutation generate/run PASS trước khi
   dùng eval làm release gate.
5. Thêm benchmark dossier lớn với giới hạn p95/p99, RSS, token/call, timeout,
   retry và cache invalidation; CI phải fail nếu vượt budget.
6. Tạo task-based UX eval: mở đúng citation, hiểu state, phục hồi missing
   source, xử lý conflict và đo false-reassurance rate.

### Arbiter checklist

- Mỗi persona đã ghi artifact: architect, security, performance, UX,
  devils_advocate.
- Không có persona nào sửa production; chỉ ghi report.
- Các báo cáo có điểm đồng thuận; các khác biệt đã được hợp nhất theo mức độ
  tác động.
- Các test/eval chính đã chạy; parity skip và mutation failure được ghi là
  giới hạn, không chuyển thành PASS.
- Không có destructive action nào được thực hiện.
- Unresolved trước khi re-review: production golden set, canonical state/citation
  contract, security hardening và mutation coverage.
