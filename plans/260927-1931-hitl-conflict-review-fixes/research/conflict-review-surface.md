# Research: HITL conflict review surface — bằng chứng cho planner

Phạm vi: chỉ đọc repo, không sửa code. Mọi kết luận có `file:line` kèm quote gốc.

## 1. DTO nhỏ nhất giữ `extra=forbid`, trả đủ action/comment/reviewer_name/reviewer_email/reviewed_at/action_count

**Shape thật của dict `latest`** — repo build sẵn đúng các field cần, tại
`backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py:233-241`:

```
233:        for action, name, email, action_count in rows:
234:            latest[action.review_item_id] = {
235:                "action": action.action,
236:                "comment": action.comment,
237:                "reviewer_id": action.reviewer_id,
238:                "reviewer_name": name,
239:                "reviewer_email": email,
240:                "reviewed_at": action.created_at.isoformat() if action.created_at else None,
241:                "action_count": int(action_count or 0),
```

Dict này được gắn vào `review_payload["latest"]` ở `_finding_to_dict`
(`backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py:254-259`):

```
254:        review_payload = None
255:        if review is not None:
256:            review_payload = {
257:                "item_id": review.id,
258:                "status": review.status,
259:                "current_version": int(review.version or 0),
260:                "latest": latest,
261:            }
```

**DTO hiện tại chỉ có 3 field, không đọc `latest`**
(`backend/src/contract_intelligence/conflict/application/dtos/finding_dtos.py:23-28`):

```
23:class FindingReviewDTO(BaseModel):
24:    model_config = ConfigDict(extra="forbid")
25:
26:    item_id: str
27:    status: str
28:    current_version: int = 0
```

Và `from_row` không đọc key `"latest"` từ `review_raw` (`finding_dtos.py:77-84`):

```
77:        review = None
78:        review_raw = row.get("review")
79:        if isinstance(review_raw, dict) and review_raw.get("item_id"):
80:            review = FindingReviewDTO(
81:                item_id=str(review_raw["item_id"]),
82:                status=str(review_raw.get("status") or "open"),
83:                current_version=int(review_raw.get("current_version") or 0),
84:            )
```

**Không có model lồng nào tái dùng được.** Đã kiểm `review/application/dtos/review_dtos.py`:
- `ClauseReviewEntryDTO` (`review_dtos.py:166-181`) có `revision_number`, `review_action_id`,
  `reviewer_id`, `base_version` là **required** — repo `_latest_actions` không sinh các field
  này (không có `id` hành động lẻ, không có `base_version`). Ép dùng model này buộc phải sửa
  câu SQL để bơm thêm field giả, không phải "nhỏ nhất".
- Các DTO khác trong file (`ReviewItemRevisionDTO`, `FindingReviewDTO` phía review BC…) đều
  gắn với luồng review-item/clause-node, không khớp field-set của finding's `latest`.

→ Cách nhỏ nhất: thêm **1 model mới** (ví dụ `FindingReviewLatestDTO`, `extra="forbid"`) đúng
6 field trong dict trên (`action`, `comment`, `reviewer_id`, `reviewer_name`, `reviewer_email`,
`reviewed_at`, `action_count` — 7 field, dict đã có `reviewer_id` sẵn dù finding_dtos.py không
yêu cầu), gắn `latest: FindingReviewLatestDTO | None = None` vào `FindingReviewDTO`, và
`from_row` build nó từ `review_raw.get("latest")`.

**Test đã có, sẽ không vỡ (vì hiện chưa test field `latest`):**
`backend/tests/unit/test_conflict_router.py:33-62` — helper `_finding()` gọi
`FindingDTO.from_row(base)` với `base` **không có key `"review"`** (dict `base` dừng ở `"sides"`
lúc `.update(overrides)`), nên thêm field mới vào `FindingReviewDTO` là an toàn, không phá test
cũ. Endpoint `GET /conflicts` được test ở `TestListConflicts.test_returns_conflict_subset`
(`test_conflict_router.py:117-124`) — chỉ assert `id` và `total`, không assert `review`.
`backend/tests/unit/application/test_conflict_service.py` mock `list_conflicts_for_review` ở
tầng service (dòng 40), không chạm SQL thật/`_latest_actions` — nghĩa là double-count ở Q5
hiện **không có test nào bắt được**.

## 2. Field name frontend `ReviewSpotLatest` khớp key backend

`asReviewLatest` — `frontend/src/api/structure.ts:542-556`:

```
542:function asReviewLatest(value: unknown): ReviewSpotLatest | null {
543:  const row = asRecord(value)
544:  const action = asString(row?.action)
545:  if (!row || !action) return null
546:  return {
547:    action,
548:    comment: typeof row.comment === 'string' ? row.comment : null,
549:    reviewerId: asString(row.reviewer_id),
550:    reviewerName: typeof row.reviewer_name === 'string' ? row.reviewer_name : null,
551:    reviewerEmail:
552:      typeof row.reviewer_email === 'string' ? row.reviewer_email : null,
553:    reviewedAt: typeof row.reviewed_at === 'string' ? row.reviewed_at : null,
554:    actionCount: asNumber(row.action_count),
555:  }
556:}
```

Khớp **1-1 snake_case** với dict repo build ở Q1 (`action`, `comment`, `reviewer_id`,
`reviewer_name`, `reviewer_email`, `reviewed_at`, `action_count`). Type khai báo ở
`frontend/src/api/structure.ts:61-69`:

```
61:export type ReviewSpotLatest = {
62:  action: string
63:  comment: string | null
64:  reviewerId: string
65:  reviewerName: string | null
66:  reviewerEmail: string | null
67:  reviewedAt: string | null
68:  actionCount: number
69:}
```

**Kết luận:** frontend đã đúng và đã sẵn sàng chờ backend gửi `review.latest`. Lời gọi
`asReviewLatest(reviewRow?.latest)` nằm ở `structure.ts:536`, bên trong `asReviewSpot`
(dùng bởi `listReviewSpots` → `/conflicts`, `structure.ts:557-565`). Không cần sửa gì ở
frontend cho phần field-mapping — fix hoàn toàn nằm ở backend DTO (Q1).

## 3. `structureMode`, và rủi ro nếu tách cây cho linkedClauses khỏi cây cho compare-pane

Các giá trị `StructureMode` tồn tại (`frontend/src/structure/types.ts:9,20-40`):
`'numbered' | 'freeform' | 'tables'`. `buildStructureTree` (`frontend/src/structure/index.ts:20-28`):

```
20:export function buildStructureTree(
21:  lines: OcrLine[],
22:  mode: StructureMode,
23:): ClauseNode[] {
24:  if (mode === 'tables') return []
25:  return mode === 'freeform'
26:    ? buildFreeformTree(lines)
27:    : buildNumberedTree(lines)
28:}
```
→ `mode === 'tables'` **luôn trả `[]`**; `'freeform'` dùng thuật toán heading-based hoàn toàn
khác `'numbered'` (Điều/Khoản).

**Trong `ClauseConflictPage.tsx` hiện tại, có đúng MỘT cây dùng cho cả hai việc** (không tách
như câu hỏi giả định):

- `structureMode` lấy từ `detail.structureMode` (`ClauseConflictPage.tsx:558`):
  `const structureMode = detail?.structureMode ?? 'numbered'`
- `trees` build 1 lần bằng `structureMode` đó (`ClauseConflictPage.tsx:559-568`):
  ```
  559:  const trees = useMemo(() => {
  560:    const map: Record<string, ClauseNode[]> = {}
  561:    for (const [id, lines] of Object.entries(linesByDocument)) {
  562:      map[id] =
  563:        lines.length > 0
  564:          ? buildStructureTree(lines, structureMode)
  565:          : (nodesByDocument[id] ?? [])
  566:    }
  567:    return map
  568:  }, [linesByDocument, nodesByDocument, structureMode])
  ```
- `locatePanes(spot, documents, trees, linesByDocument)` (`ClauseConflictPage.tsx:575`) —
  tham số hình thức tên là `nodesByDocument` trong định nghĩa `locatePanes`
  (`ClauseConflictPage.tsx:263-268`) nhưng **giá trị truyền vào là `trees`**, không phải
  `nodesByDocument` state gốc. `locatePanes` gọi `linkPane`/`paneForSide`, cả hai đều gọi
  `clauseForCitation(nodes, lines, side.pageNo, side.lineNo)` (dòng 226-228, 351-353) trên
  đúng cây đó, set `pane.clause`.
- `linkedClausesOf(panes)` (`ClauseConflictPage.tsx:97-111`) chỉ đọc `pane.clause` từ các
  `ComparePane` đã có sẵn (kết quả của `locatePanes` ở trên) — **không tự build cây riêng**:
  ```
  97:function linkedClausesOf(panes: ComparePane[]): LinkedClause[] {
  98:  return panes.flatMap((pane) =>
  99:    pane.clause
  100:      ? [
  101:          {
  102:            label: sourceLabel(pane.label),
  103:            documentId: pane.document.id,
  104:            node: pane.clause,
  105:            ordinal: pane.ordinal,
  106:          },
  107:        ]
  108:      : [],
  109:  )
  110:}
  ```
  Được gọi tại `ClauseConflictPage.tsx:1079-1081`: `linkedClauses={linkedClausesOf(linksById.get(card.id) ?? [])}`.

**Kết luận cho câu hỏi giả định:** hiện `ClauseConflictPage` **không** có tách cây; compare-pane
và linkedClauses đang dùng chung 1 cây theo `structureMode`. Đối chiếu với
`DossierStructurePage.tsx:201-205` — nơi cố ý ép cứng `'numbered'` cho `answerNodes` (trích dẫn
câu trả lời AI2), có comment giải thích: *"Câu trả lời AI2 không đi theo loại cấu trúc đang
xem."* Đây là một khu vực khác (AI2 answer citation), **không phải mẫu nên copy sang
ClauseConflictPage**.

Nếu planner làm giống `answerNodes` — ép `'numbered'` riêng cho cây build `linkedClausesOf` mà
để compare-pane (`locatePanes`) tiếp tục dùng cây theo `structureMode` thật của hồ sơ — hậu quả:

1. Với hồ sơ `structureMode === 'freeform'` hoặc `'tables'`: `buildStructureTree(lines,'numbered')`
   chạy `buildNumberedTree` (tìm mẫu Điều/Khoản) trên văn bản không đánh số kiểu đó, hoặc trên
   cây `'tables'` (đáng lẽ luôn `[]`) — rất có thể trả cây rỗng hoặc node sai khớp cho cùng
   `pageNo`/`lineNo`. `clauseForCitation` khi đó trả `null` → `linkedClausesOf` **rớt hẳn**
   clause khỏi `LinkedClause[]`, dù compare-pane bên cạnh (`located`, dùng cây đúng
   `structureMode`) vẫn khoanh vùng và hiện trích dẫn bình thường trên PDF.
2. Ngay cả khi cả hai cây đều khác `[]`, `'numbered'` vs `structureMode` thật là hai thuật toán
   phân cấp khác nhau → node trùng `pageNo/lineNo` có thể map ra **2 `ClauseNode` khác nhau**
   (id, `ordinal`, `label` khác nhau). Reviewer nhìn thấy trích dẫn A trên pane so sánh nhưng
   `ConflictFindingReview` (nhận `linkedClauses` từ `linkedClausesOf`) lại gắn hành động thẩm
   định vào node/ordinal B — sai lệch giữa cái hiện trên màn hình và cái được ghi vào audit
   trail của review.

→ Không nên tách; giữ nguyên 1 cây theo `structureMode` cho cả hai chỗ dùng, đúng như code hiện
tại đang làm.

## 4. Badge: `conflictMarkers.visit()`, `ConflictBadge` khi `spots.length===0`, TOC không truyền `collapsed`

`visit()` trong `conflictMarkers` — `frontend/src/structure/conflictAnchors.ts:121-137`:

```
121:  function visit(node: ClauseNode): Set<string> {
122:    const descendant = new Set<string>()
123:    for (const child of node.children) {
124:      for (const id of visit(child)) descendant.add(id)
125:    }
126:    const spots = anchors.get(node.id) ?? []
127:    if (spots.length > 0 || descendant.size > 0) {
128:      markers.set(node.id, {
129:        spots,
130:        state: worstState(spots),
131:        below: descendant.size,
132:      })
133:    }
134:    for (const spot of spots) {
135:      if (conflictState(spot) !== 'dismissed') descendant.add(spot.id)
136:    }
137:    return descendant
138:  }
```

Nhận xét quan trọng: `descendant` set chỉ cộng `spot.id` khi **không** `dismissed`
(dòng 135), nên `marker.below` đã là **đếm loại trừ dismissed** — nhưng `ConflictMarker`
không lưu lại trạng thái chi tiết (open vs reviewed) của các spot nằm trong `below`, chỉ có
tổng số.

`ConflictBadge` — nhánh `spots.length === 0` (`frontend/src/components/StructureViewShell.tsx:219-230`):

```
219:  if (marker.spots.length === 0) {
220:    if (!collapsed || marker.below === 0) return null
221:    return (
222:      <span
223:        className="inline-flex shrink-0 items-center justify-center rounded-full bg-amber-400 px-1 font-semibold leading-none text-amber-950"
224:        style={{ height: size, minWidth: size, fontSize: Math.max(9, size - 6) }}
225:        title={title}
226:      >
227:        {marker.below}
228:      </span>
229:    )
230:  }
```

→ Màu **hard-code `bg-amber-400`** (tông "open, chưa thẩm định") bất kể trạng thái thật của các
descendant spot (có thể toàn bộ đã `reviewed`, không nên tô đậm như "chưa ai thẩm định").
`worstState`/`STATE_RANK` (`conflictAnchors.ts:33-46`) hiện chỉ áp cho `marker.spots` trực tiếp
(dòng 130: `state: worstState(spots)`), không có phiên bản áp cho tập `below`.

Nhánh có `spots.length > 0` (chỗ đã đúng, dùng làm mẫu tô màu theo state):
`StructureViewShell.tsx:231-236`:
```
231:  const tone =
232:    marker.state === 'open'
233:      ? 'bg-amber-400 text-amber-950'
234:      : marker.state === 'reviewed'
235:        ? 'border border-amber-400 bg-amber-50 text-amber-800'
236:        : 'bg-slate-200 text-slate-500 opacity-70'
```

Lời gọi `ConflictBadge` trong TOC của `StructureDocument.tsx:228-230` — **không truyền `collapsed`**:
```
228:                      {markers?.get(item.node.id) ? (
229:                        <ConflictBadge marker={markers.get(item.node.id)!} size={13} />
230:                      ) : null}
```
Do default `collapsed = false` (`StructureViewShell.tsx:211`), nhánh `spots.length===0` luôn
`return null` cho TOC (điều kiện `!collapsed` đúng ⇒ null), **bất kể `below` > 0**.

So sánh với 2 nơi khác *đã* truyền đúng:
- `frontend/src/components/StructureOutline.tsx:371`:
  `{marker ? <ConflictBadge collapsed={!row.open} marker={marker} /> : null}`
- `frontend/src/components/StructureMindmap.tsx:1143`:
  `<ConflictBadge collapsed={!box.open} marker={box.marker} />`

Còn badge chính trong thân văn bản (`StructureDocument.tsx:351-353`, không truyền `collapsed`)
là **đúng theo thiết kế**: `StructureDocument` không có khái niệm "gấp/mở" — mọi `Section`
(mọi node, mọi độ sâu) đều tự render kèm badge riêng (đệ quy `kids.map` tại
`StructureDocument.tsx:381-393`), nên node cha không cần "gộp" số của con — con đã có badge của
chính nó. Ngược lại, TOC **bị chặn ở `TOC_DEPTH = 2`**
(`StructureDocument.tsx:36,46`: `if (depth < TOC_DEPTH) for (const kid of visibleChildren(node)) walk(kid, depth + 1)`) —
nên với node độ sâu = `TOC_DEPTH`, các cháu (depth 3+) không có mục riêng trong TOC; xung đột
của chúng chỉ có thể hiện qua `below` của mục TOC gần nhất, và đó chính là nơi TOC cần
`collapsed`.

**Thay đổi hành vi nhỏ nhất cho 4 yêu cầu:**
1. *Màu badge gấp theo state nặng nhất của descendant chưa dismiss*: `visit()` cần tính thêm
   trạng thái nặng nhất trong `descendant` (không chỉ đếm), lưu vào `ConflictMarker` (field mới,
   ví dụ `belowState`), rồi nhánh `spots.length===0` của `ConflictBadge` dùng field đó để chọn
   class màu (tương tự bảng `tone` ở dòng 231-236) thay vì hard-code `bg-amber-400`.
2. *Một spot neo vào cả node và con của nó chỉ tính 1 lần trên node đó*: `anchorConflicts`
   (`conflictAnchors.ts:82-107`) đã đảm bảo 1 spot chỉ neo vào **1 node** target
   (`targets.push` có kiểm `!targets.some(...)`, dòng 93-96) — nhưng câu hỏi ở đây có thể là
   việc 1 spot vừa nằm trong `anchors.get(node.id)` (trực tiếp) **và** trong `descendant` set
   của chính `node.id` đó qua một target khác của cùng spot (side khác trỏ vào con). Cần kiểm
   tra: nếu spot đã có trong `spots` (trực tiếp trên node), không được cộng lại nó vào `below`
   của cùng node dù nó cũng match một con. `visit()` hiện tại KHÔNG loại trừ trường hợp này —
   dòng 134-136 cộng mọi `spots` (trực tiếp) của node vào `descendant` trả lên cho cha, và cha
   dùng `descendant.size` làm `below` — nếu spot đó cũng có mặt trong `anchors` của một con của
   `node` (2 sides, 1 trỏ chính node, 1 trỏ con), `descendant` (được gộp từ `visit(child)`) và
   `spots` (trực tiếp trên `node`) đều chứa id đó → `Set` khử trùng ở cấp `node` (do
   `descendant.add(id)`, Set) nên **không double count ở `node.id`**, nhưng vẫn cần xác nhận với
   trường hợp target trên chính `node` (không phải con) — lúc đó `spots.length>0` nên nhánh
   dùng `marker.spots`, không dùng `below`, không có rủi ro đếm đôi ở nhánh này.
3. *Badge trực tiếp loại trừ dismissed*: `worstState(spots)` (`conflictAnchors.ts:41-48`) dùng
   `STATE_RANK` để lấy trạng thái NẶNG NHẤT trong `spots` trực tiếp (không loại bỏ dismissed
   trước) — nếu 1 node có 2 spot, 1 `dismissed` 1 `open`, `worstState` trả `'open'` (đúng, vì
   'open' rank 0 < 'dismissed' rank 2, hàm lấy rank nhỏ nhất). Số hiện trên badge nhiều-spot lại
   là `marker.spots.length` thô (`StructureViewShell.tsx:257`: `{marker.spots.length}` — dòng
   cần xem lại, hiện ở khoảng 255-260) — **đếm cả spot đã dismissed**, không khớp yêu cầu "direct
   badge count excludes dismissed". Cần đổi số hiển thị sang
   `spots.filter(s => conflictState(s) !== 'dismissed').length` (hoặc tương đương) khi
   `marker.spots.length > 1`.
4. *TOC truyền `collapsed`*: đổi lời gọi ở `StructureDocument.tsx:229` thành có `collapsed`
   (mẫu giống Outline/Mindmap: `collapsed={...}` — ở đây TOC không có state mở/gấp thật, nên
   giá trị hợp lý nhất là `collapsed` cố định `true` cho mọi mục TOC, để badge luôn lộ số
   `below` khi mục đó không có xung đột trực tiếp nhưng có xung đột ở nhánh con bị TOC cắt ở
   `TOC_DEPTH`).

## 5. AppUser outerjoin ở `_latest_actions` vs pattern lateral-join của review repo

**`_latest_actions` — outerjoin trực tiếp, có OR trên 2 cột:**
`backend/src/contract_intelligence/conflict/infrastructure/persistence/repository_impl.py:206-229`:

```
206:    async def _latest_actions(self, item_ids: list[str]) -> dict[str, dict[str, Any]]:
207:        """Lượt thẩm định gần nhất của từng review item, kèm tên và email người thẩm định."""
208:        if not item_ids:
209:            return {}
210:        stmt = (
211:            select(
212:                ReviewActionORM,
213:                AppUserORM.display_name,
214:                AppUserORM.email,
215:                func.count(ReviewActionORM.id)
216:                .over(partition_by=ReviewActionORM.review_item_id)
217:                .label("action_count"),
218:            )
219:            .outerjoin(
220:                AppUserORM,
221:                or_(
222:                    AppUserORM.id == ReviewActionORM.reviewer_id,
223:                    AppUserORM.keycloak_sub == ReviewActionORM.reviewer_id,
224:                ),
225:            )
226:            .where(
227:                ReviewActionORM.tenant_id == self._tenant_id,
228:                ReviewActionORM.review_item_id.in_(item_ids),
229:            )
230:            .order_by(ReviewActionORM.created_at.asc(), ReviewActionORM.id.asc())
231:        )
```

Rủi ro: `outerjoin` với `or_(A.id == x, A.keycloak_sub == x)` **có thể khớp nhiều hơn 1 dòng
`AppUserORM`** cho cùng 1 `ReviewActionORM` (nếu tồn tại 2 user khác nhau mà 1 có `id`, 1 có
`keycloak_sub` cùng bằng `reviewer_id`) → nhân dòng `ReviewActionORM` trong kết quả → làm
`func.count(...).over(partition_by=review_item_id)` (dòng 215-217) đếm **quá số hành động
thật** vì nó đếm số dòng sau join, không đếm số action distinct.

**Pattern lateral-join đã tồn tại, tránh đúng lỗi này:**
`backend/src/contract_intelligence/review/infrastructure/persistence/repository_impl.py:388-408`:

```
388:        reviewer = (
389:            select(AppUserORM.display_name, AppUserORM.email)
390:            .where(
391:                or_(
392:                    AppUserORM.id == ReviewActionORM.reviewer_id,
393:                    AppUserORM.keycloak_sub == ReviewActionORM.reviewer_id,
394:                )
395:            )
396:            .limit(1)
397:            .lateral()
398:        )
399:        stmt = (
400:            select(ReviewActionORM, reviewer.c.display_name, reviewer.c.email)
401:            .outerjoin(reviewer, true())
402:            .where(
403:                ReviewActionORM.review_item_id == item_id,
404:                ReviewActionORM.tenant_id == self._tenant_id,
405:            )
406:            .order_by(ReviewActionORM.created_at.asc(), ReviewActionORM.id.asc())
407:        )
```

`.limit(1).lateral()` ép subquery chỉ trả **tối đa 1 dòng** AppUser mỗi `ReviewActionORM`, join
bằng `true()` (correlated theo `or_` bên trong subquery) — không thể nhân dòng
`ReviewActionORM`, nên bất kỳ `count`/window function nào phía trên vẫn đúng.

**Copy pattern nào:** thay `.outerjoin(AppUserORM, or_(...))` trực tiếp ở `_latest_actions`
(dòng 219-225) bằng đúng subquery `reviewer = select(...).where(or_(...)).limit(1).lateral()`
rồi `.outerjoin(reviewer, true())`, y hệt `review/infrastructure/persistence/repository_impl.py:388-401`
— chỉ đổi tên cột lấy thêm (vẫn cần `display_name`, `email`) và giữ `func.count(...).over(...)`
tính trên `ReviewActionORM.id` sau khi join đã an toàn.

## 6. `card.sources` / `CardSource` — gán nhưng không đọc; `sourceLabel` vẫn dùng, không được xoá

`CardSource` khai báo (`ClauseConflictPage.tsx:55-59`):
```
55:type CardSource = {
56:  label: string
57:  quote: string
58:  mark: 'amber' | 'sky'
59:}
```
Field `sources: CardSource[]` trên `ReviewCard` (`ClauseConflictPage.tsx:70`), **được gán** ở
2 nơi:
- `spotToCard` (`ClauseConflictPage.tsx:152-161` build `sources`, gán ở dòng 190: `sources,`)
- `demoCards()` (`ClauseConflictPage.tsx:394-399`)

Grep toàn file cho `.sources`/`sources:` chỉ ra đúng 2 điểm gán này (`ClauseConflictPage.tsx:70`
là khai báo type, `394` là gán demo) — **không có điểm đọc** (`card.sources`, `.sources.map(...)`
không xuất hiện trong JSX hay logic khác của file). Xác nhận: `sources`/`CardSource` là dead
write-only field, an toàn để planner xoá.

`sourceLabel` (hàm, không phải field `sources`) — **vẫn đang được dùng** ở
`linkedClausesOf` (`ClauseConflictPage.tsx:99-102`: `label: sourceLabel(pane.label)`) và ở
`spotToCard` khi build `sources` (dòng 159: `label: sourceLabel(side.label)`). Nếu xoá field
`sources`/type `CardSource`, lời gọi `sourceLabel(side.label)` bên trong khối build-`sources`
(dòng 152-162) sẽ mất theo cùng, nhưng **định nghĩa hàm `sourceLabel` (dòng 91-96) và lời gọi
tại `linkedClausesOf` (dòng 102) phải giữ lại** — đây là 1 hàm dùng chung, không phải phần dead
code.

## Kết luận xếp hạng — nên sửa theo thứ tự nào

1. **Q1 — thêm `latest` vào `FindingReviewDTO`** (backend). Đây là fix rẻ nhất, không đụng
   frontend (frontend đã đúng — Q2), không đụng SQL, chỉ thêm 1 model + gán field. Mở khoá toàn
   bộ tính năng review-latest trên trang conflict list (banner trạng thái, `conflictState`,
   `worstState`, mọi thứ ở Q3/Q4 đều đọc `spot.review.latest`; không có field này thì badge và
   review-state coi như luôn "open"). **Làm trước tiên vì mọi thứ khác phụ thuộc vào nó có dữ
   liệu thật để test.**
2. **Q5 — đổi `_latest_actions` sang lateral-join.** Vá đúng dạng lỗi double-count đã biết có
   pattern chuẩn sẵn trong repo (copy 15 dòng), rủi ro thấp, không đổi contract trả về (`latest`
   dict shape giữ nguyên). Nên làm cùng lúc hoặc ngay sau Q1 vì cùng 1 function/1 file.
3. **Q4 — badge fixes.** 4 thay đổi độc lập tương đối (tô màu theo state, không double-count,
   loại dismissed khỏi count trực tiếp, TOC truyền `collapsed`). Có thể làm sau khi Q1 cấp dữ
   liệu `review.latest` thật để test bằng mắt/bằng test case.
4. **Q3 — vẫn phải sửa khóa tra cứu, không phải bỏ.** Phần trên đúng khi nói đừng để pane PDF
   và timeline trỏ hai nút khác nhau một cách tùy tiện. Khóa lưu thẩm định trích dẫn là
   `node.id` trên URL (`clauseReview.ts` `reviewPath`). Search lưu bằng cây `'numbered'`
   (`DossierStructurePage` `answerNodes`). Trang đối soát đang tra bằng cây `structureMode`.
   Hai id khác nhau thì timeline không thấy lần đã lưu. Planner phải: tra `linkedClauses`
   trên cây `'numbered'` (cùng khóa với search); vùng tô PDF vẫn lấy từ citation/side khi
   nút numbered không có region. Không xóa phase này.
5. **Q6 — xoá `sources`/`CardSource` dead field.** Dọn dẹp nhỏ, không ảnh hưởng hành vi, làm
   cuối cùng hoặc gộp vào PR dọn code sau khi các fix hành vi (1-4) đã xong và có test.

## Câu hỏi mở

- Field `latest` mới trong `FindingReviewDTO` (Q1) nên **required khi `review` không None** hay
  `Optional`? Repo luôn set `"latest": latest` (có thể là `None` nếu review item chưa có action
  nào — `_latest_actions` chỉ set key cho item có ít nhất 1 row action). Cần xác nhận đường ống
  `latest_by_item.get(...)` trả `None` cho review item mới tạo, chưa ai action — DTO field nên
  là `FindingReviewLatestDTO | None = None`.
- Q4 mục 2 (spot neo cả node và con chỉ tính 1 lần) — bằng chứng cho thấy `Set` đã khử trùng ở
  từng node do dùng `descendant.add(id)`, nhưng chưa tìm được ví dụ cụ thể (test hoặc data thật)
  nào tái hiện đúng tình huống "1 spot có 2 side, 1 trỏ node cha 1 trỏ con của nó" để xác nhận
  100% không có edge case sót (ví dụ thứ tự visit cha/con, hoặc trường hợp node trung gian không
  có target trực tiếp nào khác). Planner nên yêu cầu 1 test case cụ thể tái hiện tình huống này
  trước khi đóng mục 2.
- Chưa tìm thấy test frontend nào cho `conflictAnchors.ts` hay `ConflictBadge` (không có file
  `*.test.ts(x)` match) — planner cần tính luôn việc viết test mới cho toàn bộ Q4, không có
  baseline để so sánh regression.
