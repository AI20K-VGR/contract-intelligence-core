# Issue #131 — implementation and local verification

## Result

The signed AI2 dossier deletion API and its Backend integration are implemented.
Purge uses PostgreSQL + pgvector; no SQLite deletion path is introduced. The user
requested local verification before deployment. No staging/production data was
read or deleted. After rollout, the sweeper automatically purges historical completed
scopes missing AI2 evidence, including the seven reported production scopes.

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

### PR #132 review revision (19/10)

- AI2 targeted regression: **87 passed**, covering PostgreSQL jobs/graph/pairs,
  the **21 purge acceptance cases**, Kafka worker/results and job progress.
- Backend focused regression: **19 passed**, including **4 local-only E2E** cases
  using real HTTP + migrated PostgreSQL. Historical completed ledgers are tested
  both directly and after transport failure; prior Backend counts survive retry.
- Full Backend regression: **1003 passed, 14 deselected**, with separate disposable
  PostgreSQL databases for CI invariants and lexicon; local E2E ran separately above.
- New PostgreSQL checks prove five writers overlap while another writer holds its
  gate, purge waits for an in-flight writer, competing owners cannot cross dossiers,
  and a progress update does not pass unchanged 6 MiB wire JSON for parsing while
  changed digest pins still register references. Kafka deletion before publication
  emits the terminal deletion code and commits only after successful publication.
- Ruff on changed Python files, Backend MyPy and `git diff --check` pass.

Local synthetic lock comparison (PostgreSQL 16 + pgvector, five concurrent job
INSERTs per batch, three batches per mode, each job has 3 MiB request JSON + 3 MiB
wire JSON; only the advisory gate mode changes):

| Gate mode | Batch durations (seconds) | Mean gate wait | Maximum gate wait |
|---|---|---|---|
| Exclusive writers | 0.825 / 0.700 / 0.506 | 0.278 s | 0.661 s |
| Shared writers | 0.274 / 0.322 / 0.197 | 0.006 s | 0.011 s |

These are local synthetic measurements, not staging throughput or a 202-page
end-to-end processing run. Initial JSON decoding still costs CPU; shared gates
remove global writer serialization. No production/staging data was accessed.
The unmerged migration 0009 is revised in place; acceptance/E2E used fresh databases.

### Original implementation baseline

| Area | Evidence |
|---|---|
| LLM live | **2 passed** using the existing local gateway's configured credential; no key was printed, committed or changed |
| AI2 acceptance | **17 passed** on real PostgreSQL 16 + pgvector, including upgrade from 0008 with existing content, shared/historical digests, tenant isolation, late writers, cancellation, audit, cleanup/recovery and claimed outbox |
| Backend → AI2 E2E (local only; excluded from CI) | **2 passed**: real AI2 HTTP process, migrated PostgreSQL, authenticated Backend DELETE, two files and OCR, ledger evidence, failed transport + sweeper retry, another dossier preserved, AI2 restart and idempotent DELETE |
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
writers before deploying Backend; do not run an older writer after erasure.
Backend calls purge immediately after deployment; there is no enable flag.
If AI2 lacks the endpoint, purge fails and the sweeper retries. Downgrade is
refused once any tombstone exists.

Short persistence transactions take a shared advisory gate; purge takes the same
gate exclusively. Writers for different resources can overlap; immutable ownership
uses resource-specific locks. No LLM/embedding call holds this gate. Durable
outbox publication holds it for a bounded synchronous emitter callback, which must
not re-enter AI2 persistence; purge waits for publication already in progress.
Functional tests do not establish production throughput at higher concurrency.

Backend erases its DB content before calling AI2. Only both successful phases
complete deletion. Completed historical ledgers without AI2 evidence run only the
AI2 phase, preserving prior Backend counts even after a failed retry.

Production deployment, staging verification and count audit of the seven historical
scopes require a subsequent rollout. The sweeper performs historical erasure after
deployment; this local change does not deploy or close the issue. Backend (Chương)
approved DEC #131 / §7 on 19/10 in
[review 5566790702](https://github.com/AI20K-VGR/contract-intelligence-core/pull/132#pullrequestreview-5566790702).
The documents now record that approval.

## Follow-up review revision (19/10)

Merged the latest develop, including #128, #129, #133 and #134. Historical AI2
backfill now retains existing dossier `purge_completed_at` and ledger `purged_at`,
including transport failures and subsequent successful retries. A first-time purge
still records its completion time. Unit and local HTTP/PostgreSQL E2E assertions
use a seven-day-old timestamp to detect accidental replacement by the current time.
Staging performance with 202 pages / pairs concurrency 5 and the seven production
scope audit remain rollout work, as the reviewers requested.

Validation on this revision: **19 Backend focused tests passed**, including all
**4 local HTTP/PostgreSQL E2E cases** with timestamp-preservation assertions;
**15 AI1 golden/structure + Kafka tests passed** without API keys or AI2 database.
Backend Ruff, MyPy and `git diff --check` passed. The earlier 1003-test Backend
regression and 87-test AI2 run above belong to the previous review revision.
