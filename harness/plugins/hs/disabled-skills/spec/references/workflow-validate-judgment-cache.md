# Workflow — Validate — Judgment Cache & Impact-Pass (retired)

**NOT SHIPPED in this build.** This file described two designs that never landed:

- A judgment-caching layer (`scripts/judgment_cache.py`) meant to let a re-`--validate` of an
  unchanged spec skip re-judging unchanged nodes. The script does not exist — every `--validate`
  re-runs the LLM judgment checks listed in `workflow-validate.md` Step 2 from scratch, with no
  cache, no staleness key, and no `po_ruling_ref` carry-forward.
- A per-change impact-pass that would annotate downstream nodes and write
  `docs/product/impact/<ts>.md`. The graph-diff primitives it would have used
  (`spec_graph.diff_graphs` / `spec_graph.changed_nodes` / `spec_graph.downstream()`) do exist and
  remain available for a future implementation, but no script or workflow step currently drives
  them into an impact report.

Do not invoke `judgment_cache.py`, its `--check` / `--store-batch` / `--gc` CLI, or
`jc.write_last_validated(...)` — none of it is on disk. See `workflow-validate.md` for the
`--validate` flow that actually ships.
