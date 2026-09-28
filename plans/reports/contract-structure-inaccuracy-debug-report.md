# Cây cấu trúc hồ sơ không chính xác — Debug Report

## Executive Summary

- **Issue:** Tab “Đối chiếu Điều khoản” hiển thị cây cấu trúc không đúng hồ sơ đang mở.
- **Impact:** Mọi dossier có thể hiển thị cùng một cây hợp đồng mẫu; người dùng có thể đọc nhầm điều khoản/phụ lục và citation.
- **Root cause:** `DossierReviewPage` render `ContractMindmap` tĩnh; component không nhận `dossierId`, `ClauseNode` hoặc snapshot structure và chứa cứng dữ liệu mẫu.
- **Status:** Root cause identified; chưa sửa.
- **Next step:** `/hs:fix frontend/tests/contract-mindmap-repro.test.tsx`.

## Evidence

1. `frontend/src/pages/DossierReviewPage.tsx:10` import `ContractMindmap` và `frontend/src/pages/DossierReviewPage.tsx:574` render `<ContractMindmap />` không truyền props.
2. `frontend/src/components/ContractMindmap.tsx:82` khai báo component không có tham số dữ liệu.
3. `frontend/src/components/ContractMindmap.tsx:128` hiển thị cố định `9 Điều khoản • 4 Phụ lục`.
4. `frontend/src/components/ContractMindmap.tsx:320-472` chứa cố định các nhãn mẫu như `Điều 1: Định nghĩa & Giải thích thuật ngữ`, `Điều 5: Giá trị HĐ & Dự phòng (28,45 tỷ)` và `Điều 9: Luật áp dụng & VIAC`.
5. Luồng structure thật tồn tại riêng trong `DossierStructurePage`: tải `/api/v1/dossiers/{id}`, lấy OCR lines, gọi `buildStructureTree`, rồi render `StructureMindmap`/`StructureOutline`. Luồng này không được dùng bởi tab clauses nói trên.

## Live dossier comparison

Authenticated GET probes against the local stack returned:

| Dossier | OCR pages/lines | OCR marker lines | Backend clauses | Observation |
|---|---:|---:|---:|---|
| `dos_01M39XXAHPTZGW1X5RCTEWT52F` | 5 / 58 | 0 | 1 (`UNMARKED__unnumbered_1`) | No usable numbered headings reached the structure fallback. |
| `dos_01M39XPA10F5B70J7VAHQXH0PG` | 11 / 514 | 18 | 22 | Structure input is present, but repeated `ARTICLE_1/2/3/4` labels indicate a document/annex hierarchy that needs verification. |
| `dos_01M38T3PD2Z45CJXGS6FQGKSWX` | 12 / 257 | 50 | 133 | This is the dossier the user reports as comparatively correct; it has dense numbered markers and a much richer clause tree. |

This distinguishes two issues: the Review-page mindmap is unconditionally static for every dossier, while the true Structure page also has dossier-specific data-quality cases where OCR contains no recognizable markers or the backend clause hierarchy is sparse/repeated.

## Hypotheses

1. **OCR/AI1 dựng sai cây:** Không phù hợp với lỗi ở tab review, vì tab này không đọc structure API mà render component tĩnh.
2. **Backend trả sai structure:** Không phải nguyên nhân trực tiếp của triệu chứng; review tab không truyền dữ liệu backend vào mindmap.
3. **UI đang hiển thị cây mẫu cố định:** Được xác nhận bởi source inspection và failing repro test.
4. **Một số dossier thiếu marker cấu trúc từ OCR:** Được quan sát trực tiếp ở `dos_01M39XX...` (58 OCR lines, 0 marker lines, 1 unmarked backend clause). Đây là nguyên nhân dữ liệu riêng, chưa gộp với lỗi mindmap tĩnh.

## Failing Repro Test

`frontend/tests/contract-mindmap-repro.test.tsx`

Run:

```text
npm test -- --run tests/contract-mindmap-repro.test.tsx
```

Expected current result: FAIL because the component contains the hard-coded sample structure.

## Scope Boundary

This report confirms the review-tab mindmap bug. It does not yet prove that the dynamic OCR-derived tree in `DossierStructurePage` is semantically correct for every document type; that requires a separate dossier fixture comparison after the static component is removed from the path.
