# P1 implementation notes

## Changes

- Replaced the AI service CI placeholder with a locked `uv` install, changed-Python-file Ruff checks, and provider-free tests. The job includes the Kafka extra required during test collection; its isolated test profile explicitly disables mandatory DB startup without changing runtime defaults.
- Existing dossiers now fail closed when consent metadata is absent, null, or malformed. New dossiers persist the approved operator default (`true` unless explicitly configured `false`), while supplied consent values remain authoritative.
- Wrapped the graph-evidence response validation expression without changing its accepted schema or behavior.
- Added regression coverage for malformed/missing consent and for explicit consent initialization and operator override. Updated ContractService metadata expectations to reflect the explicit persisted consent field.

## Red-to-green evidence

- Before implementation: consent regression selection failed 6 cases because malformed/missing metadata inherited the environment default and new dossiers did not persist consent.
- After implementation: consent tests passed (9 passed, 70 deselected); ContractService tests passed (33 passed).
- Backend unit suite passed (575 passed); architecture suite passed (4 passed); Ruff check passed; MyPy passed (228 source files).
- Backend `ruff format --check src/ tests/` initially exposed nine existing unformatted files (the evidence-response adapter was already formatted as part of P1); applied Ruff formatting only, then the full-tree format check passed. No behavior was changed by those formatting edits.
- AI service Ruff whole-tree baseline contains 198 pre-existing unformatted files and existing lint violations. CI checks changed Python files to avoid unrelated baseline failures while retaining broad deterministic tests.
- AI service workflow YAML parses locally. A broad local profile passed 1,562 tests; 7 Mistral OCR tests initially failed because the optional `mistralai` extra was absent. CI now installs that extra, and the affected Mistral module passes (9 passed). The 57 PostgreSQL-dependent cases were excluded locally because Docker did not respond.
- CI supplies a PostgreSQL 16/pgvector service and `AI2_TEST_DATABASE_URL` for PostgreSQL-backed AI service tests. Backend PostgreSQL integration tests were not run locally because the Docker daemon did not return from `docker info`; Backend CI already provisions PostgreSQL for its integration profile.

## Scope notes

No provider key or contract content is needed by this phase's CI checks. No runtime graph-pair algorithm, threshold, review policy, or database data was changed.

## CI follow-up on the pushed branch

- Backend CI passed on P1 SHA `84dcbfbee77c7794132878f3e1b85efdf56513a8`: unit, architecture, Ruff, MyPy, and PostgreSQL integration checks all succeeded ([run 38447999105](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/38447999105)).
- Initial AI-service run `38447999238` exposed three setup/test-profile mismatches: Python 3.11 versus Python 3.12 goldens, a job-wide pairs-off override breaking graph-on regressions, and PDF tests depending on ignored generated binaries.
- Follow-up `04b5f57b707d8aba824f5e144429f84de35a9ab4` pins Python 3.12, removes the pairs-off job override, and explicitly prints/deselects tests whose PDF fixtures are gitignored. The job sets `AI2_REQUIRE_DATABASE=false` only for this isolated test profile; the runtime default remains required.
- AI-service CI passed on the follow-up SHA: 1,603 passed, 17 deselected, 24 warnings in 217 seconds ([run 38451182250](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/38451182250)). The deselected set includes explicitly reported PDF-only contract gold tests; the remaining deterministic suite passed.
- P1 machine receipt is `artifacts/verification-P1.json`, written by `hs-run cook verify`, verdict PASS with a named SKIP check for PDF-only gold fixtures.
