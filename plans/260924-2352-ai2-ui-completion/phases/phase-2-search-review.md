---
phase: 2
title: "Live Search & Evidence Review"
status: pending
plan: 260924-2352-ai2-ui-completion
created: 2026-09-24
---

# Phase 2 — Live Search & Evidence Review

## Mục tiêu

Thay dữ liệu static trong màn hình review trung tâm bằng query thật theo dossier đang chọn, đồng thời nối lại các trạng thái upload/OCR/retry đã có để người dùng đi trọn workflow. Người dùng nhập câu hỏi, nhận answer/hits đúng hồ sơ, thấy loading/error/empty/insufficient-evidence, click citation để mở đúng nguồn và có thể copy/export kết quả hiện tại.

## Files

- **Modify:** `frontend/src/pages/DossierReviewPage.tsx`, `frontend/src/components/DossierSearchResults.tsx`, `frontend/src/api/structure.ts` hoặc API module mới.
- **Verify/modify:** `frontend/src/pages/CreateDossierPage.tsx`, `frontend/src/pages/AnalysisProgressPage.tsx`, `frontend/src/api/dossiers.ts`; giữ `restartDossierOcr` và map lỗi env/401/403/404 thật.
- **Remove from live path:** imports `sampleSearchQuery`, `searchAnswerText`, `searchCitations` từ `frontend/src/data/dossierSearch`.
- **Reuse/modify:** source viewer/navigation component hiện có để nhận `source_file_id`, `page_no`, `line_id`, bbox.
- **Add:** query state/data hook, query history state và UI tests/fixtures.

## TDD

- **RED:** render test với response answered; test query được gửi kèm dossier id; test click citation navigates to source; test 401/404/409/5xx, empty hits và `INSUFFICIENT_EVIDENCE`.
- **Implement:** API call + abort/debounce, normalized response, answer/hit rendering từ props, source navigation, retry CTA và remove mock data from production path.
- **GREEN:** component behavior tests; manual smoke trên `dos_01M38T3PD2Z45CJXGS6FQGKSWX` cho party, value, payment và penalty.
- **Regression:** frontend build/lint; backend search route tests; AI2 reasoning suite.

## Success

- [ ] Hỏi “Thông tin bên A”, “Giá trị tổng của hợp đồng”, “Thời hạn thanh toán” trả dữ liệu đúng dossier và citation mở được nguồn.
- [ ] Hỏi câu chưa có evidence không hiển thị paragraph bịa; hiển thị lý do và hướng review.
- [ ] Không còn answer/citation hardcoded trên live review route.
- [ ] Upload → progress → OCR error → retry → ready có một dossier id/run thật; thiếu `MISTRAL_API_KEY` hiện thành lỗi cấu hình actionable và không làm nút retry vô hiệu một cách mơ hồ.

## Risks

Dossier id có thể chỉ nằm trong route/state cũ. Mitigation: chuẩn hóa route param/context trước khi gọi API; nếu không có dossier id thì disable submit và yêu cầu chọn hồ sơ.
