# Issue #131 — implementation and local verification

## Result

The signed AI2 dossier deletion API and its Backend integration are implemented.
Purge uses PostgreSQL + pgvector; no SQLite deletion path is introduced. The user
requested local verification before deployment. No staging/production data was
read or deleted, and the seven historical production scopes remain a rollout task.

Backend now calls AI2 before marking its purge completed, validates cumulative
count evidence and stores it in `deletion_ledger.evidence.ai2`. A remote failure
leaves a durable failed state for the existing sweeper; a healthy failure transaction
is committed instead of discarding that state when the background task exits.

AI2 deletes content under a permanent tenant/dossier tombstone. Database triggers
fence late job/snapshot/graph/trace/session/durable/vector writes. Ownership history
protects shared and historical vector digests across tenants. File cleanup survives
DB commit/crash and is retried. Live-run audit remains append-only; deleted-run audit
is erased because its details may contain content. Nonces and content-free ownership,
tombstone and count metadata remain.

## Verified locally

| Area | Evidence |
|---|---|
| LLM live | **2 passed** using the existing local gateway's configured credential; no key was printed, committed or changed |
| AI2 acceptance | **17 passed** on real PostgreSQL 16 + pgvector, including upgrade from 0008 with existing content, shared/historical digests, tenant isolation, late writers, cancellation, audit, cleanup/recovery and claimed outbox |
| Backend → AI2 E2E | **2 passed**: real AI2 HTTP process, migrated PostgreSQL, authenticated Backend DELETE, two files and OCR, ledger evidence, failed transport + sweeper retry, another dossier preserved, AI2 restart and idempotent DELETE |
| AI2 regression | Previous final run **2555 passed**, 6 live tests deselected; the 10 expensive golden tests omitted from that final rerun had passed in both earlier full runs |
| Backend regression | **1001 passed, 12 deselected**, with dedicated PostgreSQL databases for invariants/role tests and lexicon; the new local E2E cases were run separately |
| Lint | Ruff on changed Python files and `git diff --check` pass |

Backend migrations were applied from an empty database to
`v24__pipeline_step_progress`; AI2 startup migrated its own schema to
`0009_dossier_purge`. Restart after deletion still returned 404 for the old job,
410 for signed query, and a successful repeated DELETE with zero new deletions and
the original cumulative job count. Backend database shells remain, as required.

A read-only count audit of **8 deleted synthetic dossiers** in the local E2E database found no jobs, query snapshots,
edges, pairs, graph receipts, processing traces or Backend OCR belonging to deleted
dossiers, and no deleted dossier pending Backend purge. These are synthetic local
fixtures, not the seven dossiers reported on production.

## LLM connectivity diagnosis

The Windows process inherited an unresolvable proxy hostname `http.docker.internal`.
Bypassing that proxy exposed a second local mismatch: `host.docker.internal:20128`
timed out from Windows, while `127.0.0.1:20128` was reachable. The initial local
`.env` supplied no AI2 key, so the client fell back to an unrelated OpenAI credential
and the gateway returned 401. Both live tests passed after using the running local
AI2 container's explicit LLM credential/model in memory and the Windows loopback
address. No persistent environment/configuration files were edited. A passing IDP
test alone was not treated as proof of provider availability; the direct JSON
completion test also passed.

## Reproduce

Use disposable PostgreSQL databases on an image with pgvector. Do not point these
commands at production or a developer's business database. The local E2E test uses
the Windows `ai-service/.venv/Scripts/python.exe` interpreter.

1. Set `DATABASE_URL` to a dedicated `postgresql+asyncpg` database and run
   `python -m alembic upgrade head` from `backend/`.
2. Set `AI2_PURGE_TEST_DATABASE_URL` to that database and run
   `pytest tests/integration/test_dossier_purge_local_e2e.py -q` from `backend/`.
3. For the Backend regression suite set `CI_TEST_POSTGRES_URL` to a separate
   disposable database and `LEXICON_TEST_DATABASE_URL` to a third empty database,
   matching backend-ci.yml. Run `pytest -q -m 'not ai2_local_e2e'`.
4. Set `AI2_TEST_DATABASE_URL` to a disposable PostgreSQL server, then run
   `pytest tests/test_dossier_purge_postgres.py -q` from `ai-service/`.

Machine-readable JUnit results are retained locally as `pytest-live.xml`,
`pytest-ai2-purge.xml`, `pytest-backend-ai2-e2e.xml` and
`pytest-backend-regression.xml`; they are not staged in the PR. Earlier full AI2
runs and their corrected memory/test-ID isolation failures are recorded in the
local `pytest-final.xml` / `pytest-offline.xml` artifacts. Golden outputs were not
rewritten. Recursive test-temp cleanup was previously rejected by automatic review
with "blocked by policy", so temporary directories are retained.

## Rollout and review

Review both Backend and AI2 changes. Deploy migration 0009 with the new readers and
writers before enabling purge calls; do not run an older writer after erasure is
enabled. Downgrade is refused once any tombstone exists.

Short persistence transactions share an advisory gate to order all writers and
shared-digest ownership vs purge. No LLM/embedding call holds this gate. Durable
outbox publication holds it for a bounded synchronous emitter callback, which must
not re-enter AI2 persistence; purge waits for publication already in progress.
Functional tests do not establish production throughput at higher concurrency.

Production deployment, staging verification and erasure/count audit of the seven
historical scopes require a subsequent rollout. This PR does not perform those
actions or close the issue before the rollout evidence is available.
