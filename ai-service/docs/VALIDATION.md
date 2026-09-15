# Validation on the development machine

Python 3.12 virtual environment at `D:\codebase_ocr\.venv`, with base and dev extras installed. Locked dependency versions are in `uv.lock`.

Executed:

```text
python -m pytest -q
41 passed

python -m ruff check src scripts tests
All checks passed

python -m ruff format --check src scripts tests
42 files already formatted
```

Coverage includes normalization/IoU, Unicode CER/WER and Vietnamese stroke/diacritic alignment, manifest/schema/config validation, value normalization, preprocessing transforms/inverse geometry, deterministic degradation, native routing, rotated PDF coordinates, page exception isolation, report generation, unavailable engines and adapter payload mapping using explicit stubs.

End-to-end CLI smoke: `reports/synthetic_smoke/` processes two explicitly synthetic PDFs through E0/E1/E2. Six sample-experiment attempts: 3 SUCCESS using native extraction, 3 SKIPPED (native scan extraction unsupported; Paddle and Torch not installed). These are software validation outcomes, not measurements of OCR model quality. The native bbox overlay was rendered and visually inspected on the source PDF.

PaddleOCR PP-OCRv6 model inference, DeepSeek Transformers/vLLM inference, GPU memory behavior and real Vietnamese contract accuracy have **not** been tested on this machine. Adapter unit tests use stubs, not model weights. No real 30-sample annotated benchmark has been run. Existing `dataset/` contents were not modified or used to fabricate annotations.
