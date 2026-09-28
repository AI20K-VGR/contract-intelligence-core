---
id: 260927-0410-ai2-visible-pair
title: "Hien cap gia va health that tren ho so OCR dang chay"
status: pending
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-27
author: user:dungskbg2004@gmail.com
decisions: [DEC-1]
phases:
  - phases/phase-1-health-probe.md
  - phases/phase-2-show-unconfirmed.md
  - phases/phase-3-live-reprocess.md
harness_version: 0.0.0-dev
harness_kit_digest: 
harness_schema_version: 1.0
---

# Plan: Hien cap gia va health that tren ho so OCR dang chay

> hs:cook ĐỌC file này làm hợp đồng. Mọi claim không hiển nhiên có anchor
> `file:line`. Tag `[ASSUMED]`/`[PRIOR]` cho claim chưa neo được.

## Tổng quan
Một hồ sơ OCR thật (một item_key, hai nguồn trong cùng snapshot bất biến) phải
hiển thị **cặp giá trị + hai citation + chú thích quan hệ CHƯA XÁC NHẬN** trên
màn AI2, đúng DEC-1. Đồng thời `/health` phải nói thật: không báo `llm=ready`
khi model cấu hình gọi không được. Scope FULL (không HOLD): 3 phase, làm hết.
Cắt YAGNI: không đụng sáu contract profile, không pgvector, không bịa source
hash, không chọn bên thắng, không bịa câu "theo Phụ lục 01".

Tại sao cần: `health()` hiện chỉ kiểm tra key có mặt (`configured()` là key
presence — `ai-service/app/llm/client.py:31-32`) nên báo `ready` cả khi model
không gọi được; và màn phân tích đang hiện *đếm* context findings nhưng KHÔNG
render `metadata.relation` = `UNCONFIRMED` (nguồn note ở
`ai-service/app/pipeline/contract_context.py:56`), nên reviewer không thấy chú
thích quan hệ.

## Quyết định đã khoá
- **DEC-1** (`docs/decisions.md:4-14`): cùng item_key trong một snapshot bất
  biến → hiện cặp + hai citation; thiếu chú dẫn chiếu Phụ lục N = chú thích
  quan hệ CHƯA XÁC NHẬN, KHÔNG xoá cặp; không bịa câu dẫn chiếu; không chọn bên
  thắng; không dùng embedding để quyết định quan hệ.
- **Scope = FULL** (user chốt): cả 3 phase.
- **Phase 2 chọn MỘT màn**: `DossierAnalysisPanel` (render bởi
  `frontend/src/pages/AnalysisCenterPage.tsx:171`) vì nó lấy context findings
  qua endpoint `/ai2-analysis` (đường đã mang sẵn `metadata`), KHÔNG đi qua
  search DTO (search DTO drop context findings — xem constraint bên dưới).

## Ràng buộc (constraint-scan)
- **Docker healthcheck chỉ nhìn `status`**: `ai2-service` healthcheck chỉ mở
  `/health` và fail khi urlopen ném (`docker-compose.yml:469-476`) —
  KHÔNG được đổi `status: "ok"` (`ai-service/app/api/main.py:695`) nếu không
  muốn container bị đánh unhealthy khi LLM offline. Trường mới chỉ nằm ở `llm`.
- **Egress mặc định trong code = false**; local compose được phép giữ
  `AI2_QUERY_EGRESS_ALLOWED` / `AI2_PROCESSING_EGRESS_ALLOWED = true`
  (`docker-compose.yml:328-329, 406-407`). Không đổi default trong code.
- **Citation gate giữ nguyên**: mục thiếu citation định vị vẫn không được coi là
  nguồn đã xác minh (`frontend/src/components/DossierAnalysisPanel.tsx:269-271`).
- **Search DTO không mang context findings**: `DossierSearchDTO`
  (`backend/.../contract_router.py:678-687`) chỉ có `hits`; `_search_dto_from_ai2`
  (`:719-745`) không đọc `context_findings`. Vì vậy `DossierReviewPage` đọc
  `searchResult.contextFindings` (`frontend/src/pages/DossierReviewPage.tsx:208`)
  thực tế luôn rỗng → KHÔNG chọn màn đó. Không mở rộng search response đợt này.

## Features
- Health nói thật trạng thái LLM: `off` (không key) / `ready` (gọi được) /
  `unreachable` (có key nhưng connection fail hoặc 404 model), `status` vẫn `ok`.
- Màn phân tích AI2 hiển thị chú thích quan hệ **CHƯA XÁC NHẬN** cho cặp
  body/annex cùng item_key (từ `metadata.relation`), kèm lý do.
- Bằng chứng reprocess live một hồ sơ thật cho thấy cặp giá trị + hai citation +
  chú thích chưa xác nhận trên màn (ghi chú thủ công, không phải hash giả).

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Health Probe | — | S |
| 2 | Show Unconfirmed | P1 | S |
| 3 | Live Reprocess | P2 | S (thủ công) |

DAG tuyến tính P1→P2→P3 (plan-graph.yaml). Ghi chú: P1 (ai-service) và P2
(frontend) chạm cây file rời nhau nên không xung đột file — cook có thể chạy
song song nếu muốn; P3 là nghiệm thu thủ công, cần P1+P2 đã xanh.

## Out of scope
- Sáu contract profile; pgvector / embedding-quyết-định-quan-hệ.
- Bịa source hash / bịa câu "theo Phụ lục 01"; chọn bên thắng.
- Mở rộng `DossierSearchDTO` để mang context findings.
- Đổi `status: "ok"` hay default egress trong code.

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; suite xanh sau mỗi phase.
      ai-service: `uv run pytest -q`; frontend: `npm test` (vitest).
- [ ] Lint/type-check/build sạch: frontend `npm run lint` + `npm run build`;
      ai-service `uv run ruff check .`.
- [ ] P1: unit test chứng minh `/health` trả `llm=unreachable` (hoặc tương
      đương, KHÔNG `ready`) khi `complete_json`/chat fail connection hoặc 404
      model, `status` vẫn `ok`; và `llm=off` khi không có API key. Không gọi mạng
      trong unit test — inject fake client.
- [ ] P2: một test UI/DTO cho thấy `relation = UNCONFIRMED` được suy ra từ
      `metadata` của context finding và hiển thị được.
- [ ] P3: ghi chú bằng chứng reprocess live một trong hai ID
      (`dos_01M3BPQFSXW68FGZJ1RPFMYXTY` hoặc `dos_01M3A9R46PBKKKPXH49T308PR1`)
      cho thấy cặp giá trị + hai citation + chú thích chưa xác nhận trên màn.

## Rollback
Mỗi phase commit riêng. Hoàn tác: `git revert <sha-range>` cho P1/P2 rồi chạy
lại `uv run pytest -q` (ai-service) / `npm run build` (frontend). P3 không đổi
code → không cần revert; chỉ bỏ file ghi chú bằng chứng nếu cần.

## Risks
| Rủi ro | K×I | Mitigation |
|---|---|---|
| Probe `/health` gọi mạng mỗi lần → chậm/timeout | M×M | Timeout ngắn; chỉ probe khi `configured()`; unit test inject fake, không chạm mạng |
| Probe rò rỉ secret vào log/JSON | L×H | Chỉ trả nhãn `off/ready/unreachable`; không đưa exception message/api_key vào response |
| Đổi nhầm `status` → container unhealthy | L×H | Test khẳng định `status=="ok"` bất kể LLM; chỉ đổi trường `llm` |
| Snapshot sqlite cũ/lệch DEC-1 | M×M | Nếu stale → rerun IDP từ canonical wire snapshot trước khi nghiệm thu (P3) |
| Frontend chưa có hạ tầng test | M×L | P2 tách hàm map thuần (không React) để test vitest môi trường node |
