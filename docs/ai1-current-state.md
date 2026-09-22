# AI1 Current-State Inventory

Produced per the "inspect before coding" rule. No source files were changed to produce this
document. Everything below was verified by reading the actual code, running discovery commands
against the actual working tree, and checking actual tool/dependency availability in this
environment — not inferred from file names or prior docs alone (several claims in existing docs
turned out to be stale; noted where found).

## 0. The central fact

**This repository contains two independent, non-communicating implementations of AI1's scope**
(OCR → structure → tables → evidence), plus **a third, internally-disconnected implementation
inside one of the two**. None of the three is "wrong" — each was built by a different
team/session for a real reason — but the repo has never converged on one. That convergence is
what phases 1+ of this task are actually about; this document is the map needed to do it without
guessing.

| # | Implementation | Where | Wired to a runtime entry point? |
|---|---|---|---|
| A | Backend's own OCR/table/structure pipeline | `backend/app/document_processing.py`, `tables.py`, `table_continuity.py`, `structure.py` | **Yes — this is what actually runs in production** (FastAPI + worker) |
| B | AI1's benchmark-shaped pipeline | `ai-service/src/contract_ocr/application/use_cases/{process_document,build_snapshot}.py` + CLI | Yes, but only for OCR text/geometry — produces the `ai1.snapshot.v1` handoff contract with `blocks[]`/`tables[]` **always empty** |
| C | AI1's reconstruction pipeline (structure + tables) | `ai-service/src/contract_ocr/reconstruction/` | **No.** Fully built, fully tested, has its own README — called from nowhere except its own tests |
| C′ | AI1's geometry-based table pipeline | `ai-service/src/contract_ocr/table_reconstruct/` + `word_adapters/` | **No.** Also fully built and tested, also called from nowhere except its own tests, and **not the same table algorithm as C** |

The rest of this document explains each row, then proposes what "canonical" should mean given
this task's scope (AI1 = the OCR/IDP layer, distinct from "Backend" and "AI2" per the repo's own
existing team-boundary docs — see §1).

## 1. What "AI1" refers to in this repository

This isn't an assumption — the repo already has role-scoped documents that settle it:

- `ai-service/docs/AI1_SNAPSHOT_DELIVERY_REPORT.md`: *"Người gửi: AI1 (AI Engineer, OCR) | Người
  nhận: AI2"* — i.e. the team that owns `ai-service/` self-identifies as **AI1**.
- `ai-service/docs/BACKEND_CONTRACT_RESPONSE_v0.1.md`: AI1 replying to a **separate** Backend
  team's contract document (`backend-ai-contract-v2.md`), confirming AI1 and Backend are meant to
  be two services talking over an async HTTP contract (`POST /extract` + callback), not one
  codebase.
- `ai-service/README.md` §10: the `ai1.snapshot.v1` schema already exists and is explicitly the
  "OCR Snapshot" contract this task's §19 describes.

**Conclusion:** "AI1" in this task = `ai-service/src/contract_ocr`. "Backend" = `backend/app`,
a separate, already-running service that (per §3 below) currently does **not** consume anything
AI1 produces — it built its own parallel OCR stack instead, for a documented reason (§4).

## 2. Current OCR entry points (all of them)

| Entry point | Command | What it runs |
|---|---|---|
| Backend HTTP API + worker (**live, production-shaped**) | `uvicorn app.api:app` / `python -m app.worker` | `backend/app/document_processing.py:process_page` — pytesseract + PyMuPDF + optional GPT-vision, per page, via a Postgres-backed task queue |
| AI1 CLI `snapshot` | `contract-ocr snapshot --file x.pdf ...` | `ProcessDocument` → `BuildSnapshot`, produces `ai1.snapshot.v1` JSON. **No structure, no tables.** |
| AI1 CLI `benchmark` | `contract-ocr benchmark --manifest ...` | `ProcessDocument` → `RunBenchmark`, produces engine-comparison metrics (CER/WER/bbox IoU) against labeled ground truth |
| AI1 web API (manual test tool) | `scripts/serve_backend.py` → `POST /api/ocr`, `POST /api/ai2/analyze` | Same `ProcessDocument`, plus `extract_ai2_facts.py` for a demo classification/clause/fact/citation layer. Explicitly documented as a **manual test tool, not a product**, and CORS-open/no-auth by design |
| AI1 reconstruction pipeline | `from contract_ocr.reconstruction import reconstruct_document` | Not exposed by *any* CLI/HTTP entry point. Only reachable from Python or its own tests |

Nothing currently calls AI1's `contract_ocr` package from `backend/`. Confirmed by dependency
inspection (`backend/pyproject.toml` has no path/git dependency on `ai-service`) and by grep
(`contract_ocr` appears in exactly one backend file, `document_processing.py:228`, in a comment —
not an import).

## 3. Duplicate implementations, in detail

### 3.1 Table reconstruction — four separate algorithms exist

1. **`backend/app/document_processing.py`** (`_find_tables`, `_ocr_tables`, ~900 lines) +
   **`backend/app/tables.py`** (`link_continuations`, `build_logical_tables`) +
   **`backend/app/table_continuity.py`** (the new LLM "Table Continuity Agent", DeepSeek-backed,
   opt-in per job). Word-bbox/column-alignment based. Heavily hardened against real scanned
   documents — comments cite specific real files by name (e.g. a 744287578-*.pdf edge case at
   `tables.py:30-35`) and specific bugs fixed in the last 5 commits on this branch. **This is the
   only one of the four that is live.**
2. **`ai-service/src/contract_ocr/table_reconstruct/`** (`columns.py`, `lines.py`, `rows.py`,
   `merge.py`, `numbers.py`, `validate.py`) + **`ai-service/src/contract_ocr/word_adapters/`**
   (`native.py`, `ocr.py`, `vision.py`, `routing.py`, `escalation.py`). Also word-bbox/column
   based. Git history shows this was built *together* with backend's version in the same commit
   (`940a313 feat(ai,backend): pure-logic table reconstruction + OCR word-source adapters`) —
   i.e. this is a **parallel, not-yet-reconciled port** of the same idea into AI1's own package.
   Has its own test suite (`ai-service/tests/table_reconstruct/`, `tests/word_adapters/`) but no
   caller outside those tests.
3. **`ai-service/src/contract_ocr/reconstruction/table_merger.py`**. A *third*, unrelated
   algorithm: parses pipe-delimited (`|`) markdown-style table rows out of `Block` objects
   (`reconstruction/schemas/block.py`), not word bboxes. This is the shape a vision/markdown OCR
   engine (e.g. DeepSeek's `raw_markdown`) would naturally produce, not the shape
   `ProcessDocument` currently produces. Cross-page continuation logic here is genuinely more
   sophisticated than table 1/2's heuristic (hard guards → rule engine → LLM resolver →
   merge/split/needs-review — this *is* the exact pattern the task spec asks for in §11-12) but
   it is fed by nothing real.
4. Neither AI1 use case (`build_snapshot.py`) calls either of AI1's own table systems — it
   hard-codes `tables=[]` (see `build_snapshot.py:9-10`, explicitly disclosed as a known gap).

### 3.2 Clause/structure hierarchy — two separate algorithms

- `backend/app/structure.py`: regex-based Điều/Khoản/Điểm parser (~115 lines), diacritic-
  insensitive, battle-tested, wired into the live worker.
- `ai-service/src/contract_ocr/reconstruction/clause_parser.py` +
  `reconstruction/hierarchy_builder.py`: a more general marker parser + tree builder, part of the
  same disconnected `reconstruction/` package as §3.1 item 3. Not wired to anything live.

### 3.3 OCR engine abstraction — AI1 already has exactly what §4 of this task asks for

`ai-service/src/contract_ocr/word_adapters/protocols.py` (`WordSource`) and
`application/ports/ocr_engine.py` (`OCREngine`) are already a clean provider-agnostic contract,
with `NativeAdapter` / `OcrAdapter` / `VisionAdapter` implementations and a routing/escalation
layer (`routing.choose_adapter`, `EscalationController`) that already encodes "vision is a bounded
fallback, not primary" (task §18). Backend, by contrast, branches on `settings.ocr_engine ==
"gpt_vision"` directly inside `document_processing.py` with pytesseract and the OpenAI SDK called
inline — provider-specific code is not isolated behind an abstraction there.

### 3.4 OCRSnapshot — one schema exists, is not fully populated, and is not what Backend emits

`ai-service/src/contract_ocr/domain/snapshot.py` (`DocumentSnapshot`, `SnapshotPage`,
`SnapshotLine`, `SnapshotWord`) implements `ai1.snapshot.v1` almost exactly as task §19 describes:
versioned, per-word/line bbox (`bbox_normalized`, 0-1, top-left origin), explicit `PageStatus`
states (`SUCCESS`/`PARTIAL`/`FAILED`, plus an explicit `blank_page` warning rather than treating
an empty page as "no content" — this already satisfies task §15's core requirement). **Gaps,
disclosed by AI1 in their own delivery report:** `blocks[]` and `tables[]` are always `[]`; word
bbox exists for native/vision text but only line-level bbox exists for Paddle-routed pages.

Backend's worker (`backend/app/worker.py:publish_ready`) independently assembles its own result
JSON (`"schema_version": "0.1"`) with its own shape (`pages`, `clauses`, `tables`, `facts`,
`findings`, `citations`) — structurally similar in spirit (explicit `is_partial`, `coverage`,
`limitations`, real citations with source-hash verification) but it is **not** `ai1.snapshot.v1`
and does not reuse its Pydantic models. AI2's actual current implementation
(`ai-service/src/contract_ocr/application/use_cases/extract_ai2_facts.py`) reads AI1's *internal*
`Document`/`Page` objects directly (pre-snapshot), not the `ai1.snapshot.v1` handoff file — so the
one schema meant to decouple AI1 from its consumers is not actually being used as the interface
by the one downstream consumer that exists in this repo.

## 4. Why this happened (not a mistake — a documented interim decision)

`ai-service/docs/BACKEND_CONTRACT_RESPONSE_v0.1.md` §6 (AI1 writing to Backend, dated during
Sprint 1): *"Codebase hiện tại là OCR Lab (công cụ benchmark engine), **chưa** phải bản triển khai
contract này"* — AI1 told Backend, explicitly, that `ai-service` was a benchmarking spike, not a
production service, and listed exactly what was missing (async queue, callback client, `is_sensitive`
enforcement, cascade engine fallback, structuring layer). Backend evidently could not wait, and
built a complete vertical slice (`backend/app/document_processing.py:228`'s comment states this
outright: *"these are two independent projects in this repo by design"*). That was a reasonable
Sprint-1 call. It is exactly the state this task now asks to end.

## 5. What actually runs, today, in this environment

Verified directly (not from stale docs — `docs/IMPLEMENTATION_STATUS.md` claims Tesseract is not
in PATH and Docker is unavailable; both are **wrong** in this environment as of this session):

- `tesseract 5.5.3` — available.
- `docker 28.4.0` — available.
- `ai-service/.env` has non-empty `OPENAI_API_KEY`, `GEMINI_API_KEY`, `DEEPSEEK_API_KEY` (values
  not inspected; presence only — validity not yet confirmed by a live call).
- `backend/.env` has a non-empty `CI_OPENAI_API_KEY`.
- `ai-service/data/raw/{digital,scanned_clean,scanned_bad,hard_cases}` already contain **30 real
  Vietnamese contract-template PDFs** (17/3/5/5), matching the README's Sprint-1 target
  distribution — gitignored, correctly not committed. **However `ai-service/data/manifest.csv`
  does not exist yet** (only `manifest.example.csv`) and `ai-service/data/ground_truth/text/`
  contains only `.gitkeep` — i.e. **zero pages currently have ground truth**. The benchmark
  harness (§8 below) is real and runnable, but has never been run against this real data with
  labels, so no CER/WER/bbox-IoU number for real documents exists anywhere in this repo.
- Postgres is not confirmed running (backend needs it for the API/worker/DB-backed tests); not
  yet checked in this session.

## 6. Existing tests

| Suite | Files | Notes |
|---|---|---|
| `ai-service/tests/` | 32 files across `unit/`, `integration/`, `reconstruction/`, `table_reconstruct/`, `word_adapters/` | Reconstruction and table_reconstruct/word_adapters both have real test coverage despite having no live caller — tests exercise the modules directly |
| `backend/tests/` | 6 files: `test_processing.py`, `test_logical_tables.py`, `test_table_continuity.py`, `test_workflow.py`, `test_corrections.py`, `conftest.py` | `test_processing.py` alone has 708 uncommitted new lines on this branch — this is where almost all current engineering effort is going |

Per `docs/IMPLEMENTATION_STATUS.md`, backend's tests use synthetic/mocked data generated at
runtime, not real scanned pages — "Mock routing không phải benchmark OCR" (mock routing is not an
OCR benchmark), which the backend team already states honestly.

## 7. Unused but valuable modules (do not rebuild these — connect them)

- `ai-service/src/contract_ocr/reconstruction/` (entire package). Implements task §8-12 almost
  exactly: hard guards → deterministic score → LLM resolver → merge/split/needs-review for
  cross-page table continuity (`pipeline.py:_build_tables`), `ReasonCode`/`ResolutionMethod`
  enums, `ReviewItem` for anything not confident, `source_blocks` provenance on every
  clause/table. Fully tested, has its own README explaining the design. **Zero integration work
  has been done to feed it real OCR output** — it consumes `reconstruction.schemas.page.Page`
  (a `Block`-based shape with `bbox`, `font_size`, `bold`, etc.) and nothing in the codebase
  currently produces that shape from `contract_ocr.domain.entities.Page` (the shape
  `ProcessDocument` actually returns).
- `ai-service/src/contract_ocr/word_adapters/` + `table_reconstruct/`. Provider-agnostic word
  source abstraction + geometry-based table reconstruction with configurable escalation to
  vision — same, again untouched by any live entry point.
- `ai-service/src/contract_ocr/infrastructure/metrics/` (`ocr_metrics.py`, `evaluation.py`) +
  `scripts/benchmark.py` + `scripts/visualize_bbox.py`. A working CER/WER/bbox-IoU benchmark
  harness with an honest "SKIPPED means unlabeled, not zero error" convention already built in
  (README §5-6). This is most of task §20-22's requirement, already implemented — it just has
  never been run against labeled real data (§5 above).
- `backend/app/table_continuity.py` (the new Table Continuity Agent, opt-in, DeepSeek-backed) is
  itself a working instance of task §11-12's "gray-zone agent" pattern — bounded input, decision-
  only output, no invented coordinates (needs re-verification against task §12's exact
  constraints once reviewed in depth, but it is not a throwaway prototype).

## 8. Missing integrations (the actual gap list)

1. No adapter from `contract_ocr.domain.entities.{Page,Line,Word}` → `reconstruction.schemas.
   page.Page` (`Block`s). Without it, `reconstruct_document()` can never run on real OCR output.
2. `BuildSnapshot` does not call `reconstruct_document()` (or `table_reconstruct`) at all —
   `blocks[]`/`tables[]` stay `[]` by construction, not by failure.
3. AI1's `ai1.snapshot.v1` is not consumed anywhere — `extract_ai2_facts.py` bypasses it and reads
   pre-snapshot internal objects instead.
4. Backend does not depend on `ai-service` at all — no shared package, no HTTP call, no shared
   schema. Two full OCR stacks are maintained independently.
5. `ai-service/data/manifest.csv` + ground truth annotations do not exist — the real 30-file
   dataset cannot currently produce a single measured accuracy number.
6. No page-classification concept matching task §3's `PageProfile` (native/scanned/mixed/
   unreadable with `image_coverage`, `reason_codes`) exists in either codebase as such —
   AI1's `PdfPageClassifier` (`application/use_cases/classify_pdf.py`, not yet read in full)
   and backend's own text/image-coverage check (`document_processing.py:_image_coverage_ratio`,
   `:1329`) both do *some* form of this independently — needs closer comparison before choosing
   or merging them (deferred to Phase 2; flagged here so it isn't missed).
7. No `GeometryProvenance` (`MEASURED`/`DERIVED`/`CLAIMED`) concept exists anywhere yet in either
   codebase under that name, though the *practice* is partially followed (e.g. AI1's snapshot
   never claims word bbox for Paddle output it didn't get). This needs to be introduced as an
   explicit field, not assumed from behavior.

## 9. Proposed canonical implementation (for confirmation — see the question below)

Given §1's finding that "AI1" = `ai-service/src/contract_ocr`, and that this package is
architecturally the closest of the three to the target in every dimension the task cares about
(provenance-aware snapshot schema, provider-agnostic OCR abstraction, a cross-page continuity
resolver with hard-guard → score → LLM → decision structure, an honest benchmark harness), the
proposed canonical AI1 implementation is:

**`ai-service/src/contract_ocr`, converged internally first** (§3.1/§3.2's `reconstruction/` vs
`table_reconstruct/`+`word_adapters/` duplication resolved — most likely by adopting
`word_adapters`+`table_reconstruct` as the word/bbox-level engine, since it's geometry-first and
matches this task's "measured bbox" priority better than markdown-parsing, and using
`reconstruction/`'s boundary-resolution *pattern* (hard guard → rule → LLM → decision) as the
cross-page/cross-boundary decision layer on top of it — but this needs a design pass, not a
snap judgment), **then wired end-to-end so `BuildSnapshot` actually populates `blocks[]`/
`tables[]`**, publishing a complete `ai1.snapshot.v1`.

**Backend's pipeline is proposed to be kept as-is and marked as a consumer-to-be**, not deleted
and not rewritten in this pass: it is live, tested against real edge cases, and serves real API
traffic. The convergence step for Backend is a *separate, later* decision — either (a) Backend
starts consuming AI1's `ai1.snapshot.v1` instead of running its own OCR, or (b) Backend's own
pipeline is explicitly declared the canonical *production* implementation and AI1's package is
re-scoped to be the benchmark/R&D harness that validates it. Both are legitimate; they are not
the same decision, and this task's own instructions ("do not create a third implementation" /
"do not delete code" / "mark duplicates deprecated") do not by themselves settle which.

## 10. Files proposed to keep vs. eventually deprecate

**Keep, extend:**
`backend/app/*` (live system — untouched for now), `ai-service/src/contract_ocr/word_adapters/*`,
`table_reconstruct/*`, `domain/snapshot.py`, `application/use_cases/{process_document,
build_snapshot,run_benchmark}.py`, `infrastructure/*`, `cli/main.py`.

**Keep, but resolve duplication before extending further:**
`ai-service/src/contract_ocr/reconstruction/*` — do not add a *third* table/structure algorithm
on top of this and `table_reconstruct/`; §9's converged design must pick which parts of
`reconstruction/` survive (its boundary-resolution/review-item pattern looks worth keeping; its
own bespoke table parser competing with `table_reconstruct/` does not need to survive in
parallel).

**Not proposed for deletion, but flagged as the actual duplication risk if left untouched:**
running two independently-evolving table/structure implementations inside `ai-service/` itself
(`reconstruction/` vs `table_reconstruct/`+`word_adapters/`) is the one place this task's "do not
create a third implementation" warning is most at risk of being violated by accident, since both
already look reasonable in isolation.

## 11. Explicit BLOCKED / NOT_RUN items

- **Ground truth annotation for the 30 real sample PDFs**: NOT_RUN. Requires human labeling
  effort (text transcription, critical-field values, bbox for a sample of pages) that cannot be
  fabricated. Blocks all of task §20's CER/WER/bbox-IoU numbers until done.
- **Vision API key validity** (OpenAI/Gemini/DeepSeek): present but unverified — first real call
  will confirm or fail this.
- **Postgres/Docker-compose live run of the full backend stack**: not yet attempted in this
  session; needs verification before claiming any backend end-to-end run succeeded.
- **DeepSeek-OCR-2 (local, GPU)**: confirmed NOT_RUN by AI1's own README — no NVIDIA GPU on the
  authoring machine; this was already honestly disclosed, not newly discovered.

## 12. Next step

This document is Phase 0/1 output only. No code was changed. §9 contains the one decision this
session cannot make unilaterally — which pipeline is canonical for which purpose — and the
answer materially changes every subsequent phase's file list. See the follow-up question posed
alongside this document.
