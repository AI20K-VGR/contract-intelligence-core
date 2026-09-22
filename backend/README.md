# Backend — Contract Intelligence

FastAPI modular monolith + worker chung codebase, theo [architecture.md](../docs/architecture.md). Phạm vi thực tế: [implementation status](../docs/IMPLEMENTATION_STATUS.md).

## Docker

Từ root: tạo `infra/compose/.env` theo file mẫu, đặt mật khẩu PostgreSQL ngẫu nhiên và đường dẫn artifact trên máy được phép, rồi chạy:

```powershell
.\scripts\demo.ps1 -Profile core
```

Image cài Tesseract `vie+eng`. Không inference external. Web `http://localhost:8080`, Swagger `http://localhost:8000/docs`. Không có login: API không yêu cầu `Authorization`, mọi request coi như cùng một actor cục bộ (`local`, role `admin`). Đây là tool chạy local cho một người vận hành; chưa có multi-user, chưa có ACL từng dossier.

## Phát triển local

Cần Python 3.12, uv và PostgreSQL. Scan cần Tesseract + packs `vie`, `eng` trong PATH; native PDF không cần Tesseract.

```powershell
cd backend
uv sync --locked
Copy-Item .env.example .env
# Sửa CI_DATABASE_URL, CI_ARTIFACT_ROOT trong .env.
uv run alembic upgrade head
uv run uvicorn app.api:app --host 127.0.0.1 --port 8001
```

Terminal thứ hai tại `backend/`: `uv run python -m app.worker`.
Terminal frontend tại `apps/web/`: `npm ci`, rồi `npm run dev`.
Vite proxy `/api` tới localhost:8001, không CORS wildcard. Cổng 8000 dành cho OCR lab cũ; Swagger backend mới ở `http://localhost:8001/docs`. SQLite chỉ dùng test một worker; queue production dựa PostgreSQL `FOR UPDATE SKIP LOCKED`.

## Bật OCR vision (gpt_vision / mistral_vision / \*\_vision_only)

Tesseract luôn chạy trước và giữ toàn bộ bbox/thứ tự dòng; `gpt_vision`/`mistral_vision` chỉ THAY TEXT khi số dòng hai bên khớp — xem `document_processing.py` trong bảng module bên dưới. **4 giá trị loại trừ lẫn nhau**, chỉ đặt một trong số đó trong `.env`:

```powershell
# GPT vision (terra_assisted) — Tesseract vẫn giữ bbox, GPT chỉ thay text
CI_OCR_ENGINE=gpt_vision
CI_OPENAI_API_KEY=sk-...
# CI_OCR_VISION_MODEL=gpt-5.6-terra   # mặc định

# hoặc Mistral OCR (mistral_assisted) — endpoint OCR chuyên dụng, không phải chat completion
CI_OCR_ENGINE=mistral_vision
CI_MISTRAL_API_KEY=...   # lấy tại console.mistral.ai/api-keys
# CI_OCR_MISTRAL_MODEL=mistral-ocr-4   # mặc định

# hoặc bỏ hẳn Tesseract — vision model tự đọc chữ VÀ tự dựng bảng, không cần Tesseract
# dò vùng bảng trước. Đổi lại: bbox không còn đo thật, toàn bộ là "inferred" (chia đều
# theo dòng/hàng-cột) — đánh đổi có chủ đích: ưu tiên chữ đúng + bảng dựng đúng hơn là
# toạ độ chính xác tuyệt đối. mistral_vision_only đã test thật với bảng scan thật;
# gpt_vision_only cùng thiết kế nhưng CHƯA được gọi thử API thật (GPT tự chối markdown
# trong lúc đọc text nên cần 1 lệnh gọi JSON riêng để dò bảng, không có vùng crop sẵn
# như trước — xem _GPT_VISION_FULL_PAGE_TABLE_PROMPT). Dùng chung key ở trên.
CI_OCR_ENGINE=mistral_vision_only
# CI_OCR_ENGINE=gpt_vision_only
```

Sửa `.env` xong phải khởi động lại **cả backend lẫn worker** — `uv run uvicorn`/`python -m app.worker` không tự nạp lại code hay `.env` khi đang chạy (`Ctrl+C` rồi chạy lại lệnh ở Bước "Phát triển local" phía trên). Cả 4 engine đều gửi ảnh trang PDF ra ngoài (OpenAI hoặc Mistral) — không dùng cho hợp đồng thật/nhạy cảm.

## Module trong app/

| Module | Trách nhiệm |
|---|---|
| `api.py` | REST, idempotency, error envelope, health, HTTP metrics |
| `models.py`, `db.py`, `domain.py` | Schema, transaction, invariants |
| `ingestion.py`, `storage.py` | PDF validation, frozen manifest, hash, atomic artifacts |
| `orchestration.py`, `worker.py` | Page queue, lease/token, heartbeat, attempts, checkpoint, publish |
| `document_processing.py` | Native geometry, canonical PNG, scan/mixed Tesseract; `CI_OCR_ENGINE=gpt_vision`/`mistral_vision` thêm vision re-transcription theo dòng (Tesseract vẫn giữ bbox); `gpt_vision_only`/`mistral_vision_only` bỏ hẳn Tesseract — vision model tự đọc chữ + tự dựng bảng trong 1 lệnh gọi, bbox toàn bộ "inferred" (chia đều). `mistral_vision`/`mistral_vision_only` gọi endpoint OCR chuyên dụng của Mistral (`client.ocr.process`, model `mistral-ocr-4`), không phải chat completion |
| `structure.py`, `facts.py` | Article heading và fact candidates từ rule |
| `evidence.py`, `comparison.py` | Citation validation, hai nguồn, abstention khi thiếu context |
| `review.py` | Human overlay append-only, optimistic concurrency, approval gate |
| `reporting.py`, `policy.py` | Batch accounting, actor/role scaffold (không login) |

Module là file Python nhỏ; tách package khi lớn hơn. `ai-service/` vẫn là lab/demo độc lập, không phải microservice của backend này.

## API workflow

Không cần `Authorization`; mutation vẫn cần `Idempotency-Key: <unique-key>`. Cùng key/body trả response cũ; khác operation/body trả 409. Job ID cũng là run ID; retry tạo run mới, giữ snapshot cũ.

1. `POST /api/v1/dossiers` với `{"title":"Demo"}`.
2. Upload từng PDF vào `/dossiers/{id}/documents`, multipart `file` và `role=contract|appendix`.
3. `POST /dossiers/{id}/jobs`: một contract, 0..n appendix; đóng manifest sau start.
4. Poll `/jobs/{id}`; đọc `/dossiers/{id}/results` khi có snapshot.
5. Resolve `/citations/{id}/resolve`; lấy page URL. Bbox normalized trên PNG sau rotation/crop.
6. `POST /review-events`, kèm `expected_revision` từ `review_version`. Target `completeness` luôn bắt buộc; appendix có `relation:{document_id}`.
7. `POST /dossiers/{id}/approve`: chỉ khi `reviewed`, coverage đầy đủ, review resolved, không stale.

`correct` giữ machine, validate giá trị theo loại fact và tạo analysis revision bất biến trong cùng transaction. Chỉ finding phụ thuộc có ID mới, trường `supersedes` và cần review lại; kiểm tra `completeness` cũng mở lại. API results trả cả `machine`, `effective` và hai hash; các collection mặc định effective, dùng `?view=machine` để xem gốc. Approval gắn hash effective cùng review version. `reject` vẫn chặn approval. Start job mới không tự áp correction từ job cũ. Thêm/thay file cần dossier mới; chưa API mở revision manifest.

Sau khi cập nhật code từ bản nền đầu tiên, chạy `uv run alembic upgrade head` để tạo bảng `analysis_revisions` (migration `0002`) và `audit_events` (migration `0003`). Docker migrate service tự thực hiện bước này. Correction chỉ sửa normalized value, giữ source citation gốc và lưu actor/event provenance; không tự kết luận sửa đổi có hiệu lực pháp lý.

`GET /dossiers/{id}/audit` trả toàn bộ dòng thời gian append-only của hồ sơ (upload, enqueue, retry, review, approve, batch) — mỗi event có actor, action, object, request ID và kết quả; ghi song song với nghiệp vụ trong cùng transaction, không phụ thuộc log level.

`POST /jobs/{id}/retry` chỉ cho failed run hiện hành. Copy checkpoint thành công sang run mới, xử lý trang lỗi. Batch thay run ID trong cùng slot, denominator không tăng. Empty OCR giữ issue và chặn approval, không coi là blank.

## Kiểm thử

```powershell
uv run pytest -q
uv run ruff check app tests migrations scripts
```

Test tạo synthetic PDF trong thư mục tạm. Suite kiểm native end-to-end, bbox xoay/crop, scan routing (mock), review/approval, idempotency, fencing, retry, batch, migration SQLite. PostgreSQL multi-worker, scan OCR thật và Docker runtime cần môi trường Docker/Tesseract hoạt động. `gpt_vision`/`mistral_vision` được test bằng cách monkeypatch thẳng `_gpt_vision_lines`/`_mistral_vision_lines`/`_*_vision_table` trong `test_processing.py` — không gọi API thật, không cần key khi chạy suite.

Chỉ chạy nhóm test Mistral: `uv run pytest -q tests/test_processing.py -k mistral`. Nhóm test riêng cho 2 chế độ bỏ Tesseract: `uv run pytest -q tests/test_processing.py -k vision_only`.

**Windows: nếu `pytest` báo `PermissionError: ... pytest-of-<user>`** (thư mục temp hệ thống bị khoá quyền, không liên quan code) — trỏ `--basetemp` ra chỗ khác và tắt cache provider:

```powershell
uv run pytest -q --basetemp="$env:TEMP\pytest-ci-tmp" -p no:cacheprovider
```

**Đã biết, chưa sửa (không liên quan gpt_vision/mistral_vision):** 4 test — `test_gpt_vision_table_recovers_a_column_ocr_tables_geometry_dropped`, `test_gpt_vision_table_unavailable_keeps_the_geometry_based_table` và 2 bản mirror phía Mistral — hiện fail vì `_ocr_tables()` (phát hiện bảng từ hình học Tesseract) không nhận ra bảng từ fixture 3x3 trong test nữa, kể cả gọi trực tiếp không qua GPT/Mistral. Xác nhận có từ trước, thuộc phần "harden OCR table reconstruction" đang sửa dở, chưa commit — không phải regression từ việc thêm `mistral_vision`.

Tham chiếu: [SQLAlchemy row locking](https://docs.sqlalchemy.org/en/20/core/selectable.html#sqlalchemy.sql.expression.Select.with_for_update), [FastAPI UploadFile](https://fastapi.tiangolo.com/tutorial/request-files/).
