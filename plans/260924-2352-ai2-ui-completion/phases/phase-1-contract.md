---
phase: 1
title: "Contract & Evidence Model"
status: pending
plan: 260924-2352-ai2-ui-completion
created: 2026-09-24
---

# Phase 1 — Contract & Evidence Model

## Mục tiêu

Đóng băng một view-model dùng chung cho search answer, hit, citation, review state, pipeline status và error/evidence gap. Map rõ AI2 envelope → backend response → frontend DTO; không để từng component tự đoán shape.

## Files

- **Modify:** `frontend/src/api/structure.ts`, tạo `frontend/src/api/ai2.ts` hoặc module tương đương cho DTO/normalizer; map auth token và `X-Tenant-Id` theo client hiện có.
- **Modify:** backend DTO/router chỉ khi contract hiện tại thiếu source metadata hoặc error envelope.
- **Add:** fixture schema/response dưới `frontend` hoặc `backend/tests/fixtures` cho answered, needs-review, insufficient-evidence, stale-version và citation không locatable.
- **Add:** frontend test strategy: Vitest + Testing Library (hoặc runner tương đương được kiểm chứng), scripts/config và một boundary test; chọn runtime validator (ưu tiên schema package đã dùng trong repo, nếu chưa có thì thêm Zod hoặc validator tương đương có lý do).
- **Read-only anchors:** `docs/DOC-05b-frontend-backend-api-contract.md`, `docs/contracts/ai2.service-envelope.v1.schema.json`, `docs/contracts/ai2.be.processing.result.v1.schema.json`.

## TDD

- **RED:** test parser từ response thật cho 4 review states; test giữ `source_file_id`, `line_id`, page và bbox; test reject response thiếu dossier scope hoặc citation node.
- **Implement:** types/discriminated unions, runtime validation ở fetch boundary, normalized error/evidence helpers và query-key convention.
- **GREEN:** unit tests cho normalization; backend/AI2 contract tests không đổi behavior cũ.
- **Test command:** `npm run test` (sau khi script được thêm) phải chạy được không cần backend; boundary fixture phải fail rõ khi response sai shape.
- **Regression:** `backend`: pytest unit/contract; `ai-service`: pytest offline; `frontend`: `npm run build`, `npm run lint`.

## Success

- [ ] Mọi live UI API dùng một DTO có typed answer/hits/citations/review state.
- [ ] Citation có thể phân biệt locatable, partial và unresolved; unresolved không được render như link hợp lệ.
- [ ] Không có public API nào dùng `any` hoặc cast mù cho response ngoài boundary.

## Risks

Schema docs và payload runtime có thể lệch. Mitigation: fixture lấy từ response đang chạy, test contract trước khi nối UI, ghi rõ field optional thay vì silently default.
