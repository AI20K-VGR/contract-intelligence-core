---
phase: 2
title: "Numbered Timeline"
status: pending
plan: 260927-1931-hitl-conflict-review-fixes
created: 2026-09-27
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 2 — Numbered Timeline

## Overview
Cho timeline trên trang đối soát tìm được lần thẩm định trích dẫn đã lưu ở search.
Search lưu theo `node.id` của cây `'numbered'` (`DossierStructurePage.tsx:202-205`),
còn `ClauseConflictPage` tra `linkedClauses` theo cây `structureMode`
(`ClauseConflictPage.tsx:558-568`) → id lệch. Fix: khóa tra cứu (review-target node)
lấy từ cây `'numbered'`; vùng tô PDF giữ nguyên cây `structureMode`/citation region.
Phụ thuộc: P1 (cần `review.latest` thật để trạng thái đúng).

## Files
- **Create** `frontend/src/structure/reviewTarget.ts` — hàm thuần `reviewTargetNode`.
- **Modify** `frontend/src/pages/ClauseConflictPage.tsx` — thêm `numberedTrees`, luồng
  numbered node vào pane, `linkedClausesOf` dùng review-target node.
- **Create** `frontend/tests/conflict-review-target.test.ts` — test khóa hành vi.

## Requirements
- `reviewTargetNode(numberedNodes: ClauseNode[], lines: OcrLine[], side: ReviewSpotSide):
  { node: ClauseNode; ordinal: number } | null` — dùng `clauseForCitation(numberedNodes,
  lines, side.pageNo, side.lineNo)` (fallback `findClauseByQuote(numberedNodes, quote,
  side.pageNo)` như `anchorConflicts.nodeForSide` — `conflictAnchors.ts:66-76`), ordinal =
  `clauseOrdinal(numberedNodes, node.id)` (`clauseReview.ts:130`). KHÔNG tính sha256/hash.
- `ComparePane` (`ClauseConflictPage.tsx:74-87`) thêm `reviewNode: ClauseNode | null` và
  `reviewOrdinal: number`.
- `linkPane` (`:215-263`) và `paneForSide` (`:328-377`) nhận thêm tham số
  `numberedNodes: ClauseNode[]`. Chỉ gọi `reviewTargetNode` khi `side` khác null
  (`linkPane` có nhánh `side` null ở `:223`). Không có side thì `reviewNode` là null
  và `reviewOrdinal` là 0. Không đổi `regions`/`quote`/`clause` (vẫn từ
  `structureMode` — vùng tô PDF không đổi).
- `locatePanes` (`:265-326`) nhận thêm `numberedByDocument: Record<string, ClauseNode[]>`,
  truyền vào `linkPane`/`paneForSide`.
- Thêm memo `numberedTrees` (song song `trees` — `:559-568`) build
  `buildStructureTree(lines, 'numbered')`; truyền vào `locatePanes` tại
  `linksById` (`:571-578`).
- `linkedClausesOf` (`:98-111`): `node = pane.reviewNode ?? pane.clause`;
  `ordinal = pane.reviewNode ? pane.reviewOrdinal : pane.ordinal`; giữ
  `label: sourceLabel(pane.label)`. Bỏ pane khi cả hai đều null.
- Khi hồ sơ đã là `structureMode === 'numbered'`: `numberedTrees` == `trees` → no-op,
  không đổi hành vi.

## TDD

### Tests Before (RED) — khóa gì
File mới `frontend/tests/conflict-review-target.test.ts`:
- Dựng `lines` với một dòng `(pageNo, lineNo)`; dựng `numberedNodes` mà dòng đó rơi vào
  node `id: 'clause-numbered'`, và một cây khác kiểu structureMode (freeform) mà cùng dòng
  rơi vào node `id: 'clause-freeform'`. Gọi `reviewTargetNode(numberedNodes, lines, side)`.
  Assert `result.node.id === 'clause-numbered'`. **Khóa**: review-target luôn lấy từ cây
  numbered (cùng khóa search lưu), không phải cây đang xem.
- Assert `result.ordinal === clauseOrdinal(numberedNodes, 'clause-numbered')`. **Khóa**:
  ordinal cũng tính trên cây numbered để descriptor khớp.
- Assert citation không khớp node nào → `reviewTargetNode(...) === null`. **Khóa**: không
  bịa node khi trích dẫn ngoài cây.
RED vì `frontend/src/structure/reviewTarget.ts` chưa tồn tại.

### Implement → GREEN
Tạo `reviewTarget.ts`; nối `numberedTrees` + tham số numbered vào pane; sửa
`linkedClausesOf`. Chạy test tới xanh.

### Tests After
- Test mới xanh.
- `conflict-cite.test.ts` (nguồn `clauseForCitation`/regions) không đổi hành vi → vẫn xanh.

### Regression Gate (lệnh thật)
Từ `frontend/`:
```
npx vitest run tests/conflict-review-target.test.ts
npx tsc --noEmit -p tsconfig.app.json
```
Rồi xác nhận không hồi quy: `npx vitest run tests/conflict-cite.test.ts`. Xanh → commit.

## Success
- [ ] `reviewTargetNode` trả node từ cây numbered; `null` khi ngoài cây.
- [ ] `linkedClauses.node.id` (feed `getClauseReview` → `reviewPath`,
      `clauseReview.ts:107`) khớp `node.id` search lưu → timeline hiện lần đã lưu.
- [ ] Vùng tô PDF (`pane.regions`) không đổi so với trước.
- [ ] `npx vitest run tests/conflict-review-target.test.ts` xanh; `conflict-cite` xanh; `npx tsc --noEmit -p tsconfig.app.json` sạch.

## Risks
- **Pane PDF và review-target trỏ node khác nhau** (research §3). L: có chủ đích, I: thấp
  — chỉ khóa tra cứu đổi cây; hiển thị/regions giữ nguyên. Mitigation: test khóa node id;
  no-op khi `structureMode==='numbered'`.
- **Import vòng** `reviewTarget.ts` → `api/clauseReview.ts` (dùng `clauseOrdinal`). L: thấp
  (`clauseReview` chỉ import type từ `api/structure`; không import `reviewTarget`).
  Mitigation: nếu vòng, sao chép logic ordinal thuần vào `reviewTarget.ts`.
- **Shared file với P3** (`ClauseConflictPage.tsx`). Mitigation: P2 sửa vùng
  `trees`/`linkedClausesOf`/pane; không đụng `CardSource`/`sources` (vùng P3).
