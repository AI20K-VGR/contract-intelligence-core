---
phase: 4
title: "Accessible timeline and paged relation list"
status: completed
plan: 261011-1654-ai2-graph-ui
created: 2026-10-11
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 4 — Accessible timeline and paged relation list

## Overview

Tạo timeline processing và relation list/inspector dùng chung Backend DTO. List là đường thao tác accessible hoàn chỉnh và tự tải cursor tiếp; trang đầu không được gọi là toàn graph.

## Requirements

- Tách “Luồng AI2” khỏi “Quan hệ điều khoản”; không trộn stage thành node pháp lý.
- Timeline chỉ dùng trace có timestamp/status/count/reason từ backend. Trace-unavailable, running, interrupted/unknown, failed và success khác nhau.
- Relation row thể hiện document/address hai đầu, kind/label, direction, review badge và opaque citation refs; không render excerpt/span từ graph API.
- Có Load more/Next page, số đã tải/tổng nếu API có; status complete chỉ khi không còn cursor và count bằng total. Khi còn trang, nói rõ danh sách chưa tải hết.
- Append page theo stable relation identity, chống duplicate, giữ selection/citation refs khi tải tiếp.
- Không thêm filter client-side có thể khiến page đầu trông như toàn bộ kết quả; nếu filter theo server được thêm, cursor phải gắn filter.
- Keyboard Tab/Enter/Escape, focus rõ, accessible names; màu không phải tín hiệu duy nhất; usable tại 320 CSS px.

## Related Code Files

**Create**
- frontend/src/components/ai2-graph/ProcessingTimeline.tsx
- frontend/src/components/ai2-graph/RelationList.tsx
- frontend/src/components/ai2-graph/RelationInspector.tsx
- frontend/src/components/ai2-graph/contractGraphViewModel.ts
- frontend/src/components/ai2-graph/ai2GraphViews.test.tsx

**Modify**
- None. P5 sở hữu page integration để không dùng chung page với renderer.

## Implementation Steps

1. Viết status matrix tests trước khi render.
2. Build timeline chỉ từ trace; không suy success từ thứ tự stage hoặc zero count.
3. Build list có cursor continuation, stable ordering, append/dedupe và progress text “đã tải X/Y”.
4. Inspector gọi citation navigation Backend; không tự gọi AI2 hoặc đưa text vào DTO graph.
5. Thêm keyboard tests cho row/cạnh và cả hai evidence actions.
6. Test 3+ pages, retry cùng cursor, cursor hết hạn, page lỗi và tổng count không khớp.
7. Ở mobile, xếp source/target thành 2 block đọc được; không cần canvas.

## Tests Before (RED)

- [ ] OFF/skipped vs empty-ready; persist-failed vs zero; missing trace vs interrupted trace.
- [ ] Load more nối trang mà không duplicate; còn cursor luôn hiện incomplete/loading state.
- [ ] Ba trang không bỏ/mất item; complete chỉ sau trang cuối/count khớp.
- [ ] Keyboard đạt từng relation và hai citation actions; visible focus.
- [ ] At 320 CSS px no horizontal overflow.

## Tests After (GREEN)

- [ ] cd frontend; npm test -- --run src/components/ai2-graph/ai2GraphViews.test.tsx
- [ ] cd frontend; npm run lint
- [ ] Component/integration test với giả lập Backend pages >2 và status/error matrix.

## Regression Gate

cd frontend; npm test phải qua trước P5.

## Success Criteria

- [ ] List hiển thị chính xác loaded/total/remaining; không gọi full graph đến khi hết cursor.
- [ ] Select row/citation action keyboard và pointer cho cùng identity.
- [ ] Từng status có distinct text/icon; không gọi unknown là “không có quan hệ”.
- [ ] Timeline chỉ hiển thị persisted stage events; worker crash không hiện success.

## Risk Assessment

- **High (M×H), first page mistaken for full result:** explicit cursor/loading/completion state; three-page no-omission test.
- **Medium (M×M), status colors confuse users:** icon + text + pattern; keyboard/screen reader check.
- **Medium (M×M), timeline wording sounds like legal outcome:** labels identify processing stage vs legal relation, badge says “AI2 đề xuất / cần review”.

## Rollback

Hide components behind UI flag. OCR modes and existing citation actions remain unchanged.

