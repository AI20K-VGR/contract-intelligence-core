# Phase 2 — Show Unconfirmed: reviewer thấy chú thích quan hệ CHƯA XÁC NHẬN

## Overview
Trên màn `DossierAnalysisPanel` (dùng bởi `AnalysisCenterPage`), context finding
có `metadata.relation == "UNCONFIRMED"` phải hiện chú thích quan hệ chưa xác
nhận + lý do, không chỉ đếm số. TDD (test DTO thuần trước). Đúng DEC-1: không
xoá cặp, không bịa câu dẫn chiếu.

## Requirements
Functional:
- Với mỗi context finding, đọc `metadata.relation`. Khi `== "UNCONFIRMED"`,
  hiển thị nhãn "Quan hệ: CHƯA XÁC NHẬN" (hoặc tương đương) kèm `reason`.
- Không làm hỏng render hiện có khi `metadata`/`relation` vắng (fallback êm).

Non-functional:
- Đổi tối thiểu; KHÔNG redesign UI, KHÔNG mở rộng `DossierSearchDTO`.
- Hàm map là thuần (không React) để test được ở vitest môi trường node.

## Chọn màn (một)
`DossierAnalysisPanel` (render bởi
`frontend/src/pages/AnalysisCenterPage.tsx:171`). Lý do: nó lấy context findings
qua `getDossierAi2Analysis` → endpoint `/ai2-analysis`
(`frontend/src/api/analysis.ts:229-260`, trường `context_findings` giữ raw dict,
kể cả `metadata`). Backend DTO của endpoint này giữ nguyên
`context_findings: list[dict]` (`.../ai2_analysis_dtos.py:29`;
`.../extraction_service.py:327`), nên `metadata` đã đến frontend.
KHÔNG chọn `DossierReviewPage`: nó đọc `searchResult.contextFindings`
(`frontend/src/pages/DossierReviewPage.tsx:208`) nhưng `DossierSearchDTO`
(`backend/.../contract_router.py:678-687`) không mang `context_findings` →
mảng luôn rỗng ở màn đó.

## Data flow đã xác minh
- Nguồn note: `ai-service/app/pipeline/contract_context.py:53-59` tạo
  `{"relation": "UNCONFIRMED", "item_key": ..., "pair_fact_ids": [...]}` và gắn
  vào `metadata=pair_note` (`:170`).
- Serialize: `ContextFinding` có field `finding_id, subject_key, reason,
  review_state, metadata` (`ai-service/app/contracts/models.py:284-301`).
- Frontend hiện tại: `contextPanelModel` trong
  `frontend/src/components/DossierAnalysisPanel.tsx:41-63` map
  `reasonCode/subject/reviewState` nhưng KHÔNG đọc `metadata.relation`;
  `ContextFindingsPanel` render `reasonCode/subject/reviewState`
  (`frontend/src/components/ContextFindingsPanel.tsx:84-99`).

## Related Code Files
Create:
- `frontend/src/api/contextFindings.ts` — hàm thuần
  `toContextFindingItems(contextFindings: unknown[]): ContextFindingPanelItem[]`
  đọc `finding_id/id`, `reason_code/reason`, `subject_key/subject`,
  `review_state`, và `metadata.relation` → thêm field `relation?: string`.
- `frontend/src/api/contextFindings.test.ts` — test vitest.

Modify:
- `frontend/src/components/ContextFindingsPanel.tsx` — thêm `relation?: string`
  vào `ContextFindingPanelItem` (`:1-6`); trong `<li>` (`:84-99`) render nhãn
  "CHƯA XÁC NHẬN" khi `finding.relation === 'UNCONFIRMED'`.
- `frontend/src/components/DossierAnalysisPanel.tsx` — trong `contextPanelModel`
  (`:41-63`) thay khối map inline bằng gọi `toContextFindingItems(
  analysis.contextFindings)` để dùng chung logic đã test.

## Implementation Steps
1. **RED** — `contextFindings.test.ts`:
   - Input một context finding có `metadata: { relation: "UNCONFIRMED" }` và
     `reason: "..."` → khẳng định item trả về có `relation === "UNCONFIRMED"`.
   - Input không có `metadata` → `relation` undefined, không ném.
2. `npm test` → đỏ (module chưa tồn tại).
3. **GREEN** — viết `toContextFindingItems` (thuần, không import React); export
   type `ContextFindingPanelItem` hoặc tái dùng type từ `ContextFindingsPanel`.
   (Nếu cần tránh phụ thuộc vòng, khai báo type item tại `contextFindings.ts` và
   để `ContextFindingsPanel` import lại.)
4. Sửa `ContextFindingsPanel.tsx`: thêm `relation?` + render nhãn có điều kiện.
5. Sửa `DossierAnalysisPanel.tsx`: gọi hàm chung.
6. `npm test` xanh; `npm run lint` + `npm run build` sạch.

## Success Criteria
- [ ] Test DTO chứng minh `relation === "UNCONFIRMED"` suy ra từ `metadata`.
- [ ] Panel render nhãn "CHƯA XÁC NHẬN" cho finding UNCONFIRMED (đọc code path).
- [ ] Không đổi `DossierSearchDTO`; không đổi màn `DossierReviewPage`.
- [ ] `npm test` + `npm run build` + `npm run lint` sạch.

## Risk Assessment
| Rủi ro | K×I | Mitigation |
|---|---|---|
| `metadata` không tới do backend field khác tên | L×M | Đã xác minh field `metadata` giữ raw ở DTO (`ai2_analysis_dtos.py:29`) |
| Chưa có hạ tầng test frontend | M×L | Hàm map thuần, vitest node (zero-config), không cần jsdom |
| Render vỡ khi thiếu `relation` | L×M | Fallback: chỉ render nhãn khi `relation` có mặt |
| Trùng type giữa 2 file gây vòng import | L×L | Đặt type ở `contextFindings.ts`, panel import lại |

## Post
- `verification-P2.json`
