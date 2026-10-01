FILE ?= example.pdf
MANIFEST ?= data/manifest.csv
OUTPUT ?= reports/run_001
ENGINES ?= pymupdf,paddle,deepseek

.PHONY: install test lint inspect generate-degraded benchmark
install:
	uv sync --python 3.12 --extra dev
test:
	uv run --extra dev pytest
lint:
	uv run --extra dev ruff check src scripts tests
	uv run --extra dev ruff format --check src scripts tests
inspect:
	uv run python scripts/inspect_pdf.py --file "$(FILE)"
generate-degraded:
	uv run python scripts/generate_degraded_samples.py --file "$(FILE)"
benchmark:
	uv run python scripts/benchmark.py --manifest "$(MANIFEST)" --engines "$(ENGINES)" --output "$(OUTPUT)"
