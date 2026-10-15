# Báo cáo tester độc lập P5 — final refresh cx/gpt-5.5

**Verdict: PASS.**

The current verification uses the six completed `cx/gpt-5.5` trials, locked HG-1 data, the current code fingerprint, dataset verification, 225 eval tests, and targeted Ruff. The canonical runtime decision is `KEEP_OFF_INSUFFICIENT_N`; the feature remains off by policy.

## Snapshot lịch sử — cx/gpt-6-sol

- Snapshot có đủ sáu artifact theo đúng thứ tự C1 → B1 → E1 → C2 → B2 → E2 trong .harness/state/contract-graph-pairs/bakeoff/.
- Cả sáu artifact có status=OBSERVED, split heldout, 14 tài liệu và 181 nhãn; scoreboard dùng 101 item. Sáu artifact dùng cùng code_sha256 map và decisions_sha256=1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64.
- Model được yêu cầu là cx/gpt-6-sol; model phục vụ quan sát được là gpt-6-sol ở mọi trace. Mọi trace có error_type=null; không có false duplicate (observed=0, unreviewed=0).
- Chính sách model-family hiện chấp nhận classifier thuộc family đã nhận diện (anthropic, google, openai) và yêu cầu model classifier cụ thể khác model labeler. Run này đạt kiểm tra: family openai, classifier gpt-6-sol, labeler gpt-4o-mini-2024-07-18, classifier_model_differs_from_labeler=true trong plans/261008-1500-ai2-contract-graph-implicit/reports/p5-bakeoff-preflight.json.

## Kết quả sáu trial

| Trial | Recall any | Predictions | LLM calls | Tokens (prompt + completion) | Elapsed (s) | Budget |
|---|---:|---:|---:|---:|---:|---|
| C1 | 3/101 (0.0297) | 28 | 28 | 54,743 | 204.675559 | trong ngân sách |
| B1 | 2/101 (0.0198) | 15 | 27 | 51,415 | 186.923525 | trong ngân sách |
| E1 | 9/101 (0.0891) | 58 | 89 | 241,653 | 635.613463 | **over-budget** |
| C2 | 4/101 (0.0396) | 30 | 28 | 55,115 | 215.827651 | trong ngân sách |
| B2 | 3/101 (0.0297) | 17 | 27 | 51,388 | 178.249314 | trong ngân sách |
| E2 | 9/101 (0.0891) | 55 | 89 | 241,307 | 639.616101 | **over-budget** |

E vượt giới hạn thời gian 550 giây ở cả hai trial; token budget 500,000 không bị chạm. Vì vậy E được ghi trong budget_blocked_variants dù có recall quan sát cao nhất.

## Quyết định và rank

- Báo cáo bake-off: evals/contract_graph/reports/l2-p5-bakeoff.json.
- Quyết định thống kê: evals/contract_graph/reports/l2-p5-decision.json, verdict=HUMAN_DECISION, recommendation_only=true, budget_blocked_variants=["E"].
- Rank artifact: plans/261008-1500-ai2-contract-graph-implicit/bakeoff-verdict.json xếp E > C > B, nhưng E vẫn bị chặn do vượt ngân sách; không tự động bật feature hoặc chọn winner cho production.
- Recall thấp hơn ngưỡng quality policy ở mọi variant. Kết quả này đủ để gate chất lượng và provenance, nhưng cần quyết định người dùng trước mọi rollout.

## Kiểm thử độc lập

Dataset verify:

    uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m evals.contract_graph.pairs.run verify --data-dir .harness/state/contract-graph-pairs

Kết quả: verify ok: .../evals/contract_graph/pairs/manifest.json.

Full eval suite:

    uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests

Kết quả: **223 passed**, 0 failed.

Targeted Ruff trên các file Python đã thay đổi trong P3–P5:

    uv run --project ai-service --frozen --extra dev ruff check --config ai-service/pyproject.toml ai-service/app/llm/client.py ai-service/app/pipeline/contract_graph/pair_builder.py ai-service/app/pipeline/contract_graph/pair_classifier.py ai-service/tests/test_contract_graph_pair_builder.py ai-service/tests/test_llm_complete_json.py evals/contract_graph/pairs/bakeoff.py evals/contract_graph/pairs/models.py evals/contract_graph/pairs/predictor.py evals/contract_graph/pairs/run.py evals/contract_graph/tests/test_cg_pairs_bakeoff.py evals/contract_graph/tests/test_cg_pairs_labeler.py evals/contract_graph/tests/test_cg_pairs_predictor.py

Kết quả: All checks passed!.

## Kết luận gate

Code, lock/preflight, sáu trial live, provenance model-family, dataset verify, full eval và lint đều có bằng chứng PASS. Snapshot lịch sử này ghi **PASS_WITH_RISK** khi verdict còn là HUMAN_DECISION; nó đã được supersede bởi final refresh cx/gpt-5.5 bên dưới.

## Final refresh — cx/gpt-5.5 (2026-10-10)

Verification rerun completed with six live trials using `cx/gpt-5.5` (served `gpt-5.5`), the locked HG-1 dataset, and one current code fingerprint. Recall any was C1 `5/101`, B1 `2/101`, E1 `7/101`, C2 `4/101`, B2 `3/101`, E2 `10/101`; E exceeded the 550-second time budget in both trials. Rank output is `tie_within_noise` with no production winner. The corrected decision precedence returns `KEEP_OFF_INSUFFICIENT_N` because C label denominators remain below `MIN_N`; no threshold or data was changed. Full eval passed `225`, focused bakeoff tests passed `61`, and targeted Ruff passed. Verification verdict: **PASS**; runtime feature remains off by the fail-closed gate.
