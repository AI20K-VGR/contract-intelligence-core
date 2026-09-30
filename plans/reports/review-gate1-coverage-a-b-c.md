# Cross-review Gate 1 against plans A, B, and C

Date: 2026-09-30  
Scope: Review `docs/reviews/review-gate1-van-dung.pdf` and `docs/reviews/review-gate1-nhom.pdf` against the existing A/B/C plans. This is a separate coverage review; it does not amend those plans or approve their execution.

## Executive summary

The technical remediation is substantially represented across A/B/C: evaluation integrity and CI in A, runtime configuration and image hygiene in B, and persistence, integration, and fixture-rule removal in C. The plans do not yet provide a complete response to Gate 1 as a whole. Several delivery-governance requirements remain outside their scope, and C's proposed fixture-constant move does not meet the review's requirement that production code must not import fixtures.

The user confirmed two constraints for this review: (1) prepare the list of sensitive paths/history evidence and wait for mentor approval before any history rewrite; no force-push before that approval; (2) the demo deadline is 2026-10-04 and the demo must be verified from a tag on `develop`.

## Coverage crosswalk

| Gate 1 item | Existing coverage | Assessment |
|---|---|---|
| Inflated evaluation result; report `ANSWERED` separately and exclude `NEEDS_REVIEW` from correct answers | A builds synthetic ground truth, a deterministic scorer, separate states and a diagnostic-only `fixture_tuned_legacy` bucket; C gates quality against A's scorer. See A `plan.md` and `phases/phase-1-golden-set-synthetic.md`, `phase-2-scorer-and-thresholds.md`; C `phases/phase-4-quality-to-95.md`. | **Covered technically.** Keep the external demo/report wording aligned with these state semantics; do not repeat the old 99% figure as validated accuracy. |
| Fixture-specific production behavior and hard-coded sample intent/endpoint | C removes known fixture-specific rules in `l0_rules.py` and calls for a leakage allowlist of zero. C phase 4 F4.7 moves `LABEL_CITE` into `ai-service/fixtures/gold_labels.py` but explicitly keeps an import of it from `app/reasoning/gold.py`. The Gate 1 individual review calls out `ask_intent.py` and `/api/cases/HD-TONG-HOP/reason`; the C phase 4 file list/acceptance does not explicitly name those two findings. | **Partial, with a direct conflict.** Moving fixture data to a fixture module while importing it from runtime app code still violates “production code must not import fixtures.” Also explicitly cover and test the hard-coded intent and endpoint findings. An empty text-literal allowlist alone does not establish the architectural boundary. |
| Contract + annex comparison returns zero findings when `item_key` is absent | C phase 4 proposes generalized fact comparison by unit/scope and better retrieval, but its stated acceptance does not explicitly require comparison of valid facts with no `item_key` or assert a non-zero finding for a contract-plus-annex case. | **Partial / acceptance gap.** Add a direct contract-plus-annex regression case with missing `item_key`, and assert the expected comparison findings and citations. |
| Clean-checkout tests fail because required PDFs are ignored/unavailable | A phase 4 repairs collection and offline CI, but accepts five `requires_pdf_fixture` skips when PDFs are absent; it explicitly hands creation of Vietnamese-font fixtures to C as a follow-up with a deadline. | **Partial.** CI collection can become green while those five cases remain unexecuted on a clean checkout. The Gate 1 criterion is stronger: tests should have committed/generated fixtures and run from a clean clone, or have an explicit, accepted exception. |
| Broken AI test collection / removed import | A phase 4 includes the offline suite and a target of zero failures/errors; C relies on A's CI gate. | **Covered**, pending actual verification on `develop` and a clean checkout. |
| LLM URL points to localhost and compose cannot run independently | B chooses a remote provider URL and defines env/compose configuration in phase 2; phase 3 verifies image/compose behavior. | **Covered** for AI2 configuration. The exact Gate 1 verification should prove a fresh checkout/compose setup has no dependency on a developer laptop. |
| Docker image includes `data/` and local state | B phase 3 explicitly removes `COPY data/`, excludes local data/secrets and checks image contents. | **Covered.** |
| ADR-02/DOC-11 database ownership conflict; AI2 SQLite jobs vs required Postgres | C phase 1 gates ADR-14; phase 2 migrates the AI2 job state into Postgres schema `ai2`, with migrations and role boundaries. | **Covered technically, gated on human decision.** Do not treat this as resolved until the ADR decision and migration evidence are recorded. |
| Logic incorrectly placed in Backend / hard-coded digest / fabricated OCR confidence | C phase 3 covers Backend↔AI2 persistence and E2E; C phase 2 scopes deterministic IDs. The plans inspected do not explicitly state acceptance checks for the cited Backend private-hash mimic or `ocr_confidence: 1.0`. | **Partial / verify scope.** Add explicit ownership and regression checks for the cited Backend behaviors if they remain in the Gate 1 target. |
| Real contract data already present in public Git history | The Gate 1 group review says to prepare a path list and wait for mentor direction; no history rewrite before that. | **Missing from A/B/C; user decision recorded here.** Prepare evidence/path list and send for mentor decision. Do not force-push or rewrite history before approval. Also track removal of exposed files from current branches and prevention rules separately from rewriting history. |
| `.gitignore` replacement, generated result JSON, `node_modules`, `output/ocr`, `.worktrees` gitlink | B phase 3 has Docker build-context hygiene; it does not restore repository-wide ignore rules or clean tracked generated files. | **Missing / partial.** Docker ignore is not Git ignore. Add a repository hygiene task with two substantive reviews as requested by the group review, while preserving the sensitive-history mentor gate. |
| Reproducible demo/release from a tag on `develop` | B creates versioned AI2 SemVer tags and a controlled image release. C runs E2E on PR/develop and can run a pinned image. Neither plan explicitly requires the user-facing demo to be built from a tag that points to `develop`. | **Missing as a release acceptance condition.** User confirmed demo by 2026-10-04 from a tag on `develop`; define a verifiable tag/SHA/deploy record in the demo tracker item. |
| PR ownership, substantive reviews, no unauthorized cross-module edits | A/B/C include specific CODEOWNERS/human gates for selected workflow or release paths, not the general ownership/review requirement from Gate 1. | **Partial.** Gate 1 asks for module-owner review on each affected PR and a substantive review by Dung where assigned. Track this as a repository-wide rule, not only workflow CODEOWNERS. |
| Tracker Epics, accurate Done status/dates/evidence | No matching A/B/C acceptance criteria found. | **Missing.** Group review asks to populate Epics, revert incomplete Done items, correct dates, and make evidence match acceptance. |
| Daily progress or blocker reporting; no silent gap over two working days | No matching A/B/C acceptance criteria found. | **Missing.** Individual review asks for a pushed commit or tracker blocker each workday and no silent gap longer than two workdays. |
| Review quality and communication of architecture changes | C has human gates for ADR-14/backend semantics; plans have phase-level review artifacts. They do not establish a general requirement to communicate cross-module changes before implementation or substantive PR review behavior. | **Partial.** Use the existing ADR/owner gates, but add a team-level communication/review practice if this remains a Sprint 2 commitment. |

## Priority gaps to reconcile before treating Gate 1 as closed

1. **C fixture boundary:** F4.7 currently relocates a fixture constant but leaves runtime `app` importing it. Change the acceptance to require no runtime imports from fixture/test/eval data, and cover all named production paths including `ask_intent.py` and the sample endpoint.
2. **Comparison regression:** explicitly test contract-plus-annex comparison when `item_key` is missing; assert non-zero expected findings and valid citations.
3. **Clean-clone evidence:** resolve A's five accepted PDF skips against Gate 1's clean-checkout requirement. Prefer deterministic synthetic/generated Vietnamese fixtures committed or created during tests; if an exception remains, record it as a consciously accepted residual, not “all tests green.”
4. **Sensitive Git history:** prepare the exact paths/commits and impact evidence for the mentor. Wait for approval before history rewrite; do not force-push first. Restore preventive ignore/guard rules independently and review that change substantively.
5. **Demo gate:** before 2026-10-04, record the `develop` commit, tag, image/artifact digest, and successful run used for the demo. An AI2 package tag alone does not prove the full demo was cut from `develop`.
6. **Team/repo controls:** assign explicit work for PR ownership/review, tracker cleanup, and daily blocker/progress reporting; these are not covered by A/B/C's technical phase gates.

## Gate 1 review evidence used

- `review-gate1-van-dung.pdf`: pp. 2–3 (evaluation, fixture-specific behavior, comparison, tests, config/image/database and code ownership findings); pp. 4–6 (delivery/review practices and pre-demo requirements).
- `review-gate1-nhom.pdf`: pp. 1–4 (review/ownership/reproducibility and communication); pp. 5–7 (public-history data exposure, ignore rules, tracker and demo requirements).

## Plan evidence used

- A: `plans/260929-2323-ai2-a-measure-baseline/plan.md`; phase files 1–4, especially phase 2 scorer and phase 4 CI.
- B: `plans/260929-2323-ai2-b-versioned-service/plan.md`; phases 2–3, especially environment configuration and image hygiene.
- C: `plans/260929-2323-ai2-c-integration/plan.md`; phases 2–4, especially `phase-4-quality-to-95.md` F4.7 and acceptance criteria, plus phase 3 E2E.

## Boundary of this review

This artifact is a coverage assessment, not a new execution plan and not approval to publish, deploy, or rewrite Git history. A/B/C remain unchanged by this review.
