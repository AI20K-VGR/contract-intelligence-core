# P2 — Numbered Timeline: báo cáo triển khai

## Phạm vi
- **Tạo**: `frontend/src/structure/reviewTarget.ts`, `frontend/tests/conflict-review-target.test.ts`
- **Sửa**: `frontend/src/pages/ClauseConflictPage.tsx`
- Không đụng `conflictAnchors.ts`, `StructureViewShell`, finding DTOs, OCR pipeline.
- Không commit (theo yêu cầu).

## TDD

### RED
Viết `frontend/tests/conflict-review-target.test.ts` (3 case: khóa lấy từ cây numbered,
ordinal khớp `clauseOrdinal`, trả `null` khi trích dẫn ngoài cây) trước khi
`reviewTarget.ts` tồn tại.

Lệnh: `npx vitest run tests/conflict-review-target.test.ts` (từ `frontend/`)

```
FAIL  tests/conflict-review-target.test.ts [ tests/conflict-review-target.test.ts ]
Error: Cannot find module '../src/structure/reviewTarget' imported from
'.../frontend/tests/conflict-review-target.test.ts'
Test Files  1 failed (1)
     Tests  no tests
```

RED đúng nguyên nhân: module `reviewTarget.ts` chưa tồn tại — không phải lỗi test sai.

### GREEN
Tạo `frontend/src/structure/reviewTarget.ts:1-45`: hàm thuần `reviewTargetNode`,
copy đúng logic `nodeForSide` của `conflictAnchors.ts:66-76` (ưu tiên
`clauseForCitation`, fallback `findClauseByQuote`), ordinal qua `clauseOrdinal`
(`api/clauseReview.ts:130`). Không tính sha256/hash trong file này (khớp red-team
note "Do not invent hashes" — hash chỉ dùng ở `getClauseReview`/`saveClauseReview`
phía `clauseReview.ts`, không nằm trong `reviewTarget.ts`).

Lệnh: `npx vitest run tests/conflict-review-target.test.ts`

```
✓ tests/conflict-review-target.test.ts (3 tests) 3ms
Test Files  1 passed (1)
     Tests  3 passed (3)
```

## Nối vào `ClauseConflictPage.tsx`
- Import `reviewTargetNode` (`:45`).
- `ComparePane` thêm `reviewNode: ClauseNode | null`, `reviewOrdinal: number`
  (`:87-88`).
- `linkedClausesOf` (`:101-113`): `node = pane.reviewNode ?? pane.clause`;
  `ordinal = pane.reviewNode ? pane.reviewOrdinal : pane.ordinal`; bỏ pane khi
  `node` vẫn null (cả `reviewNode` và `clause` đều null) — giữ nguyên
  `label: sourceLabel(pane.label)`.
- `linkPane` (`:218-266`) nhận thêm `numberedNodes: ClauseNode[]`; tính
  `reviewTarget = side ? reviewTargetNode(numberedNodes, lines ?? [], side) : null`
  (`:233`, chỉ gọi khi có `side`, nhánh `side` null giữ nguyên ở `:224-225`);
  gán `reviewNode`/`reviewOrdinal` vào pane trả về (`:262-263`). `regions`/`quote`/
  `clause` không đổi (vẫn từ cây `structureMode` qua tham số `nodes`/`lines` cũ).
- `paneForSide` (`:339-388`) nhận thêm `numberedNodes`; nhánh `!side` trả
  `reviewNode: null, reviewOrdinal: 0` (`:360-361`); nhánh có `side` gọi
  `reviewTargetNode(numberedNodes, lines ?? [], side)` không điều kiện thêm vì
  `side` đã chắc chắn tồn tại tại điểm này (`:369`).
- `locatePanes` (`:272-334`) nhận thêm `numberedByDocument: Record<string, ClauseNode[]>`,
  truyền `numberedByDocument[host.id] ?? []` vào `paneForSide` (`:302`) và
  `numberedByDocument[contract.id] ?? []` / `numberedByDocument[annex.id] ?? []`
  vào hai lần gọi `linkPane` (`:317`, `:328`).
- Thêm memo `numberedTrees` (`:586-595`), song song `trees` (`:576-585`) nhưng
  luôn build `buildStructureTree(lines, 'numbered')` (không phụ thuộc
  `structureMode`) — khi hồ sơ đã là `numbered`, giá trị bằng `trees` (no-op
  hành vi, dù khác tham chiếu object).
- `linksById` (`:598-608`) truyền `numberedTrees` vào `locatePanes` (`:604`).

## Kết quả kiểm tra (từ `frontend/`)

1. `npx vitest run tests/conflict-review-target.test.ts`
```
✓ tests/conflict-review-target.test.ts (3 tests) 3ms
Test Files  1 passed (1)
     Tests  3 passed (3)
```

2. `npx vitest run tests/conflict-cite.test.ts` (regression — nguồn
   `clauseForCitation`/regions không đổi hành vi)
```
✓ tests/conflict-cite.test.ts (4 tests) 4ms
Test Files  1 passed (1)
     Tests  4 passed (4)
```

3. `npx tsc --noEmit -p tsconfig.app.json`
Kết quả: **14 lỗi**, toàn bộ ở `src/components/StructureSearchResult.tsx`
(`Ai2SearchHit`/`Ai2SearchResult` thiếu field `breadcrumb`/`tableId`/`state`/
`notes`/`n`/`citationId`/`validationStatus`, và export `DossierSearchState`
không tồn tại). Đã xác minh đây là lỗi **tiền tồn tại, không do P2 gây ra**:
`git stash -- frontend/src/pages/ClauseConflictPage.tsx` rồi chạy lại `tsc` cho
đúng 14 lỗi giống nhau (file không đổi, không nằm trong phạm vi P2 — không được
sửa). `git stash pop` khôi phục lại thay đổi P2 trước khi tiếp tục. `reviewTarget.ts`
và các đoạn sửa trong `ClauseConflictPage.tsx` không phát sinh lỗi `tsc` mới.

## Sai lệch / quyết định
- Không có sai lệch so với hợp đồng phase. `numberedTrees` build không rẽ nhánh
  theo `structureMode` (khác một chút cách viết so với gợi ý "song song `trees`"
  vì `trees` có rẽ nhánh theo `structureMode` còn `numberedTrees` cố định
  `'numbered'`) — hành vi đúng yêu cầu: khi `structureMode==='numbered'` hai map
  có giá trị bằng nhau (no-op), khi khác `'numbered'` thì `numberedTrees` vẫn
  luôn là cây numbered để khớp khóa search đã lưu.
- `tsc` còn 14 lỗi tiền tồn tại ngoài phạm vi (file `StructureSearchResult.tsx`,
  không thuộc "MAY modify" của phase này) — đã xác minh không phải do thay đổi
  của P2, không tự sửa vì ngoài quyền sở hữu file.

## Files đã sửa/tạo (trong đúng phạm vi cho phép)
- `frontend/src/structure/reviewTarget.ts` — mới, 45 dòng.
- `frontend/tests/conflict-review-target.test.ts` — mới, 100 dòng.
- `frontend/src/pages/ClauseConflictPage.tsx` — sửa (thêm ~40 dòng thực chất cho
  P2: import, `reviewNode`/`reviewOrdinal` trên `ComparePane`, `linkedClausesOf`,
  tham số `numberedNodes`/`numberedByDocument` trên `linkPane`/`paneForSide`/
  `locatePanes`, memo `numberedTrees`, cập nhật gọi `locatePanes`).

Không commit theo yêu cầu.
