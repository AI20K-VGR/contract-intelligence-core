# P1 — Chẩn đoán recall theo tầng

## Mục tiêu

Tạo một diagnostic reproducible để biết mỗi gold positive bị mất ở đâu: candidate set, classifier decision, schema/grounding validator hay budget. P1 không sửa prompt, model, threshold hoặc held-out data.

## Evidence đầu vào

- `evals/contract_graph/reports/l2-p5-bakeoff.json`.
- `.harness/state/contract-graph-pairs/bakeoff-gpt55-final-20261010/t*/{B,C,E}.json`.
- Locked HG-1 manifest/decisions SHA và dev candidate report.

## Files

| Action | File | Mục đích |
|---|---|---|
| create | `evals/contract_graph/pairs/recall_diagnostic.py` | Chấm coverage và failure taxonomy; không ghi raw contract text |
| create | `evals/contract_graph/tests/test_cg_pairs_recall_diagnostic.py` | TDD cho từng failure class |
| create | `evals/contract_graph/reports/l2-p6-recall-diagnostic.json` | Aggregate machine receipt |
| create | `evals/contract_graph/reports/l2-p6-recall-diagnostic.md` | Human-readable diagnosis |
| modify | `evals/contract_graph/pairs/run.py` | CLI entrypoint nếu cần |

## Test matrix

| Priority | Scenario | Expected |
|---|---|---|
| Critical | Gold pair không nằm trong C/B candidate | `candidate_miss`, ghi variant/source/score nếu có |
| Critical | Gold pair nằm trong E nhưng model trả `UNRELATED` | `classifier_unrelated`, không tính là provider error |
| High | Label có raw output nhưng span/direction sai | `validation_reject` với code cụ thể |
| High | Không có answer, timeout, family mismatch | `unclassified_or_provider`, fail-closed |
| High | False `DUPLICATE` | hard stop và receipt |
| Medium | Pair xuất hiện hai lần hoặc sai metadata | deterministic validation error |

## Acceptance

- Reproduce được baseline: C/B candidate coverage `74/101`, `77/101`; E `101/101`.
- Reconcile được tổng candidate với `predictions + rejection counts + unclassified`; không có hàng mất không giải thích.
- Diagnostic không chứa clause text, API key, raw prompt hoặc raw response trong tracked artifact.
- `pytest` tests mới và full eval pass; report ghi lock SHA/code SHA/model provenance.

## Stop conditions

Nếu diagnostic không phân biệt được candidate miss với classifier miss, dừng P2/P3 và sửa instrumentation trước. Không dùng held-out để chọn thay đổi.
