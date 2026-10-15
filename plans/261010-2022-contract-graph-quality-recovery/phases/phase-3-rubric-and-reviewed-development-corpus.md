# P3 — Rubric thống nhất và corpus dev đã duyệt

## Overview

Tạo rubric có decision table và dev corpus mới đã được review, đủ bốn scored labels, negatives và cluster coverage. Output là packet HG-QR1, gold/manifest version mới và annotation/adjudication audit; chưa tuyên bố classifier quality PASS.

## Technical completion amendment (2026-10-11)

P3 verification records the offline implementation and rubric/corpus tooling as PASS. The user waived a second independent annotator and accepted continuation with the available smaller gold set; product-quality evidence and sufficiency remain `NOT_EVALUATED`. The original data-readiness/independent-annotation items below are retained as historical product-readiness criteria and do not block technical plan closure. This amendment does not claim those items were completed.

## Requirements

- Rubric phân biệt scope/exception/additional obligation với restatement, cùng actor/action/condition, changed quantities và semantic references. Hướng A là general/referrer khi khoản A đóng vai trò đó; schema chỉ A/B. Reviewer xem đủ context local.
- Source/clusters dev độc lập khỏi fresh held-out; exposed old held-out được đánh dấu historical/training-exposed và không được tái thành independent evaluation. Không sửa historical approved labels theo model.
- Design minimum60 approved positives mỗi label +120 representative negatives, >=5 clusters tổng, >=3 clusters/label, không cluster>40% một label. Đây là readiness/data coverage target, chưa bảo đảm model precision prediction count hoặc Wilson floor.
- Candidate-independent sampling frame, negatives cùng-topic, gần trùng, reference explicit, scope mismatch, number mismatch; report prevalence/selection π và label yield. Không lấy positives chỉ từ classifier đã chọn.
- Khóa recall membership trước candidate generation; metadata mỗi row giữ roles recall/precision/both + frame_version. Union-only positive không cộng vào recall counts/quota; shared row dedup với2 roles. Gold reader new-schema dispatch tại `predictor.py:501` đã có P2, P3 kiểm manifest/gold membership end-to-end.
- Blind independent second annotation trên tối thiểu25% packet, stratified tất cả labels/negatives và tất cả ambiguous rows; reviewer không thấy model suggestion/first decision trước own label. Không có người độc lập thì packet ghi chưa đủ annotation evidence; không giả AI second review là human-independent.
- Disagreements adjudicated/reject có receipt, không đổi nhãn để đủ quota. HG-QR1 approval bind rubric/selection/gold/split/manifest hashes và scope counts. User approvals cũ không bao phủ packet mới.

## Related Code Files / deep inventory

| Action | File | Cỡ / responsibility |
|---|---|---|
| Modify | `evals/contract_graph/pairs/LABELING.vi.md` | existing rubric, especially GS (`:18`); decision table/examples dev-only |
| Modify | `evals/contract_graph/pairs/corpus.py` | ~320 LOC; `near_duplicate_clusters` (`:241`), exposure/template audit |
| Modify | `evals/contract_graph/pairs/manifest.py` | ~300 LOC; `assign_splits` (`:89`), version/review readiness metadata |
| Modify | `evals/contract_graph/pairs/review.py` | ~260 LOC; `export_sheet` (`:144`), `import_sheet` (`:184`) blind/adjudication metadata |
| Modify | `evals/contract_graph/tests/test_cg_pairs_corpus.py` | cluster/template/exposure fixtures |
| Modify | `evals/contract_graph/tests/test_cg_pairs_manifest.py` | hash/split/readiness fixtures |
| Modify | `evals/contract_graph/tests/test_cg_pairs_review.py` | independent review/direction/decision validation |

Create safe immutable `evals/contract_graph/pairs/quality-recovery-manifest.v1.json` and `evals/contract_graph/reports/quality-recovery-p3-dev-corpus.{json,md}` at cook. Actual source lists, raw docs, reviewer annotations and membership IDs local ignored; safe manifest contains hashes/counts/version. Delete none; preserve historical `pairs/manifest.json`. Gold review lock independent of measurement report; v1 never overwritten, new locks supersede with predecessor SHA/audit.

## Tests Before

Failing tests: cross-template split contamination, historical-exposed cluster wrongly marked fresh, missing/duplicate annotations, missing reviewer decision cannot lock, invalid directed gold, reject excluded from approved denominator but in audit, any label n<60 or missing cluster coverage, new file hash invalidates prior approval, low-level LLM suggestion cannot become user-review source.

Command: `$env:PYTHONPATH='ai-service;.'`; `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests/test_cg_pairs_corpus.py evals/contract_graph/tests/test_cg_pairs_manifest.py evals/contract_graph/tests/test_cg_pairs_review.py -m 'not live' --basetemp .harness/state/pytest-quality-P3`.

## Implementation Steps

1. Audit rubric vs classifier override (`pair_classifier.py:73`) using independent dev scenarios; record causal claims as hypotheses. Write decision table with short synthetic positive/negative examples; no held-out pair content in examples.
2. Collect eligible source documents respecting existing consent/licenses/data-local boundary. Run clustering/split audit before labeling; freeze source universe, dev selection and exposure map. Reuse existing fetch/build/cluster/pool APIs and supplied local source list.
3. Create primary blind annotation packet and independent subset packet. AI may prepare candidate-independent frame and draft suggestions separately; it cannot sign reviewer approval. Supply necessary context privately, no raw clauses in safe report.
4. Measure per-label yield, confusion/agreement and disagreement adjudication; review rejected cases/near duplicates, keep immutable source/pair IDs. If yield insufficient, collect new predeclared dev tranche; no manufactured gold/quota labels.
5. Prepare HG-QR1 packet: rubric version, source/cluster coverage, counts by label/stratum, all final decisions/directions, independent review audit, scope, hashes. Ask human to confirm this concrete new packet and design constraints.
6. After explicit human response, P2-designed `review-quality-dev-lock` locks gold/frame/rubric metadata without requiring prediction report or classifier PASS. Check report-independent path through `_review_dev_lock` (`run.py:224`) dispatch and new gold reader (`predictor.py:501`). Freeze immutable v1 review manifest; P4/P5 report locks are separate later records with predecessor SHA, no overwrite or recursive hash dependency.
7. Produce safe corpus report and verification. Classifier quality measurement starts P4 only; data-ready does not equal quality-ready.

## Tests After / scenario matrix

Repeat focused command; run scorer+predictor review regression: `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests/test_cg_pairs_score.py evals/contract_graph/tests/test_cg_pairs_predictor.py -m 'not live' --basetemp .harness/state/pytest-quality-P3-regression`.

| Priority | Scenario | Expected |
|---|---|---|
| Critical | Missing user decision/independent reviewer/one label | No approved data readiness; actionable blocker |
| Critical | Held-out exposed/template duplicate in fresh cluster | Exclude from independent eval, preserve provenance |
| High | Model suggested label vs reviewer relabel/reject | Human decision owns gold; no silent overwrite |
| High | GS detail vs same obligation, implied reference A/B | Rubric adjudication, explicit direction, no missing values |
| High | Add union-only positives to recall or gold import before report | Recall unchanged; review-only import succeeds, no PASS prerequisite |
| Medium | Review edits after hash lock / cluster domination | Approval stale or readiness blocked |

## Success Criteria

- [ ] Rubric/dev design documented, enough approved positives/negatives/clusters; metadata counts independently checked.
- [ ] Blind independent annotation/adjudication audit complete; if unavailable, unresolved blocker kept explicit.
- [ ] HG-QR1 user receipt bound to new packet hashes/version; directed gold has explicit valid A/B.
- [ ] Focused tests PASS; emit `artifacts/verification-P3.json`, safe corpus report/manifest. Pending human gate/data insufficiency means P3 not complete.

## Dependency map / Risk Assessment / Rollback

Depends P2 metric/readiness definitions; human HG-QR1 is blocker for P4. Scarce REFERENCE or reviewer capacity **High×High**, measure yield early and provide review packet, report blocker without lowering quotas. Annotation bias/leakage **High×High**, blind subset/independent reviewer and grouped split. Rollback invalidate new corpus version/lock, preserve raw annotation audit; historical manifests untouched, no model use of held-out.
