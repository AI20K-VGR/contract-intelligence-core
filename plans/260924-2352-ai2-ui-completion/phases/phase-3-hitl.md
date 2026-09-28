---
phase: 3
title: "HITL Review & Approval"
status: pending
plan: 260924-2352-ai2-ui-completion
created: 2026-09-24
---

# Phase 3 — HITL Review & Approval

## Mục tiêu

Đưa queue/detail/revision/action/lock/approve của backend vào UI để reviewer xác nhận, sửa citation/value, từ chối hoặc yêu cầu thêm evidence. Trạng thái phải phản ánh optimistic concurrency và RBAC.

## Files

- **Modify:** review API client/hooks và các page/component review hiện có.
- **Reuse/modify:** `backend/src/contract_intelligence/review/interfaces/api/routers/review_full_router.py`, `approval_router.py` chỉ khi DTO/error mapping cần bổ sung.
- **Add:** review action DTOs, revision timeline, conflict dialog, lock/approval controls và tests.

## TDD

- **RED:** test action payload `base_version`; test `correct` bắt buộc corrected value/bbox; test 409 giữ dữ liệu local và yêu cầu reload; test unauthorized action; test revision hiển thị append-only.
- **Implement:** queue → detail → action mutation → invalidate/refetch; lock/approve UI; citation correction với audit trail.
- **GREEN:** backend unit/integration tests và frontend behavior tests cho toàn bộ state transition.
- **Regression:** RBAC/optimistic locking tests, backend pytest, frontend build/lint, Docker API smoke.

## Success

- [ ] Reviewer xem được item ưu tiên, evidence và revision history.
- [ ] Confirm/correct/reject/needs-more-evidence cập nhật đúng trạng thái và không mất citation.
- [ ] Approve chỉ khả dụng khi điều kiện backend cho phép; conflict không bị ghi đè im lặng.

## Risks

UI có thể coi action thành công trước khi backend commit. Mitigation: optimistic UI chỉ cho pending state; trạng thái canonical lấy từ response/refetch, 409 là first-class error.
