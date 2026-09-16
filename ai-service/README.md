# ai-service/

> **Sẽ generate chi tiết ở bước tiếp theo — phụ trách: AI Engineer**

Thư mục này chứa **Python service** chạy OCR / IDP / LLM extraction cho **Contract Intelligence**.

## Tech stack đích

- Python 3.11+
- Python worker nội bộ, claim task từ PostgreSQL theo lease do backend điều phối
- OCR/layout baseline: PaddleOCR hoặc Tesseract; native PDF text qua adapter phù hợp
- External recognizer/LLM: chỉ là adapter opt-in sau policy approval và Gate B
- Embedding/vector index: không thuộc MVP; chỉ đánh giá sau benchmark semantic retrieval
- Container: Docker + Docker Compose

## Kiến trúc dự kiến

```
ai-service/
├── app/
│   ├── worker/         # Claim lease, execute task, post artifact result
│   ├── adapters/       # PDF/OCR/layout/external-provider adapters
│   ├── pipeline/       # Snapshot, structure, fact and comparison stages
│   └── contracts/      # Snapshot/result validation models
├── models/             # Lưu ML model files (git-lfs)
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Vai trò

- Claim task lease do backend phát hành và đọc source qua URI được cấp quyền
- OCR/layout → snapshot có provenance; structure/fact/comparison candidate theo task
- Trả artifact digest + contract version về internal backend endpoint

> **Ranh giới bắt buộc:** service này không là public API, không sở hữu queue/callback lifecycle và không ghi trực tiếp business tables. Backend Spring Boot là owner của API, run, retry và persistence. External OCR/LLM mặc định tắt; chỉ route sau policy approval và Gate B.

Xem [DOC-04](../docs/DOC-04-architecture.md), [API contract](../docs/DOC-05-api-spec.yaml) và [OCR snapshot schema](../docs/contracts/ai1.snapshot.v1.schema.json).

> Chi tiết sẽ được generate khi AI Engineer nhận task. Thư mục này giữ trống trước.
