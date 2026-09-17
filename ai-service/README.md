# ai-service/

> **Sẽ generate chi tiết ở bước tiếp theo — phụ trách: AI Engineer.** Theo DOC-03 CON-06, feature code chỉ bắt đầu sau khi mentor phê duyệt kiến trúc.

Thư mục này chứa **Python HTTP service** chạy OCR/layout (AI1) và IDP (AI2) cho **Contract Intelligence**.

## Tech stack đích

- Python 3.12 (cùng target với backend, DOC-04 ADR-01)
- FastAPI + Uvicorn; service nội bộ, **stateless**, được backend gọi theo mô hình push (DOC-04 ADR-02)
- OCR/layout baseline: PaddleOCR hoặc Tesseract; native PDF text qua adapter phù hợp; engine chọn theo benchmark DOC-06
- External recognizer/LLM: chỉ là adapter opt-in sau policy approval, egress grant và Gate B
- Embedding/vector index: không thuộc MVP; chỉ đánh giá sau benchmark semantic retrieval
- Container: Docker + Docker Compose (profile `local-baseline`)

## Kiến trúc dự kiến

```
ai-service/
├── app/
│   ├── api/            # FastAPI router: POST /jobs/{kind}, GET /jobs/{id}, DELETE /jobs/{id}, /health
│   ├── jobs/           # In-memory/ephemeral job registry theo task_id + attempt_id
│   ├── adapters/       # PDF/OCR/layout/external-provider adapters
│   ├── pipeline/       # AI1: render, route, OCR, layout, table; AI2: structure, fact, link, compare
│   └── contracts/      # Pydantic models cho ai1.snapshot.v3, evidence-gap-event.v2, result envelope
├── models/             # ML model files (git-lfs)
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Job API nội bộ (không nằm trong DOC-05)

| Endpoint | Ý nghĩa |
|---|---|
| `POST /jobs/ocr` | AI1 OCR/layout cho một page/crop hoặc document; input là URL artifact ngắn hạn + `task_id`/`attempt_id` + config digest. Trả `202 {job_id}`. |
| `POST /jobs/reocr` | AI1 bounded re-OCR theo `reocr-request.v3` target (`REGION`/`PAGE`/`PAGE_PAIR`); external route chỉ khi request mang grant ID hợp lệ. |
| `POST /jobs/idp` | AI2 structure/fact/link/compare trên snapshot v3 đã validate; kết quả có thể chứa `evidence-gap-event.v2` items. |
| `GET /jobs/{job_id}` | `RUNNING` \| `SUCCEEDED` (payload + SHA-256 digest) \| `FAILED` (error code). |
| `DELETE /jobs/{job_id}` | Backend huỷ job mồ côi khi lease hết hạn. |

Payload trả về phải khớp [`ai1.snapshot.v3`](../docs/contracts/ai1.snapshot.v3.schema.json) hoặc AI2 result envelope; backend validate schema + semantic trước khi persist. Kết quả không hợp lệ bị `QUARANTINED`, không auto-retry.

## Ranh giới bắt buộc (DOC-04 ADR-02)

- Không là public API; không nhận request từ frontend/operator.
- Không kết nối PostgreSQL, không sở hữu queue/lease/callback lifecycle, không ghi business table, không phát domain event.
- Chỉ đọc source/render qua URL ngắn hạn do backend cấp; không giữ credential storage dài hạn.
- AI2 không gọi AI1 trực tiếp và không sửa OCR text/bbox; evidence gap chỉ được trả trong kết quả job.
- External OCR/LLM mặc định tắt; egress broker là nơi duy nhất có credential provider.
- Job là ephemeral: backend là nơi duy nhất giữ trạng thái bền vững của task.

Xem [DOC-04](../docs/DOC-04-architecture.md), [API contract](../docs/DOC-05-api-spec.yaml), [contracts](../docs/contracts/README.md) và [AI2 pipeline](../docs/AI2-IDP-OPTIMIZATION-PIPELINE.md). Snapshot v1/v2 chỉ còn ở documentation archive để đọc/audit migration.
