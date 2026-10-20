# P5 — Held-out mới và verdict chất lượng sản phẩm

## Scope amendment — WAIVED BY USER (2026-10-11)

Người dùng quyết định không cần bằng chứng đánh giá nữa. P5 held-out, dev confirmation runs, label review và product quality verdict được waive; không đọc hoặc chạy dữ liệu P5, không gọi model. Kết quả của plan là `product_quality=NOT_EVALUATED`, không phải product PASS. Giữ runtime OFF. Phase này chỉ cần ghi waiver trong verification artifact; không tạo giả manifest, trial hoặc decision report. Nội dung gốc bên dưới được giữ làm lịch sử của yêu cầu trước amendment.

## Original P5 specification (not executed)

## Overview

Hoàn tất orchestration/gold-reader code, freeze rồi chạy2 dev confirmation trên winner đã chọn; sau PASS mới đo corpus held-out mới với2 trial/variant. Recommendation cần precision/recall/hướng/provenance/budget thật hoặc named blocker; cờ runtime OFF.

## Requirements

- New documents/template clusters disjoint dev, old exposed held-out và spike; không tune held-out. Independent recall frame membership khóa trước candidate generation. Candidate union thêm precision/safety rows; union-only positives không tăng recall numerator/denominator/quota. Shared pair retains2 roles/dedup; false DUPLICATE checks all outputs.
- Design minimum60 approved positives/label; target100/label+>=200 negatives từ>=10 fresh clusters, >=5 clusters/label, không cluster>25% positives nhãn. Review toàn union candidate B/C trước classification; representative negative frame và sampling π report rõ. Nếu enrichment, không claim production precision/prevalence từ enriched sample.
- **HG-QR2:** user reviews new held-out decisions + rubric/scope/selection hashes, confirms new data egress consent. Independent blind annotation25% stratified và ambiguous100%; disagreements adjudicated, explicit A/B for directed gold. Old HG-2 scope474 approval không hợp lệ cho corpus mới.
- Readiness kiểm gold positives từng label và projected candidates/budget. Prediction denominator>=60 từng label chỉ biết sau đo; nếu không đủ, giữ insufficient-n, không kéo thêm sample sau xem kết quả rồi reuse protocol.
- Tất cả P5 source/test changes hoàn tất và review offline trước final code freeze. Reserve2 runs của ledger P4 cho same-winner dev confirmation, cùng approved data/rubric/candidate/model, không tuning. P4 report fingerprints cũ chỉ preliminary; new confirmed reports path/version + final code_fingerprints (`predictor.py:66`) mới authorize held-out.
- Immutable final manifest `.v2.json` supersedes v1 qua predecessor SHA/audit, giữ cả2 confirmation report hashes/path và stable corpus/review/frame digests, không overwrite prior reports/locks. Final code/config/dev data/prompt không đổi từ confirmations đến cuối held-out; thay đổi/fail confirmation block run, không chạy thêm ngoài ledger.
- Designed final-dev confirmation schema có2 measured trial reports riêng, cùng winner/fingerprints/corpus/review/frame hashes, metrics từng trial và worst-trial gate; safe summary `.v1.json` tham chiếu cả2 report digests. Một ordinary single-run predictor report không đủ thay final2 confirmations. New manifest dùng declared version/schema dispatch và file paths, không legacy HG reader fallback.
- Freeze B/C variants, sources/top_k/cap/config/prompt/model/code/manifest/review SHA, metrics schema/floors, doc order/seed, trial1&2, error/retry policy before first classifier call. E không chạy mặc định; chỉ oracle dev nhỏ P4.
- Each trial<=550s/500000 tokens; two repeats dùng cùng frozen version. Preserve safety/provenance counters; no missing or unknown value passes. Failures not retried to select good result. Actual provider transport retry remains bounded and traceable.
- Product acceptance worst trial per label for candidate C: precision/exact-direction precision n>=60/lower>=.85, exact recall positive n>=60/lower>=.85, existing cluster precision lower gate, false DUPLICATE0/0 and budget. B reports comparator; winning criterion declared before run. No silent swapping to B after C fails.
- Held-out-specific change after results requires new protocol version and fresh evaluation corpus, no retuning/read-back path. Technical suite PASS cannot complete product objective when real gate blocked.

## Related Code Files / deep inventory

| Action | File | Cỡ / responsibility |
|---|---|---|
| Modify | `evals/contract_graph/pairs/run.py` | ~800 LOC; CLI review/eval orchestration (`:47`, `:166`) |
| Modify | `evals/contract_graph/pairs/bakeoff.py` | ~1350 LOC; preflight (`:449`), run (`:814`), assemble (`:1244`), verdict (`:1184`) |
| Modify | `evals/contract_graph/pairs/predictor.py` | ~500 LOC; final fingerprints (`:66`) và explicit new gold/frame schema dispatch (`_read_reviewed_gold`, `:501`) |
| Modify | `evals/contract_graph/pairs/manifest.py` | ~300 LOC; new version/split/review/protocol locks (`:163`, `:225`) |
| Modify | `evals/contract_graph/pairs/review.py` | ~260 LOC; exact new packet import/independent review (`:184`) |
| Modify | `evals/contract_graph/tests/test_cg_pairs_bakeoff.py` | full mocked CLI/preflight/trials/decision and missing-data bypass |
| Modify | `evals/contract_graph/tests/test_cg_pairs_predictor.py` | new gold reader/frame dispatch and final source-confirmation locks |
| Modify | `evals/contract_graph/tests/test_cg_pairs_run.py` | dedicated CLI report path, review-only import and immutable supersession |
| Modify | `evals/contract_graph/tests/test_cg_pairs_manifest.py` | strict freshness/version/locks |
| Modify | `evals/contract_graph/tests/test_cg_pairs_review.py` | scoped fresh user approval/annotation |

Create safe immutable `evals/contract_graph/pairs/quality-recovery-manifest.v2.json`, `evals/contract_graph/reports/quality-recovery-p5-dev-confirmation.v1.{json,md}`, `quality-recovery-p5-bakeoff.{json,md}`, `quality-recovery-p5-decision.json`; local packet/clauses/trials/raw predictions stay ignored. Prior v1/reports not modified. Source/test inventory10 files, explicit integration scope. Delete none.

## Tests Before

Failing full mocked fixtures: new reviewed gold read from declared schema/path rather than legacy HG1/HG2; missing/stale locks; P4 code hash differs P5 blocks until2 confirmations; immutable lock successor preserves predecessor; report-independent gold import; final code change invalidates both confirmations; frame53/60+40union positives remains53/60; missing direction/n/metrics/falseDup/model/budget violations; classifier before human lock forbidden.

Command: `$env:PYTHONPATH='ai-service;.'`; `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests/test_cg_pairs_bakeoff.py evals/contract_graph/tests/test_cg_pairs_predictor.py evals/contract_graph/tests/test_cg_pairs_run.py evals/contract_graph/tests/test_cg_pairs_manifest.py evals/contract_graph/tests/test_cg_pairs_review.py -m 'not live' --basetemp .harness/state/pytest-quality-P5`.

## Implementation Steps

1. Implement all P5 code first: dedicated report-path CLI→API and new schema dispatch/gold reader (`predictor.py:501`), immutable lock supersession and dual-frame membership accounting. Preserve legacy HG1/HG2 paths/commands. Complete Tests Before/After+code review before freeze; no placeholder “as needed” reader/lock wiring.
2. Freeze all source/prompt/candidate/runtime/model and stable dev/rubric/review/frame hashes. Run exactly2 SAME-winner dev confirmations from reserved ledger, output versioned final-confirmation reports. No tuning/new dev rows/source edits. If either fails or drift appears, block held-out; new work requires approved amendment, not third confirmation.
3. Collect fresh sources and lock independent recall frame before candidates; cluster/exposure audit and yield/cost sizing. Add candidate union-only precision/safety review rows with roles; never enlarge recall quota/denominator to pass. Gold dispatch validates membership/hashes without fallback legacy selection.
4. Prepare independent annotations/adjudication and HG-QR2 actual-count/π/budget/scope/hash packet; ask human review. Import approval using strict new-schema API; write immutable final `.v2.json` once from local staging with predecessor v1 SHA, final2 report locks and stable corpus/review digests. Report bindings avoid circular final-manifest digest. Preflight rejects source/dataset/path/lock drift.
5. Execute B1/B2/C1/C2 sequentially. Designed CLI after P2 plumbing: `.\ai-service\.venv\Scripts\python.exe -m evals.contract_graph.pairs.run bakeoff run C --trial 1 --model cx/gpt-5.5 --data-dir .harness/state/contract-graph-quality-recovery --manifest evals/contract_graph/pairs/quality-recovery-manifest.v2.json --dev-report evals/contract_graph/reports/quality-recovery-p5-dev-confirmation.v1.json --out .harness/state/contract-graph-quality-recovery/bakeoff --env-file ai-service/.env --allow-heldout --budget-seconds 550 --budget-tokens 500000`. `--dev-report` is designed new argument, test help/wiring before live; substitute only registered variant/trial.
6. Decide with same final manifest/dev-report path, recompute separate recall-frame/precision-frame metrics and safety across all outputs. Publish legacy label-only metrics alongside exact metrics/denominators/Wilson/cluster intervals and population limitations. Preserve all outputs; no edits/tuning after frozen confirmations.
7. Final read-only regression/review and evidence. If source fix becomes necessary, final lock invalidates and outcome remains blocked because confirmation budget consumed; seek concrete amendment. Report true PASS recommendation or failing labels/n/lower/false duplicate/time, objective not complete on product failure. Runtime OFF.

## Tests After / scenario matrix

Repeat focused command; final regression command from plan.md. Scan committed reports/manifest for raw contract/key/provider response. No new build/type-check command claimed unless project config defines one; Python module imports exercised by real pytest commands.

| Priority | Scenario | Expected |
|---|---|---|
| Critical | HG-QR2 absent/stale/old HG-2 approval reused | Zero classifier calls, explicit BLOCKED |
| Critical | Recall below/missing floor with precision good | KEEP_OFF; exact per-label gate governs |
| Critical | Union-only40 positive hits added to recall53/60 | Still53/60 and FAIL; shared roles dedup |
| Critical | P4 preliminary hash vs P5 code / old report path | Require2 final confirmations/new lock; never legacy fallback |
| Critical | Wrong/missing direction or unreviewed DUPLICATE | Conservative miss/veto, no PASS |
| High | Correlated/exposed clusters / positive-enriched frame | Readiness block or clearly scoped estimate, no production prevalence claim |
| High | Too few predictions, budget exceed, one bad trial | Insufficient/budget/worst-trial fail |
| Medium | Recompute historical report / report mutation | Historical-only compatibility; new hashes/schema invalidation |

## Success Criteria

- [ ] HG-QR2 new human-approved scope/version/gold, independent annotation and disjoint fresh clusters verified; no tune held-out.
- [ ] Final2 dev confirmations PASS under complete frozen P5 source; versioned report/manifest locks valid and no source/data/prompt drift through held-out.
- [ ] Recall membership fixed before candidates; union-only positives excluded from recall/quota; protocol/all2 repeats retained with hashes.
- [ ] Real product gates all PASS to call outcome achieved; otherwise blocker reported and plan/objective not quality-complete.
- [ ] Offline/regression tests PASS, final review no unresolved high/critical; emit `artifacts/verification-P5.json`, `artifacts/review-decision.json` and safe reports/decision. Runtime OFF.

## Dependency map / Risk Assessment / Rollback

Depends P4 genuine dev quality PASS + new corpus readiness + HG-QR2. No phase after P5; human activation is separate action. Yield/annotation/budget conflict **High×High**, preflight sizing and stop with quantitative blocker. Adaptive held-out reuse **High×High**, freeze/no tune/fresh corpus after mutation. Apparent precision from enriched sample **High×High**, candidate-independent frame, π and population limitations. Rollback invalidates protocol/version, keeps all trials immutable/historical, reverts only task commits after diff audit; no flag/schema/database migration.
