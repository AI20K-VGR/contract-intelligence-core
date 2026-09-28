# AI2 query authoritative evidence — Debug report

## Executive Summary

- Issue: UI Q&A returned `AI2_QUERY_EVIDENCE_REQUIRED` for every dossier query.
- Root cause: `ai-service/app/api/main.py` returned a fixed fail-closed response from `/query` and never read the canonical record created by `/jobs/idp`.
- Fix: signed backend queries now resolve the canonical `DossierRecord` from AI2 memory, run the existing `QueryRouter`, and return grounded citations. Explicitly labelled contract totals in compact OCR snapshots are also promoted to `contract_value` with the original line citation.
- Status: fixed and covered by a regression test.

## Evidence

- `POST /api/v1/query` returned `state=INSUFFICIENT_EVIDENCE` with no citations even after a canonical record was present.
- The old `/query` implementation returned that response unconditionally.
- The red regression test reproduced the failure before the fix.
- The green regression test confirms a canonical record produces an answer and citation.
- A compact-snapshot regression test confirms `Giá trị hợp đồng: ... VND` becomes a structured `contract_value` node without losing the source line.

## Data flow

1. Backend worker sends `be.ai2.processing.request.v1` to `/jobs/idp`.
2. AI2 adapts and stores the authoritative dossier record in `STORE`.
3. Backend Q&A now signs a separate `ai2.query` request.
4. AI2 verifies the envelope, reads `STORE`, runs `QueryRouter`, and returns citations.

## Regression test

`ai-service/tests/test_legacy_compat.py::test_backend_query_reads_authoritative_canonical_record`

`ai-service/tests/test_ai1_snapshot_adapter.py::test_compact_ocr_promotes_explicit_contract_value_with_line_citation`

Command:

```powershell
uv run pytest tests/test_legacy_compat.py::test_backend_query_reads_authoritative_canonical_record -q
```

Live container smoke test: signed `/jobs/idp` → worker → `/query` returned
`ANSWERED`, value `1234567`, and a `VALID` citation for the OCR line.
