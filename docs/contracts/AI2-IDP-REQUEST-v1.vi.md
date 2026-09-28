# AI2 IDP request v1

Đây là envelope canonical để AI2 nhận một dossier. Envelope chứa đúng một
`ai1.dossier-manifest.v1` và một snapshot `ai1.snapshot.v1` cho mỗi document
trong manifest.

Machine-readable authority:

- `ai2.idp.request.v1.schema.json`
- `ai1.dossier-manifest.v1.schema.json`
- `ai1.snapshot.v1.schema.json`

Quy tắc bắt buộc:

- `schema_version` của request là `ai2.idp.request.v1`.
- `task_id` và `attempt_id` là identity của lần xử lý, không suy ra từ filename.
- Manifest có đúng một `body`, tối đa sáu document; các document còn lại là
  `annex`.
- `document_id`, `snapshot_id`, `dossier_id` và `source_digest` của snapshot
  phải khớp manifest.
- Root và các object canonical dùng `additionalProperties: false`; field lạ bị
  reject tại boundary.
- Legacy result envelope, snapshot version khác v1 và OCR catalog không thuộc request
  canonical này. Nếu cần migration, result/legacy chỉ đi qua compatibility path riêng; snapshot version khác v1 bị từ chối.

AI2 không được suy luận role từ tên file hoặc thứ tự upload. Snapshot gốc chỉ
được đọc; facts, findings, citations và review state là output nội bộ của AI2.
