# P2 developer record — default-on runtime AI2

## Implementation

- Set source defaults ON for contract graph, pair generation, processing egress, query LLM/vector/egress, vector recall, and required PostgreSQL persistence. Explicit `false` remains an operator kill switch.
- Kept query egress constrained by both server caps and dossier consent. Consent is accepted for query egress only from a verified signed service envelope; unsigned compatibility requests stay local even if they claim consent.
- Added graph and pair defaults to `.env.example`; kept discovery OFF, auto-pass OFF, and query signature required.
- Isolated tests that intentionally run without PostgreSQL with explicit `AI2_REQUIRE_DATABASE=false`; CI deterministic profile uses the same explicit override.
- Pinned graph-off and graph-only golden capture/tests to explicit OFF values so enabling the new defaults does not change what those regression fixtures measure.
- Updated query/vector test fixtures to include signed request consent and persisted dossier consent where external egress is the behavior under test.

## Red → green evidence

- The graph sample-default assertion failed while the two variables were absent from `.env.example`, then passed after adding them.
- The new unsigned-query consent regression failed before the signature gate (`_llm_calls() == 1`) and passed after requiring a verified service envelope.
- The first broad run exposed stale test assumptions for database, graph-off, graph-only pairs, and signed consent. Those tests now set their intended profile explicitly; no production safeguards were relaxed.

## Verification

- Command: `AI2_REQUIRE_DATABASE=false; AI2_LLM_API_KEY=; AI2_EMBEDDING_API_KEY=; AI2_DATABASE_URL=; AI2_TEST_DATABASE_URL=; uv run pytest -m "not live and not integration" --ignore=tests/test_hd_gold.py --ignore=tests/test_structure_reconstruction.py --deselect=tests/test_ingest.py::test_hd_tong_hop_sample_pdf_extracts_and_answers_dieu_9 -q`
- Result: `1606 passed, 3 skipped, 17 deselected, 25 warnings in 301.84s` on Python 3.12.13.
- Targeted query/consent/graph tests: `67 passed, 1 warning in 7.55s`.
- Ruff check: PASS. Ruff format check: PASS for all 16 changed Python files.
- `docker compose config --quiet`: PASS. Rendered `ai2-service` defaults for graph, pairs, processing/query egress, query LLM/vector, vector recall, and `AI2_REQUIRE_DATABASE` were all `true`.
- Provider keys were blank for the deterministic runs; no live inference was attempted.

## Limitations

- PDF-only goldens were excluded because generated PDF inputs are gitignored and absent from a clean checkout.
- Live and integration markers were excluded from the local deterministic profile. P1's pushed GitHub CI receipt is recorded separately; this P2 tree still needs its own remote CI run after push.
