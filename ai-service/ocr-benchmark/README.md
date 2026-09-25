# Scan-only OCR Pilot Benchmark

Framework này chỉ benchmark PDF scan và PNG/JPG/JPEG. Mọi PDF luôn được render thành
ảnh trước khi OCR; code benchmark không gọi API trích xuất text layer của PyMuPDF.

## Chuẩn bị

```powershell
cd ai-service
Copy-Item ocr-benchmark/.env.example .env
uv sync --extra mistral
```

Đặt `MISTRAL_API_KEY` trong `.env`. Nếu thiếu key, run được ghi `SKIPPED` thay vì làm
hỏng toàn bộ benchmark.

## Thêm dataset thật

1. Chép PDF scan/PNG/JPG vào `ocr-benchmark/data/scans/`.
2. Khai báo từng file trong `ocr-benchmark/data/metadata/dataset.json`. `file_name`
   phải đúng tên file; một document có thể có nhiều `test_cases`.
3. Tạo `ocr-benchmark/data/ground_truth/<document_id>.json` theo file mẫu. Ground truth
   phải được người review; ưu tiên full-page text, critical fields và bảng quan trọng.
4. Không đưa digital/selectable-text PDF vào pilot này. Nếu có text layer nhưng nguồn
   thực sự là scan, benchmark vẫn chỉ dùng ảnh render.

## Chạy

```powershell
uv run python -m benchmark prepare --input ocr-benchmark/data/scans
uv run python -m benchmark run
uv run python -m benchmark evaluate
uv run python -m benchmark report
```

Hoặc:

```powershell
uv run python -m benchmark all --input ocr-benchmark/data/scans
```

Benchmark chỉ chạy Mistral OCR. `raw` và `preprocessed` là hai experiment paired trên
cùng document/page để đo chính xác tác động của preprocessing.

## Output

- `artifacts/<document>/<experiment>/mistral/normalized.json`
- `artifacts/.../raw/raw.md`
- `reports/benchmark_summary.csv`
- `reports/benchmark_by_document.csv`
- `reports/benchmark_by_page.csv`
- `reports/benchmark_by_category.csv`
- `reports/critical_fields.csv`
- `reports/failure_cases.csv`
- `reports/benchmark_report.md`

Hai experiment `raw` và `preprocessed` đều chạy Mistral trên cùng document/page để so
sánh paired. Bootstrap lấy mẫu ở document level (1000 lần, 95%, seed 42). Đây là pilot
benchmark trên dataset hiện tại, không phải kết luận cho toàn bộ population.
