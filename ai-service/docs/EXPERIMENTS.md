# Experiments and metrics

| ID | Engine | Transformations on rendered scan |
|---|---|---|
| E0 | PyMuPDF | Native text only; scan pages SKIPPED |
| E1 | Paddle PP-OCRv6 | None; 300 DPI rendering |
| E2 | DeepSeek-OCR-2 | None; configurable model/backend/prompt |
| E3 | Paddle PP-OCRv6 | Deskew |
| E4 | Paddle PP-OCRv6 | Deskew, then denoise |
| E5 | Paddle PP-OCRv6 | CLAHE contrast enhancement |
| E6 | Paddle PP-OCRv6 | Adaptive Gaussian threshold |

Every selected experiment processes the exact same manifest entries. All pipelines use PyMuPDF on usable text layers; E0 cannot recover scan content. Use `actual_engines`, `ocr_pages`, `native_pages`, status and page evidence when comparing. Do not call native-page performance Paddle/DeepSeek accuracy. For clean comparisons, select paired complete samples from the same scan strata and inspect differences between E1 and E3–E6. Report both gains and regressions. The summary does not select a winner.

Add a new experiment by adding `{id, engine, preprocessing}` to the selected config. IDs are unique, filesystem-safe strings. Supported steps: `orientation90`, `orientation180`, `orientation270`, `deskew`, `grayscale`, `contrast`, `denoise`, `threshold`. Orientation angles are explicit counterclockwise corrections; automatic upside-down detection is not claimed. Duplicate/unknown steps are rejected. Step order is significant.

## Text metrics

Normalize reference and hypothesis to Unicode NFC without stripping Vietnamese diacritics or changing case. CER is Levenshtein edit distance on characters divided by reference character count. WER is the same on whitespace-split words, implemented with RapidFuzz's Levenshtein distance. CER preserves whitespace, including page form feeds; WER collapses whitespace by tokenization. Exact match compares complete NFC strings. Empty reference denominator is defined as 1: empty/empty = 0 errors; each insertion into an empty reference adds 1. Error rates can exceed 1.

Vietnamese diacritic metric: NFC strings are decomposed to base letters by NFD mark removal and `đ→d`, `Đ→D`. Align the base strings by minimum-edit-distance opcodes. Among equal aligned alphabetic base letters, count cases where original NFC characters differ. Rate = differing diacritics / equal aligned alphabetic base letters. Also save numerator and denominator. If no equal aligned letters exist, rate is undefined. This captures `a/á/à/ả/ã/ạ/ă/â`, `o/ô/ơ`, `u/ư`, `d/đ`. It excludes insertions, deletions and different-base substitutions; use CER alongside it. Ambiguous repeated-letter alignments follow RapidFuzz's deterministic alignment.

## Critical fields

Supported annotation types: ARTICLE_NUMBER, CLAUSE_NUMBER, MONEY, DATE, PERCENTAGE, QUANTITY, TAX_CODE, CONTRACT_NUMBER, PARTY_NAME.

The metric measures annotation-guided transcription retention, **not semantic extraction accuracy**. Dates normalize to ISO. Numbers use Vietnamese dot grouping/comma decimal; ambiguous English grouping must be curated. Tax codes remove spaces/hyphens. Names and identifiers use NFC, case-folding and collapsed whitespace. Numeric candidates use whole-number boundaries, so `100` cannot match `1000`. Multiple identical annotations consume matching occurrences rather than reusing one occurrence within the same annotation group. Page-scoped fields are preferred. Without location-aware semantic extraction, the same value in an unrelated field can still count as correct; do not use this metric as a validation of contract meaning.

Report correct fields / total annotated fields. Summary includes sample mean accuracy with sample n and pooled correct/total with field n. An empty annotation array yields undefined accuracy, not 100%.

## Geometry

For each page and level (word/line), match boxes one-to-one using maximum total IoU assignment (Hungarian algorithm). IoU = intersection area / union area. Unmatched reference boxes get zero. Mean IoU and hit rate at IoU ≥ configured threshold (default 0.5) use reference-box n. Extra predictions do not reduce these recall-oriented metrics; precision is not implemented. Text content is not used to fabricate or align geometry.

If no reliable predicted geometry is available for a level, leave metrics undefined. Paddle word metrics and DeepSeek OCR geometry metrics are N/A. This is distinct from missed reference boxes where the engine produced some geometry. Line/word counts and mean metrics are separate. Clause-level evaluation is outside scope.

## Aggregation and failure review

Group by engine, experiment, language, manifest input_type, quality and degradation. Save total attempts n, successful/failed/skipped counts and success rate with its denominator. Each mean/median metric has its own `_n`, since annotations may be missing. Incomplete samples never enter summary accuracy. Timing aggregates also describe successful samples; failed/skipped timing remains in per-sample CSV.

`failures.csv` contains errors/skips, empty predictions, critical-field mismatches and top 10 positive CER/WER cases per run (categories may repeat a sample). It includes reference, prediction, error type and metadata. `failure_analysis.md` indexes these cases. `summary.md` supplies a decision-support table with accuracy, critical fields, bbox support, Vietnamese strata, latency, infrastructure and failures, always with metric counts.

No real OCR benchmark numbers are checked in. Synthetic tests validate software behavior and cannot establish quality on commercial contracts.
