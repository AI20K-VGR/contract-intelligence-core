---
phase: 5
title: "Full-stack Release Gate"
status: pending
plan: 260924-2352-ai2-ui-completion
created: 2026-09-24
---

# Phase 5 — Full-stack Release Gate

## Mục tiêu

Đóng workflow vận hành: action/revision history canonical, export có citation, health/env diagnostics và kiểm thử từ upload đến review trên Docker stack thật. Query-history persistence chỉ được claim khi có backend contract; nếu chưa có thì report là chưa hỗ trợ.

## Files

- **Modify:** history/export UI và API client; health/status display; Docker/env documentation nếu thiếu mapping; reuse `frontend/src/components/DossierAuditLog.tsx` và review revisions làm nguồn canonical.
- **Add:** smoke/e2e script, release checklist/artifact, export fixtures và secret-safe diagnostics.
- **Read-only/reference:** `docs/ai2/AI2-12-review-and-release-gate.md`, Docker compose files, `.env.example`/env contract.

## TDD / verification

- **RED:** smoke fail nếu upload không tạo run, OCR không complete, AI2 không nhận snapshot, citation không resolve, review action không persist hoặc export thiếu source metadata.
- **Implement:** history/export/diagnostics và retry/refresh behavior.
- **GREEN:** frontend `npm run build` + `npm run lint`/format check; backend pytest unit/integration phù hợp; AI2 offline suite với `-m "not live"`; exact replay và live command ghi `NOT_RUN` nếu thiếu credential, không giả thành PASS.
- **Full-stack:** Docker health check cho upload, backend, worker, AI1, AI2, frontend; manual smoke một dossier thật và một case thiếu evidence.

## Success

- [ ] Có artifact ghi rõ pass/fail/not-run cho từng gate.
- [ ] Export/history chứa query, dossier, answer, review state và citation; không lộ API key/token.
- [ ] Luồng upload → OCR → AI1 → AI2 → hỏi → click nguồn → review → approve chạy được hoặc dừng ở safe state có lỗi actionable.
- [ ] `NEEDS_REVIEW` vẫn được giữ nguyên nếu evidence/replay chưa đạt.

## Risks

Môi trường local có thể thiếu Mistral key hoặc dữ liệu OCR khác schema. Mitigation: diagnostics chỉ kiểm tra presence/mapping, replay offline là gate bắt buộc, live provider là opt-in và report đúng `NOT_RUN`.
