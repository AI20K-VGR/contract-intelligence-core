# ai-service/

> **Sẽ generate chi tiết ở bước tiếp theo — phụ trách: AI Engineer**

Thư mục này chứa **Python service** chạy OCR / IDP / LLM extraction cho **Contract Intelligence**.

## Tech stack dự kiến

- Python 3.11+
- FastAPI (REST interface với backend) hoặc Celery + Redis (async worker)
- OCR: PaddleOCR / Tesseract / Cloud Vision API
- LLM extraction: OpenAI API / Local LLM (Llama 3 / Qwen)
- Vector DB: ChromaDB / FAISS (để lưu clause embeddings)
- Container: Docker + Docker Compose

## Kiến trúc dự kiến

```
ai-service/
├── app/
│   ├── api/            # FastAPI routes
│   ├── core/           # Config, logging
│   ├── services/       # OCR, LLM, embedding logic
│   └── models/         # Pydantic schemas
├── models/             # Lưu ML model files (git-lfs)
├── tests/
├── Dockerfile
├── docker-compose.yml
└── requirements.txt
```

## Vai trò

- Nhận request trích xuất từ `backend/`
- Gọi OCR → tách text
- Gọi LLM → trích xuất cấu trúc điều khoản (Điều > Khoản > Điểm)
- Trả kết quả về `backend/` qua REST hoặc message queue

> **Lưu ý:** Bước đầu, OCR/IDP có thể chạy trong `backend/` (gọi external API). Thư mục này chỉ tạo khi team muốn tách AI worker ra riêng để scale.

> Chi tiết sẽ được generate khi AI Engineer nhận task. Thư mục này giữ trống trước.
