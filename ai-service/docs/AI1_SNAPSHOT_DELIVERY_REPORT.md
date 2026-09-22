# Báo cáo hoàn thành: OCR Snapshot handoff cho AI2

**Người gửi:** AI1 (AI Engineer, OCR) | **Người nhận:** AI2 | **Ngày:** 2026-09-16
**Theo yêu cầu:** `AI1-OCR-SNAPSHOT-HANDOFF.md`
**Trạng thái:** Đã code xong contract `ai1.snapshot.v1` + có dossier mẫu chạy được; còn 3 khoảng trống đã liệt kê rõ, chưa chặn AI2 bắt đầu tích hợp.

> **Cập nhật (sau ngày báo cáo):** khoảng trống #1 dưới đây (`tables[]` luôn rỗng) đã được lấp —
> xem [AI1 team handoff](AI1_TEAM_HANDOFF.md) mục 4 để biết trạng thái hiện tại. Phần còn lại
> của báo cáo giữ nguyên làm biên bản tại thời điểm gửi.

## Đã hoàn thành

- Contract JSON `ai1.snapshot.v1` đúng field/kiểu theo tài liệu bàn giao gốc (document/page/line/word, `bbox_normalized`, char offset, dossier manifest).
- CLI sinh snapshot từ PDF thật: `contract-ocr snapshot --file <pdf> --document-id <id> --dossier-id <id> --role contract|annex`.
- Script sinh **dossier mẫu chạy ngay được** (1 hợp đồng TEXT_LAYER + 1 phụ lục SCANNED_OCR + dossier manifest, dữ liệu tổng hợp): `uv run python scripts/export_snapshot_demo.py`.
- JSON Schema để AI2 validate độc lập (không cần Python): `docs/ai1.snapshot.v1.schema.json`, `docs/ai1.dossier_manifest.v1.schema.json`.
- 8 test tự động, mỗi test ứng với đúng 1 tiêu chí nghiệm thu ở mục 6 tài liệu gốc (traceability, re-OCR không đè snapshot cũ, trang lỗi/trắng có warning rõ thay vì im lặng, v.v.) — toàn bộ 49 test của ai-service đang pass.
- Phản hồi kỹ thuật đầy đủ, mapping từng mục tài liệu gốc: `docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md`.

## Còn mở (không che giấu, cần AI2 xác nhận trước khi chốt)

1. `blocks[]` luôn rỗng — chưa có logic gộp heading/paragraph. Schema đã sẵn sàng để AI2 code song song phần đọc. (`tables[]` từng rỗng ở bản này — đã lấp sau ngày báo cáo, xem ghi chú cập nhật đầu file.)
2. Trang scan qua Paddle hiện chỉ có bbox **cấp dòng**, chưa có bbox cấp từ (word).
3. Trạng thái `PARTIAL` ("OCR một phần") hiện dùng 2 heuristic tạm của AI1, chưa có tín hiệu thật từ engine — cần AI2 xác nhận có chấp nhận được không.
4. Quy ước `page_image_ref.uri` (`storage://ocr/...`) và ID dòng/từ — cần đối chiếu với layout storage đã phác thảo ở `architecture.md` trước khi 2 bên code cứng vào từng chỗ.

Chi tiết đầy đủ từng điểm: xem `docs/AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md` mục 4-9.

## AI2 có thể bắt đầu ngay

```powershell
cd ai-service
uv run python scripts/export_snapshot_demo.py
```

Sinh ra dossier mẫu tại `data/generated/synthetic_demo_dossier/dossier-001/` (contract-001 + annex-001, mỗi document 1 file `ocr-run-*.json` đúng shape `ai1.snapshot.v1`, cộng `dossier_manifest.json`). Dùng để test parser/UI overlay bbox trước khi có tài liệu thật.
