# Canonical output

This is the internal benchmark schema (`Document`/`Page`/`Line`/`Word`), used to compare OCR engines. It is **not** the contract handed off to AI2 — that is `ai1.snapshot.v1`, a separate, frozen shape documented in [AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md](AI1_OCR_SNAPSHOT_HANDOFF_RESPONSE.md) and [ai1.snapshot.v1.schema.json](ai1.snapshot.v1.schema.json) (models in `domain/snapshot.py`), built from this one via `application/use_cases/build_snapshot.py`. The two evolve independently on purpose.

Authoritative validation schema: [output.schema.json](output.schema.json). Pydantic models live in `domain/entities.py`; public re-exports in `schemas/output.py`.

Document: `schema_version`, `document_id`, `source_file` (resolved source path), `pages`.

Page: one-based `page_number`, `input_type`, `width`, `height`, `dimension_unit` (`pt` for native, `px` for OCR), original PDF `rotation`, actual `engine`, `model`, `processing_ms`, `status`, `error`, classifier `evidence`, `lines`, `geometry_available`, `raw_markdown`, `raw_output_path`, ordered `preprocessing`, and forward affine `transform` when preprocessing ran.

Line: stable `line_id`, `text`, optional confidence in `[0,1]`, nullable `bbox`, `geometry_available`, and `words`. Word: stable `word_id`, text, optional confidence, nullable bbox and geometry flag. IDs contain document ID, one-based page and sequence, e.g. `S001-p001-l0001`, `S001-p001-w0001`. They identify output occurrences, not semantic alignment across engines.

Every bbox uses `{x1,y1,x2,y2}` in `[0,1]`, ordered corners, origin top-left of the displayed original page. PDF rotation has already been applied to coordinates; do not rotate them again when visualizing. Width/height match that frame. Preprocessed boxes have been inverse-mapped to that frame. Confidence is null when the engine does not supply it.

Unavailable geometry has `bbox: null`, `geometry_available: false`; words may be an empty list. PyMuPDF supplies native word and derived enclosing line boxes. Each `OCREngine` adapter supplies whatever detection granularity it actually measures — a line-only detector produces text-line geometry without invented word boxes, never a guessed one; an adapter with no grounded coordinates at all (e.g. one that only returns raw markdown/text) retains that raw output but no parsed geometry.

Page status is SUCCESS, SKIPPED or FAILED with reason. Failed page loading may retain placeholder dimensions of 1×1 because no page geometry could be read; do not use geometry from failed pages. A corrupt document can have a failed CSV row without an output JSON. Partial documents retain all readable page results.

Raw model output is stored separately beside each experiment/page. An adapter's own stdout, if any, is captured in the raw directory rather than the page log. Logs themselves contain only metadata. Treat raw output, normalized predictions and reports as confidential.
