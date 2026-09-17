# DOC-06 · Evaluation Protocol and Immutable Report Template

| Thuộc tính | Giá trị |
|---|---|
| Version / status | v0.5 — Draft · Ready for Review |
| Owner | AI/QA Lead |
| Contributors / reviewer | AI, QA, Architecture team / Mentor |
| Effective / review date | 2026-09-17 / TBD |
| Upstream | DOC-01; DOC-02 BR-03, BR-06…BR-19, NFR-02…NFR-05; DOC-03…DOC-05/contracts |
| Thay thế | Không có |

## 1. Gate and dataset rules

Gate A validates design only. Gate B requires permitted source data, consent/classification/retention, immutable dataset/gold/adjudication manifests, source-family split and execution provenance. `DEV` and `SEALED_HOLDOUT` are separate; fixture/demo data cannot substantiate quality claims.

## 2. Mandatory report template

Every report must contain:

1. purpose, decision requested and no-claim status when required fields are absent;
2. dataset/gold/adjudication IDs and digests, consent/classification, split/leakage guard;
3. config/policy/code/engine/snapshot/run/manifest digests and input inventory;
4. `n`, denominator, missing/failed/not-run/excluded with reason;
5. metric tables, confidence intervals where applicable, redacted error taxonomy and reviewer sign-off;
6. measured latency/cost, re-OCR/batch/approval outcomes and promotion/no-promotion decision.

## 3. Stratification and metrics

Report every applicable metric by input type, language profile (`vi`, `en`, `vi-en`, `unknown`), quality class, table/rotation, document role, dossier family and pages-per-document.

| Domain | Required measures |
|---|---|
| OCR/layout | CER/WER/diacritic and critical-field accuracy when gold exists; geometry coverage/IoU; table/structure accuracy. |
| Citation | Exact source/document/page/line/span/word/bbox validity. |
| Facts | TP/FP/FN, precision/recall/F1 by entity; raw, normalized and context errors separate. |
| Findings | Disposition confusion matrix; structured difference precision/recall/F1; amendment/semantic candidate separate. |
| Batch | Submitted/terminal counts, per-member retry/quarantine, queue wait, throughput and independent `DONE/FAILED/NEEDS_REVIEW`. |
| Re-OCR | Reason/scope/source, dedupe, route, repair action, transport/quality/provider budget usage, evidence-resolution, recompute and failure outcomes. |
| Long-document coverage | Page/chunk terminal coverage, continuation-finalization correctness, unsupported-fact rate from human audit, budget exhaustion and stale-dependency rate. |
| Review/approval | Pending-review aging, action/override rate, approval CAS failures and processed→reviewed→approved completion. |

`NEEDS_EVIDENCE` is an operational/coverage outcome, never silently removed from a metric denominator or counted as a Conflict false positive.

## 4. Required scenarios

- Unicode, Vietnamese composed/decomposed text, rotation, table and multi-page citation round-trip.
- 50-page contract fan-out with bounded concurrency and no whole-document model prompt.
- Vietnamese, English, bilingual and unknown language profiles.
- Critical `O/0` ambiguity, failed/exhausted re-OCR, targeted page-pair continuation and selective recompute.
- Page/chunk ledger on a 50-page dossier: missing middle page, blank verified page, truncated OCR output, bounded crop repair and a fact blocked by incomplete continuation.
- Batch member isolation, retry and summary; review/approval concurrency; approval superseded by rerun/re-OCR.

## 5. Promotion

Candidate config follows DEV → sealed holdout → human approval → shadow → canary → active. No automatic promotion; rollback creates a new routing binding and preserves historical provenance.

## 6. Long-document publication gates

Every report that claims long-document extraction/comparison quality must separately report page and chunk denominators. A positive fact/finding is eligible only when all source pages are `COMPLETED`/`BLANK_VERIFIED`, required chunks are `FINALIZED`, and every citation resolves. `NEEDS_EVIDENCE`, `PARTIAL_FAILED`, budget exhaustion and unresolved grounding remain explicit outcomes; they cannot be excluded or merged into a successful OCR/extraction denominator.
