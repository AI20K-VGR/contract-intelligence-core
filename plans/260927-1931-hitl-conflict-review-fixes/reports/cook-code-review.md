# Code Review — cook plan 260927-1931-hitl-conflict-review-fixes

- **Ngày:** 2026-09-28
- **Người review:** hs:code-reviewer (READ ONLY, không sửa, không commit)
- **Phạm vi:** đúng 10 file của 3 phase (P1 backend `review.latest`, P2 numbered timeline, P3 badge counts)
- **Commit cook:** `7e43e19` (P1), `570a338` (P2), `86d5608` (P3)

## Phán quyết: PASS_WITH_RISK

Toàn bộ code của plan đúng, cả ba tiêu chí nghiệm thu đều giữ, test thật xanh.
Rủi ro **duy nhất** là cổng `tsc` cấp repo hiện **đỏ** vì WIP ai2-integration ngoài
phạm vi (không phải lỗi của file review) — chi tiết ở mục Rủi ro Medium.

---

## Chứng cứ chạy thật

| Lệnh | Kết quả |
|---|---|
| `uv run pytest tests/unit/test_conflict_router.py -q` | **8 passed** (exit 0) |
| `npx vitest run tests/conflict-anchors.test.ts tests/conflict-review-target.test.ts tests/conflict-cite.test.ts` | **16 passed** (exit 0) |
| `npx tsc --noEmit -p tsconfig.app.json` | **14 errors, exit 2** — TẤT CẢ ở `src/components/StructureSearchResult.tsx` (ngoài scope) |

---

## Đối chiếu tiêu chí nghiệm thu

### AC1 — DTO `GET /conflicts` giữ `review.latest` đủ 7 key — ĐẠT
- `FindingReviewLatestDTO` khai đúng 7 field `extra="forbid"`: `finding_dtos.py:24-33`.
- Gắn vào `FindingReviewDTO.latest`: `finding_dtos.py:42`.
- `from_row` chuyển `latest` qua an toàn (dict → model, else `None`): `finding_dtos.py:90-100`.
- Xuất khẩu cập nhật: `finding_dtos.py:121`.
- Test khoá hợp đồng JSON: endpoint assert `latest == _LATEST_RAW` (đủ 7 key)
  `test_conflict_router.py:177-192`; from_row pass-through `:152-164`; `None` khi
  review chưa có action `:166-175`. Tất cả xanh.

### AC2 — Tra cứu review dùng cây numbered; regions PDF giữ structureMode; side null không gọi reviewTargetNode — ĐẠT
- `reviewTargetNode` tra trên `numberedNodes` (cùng khóa search lưu), trả `null` khi
  ngoài cây: `reviewTarget.ts:25-33`, `:35-45`.
- `numberedTrees` build `buildStructureTree(lines, 'numbered')` song song `trees`
  (structureMode): `ClauseConflictPage.tsx:559-568`; feed vào `locatePanes`
  `:571-579`.
- **regions vẫn từ structureMode**: `linkPane` lấy `clause`/`regions` từ `nodes`
  (structureMode) `ClauseConflictPage.tsx:208-218`; `reviewTarget` chỉ dùng cho khóa
  tra cứu `:212`. Tương tự `paneForSide:345-355`.
- `linkedClausesOf` feed `reviewNode ?? clause` + ordinal tương ứng vào `getClauseReview`:
  `ClauseConflictPage.tsx:92-104`.
- **side null KHÔNG gọi reviewTargetNode**: `linkPane` dùng `side ? reviewTargetNode(...) : null`
  `ClauseConflictPage.tsx:212`; `paneForSide` return sớm khi `!side` trước khi tới lời gọi
  `:327-344` (lời gọi ở `:348`).
- Test khoá: lấy node cây numbered `conflict-review-target.test.ts:61-71`; ordinal trên
  cây numbered `:73-82`; `null` khi ngoài cây `:85-95`. Xanh. `conflict-cite.test.ts`
  không hồi quy (regions) — 4 passed.

### AC3 — Đếm 1 lần (below loại id trực tiếp), directCount loại dismissed, badge gấp dùng belowState — ĐẠT
- `visit()` xóa mọi id trực tiếp khỏi tập hậu duệ trước khi ghi `below`:
  `conflictAnchors.ts:136` (`descendant.delete(spot.id)`), ghi marker `:142-147`.
- `directCount` loại dismissed: `conflictAnchors.ts:62-64`.
- `belowState` = trạng thái nặng nhất (rank thấp nhất) trong hậu duệ chưa dismissed;
  hậu duệ chỉ nạp spot chưa dismissed: `conflictAnchors.ts:138-141`, `:149-151`.
- Badge gấp (nhánh `spots.length === 0`) tô theo `toneOf(marker.belowState)`:
  `StructureViewShell.tsx:230-240` (belowState ở `:234`); số trực tiếp + padding dùng
  `directCount`: `:242`, `:257-258`, `:263`.
- TOC truyền `collapsed`: `StructureDocument.tsx:228-233`; badge thân văn bản giữ
  nguyên (không `collapsed`): `:355-356`.
- Dead code đã dọn: `CardSource`/`MARKS`/`sources` không còn trong file; `ReviewCard`
  không có `sources` (`ClauseConflictPage.tsx:56-66`); `sourceLabel` còn nguyên `:85-90`.
- Test khoá: below−direct−trạng thái `conflict-anchors.test.ts:150-154`; belowState theo
  con `:161-165`; directCount loại dismissed `:167-177`; đếm 1 lần cha+con
  `:178-193`; case anh em `below===1` `:196-219`. 9 passed.

---

## Trace logic thủ công (khớp test)
- **Cha trực tiếp neo + con neo (2 side):** con ghi direct + trả id lên; cha xóa id đó
  khỏi hậu duệ → `below===0`, hiện direct trên cả cha lẫn con, không cộng `+1` trùng id.
  Đúng `conflictAnchors.ts:136`.
- **Cha chỉ là tổ tiên (không neo trực tiếp):** không xóa gì → hậu duệ gộp id duy nhất →
  `below===1` (case anh em / same-file). Đúng.
- **belowState:** map hậu duệ chỉ chứa chưa-dismissed, chọn rank thấp nhất
  (`open` < `reviewed`); rỗng → `'dismissed'` (không dùng vì badge gấp chỉ render khi
  `below>0`). Đúng.

## Backend lateral join (action_count)
- `_latest_actions` thay `outerjoin(AppUserORM, or_(...))` bằng subquery
  `.limit(1).lateral()` rồi `.outerjoin(reviewer, true())`: `repository_impl.py:207-234`;
  import `true` có mặt `:8`. Sao đúng pattern đã kiểm ở review BC
  (`review/.../repository_impl.py:387-407`).
- `func.count(...).over(partition_by=review_item_id)` giữ nguyên `:224-226`; vòng lặp
  ghi đè theo `order_by created_at ASC` → phần tử cuối (mới nhất) thắng: `:236-247`.
  **[ASSUMED]** hành vi distinct/window-count trên DB thật — đúng như plan tuyên bố, KHÔNG
  yêu cầu integration test SQL (theo chỉ thị review).

---

## Rủi ro

### Medium — Cổng `tsc` cấp repo đang đỏ (nguyên nhân NGOÀI phạm vi plan)
`npx tsc --noEmit -p tsconfig.app.json` báo 14 lỗi, **toàn bộ** ở
`src/components/StructureSearchResult.tsx` (`:4`, `:46`, `:48`, `:71`, `:101`, `:155`,
`:157`, `:171`, `:174`, `:191`, `:203`) — do WIP ai2-integration chưa commit ở
`src/api/structure.ts` (đang `M` trong working tree), làm lệch kiểu `Ai2SearchHit` /
`DossierSearchState`. File này KHÔNG thuộc 10 file review và KHÔNG bị 3 commit cook đụng
(lần sửa cuối `2f6052c`, trước plan). **Không có lỗi tsc nào trỏ vào file của plan** →
code plan sạch kiểu.

Tác động: cổng nghiệm thu P2/P3 (`tsc clean`) không thể tái lập xanh ở cấp repo cho tới
khi WIP `structure.ts`/`StructureSearchResult.tsx` được sửa. Đây là nợ của lane khác.

Khuyến nghị: chủ WIP ai2-integration sửa `StructureSearchResult.tsx` hợp với
`structure.ts` mới, HOẶC xác nhận cổng tsc của plan này chạy trên phạm vi tách biệt.
Không đề xuất chỉnh code plan.

### Low — pytestmark asyncio dính test đồng bộ
`pytestmark = pytest.mark.asyncio` (`test_conflict_router.py:20`) áp lên 2 test đồng bộ
`test_from_row_passes_latest_through` (`:152`) và `test_from_row_latest_none...` (`:166`)
→ cảnh báo PytestWarning. Test vẫn chạy và xanh. Đề xuất: tách 2 test đồng bộ ra lớp
không mark, hoặc bỏ mark cho chúng. Không chặn.

---

## Ghi chú độ phức tạp (không chặn merge)
- `directCount`/`worstState`/`belowState` là helper thuần, tối giản, tái dùng bảng
  `STATE_RANK`/`toneOf` sẵn có — không thấy tầng trừu tượng thừa.
- `reviewTarget.ts` tách hàm thuần đúng mức, tránh import vòng bằng cách chỉ dùng
  `clauseOrdinal` (type-only chain). Hợp lý.

## Câu hỏi mở
- Cổng tsc của plan lúc commit `570a338`/`86d5608` có xanh không, hay working tree khi đó
  chưa có WIP `structure.ts`? Không xác minh được từ trạng thái hiện tại; không ảnh hưởng
  tính đúng của code plan.

## Không làm (theo chỉ thị)
- Không chọn bên đúng pháp lý.
- Không yêu cầu integration test SQL cho `action_count` (đã `[ASSUMED]`).
