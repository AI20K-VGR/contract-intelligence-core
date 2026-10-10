# P2 — Khôi phục candidate coverage

## Mục tiêu

Giảm ceiling mất recall của C/B trên dev bằng thay đổi deterministic, có thể giải thích và không làm mất fail-closed. E chỉ dùng làm upper-bound coverage và phải được tính budget trước.

## Dependencies

P1 diagnostic phải chỉ ra candidate miss và source/stratum bị mất. Không được dùng held-out để chọn `top_k`, weight hoặc rule.

## Files

| Action | File | Mục đích |
|---|---|---|
| modify | `ai-service/app/pipeline/contract_graph/pair_candidates.py` | rule/score/top-k deterministic |
| modify | `ai-service/tests/test_contract_graph_pair_candidates.py` | regression và edge cases |
| modify | `evals/contract_graph/pairs/candidate_eval.py` | coverage theo label/source/stratum |
| modify | `evals/contract_graph/tests/test_cg_pairs_candidate_eval.py` | test measurement |
| create | `evals/contract_graph/reports/l2-p6-candidate-coverage.{json,md}` | dev evidence |

## TDD cases

- Conflict/duplicate candidate không bị loại nhầm bởi ancestor/Luong-1 rule nếu thuộc scope luồng 2.
- Explicit reference ngoài văn bản vẫn bị loại đúng policy.
- Near-duplicate, nested clause, short node và multi-article ordering giữ deterministic.
- Hai `PYTHONHASHSEED` cho cùng candidate set và digest.
- `top_k`/score thay đổi phải làm preflight fingerprint đổi và buộc rerun P5.

## Acceptance

- Dev coverage đạt engineering target `>=95%` cho từng scored label hoặc report nêu rõ label/stratum không thể cover và lý do.
- Candidate universe không sinh cặp ngoài pool + S4; pair IDs stable.
- Candidate count và dự toán E vẫn trong giới hạn preflight hoặc E bị loại minh bạch.
- Không thay đổi review lock/held-out decisions.

## Stop conditions

Nếu tăng coverage làm candidate explosion khiến E vượt budget hoặc làm precision dev tụt dưới policy, giữ variant an toàn hơn và chuyển sang P3; không tăng `top_k` vô hạn.
