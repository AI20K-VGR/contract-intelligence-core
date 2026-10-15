## Phase Implementation Report

### Executed Phase
- Phase: P5 — `phase-5-bakeoff-rerun`
- Plan: `plans/261008-1500-ai2-contract-graph-implicit`
- Status: completed — phần implementation được giao; toàn phase còn phụ thuộc live trials, artifact và review do lead thực hiện.
- Worktree: `C:/Users/dungs/OneDrive/Documents/VSF-ai2-contract-graph`; branch `feature/ai2-contract-graph`.
- Đã đọc `CLAUDE.md` tại cây gốc, tiêu chuẩn code/architecture, plan, phase P5, `hs:cook` và quy tắc sampled-rate-reporting. Posture subagent do lead đã giải quyết trước giao việc.

### Files Modified
- `evals/contract_graph/pairs/bakeoff.py`: tạo mới, 501 dòng.
- `evals/contract_graph/pairs/run.py`: +76/-0, tổng 681 dòng.
- `evals/contract_graph/tests/test_cg_pairs_bakeoff.py`: tạo mới, 317 dòng.
- Báo cáo này: thuộc đường dẫn báo cáo được giao.
- Không sửa runtime P1–P4, manifest, calibration, env, harness hoặc file của owner khác. Không commit, không gọi LLM thật, không viết verification/review receipt.

### Tasks Completed
- [x] Viết test trước implementation; chạy RED thật khi `bakeoff.py` chưa có.
- [x] Nhập HG-1: SHA selection, IDs duy nhất/đúng toàn bộ/count, metadata GPT label/direction khớp nhãn frozen; quyết định JSONL canonical; chỉ thay khối manifest `heldout_review`; không thay lock đã khác.
- [x] Tiền điều kiện: verify toàn dataset, gold khóa/SHA/count, họ labeler OpenAI, model thực phục vụ Anthropic nếu supplied, prompt/version/K frozen, B/C nằm trong pool ∪ S4, E cap 300, ước feasibility/ngân sách từ dev.
- [x] Runner: yêu cầu `--allow-heldout` và env-file có thật qua CLI; lock review phải có trong `HEAD`; đúng thứ tự C1 B1 [E1] C2 B2 [E2]; trial không ghi đè; budget không vượt trần preflight 600 giây/2.000.000 token.
- [x] Trace production: classifier tạo client mới nên lấy slice `NineRouterClient.all_traces` sau start index mỗi doc; kiểm họ model trên mọi trace thành công, ghi whitelist metadata/cost/latency; không prompt/span/key. Lưu timestamps, commit khóa review, SHA source code và model thực phục vụ.
- [x] Chấm từ gold approved và selection 1/π, gồm per-label/per-stratum/per-doc, recall_any với denominator gold positive đã duyệt, false DUPLICATE, cụm, token/calls, latency và over_budget.
- [x] Metric CLI chỉ in một số trial mới nhất; `--dry-run` in `0.0` để probe hợp đồng CLI, không tạo số đo hoặc gọi classifier.
- [x] Decide thuần: tái kiểm canonical SHA của gold trong report, mọi trial SHA, đúng hai trial/variant, model/prompt/source SHA không đổi; tái chấm predictions thay vì tin metric từ trial JSON.
- [x] Cổng nhập ngưỡng review_policy; trial C tệ hơn, false DUPLICATE veto, insufficient n, below threshold, HT discrepancy thật, cụm/McNemar HUMAN, recommendation-only.
- [x] McNemar cùng gold-positive, worse-of trial theo recall_any; Newcombe precision difference; cluster engine tái dùng, không tính từ chồng khoảng.
- [x] Báo cáo số đo bằng JSON/Markdown allowlist và trial được tái chấm; scoreboard giữ mọi variant, spread/over_budget; hiệu chuẩn labeler qua confusion/judge-screen, ghi rõ cận trên vì không có người gán mù.
- [x] Sizing phân biệt all-pass tốt nhất với tìm hữu hạn `floor(p*n)` theo tỷ lệ đo; tỷ lệ ≤ 0,85 trả null. Ước docs bổ sung chỉ khi có tốc độ dự đoán/nhãn đo được.
- [x] GREEN focused/all-eval và lint file thuộc ownership; gửi code freeze/CLI cho lead.
- [ ] Lead: import dữ liệu thật, commit lock, live preflight/trials/rank/statistical CLI, xuất artifact, cập nhật doc và independent review.

### Tests Status
- RED: `uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests/test_cg_pairs_bakeoff.py` → exit 1; `ImportError: cannot import name 'bakeoff'`; `1 error in 0.17s`.
- GREEN focused trước probe dry-run: `30 passed, 1 skipped in 2.27s`.
- GREEN cuối: cùng Python flags, selector `evals/contract_graph/tests` → `192 passed, 1 skipped in 7.23s`; baseline 161 ⇒ 31 test case P5 passed, 1 artifact test pending.
- Type/lint check: PASS cho 3 file Python được giao với `ruff check --config ai-service/pyproject.toml`; repo không có typecheck riêng cho ai-service.
- Unit tests: PASS; đầy đủ 17 guard phase yêu cầu, thêm CSV duplicate/missing/direction/hash, digest gold mutation, model/source consistency, dry-run metric và explicit-heldout.
- Integration tests: PASS cho runner mock/offline; kiểm lưu cost thực từ stats mock, trace whitelist, no-overwrite, clone-client global traces. Không claim live/provider integration.
- Coverage: phủ matrix 17 guard bắt buộc bằng test tương ứng; không đo line coverage.
- Test artifact `test_committed_decision_matches_report`: SKIP có lý do rõ khi report/decision live chưa có; phải chạy xanh sau lead tạo artifact. Không coi skip là phase PASS.
- Readonly CLI thật: `python -m evals.contract_graph.pairs.run verify --data-dir C:/Users/dungs/OneDrive/Documents/VSF-ai2-contract-graph/.harness/state/contract-graph-pairs` → exit 0, `verify ok`.

### Issues Encountered
- Classifier production tạo client mới, instance đầu vào không có trace phục vụ: đã sửa runner để đọc class buffer và thêm test pin.
- Cách diễn giải HUMAN cho 1/π: weighted point phải ≥ threshold và **lớn hơn conservative point**, đồng thời conservative gate fail. HT bằng conservative ở 56/60 không tự chuyển thành HUMAN chỉ vì Wilson chưa đạt. Thứ tự ngoại lệ: false DUPLICATE → insufficient → HT discrepancy thật → below threshold → cụm/McNemar → enable recommendation. Clarification đã thống nhất với lead, không thêm khoảng cho HT.
- Scope code vượt ước tính ~250 dòng của plan (501 dòng) để đủ import/preconditions/provenance/runner/gate/report; không thêm framework hoặc thay contract runtime.
- Lint toàn pairs+tests báo hai `I001` sẵn có tại `test_cg_pipeline_predictor.py` và `test_cg_resolver_eval.py`; nằm ngoài ownership, giữ nguyên và gửi lead. Lead xác nhận baseline trong `reports/p5-lint-baseline.json`.
- Dataset cây gốc VSF khác dataset worktree frozen nên readonly verify trên cây gốc fail; path worktree ở trên đã PASS.
- Không chạy full ai-service hoặc Docker suite; thuộc lead/tester. Không ghi kết quả 13 lỗi môi trường như bằng chứng của run này.

### Next Steps
- Lead nhập CSV: `python -m evals.contract_graph.pairs.run review-import --csv <data>/review/heldout_review.csv --data-dir <data> --manifest evals/contract_graph/pairs/manifest.json`; kiểm diff và commit lock trước live.
- Preflight: `python -m evals.contract_graph.pairs.run bakeoff preflight-checks --data-dir <data> --served-model claude-4.6-sonnet-medium` sau production probe; bỏ served-model chỉ cho kiểm offline và trường pending ghi rõ.
- Metric dry-run: `python -m evals.contract_graph.pairs.run bakeoff metric C --out <data>/bakeoff --dry-run`.
- Trial: `python -m evals.contract_graph.pairs.run bakeoff run C --trial 1 --out <data>/bakeoff --data-dir <data> --model cu/claude-4.6-sonnet-medium --env-file ai-service/.env --allow-heldout --budget-tokens 500000 --budget-seconds 550`; lặp thứ tự khai báo cho B/E và trial 2.
- Metric thật: `python -m evals.contract_graph.pairs.run bakeoff metric C --out <data>/bakeoff`.
- Report/decision: `python -m evals.contract_graph.pairs.run bakeoff decide --out <data>/bakeoff --data-dir <data>`; default ghi `l2-p5-bakeoff.{json,md}` và `l2-p5-decision.json`.
- Chạy lại test artifact sau live, các statistical CLI/rank và verification/review bằng lead. Runner không bật flag hoặc thay calibration.
- Unresolved: live/model/network/budget thực và artifact cuối chưa thuộc evidence của developer slice; không có cross-owner code change cần thiết.

Status: DONE_WITH_CONCERNS

Update 2026-10-09: integrity recheck added after reviewer preflight. Assembled reports carry the verified candidate universe and review-lock summary; decide rejects predictions outside the universe and mismatched lock summary fields. Regression evidence: focused P5 `43 passed, 1 skipped in 2.17s`; full eval selector `204 passed, 1 skipped in 6.74s`; Ruff PASS. Live provider trials, final artifacts, statistical rank, and independent review remain lead-owned and pending. Current counts: bakeoff.py 561 lines; test_cg_pairs_bakeoff.py 335 lines.
Summary: Hoàn tất implementation P5 trong ownership; eval/lint file đã sửa xanh và code đã freeze cho lead chạy live.
Concerns/Blockers: Test artifact live còn pending; hai lỗi lint baseline ngoài ownership đã báo lead.
Implementation update: added fail-closed validation for provider error traces, requested and served model provenance, exact trace call/token totals, directed versus undirected prediction direction, and measured `over_budget`. Added atomic per-trial claim files with dead-owner recovery and owner-safe cleanup before any provider call. Focused P5: `49 passed, 1 skipped in 2.01s`; Ruff PASS. Current counts: `bakeoff.py` 673 lines; `test_cg_pairs_bakeoff.py` 396 lines. Full eval rerun remains `209 passed, 1 skipped in 7.19s`.
Final verification update: after stale-claim TOCTOU hardening, focused P5 remains `49 passed, 1 skipped in 2.40s`; full eval selector `210 passed, 1 skipped in 7.06s`; Ruff PASS. Current counts: `bakeoff.py` 684 lines; `test_cg_pairs_bakeoff.py` 396 lines.
Final provenance update: runner now rejects any missing or invalid `prompt_tokens`, `completion_tokens`, or `total_tokens` before writing the trial artifact; per-document trace coverage, calls, tokens, and prediction counts are recorded and revalidated. Added adversarial tests for each missing usage field and trace-doc mutation. Focused P5: `53 passed, 1 skipped in 2.10s`; full eval: `214 passed, 1 skipped in 6.61s`; Ruff PASS. Current counts: `bakeoff.py` 745 lines; `test_cg_pairs_bakeoff.py` 432 lines.
Provider diagnostic update: `NineRouterClient` now records a sanitized `ResponseParseError` trace with actual served model and usage before re-raising malformed JSON. P5 accepts only this parse-error trace when Anthropic provenance, exact calls/tokens, and `classification_failed=true` all match; provider errors and GPT traces remain blocked. `client.py` is now included in `code_sha256`, so any C1 artifact made before this change is invalid for comparison and must be archived as superseded and rerun under the new fingerprint before decision. Tests: P5 eval `55 passed, 1 skipped`; full eval `216 passed, 1 skipped in 6.80s`; client trace test `4 passed`; Ruff PASS.

Final reviewer update: `classifier_client` now fails closed when exactly one dedicated pairs base URL/API key is configured, and returns no inherited `NineRouterClient` when both dedicated settings are absent; fake/non-NineRouter clients remain usable and a complete dedicated override remains supported. `_checked_trials` now requires one Anthropic `requested_model` per trial and exact equality with every trace model. Decisions expose `budget_blocked_variants` and return `HUMAN_DECISION` for any measured over-budget trial after the false-duplicate veto. Added tests for partial/no inherited client configuration, trial model mutation, and over-budget decision policy. Targeted builder/bakeoff tests: `95 passed`; full eval selector: `219 passed`; targeted Ruff: PASS. These changes alter the P5 code fingerprint; lead must archive any prior C1 result and rerun trials under the new fingerprint. No live provider calls or data/env/manifest edits were made.

Live rerun update 2026-10-09: `/v1/models` with the user-supplied endpoint/key exposed available Claude routes. `cu/claude-4.6-sonnet-medium` was selected after a successful probe (`served_model=claude-4.6-sonnet-medium`, family `anthropic`). The prior model artifacts were archived; C1/B1/E1/C2/B2/E2 completed under the current fingerprint and lock. All `recall_any` values are `0/101`; E exceeds the declared token budget in both trials. Decision is `HUMAN_DECISION`; rank is `tie_within_noise` with no winner. Independent tester/reviewer and P5 verification remain pending.

## Biên nhận developer P5 — live rerun sau chuyển model (2026-10-09)

### Phạm vi và đầu vào

- Đã đối chiếu lại phase P5, HG-1 lock, preflight và các artifact live hiện tại. Không gọi lại provider trong biên nhận này.
- `/v1/models` qua endpoint/key do người dùng cung cấp cho thấy route cũ bị quota; đã chọn `cu/claude-4.6-sonnet-medium` sau probe thành công.
- Model yêu cầu: `cu/claude-4.6-sonnet-medium`; model phục vụ: `claude-4.6-sonnet-medium`; family: `anthropic`.
- Artifact của model trước được lưu tại `tmp/p5-superseded-before-model-switch`; chỉ dùng sáu trial dưới fingerprint hiện tại `3546beeb6a72fd9795a3b83464b1a86b2bb8ab069289876701406717b7e11a58`.
- Thứ tự chạy và lock được giữ nguyên: `C1, B1, E1, C2, B2, E2`; report dùng `status=OBSERVED`, `decisions_sha256=1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64`.

### Sáu trial live

| Trial | Variant | recall_any | LLM calls | Tokens | elapsed_s | over_budget |
|---|---:|---:|---:|---:|---:|---:|
| C1 | C | 0/101 | 28 | 150204 | 51.482959 | no |
| B1 | B | 0/101 | 27 | 144482 | 47.588798 | no |
| E1 | E | 0/101 | 89 | 536078 | 109.050338 | yes |
| C2 | C | 0/101 | 28 | 150204 | 53.787138 | no |
| B2 | B | 0/101 | 27 | 144482 | 47.773808 | no |
| E2 | E | 0/101 | 89 | 536078 | 111.339566 | yes |

Budget khai báo cho trial là `500000` tokens và `550` giây. E vượt trần token ở cả hai trial nên được đưa vào `budget_blocked_variants`; C/B nằm trong budget.

### Kết quả và acceptance evidence

- `evals/contract_graph/reports/l2-p5-bakeoff.json`: sáu artifact hợp lệ, cùng lock/fingerprint/model provenance.
- `evals/contract_graph/reports/l2-p5-decision.json`: `verdict=HUMAN_DECISION`, `recommendation_only=true`, không bật cờ runtime; tất cả nhãn đều có recall `0/101` tổng thể theo trial worst-case và McNemar C/B, C/E đều `b=0,c=0`, inconclusive.
- `plans/261008-1500-ai2-contract-graph-implicit/bakeoff-verdict.json`: run `contract-pairs-261009-cu46-medium`, `verdict=tie_within_noise`, `winner=null`, `over_budget=["E"]`.
- Không diễn giải kết quả `0/101` là đạt chất lượng; P5 cần quyết định người dùng và giữ candidate tắt.

### Lệnh xác minh đã chạy

```text
uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests/test_cg_pairs_bakeoff.py ai-service/tests/test_llm_complete_json.py
# 62 passed, 0 failed

uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests
# 219 passed, 0 skipped, 0 failed

uv run --project ai-service --frozen --extra web --extra dev ruff check --config ai-service/pyproject.toml evals/contract_graph/pairs/bakeoff.py evals/contract_graph/pairs/run.py evals/contract_graph/tests/test_cg_pairs_bakeoff.py ai-service/app/llm/client.py ai-service/tests/test_llm_complete_json.py
# All checks passed!

python -m evals.contract_graph.pairs.run verify --data-dir .harness/state/contract-graph-pairs
# verify ok

python -m evals.contract_graph.pairs.run bakeoff decide --out .harness/state/contract-graph-pairs/bakeoff --data-dir .harness/state/contract-graph-pairs
# HUMAN_DECISION
```

Các artifact thống kê/rank và báo cáo tester độc lập đã được tạo từ cùng snapshot. Receipt này không tạo `verification-P5.json` hay `review-decision.json`; đó là gate cuối do lead và reviewer sở hữu.

Status: DONE_WITH_CONCERNS
Summary: Đã hoàn tất phần live rerun và ghi nhận đầy đủ sáu trial dưới model Anthropic khả dụng mới; kết quả có tính toàn vẹn nhưng recall bằng 0, E vượt ngân sách, nên verdict giữ ở HUMAN_DECISION.
Concerns/Blockers: Chờ reviewer cuối và gate verification/review của lead; không ghi API key vào report.

## Biên nhận developer P5 — snapshot cx/gpt-6-sol (2026-10-09)

### Snapshot live cuối

- Người dùng cho phép dùng model khác Claude; các route Claude trước đó trả response rỗng và bị archive vì client mới fail-closed.
- Requested model cx/gpt-6-sol; served model gpt-6-sol; family openai; frozen labeler gpt-4o-mini-2024-07-18. Tên model cụ thể khác nhau và mọi trace đều nhất quán.
- Lock HG-1: commit 836c91ae8b350ae329546e02cc0808f9ce6954ea, decisions_sha256=1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64.
- Sáu trial theo đúng thứ tự C1, B1, E1, C2, B2, E2; chỉ artifacts dưới fingerprint hiện tại được dùng.

| Trial | recall_any | calls | tokens | elapsed_s | over_budget |
|---|---:|---:|---:|---:|---|
| C1 | 3/101 | 28 | 54.743 | 204,676 | no |
| B1 | 2/101 | 27 | 51.415 | 186,924 | no |
| E1 | 9/101 | 89 | 241.653 | 635,613 | yes |
| C2 | 4/101 | 28 | 55.115 | 215,828 | no |
| B2 | 3/101 | 27 | 51.388 | 178,249 | no |
| E2 | 9/101 | 89 | 241.307 | 639,616 | yes |

### Decision and verification

- l2-p5-decision.json: HUMAN_DECISION, recommendation_only=true, budget_blocked_variants=[E].
- Rank contract-pairs-261009-cx-gpt6sol: E > C > B; rank winner is not enablement because E is over-budget.
- Dataset verify ok; eval suite 223 passed; targeted Ruff on changed scope All checks passed.
- Candidate flag remains off. This receipt contains no endpoint, prompt, response text, or API key.
- Remaining gate work: independent tester/reviewer reports and cook verification/review artifacts.

## Developer receipt audit — current `cx/gpt-6-sol` snapshot (2026-10-09)

Phần này là evidence hiện tại của P5. Các snapshot model trước nằm ở các section lịch sử trong report và không được dùng làm số liệu hiện tại.

### Artifact và model-family policy

- Run hiện tại: `contract-pairs-261009-cx-gpt6sol`; sáu artifact `C1 B1 E1 C2 B2 E2` đều `status=OBSERVED`, cùng `code_sha256`, HG-1 lock `836c91ae8b350ae329546e02cc0808f9ce6954ea` và `decisions_sha256=1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64`.
- Requested model: `cx/gpt-6-sol`; served model: `gpt-6-sol`; 288/288 traces có cùng served model, `error_type=null`.
- Policy hiện tại trong `evals/contract_graph/pairs/models.py:16-18,43-46` cho phép classifier thuộc family đã nhận diện (`anthropic|google|openai`) và yêu cầu model cụ thể khác labeler. Preflight hiện tại xác nhận `classifier_family=openai`, labeler `gpt-4o-mini-2024-07-18`, `classifier_model_differs_from_labeler=true`, `preflight_ok=true`.
- Guard thực thi cùng policy tại `evals/contract_graph/pairs/bakeoff.py:144-148,364-365,391-394`; artifact hiện tại vượt qua các guard này.

### Sáu trial hiện tại

| Trial | recall_any | LLM calls | Tokens | elapsed_s | over_budget |
|---|---:|---:|---:|---:|---|
| C1 | 3/101 | 28 | 54,743 | 204.675559 | no |
| B1 | 2/101 | 27 | 51,415 | 186.923525 | no |
| E1 | 9/101 | 89 | 241,653 | 635.613463 | yes |
| C2 | 4/101 | 28 | 55,115 | 215.827651 | no |
| B2 | 3/101 | 27 | 51,388 | 178.249314 | no |
| E2 | 9/101 | 89 | 241,307 | 639.616101 | yes |

E vượt budget thời gian `550` giây ở cả hai trial; token budget `500000` không bị chạm. Vì vậy `budget_blocked_variants=["E"]`. Rank artifact xếp `E > C > B`, nhưng E không đủ điều kiện enable.

### Empty-response guard audit

- `ai-service/app/llm/client.py:172-177` coi content rỗng hoặc chỉ whitespace là `EmptyResponseError`, ghi `response_empty=true` vào trace an toàn rồi raise `LLMEmptyResponseError`; không biến response rỗng thành JSON `{}`.
- Test pin nằm tại `ai-service/tests/test_llm_complete_json.py:73-88` và kiểm tra exception, error type, cờ `response_empty`, model phục vụ và usage.
- Đối chiếu sáu artifact hiện tại: 288 trace, `error_traces=0`, `zero_completion=0`, `bad_total=0`; mỗi trace có `total_tokens = prompt_tokens + completion_tokens`. Đây là snapshot có completion thực, khác với artifact response rỗng đã bị loại khỏi current evidence.

### Decision và verification evidence

- `evals/contract_graph/reports/l2-p5-decision.json`: `verdict=HUMAN_DECISION`, `recommendation_only=true`, `budget_blocked_variants=["E"]`; candidate flag tiếp tục tắt.
- `plans/261008-1500-ai2-contract-graph-implicit/bakeoff-verdict.json`: run `contract-pairs-261009-cx-gpt6sol`, rank `winner=E`, nhưng E bị budget block nên không có enablement tự động.
- Dataset verify:

```text
uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m evals.contract_graph.pairs.run verify --data-dir .harness/state/contract-graph-pairs
# verify ok
```

- Decision recomputation:

```text
uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m evals.contract_graph.pairs.run bakeoff decide --out .harness/state/contract-graph-pairs/bakeoff --data-dir .harness/state/contract-graph-pairs
# HUMAN_DECISION
```

- Full eval:

```text
uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests
# 223 passed, 0 failed
```

- Targeted Ruff:

```text
uv run --project ai-service --frozen --extra dev ruff check --config ai-service/pyproject.toml ai-service/app/llm/client.py ai-service/app/pipeline/contract_graph/pair_builder.py ai-service/app/pipeline/contract_graph/pair_classifier.py ai-service/tests/test_contract_graph_pair_builder.py ai-service/tests/test_llm_complete_json.py evals/contract_graph/pairs/bakeoff.py evals/contract_graph/pairs/models.py evals/contract_graph/pairs/predictor.py evals/contract_graph/pairs/run.py evals/contract_graph/tests/test_cg_pairs_bakeoff.py evals/contract_graph/tests/test_cg_pairs_labeler.py evals/contract_graph/tests/test_cg_pairs_predictor.py
# All checks passed!
```

Status: DONE_WITH_CONCERNS (historical cx/gpt-6-sol snapshot; superseded by the final cx/gpt-5.5 refresh below)
Summary: Snapshot `cx/gpt-6-sol` có provenance và model-family hợp lệ, empty-response guard đã được pin bằng test và không có trace rỗng trong 288 trace hiện tại. Full eval `223 passed` và Ruff PASS; decision vẫn là `HUMAN_DECISION` vì E vượt budget và không được tự động enable.
Concerns/Blockers: Reviewer receipt cần được refresh riêng cho snapshot cx/gpt-6-sol; audit này không tạo verification/review artifact và không gọi provider.

## Final refresh — cx/gpt-5.5 (2026-10-10)

The implementation refresh completed against the six-trial `cx/gpt-5.5` snapshot. The deterministic gate now reports `KEEP_OFF_INSUFFICIENT_N` before non-gating budget advisory when a C label denominator is below `MIN_N`; E remains over the time budget and no runtime enablement is performed. Verification/review artifacts are PASS, full contract-graph eval is `225 passed`, focused bakeoff tests are `61 passed`, and targeted Ruff passes.
