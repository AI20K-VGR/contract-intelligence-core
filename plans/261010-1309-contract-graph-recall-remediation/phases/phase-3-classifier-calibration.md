# P3 — Hiệu chỉnh classifier và rejection telemetry

## Mục tiêu

Giảm hành vi trả `UNRELATED` quá mức, nhất là `CONFLICT`, `DUPLICATE`, `REFERENCE`, nhưng vẫn giữ span nguyên văn, direction, citation validation và prompt-injection defense.

## Dependencies

P2 phải freeze candidate code trên dev. Mọi rubric/few-shot chỉ lấy từ dev labels; held-out HG-1 vẫn sealed.

## Files

| Action | File | Mục đích |
|---|---|---|
| modify | `ai-service/app/pipeline/contract_graph/pair_classifier.py` | rubric, dev examples, rejection reason |
| modify | `ai-service/app/pipeline/contract_graph/pair_builder.py` | aggregate telemetry không rò text |
| modify | `ai-service/tests/test_contract_graph_pair_classifier.py` | red→green label/span tests |
| modify | `ai-service/tests/test_contract_graph_pair_builder.py` | citation/fail-closed tests |
| modify | `evals/contract_graph/pairs/predictor.py` | diagnostic provenance nếu cần |
| create | `evals/contract_graph/reports/l2-p6-classifier-calibration.{json,md}` | dev calibration evidence |

## TDD cases

- Conflict khác value/time/rate nhưng cùng subject/action → `CONFLICT` với exact spans.
- General/specific exception → `GENERAL_SPECIFIC` đúng direction.
- Same value/obligation wording → `DUPLICATE`; mismatch numeric value → reject.
- Semantic reference không dùng số điều → `REFERENCE`; explicit article reference vẫn bị policy loại.
- Uncertain or unrelated → `UNRELATED`, không fabricate relation.
- Ungrounded span, missing direction, malformed JSON, injection signal → fail-closed và có reason code.

## Acceptance

- Dev diagnostic tách được raw `UNRELATED` khỏi validation rejection.
- `CONFLICT` và `DUPLICATE` không còn zero trên dev calibration set; không đánh đổi bằng false duplicate.
- Exact span/citation và model-family checks vẫn pass.
- Prompt/code fingerprint và requested/served model được ghi trong report.

## Stop conditions

Không nới span, bỏ citation validation, hoặc biến `UNRELATED` thành label quan hệ để tăng recall. Nếu model vẫn zero conflict/duplicate trên dev, phải thử prompt/model alternative có provenance trước khi P4.
