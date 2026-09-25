# AI2-12 - Review and release gate

## Source of truth

The current integration input is the actual OCR-lab `ai1.snapshot.v1`
output, not the older canonical backend snapshot shape:

- `C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json`
- `C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json`
- profile schema: `docs/contracts/ai1.snapshot.v1.ocr-lab.schema.json`

The adapter keeps the producer payload immutable, preserves raw evidence, and
maps it into the internal AI2 record. The two documents are isolated by
`dossier_id:document_id`; AI2 does not infer cross-document findings.

## Current producer facts [OBSERVED 2026-09-23]

The two inputs have the same `dossier_id=dossier-001` but different
`document_id` and `source_digest`, so the package must keep
`relation_policy=INDEPENDENT`.

| Input | Observed structure | Release implication |
|---|---|---|
| `doc-001` | `TEXT_LAYER`, 8 pages, 69 root nodes, 358 lines, 3633 words, 1 table under `pages[*].tables`, 0 continuity records | root node geometry is `DERIVED` |
| `doc-002` | `SCANNED_OCR`, 4 pages, 7 root nodes, 48 lines, 0 words, 3 tables under `pages[*].tables`, 2 continuity records | table geometry is `MEASURED`; some cell geometry is `CLAIMED` |

The producer payload has no authoritative root `tables` collection. Tables are
nested under pages, cells under rows, and continuity records at
`table_continuity`. The release checks must validate that topology and must not
interpret `word_count=0` on a scanned OCR document as proof that the document
has no usable text.

## Exact two-file replay [OBSERVED 2026-09-23]

Command used from `ai-service/`:

```powershell
.venv\Scripts\python.exe scripts/run_ai2_ai1_files.py `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json" `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json" `
  --strict --output artifacts/ai2-two-input-replay-20260923.json
```

Observed report: `overall_review_state=NEEDS_REVIEW`, two jobs
`SUCCEEDED`, `batch_issues=0`, `cross_document_findings=[]`. `doc-001` returned
126 events, 0 facts, and 2 evidence issues. `doc-002` returned 34 facts, 20
events, 1 context finding, and 6 evidence issues. Exit code `0` means the
machine completed; it does not promote the review state to `PASS`.

## Review findings fixed

1. OCR-lab root `nodes` and `table_continuity` are now consumed directly.
2. `sha256:<hex>` digests, duplicate raw node IDs, missing parents, sparse
   tables, continuity conflicts, and claimed/derived geometry are surfaced as
   review issues.
3. A failed extraction unit no longer discards successful units. Processing
   budget exhaustion falls back to bounded local extraction and returns
   `SUCCEEDED + NEEDS_REVIEW` with `BUDGET_EXCEEDED`.
4. Citation checks validate the exact page/table source span and node/page
   scope. A structural node's citation is not incorrectly required to be a
   substring of the node preview text.
5. The public package boundary is versioned as `vsf-ai2` `1.0.0`, API
   `ai2.package.v1`, with `process_files()` and `process_payloads()`.

## Release commands

From `ai-service/`:

```powershell
.venv\Scripts\python.exe -m pytest -o addopts='' -q -m "not live" --basetemp ..\tmp\ai2-release-basetemp
python scripts/run_ai2_ai1_files.py `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json" `
  --input "C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json" `
  --strict --output artifacts/ai2-ai1-replay.json
python scripts/live_eval.py --mode live --vector-mode off --strict `
  --review-output --output artifacts/ai2-live-audit
```

The first two commands are the offline gate. The live command is opt-in and
must be reported as `NOT_RUN` when credentials/provider are unavailable; that
state is not a live pass. If a live run starts and has machine failures,
forbidden claims, or invalid citations, the release decision is `BLOCKED` or
`FAIL`, never downgraded to `NOT_RUN`. `NEEDS_REVIEW` remains an intended
safety state and is never silently promoted to `PASS`.

## Baseline only (2026-09-23)

- offline suite: `198 passed, 6 deselected` with a workspace `--basetemp`; this
  is a dirty-tree baseline, not post-cook release evidence
- the exact two-file replay is recorded above and was run without LLM
- previous live/deterministic scores are not a current release claim until the
  corresponding command and artifact are rerun and attached to this gate

The two real OCR-lab files remain `NEEDS_REVIEW` because the current handoff
contains evidence issues. This is the intended fail-safe result, not a hidden
promotion to `PASS`.

All changes in this review are local only. No Git commit or push is part of the
release gate.
