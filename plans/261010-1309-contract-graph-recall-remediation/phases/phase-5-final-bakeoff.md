# P5 — Final bake-off và decision

## Mục tiêu

Chạy lại bằng chứng cuối sau khi candidate/classifier/data đã freeze; quyết định chỉ là recommendation-only và không tự bật cờ.

## Dependencies

P1 diagnostic, P2 candidate report, P3 classifier calibration, P4 HG-2 approval/manifest lock đều phải PASS. Nếu bất kỳ phase nào fail, không chạy full live bake-off.

## Protocol

1. `preflight-checks`: manifest verify, lock commit, decisions SHA, code/prompt fingerprint, served model, candidate counts và budget.
2. Chạy C/B/E × 2 trial cùng một requested/served model hợp lệ.
3. Re-derive metrics từ trial artifacts; không copy số tay.
4. Chấm candidate coverage, recall observed/weighted, conservative precision, Wilson, cluster interval, false duplicate, McNemar, tokens và latency.
5. `decide` theo thứ tự: false duplicate → insufficient N/threshold → recall safety gate HG-2 → budget → discrepancy → enablement.

## Hard gates

- `CONFLICT` hoặc `DUPLICATE` zero recall → `KEEP_OFF_*`.
- Recall không đạt floor HG-2 → `KEEP_OFF_BELOW_RECALL` (hoặc verdict tương đương được ghi trong decision schema), không dùng `HUMAN_DECISION` để lách gate.
- Conservative precision không đạt `MIN_N=60` và Wilson lower `0.85` → `KEEP_OFF_INSUFFICIENT_N`/`KEEP_OFF_BELOW_THRESHOLD`.
- E vượt `550s` hoặc `500,000 tokens` → không production winner.
- Bất kỳ model family mismatch, provider error, trace mismatch, decision SHA mismatch, hoặc candidate fuera universe → BLOCKED.

## Acceptance artifacts

- `evals/contract_graph/reports/l2-p6-bakeoff.json` và `.md`.
- `evals/contract_graph/reports/l2-p6-decision.json`.
- `docs/ai2/AI2-20-contract-graph-pairs.vi.md` cập nhật số liệu hiện hành.
- `verification-P5.json`, `review-decision.json`, full eval, focused tests, Ruff và manifest verify PASS.
- Runtime flag chỉ được xem xét nếu decision là `ENABLE_CANDIDATE` và có human approval riêng; mọi verdict khác giữ off.
