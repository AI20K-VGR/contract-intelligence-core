# Review PR #122 (feature/code-full -> develop) — 2026-10-18

Phạm vi: chỉ một lượt đọc diff ở mức low effort, tập trung vào `useAnalysisWatch.ts`, `runEvents.ts` (`ai2ProgressPercent`), `ProcessingTimeline.tsx`, `timelineOutcome.ts`. Chưa chạy lint/typecheck/test, chưa đọc 9 review đã có, nên một số điểm dưới đây có thể đã được trả lời rồi.

## Verdict
REQUEST_CHANGES (nhẹ): không có lỗi chặn về bảo mật. Có 1 lỗi đúng/sai (NaN %) và 1 conflict chắc chắn xảy ra với PR #125 / thay đổi local ở ProcessingTimeline.

## Findings (xếp theo mức độ)
1. **Medium** — `frontend/src/api/runEvents.ts` (`ai2ProgressPercent`, khoảng diff L52-57): `row.progress.done / row.progress.total` không chặn trường hợp `total === 0`. PR #125 trả `progress {step,done,total,unit}` trong GET /jobs; một bước có 0 cặp (ví dụ không có cặp điều khoản nào) sẽ cho `0/0 = NaN`, rồi `Math.min(99, Math.floor(NaN))` ra `NaN`, nên banner hiện "NaN%". Sửa: `row.progress && row.progress.total > 0 ? sum + Math.min(1, row.progress.done / row.progress.total) : sum`.
2. **Medium** — `frontend/src/components/ai2-graph/ProcessingTimeline.tsx:10-15` (stageLabels): PR thêm `extraction: 'Trích xuất dữ kiện'`, `semantic: 'Phân tích ngữ nghĩa'` trên base chưa có hai key này. Trong khi đó nhánh #125 (`feature/ai2-contract-graph`) đã có `extraction: 'Trích xuất dữ kiện từ điều khoản'` / `semantic: 'Phân tích ngữ nghĩa điều khoản'` ở cùng object. Merge PR thứ hai sẽ bị conflict text, và nếu resolve tay không cẩn thận thì sinh duplicate key (TS sẽ báo lỗi). Xem phần so sánh bên dưới.
3. **Low** — `frontend/src/hooks/useAnalysisWatch.ts` (`start()`, nhánh `onRejected: () => schedulePoll()` rồi sau `await watchRun` lại gọi `if (!(await checkDone())) schedulePoll()`): `schedulePoll` có `clearTimeout` nên không tạo hai timer song song. Tuy vậy `onLost` + `run.status_changed` có thể bắn nhiều `checkDone()` đồng thời. `finish()` có guard `finished` nên `onDone` chỉ được gọi một lần, chỉ tốn thêm vài request. Không cần làm gì.
4. **Low** — `useAnalysisWatch.ts`: trạng thái kết thúc chỉ dựa vào `latestJobStatus !== 'extracted'`. Nếu backend dùng thêm một trạng thái trung gian khác khi AI2 đang chạy, hook sẽ `finish` quá sớm. Cần xác nhận với contract #125 rằng job khi AI2 đang chạy chỉ có đúng trạng thái `extracted`.

Về failed state: `timelineOutcome` vẫn xét FAILED trước nhánh `job-succeeded-limited`, nên thứ tự ưu tiên lỗi giữ nguyên. Các stage id `extraction`/`semantic` map sang `null` trong `stageKinds`, nên bị ẩn khỏi tab đồ thị, đúng ý đồ. Stage id lạ vẫn hiện (fallback = graphKind), khớp với #125.

## So sánh ProcessingTimeline (thay đổi local chưa commit)
- Local (worktree #125) **chỉ đổi nhãn** của `contract_graph_operation` -> 'Nối điều khoản sửa đổi với điều khoản gốc' và `contract_graph_pairs` -> 'Phân tích quan hệ giữa các điều khoản'.
- PR #122 **giữ nhãn cũ** cho hai key này ('Tìm quan hệ điều khoản sửa đổi' / 'Tìm quan hệ giữa các điều khoản') và thêm nhãn ngắn cho extraction/semantic.
- Kết luận: **PR #122 chưa bao gồm thay đổi này, và hai bên conflict** (cùng object `stageLabels`, cùng vùng dòng). Đề xuất: commit thay đổi local vào #125. Khi rebase/merge PR thứ hai thì resolve thành một object duy nhất: lấy nhãn mới của local cho operation/pairs, và chọn **một** bộ nhãn cho extraction/semantic (nên lấy bản dài của #125 cho thống nhất). Không cần đưa vào #122, nếu không thì sẽ phải xử lý conflict hai lần.

## Chưa kiểm chứng
- Lint/typecheck/test frontend chưa chạy.
- Chưa đối chiếu với 9 review hiện có.

## Bản nháp comment PR (tiếng Việt)
> Cảm ơn PR. Mình có mấy điểm sau:
> 1. `runEvents.ts` `ai2ProgressPercent`: khi `progress.total === 0` (bước không có cặp nào, contract #125 có thể trả như vậy) thì `done/total = NaN` và banner sẽ hiện "NaN%". Nhờ thêm guard `total > 0` và kẹp tỉ lệ ở mức 1.
> 2. `ProcessingTimeline.tsx` `stageLabels`: PR #125 cũng thêm `extraction`/`semantic` (nhãn dài hơn) và đổi nhãn `contract_graph_operation`/`contract_graph_pairs`. PR nào merge sau cũng sẽ conflict. Đề xuất thống nhất: operation = "Nối điều khoản sửa đổi với điều khoản gốc", pairs = "Phân tích quan hệ giữa các điều khoản", extraction/semantic theo bản của #125.
> 3. `useAnalysisWatch`: điều kiện dừng là `latestJobStatus !== 'extracted'`. Nhờ xác nhận là trong lúc AI2 chạy không có trạng thái trung gian nào khác, để tránh dừng theo dõi quá sớm.
