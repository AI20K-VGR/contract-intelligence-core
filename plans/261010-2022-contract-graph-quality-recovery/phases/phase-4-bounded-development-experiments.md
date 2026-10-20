# P4 — Thử nghiệm candidate và classifier trên dev có giới hạn

## Overview

Dùng approved dev/rubric để tách candidate ceiling, classifier error và validator loss; chọn cấu hình bằng metric exact-direction và cost. Không dùng historical/fresh held-out để tune, không hứa prompt sẽ đạt floor.

## Scope amendment (2026-10-11)

Người dùng waive bằng chứng đánh giá empirical. Hoàn thành P4 ở mức implementation + synthetic/offline regression; không chạy thêm dataset/model. Các target recall/precision/candidate coverage vẫn là product gates nhưng được ghi `NOT_EVALUATED`, không chặn technical completion và không được ghi PASS.

Yêu cầu live runs, model/data locks, empirical thresholds và các bước trial bên dưới là tiêu chí gốc trước amendment; chúng được giữ để làm lịch sử, đã được thay bằng kỹ thuật offline. Chúng không còn là acceptance gate của phase này.

## Requirements

- Chỉ HG-QR1-locked dev; requested `cx/gpt-5.5`, served recognized và khác model gán nhãn từng call. Consent/citation/number/direction/injection validators giữ nguyên safety contract.
- Bounded ledger **trước** run: baseline+max2 candidate ablations offline, chọn1 config; baseline+max1 prompt ablation, each2 repeats =max4 P4 live runs. Reserve2 SAME-winner confirmation runs P5 sau final orchestration code freeze, không tuning. Oracle20pairs/max1run. Cumulative toàndev vẫn6live+oracle1,7runs/3500000 tokens; mỗi run550s/500000 tokens.
- Chọn winner bằng worst-trial exact per-label quality, false DUPLICATE0/0 rồi budget. Không cherry-pick best trial; sửa hypothesis sau capped rounds cần plan/scope amendment. Candidate>=95% per reviewed label sau cap, recall/gate end-to-end vẫn riêng.
- Oracle exhaustive trên small dev đủ eligibility/exclusions chỉ đo classifier ceiling; không gọi E historical pool là exhaustive và không mở O(n²) production.
- Mỗi miss có P1 outcome; ablation rubric mismatch là hypothesis kiểm trên dev independent, không nhúng false duplicate historical pair/text vào few-shot.
- Preliminary P4 dev gate bốn nhãn: recall exact Wilson lower>=.85, precision n>=60/lower>=.85, directed exact precision/recall, no unknown/unreviewed DUPLICATE. PASS chỉ cho chuẩn bị code/corpus P5; chưa authorize held-out calls. P5 changes có trong `code_fingerprints` (`predictor.py:66`) nên phải final2 confirmation runs đúng frozen source trước new dev report lock.

## Related Code Files / deep inventory

| Action | File | Cỡ / responsibility |
|---|---|---|
| Modify | `ai-service/app/pipeline/contract_graph/pair_candidates.py` | ~350 LOC; `generate_pair_candidates` (`:143`), ranking/cap coverage |
| Modify | `ai-service/app/pipeline/contract_graph/pair_classifier.py` | ~300 LOC; approved rubric/prompt (`:27`, `:73`), safety validators (`:172`) |
| Modify | `ai-service/app/pipeline/contract_graph/pair_builder.py` | ~150 LOC; consent/budget/grounding-compatible context (`:72`) |
| Modify | `evals/contract_graph/pairs/candidate_eval.py` | ~360 LOC; `measure_dev` (`:92`), `assess_engineering_target` (`:159`) |
| Modify | `evals/contract_graph/pairs/predictor.py` | ~500 LOC; dev-only oracle/experimental config (`:169`, `:193`) |
| Modify | `ai-service/tests/test_contract_graph_pair_candidates.py` | cap/ranking/exclusions deterministic |
| Modify | `ai-service/tests/test_contract_graph_pair_classifier.py` | rubric schema/span/safety regressions |
| Modify | `evals/contract_graph/tests/test_cg_pairs_candidate_eval.py` | four-label coverage floor + dev-only config |

Create safe `evals/contract_graph/reports/quality-recovery-p4-development.{json,md}`; ledger/outcomes/prompts hashes local ignored. No new model client/module/dependency. Sources handed from P1/P2; no parallel writes. Do not modify luồng1 builder/resolver/contract schemas without scope review.

## Tests Before

Failing meaningful fixtures from adjudicated **dev** failure categories: candidate hidden by same-article flood/top-k starvation, inherited context truncation, cross-document exclusion, real subset vs concise restatement, numeric mismatch, GS/reference direction, invalid/missing spans and model-family rejection. Synthetic excerpts allowed; no real held-out text.

Command: `$env:PYTHONPATH='ai-service;.'`; `.\ai-service\.venv\Scripts\python.exe -m pytest -q ai-service/tests/test_contract_graph_pair_candidates.py ai-service/tests/test_contract_graph_pair_classifier.py evals/contract_graph/tests/test_cg_pairs_candidate_eval.py -m 'not live' --basetemp .harness/state/pytest-quality-P4`.

## Implementation Steps

1. Freeze dev packet/label/rubric/order/seed/model hashes, code diff inventory and run ledger. Reproduce baseline with telemetry; measure candidate coverage per label before classifier calls.
2. Size oracle20 eligible dev pairs using same validators/consent; report raw-vs-accepted/label-direction accuracy and eligibility definition. Its results are diagnostic, not product estimate.
3. Candidate experiments minimal: source/ranking/quota strategy and top_k grid from existing `K_GRID` (`candidate_eval.py:40`); compare coverage after cap per label, candidates/calls/tokens/latency. Pick one configuration or stop if budget insufficient.
4. Prompt experiments minimal against adjudicated rubric: remove/rewrite conflicting override only with dev evidence, clarify label boundaries/direction, preserve exact spans/output schema. No unbounded retries or lowering grounding/duplicate-value checks to boost recall.
5. CLI measured dev command shape: `.\ai-service\.venv\Scripts\python.exe -m evals.contract_graph.pairs.run predict --split dev --variant C --model cx/gpt-5.5 --data-dir .harness/state/contract-graph-quality-recovery --manifest evals/contract_graph/pairs/quality-recovery-manifest.v1.json --dev-review .harness/state/contract-graph-quality-recovery/review/dev-approved.jsonl --env-file ai-service/.env --report-prefix evals/contract_graph/reports/quality-recovery-p4-development`. P2 new-schema CLI lock/path plumbing handles dedicated report; candidate/prompt configs use package APIs and controlled commits. Guard budget/ledger before calls; output prefix immutable/versioned per run, không overwrite trials.
6. Evaluate registered runs, review all predicted DUPLICATE against approved gold/precision frame; unreviewed requires user receipt. Freeze winner prompt/candidate/rubric/data and preliminary source/report hashes. These are selection evidence; P5 final source-confirmation lock supersedes with predecessor hashes, không overwrite initial lock.
7. Emit preliminary dev verdict/test evidence. Candidate-only pass cannot open P5; full preliminary quality PASS permits preparation. Reserve2 ledger runs for final source confirmation; failure there blocks held-out with no tuning or extra runs.

## Tests After / scenario matrix

Repeat Tests Before; `.\ai-service\.venv\Scripts\python.exe -m pytest -q ai-service/tests/test_contract_graph_pair_builder.py ai-service/tests/test_contract_graph_pairs_consent.py ai-service/tests/test_contract_graph_pairs_flag_regression.py evals/contract_graph/tests/test_cg_pairs_predictor.py -m 'not live' --basetemp .harness/state/pytest-quality-P4-regression`.

| Priority | Scenario | Expected |
|---|---|---|
| Critical | Candidate>=95%, classifier still fails floor | Dev quality blocked, no P5 |
| Critical | Any false DUPLICATE/unreviewed/invalid span | Safety rejection, no winner PASS |
| High | Coverage gain exceeds budget / missing truncation context | Reject config or named blocker, keep limits |
| High | Correct directed label wrong direction / one bad repeat | Exact recall miss/worst-trial fail |
| Medium | Oracle-only success / instruction-like clauses | No production claim, injection safety preserved |

## User-authorized continuation note

The user explicitly waived a second human reviewer and accepted continuation with the current small approved-gold set. This permits bounded P4 development diagnostics at the existing support; it does not lower the recall Wilson lower-bound floor (0.85), candidate-coverage target, or held-out gates. Do not describe the AI blind annotation as independent human review.

## Success Criteria

- [ ] Bounded ledger complete; every live run documented model/consent/hash/token/time/outcomes.
- [x] Candidate ranking giữ cap và đa dạng hóa core top-K bằng deterministic regression; candidate source recall remains NOT_EVALUATED.
- [x] REFERENCE rubric and abstention accounting regressions pass; no live model/data evaluation.
- [x] Focused/offline regression PASS; `artifacts/verification-P4T.json` records technical PASS separately from product quality NOT_EVALUATED. Additional review findings are handled by P4U.

## Dependency map / Risk Assessment / Rollback

Depends P3 data/rubric readiness + HG-QR1; blocks P5 unless quality gate PASS. Prompt overfit **High×High**, bound rounds/independent dev examples/fresh evaluation. Candidate growth/budget **High×High**, measured caps and no exhaustive production. Dirty candidate conflicts **Medium×High**, preserve/integrate owner diff with version inventory. Rollback task commits to last dev frozen config, never revert other's edits, preserve experiment ledger and runtime OFF.
