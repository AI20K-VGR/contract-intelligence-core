# P3 — Badge Counts — Developer Report

## Phạm vi đã sửa (đúng danh sách được giao)
- `frontend/src/structure/conflictAnchors.ts`
- `frontend/src/components/StructureViewShell.tsx`
- `frontend/src/components/StructureDocument.tsx`
- `frontend/src/pages/ClauseConflictPage.tsx`
- `frontend/tests/conflict-anchors.test.ts`

Không đụng `reviewTarget.ts`, backend, hay các field P2 (`reviewNode`/`reviewOrdinal` trên
`ComparePane`, `numberedTrees` trong `ClauseConflictPage.tsx`) — chỉ xoá đúng
`CardSource`/`sources`/`MARKS`, giữ nguyên `sourceLabel` + `linkedClausesOf`.

## TDD — RED trước

Thêm 4 assert/case mới vào `frontend/tests/conflict-anchors.test.ts`:
- `tests/conflict-anchors.test.ts:150-155` — thêm `belowState: 'open'` vào assert cũ của
  `markers.get('3')`.
- `tests/conflict-anchors.test.ts:159-163` — case mới: chỉ có spot `c` (confirm) dưới
  `3.2` → `markers.get('3')` có `belowState: 'reviewed'`, `below: 1`.
- `tests/conflict-anchors.test.ts:165-174` — case mới: 2 spot neo vào node `'9'` (1 open,
  1 dismissed) → `directCount(markers.get('9')!) === 1` nhưng `spots.length === 2`.
- `tests/conflict-anchors.test.ts:176-191` — case mới: 1 spot neo cả vào node cha
  (`nestedRoot`) và con trực tiếp của nó (`leaf`, cùng document) → `markers.get('nestedRoot')
  .spots` chứa id đó và `below === 0` (không cộng `+1` cho cùng spot).

Lệnh: `npx vitest run tests/conflict-anchors.test.ts` (từ `frontend/`).

RED (trước khi implement) — 4/9 fail đúng lý do thiếu field/hàm:
```
FAIL tests/conflict-anchors.test.ts > conflictMarkers > marks the node...
  - "belowState": "open"  (Received thiếu field)
FAIL tests/conflict-anchors.test.ts > conflictMarkers > uses the worst non-dismissed...
  expected {...} to match object { below: 1, belowState: 'reviewed' }
FAIL tests/conflict-anchors.test.ts > conflictMarkers > excludes dismissed spots from directCount...
  TypeError: (0 , directCount) is not a function
FAIL tests/conflict-anchors.test.ts > conflictMarkers > counts a spot once when it is anchored...
  expected 1 to be +0 (below nhận 1 thay vì 0 — chưa loại trùng)
Test Files  1 failed (1)
     Tests  4 failed | 5 passed (9)
```
5 case cũ (`conflictState`, `anchorConflicts`, case sibling `below===1`, `conflict summary
helpers`) vẫn xanh — xác nhận chỉ thêm assert, không phá hồi quy.

## Implement → GREEN

### `conflictAnchors.ts`
- `ConflictMarker` (`:50-58`) thêm field `belowState: ConflictState`.
- Export `directCount(marker)` (`:61-63`) = `spots.filter(s => conflictState(s) !==
  'dismissed').length`.
- `visit()` trong `conflictMarkers()` (`:127-152`) đổi kiểu trả từ `Set<string>` sang
  `Map<string, ConflictState>` (id → trạng thái). Trước khi ghi marker: xoá khỏi
  `descendant` mọi id đang neo trực tiếp vào node đó (`spots`) — đây là điểm khoá yêu cầu
  #2 (đếm 1 lần). Sau đó `belowState` = trạng thái có `STATE_RANK` nhỏ nhất trong các giá
  trị còn lại của `descendant`, mặc định `'dismissed'` khi rỗng.

### `StructureViewShell.tsx`
- Import thêm `directCount`, `type ConflictState` (`:1-9`).
- Thêm helper `toneOf(state)` (`:200-207`) gộp logic màu dùng chung cho cả badge trực
  tiếp và badge gấp.
- Nhánh không có spot trực tiếp nhưng đang gấp (`marker.spots.length === 0`, `:225-233`):
  đổi `bg-amber-400 ... text-amber-950` hard-code thành `toneOf(marker.belowState)`.
- Badge trực tiếp: `const direct = directCount(marker)` (`:236`), dùng `direct` thay
  `marker.spots.length` ở điều kiện padding và số hiển thị (`:254-267`).

### `StructureDocument.tsx`
- TOC (`:228-234`): `<ConflictBadge marker={...} size={13} />` → thêm `collapsed` để lộ
  dấu `+below` khi mục con bị cắt bởi `TOC_DEPTH`. Badge trong thân văn bản (`:355-357`)
  giữ nguyên, không truyền `collapsed`.

### `ClauseConflictPage.tsx`
- Xoá `type CardSource` (cũ `:55-59`), field `sources: CardSource[]` trên `ReviewCard`
  (cũ `:70`), khối build `sources` + field `sources,` trong `spotToCard()` (cũ
  `:154-165`, `:190`), `const MARKS` (cũ `:89`), `sources: [...]` trong `demoCards()`
  (cũ `:409-415`).
- Giữ nguyên `sourceLabel()` và lời gọi trong `linkedClausesOf()`; không đụng
  `reviewNode`/`reviewOrdinal`/`numberedTrees`/pane logic của P2.

Grep xác nhận sạch: `rg "CardSource|MARKS|sources" frontend/src/pages/ClauseConflictPage.tsx`
→ không còn kết quả.

GREEN sau implement:
```
npx vitest run tests/conflict-anchors.test.ts
 ✓ tests/conflict-anchors.test.ts (9 tests) 6ms
 Test Files  1 passed (1)
      Tests  9 passed (9)
```

## Regression

```
npx vitest run tests/conflict-cite.test.ts tests/conflict-review-target.test.ts
 ✓ tests/conflict-cite.test.ts (4 tests) 5ms
 ✓ tests/conflict-review-target.test.ts (3 tests) 5ms
 Test Files  2 passed (2)
      Tests  7 passed (7)
```

`npx tsc --noEmit -p tsconfig.app.json`: còn 14 lỗi, toàn bộ nằm trong
`src/components/StructureSearchResult.tsx` (thuộc mảng AI2 search, ngoài phạm vi P3).
Đã xác minh bằng `git stash` → chạy lại tsc trên baseline (không có thay đổi P3) → cùng
file `StructureSearchResult.tsx` vẫn lỗi tương tự (cộng thêm vài lỗi khác ở
`ConflictNotice.tsx`/`DossierAnalysisPanel.tsx`/`conflictCite.ts` do các phase P1/P2 chưa
merge lúc stash) → xác nhận các lỗi còn lại là tồn tại từ trước, không do P3 gây ra; 5
file trong phạm vi P3 không phát sinh lỗi type mới sau `git stash pop`.

## Deviations so với contract
- Không có sai lệch về logic. Một khác biệt nhỏ về đặt tên: contract gợi ý dùng lại biến
  cục bộ tên `tone` cho bảng màu; tôi tách thành hàm `toneOf(state)` để dùng chung cho cả
  hai nhánh (trực tiếp + gấp) thay vì lặp lại object ternary — không đổi hành vi, chỉ giảm
  trùng lặp (đúng tinh thần "dùng lại bảng tone" trong contract).
- Test case "neo cha+con đếm 1 lần" dựng cây mới (`nestedRoot`/`leaf`) thay vì tái dùng
  `tree` có sẵn, vì `tree` hiện tại không có cặp cha-con nào cùng có OCR line riêng biệt
  phù hợp cho tình huống này mà không phá case sibling cũ (`below === 1`).

## Kết quả cuối
- `npx vitest run tests/conflict-anchors.test.ts` → 9/9 pass.
- `npx vitest run tests/conflict-cite.test.ts tests/conflict-review-target.test.ts` →
  7/7 pass.
- `npx tsc --noEmit -p tsconfig.app.json` → sạch trong phạm vi P3 (lỗi còn lại thuộc
  `StructureSearchResult.tsx`, tồn tại từ trước, ngoài scope).
- Không commit theo yêu cầu.
