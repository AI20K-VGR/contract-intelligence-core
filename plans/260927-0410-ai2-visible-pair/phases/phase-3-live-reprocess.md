# Phase 3 — Live Reprocess: nghiệm thu thủ công trên hồ sơ OCR thật

## Overview
Replay snapshot đã lưu qua AI2 đang chạy (egress bật) và xác nhận trên màn phân
tích: **cặp giá trị + hai citation + chú thích quan hệ CHƯA XÁC NHẬN**. Thành
công = ghi chú bằng chứng viết tay, KHÔNG phải unit test xanh, KHÔNG bịa hash.

## Requirements
- Không viết product code tạo bằng chứng giả.
- Dùng một trong hai ID thật:
  `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` hoặc `dos_01M3A9R46PBKKKPXH49T308PR1`.
- Cần P1 (health thật) và P2 (render UNCONFIRMED) đã merge/xanh.

## Related Code Files
Create (chỉ tài liệu bằng chứng, không phải code):
- `plans/260927-0410-ai2-visible-pair/artifacts/phase-3-live-reprocess-evidence.md`.

Modify: none.

## Implementation Steps (thủ công)
1. **Dựng stack** với egress local bật (mặc định compose đã `true` —
   `docker-compose.yml:328-329, 406-407`):
   `docker compose up -d ai2-service backend backend-db kafka minio` (kèm phụ
   thuộc). Xác nhận `AI2_QUERY_EGRESS_ALLOWED` / `AI2_PROCESSING_EGRESS_ALLOWED`
   = `true` trong môi trường chạy.
2. **Kiểm tra health thật (P1)**: `GET http://localhost:8002/health` →
   `status=="ok"` và `llm` phản ánh đúng (`ready` nếu model gọi được; nếu
   `unreachable`/`off` thì sửa cấu hình `AI2_LLM_*` trước khi tiếp).
3. **Replay snapshot** của một trong hai `dos_...` qua đường AI2 processing đang
   chạy (POST reprocess/xử-lý theo đường backend→AI2 hiện có). KHÔNG bịa
   `snapshot_id`/`digest`/`source hash` — dùng đúng snapshot đã lưu.
   - **Nếu snapshot trong sqlite cũ/lệch** (không ra cặp theo DEC-1): rerun IDP
     từ **canonical wire snapshot** rồi replay lại, không vá tay dữ liệu.
4. **Mở màn phân tích**: `AnalysisCenterPage` cho `dossierId` tương ứng
   (`frontend/src/pages/AnalysisCenterPage.tsx:171` → `DossierAnalysisPanel`).
5. **Xác nhận trên màn** (đúng DEC-1):
   - Hai giá trị tiền của cùng item_key hiển thị thành **cặp**.
   - **Hai citation** (mỗi nguồn một citation, định vị được).
   - **Chú thích quan hệ CHƯA XÁC NHẬN** (từ P2) hiện kèm lý do; cặp KHÔNG bị
     xoá dù thiếu chú dẫn chiếu Phụ lục.
6. **Ghi bằng chứng** vào file artifacts: ID hồ sơ đã dùng, thời điểm, giá trị
   `/health` quan sát được, ảnh chụp/mô tả màn (cặp + 2 citation + note), và
   liệu có phải rerun IDP không. Nêu rõ đây là quan sát live, không phải hash.

## Success Criteria
- [ ] File `artifacts/phase-3-live-reprocess-evidence.md` tồn tại, ghi rõ ID
      thật đã dùng và quan sát trên màn.
- [ ] Ghi chú cho thấy: cặp giá trị + hai citation + chú thích CHƯA XÁC NHẬN.
- [ ] Ghi lại giá trị `/health` (`status=="ok"`, `llm=...`) tại thời điểm chạy.
- [ ] Không có source hash bịa; nếu rerun IDP thì nêu rõ lý do stale.

## Risk Assessment
| Rủi ro | K×I | Mitigation |
|---|---|---|
| Snapshot sqlite stale → không ra cặp | M×M | Rerun IDP từ canonical wire snapshot, không vá tay |
| Egress tắt ở môi trường chạy → LLM off | M×M | Xác nhận cờ egress local `true` trước; đọc `/health` (P1) |
| Cám dỗ "chứng minh" bằng hash/dữ liệu giả | L×H | Cấm bịa; thành công là ghi chú quan sát live, không phải test giả |
| Nhầm màn (search thay vì analysis) | L×M | Bằng chứng phải từ `AnalysisCenterPage`/`DossierAnalysisPanel` (P2) |

## Post
- `verification-P3.json`
