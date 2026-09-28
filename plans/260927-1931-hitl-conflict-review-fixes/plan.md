---
id: 260927-1931-hitl-conflict-review-fixes
title: "Sua review.latest va trang thai xung dot tren cay"
status: completed
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-27
author: user:dungskbg2004@gmail.com
decisions: []
phases:
  - phases/phase-1-list-latest.md
  - phases/phase-2-numbered-timeline.md
  - phases/phase-3-badge-counts.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: Sua review.latest va trang thai xung dot tren cay

> hs:cook ĐỌC file này làm hợp đồng. Mọi claim không hiển nhiên có anchor
> `file:line`. Tag `[ASSUMED]`/`[PRIOR]` lên claim chưa xác minh trực tiếp.

## Tổng quan
Sửa mọi review finding đã xác nhận trên mặt phẳng đối soát xung đột HITL (quyết
định HOLD / Full — chỉ sửa lỗi đã xác nhận, không thêm gì). Ba lỗi độc lập nhưng
cùng một hợp đồng dữ liệu `review.latest` + một hàm đếm badge:

1. **List Latest (backend):** `GET /conflicts` trả `review` nhưng rớt `latest` —
   `FindingReviewDTO.from_row` chỉ serialize `item_id/status/current_version`
   (`finding_dtos.py:77-84`), nên frontend (đã sẵn sàng đọc `review.latest`,
   `structure.ts:542-556`) luôn coi xung đột là `open`. Kèm sửa double-count
   `action_count` do `outerjoin(AppUserORM, or_(...))` ở `_latest_actions`
   (`repository_impl.py:217-223`).
2. **Numbered Timeline (frontend):** search lưu thẩm định trích dẫn theo `node.id`
   của cây `'numbered'` (`DossierStructurePage.tsx:202-205`), còn `ClauseConflictPage`
   tra `linkedClauses` theo cây `structureMode` (`ClauseConflictPage.tsx:558-568`) →
   id lệch → timeline không thấy lần đã lưu ở search.
3. **Badge Counts (frontend):** badge nút cha đang gấp hard-code màu amber bất kể
   trạng thái con (`StructureViewShell.tsx:222-223`); số trực tiếp đếm cả spot đã
   dismissed (`:256-259`); TOC không truyền `collapsed` (`StructureDocument.tsx:229`);
   dọn field `card.sources`/`CardSource` write-only (`ClauseConflictPage.tsx:55-59`).

Scope cắt theo YAGNI: không đụng OCR/grounding/`clause_compare.py`, không chọn bên
đúng pháp lý, không sinh câu tham chiếu, không sửa doc kiến trúc.

## Quyết định đã khoá
- **HOLD / Full**: sửa MỌI review finding đã xác nhận, không hơn.
- **Q3 KHÔNG bỏ**: research xếp hạng gợi ý "đừng fix Q3" nhưng phần chốt cuối
  (research §Kết luận mục 4) ghi đè — phải sửa khóa tra cứu timeline, không xóa
  Phase 2.
- **Không tái dùng `ClauseReviewEntryDTO`** cho `latest`: field required của nó
  (`revision_number`, `review_action_id`, `base_version` — `review_dtos.py:166-181`)
  không khớp dict `_latest_actions` sinh ra → thêm model mới nhỏ nhất.
- **PDF highlight giữ nguyên nguồn**: chỉ khóa tra cứu (review-target node) đổi sang
  cây `'numbered'`; vùng tô trên PDF vẫn lấy từ cây `structureMode`/citation region.
- Giữ 3 phase như đã tách; chạy tuần tự P1→P2→P3.

## Ràng buộc (constraint-scan)
Kết luận constraint-scan (main đã chạy, không mở lại):
- Không zone mới. Thay đổi nằm trong `backend/src` và `frontend/src` hiện có.
- Không đổi stage-policy hay harness schema.
- **ADR: skip** — chỉ mở rộng một response field sẵn có; không store mới, không
  ranh giới auth, không vendor.
- **OBSERVED**: `FindingDTO.from_row` rớt `latest`; `from_row` của action=confirm chỉ
  serialize `item_id`, `status`, `current_version` (`finding_dtos.py:80-84`).

## Features
- conflict-list-latest: danh sách xung đột trả lần thẩm định gần nhất (hành động, ghi chú, tên, email, thời điểm, số lần).
- tree-state: badge và banner trên cây đổi theo lần thẩm định đó, không còn kẹt ở "chưa thẩm định".
- citation-timeline: trang đối soát hiện lịch sử thẩm định trích dẫn đúng điều khoản đã lưu ở search.
- collapsed-color: badge khi gấp nút cha có màu đúng trạng thái bên trong.
- single-count: một xung đột neo cả cha và con chỉ đếm một lần trên nút đó.
- live-count: số trên badge không gồm xung đột đã thẩm định là sai lệch.
- toc-marker: mục lục văn bản hiện dấu khi xung đột nằm ở mục con đang gấp.
- honest-action-count: số lần thẩm định không phồng vì join người dùng.
- no-dead-sources: thẻ đối soát không còn khối nguồn tính ra rồi không hiện.

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | List Latest | — | S (2 file backend + test) |
| 2 | Numbered Timeline | P1 | M (frontend, 1-2 file + test) |
| 3 | Badge Counts | P2 | M (4 file frontend + test) |

Tuần tự P1→P2→P3. P1 cấp dữ liệu `review.latest` thật để P2/P3 test đúng trạng
thái. P2 và P3 cùng chạm `ClauseConflictPage.tsx` (P2: cây numbered cho
linkedClauses; P3: xóa `card.sources`) → phải tuần tự, không song song; sửa ở vùng
tách biệt (xem Risks).

## Out of scope
- Pipeline OCR, grounding, `clause_compare.py`.
- Chọn bên "đúng" pháp lý; sinh/đặt câu tham chiếu.
- Sửa `docs/system-architecture.md`; JWT audience.
- Commit/push (planner không commit; cook lo commit theo phase).
- Không sinh hash mới trong test (dùng dữ liệu/hàm thật).

## Red-team disposition
Báo cáo: `reports/from-code-reviewer-to-planner-red-team-failure-plan-review-report.md`.

| Finding | Quyết định | Chỗ đã sửa |
|---|---|---|
| F1 đếm đôi cha+con | Accept | `phase-3`: `below` bỏ id đang neo trực tiếp; test `below === 0` khi cha cũng chứa spot |
| F2 action_count | Accept | `phase-1`: pytest không được nhận là chứng minh SQL distinct; giữ `[ASSUMED]` |
| F3 thiếu tsc | Accept | Gate P2 và P3 thêm `npx tsc --noEmit -p tsconfig.app.json` |
| F4 side null | Accept | `phase-2`: không gọi `reviewTargetNode` khi `side` null |
| F5 research vs test có sẵn | Reject | Cook đọc phase-3, phase đã trỏ `conflict-anchors.test.ts` |
| F6 fallback freeform | Accept | Acceptance: timeline chỉ hứa khi cây numbered giải ra nút |
| F7 số dòng dịch sau P2 | Reject | Cook bám tên symbol, không bám số dòng cũ |

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; regression gate của phase xanh trước khi commit.
- [ ] `GET /conflicts` JSON có `review.latest` với đủ key `action, comment,
      reviewer_id, reviewer_name, reviewer_email, reviewed_at, action_count`.
- [ ] Sau một `confirm` đã lưu, cây/banner rời trạng thái `open` (không còn kẹt
      "chưa thẩm định").
- [ ] Trang đối soát: timeline tìm thấy lần thẩm định đã lưu ở search khi cây numbered
      giải ra được nút. Hồ sơ `freeform`/`tables` mà cây numbered không có nút đó thì
      timeline không bịa khóa mới; vùng tô PDF vẫn theo `structureMode`.
- [ ] Badge: màu nút cha gấp theo trạng thái nặng nhất của descendant chưa dismissed;
      spot neo cả cha+con đếm 1 lần; số trực tiếp loại dismissed; TOC hiện dấu khi
      xung đột nằm ở mục con đang gấp.
- [ ] `action_count` không phồng vì join người dùng.
- [ ] Test cũ vẫn xanh: `conflict-anchors.test.ts`, `conflict-cite.test.ts`,
      `test_conflict_router.py`.

## Rollback
Mỗi phase commit riêng. Hoàn tác: `git revert <sha phase>` rồi chạy lại regression
gate của phase đó. P1 (backend) độc lập frontend; revert P2/P3 không ảnh hưởng P1.
Revert P3 không đụng khóa tra cứu của P2 (vùng code tách biệt trong cùng file).

## Risks
- **Shared file `ClauseConflictPage.tsx` (P2+P3)** — L: trung bình, I: trung bình.
  Mitigation: P2 sửa vùng `trees`/`linkedClausesOf` (`:558-568`, `:98-111`); P3 chỉ
  xóa `CardSource`/`sources` (`:55-59`, `:152-162`, `:190`) + không đụng vùng P2.
  Chạy tuần tự, cook rebase P3 trên P2.
- **Tách cây numbered cho linkedClauses (P2)** — rủi ro pane PDF và review-target trỏ
  node khác nhau (research §3). Mitigation: chỉ đổi khóa tra cứu (node.id), giữ
  regions từ `structureMode`; test khóa đúng behavior; với hồ sơ `structureMode`
  đã là `'numbered'` thì no-op.
- **Double-count `action_count` (P1)** — `or_` khớp >1 AppUser nhân dòng. Mitigation:
  copy pattern lateral `.limit(1).lateral()` đã kiểm chứng ở review BC
  (`review/.../repository_impl.py:388-401`); nhớ thêm import `true`.
- **Không có baseline test frontend cho badge màu/TOC** (research §Câu hỏi mở) —
  Mitigation: P3 mở rộng `conflict-anchors.test.ts` phủ belowState + đếm loại
  dismissed trước khi implement.
