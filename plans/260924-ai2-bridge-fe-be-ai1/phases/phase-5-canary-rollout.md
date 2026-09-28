# P5 — Canary, rollback, documentation và handoff

## Mục tiêu

Đưa Backend↔AI2 integration vào sử dụng có kiểm soát, giữ đường quay lại legacy và bàn giao rõ boundary cho phase FE sau này.

## Module/file dự kiến

- Backend `.env.example`/deployment config.
- Docker compose/deployment manifest nếu cần.
- Backend/AI2 contract docs và architecture docs.
- Rollout/rollback runbook, dashboards/alerts.

## Contract

- Default ban đầu là legacy/off nếu chưa có approval canary.
- Canonical mode bật theo environment hoặc dossier/tenant nếu hệ thống hỗ trợ; không bật global khi chưa có metric.
- Rollback chỉ đổi flag/routing và không xóa raw result/audit.
- FE không được đưa vào release gate của phase này.

## Acceptance criteria

- Có hướng dẫn chạy Backend với fake AI2 và integration environment.
- Có canary scope, success threshold, abort threshold và owner.
- Có rollback trong một cấu hình/release action.
- Docs phản ánh rõ legacy/canonical Backend path.
- Open question cho phase sau: FE mapping/read API, HITL UI và streaming.

## Test cases

- flag off/on trong environment mới.
- canary success.
- abort khi mapping/evidence/retry metric vượt ngưỡng.
- rollback giữa một run đang chạy và run mới.
- re-enable sau rollback không duplicate task.

## Verification artifact

Release checklist, rollout evidence, rollback rehearsal report, updated Backend/AI2 contract docs và final decision record.

## Risk / rollback

Risk là canary che khuất lỗi do dataset nhỏ. Rollback về legacy; giữ canonical raw evidence để điều tra, không publish index.

## Dependency

P4 pass và human approval cho canary.

