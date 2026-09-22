# AI1 Decisions Log

Records the concrete engineering decisions made while converging AI1 toward the target
architecture (see `docs/ai1-current-state.md` for the inventory these respond to). Each
entry states the decision, why, and what it leaves open.

## D1 — Canonical AI1 implementation: `ai-service/src/contract_ocr`

**Decision:** `ai-service/src/contract_ocr` is the canonical AI1 pipeline going forward.
`backend/app`'s independent OCR/table/structure stack is left untouched and not deleted;
whether/how it eventually consumes AI1's `ai1.snapshot.v1` instead of running its own OCR
is a separate, later decision, not part of this pass.

**Why:** `ai-service` is what the repo's own prior documents call "AI1" (see
`ai-service/docs/AI1_SNAPSHOT_DELIVERY_REPORT.md`, `BACKEND_CONTRACT_RESPONSE_v0.1.md`), and
it is architecturally closest to the target in every dimension that matters here: a
provenance-aware snapshot schema, a provider-agnostic OCR abstraction, an already-built
cross-page boundary resolver, and an honest benchmark harness. Confirmed with the user
before any code changed.

## D2 — Fix MIXED-page routing before anything else (Phase 2)

**Decision:** `PdfPageClassifier` now sets `requires_ocr_regions=True` for any page with
usable native text *and* heavy image coverage (MIXED), and `ProcessDocument` gates the
native-only fast path on that flag, not on `usable_text` alone.

**Why:** This was a live, silent-data-loss bug matching the task spec's own named example
almost verbatim: a page with a usable text layer and an unrelated scanned/stamped image
overlay was read as pure native text, discarding the image entirely. Fixed as the very
first code change since every later phase's correctness assumes routing is sound.

**Left open:** MIXED pages now get a *full-page* OCR re-read when an engine is available,
not true sub-page region compositing (native text kept where genuinely native, OCR only
on the image-covered sub-region). That is the "region routing" cell of the target
pipeline diagram and is deferred — full-page re-OCR is strictly safer than the prior
behavior and a complete, honest increment on its own; region-level compositing is future
work, not a rushed partial one.

## D3 — Add `GeometryProvenance` as a hard, validated field (Phase 3)

**Decision:** `Word`, `Line`, `Cell`, `Table` (internal, `domain/entities.py`) and their
snapshot mirrors (`domain/snapshot.py`) all carry `geometry_provenance: MEASURED | DERIVED
| CLAIMED`, enforced by a model validator: a bbox and its provenance must be set together
or not at all. This is not advisory — omitting one when the other is present raises a
`ValidationError` (see the positive-control tests in `tests/unit/test_core.py` and
`tests/integration/test_build_snapshot.py`).

**Why:** Task section 6 is one of the most repeated non-negotiables in the spec, and
"do not silently convert DERIVED to MEASURED" is much easier to violate by omission than
by explicit code, so it needed to be a schema-level gate, not a convention.

**Concrete assignments decided:**

- PyMuPDF native word bbox: `MEASURED` (direct PDF glyph rect).
- PyMuPDF native line bbox: `DERIVED` (union of its own measured word boxes) — same
  reasoning the spec itself uses for "clause bbox = union(line boxes)", applied one level
  down.
- PaddleOCR line bbox: `MEASURED` (Paddle's own text-detector polygon, not a union of
  anything this codebase computed — Paddle does not currently supply word-level boxes).
- `word_adapters.vision.VisionAdapter`: already correct by construction before this pass —
  every word's bbox is the caller-supplied crop/cell region, never a model-reported
  coordinate. Not yet carrying an explicit `geometry_provenance` field since that pipeline
  (`table_reconstruct`) is not wired into the live snapshot yet (see D5); noted here so it
  is not forgotten when it is.
- Native table cells (PyMuPDF `find_tables()`): `MEASURED` (a direct detector output, same
  reasoning as Paddle's line bbox).

## D4 — Clause/section hierarchy: reuse `reconstruction`'s parser, not its whole pipeline (Phase 4)

**Decision:** New `application/use_cases/build_structure.py` calls
`reconstruction.clause_parser.parse_marker` and `reconstruction.hierarchy_builder.
build_hierarchy` directly — both pure, already-tested functions — building one
`LogicalSegment` per real OCR line, in-page only. It does **not** invoke
`reconstruction.pipeline.reconstruct_document` (the full boundary-resolution pipeline with
rule engine + LLM fallback), because that pipeline operates on a `Block`-based page shape
(`reconstruction.schemas.page.Page`) that nothing in the live pipeline produces, and
building that adapter is a materially larger effort than reusing the two leaf functions.

**Why:** `reconstruct_document` was one of the highest-value "unused but valuable modules"
found in Phase 0 (fully tested, has its own README, implements exactly the hard-guard →
score → resolver → decision pattern the target spec asks for) but wiring the *entire*
pipeline in one pass, including its cross-page LLM-assisted boundary resolution, was judged
too large a single change to land safely and test thoroughly in this pass. Reusing just the
marker parser and tree builder gives a complete, correct, well-tested capability today
(within-page hierarchy, real citations) without half-implementing the cross-page part.

**Left open:** A clause whose body genuinely continues across a page break is **not**
spliced into one node — it currently surfaces as two separate nodes under whichever clause
was open on each page. This is the same class of problem as cross-page table continuity
(section 11) and should be solved by the same mechanism when that is built, most likely by
finally building the `Block`-shape adapter and using `reconstruct_document`'s boundary
resolver for both structure and tables at once, rather than solving cross-page structure
and cross-page tables as two unrelated features.

**Also discovered (not a decision, a fact worth recording):** `clause_parser._SECTION_RE`
requires real Vietnamese diacritics ("Điều"/"ĐIỀU") or the English forms ("Article"/
"Section") — a diacritic-stripped scan ("Dieu") is not recognized and falls through as
`UNMARKED` body text rather than an `ARTICLE`. Khoản numbers must repeat the article number
as a dotted prefix ("1.1" under "Điều 1"), not reset per-article ("1.", "2." starting
over) — the latter is parsed as an unrelated top-level marker. Both are real, pre-existing
limitations of the reused module, not something this phase changed; surfaced here so a
future session doesn't waste time re-discovering them.

## D5 — Tables: native (PyMuPDF `find_tables()`) first; OCR-page detection deferred whole (Phase 5, partial)

**Decision:** `PyMuPDFExtractor` now also runs PyMuPDF's own `find_tables()` on every
native page and attaches the result as internal `Table`/`Row`/`Cell` objects;
`BuildSnapshot` converts these into the snapshot and sets an explicit `SnapshotPage.
table_status`: `DETECTED` (tables present), `NOT_PRESENT` (checked a TEXT_LAYER page, found
none), or `NOT_CHECKED` (SCANNED_OCR/MIXED — no detector exists for these yet). This status
field did not exist before this pass; it is a schema addition specifically so an empty
`tables[]` can never be misread as "no table" when detection never actually ran (section
15).

**Why not also wire the OCR-page path this pass:** two separate, already-built table
systems exist in `ai-service` for the word/bbox case —
`table_reconstruct/`+`word_adapters/` (geometry-first, built in tandem with `backend/`'s
own table logic per git history) and `reconstruction/table_merger.py` (markdown/pipe-text
based, part of the disconnected `reconstruction/` package). Neither has a fragment/table-
*region* detector in front of it — both assume "here is a `Fragment`/set of `table_row`
blocks that is already known to be a table," which nothing in this codebase currently
produces for OCR'd pages. Building that detector from scratch to a quality bar comparable
to `backend/app/document_processing.py`'s (hardened over 5+ recent commits against real
scanned contracts) is a substantial, real-scan-validation-dependent effort in its own
right, and doing it hastily would risk exactly the "half-finished implementation" and "yet
another table stack" outcomes the task spec explicitly warns against. Native detection
alone is a complete, real, fully-tested capability; it was shipped on its own rather than
alongside a rushed OCR-page detector.

**`TableStatus` intentionally omits `STRUCTURE_UNAVAILABLE`/`NEEDS_REVIEW`/`FAILED`** from
the target design's full state list for the same reason: nothing in this codebase can
produce them honestly yet (no partial-reconstruction recovery path, no gray-zone agent).
Add them when — and only when — something real can set them.

**Left open, in priority order for the next pass:**

1. Decide which of `table_reconstruct`/`word_adapters` vs `reconstruction/table_merger.py`
   becomes the OCR-page table engine (leaning `table_reconstruct`, since it is geometry-
   first and matches this task's bbox-provenance priorities better than markdown-parsing —
   see `docs/ai1-current-state.md` section 9 — but this needs its own design pass, not a
   snap judgment made alongside unrelated work).
2. Build the fragment/table-region detector feeding it (deterministic first: ruling lines
   for bordered tables, column/whitespace-gap analysis for borderless — task section 9).
3. Cross-page table continuity: hard guards → deterministic score → gray-zone LLM agent →
   merge/split/needs-review (task section 11-12). `backend/app/table_continuity.py`
   already implements a working instance of this pattern and is worth studying before
   building AI1's own, rather than designing it from zero.

## D7 — Scanned-page bordered tables: ruling-line grid detection, not word alignment (Phase 5 continued)

**Decision:** New `infrastructure/image/table_grid.py` detects bordered-table regions
directly from the rendered page's pixels (grayscale → Otsu threshold → morphological
opening with wide horizontal/tall vertical kernels → contour regions → row/column ruling-
line positions within each region), with no dependency on OCR output at all. New
`application/use_cases/extract_scanned_tables.py` then assigns each detected cell's text
from whichever already-recognized OCR line's bbox center falls inside it — **no new OCR
calls are issued**, it reuses the same page-level recognition that already ran. Wired into
`ProcessDocument.run_ocr_job` for every SCANNED_OCR/MIXED page; `BuildSnapshot` no longer
special-cases these input types away from `_build_tables` (D5's `NOT_CHECKED` short-
circuit for non-TEXT_LAYER pages is gone — a detector now runs for every input type).

**Why ruling-line detection instead of finally wiring `table_reconstruct`:** Checked
first, concretely: neither scanned-page word source actually wired into this codebase
produces word-level bbox. `infrastructure/ocr/paddle_ocr.py`'s `PaddleOCREngine` and
`word_adapters/ocr.py`'s `OcrAdapter` (the latter's own docstring says so explicitly) both
detect at **line** granularity only. `table_reconstruct.detect_column_bounds` fundamentally
needs multiple words per row at distinct x-positions to find column gaps — with only one
line-bbox per row, every row would resolve to exactly one column, a degenerate, silently-
wrong result. Wiring `table_reconstruct` today would have been connecting an unused module
to input it cannot actually do its job on — not a real capability, just a facade. Ruling-
line detection needs no word-level input at all, so it sidesteps the constraint entirely
and is a complete, real capability today. (`table_reconstruct` remains the right answer for
*borderless* tables once genuine word-level scanned OCR output exists — still open, see D5.)

**Cost tradeoff decided:** reusing already-recognized line text (bbox-center-in-cell
matching) instead of cropping and re-running OCR on every individual cell. The latter is
what task section 17 literally describes ("crop cell -> re-OCR cell") and would likely be
more accurate for multi-word cells, but at a real cost: Paddle-CPU is already documented as
tens of seconds to minutes per *page*; a table with 100 cells would mean 100 extra engine
calls per page. Reuse is free and was judged the better "smallest implementation" call for
this pass; per-cell re-OCR (or a vision-backed version of it) is a natural candidate to add
later as a *targeted recovery* step (task section 17) specifically for cells a first pass
leaves empty or low-confidence, rather than the default path for every cell.

**Real-scan sanity check (not a benchmark — no ground truth, no accuracy number):** swept
all 30 real sample PDFs already in `ai-service/data/raw/` (n=435 pages total) end to end.
32 grid detections across 9 documents, concentrated in `data/raw/hard_cases/` files whose
own filenames declare them purpose-built table test fixtures (e.g.
`Hop_dong_scan_bang_lien_trang_OCR_test.pdf` = "table across pages OCR test",
`744287578-Hợp-đồng.pdf` — also the exact file `backend/app/tables.py`'s own code comments
cite as a real hard case it was hardened against). Detected column counts were consistent
page-to-page within each multi-page hit (e.g. 7,7,7,7,7 and 8,8,8), which is what a real
single logical table spanning several pages should look like — a meaningful positive
signal, not a fabricated accuracy claim. `data/raw/scanned_clean/` and `scanned_bad/`
produced zero hits on the pages checked; unknown whether that's a true negative (no tables
on those pages) or a detector miss — no ground truth exists to tell the difference (see
Phase 8, still blocked on annotation).

**Left open:**

- Borderless scanned tables: still undetected (needs word-level OCR, see above).
- A grid larger than `MAX_CELLS_PER_TABLE` (300; every real hit above topped out at 104)
  is silently skipped rather than reconstructed — not yet surfaced as an explicit
  `STRUCTURE_UNAVAILABLE` page signal. `TableStatus` was deliberately *not* extended with
  that value this pass (D5's reasoning still applies: nothing else can produce it honestly
  yet either); add it together with the validation/recovery phase, not as a one-off here.
- `line_length_divisor`/kernel-size defaults are untuned against real scans — the sweep
  above is a sanity check that the detector isn't obviously broken, not a calibration.
- Cross-page table continuity (joining the per-page grids the sweep above found into one
  logical table) is not implemented — see D5's priority list.

## D8 — Cross-page table continuity: deterministic only, no LLM gray-zone agent (Phase 5 continued)

**Decision:** New `application/use_cases/table_continuity.py::link_continuities` runs
hard guards (column-count mismatch, tables not positioned at their page's own bottom/top
edge) then a deterministic score (column match + edge proximity + whether the header
repeats verbatim) to decide `MERGE`/`SPLIT`/`NEEDS_REVIEW` between the last table on one
page and the first table on the next. **No LLM call anywhere in this path** — confirmed
explicitly with the user before building it, given the real API-cost/design implications.
Anything the score doesn't confidently resolve becomes `NEEDS_REVIEW`, never a guess.
Wired into `BuildSnapshot` as a new document-level `DocumentSnapshot.table_continuity:
list[TableContinuityLink]`.

**Does not merge rows/cells.** Only records a decision + reason codes linking two
page-level `Table` objects by id. This mirrors `backend/app/tables.py`'s own
`link_continuations`, which independently made the identical "link, don't merge" call for
the same real problem — worth noting as convergent validation of the approach, not just a
borrowed idea. Physically stitching a merged table's rows together (and deciding what that
even means for cell provenance across two different source pages) is left to whatever
consumes the link.

**Left open:** the LLM gray-zone agent itself (deferred by explicit user choice, not
forgotten); the three "hard SPLIT" guards from the target design this pass has no signal
for yet (document changed, annex boundary, strong new table heading — none of these have
an existing detector in AI1 to feed them); and cross-page *structural* (clause) continuity,
which is the analogous gap from D4 and could reasonably share this same hard-guard →
score → NEEDS_REVIEW shape once tackled.

## D6 — Positive controls for every new validation gate (task section 26)

**Decision:** Every schema-level consistency gate added this pass (`geometry_provenance`
required alongside bbox, on `Word`/`Line`/`Cell`/`Table`/`StructuralNode` internally and on
`SnapshotWord`/`SnapshotLine`/`Cell`/`StructuralNode`/`SnapshotPage.table_status`
externally) ships with a test that deliberately constructs the violation and asserts it is
rejected, not just a test that well-formed input passes.

**Why:** Explicitly required by the task spec, and cheap to do at the point a gate is
introduced versus retrofitting later.
