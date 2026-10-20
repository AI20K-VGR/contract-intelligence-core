# P1 implementation notes

## Changes

- Added `ai2.contract_graph_write_receipts` migration/table with per-job, per-kind stage and persistence status, count, digest, and safe error code.
- Graph completion now records operation/pair receipts in the outer job transaction, isolates each graph write with a savepoint, and clears stale pair rows for the new successful snapshot even when the pair stage was skipped.
- Added a signed, scope-bound, bounded internal read endpoint. It checks tenant/dossier/job, latest successful job, current digest, receipt and actual row count before returning pages. SQLite returns `UNAVAILABLE`; absent/failed persistence never appears as a successful empty graph.
- Graph projection returns node ids and citation ids/opaque refs, but omits citation text spans, pair spans, replacement/scope text and raw contract content.
- Added response JSON Schema and unit/API/PostgreSQL integration tests.

## Test evidence

- **RED:** initial focused run failed 4/4 with `ModuleNotFoundError` for the new read-model module.
- **Focused after implementation:** `uv run pytest tests/test_contract_graph_read_api.py -q` — 9 passed, including the PostgreSQL integration test after Docker Desktop was started. The real database run found the new Alembic revision exceeded the 32-character version column; shortened the new revision ID to `0007_graph_receipts`.
- **PostgreSQL migration regression:** `uv run pytest tests/test_contract_graph_read_api.py tests/test_contract_graph_pairs_postgres_store.py tests/test_contract_graph_postgres_store.py -q` — 24 passed. Updated migration-head/down-upgrade assertions and the skipped-pair stale-row expectation to match P1 semantics.
- **Lint:** targeted `uv run ruff check ...` — passed.
- **Schema compatibility repair:** the existing `document_number` request field is nullable in the Pydantic DTO; JSON Schema now allows null too. Its focused request test passes.
- **Fixture restoration:** restored the existing PDF fixtures and P0 baseline artifact from the source checkout into this worktree as local test inputs; they are not staged or committed.
- **Gold regression repair:** The HD gold fixture's annex is explicitly titled "Phụ lục 1 — Sửa Điều 5", while its penalty Fact had lost its article heading context. Narrowed interpretation to explicit annex titles that address the body clause's own Điều/Khoản/Điểm/Mục; mismatched address remains `COMPARABLE_DIFFERENCE`. Kept general amendment marker rules unchanged. Preserved unaccented OCR headings (`Phu luc`, `Cung sua`) through Fact subject extraction and comparison. Added targeted match/mismatch and extraction tests.
- **Focused marker/gold tests:** `uv run pytest tests/test_compare.py tests/test_relation_markers.py tests/test_st045_facts_findings.py::test_fact_extraction_preserves_ascii_annex_amendment_heading_from_ancestors tests/test_hd_gold.py::test_hd_tong_hop_gold_two_source_findings -q` — 40 passed.
- **Full AI2 suite:** `uv run pytest -q` — 1,586 passed, 9 skipped, 25 existing warnings, 0 failures (229.11s).

## Gate status

P1 is verified **PASS**. The real PostgreSQL migration/API tests and full AI2 suite pass, targeted Ruff passes, and runtime remains gated with the read API internal-only. The heading fix was narrowed to explicitly titled amendment headings whose cited clause address matches the body subject; it does not change candidate generation, classifier, prompt, threshold, or graph runtime flags.
