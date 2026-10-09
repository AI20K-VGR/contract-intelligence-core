# P5 — independent pre-execution review

**Ngày:** 2026-10-09
**Phạm vi:** `evals/contract_graph/pairs/bakeoff.py`, `evals/contract_graph/pairs/run.py`, `ai-service/app/llm/client.py`, `evals/contract_graph/tests/test_cg_pairs_bakeoff.py`, `ai-service/tests/test_llm_complete_json.py`
**Đối chiếu:** `phases/phase-5-bakeoff-rerun.md`, predictor/score contracts P3/P4, `review_policy.py`
**Provider live bởi reviewer:** không gọi; không chạy held-out.

## Verdict

**PASS** cho implementation/probe pre-execution gate. Hai blocker integrity của vòng trước và blocker parse-provenance hiện đã được sửa; focused/full tests, client tests, Ruff và adversarial probes đều đạt. P5 chưa được coi là hoàn tất cho đến khi lead supersede artifact C1 cũ, chạy lại trial theo code snapshot hiện tại, rồi chạy held-out C/B/E × 2, rank/statistical checks và tạo final artifacts theo kế hoạch.

## Scope

- `bakeoff.py`: runner fail-closed với trace/model/call/token/direction/budget và atomic claim trước provider call; report kiểm tra provenance theo từng document.
- `run.py` và `test_cg_pairs_bakeoff.py`: CLI và regression/adversarial coverage cho các guard trên.
- `hs-run review next --effort low`: scope `large`, suggested effort `high`, 17 rules applied; `code.fan_in` unavailable vì worktree không có `codemap.yaml`.
- Scout edge cases: thiếu usage, trace coverage theo document, per-document totals/prediction counts, concurrent claim, model/call/direction/budget mutation.

## Blocking issues

Không còn blocker được chứng minh trong scope pre-execution. Probe môi trường trước đây ghi `usage: null`; probe hiện tại đã được chạy lại và có usage hợp lệ. Reviewer chỉ xác thực artifact/provenance offline, không gọi live provider.

## Latest parse-provenance recheck

- `NineRouterClient.complete_json()` ghi `served_model`, latency và usage trước khi parse; khi `_parse_json()` ném `JSONDecodeError`, nó chỉ lưu trace metadata an toàn với `error_type=ResponseParseError`, rồi re-raise (`ai-service/app/llm/client.py:159-177`). Không có response body, prompt hay credential trong trace.
- Runner chỉ chuyển parse error thành `classification_failed=true` sau khi đã kiểm tra served model Anthropic và đủ token fields (`bakeoff.py:378-401`). Provider errors khác `ResponseParseError` bị reject.
- Decision gate yêu cầu `error_type` thuộc `{None, ResponseParseError}`, served/requested model đều Anthropic, `llm_calls` khớp fallback (1/2), token totals khớp và `classification_failed` đúng với parse-error classification (`bakeoff.py:605-637`). GPT/provider-error traces vẫn reject.
- `client.py` hiện nằm trong `FINGERPRINT_FILES` và được hash trong preconditions (`bakeoff.py:41,182-191`); C1 artifact được tạo trước parse-provenance fix không thể dùng cho recommendation và phải chạy lại.

## Production probe recheck

`plans/261008-1500-ai2-contract-graph-implicit/reports/p5-production-probe.json:2-17` hiện ghi:

- requested model `ag/claude-sonnet-4-6`, served model `claude-sonnet-4-6`, family `anthropic`;
- `prompt_tokens=2038`, `completion_tokens=13`, `total_tokens=2051`;
- `2051 = 2038 + 13`, `fallback_without_json_format=false`;
- `elapsed_s=4.905`, trace `latency_ms=4905.0`, `results_list=true`.

Offline validation bằng `models.family` in ra `PROBE_VALID claude-sonnet-4-6 2038 13 2051 False`, exit 0. Các trường này đáp ứng fail-closed usage/model/family contract của runner.

## Adversarial recheck

- Thiếu từng trường `prompt_tokens`, `completion_tokens`, hoặc `total_tokens`: `test_runner_missing_usage_field_writes_no_artifact` xác nhận runner thoát 2 và không tạo `t1/C.json`.
- Đổi trace của mọi document thành `d0`: `decide()` reject với `document trace coverage`.
- Đổi per-document call/token/prediction counts: đều reject; `doc_provenance` phải phủ đúng held-out docs và totals phải khớp traces.
- Claim cạnh tranh: guard `O_CREAT | O_EXCL` tạo claim trước predictor/provider; test claim tồn tại xác nhận provider không bị gọi.
- Trace lỗi/provider, served family, exact call/token totals, direction, `over_budget`, prediction universe và per-document provenance đều được kiểm tra trong `_checked_trials()` (`bakeoff.py:585-667`).
- Parse-error probe offline qua `NineRouterClient` tạo `ResponseParseError` với served Anthropic và usage `11/7/18`; runtime trả fallback có kiểm soát, không gọi provider thật.
- `decide()` nhận parse-error trace chỉ khi `classification_failed=true`, usage/call counts chính xác; parse-error với GPT hoặc provider error đều bị reject trong regression tests.
- `trial.requested_model` lệch top-level vẫn được `decide()` chấp nhận nếu trace thực tế vẫn đúng Anthropic. Đây là metadata audit follow-up; không làm suy yếu gate served model/family hiện tại. Có thể bind trường này với trace nếu cần audit chặt hơn.

## Checklist

- Concurrency: **PASS** — atomic claim trước provider call và regression test.
- Error boundary: **PASS** — missing/error usage fail closed trước serialization.
- API contract/provenance: **PASS** — trace coverage, calls, token totals và prediction counts được bind theo từng document.
- Input/auth/data exposure: **PASS** trong scope — trace serialization chỉ whitelist metadata, không ghi prompt/span/key.
- N+1/query: không áp dụng.
- Complexity-only: không có finding độc lập cần chặn.

## Evidence

- Current focused: cùng profile với `evals/contract_graph/tests/test_cg_pairs_bakeoff.py` → **55 passed, 1 skipped in 2.25s**, exit 0.
- Full contract-graph tests: cùng profile với `evals/contract_graph/tests` → **216 passed, 1 skipped in 6.63s**, exit 0.
- Client tests: `uv run --project ai-service --frozen --extra web --extra dev python -m pytest -q -p no:cacheprovider ai-service/tests/test_llm_complete_json.py` → **4 passed in 1.76s**, exit 0.
- Ruff: `uv run --project ai-service --frozen --extra web --extra dev ruff check --config ai-service/pyproject.toml evals/contract_graph/pairs/bakeoff.py evals/contract_graph/pairs/run.py ai-service/app/llm/client.py evals/contract_graph/tests/test_cg_pairs_bakeoff.py ai-service/tests/test_llm_complete_json.py` → **All checks passed**, exit 0.
- Offline parse-error probe → **`PARSE_TRACE_VALID ResponseParseError anthropic/claude-sonnet-4-6 11 7 18 1`**, exit 0.
- Offline probe/model/provenance mutations: document coverage, per-document totals và missing usage đều reject; không có live/provider call.
- `test_committed_decision_matches_report` vẫn skip vì chưa có held-out report/decision thật; đây là phase follow-up, không phải blocker của pre-execution gate.

## Plan follow-up

1. Bỏ/supersede C1 artifact được tạo trước khi `client.py` có parse-provenance fix; fingerprint mới sẽ chặn artifact cũ.
2. Chạy lại C1 theo code snapshot hiện tại, sau đó chạy held-out C/B/E × 2 theo thứ tự khóa.
3. Chạy rank/statistical checks và tạo final report/decision artifacts.
4. Chạy ship review sau khi các artifact held-out tồn tại.

## Unresolved questions

- Có yêu cầu audit chặt buộc `trial.requested_model` phải bằng `trace.model` ở mọi document hay không? Hiện chưa phải blocker vì actual served model/family và usage đã được kiểm tra.
