# AI1 OCR snapshot handoff

Gói này dùng để bàn giao luồng **PDF → AI1 → `ai1.snapshot.v1` JSON + ảnh trang** cho AI2, Backend và Frontend. Mã nguồn đang phát triển và chạy kiểm thử tại [`../ai-service/`](../ai-service/); bản mã nguồn tại `ai-service-source.zip` là bản đóng gói để chuyển giao, không phải nơi sửa code tiếp.

## Nội dung

- `contracts/ai1.snapshot.v1.schema.json`: JSON Schema của snapshot.
- `contracts/ai1.dossier_manifest.v1.schema.json`: JSON Schema của dossier manifest.
- `examples/dossier-001/`: 1 PDF native có bảng, 1 trang scan dùng engine giả lập để kiểm tra định dạng, hai JSON snapshot, ảnh trang và manifest. Đây là dữ liệu tổng hợp, không dùng để đo chất lượng OCR Mistral.
- `ai-service-source.zip`: `src`, `scripts`, `tests`, `configs`, `pyproject.toml`, `uv.lock`, README và tài liệu từ `ai-service`; không chứa `.env`, `.venv` hay dữ liệu người dùng.

## Chạy từ repo

```powershell
cd ai-service
uv sync --locked --python 3.12 --extra dev --extra web --extra mistral
uv run pytest -q -p no:cacheprovider
uv run python scripts/export_snapshot_demo.py --output data/generated/ai1-handoff-check
uv run contract-ocr snapshot --file <pdf> --document-id <id> --dossier-id <id> --role contract --engine none --output data/generated/snapshots
uv run python ../ai1/verify_handoff.py
```

Với PDF scan, đặt `MISTRAL_API_KEY` trong môi trường và dùng `--engine mistral`. AI1 tự chọn PyMuPDF cho trang có text layer, Mistral cho trang cần OCR. Không đưa `.env` vào gói bàn giao.

## Trường mới và ý nghĩa

`parent_snapshot_id` là `null` ở lần đầu, truyền `--parent-snapshot-id` khi chạy lại. `run_id` mặc định bằng `snapshot_id`; `created_at` là UTC. `status` tổng hợp từ các trang: tất cả lỗi → `FAILED`, có lỗi hoặc một phần → `PARTIAL`, còn lại → `SUCCESS`. `language` là `null` đến khi có bước nhận diện ngôn ngữ đáng tin cậy.

`execution` lưu ID lần chạy, ba digest SHA-256 và `replay`. CLI hash cấu hình và tham số xử lý thực tế; demo scan có `replay: true` vì dùng engine giả lập. `page_revision_id` gắn với snapshot và nội dung trang; `raw_text_digest` hash UTF-8 của `page.text`. `quality` đếm dòng và bbox; `table_coverage` ghi trạng thái detector, số bảng, còn `examined_area_ratio: null` khi chưa đo được vùng đã kiểm tra.

`bbox_source` phản ánh `geometry_provenance`; `engine_confidence` chỉ có giá trị khi engine thực sự trả confidence. Dòng không có bbox được giữ trong `page.text`, trang thành `PARTIAL` và có warning; dòng đó chưa có đối tượng `lines[]` để tham chiếu bbox. `logical_table_id` chung cho các fragment chỉ khi quyết định nối bảng là `MERGE`; trường `continuation` có thể là `UNCERTAIN` khi cần review. `Cell.line_ids` chỉ chứa dòng có text khớp chính xác và bbox giao nhau; mảng rỗng nghĩa là chưa có grounding đủ chắc. `rowspan` và `colspan` hiện mặc định 1 vì detector chưa xuất merged cell. `warnings[]` là object `{code,message,line_ids}`.

Backend nên lưu snapshot và ảnh, trả nguyên contract hoặc ánh xạ có version rõ ràng. Frontend dùng `page_image_ref`, `bbox_normalized` và `geometry_provenance` để vẽ overlay; tránh coi bbox `CLAIMED` là tọa độ đo chính xác. Chi tiết luồng và giới hạn hiện tại: [`../ai-service/docs/AI1_TEAM_HANDOFF.md`](../ai-service/docs/AI1_TEAM_HANDOFF.md).
