---
phase: 3
title: "Badge Counts"
status: pending
plan: 260927-1931-hitl-conflict-review-fixes
created: 2026-09-27
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 3 — Badge Counts

## Overview
Sửa 4 lỗi badge/đếm xung đột trên cây + dọn field chết. Phụ thuộc: P2 (cùng chạm
`ClauseConflictPage.tsx`; chạy sau P2).

## Files
- **Modify** `frontend/src/structure/conflictAnchors.ts` — thêm `belowState` vào
  `ConflictMarker`; `visit()` tính trạng thái nặng nhất của descendant chưa dismissed;
  export helper `directCount`.
- **Modify** `frontend/src/components/StructureViewShell.tsx` — badge nút gấp tô theo
  `belowState`; số trực tiếp dùng `directCount`.
- **Modify** `frontend/src/components/StructureDocument.tsx` — TOC truyền `collapsed`.
- **Modify** `frontend/src/pages/ClauseConflictPage.tsx` — xóa `CardSource`/`sources`
  (+ `MARKS` nếu hết dùng); GIỮ `sourceLabel`.
- **Modify** `frontend/tests/conflict-anchors.test.ts` — mở rộng test.

## Requirements
1. **Màu nút cha gấp theo trạng thái con** — `ConflictMarker` (`conflictAnchors.ts:50-57`)
   thêm `belowState: ConflictState`. `visit()` (`:121-137`) đổi trả `Map<string,
   ConflictState>` (id→state) cho descendant chưa dismissed thay vì `Set<string>`:
   gộp con (`for (const [id, st] of visit(child)) descendant.set(id, st)`), rồi
   `for (const spot of spots) if (conflictState(spot) !== 'dismissed')
   descendant.set(spot.id, conflictState(spot))`. Marker: `below = descendant.size`,
   `belowState` = trạng thái nặng nhất trong `descendant.values()` (rank theo
   `STATE_RANK` `:34-38`; `'dismissed'` khi rỗng). Trong `StructureViewShell.tsx` nhánh
   `spots.length === 0` (`:219-230`) đổi class hard-code `bg-amber-400` (`:223`) sang
   chọn theo `marker.belowState` (dùng lại bảng `tone` `:231-236`).
2. **Neo cả cha + con đếm 1 lần** — khi ghi marker của một nút, `below` là số id ở
   hậu duệ sau khi đã bỏ mọi `spot.id` đang neo trực tiếp vào chính nút đó. Một spot
   vừa nằm trong `spots` của cha vừa nằm ở con thì cha không còn hiện thêm `+1` cho
   cùng id đó.
3. **Số trực tiếp loại dismissed** — thêm export `directCount(marker: ConflictMarker):
   number` = `marker.spots.filter(s => conflictState(s) !== 'dismissed').length`. Trong
   `StructureViewShell.tsx` thay `marker.spots.length` ở số hiển thị (`:256-259`) và
   điều kiện padding (`:250-251`) bằng `directCount(marker)` (import từ conflictAnchors).
4. **TOC truyền `collapsed`** — `StructureDocument.tsx:229` đổi thành
   `<ConflictBadge collapsed marker={markers.get(item.node.id)!} size={13} />` (cố định
   `true` — TOC không có state gấp thật; để lộ số `below` khi mục con bị cắt ở
   `TOC_DEPTH`, research §4). Badge chính trong thân văn bản (`:351-353`) GIỮ nguyên
   (không truyền `collapsed` — đúng thiết kế đệ quy).
5. **Xóa dead code** — bỏ type `CardSource` (`ClauseConflictPage.tsx:55-59`), field
   `sources: CardSource[]` trên `ReviewCard` (`:70`), khối build `sources` trong
   `spotToCard` (`:152-162`) + `sources,` (`:190`), `sources` trong `demoCards()`
   (`:394-399`), và `const MARKS` (`:89`, chỉ dùng ở `:159`). GIỮ hàm `sourceLabel`
   (`:90-96`) và lời gọi ở `linkedClausesOf` (`:103`).

## TDD

### Tests Before (RED) — khóa gì
Mở rộng `frontend/tests/conflict-anchors.test.ts` (tái dùng `tree`/`lines` `:100-109`):
- **belowState**: bổ sung assert vào case `conflictMarkers` hiện có (`:139-154`) —
  `markers.get('3')` hiện `{state:'dismissed', below:2}` với `a`(open,3.1)+`c`(confirm,3.2)
  → thêm `belowState: 'open'`. Thêm case chỉ có `c`(confirm) dưới `3.2` → `markers.get('3')`
  có `belowState: 'reviewed'`, `below: 1`. **Khóa**: màu nút gấp theo trạng thái nặng nhất
  của con chưa dismissed, không cứng amber.
- **direct count loại dismissed**: dựng 2 spot cùng neo vào node `'9'` (page4/line1,
  `:107`) — 1 `null`(open) + 1 `'reject'`(dismissed). Assert
  `directCount(markers.get('9')!) === 1` còn `markers.get('9')!.spots.length === 2`.
  **Khóa**: số trực tiếp loại spot dismissed.
- **neo cha+con đếm 1 lần**: spot hai side, một side trỏ `root`, side kia trỏ con của
  `root`. Assert `markers.get('root')!.spots` chứa id đó và `markers.get('root')!.below === 0`.
  **Khóa**: không hiện cả badge trực tiếp lẫn `+1` cho cùng một spot. Case hai nút anh em
  (`below === 1`) giữ nguyên.
RED vì `belowState`/`directCount` chưa tồn tại (thiếu field/hàm).

### Implement → GREEN
Sửa `visit()`/`ConflictMarker`/`directCount`, `StructureViewShell`, `StructureDocument`,
xóa dead code. Chạy test tới xanh.

### Tests After
- Toàn bộ `conflict-anchors.test.ts` xanh (case cũ `:139-154`, `:157-181`, `:183-190`
  không hồi quy — chỉ thêm assert).
- Type-check sạch sau khi đổi kiểu trả `visit()` và xóa `CardSource`.

### Regression Gate (lệnh thật)
Từ `frontend/`:
```
npx vitest run tests/conflict-anchors.test.ts
npx tsc --noEmit -p tsconfig.app.json
```
Xác nhận thêm không hồi quy: `npx vitest run tests/conflict-cite.test.ts`. Xanh → commit.

## Success
- [ ] `belowState` phản ánh trạng thái nặng nhất của con chưa dismissed; badge nút gấp
      đổi màu theo đó (không cứng amber).
- [ ] `directCount` loại dismissed; badge số trực tiếp dùng nó.
- [ ] TOC hiện dấu khi xung đột nằm ở mục con đang gấp (`collapsed` truyền).
- [ ] Spot neo cả cha+con đếm 1 lần trên tổ tiên.
- [ ] `CardSource`/`sources`/`MARKS` bị xóa; `sourceLabel` còn nguyên và
      `linkedClausesOf` vẫn build đúng label.
- [ ] `npx vitest run tests/conflict-anchors.test.ts` xanh; `conflict-cite` xanh; `npx tsc --noEmit -p tsconfig.app.json` sạch.

## Risks
- **Đổi kiểu trả `visit()`** (`Set`→`Map`) có thể lỡ chỗ dùng. L: thấp — `visit` là
  closure nội bộ `conflictMarkers` (`:121-139`), không export. Mitigation: chỉ sửa trong
  hàm; type-check bắt lỗi còn sót.
- **Xóa `MARKS` khi vẫn còn dùng** → build lỗi. Mitigation: grep xác nhận chỉ `:159`
  dùng (đã kiểm: chỉ 1 điểm); xóa cùng khối `sources`.
- **Shared file với P2** (`ClauseConflictPage.tsx`). Mitigation: P3 chỉ đụng
  `CardSource`/`sources`/`MARKS`; không sửa `trees`/`linkedClausesOf`/pane (vùng P2);
  rebase trên P2.
- **`belowState` khi below===0**: giá trị `'dismissed'` mặc định không được dùng (nhánh
  gấp chỉ render khi `below>0`). Mitigation: test chỉ assert belowState khi below>0.
