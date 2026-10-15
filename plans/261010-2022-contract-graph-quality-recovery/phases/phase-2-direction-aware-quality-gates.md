# P2 — Metric đúng hướng và gate chất lượng fail closed

## Overview

Giữ semantics historical metrics; bổ sung schema mới cho exact label+direction recall/precision và enforce floor theo từng nhãn. P3 quality gate phải chặn duplicate chưa duyệt, nhãn/mẫu số thiếu và malformed metrics; decision không thể enable chỉ nhờ precision.

## Requirements

- Canonical correctness: correct label; GENERAL_SPECIFIC/REFERENCE thêm gold direction và prediction direction đều trong {A,B} và bằng nhau. Missing/None==None không đúng. Validate reviewed directed gold trước readiness.
- Recall denominator là toàn approved positive gold của nhãn, gồm candidate miss/reject/not-sent. Precision denominator là toàn predicted label; unreviewed predictions là sai. Không dùng denominator precision thay recall.
- New dataset schema có `frame_version`, `recall_frame` immutable membership/hash và `precision_frame` candidate union membership/hash. Per-row roles `recall|precision|both`; shared pair dedup nhưng giữ2 roles. Recall chỉ dùng independent frame đã khóa trước generation; union-only positives chỉ precision/safety, không tăng recall/quota.
- Mỗi scored label cần n>=60 và Wilson95 lower>=0.85 cho end-to-end exact recall, existing conservative precision, exact-direction precision directed labels. Giữ existing cluster precision lower gate. False DUPLICATE observed/unreviewed typed int0.
- Missing label/field, null/n0, bool masquerading int, negative/out-of-range count, NaN/Inf, wrong schema, unknown direction/provenance phải BLOCKED/KEEP_OFF; không `.get(...,0)` mặc định pass.
- Approved gold cần `type(approved) is bool` và `approved is True`, source review hợp lệ; `1`, `"true"`, missing hoặc LLM suggestion không vào gold denominator. Tất cả retained gold positive/negative phải duyệt trước live evaluation; ambiguous reject giữ audit riêng.
- Legacy fields giữ nguyên version/semantics và readable historical-only. Evaluation/P3 gate schema mới version riêng; historical reports thiếu exact-direction metric không được authorize new run/decision.
- Gate recompute từ valid raw gold/predictions khi kiểm report; forged precomputed lower/pass không đủ. Verdict reasons ổn định, report precision và recall riêng.

## Related Code Files / deep inventory

| Action | File | Cỡ / responsibility |
|---|---|---|
| Modify | `evals/contract_graph/pairs/score.py` | ~190 LOC; `score_relations` (`:29`), legacy block (`:96`) + additive metrics |
| Modify | `evals/contract_graph/pairs/predictor.py` | ~500 LOC; `_classifier_gate` (`:81`), `build_report` (`:267`) |
| Modify | `evals/contract_graph/pairs/bakeoff.py` | ~1350 LOC; `preconditions` (`:449`), `_checked_trials` (`:986`), `decide` (`:1184`) |
| Modify | `evals/contract_graph/pairs/run.py` | ~800 LOC; `_review_dev_lock` (`:224`), dedicated new-schema review/report lock và CLI report path |
| Modify | `evals/contract_graph/tests/test_cg_pairs_score.py` | scorer labels/directions/missing cases |
| Modify | `evals/contract_graph/tests/test_cg_pairs_predictor.py` | full four-label dev gate |
| Modify | `evals/contract_graph/tests/test_cg_pairs_bakeoff.py` | preflight→checked report→decision integration |
| Create | `evals/contract_graph/tests/test_cg_pairs_run.py` | CLI new manifest/gold review-only lock và versioned report-lock boundary; file chưa tồn tại |

Create safe report `evals/contract_graph/reports/quality-recovery-p2-gates.{json,md}`; no new production module, no delete. Shared eval owner receives P1 and hands to P4/P5 serially. Do not modify shared threshold source `review_policy.py:21`.

## Tests Before

Failing regressions: correct directed label/wrong/missing direction; candidate absent FN; precision60/60+recall0/60 cannot enable; all4 labels below/missing floor; unreviewed DUPLICATE1 blocks P3; bool-approved/type errors. Integration fixture independent recall53/60 lower0.7782097940014187 plus40 correct union-only positives remains53/60, không93/100 lower0.8625032899347025 falsepass. Review-only import succeeds before report exists and classifier PASS; legacy report path cannot authorize new protocol.

Command: `$env:PYTHONPATH='ai-service;.'`; `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests/test_cg_pairs_score.py evals/contract_graph/tests/test_cg_pairs_predictor.py evals/contract_graph/tests/test_cg_pairs_bakeoff.py evals/contract_graph/tests/test_cg_pairs_run.py -m 'not live' --basetemp .harness/state/pytest-quality-P2`.

## Implementation Steps

1. Document new report/gate/frame schema and exact metrics; validate directed reviewed gold, unique pair IDs, membership hashes/counts. Explicit schema dispatch in `predictor._read_reviewed_gold` (`predictor.py:501`): new locked gold/frame file vs existing HG1/HG2 reader, unsupported/missing schema blocks. Never fallback new dataset into legacy gold.
2. Compute label-only legacy and exact-direction metrics from the same approved raw records, count unknown/unreviewed conservatively; retain separate `direction_accuracy` reporting.
3. Recompute evaluation Wilson with existing `bakeoff.wilson`/scorer helper; include denominator/rate/lower explicitly. Regression57/60 lower0.8629926537490016 passes,56/60 lower0.8407442010623228 fails, independently for precision/recall. Runtime `review_policy.wilson_lower` currently has the same arithmetic/default z=1.96; preserve existing thresholds and historical semantics.
4. Replace smoke-only P3 status with four-label quality status; optionally label smoke separately as advisory, never let it stand in for readiness. observed/unreviewed both required0.
   Extend fingerprint dependency closure from `predictor.code_fingerprints` (`predictor.py:66`) and `bakeoff._code_fingerprints` (`bakeoff.py:61`) to all touched runtime/eval parsers: run/manifest/review/scorer/predictor/bakeoff plus candidate/classifier/pair-builder/luồng1 builder/resolver/client/runtime/model-family. Use repo-relative path keys and one shared inventory; new source cannot bypass final lock because old7-file list omitted it.
5. Implement designed new CLI `review-quality-dev-lock` for review-only import and `review-quality-dev-report-lock --report <versioned path> --predecessor-sha256 <digest>` for verified measurements. Add explicit `--dev-report` path plumbing to new-protocol predict-heldout/preflight/run/decide CLI→API, sanitize repo-relative path and bind hash/dataset/schema/source to new manifest. Legacy commands/path untouched. Report lock missing/stale blocks held-out; absence cannot block gold import.
6. Add synthetic complete valid preflight→run-output→assemble→decide fixtures using mock provider, valid model/manifest/review/provenance; do not bypass `_checked_trials` for E2E evidence. Record baseline historical artifact compatibility.
7. Wire trial/raw-record membership consistency and worst-trial gates; false DUPLICATE checks all outputs/frames, recall only fixed recall frame. Versioned lock supersession writes new manifest/report with predecessor hashes/audit; never replace immutable prior lock. Later P5 edits require final dev remeasurement under new source freeze.

## Tests After / scenario matrix

Repeat Tests Before and all `evals/contract_graph/tests` offline: `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests -m 'not live' --basetemp .harness/state/pytest-quality-P2-regression`. Tests specific to new quality protocol must not perform live provider calls.

| Priority | Scenario | Expected |
|---|---|---|
| Critical | All precision pass, recall zero or missing | KEEP_OFF/BLOCKED, no enable |
| Critical | GS/REFERENCE correct label but wrong/missing A/B | Exact metric miss/readiness block |
| Critical | False DUPLICATE observed or unreviewed nonzero/missing | Safety veto or incomplete evidence |
| High | n59 vs60;56/60 vs57/60; bad types/NaN | Explicit insufficient/below floor/invalid reason |
| High | Historical schema and forged passing aggregates | Audit readable; new decision cannot pass |
| Medium | One trial good, one below floor; weighted precision higher | Worst trial governs; weighted values advisory |

## Success Criteria

- [x] Actual code path rejects low/missing recall and missing/wrong directions; new fields fail closed.
- [x] Four labels/independent denominators and observed/unreviewed duplicate safety enforced at dev and final gate.
- [x] Legacy metric semantics/history unchanged; new schema required for quality decision.
- [x] Emit `artifacts/verification-P2.json` + gate report, offline tests PASS; no product quality PASS claimed from synthetic tests.

## Dependency map / Risk Assessment / Rollback

Depends P1 telemetry/schema and verified data boundary; blocks P3 data readiness design. Gate bypass/missing defaults **High×High**, mitigate negative fixture matrix and full mocked integration. Compatibility drift **Medium×High**, version schemas and baseline legacy snapshots. Rollback P2 commit after dependency audit; strict quality recommendation remains OFF until restored gates validate real evidence.
