# AI2-11 — Input AI1 snapshot thực tế và package AI2 v1

## Quyết định đầu vào

Từ ngày 22/09/2026, hai file output AI1:

- `ocr-run-20260922-093747-doc-001.json`
- `ocr-run-20260922-095540-doc-002.json`

được dùng làm integration input thực tế cho AI2. Chúng khai báo
`schema_version = ai1.snapshot.v1` và có producer profile OCR-lab gồm
`filename`, `document_role`, `engine`, `pages`, root `nodes` và
`table_continuity`.

Shape này khác với canonical backend snapshot cũ trong
`docs/contracts/ai1.snapshot.v1.schema.json`. Vì vậy không được đổi tên field
để giả lập canonical payload. Shape thực tế được đăng ký tại:

`docs/contracts/ai1.snapshot.v1.ocr-lab.schema.json`

## Kiểm kê producer output hiện tại [OBSERVED 2026-09-23]

Hai file Downloads là producer snapshots thật đang dùng cho replay, không phải
fixture canonical đã commit trong repo:

| File | Profile/thông số thật | Cần lưu ý cho AI2 |
|---|---|---|
| `ocr-run-20260922-093747-doc-001.json` | `TEXT_LAYER`, 8 pages, 69 root nodes, 358 lines, 3633 words, 1 nested table, 0 continuity records | root node geometry là `DERIVED`; page status `SUCCESS` |
| `ocr-run-20260922-095540-doc-002.json` | `SCANNED_OCR`, 4 pages, 7 root nodes, 48 lines, 0 words, 3 nested tables, 2 continuity records | table geometry `MEASURED`, cell geometry có `CLAIMED`; page status `SUCCESS` |

Shape quan sát được ở root là `schema_version`, `snapshot_id`, `source_digest`,
`dossier_id`, `document_id`, `filename`, `document_role`, `input_type`, `engine`,
`page_count`, `processing_ms`, `pages`, `nodes`, `table_continuity`. Table không
nằm ở root `tables`: table thật nằm trong `pages[*].tables`, cell nằm trong
`rows[*].cells`, và continuation nằm trong root `table_continuity`. Adapter phải
assert topology này, không được coi `root.tables` là nguồn duy nhất.

Hai file cùng `dossier_id=dossier-001` nhưng khác `document_id` và
`source_digest`; package v1 phải giữ `relation_policy=INDEPENDENT`. Chuỗi
`schema_version=ai1.snapshot.v1` trong producer output không làm payload trở thành
canonical backend snapshot; profile thực tế cần ghi rõ là `ai1.snapshot.v1/ocr-lab`.

AI2 package v1 nhận profile này qua adapter riêng, giữ raw evidence và tạo
model nội bộ để chạy pipeline.

## Package API

```python
from app.ai2.v1 import process_files

result = process_files(
    [
        r"C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json",
        r"C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json",
    ],
    use_llm=False,
)
```

Package identity:

- package: `vsf-ai2`
- API: `ai2.package.v1`
- input profile: `ai1.snapshot.v1/ocr-lab`
- package version: `1.0.0`

CLI tương đương:

```powershell
python scripts/run_ai2_ai1_files.py `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json" `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json" `
  --strict --output artifacts/ai2-two-input-replay.json
```

`--use-llm` chỉ là gate opt-in khi provider/credential được phê duyệt; không
đưa vào offline release gate. Khi file Downloads không có, replay phải ghi
`NOT_RUN`, không được coi là pass; deterministic fixtures trong repo vẫn là
gate bắt buộc.

## Quy tắc xử lý

- Hai document chạy trong scope riêng, không tự tạo cross-document finding.
- `source_digest` dạng `sha256:<hex>` được kiểm tra và giữ raw value.
- Duplicate node ID tạo occurrence ID nội bộ, không overwrite node AI1.
- Raw text dùng cho citation; analysis text chỉ là view phụ trợ.
- `CLAIMED`/`DERIVED` geometry không được nâng thành citation-grade.
- Table continuation chỉ được liên kết logical; không tự ghép cell hoặc tạo dữ liệu.
- LLM chỉ tạo proposal/extraction bounded; lỗi một unit không làm mất các unit khác.
- Kết quả có evidence issue phải là `NEEDS_REVIEW`, không được coi là `PASS`.

## Kiểm chứng bắt buộc

```powershell
.venv\Scripts\python.exe -m pytest -o addopts='' -q -m "not live" --basetemp ..\tmp\ai2-release-basetemp
python scripts/live_eval.py --mode live --vector-mode off --strict `
  --review-output --output artifacts/ai2-live-audit
```

`source_digest`, raw text, page/line/table IDs và issue codes phải được ghi
trong report để replay được mà không cần PDF bytes.
