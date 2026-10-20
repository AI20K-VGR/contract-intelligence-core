# Báo cáo sửa AI1 handoff để khớp `ai1.snapshot.v1` của AI2

Ngày: 2026-09-22
Phạm vi: giữ nguyên AI2 hiện tại; chỉ lấy pipeline OCR từ nhánh `feature/ocr-lab-architecture-review` và sửa lớp phát hành snapshot của AI1.

## Cập nhật source of truth [OBSERVED 2026-09-23]

Hai file Downloads mới (`doc-001`, `doc-002`) là producer profile
`ai1.snapshot.v1/ocr-lab`: table nằm trong `pages[*].tables`, cell nằm trong
rows, và continuity nằm trong `table_continuity`. Chúng không phải canonical
backend snapshot dù root `schema_version` có chuỗi `ai1.snapshot.v1`.

Serializer handoff canonical trong báo cáo này và adapter OCR-lab của AI2 là hai
ranh giới khác nhau: producer output được giữ raw/immutable, còn canonical
snapshot phải được validate theo `docs/contracts/ai1.snapshot.v1.schema.json`.
Không dùng hai file Downloads như canonical fixture nếu chưa qua serializer.

## 1. Kết luận

Đã đưa pipeline OCR của AI1 vào namespace riêng `ai-service/src/contract_ocr` và thêm một lớp handoff chuyển model nội bộ của AI1 sang đúng canonical schema `ai1.snapshot.v1` mà AI2 hiện tại đang validate.

AI2 không bị thay thế. Các file xử lý hiện tại dưới `ai-service/app` vẫn là nguồn xử lý của AI2. Model nội bộ OCR của AI1 vẫn có thể giữ các trường phong phú như `filename`, `document_role`, `nodes` và `table_continuity`; các trường đó chỉ không được phép lọt vào payload canonical gửi sang AI2.

## 2. Vấn đề trước khi sửa

Output của nhánh OCR tự khai báo `ai1.snapshot.v1` nhưng thực tế là một schema khác:

| Nhánh OCR phát | Canonical AI2 cần |
|---|---|
| `page_number`, `text` | `page_no`, `raw_text_digest`, `quality` |
| `line.text`, words ở cấp page | `line.raw_text`, words nested trong line |
| `geometry_provenance=MEASURED/CLAIMED` | `bbox_source` và `geometry_status` theo enum AI2 |
| `table.header`, `rows`, `cells` | `table_coverage`, `cells` phẳng có row/column index |
| `source_digest=sha256:<hex>` | `source_digest=<hex>` |
| `filename`, `engine`, `nodes`, `table_continuity` ở root | Không có trong canonical snapshot AI2 |
| thiếu execution/producer/language/status theo contract AI2 | Bắt buộc ở root AI2 |

Vì vậy chỉ đổi tên `schema_version` là không đủ; AI2 phải từ chối payload để tránh hiểu sai evidence.

## 3. Phần đã sửa

### 3.1. Lấy code AI1 nhưng không merge đè AI2

- Lấy `ai-service/src/contract_ocr` từ `feature/ocr-lab-architecture-review`.
- Lấy cấu hình OCR cần thiết dưới `ai-service/configs`.
- Không merge toàn bộ branch vì branch đó thay/xóa nhiều file AI2 và dùng một schema cùng tên nhưng khác nội dung.
- `ai-service/app`, `docs/contracts/ai1.snapshot.v1.schema.json` và adapter AI2 hiện tại vẫn được giữ nguyên.

### 3.2. Thêm lớp handoff canonical

File mới:

`ai-service/src/contract_ocr/application/use_cases/ai2_snapshot_handoff.py`

Lớp `to_ai2_snapshot_v1(...)` thực hiện:

- map root identity và đổi digest `sha256:<hex>` về `<hex>`;
- tạo `run_id`, `execution`, `producer`, `language`, `status` theo contract AI2;
- map `page_number` → `page_no` và tính `raw_text_digest`;
- chuyển line/word sang cấu trúc nested của AI2;
- chuyển table rows/cells sang `row_index`, `column_index`, `line_ids`, `bbox_fragments`;
- loại bỏ fields không thuộc canonical snapshot AI2;
- giữ warning khi table bị phát hiện nhưng không có cell cấu trúc hợp lệ.

### 3.3. Đổi CLI AI1 sang phát payload canonical

`ai-service/src/contract_ocr/cli/main.py` và demo exporter không còn ghi trực tiếp `result.model_dump()` của model OCR nội bộ. Chúng gọi `to_ai2_snapshot_v1(result)` trước khi ghi JSON.

Đây là điểm thay đổi contract duy nhất giữa AI1 và AI2; pipeline OCR nội bộ vẫn có thể tiếp tục phát model giàu thông tin để benchmark/debug.

### 3.4. Xử lý geometry và table an toàn

- `MEASURED`: giữ bbox; map thành `native` cho text layer hoặc `detector` cho OCR scan.
- `DERIVED`: giữ bbox với `derived`.
- `CLAIMED`: không nâng cấp thành measured/derived. Với line giữ mức `line_only`; với word/table/cell không có geometry citation-grade thì bỏ bbox.
- Table rỗng không được phát thành table hợp lệ. Nếu detector phát hiện nhưng không dựng được cell, output có `table_coverage=UNAVAILABLE` hoặc warning `table_structure_unavailable`.

## 4. Kết quả chạy thử một PDF

Input:

`C:\Users\dungs\Downloads\744287578-Hợp-đồng.pdf`

Output:

`ai-service/data/ai2/ai1-canonical-test/dossier-001/doc-001/ocr-run-ai2-canonical-doc-001.json`

Kết quả:

| Kiểm tra | Kết quả |
|---|---|
| JSON Schema `ai1.snapshot.v1` của AI2 | PASS |
| Semantic validation của AI2 | PASS |
| AI2 `adapt_snapshot_v1` | PASS |
| Root status | `SUCCESS` |
| Số page | 11 |
| Số line | 514 |
| Số table có cấu trúc | 12 |
| Warning handoff | 2 |

Lần chạy này dùng `pymupdf` cho PDF có text layer; chưa phải live Mistral OCR. Khi dùng engine OCR scan, cùng lớp handoff sẽ áp dụng quy tắc geometry/table ở trên.

## 5. Ảnh hưởng tới AI1

### Không ảnh hưởng

- Thuật toán đọc PDF, phân loại page, trích line/word/table nội bộ vẫn giữ nguyên.
- Các trường giàu thông tin như `filename`, `document_role`, `nodes`, `table_continuity`, `processing_ms` vẫn có thể tồn tại trong model nội bộ và report benchmark của AI1.
- AI1 vẫn có thể lưu raw/internal output để debug; chỉ payload gửi AI2 phải qua handoff serializer.

### Có ảnh hưởng cần chấp nhận

- JSON gửi AI2 có shape nhỏ hơn và strict hơn; không được thêm root field tùy ý.
- `filename` và `document_role` phải đi qua dossier manifest/Backend contract nếu AI2 cần dùng; không nhét lại vào root snapshot.
- `nodes` và `table_continuity` không được truyền ngầm trong snapshot hiện tại. Nếu AI2 cần chúng như evidence contract, phải mở một version/schema riêng và review lại contract, không tự thêm field.
- Geometry `CLAIMED` sẽ không còn được coi là tọa độ citation-grade. Điều này có thể làm AI2 giảm độ chính xác overlay/citation, nhưng ngăn AI2 trích dẫn sai vị trí.
- Table bị phát hiện nhưng không dựng được cell sẽ được đánh dấu unavailable/warning thay vì table rỗng giả hợp lệ.

## 6. Điểm AI1 cần hoàn thiện trước production

Serializer hiện tạo deterministic digest cho `config_digest`, `policy_digest`, `source_version_digest` và `code_image_digest` vì pipeline OCR hiện chưa truyền provenance execution đầy đủ. Đây là đủ cho smoke test và contract test, nhưng AI1 production cần truyền giá trị thật từ run manifest/config/policy/code image.

AI1 cần bổ sung:

1. `execution_manifest_id` thật cho mỗi run;
2. digest thật của config, policy và source/code version;
3. language detector thật thay cho profile mặc định `vi-en`;
4. word confidence/geometry thật khi engine cung cấp;
5. mapping line-to-cell nếu muốn AI2 citation được trực tiếp tới table cell;
6. test output sau mỗi run bằng chính schema và semantic validator của AI2.

## 7. Test hồi quy

Đã thêm:

`ai-service/tests/test_ai1_handoff_serializer.py`

Test tạo snapshot nội bộ AI1, serialize sang canonical, rồi chạy cả JSON Schema validator và `adapt_snapshot_v1` của AI2. Đây là gate bắt buộc trước khi đổi tiếp pipeline OCR.

## 8. Cách chạy lại

```powershell
cd ai-service
$env:PYTHONPATH = "src"
uv run --project . python -m contract_ocr.cli.main snapshot `
  --file "C:\path\to\input.pdf" `
  --document-id doc-001 `
  --dossier-id dossier-001 `
  --role contract `
  --output data/ai2/ai1-canonical-test
```

Sau đó gửi file JSON sinh ra vào canonical AI2 lane; không gửi model internal hoặc schema `ai1.snapshot.v1` của branch OCR trực tiếp.

## 9. Kiểm tra bổ sung với PDF scan được yêu cầu

Input:

`C:\Users\dungs\Downloads\Hop_dong_scan_cover_test_full.pdf`

Output canonical đã sinh:

`ai-service/data/ai2/ai1-canonical-scan-test/dossier-001/doc-scan-001/ocr-run-ai2-canonical-scan-001.json`

Kết quả contract:

- JSON Schema `ai1.snapshot.v1`: **PASS**;
- AI2 semantic adapter: **PASS**;
- số page: 6;
- trạng thái root: `FAILED`;
- trạng thái page: 6/6 `FAILED`;
- line/table: 0/0.

Nguyên nhân là lần chạy này dùng `--engine none` vì môi trường hiện chưa có `MISTRAL_API_KEY`. PDF là scan nên PyMuPDF không tự tạo được OCR text. Do đó lần chạy này chứng minh lớp chuyển đổi tạo đúng shape AI2, nhưng chưa chứng minh chất lượng nhận dạng nội dung.

Không nên tiếp tục gọi file canonical này là `ocr-result.json`: tên đó thường gắn với result envelope/legacy output. Với AI2, file cuối nên được phát hành trực tiếp dưới dạng `ai1.snapshot.v1`; raw OCR/internal output có thể lưu riêng để debug.

Để có snapshot scan có line/table thật, cần chạy lại với `--engine mistral` sau khi AI1 được cấp credential và được phê duyệt policy gửi ảnh ra provider. Khi đó vẫn phải chạy lại hai gate `validate_contract(...)` và `adapt_snapshot_v1(...)`; nếu OCR lỗi, snapshot `FAILED/PARTIAL` vẫn phải được phát đúng schema, không được quay về legacy `ocr-result.json`.

### Kết quả thử live Mistral

Đã thử lại chính PDF scan bằng `--engine mistral`. Provider nhận request nhưng trả `429 Too Many Requests` cho cả 6 page. Đây là lỗi rate limit/provider, không phải lỗi contract.

Output vẫn được ghi đúng canonical tại:

`ai-service/data/ai2/ai1-mistral-scan-test/dossier-001/doc-scan-001/ocr-run-ai2-mistral-scan-001.json`

File này có:

- JSON Schema: **PASS**;
- AI2 adapter: **PASS**;
- root status: `FAILED`;
- page status: 6/6 `FAILED`;
- page error: 6/6 có `error.code=OCR_FAILED`;
- line/table: 0/0 vì provider chưa trả OCR content.

Nói cách khác, sau khi sửa AI1, output lỗi của OCR cũng đã chuyển đúng về `ai1.snapshot.v1` của AI2. Khi provider hết rate limit, chỉ cần chạy lại cùng lệnh; không cần đổi contract hoặc thêm adapter legacy.

### Lần chạy thành công với credential mới

Đã chạy lại cùng PDF bằng `--engine mistral`; provider trả `200 OK` cho cả 6/6 page.

Output:

`ai-service/data/ai2/ai1-mistral-scan-test-v2/dossier-001/doc-scan-001/ocr-run-ai2-mistral-scan-002.json`

Kết quả:

- `schema_version`: `ai1.snapshot.v1`;
- JSON Schema: **PASS**;
- AI2 semantic adapter: **PASS**;
- root/page status: `SUCCESS` / 6 page `SUCCESS`;
- 47 line OCR;
- 6 table, 222 cell, 209 cell có text;
- 0 word nested vì Mistral response hiện được pipeline xử lý ở line-level;
- line geometry: `detector` + `measured`;
- table bbox: `measured`;
- cell bbox: không đưa sang AI2 vì geometry cell từ OCR table là `CLAIMED`, không đủ citation-grade.

Đây là bằng chứng rằng code AI1 đã chuyển được output OCR scan thật sang đúng mẫu `ai1.snapshot.v1` của AI2. File phát hành cuối là canonical snapshot JSON ở trên, không phải `ocr-result.json` legacy.

### So sánh trực tiếp với `ocr-result.json`

Đã so sánh output lần chạy thứ ba với file mẫu `C:\Users\dungs\Downloads\ocr-result.json`:

| Hạng mục | Kết quả |
|---|---|
| Số page | 6 = 6 |
| Số line | 47 = 47 |
| Nội dung line sau chuẩn hóa whitespace | 47/47 giống |
| Số table | 6 = 6 |
| Số table cell | 258 = 258 |
| Nội dung table cell | 258/258 giống |
| `source_digest` | Giống tuyệt đối |
| JSON Schema AI2 | PASS |
| AI2 semantic adapter | PASS |

Kết luận: output mới **giống về evidence OCR và nội dung line/table**, nhưng không giống byte-by-byte hoặc cùng shape với `ocr-result.json` vì:

- file mẫu là result envelope `machine/effective` schema `0.1`;
- output mới là canonical `ai1.snapshot.v1`;
- ID document/run được sinh theo request chạy mới;
- citation/clauses/findings của envelope cũ không nằm trong snapshot AI1; AI2 sẽ tạo phần xử lý đó sau khi nhận snapshot;
- word nested hiện là 0 vì engine trả line-level;
- bbox của cell table không được giữ vì upstream đánh dấu geometry là `CLAIMED`, không đủ citation-grade.

Vì vậy nếu mục tiêu là kiểm tra “AI1 có đọc ra cùng nội dung không” thì kết quả là **có**. Nếu mục tiêu là tạo lại đúng file `ocr-result.json` cũ thì **không**; đó là một contract khác và không nên dùng làm output cuối cho AI2.
