# Document reconstruction

Turns independently page-OCR'd blocks (`page_001.json`, `page_002.json`, ...)
into one logical document structure — a clause tree plus tables — without
re-OCRing anything and without an LLM ever rewriting a single word of the
contract.

```text
OCR = đọc nguyên văn        (OCR reads the literal text)
Reconstruction = xác định relationship   (figures out how blocks relate)
Code = merge nguyên văn     (deterministic code does any merging)
LLM = chỉ hỗ trợ case ambiguous   (LLM only classifies ambiguous boundaries)
Extraction = hiểu nội dung  (a later stage understands meaning)
Verification = đối chiếu lại source  (a later stage checks back against source)
```

## Pipeline

```text
Page OCR
   |
   v
Normalize Blocks                    (schemas/block.py, schemas/page.py)
   |
   v
Header/Footer Detection             (header_footer_detector.py)
   |
   v
Boundary Detection                  (boundary_detector.py)
   |  last 2-3 meaningful blocks of page N + first 2-3 of page N+1,
   |  plus the live DocumentState (active section/clause/list/table)
   |
   +-- Confident ("strong"/"very strong", section 13)
   |        |
   |        v
   |     Rule Engine                (rule_engine.py)
   |     -> proposes one ReconstructionAction
   |
   +-- Not confident enough
            |
            v
        LLM Resolver                (llm_resolver.py)
        -> Document Reconstruction Agent: proposes a ReconstructionAction too
            |
            v
      combine rule + LLM signals -> final confidence   (config.py)
            |
      +-----+---------------+
      |                     |
      v                     v
 requires_review=false  requires_review=true --> review_items (never merged)
      |
      v
 Deterministic Executor              (pipeline.py)
  "LLM decides relationship. Code performs mutation."
      |
 +----+-----+
 v          v
Clause    Table
Parser    Merger        (clause_parser.py, hierarchy_builder.py, table_merger.py)
 +----+-----+
      v
 ReconstructedDocument              (schemas/document.py)
```

## What each module does

| Module | Responsibility |
| --- | --- |
| `schemas/block.py`, `schemas/page.py` | Immutable input contract — one page's raw OCR blocks. |
| `header_footer_detector.py` | Learns which text recurs at the top/bottom of pages (running headers, footers, page numbers, watermarks) and classifies blocks — without ever deleting them from the raw record. |
| `boundary_detector.py` | Builds a small `BoundaryContext`: only the last/first 2-3 *meaningful* (non-noise) blocks around a page boundary, plus the live `DocumentState`. Never hands a resolver a whole page. |
| `clause_parser.py` | Pure `text -> ClauseMarker` parsing for every supported numbering style (Điều/Article/Section, Khoản, decimal, alpha/roman/number parens). No page or hierarchy knowledge. |
| `rule_engine.py` | Deterministic boundary classification, proposing a `ReconstructionAction` (the Document Reconstruction Agent's own `action`/`relationship`/`entity_type`/`target`/`reason_codes` schema). Returns `None` when signals are not conclusive. |
| `llm_resolver.py` | `BoundaryLLMResolver` Protocol + a deterministic `MockLLMResolver` (used by default and in every test) + an `OpenAIBoundaryResolver` example implementation. `SYSTEM_PROMPT` is the Document Reconstruction Agent specification; the resolver only ever sees the same small boundary window as the rule engine plus `document_state`, temperature 0, JSON-only output. |
| `header_footer_detector.py` | `action_for()` builds the explicit `IGNORE_HEADER`/`IGNORE_FOOTER` `ReconstructionAction` for a classified block, alongside `classify`/`is_noise`. |
| `config.py` | All thresholds/weights in one place: `VERY_STRONG_THRESHOLD` (0.95), `STRONG_THRESHOLD` (0.85, `= AUTO_ACCEPT_THRESHOLD`), `AMBIGUOUS_THRESHOLD` (0.70), the confidence-blend weights, table/header-footer similarity cutoffs. |
| `paragraph_merger.py` | The only place that concatenates raw text. Joins two fragments with a single space, only drops a line-break hyphen under a strict, narrow condition, and tracks the exact `char_start`/`char_end` provenance of every fragment inside the merged string. |
| `table_merger.py` | Groups consecutive `table_row` blocks into a `RawTable`, decides whether two pages' tables continue (column count + header similarity), and chains fragments into one logical `Table`: a row split across the page break is merged cell-by-cell, and a repeated header row is excluded from `rows` but kept in `repeated_header_blocks`. |
| `hierarchy_builder.py` | Places each already-merged logical segment into the clause tree using numbering/tier only (never semantics): a fresh marker opens a node, unmarked text is appended to whichever node is currently deepest open. |
| `provenance.py` | Small shared helpers for building `SourceBlockRef`s. |
| `logging_events.py` | Structured `{"event": ..., ...}` JSON logging (never full contract text). |
| `pipeline.py` | Wires all of the above together behind the two public functions. |

## Public API

```python
from contract_ocr.reconstruction import reconstruct_document, resolve_boundary

document = reconstruct_document(pages)  # list[Page] -> ReconstructedDocument
print(document.sections)  # nested clause tree, one root per Điều/Article/Section
print(document.clauses)  # every clause node flattened (for chunking/RAG)
print(document.tables)  # cross-page tables already stitched
print(document.review_items)  # boundaries the pipeline refused to guess

action = resolve_boundary(previous_page, next_page)  # Page, Page -> ReconstructionAction
```

`reconstruct_document` never makes a network call unless you pass
`llm_resolver=` explicitly — the default `MockLLMResolver` is deterministic
and always available, so the pipeline is safe and reproducible out of the
box (section 17: same input + config always gives the same output).

## Action vocabulary

`ReconstructionAction` (`models.py`) is the Document Reconstruction Agent
specification's section-15 schema:

```json
{
  "action": "MERGE_BLOCKS",
  "relationship": "CONTINUE_CLAUSE",
  "entity_type": "CLAUSE",
  "source_blocks": [{"page": 10, "block_id": "p10_b15"}, {"page": 11, "block_id": "p11_b01"}],
  "target": {"node_id": "5.3", "parent_id": "5"},
  "reason_codes": ["BOTTOM_TO_TOP", "NO_END_PUNCTUATION", "SAME_ACTIVE_CLAUSE"],
  "confidence": 0.9,
  "requires_review": false
}
```

`method` (which resolver produced it), `scores` (the breakdown below) and
`possible_relationships` (candidates when `requires_review` is true) are
this codebase's own bookkeeping — not part of what the LLM itself is
prompted to return (see `llm_resolver.SYSTEM_PROMPT`).

`Action` (what the executor should do), `Relationship` (the classified
boundary relationship), `EntityType` and `ReasonCode` are name-for-name
copies of the specification's enums — see `models.py`'s docstrings for the
full lists.

## Confidence strategy

Every action blends five independent signals (`config.py`):

```text
final = 0.30 * rule_score
      + 0.25 * layout_score
      + 0.25 * numbering_score
      + 0.10 * text_continuity_score
      + 0.10 * model_score
```

The four deterministic signals cap out at `0.90` (the sum of their
weights) — only an LLM call can push a score into the "very strong" band,
and the LLM's own self-reported confidence is never trusted alone. Bands
(spec section 13):

- `0.95 - 1.00` very strong, `0.85 - 0.94` strong: `requires_review = false`
  (`STRONG_THRESHOLD` doubles as `AUTO_ACCEPT_THRESHOLD`) — a rule-only
  match at 1.0 on every dimension lands at exactly 0.90, comfortably
  "strong" without needing the LLM at all.
- `0.70 - 0.84` ambiguous: if the rule engine alone landed here, the LLM
  resolver is consulted next.
- Below `0.70`, or still short of "strong" after the LLM has already been
  consulted: `requires_review = true`, `action = NEEDS_REVIEW`,
  `relationship = UNKNOWN`. The boundary is **never merged** — it is
  instead recorded in `review_items` with its candidate relationships.

## Design decisions where the specification was ambiguous

- **`MERGE_TABLE` vs `CONTINUE_TABLE`**: the spec lists both as actions
  without an example distinguishing them. This codebase uses `MERGE_TABLE`
  the first time two table objects are fused (`document_state.active_table`
  was still `null`) and `CONTINUE_TABLE` for a later page that extends an
  already-unified table.
- **`TABLE_CONTINUE` vs `ROW_CONTINUE`**: when the last row of the previous
  page's table has an empty cell (section 7's "incomplete last row"
  signal), `rule_engine` reports the more specific `ROW_CONTINUE`/
  `CONTINUE_ROW`; otherwise it reports the coarser `TABLE_CONTINUE` with
  `MERGE_TABLE`/`CONTINUE_TABLE`.
- **`NEW_CLAUSE` vs `ATTACH_CHILD`**: a fresh decimal/"Khoản" marker
  (section-level numbering) is `NEW_CLAUSE`; a fresh list marker
  (alpha/roman/number-paren) that isn't a sequence successor of anything
  open is `ATTACH_CHILD` under the active clause/section instead — this
  matches section 6's own list-attachment example.

## Known limitations

- **Roman vs. alpha disambiguation.** `(i)` is classified as roman-numeral
  `i` rather than the 9th letter of an alpha list (`clause_parser.py`),
  since sub-roman lists are far more common in contracts than 9-item alpha
  lists. A document that genuinely reaches `(i)` as its 9th alpha item will
  be mis-tiered.
- **Table header detection at a page boundary** uses the same small
  boundary window as every other rule (2-3 blocks). For a table with more
  rows than the window size, the boundary-level `TABLE_CONTINUE` decision
  may not see the table's true header row and can fall back to the LLM
  resolver more often than necessary. The actual row merge
  (`table_merger.build_table`) always operates on the complete per-page
  table, so once continuation is established the merge itself is accurate
  regardless of window size.
- **Decimal markers require an explicit separator.** A bare number
  ("`30 ngày...`") is never treated as a clause marker; only a multi-segment
  form ("5.1") or a single integer followed by a literal "." ("1.") is. This
  avoids misreading an ordinary quantity as a new clause, at the cost of
  requiring OCR to preserve that trailing period faithfully.
- **Unmarked text with no open clause.** If a page boundary is not
  merged (e.g. `NEEDS_REVIEW`) and neither side carries a numbering marker,
  and there is no clause already open, `hierarchy_builder` still places
  each side as its own root-level node — it does not attempt any deeper
  semantic linking between them. This only matters for text that appears
  before any clause numbering at all.

## Extending

- **Swap the LLM provider**: implement `BoundaryLLMResolver.resolve(context)
  -> ReconstructionAction` (see `llm_resolver.py`) — the pipeline only
  depends on the Protocol, never on a concrete SDK.
- **Tune thresholds**: everything tunable lives in `config.py`.
- **Add a numbering style**: extend `clause_parser.py`'s regexes and `TIER`
  mapping; `hierarchy_builder.py` needs no changes since it only reasons
  about tiers, not specific marker syntax.
