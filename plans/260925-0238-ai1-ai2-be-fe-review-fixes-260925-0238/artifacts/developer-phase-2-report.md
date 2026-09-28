# Developer report — phase-2-ai2-persistence-coverage

## Delegated red phase

The developer lane created the two phase tests and stopped safely before
implementation. The initial red run failed during collection because
`load_ai2_read_model` and `evaluate_ai2_completeness` did not exist in the
current persistence module.

## Main-thread completion

The main thread implemented an additive AI2 projection on `pipeline_run`, with
the complete wire envelope, digest/idempotency fields, completeness metrics,
reason code, review state and evidence-ready flag. It added the Alembic v11
migration, reloadable read-model loader, stable invalid-citation review item
creation, and digest conflict protection. Existing fact/finding projections
remain intact.

## Verification

- `uv run --project backend python -m pytest backend/tests/unit/test_ai2_result_persistence.py backend/tests/unit/test_ai2_read_model_completeness.py backend/tests/unit/test_worker_pipeline_run.py -q --basetemp C:\Temp\vsf-ai2-p2-regression`
  - `5 passed`
- `uv run --project ai-service python -m pytest ai-service/tests/test_processing_wire_contract.py ai-service/tests/test_contract_context.py -q --basetemp C:\Temp\vsf-ai2-p2-regression-ai`
  - `26 passed`
- `uv run --project backend ruff check backend/src backend/tests`
  - `All checks passed`

The requested full AI-service ruff scan remains a pre-existing risk: it reports
83 lint findings across unrelated files outside this phase. Those findings were
not rewritten as unrelated cleanup. Pytest cache/deprecation/unknown-mark
warnings were non-blocking.
