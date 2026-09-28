# Strategy classification

The output surface of the pipeline decides the eval strategy. Classify it in
Phase 2, then write the strategy card for the R7 approval gate.

## Output surface → strategy

| Output surface | Strategy | Example scored axis | What the scaffolder stamps |
|---|---|---|---|
| Structured fields with a known correct value (extraction, parsing) | **ground-truth** | a field, e.g. `name`/`email` | pipeline_mirror + scorer + runner + fixtures + CLI |
| Free-text / open-ended quality where there is no single correct string (summaries, chat) | **judge** | a judge dimension, e.g. `helpfulness` | ground-truth set + comparison + thresholds + the advisory judge |
| Both a checkable core AND open-ended quality | **hybrid** | a field AND a judge dimension | everything |
| You only need to pin the scoring contract (no data yet) | **contract** | the dimension weights themselves | scorer + contract tests + fixtures (minimal) |

`pipeline_mirror` names the stamped module that mirrors the production
pipeline's shape without importing `src/` — its entry symbol is
`run_pipeline` (never called "mock" in generated prose; the docstring the
scaffolder stamps says why: it must run for real, see the parity/R9 tests,
not stand in as a stub).

Default to the **most deterministic** strategy the surface allows. Reach for a
judge only when there is genuinely no ground-truth string to compare against —
a judge is advisory (VL-2) and must never be the sole gate.

## Two kinds of judge (both advisory)

1. **Batch pattern-detection** — the judge sees ALL cases together to spot
   systemic patterns a per-field scorer cannot (e.g. "email TLD fails on 10/20").
   This batch view is a **named exception** to R2's one-at-a-time rule: it is
   allowed ONLY for the holistic quality judge, it is optional, and it never
   gates PASS/FAIL alone.
2. **One-at-a-time binary** — a per-case yes/no check. Use when each case has a
   clear independent verdict. Deterministic where possible; a judge only when the
   verdict needs semantic reading.

## R8 — the judge runs a different model

The judge must NOT grade its own pipeline's model (self-eval bias). The scaffolder
sets `DEFAULT_JUDGE_MODEL` ≠ `PIPELINE_MODEL` and the generated `judge_runner.py`
carries a runtime `assert` on it. When you fill in the real models, keep them
different — pick a judge model from a different family than the pipeline's.

## The strategy card (for the R7 gate)

Present via AskUserQuestion before stamping:

- **Domain** and the **production_module** it mirrors (chosen from the Phase 1
  multi-module inventory when the repo has more than one candidate).
- **Output surface** and the **chosen strategy** + one line of why.
- **Dimensions + weights** to score — the 5-set accuracy/robustness/
  consistency/completeness/precision is a pre-filled suggestion only; the
  user edits it and the code carries no default. **primary_dimension** names
  the one dimension the judge's recommendation anchors to.
- **Threshold** and the **P0 hard-gate rules** — what forces an automatic
  BLOCK. Each rule carries a `source` anchor from one of three kinds: a code
  site (e.g. `code:src/pipeline.py:88`), a data sample (a field present in
  100% of the samples), or a memory lesson id.
- **Case matrix** — finite, with the standard edge set: empty, null,
  unicode-with-diacritics, malformed, boundary. **Epsilon** per continuous axis.
- **DOMAIN_CONFIG** — field-to-normalizer / field-to-mask; an empty map must
  carry a note explaining why it is empty.
- **mirror_lang** — the target language for the pipeline mirror.
- **Data needed** — how many samples, what formats, where ground truth comes from.
- Whether a **judge** is included and, if so, which model (≠ pipeline).

The code never fills a judgment value — it only validates what the approved
card supplies.
