# Red-team review — plan `260927-1931-hitl-conflict-review-fixes`

- **Từ**: code-reviewer (red-teamer) → **Tới**: planner
- **Ngày**: 2026-09-27
- **Phạm vi tấn công**: `plan.md`, `phases/phase-1..3`, `plan-graph.yaml`, `research/conflict-review-surface.md`
- **Kiểu tấn công**: giả định vs. thực thi (claim-vs-enforcement), gate coverage, edge case đếm badge
- **Bằng chứng**: mọi finding có `file:line` hoặc lệnh repro; đã đối chiếu với product code thật, không chỉ đọc plan.
- **Personas**: Failure Mode Analyst · Maintainer-6-months-later · Bad-day Operator.
  Bỏ Security: không có thay đổi ranh giới tin cậy — DTO mở rộng field sẵn có, `_latest_actions` vẫn trong query scoped `tenant_id` (`repository_impl.py:225-227`), đúng như plan constraint-scan kết luận (`plan.md:63-65`).

## Verdict: **CHANGES**

Plan vững về mặt sự thật OBSERVED (đã xác minh lại từng cái ở dưới) và scope hợp lý. Nhưng có **4 khoảng cách M giữa điều plan HỨA và điều gate THỰC SỰ ép** (F1–F4): một bug đếm badge mà req #2 tuyên bố sửa nhưng không sửa, hai Success criteria không gate nào chứng minh được, và một gap null-safety trốn được gate. Xử lý F1–F4 trước khi `cook`.

## Bảng finding (xếp theo severity)

| ID | Sev | Proven/Suspected | Persona | Anchor | Failure (1 câu) | Fix (1 câu) |
|----|-----|------------------|---------|--------|-----------------|-------------|
| F1 | M | Suspected `[ASSUMED]` (constructible) | Failure Mode | `conflictAnchors.ts:134-135`, `StructureViewShell.tsx:256-265`, phase-3 req#2 | Một spot neo trực tiếp vào node cha VÀ vào con của nó bị đếm hai lần trên badge gấp (icon + `+below`), plan req #2 tuyên bố sửa nhưng `visit()` mới không loại id trực tiếp khỏi `below`. | Trừ các id đã có trong `node.spots` khỏi `below` (hoặc không render `+below` cho spot đã hiện trực tiếp), và test assert TỔNG hiển thị == 1 chứ không chỉ `below===1`. |
| F2 | M | Proven | Bad-day Operator | phase-1 gate `phase-1:76` vs Success `phase-1:83`, `repository_impl.py:213-217` | Success "`action_count` = distinct" không gate nào bắt được: gate chỉ chạy `test_conflict_router.py` (DTO + endpoint mock), fix window-count chỉ chạy trên DB thật. | Thêm 1 integration test chạm DB thật cho `_latest_actions`, hoặc hạ Success item này xuống `[ASSUMED]`/manual-verify công khai. |
| F3 | M | Proven | Maintainer | phase-2 gate `phase-2:74-78`, phase-3 gate `phase-3:84-88`, phase-3 Tests-After `phase-3:82` | P2 và P3 sửa `ClauseConflictPage.tsx` (file lớn) nhưng gate chỉ chạy vitest, không tsc/build — lỗi type (ComparePane đổi shape, `visit()` `Set→Map`, null side) lọt gate xanh; P3 còn ghi rõ "Type-check sạch" mà lệnh gate không chạy nó. | Thêm `npx tsc --noEmit` (hoặc script typecheck của repo) vào regression gate của P2 và P3. |
| F4 | M | Proven | Failure Mode | `ClauseConflictPage.tsx:223-224`, phase-2 req `phase-2:36-39` | `linkPane` có `side` = `null` được nhưng plan gọi `reviewTargetNode(numberedNodes, lines ?? [], side)` với `side: ReviewSpotSide` non-null và không nêu guard → NPE/type-error, mà gate P2 (F3) không có tsc để bắt. | Guard `side ? reviewTargetNode(...) : null` và cho `reviewTargetNode` nhận `side` nullable. |
| F5 | L | Proven | Maintainer | research `conflict-review-surface.md` §Câu hỏi mở (~dòng 480) vs `conflict-anchors.test.ts:137-154` | Research khẳng định "Chưa tìm thấy test frontend nào cho conflictAnchors.ts" nhưng file test tồn tại và test `conflictMarkers`; phase-3 lại (đúng) dựa vào file thật → research mâu thuẫn thực tế, sẽ đánh lừa maintainer. | Sửa dòng research: test conflictMarkers có sẵn tại `conflict-anchors.test.ts:137`; chỉ thiếu test render màu badge/TOC của `ConflictBadge`. |
| F6 | L | Proven | Failure Mode | phase-2 req `phase-2:45-47`, research §3 mục 1 | Fallback `node = pane.reviewNode ?? pane.clause`: với hồ sơ freeform/tables mà cây numbered không giải ra node, timeline vẫn dùng khóa `structureMode` (đúng bug cũ) → Success "timeline thấy lần đã lưu" chỉ đúng cho hồ sơ cây numbered giải được. | Ghi giới hạn này vào Acceptance; chấp nhận được vì search cũng không lưu numbered-node cho hồ sơ đó — nhưng phải nói rõ, đừng để Success hứa tuyệt đối. |
| F7 | L | Proven | Maintainer | plan-graph `P1→P2→P3`, cả P2+P3 sửa `ClauseConflictPage.tsx` | Các anchor `file:line` của P3 (`CardSource :55-59`, `sources :70/:190`, `spotToCard :152-162`, `MARKS :89`) tính theo trạng thái TRƯỚC P2; P2 thêm dòng vào cùng file nên chúng dịch. | cook định vị lại theo symbol/tên, không theo số dòng cứng (rủi ro thấp vì cook re-read). |

## Chi tiết các finding M (cần xử lý trước cook)

### F1 — Bug đếm đôi cha+con vẫn còn, req #2 không thực sự sửa

Đã xác minh chuỗi thật:

1. `ownerOf` (`conflictCite.ts:34-42`) recurse con TRƯỚC rồi mới xét node → trả node SÂU NHẤT, **nhưng** một node cha CÓ con vẫn là target trực tiếp nếu nó sở hữu một dòng mà không con nào sở hữu (ví dụ trong tree test `node('3', 1, [line(1,2)], [3.1, 3.2])` — dòng (1,2) thuộc chính node '3').
2. Một spot 2 side cùng document: sideA→(1,2) neo vào '3', sideB→(1,3) neo vào con '3.1'. `anchorConflicts` (`conflictAnchors.ts:90-105`) tạo targets `['3','3.1']`.
3. `visit('3')` (`conflictAnchors.ts:121-137`): con '3.1' trả `{spot.id}` (dòng 134-135), nên `descendant` của '3' = `{spot.id}` → `below=1`; đồng thời `anchors.get('3')=[spot]` → `spots.length=1` trực tiếp.
4. Badge gấp của '3' (`StructureViewShell.tsx:218-266`): nhánh `spots.length>0`, hiện icon (spot trực tiếp) **và** dòng 261-265 `collapsed && below>0` hiện `+1` (chính spot đó) → MỘT xung đột hiện thành "icon +1".

Plan req #2 (`phase-3:40-41`) nói "dedupe theo id đã có (Set/Map)" — nhưng dedup đó chỉ khử trùng TRONG tập descendant, KHÔNG loại spot trực tiếp của node khỏi `below` của chính nó. `visit()` mới ở req #1 (`phase-3:31-38`) cũng không trừ. Test khóa duy nhất assert `markers.get('root')!.below === 1` (`phase-3:70-72`) — đúng nhưng **không** chứng minh tổng hiển thị == 1, nên bug lọt.

Reachability: `[ASSUMED]` ở dữ liệu production (xung đột same-doc cha+con), nhưng **constructible** ngay trong harness test (`conflict-anchors.test.ts` `tree`/`spot` đủ dựng). Blast radius: sai số đếm trên UI, không mất dữ liệu → M.

Cheapest fix: trong `visit()`, khi tính `below` bỏ qua id đã nằm trong `spots` trực tiếp của node; hoặc trong `ConflictBadge` không cộng `+below` cho phần trùng; và bổ sung assert tổng-hiển-thị.

### F2 — Fix double-count `action_count` ship không có test trong gate

Đã xác minh: `_latest_actions` (`repository_impl.py:206-229`) dùng `.outerjoin(AppUserORM, or_(...))` + `func.count(...).over(partition_by=...)` (`:213-217`) → nếu `reviewer_id` khớp 2 AppUser (1 theo `id`, 1 theo `keycloak_sub`) thì nhân dòng → count phồng. Pattern lateral chuẩn tồn tại đúng như plan nói (`review/.../repository_impl.py:388-406`, có `.limit(1).lateral()` + `.outerjoin(reviewer, true())`). Fix là copy hợp lệ.

Nhưng: gate P1 là `uv run pytest tests/unit/test_conflict_router.py` (`phase-1:76`). Test service mock ở tầng repo (`test_conflict_service.py:40`, xác nhận qua research §1) và test router chỉ assert DTO/JSON. **Không test nào chạy SQL window-count thật.** Success `[ ] action_count = số action distinct` (`phase-1:83`) vì thế không thể xanh-bằng-bằng-chứng qua gate đã ghi. Plan có tag `[ASSUMED]` cho hành vi SQL (`phase-1:92-95`) — trung thực — nhưng Success item lại phát biểu như đã chứng minh. Sửa: hoặc thêm integration test DB, hoặc đổi Success item sang `[ASSUMED]`/manual để không hứa quá gate.

### F3 — Gate P2 & P3 không chạy type-check dù sửa file lớn

Gate P2 = `npx vitest run tests/conflict-review-target.test.ts` + `conflict-cite` (`phase-2:74-78`); gate P3 = `npx vitest run tests/conflict-anchors.test.ts` + `conflict-cite` (`phase-3:84-88`). vitest (esbuild) **strip type, không type-check**. Nhưng:
- P2 đổi shape `ComparePane` (thêm `reviewNode`/`reviewOrdinal`), thêm param vào `linkPane/paneForSide/locatePanes` — sai chữ ký nào ở call-site khác trong `ClauseConflictPage.tsx` sẽ không bị 2 test file cô lập bắt.
- P3 đổi kiểu trả `visit()` `Set→Map` và xóa `CardSource`, còn Tests-After ghi rõ "Type-check sạch sau khi đổi kiểu trả `visit()` và xóa `CardSource`" (`phase-3:82`) — nhưng lệnh gate không có tsc.

→ Claim "Type-check sạch" không được ép. Fix: thêm `npx tsc --noEmit` (hoặc script typecheck repo) vào gate P2 và P3.

### F4 — `reviewTargetNode` với `side` null chưa định nghĩa hành vi

`linkPane` (`ClauseConflictPage.tsx:223-224`): `const side = spot.sides.find(...) ?? null`. Plan req P2 (`phase-2:36-39`) bảo tính `reviewNode` từ `reviewTargetNode(numberedNodes, lines ?? [], side)` với chữ ký `side: ReviewSpotSide` non-null (`phase-2:29`). Không có guard cho `side===null` → truy cập `side.pageNo` NPE, hoặc type-error (mà F3 khiến gate P2 không bắt). Fix: guard `side ? reviewTargetNode(...) : null`, cho `reviewTargetNode` nhận nullable.

## Xác nhận các Known facts (không mâu thuẫn — có bằng chứng)

- `FindingReviewDTO.from_row` rớt `latest`: OBSERVED xác nhận — DTO chỉ 3 field (`finding_dtos.py:24-28`), `from_row` không đọc key `latest` (`finding_dtos.py:77-84`); backend đã build `review_payload["latest"]` sẵn (`repository_impl.py:254-259`) và truyền `latest` vào (`repository_impl.py:196-199`, guard `if f.id in review_by_finding else ""` → không KeyError). Fix P1 đúng chỗ.
- Phase 2 giữ lookup theo `node.id` cây numbered: search lưu review trên `answerNodes` = `buildStructureTree(lines,'numbered')` (`DossierStructurePage.tsx:202-205`), `reviewPath` dùng `target.node.id` (`clauseReview.ts:107`), `clauseOrdinal` tồn tại (`clauseReview.ts:130`). **Không khuyến nghị xóa Phase 2** — đồng ý giữ.
- P2 & P3 cùng sửa `ClauseConflictPage.tsx`, graph P1→P2→P3: xác nhận (`plan-graph.yaml` edges; các vùng P2 = `98-111/215-377/559-568`, P3 = `55-59/70/152-162/190/89` tách biệt). Dead-code P3 an toàn: grep toàn `frontend/src` cho `.sources`/`CardSource`/`MARKS` chỉ ra `ClauseConflictPage.tsx` (khai báo + gán, không có điểm ĐỌC `card.sources`); `MARKS` chỉ dùng ở `:159`. `sourceLabel` giữ lại đúng (`linkedClausesOf` `:103`).

## Rủi ro tồn dư (chấp nhận có điều kiện)

- **`.limit(1).lateral()` chọn user không xác định** khi 2 AppUser cùng khớp `reviewer_id`: tên/email hiển thị thành 1 trong 2 tùy DB — nhưng đây đúng pattern đã chấp nhận ở review BC (`repository_impl.py:388-406`). Chấp nhận.
- **Phụ thuộc P1→P2 hơi thừa**: test P2 (`conflict-review-target.test.ts`) chỉ chạm tree/lines/side, không cần `review.latest` thật; ordering vẫn không SAI, chỉ bảo thủ. Không chặn.
- **`extra="forbid"` trên `FindingReviewLatestDTO`**: nếu `from_row` build field-by-field (như pattern hiện có `finding_dtos.py:80-84`) thì key thừa trong dict bị bỏ qua, `forbid` không bao giờ kích — an toàn nhưng gần như vô dụng; nếu cook lỡ dùng `**dict` thì key drift → 500 ở `GET /conflicts`. Ghi chú cho cook: build field-by-field.

---
**Report path**: `C:\Users\dungs\OneDrive\Documents\VSF\plans\260927-1931-hitl-conflict-review-fixes\reports\from-code-reviewer-to-planner-red-team-failure-plan-review-report.md`
**One-line verdict**: **CHANGES** — sự thật OBSERVED vững, scope hợp lý, nhưng F1–F4 (bug đếm cha+con req#2 không sửa; 2 Success không có gate ép; null-side trốn gate) cần xử lý trước cook.
