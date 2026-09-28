# LLM judge design (advisory layer)

The judge is an OPTIONAL, ADVISORY layer on top of the deterministic gate. It adds
holistic quality review the per-field scorer cannot see — and it never changes the
verdict. This is the VL-2 boundary: keep the LLM OUT of the scoring path.

## What the judge does — and does not

- **Does**: read the batch of comparison results, detect cross-case patterns, score
  five quality dimensions, classify severity, and recommend root-cause fixes. Emits
  a structured JSON report + a human-readable `quality_report`.
- **Does NOT**: multiply into the maturity score, flip `passed`, or gate release on
  its own. The generated `judge_runner.attach_judge_advisory()` returns the
  deterministic score verbatim with a `judge_advisory` block bolted on. `--skip-judge`
  bypasses it, and it is skipped by default in CI.

## The five dimensions

Accuracy (30%), robustness (25%), consistency (20%), completeness (15%),
precision (10%). Anchors + calibration examples live in the generated
`judge_rubric.md`. Borderline → score the LOWER band (a gate errs toward strictness).

## P0 recommendation (advisory only)

The judge sets a `p0_recommendation` when confidence < 0.7 or the accuracy
dimension < 60 — a *suggestion* to a human to block, surfaced in the report. It
does not set `passed`. The deterministic P0 gate (in `scorer.check_p0_gates`) is
the only thing that actually blocks.

## Why batch (the named R2 exception)

Pattern detection needs to see all cases at once — "the same field fails on 3+
cases" is invisible one case at a time. So the holistic judge reviews the batch.
This is the one sanctioned exception to R2's one-at-a-time rule, and it is bounded:
it applies only to the advisory quality judge, never to the deterministic per-field
grading, which stays strictly per-field.

## Model routing (R8)

The judge model must differ from the pipeline model to avoid self-eval bias. The
scaffolder wires `DEFAULT_JUDGE_MODEL` and `PIPELINE_MODEL` as distinct scaffold
vars and the generated runner asserts they differ at import. Pass the real model
names through to your LLM client — do not hard-code a stale model-id map (the
source did; it was removed in the re-audit). Keep judge and pipeline in different
model families.
