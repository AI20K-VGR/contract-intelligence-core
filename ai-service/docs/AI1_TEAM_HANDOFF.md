# AI1 handoff cho Backend và Frontend

**Mục đích:** thống nhất đường đi của PDF và dữ liệu OCR khi tích hợp `ai-service` vào sản phẩm. Tài liệu này mô tả code hiện tại và đề xuất ranh giới tích hợp; không tuyên bố Backend đã gọi AI1 trong runtime.

> **Đã chốt (2026-09-22):** AI2 đã đánh giá độc lập `ai1.result.v0.1` (envelope hiện tại của Backend) so với `ai1.snapshot.v1` và kết luận **`ai1.snapshot.v1` là canonical contract chính thức giữa AI1–AI2**; `ai1.result.v0.1` chỉ còn là compatibility adapter tạm thời. AI1 đồng ý — xem phản hồi đầy đủ, đối chiếu từng field AI2 yêu cầu với schema thật, ở [AI1_RESPONSE_TO_AI2_SNAPSHOT_DECISION.md](AI1_RESPONSE_TO_AI2_SNAPSHOT_DECISION.md).

## 1. Chọn một contract

Contract AI1 bàn giao là **`ai1.snapshot.v1`**, một snapshot cho **một PDF**. Nguồn xác thực là [model Pydantic](../src/contract_ocr/domain/snapshot.py); [JSON Schema](ai1.snapshot.v1.schema.json) là bản xuất cho Backend/Frontend kiểm tra cấu trúc, và [dossier manifest schema](ai1.dossier_manifest.v1.schema.json) mô tả danh sách PDF thuộc hồ sơ. Khi đổi field, cập nhật cả model, schema, ví dụ và test trong cùng thay đổi.

JSON ở Backend hiện tại (`machine.schema_version: "0.1"`, `machine.pages[]`, `effective`, `review`) là **một contract khác** do `backend/app/worker.py` tạo từ pipeline OCR riêng. Không đổi tên file hoặc gán `schema_version = "ai1.snapshot.v1"` cho JSON đó. Backend cần adapter có kiểm thử nếu muốn dùng snapshot AI1 thay pipeline hiện tại.

## 2. Luồng PDF vào và dữ liệu ra

```text
Frontend --upload PDF--> Backend --PDF + dossier_id/document_id/role--> AI1
Backend <--snapshot JSON + ảnh trang------------------------------- AI1
Frontend <--job/result + URL ảnh + dữ liệu review---------------- Backend
```

1. **Backend** nhận upload, cấp `dossier_id` và `document_id`, xác định `document_role` (`contract` hoặc `annex`), lưu PDF nguồn, tạo job và quản lý retry. AI1 không là nơi lưu hồ sơ hoặc trạng thái review.
2. **AI1** kiểm tra từng trang: text layer dùng PyMuPDF; trang scan hoặc mixed chuyển OCR khi có engine. `ProcessDocument` tạo dữ liệu OCR nội bộ; `BuildSnapshot` tạo `DocumentSnapshot` với text, tọa độ, bảng và cấu trúc.
3. **Backend** nhận đúng snapshot của lần chạy, xác thực version và schema, kiểm tra `source_digest` với PDF nguồn, lưu snapshot bất biến theo `snapshot_id`, rồi tạo kết quả nghiệp vụ/review bằng adapter. Retry tạo snapshot mới; không ghi đè bản cũ.
4. **Frontend** gọi Backend để lấy trạng thái job, snapshot/kết quả, và URL ảnh trang. Frontend không gọi trực tiếp AI1 hoặc tự đọc đường dẫn file nội bộ.

**Hiện đã chạy được:** `contract-ocr snapshot` nhận một PDF local và ghi JSON/PNG. **Chưa có:** Backend gọi pipeline AI1, endpoint production trả `ai1.snapshot.v1`, queue/callback AI1, hoặc adapter chuyển snapshot sang `backend` result `0.1`. `/api/ocr` trên cổng 8000 hiện chỉ trả bản tóm tắt text/trang; `/api/ai2/analyze` là demo AI2, không phải endpoint handoff này.

## 3. Input AI1 cần từ Backend

| Trường | Quy ước |
| --- | --- |
| PDF | Byte stream hoặc đường dẫn file mà AI1 đọc được; giữ nguyên PDF để `source_digest` có thể kiểm tra. |
| `dossier_id` | ID Backend cấp, dùng chung cho hợp đồng và phụ lục. |
| `document_id` | ID ổn định của PDF trong hồ sơ. |
| `document_role` | `contract` hoặc `annex`; không suy đoán từ tên file. |
| `filename` | Tên hiển thị; không dùng làm khóa lưu trữ. |
| `snapshot_id` | ID duy nhất cho mỗi lần OCR, kể cả retry; Backend có thể cấp hoặc AI1 sinh. |
| OCR engine | Chính sách chọn engine cần chốt theo môi trường và độ nhạy tài liệu. Không mặc định đẩy PDF sang API ngoài. |

CLI hiện hỗ trợ `--engine none|mistral` (Paddle/DeepSeek — cả bản local lẫn API — đã bị gỡ khỏi codebase, không dùng nữa). Engine `mistral` (Mistral OCR Document AI, `mistral-ocr-4`) đọc trực tiếp `page.blocks` của Mistral (bbox/confidence THẬT theo từng block, không suy diễn) và tự dựng `tables[]` từ pipe-table markdown Mistral trả về — không qua detector pixel bảng có đường kẻ. OpenAI/Gemini vẫn chỉ có trong **demo web OCR**, chưa nối vào lệnh `snapshot`.

CLI **không** tự nạp `.env` như `scripts/serve_backend.py` (demo web) làm — chạy `contract-ocr snapshot --engine mistral` cần `MISTRAL_API_KEY` đã có sẵn trong biến môi trường của phiên shell đang chạy (ví dụ PowerShell: `$env:MISTRAL_API_KEY = "..."` trước khi gọi `uv run contract-ocr ...`, hoặc nạp file `.env` bằng tay). Cần cài thêm `--extra mistral` (`uv sync --locked --python 3.12 --extra dev --extra mistral`) để có SDK `mistralai`.

## 4. Output AI1 cam kết

Một file snapshot có `schema_version: "ai1.snapshot.v1"`, `snapshot_id`, `source_digest: "sha256:<hex>"`, ID hồ sơ/tài liệu, engine, `page_count`, `pages[]`, `nodes[]`, `table_continuity[]`.

| Đường JSON | Backend/Frontend dùng để làm gì |
| --- | --- |
| `pages[].status`, `warnings`, `error` | Hiển thị SUCCESS/PARTIAL/FAILED theo trang; giữ cả trang lỗi trong kết quả. |
| `pages[].text`, `lines[]`, `words[]` | Text theo thứ tự đọc, ID và offset để gắn citation; word có thể rỗng khi engine chỉ trả geometry cấp dòng. |
| `pages[].page_image_ref` | Kích thước PNG đã render và URI ảnh để vẽ overlay. URI `storage://ocr/...` hiện là tham chiếu trong gói local, **chưa** là URL HTTP cho browser. Backend phải ánh xạ URI sang ảnh đã lưu và cấp URL có quyền truy cập phù hợp. |
| `bbox_normalized` | `[x0,y0,x1,y1]` trong khoảng 0–1, gốc trên trái của ảnh trang đã render. Frontend nhân `x` với chiều rộng và `y` với chiều cao ảnh đang hiển thị. |
| `geometry_provenance` | `MEASURED`, `DERIVED`, `CLAIMED`; Backend không dùng `CLAIMED` làm vị trí trích dẫn chính xác. |
| `pages[].table_status`, `tables[].rows[].cells[]` | Phân biệt `NOT_CHECKED`, `NOT_PRESENT`, `DETECTED`; giữ text và bbox từng ô khi có. |
| `nodes[]` | Cây ARTICLE/CLAUSE/POINT/UNMARKED, liên kết tới `pages[].lines[]` bằng `line_ids`. |
| `table_continuity[]` | Quyết định nối bảng giữa trang (`MERGE`, `SPLIT`, `NEEDS_REVIEW`); chỉ là link, chưa gộp vật lý các row. |

`blocks[]` hiện chưa được dựng. Bảng scan không viền vẫn có thể bị bỏ sót với engine ngoài `mistral` (ví dụ nếu sau này nối OpenAI/Gemini vào lệnh `snapshot` — detector pixel dự phòng chỉ bắt bảng có đường kẻ); riêng engine `mistral` không có giới hạn này vì đọc bảng từ markdown Mistral tự phân đoạn, không cần đường kẻ. `table_continuity[]` (nối bảng qua trang) đã có 3 tầng quyết định (hard guard → rule score → agent DeepSeek tùy chọn cho vùng mơ hồ, tắt mặc định qua `BuildSnapshot(table_continuity_agent=True)`), giống thiết kế backend/app/table_continuity.py. `PARTIAL` vẫn dựa trên heuristic `missing_line_geometry` hoặc `low_confidence_lines`. Frontend cần hiển thị trạng thái và nguồn geometry thay vì coi mọi bbox là đo trực tiếp — chú ý cell của bảng markdown Mistral có `geometry_provenance: CLAIMED` (chia đều trong bbox bảng thật, không đo riêng từng ô).

## 5. Gói bàn giao chạy được hôm nay

Từ thư mục `ai-service/`, chạy với PDF được phép xử lý:

```powershell
uv run contract-ocr snapshot --file .\input.pdf --document-id doc-001 --dossier-id dossier-001 --role contract --engine mistral --output data/generated/snapshots
```

Cần `MISTRAL_API_KEY` trong biến môi trường trước khi chạy (xem mục 3). `--engine mistral` không ép toàn bộ file qua Mistral — như mục 2 bước 2 đã nói, mỗi trang tự quyết định: trang có text-layer native đọc thẳng qua PyMuPDF, chỉ trang SCANNED/MIXED thật sự mới gọi Mistral. Một PDF hợp đồng thường gặp — vài trang gõ máy, vài trang chèn ảnh ký/đóng dấu scan — ra kết quả trộn trong cùng snapshot. **`engine` trong snapshot chỉ có ở mức document** (`DocumentSnapshot.engine`, tên engine đã CHỌN cho cả lần chạy) — muốn biết một trang cụ thể đã qua PyMuPDF hay Mistral, đọc `pages[].input_type` của trang đó (`TEXT_LAYER` = chỉ PyMuPDF; `SCANNED_OCR`/`MIXED` = đã gọi Mistral), không có field engine riêng theo trang trong contract này. Lệnh in ra `snapshot_id` và đường dẫn JSON. Cấu trúc file:

```text
data/generated/snapshots/
  dossier-001/
    doc-001/
      <snapshot_id>.json
      <snapshot_id>/page-001.png
      <snapshot_id>/page-002.png
```

Giao cho Backend **JSON + toàn bộ PNG mà `page_image_ref.uri` trỏ tới**; không chỉ đưa riêng file JSON. Với nhiều PDF, thêm `dossier_manifest.json` theo schema manifest và một snapshot cho mỗi document. Tạo bundle mẫu tổng hợp mới bằng:

```powershell
uv run python scripts/export_snapshot_demo.py --output data/generated/ai1-team-handoff-tables
```

Kết quả ở `data/generated/ai1-team-handoff-tables/dossier-001/`: một contract TEXT_LAYER có bảng native và một annex SCANNED_OCR (dữ liệu test, không phải hợp đồng thật). Script không ghi đè thư mục đã có; chọn `--output` mới cho lần chạy tiếp theo. Thư mục `data/generated/` bị Git ignore; chia sẻ bundle qua storage nội bộ được team thống nhất, không commit PDF/ảnh tài liệu vào repo.

Kiểm tra JSON bằng model trước khi giao:

```powershell
uv run python -c "from pathlib import Path; from contract_ocr.domain.snapshot import DocumentSnapshot; p=Path('data/generated/snapshots/dossier-001/doc-001/<snapshot_id>.json'); s=DocumentSnapshot.model_validate_json(p.read_text(encoding='utf-8')); print(s.schema_version, s.page_count)"
```

## 6. Việc cần chốt để tích hợp runtime

1. **Transport:** đề xuất Backend gọi AI1 qua adapter riêng trong worker hiện có, với job ID và đường dẫn storage nội bộ; chưa thêm queue/callback thứ hai khi chưa cần. API đồng bộ chỉ phù hợp demo PDF nhỏ vì OCR scan có thể lâu. Nếu team chọn service async riêng, viết OpenAPI request/status/result dựa trên **cùng** `ai1.snapshot.v1`, không tạo schema output thứ ba.
2. **Storage ảnh:** Backend quyết định nơi lưu JSON/PNG và cách đổi `storage://ocr/...` thành URL ảnh; AI1 giữ tên/ID trong snapshot ổn định trong một lần chạy.
3. **Chuyển đổi result:** Backend viết mapper `ai1.snapshot.v1 -> backend result 0.1` hoặc đổi API Backend sang snapshot mới theo kế hoạch versioning. Phải có test với PDF native, scan, trang lỗi, bảng qua nhiều trang và bbox overlay.
4. **Frontend:** nhận result và URL ảnh từ Backend, dùng `page_image_ref.width_px/height_px` cùng `bbox_normalized`; hiển thị `table_status`, `NEEDS_REVIEW` và provenance. Không tự suy diễn ô có `bbox` là citation đáng tin.
5. **Versioning:** giữ `ai1.snapshot.v1` ổn định; thêm field tùy chọn có thể giữ v1, đổi ý nghĩa/loại field thì tăng version và hỗ trợ chuyển đổi. Backend từ chối version không biết thay vì đọc sai âm thầm.

**Tiêu chí nhận bàn giao:** Backend đọc được bundle mẫu, validate snapshot và digest, phục vụ lại ảnh/trang, Frontend đặt overlay đúng trên PNG, và retry không thay snapshot cũ. Sau đó mới thay đường OCR hiện tại của Backend.
