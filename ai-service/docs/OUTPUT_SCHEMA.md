# Canonical output

Authoritative validation schema: [output.schema.json](output.schema.json). Pydantic models live in `domain/entities.py`; public re-exports in `schemas/output.py`.

Document: `schema_version`, `document_id`, `source_file` (resolved source path), `pages`.

Page: one-based `page_number`, `input_type`, `width`, `height`, `dimension_unit` (`pt` for native, `px` for OCR), original PDF `rotation`, actual `engine`, `model`, `processing_ms`, `status`, `error`, classifier `evidence`, `lines`, `geometry_available`, `raw_markdown`, `raw_output_path`, ordered `preprocessing`, and forward affine `transform` when preprocessing ran.

Line: stable `line_id`, `text`, optional confidence in `[0,1]`, nullable `bbox`, `geometry_available`, and `words`. Word: stable `word_id`, text, optional confidence, nullable bbox and geometry flag. IDs contain document ID, one-based page and sequence, e.g. `S001-p001-l0001`, `S001-p001-w0001`. They identify output occurrences, not semantic alignment across engines.

Every bbox uses `{x1,y1,x2,y2}` in `[0,1]`, ordered corners, origin top-left of the displayed original page. PDF rotation has already been applied to coordinates; do not rotate them again when visualizing. Width/height match that frame. Preprocessed boxes have been inverse-mapped to that frame. Confidence is null when the engine does not supply it.

Unavailable geometry has `bbox: null`, `geometry_available: false`; words may be an empty list. PyMuPDF supplies native word and derived enclosing line boxes. Paddle supplies text-line geometry without invented word boxes. DeepSeek retains raw markdown and raw artifact path but no parsed grounding geometry in this version.

Page status is SUCCESS, SKIPPED or FAILED with reason. Failed page loading may retain placeholder dimensions of 1×1 because no page geometry could be read; do not use geometry from failed pages. A corrupt document can have a failed CSV row without an output JSON. Partial documents retain all readable page results.

Raw model output is stored separately beside each experiment/page. Transformers may also save its input image and upstream artifacts. DeepSeek stdout is captured in the raw directory rather than the page log. Logs themselves contain only metadata. Treat raw output, normalized predictions and reports as confidential.
