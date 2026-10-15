# P1 — Replay bằng chứng và telemetry từng cặp

## Overview

Xác minh decomposition historical bằng frozen context và thêm event từng cặp cho evaluation mới. Output là safe replay report, dependency hash inventory, và pipeline trace phân biệt candidate miss/model/validator/citation; không dùng aggregate counters để bịa nguyên nhân pair.

## Requirements

- Input: immutable P5 artifact, snapshot metadata, frozen pool/docs/config và code dependencies; current dirty source chỉ để so sánh. Dùng `dataset.file_digest` LF normalization (`evals/contract_graph/dataset.py:188`).
- Replay deterministic không gọi model. Restore source tại historical commit into ignored temporary directory; không checkout/reset worktree. Nếu thiếu dependency/hash/context, báo `INCOMPLETE_HISTORICAL_REPLAY` và chỉ giữ conclusion có evidence.
- Collector opt-in eval, per-doc/per-run, mặc định None. Pair canonical ID/node IDs + phase/outcome/reason/batch/request ID, requested/served model, truncation/length flags; không text/spans/provider response/key. Batch errors unknown ID phải nằm batch-event riêng, không gán vào pair giả.
- Mỗi candidate có một terminal outcome: accepted, model_unrelated, validator_reject(reason), citation_reject, no_answer, not_sent(reason); gold ngoài candidate là candidate_miss/prefilter/cap khi có evidence, otherwise unknown. Một event intermediate có thể lặp nhưng terminal không double count.
- Không đưa per-pair telemetry vào product stats/coverage/wire; builder citation failures cũng ghi exact pair reason. Consent/flag-off zero provider calls và product output parity.

## Related Code Files / deep inventory

Paths relative worktree root; source/test modifications8, không tạo production module.

| Action | File | Cỡ hiện tại / test impact |
|---|---|---|
| Modify | `ai-service/app/pipeline/contract_graph/pair_classifier.py` | ~300 LOC; event callback quanh `_decision` (`:172`) và `classify_pairs` (`:213`) |
| Modify | `ai-service/app/pipeline/contract_graph/pair_builder.py` | ~150 LOC; collector forwarding + citation rejection (`:121`) |
| Modify | `evals/contract_graph/pairs/predictor.py` | ~500 LOC; per-doc collector (`predict_doc`, `:193`) |
| Modify | `evals/contract_graph/pairs/recall_diagnostic.py` | ~450 LOC; frozen provenance/event joining (`diagnose_snapshots`, `:319`) |
| Modify | `ai-service/tests/test_contract_graph_pair_classifier.py` | existing focused tests; closed outcomes |
| Modify | `ai-service/tests/test_contract_graph_pair_builder.py` | existing focused tests; citation/consent |
| Modify | `evals/contract_graph/tests/test_cg_pairs_predictor.py` | existing; scoped collector/provenance |
| Modify | `evals/contract_graph/tests/test_cg_pairs_recall_diagnostic.py` | existing; historical/current separation |

Create safe aggregates `evals/contract_graph/reports/quality-recovery-p1-evidence.{json,md}` at cook; event JSONL/replay material local ignored only. Delete: none. Shared sources handed to P2/P4 serially under same module owner.

## Tests Before

Add failing tests: mixed same-batch UNRELATED/bad-span/missing answer have correct distinct pair outcomes; malformed/unknown/duplicate IDs do not inflate pair totals; citation reject remains linked after direction swap; stopped batch/ungrounded span; collector isolation across docs and calls; no text in emitted event; frozen dependency mismatch prevents conclusive replay.

From root set `$env:PYTHONPATH='ai-service;.'`, then `.\ai-service\.venv\Scripts\python.exe -m pytest -q ai-service/tests/test_contract_graph_pair_classifier.py ai-service/tests/test_contract_graph_pair_builder.py evals/contract_graph/tests/test_cg_pairs_predictor.py evals/contract_graph/tests/test_cg_pairs_recall_diagnostic.py -m 'not live' --basetemp .harness/state/pytest-quality-P1`. Record expected failures before implementation.

## Implementation Steps

1. Record dirty inventory/diff hashes, owners and HEAD; agree scoped candidate dirty change integration. Preserve original artifacts/read access; verify git-ignore of local state.
2. Build full historical dependency inventory: classifier, candidates, pair builder, luồng1 builder/resolver, predictor, corpus/pool, client/runtime, consent/config, docs and manifest. Compare frozen SHA/config and record unavailable artifacts. Same candidate SHA alone is insufficient.
3. Replay candidate inventory with historical context offline in isolated process; join by canonical pair IDs; prove101 positive IDs/unique IDs/context parity or report limitation. Retain historical trace unknowns as unknown.
4. Add backward-compatible optional callback at classifier→builder boundary; emit code-based exact rejection outcome where code knows it, plus sent/stop/missing-answer events. Do not parse text or infer reason from aggregate counts.
5. Predictor collects local safe events and candidate metadata; diagnostic consumes exact events when present and tags historical aggregate-only evidence. Accounting checks: candidate terminal total, accepted total and reviewed gold partitions reconcile.
6. Write safe report and artifact verification with commands, hashes, missing historical evidence, unchanged runtime behavior. No model requests or prompt tuning in P1.

## Tests After / scenario matrix

Repeat Tests Before; run consent/flag-off regression: `.\ai-service\.venv\Scripts\python.exe -m pytest -q ai-service/tests/test_contract_graph_pairs_consent.py ai-service/tests/test_contract_graph_pairs_flag_regression.py -m 'not live' --basetemp .harness/state/pytest-quality-P1-regression`.

| Priority | Scenario | Expected |
|---|---|---|
| Critical | Callback default None / flags OFF / consent denied | Original wire/stats shape, no egress |
| Critical | Same batch multiple rejection causes / citation invalid | Exact pair-level outcome; no aggregate attribution |
| High | CRLF vs LF / old resolver missing | Correct normalized hash; incomplete replay explicit |
| High | Deadline/max calls/provider absent/missing ID | not_sent/no_answer/unknown, accounting preserves denominators |
| Medium | Concurrent independent docs / injection text | No shared collector state or raw content leak |

## Success Criteria

- [x] Replay either reproduces historical candidate context or explicitly identifies missing evidence; no current-code claim from partial hash match.
- [x] New eval has unique terminal outcome per candidate and exact accounted totals; unknown remains unknown.
- [x] Focused tests + consent/flag-off parity PASS; no secret/raw text in safe artifacts.
- [x] Emit `artifacts/verification-P1.json` and safe evidence report with code/source/config hashes.

## Dependency map / Risk Assessment / Rollback

Depends: approved plan + dirty ownership audit. Blocks P2; no human dataset approval or model run needed. Per-phase risk: shared-state/leak **Medium×High**, mitigate opt-in scoped collector/privacy/parity tests; frozen input unavailable **High×Medium**, named replay limitation rather than invented evidence. Rollback P1 commit only after diff audit, disable collector; keep audit/evidence immutable and runtime OFF.
