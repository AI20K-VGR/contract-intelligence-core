---
phase: 5
title: "Renderer spike và dossier integration"
status: pending
plan: 261011-1654-ai2-graph-ui
created: 2026-10-11
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 5 — Renderer spike và dossier integration

## Overview

Đo renderer trên fixture đã scrub trước khi chọn thư viện. Tích hợp canvas read-only như view bổ sung; relation list/timeline vẫn là fallback đầy đủ. React Flow + ELK chỉ là ứng viên nghiên cứu (plans/261011-1654-ai2-graph-ui/research/graph-ui-research.md:71).

## Requirements

- Owner xác nhận ngân sách đo từ baseline trước khi dependency hoặc ngưỡng được chọn; chưa có số thì dừng ở list/timeline/SVG.
- Fixture đại diện hợp đồng nhiều phụ lục; lưu digest, số node/edge, browser, config, initial/layout/interaction latency và bundle delta.
- Canvas hiển thị bounded page/subgraph; luôn ghi rõ X/Y hoặc phần còn lại chưa nạp. Danh sách P4 là đường duyệt toàn bộ qua pagination.
- Read-only; không drag-connect, review mutation, legal conclusion hay persist auto-layout.
- Nhóm theo document/address; giữ hướng, loại cạnh, review state và opaque citation refs.
- Giữ outline/document/tree OCR DossierStructurePage.tsx:936-959.

## Related Code Files

**Create**
- frontend/src/components/ai2-graph/ContractGraphCanvas.tsx
- frontend/src/pages/DossierStructurePage.test.tsx
- plans/261011-1654-ai2-graph-ui/reports/renderer-spike.md

**Modify**
- frontend/src/pages/DossierStructurePage.tsx:936-959
- frontend/package.json và frontend/package-lock.json chỉ khi spike/owner chọn dependency.

## Implementation Steps

1. Chuẩn bị dữ liệu graph scrubbed và benchmark list/SVG baseline.
2. So sánh list/SVG với React Flow + ELK; ghi metrics và license của đúng release.
3. Nếu budget chưa được owner chốt hoặc không đạt, không thêm dependency; tích hợp timeline/list duy nhất.
4. Nếu canvas được chọn, pin version, giữ layout bounded, memoize và chỉ render page/subgraph hiện có.
5. Integrate view switcher bên cạnh OCR modes; graph view request chỉ khi UI flag ON.
6. Assert canvas selection và list selection trỏ cùng relation/citation IDs trong cùng page.
7. Manual check keyboard/focus/mobile/readability; ghi manual_test_anchor.py receipt.

## Tests Before (RED)

- [ ] Page tests khóa outline/document/tree hiện hành.
- [ ] Integration test chứng minh UI flag OFF không gọi Backend graph API.
- [ ] View switch không thay OCR node selection/navigation hiện có.

## Tests After (GREEN)

- [ ] cd frontend; npm test -- --run src/pages/DossierStructurePage.test.tsx src/components/ai2-graph/ai2GraphViews.test.tsx
- [ ] cd frontend; npm run lint; npm run build
- [ ] Lưu renderer spike metrics và manual receipt.

## Regression Gate

Frontend suite/build/lint phải pass; AI2 flags vẫn OFF. Không bật runtime qua UI release.

## Success Criteria

- [ ] Spike có fixture digest/size, config, latency/bundle và license; dependency chỉ thêm sau owner budget/decision.
- [ ] Canvas thể hiện rõ bounded/partial; list P4 có thể tải hết.
- [ ] OCR view modes không đổi; toggle OFF không request graph.
- [ ] Manual review confirms keyboard, mobile, focus and text alternatives.

## Risk Assessment

- **High (M×H), dense graph làm mất quan hệ hoặc treo UI:** benchmark/spike, bounded view, list fallback.
- **Medium (M×M), canvas và list khác semantics:** shared view model và identity parity test.
- **Medium (L×H), dependency license/version:** inspect exact release and pin; dependency-free rollback.
- **Medium (M×M), graph unseen beyond current page:** visible X/Y/truncation indicator and full paged list.

## Rollback

UI flag OFF restores existing OCR page. Revert canvas and selected dependency if needed; keep P4 timeline/list when API remains available. Do not change AI2 runtime flags.

