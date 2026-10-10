# Contract graph recall thấp — Debug Report

## Executive Summary

- **Issue:** P3/P5 report `CONFLICT`/`DUPLICATE` recall rất thấp dù classifier không có lỗi provider/schema rõ ràng.
- **Impact:** Số recall hiện tại không đủ để chọn prompt/model hay đề xuất enablement; nếu tune theo số này sẽ làm tăng false positive.
- **Root cause:** Đường đánh giá dev đang tính nhãn GPT chưa được duyệt như gold (`approved_only=False`), trong khi nhiều positive GPT dev không khớp rubric quan hệ. Vì vậy false negative của classifier và lỗi nhãn bị gộp thành một recall thấp.
- **Status:** Identified; repro đỏ đã có.
- **Next step:** Chạy `hs:fix` trên test repro để buộc dev report gắn trạng thái calibration-only và chặn dùng unreviewed labels để đóng recall gate.

## Timeline

- 2026-10-10 — P5 baseline dùng `cx/gpt-5.5` → `gpt-5.5`: C1/B1/E1/C2/B2/E2 lần lượt 5/101, 2/101, 7/101, 4/101, 3/101, 10/101.
- 2026-10-10 — P1/P2 tách candidate coverage; variant E có coverage đầy đủ trên positive dev nhưng classifier vẫn không tạo positive C/D an toàn.
- 2026-10-10 — P3 `pairs-v4` chạy dev: C đúng 0/5, D đúng 0/2; raw `UNRELATED` 22 và `duplicate_value_mismatch` 3; không có provider/no-answer/schema error.
- 2026-10-10 — Probe từng cặp bằng batch size 1 trên E: C → 3 `GENERAL_SPECIFIC`, 2 `UNRELATED`; D → 1 `GENERAL_SPECIFIC`, 1 `UNRELATED`.
- 2026-10-10 — Probe tổng hợp độc lập: 30/15 ngày → `CONFLICT`, cùng nghĩa vụ cùng giá trị → `DUPLICATE`, quy tắc chung/ngoại lệ → `GENERAL_SPECIFIC`; served model `gpt-5.5`.
- 2026-10-10 — Prompt v5 làm một false `DUPLICATE`; đã loại bỏ và khôi phục v4.

## Technical analysis

### Evidence

1. **Candidate không phải nguyên nhân duy nhất.** Trên 7 positive C/D của dev, E bao phủ 5/5 C và 2/2 D; vì vậy mở rộng candidate không thể tự giải thích C/D = 0.
2. **Không phải lỗi egress/provider/validator.** Canonical v4 trace ghi served `gpt-5.5`, không có `no_answer`, malformed, ungrounded span hoặc citation rejection. Các rejection chính là model trả `UNRELATED` và validator từ chối numeric mismatch của `DUPLICATE`.
3. **Không phải batching đơn thuần.** Khi gửi từng positive C/D một lần với variant E, model vẫn không trả C/D nào; nó chọn GS hoặc UNRELATED.
4. **Classifier nhận được quan hệ rõ ràng.** Probe tổng hợp trả đúng C/D/GS và exact spans, chứng minh model/client/schema có thể thực hiện nhiệm vụ khi cặp phù hợp rubric.
5. **Nhãn dev là nguồn nhiễu.** Dev report hiện đọc toàn bộ 215 GPT labels, trong đó C=5 và D=2, không có `approved=true`. Kiểm tra ngữ nghĩa độc lập trên các id positive cho thấy phần lớn C/D được gán giữa các nghĩa vụ/sự kiện khác nhau hoặc là trường hợp chung-riêng; một D là cặp rõ ràng hơn. Đây là audit chẩn đoán, chưa phải quyết định gold của người dùng.
6. **Điểm code gây lỗi đánh giá:** `predictor.build_report()` gọi `score_relations(..., approved_only=(split == "heldout"))`; dev luôn dùng `approved_only=False` và báo `gpt-labels (approved=false), dev`. Nhãn chưa duyệt vì thế đi vào mẫu số recall và có thể dùng để kết luận P3.

### Eliminated hypotheses

1. **H1 — C/B top-k là nguyên nhân duy nhất:** loại trừ. E có coverage 100% trên C/D dev nhưng vẫn 0/0 đúng.
2. **H2 — provider/model family hoặc schema làm rơi positive:** loại trừ bằng served-model trace, zero `no_answer`/malformed/grounding rejection, và probe tổng hợp pass.
3. **H3 — batching làm mất toàn bộ quan hệ:** loại trừ là nguyên nhân duy nhất bằng probe batch size 1; kết quả vẫn không khớp C/D GPT labels.
4. **H4 — chỉ cần nới prompt để pass:** bác bỏ qua probe v5; D tăng nhưng xuất hiện false `DUPLICATE`, vi phạm veto an toàn.

### Root cause (confirmed)

`labels.gpt.jsonl` được tạo bởi labeler đề xuất và không có human approval. `predict_split()` chuyển chúng thành `gold` với `approved=False`; `build_report()` lại tắt bộ lọc approval cho split dev. Scorer vì thế coi mọi GPT positive là positive chuẩn để tính recall. Nhiều cặp trong số đó không thỏa định nghĩa C/D của classifier; model bảo thủ trả GS/UNRELATED là phù hợp rubric hơn, nhưng bị ghi là false negative. Candidate miss và prompt conservatism còn tồn tại, nhưng không thể được tách hoặc tối ưu đúng khi gold dev chưa được duyệt.

## Failing repro test

`evals/contract_graph/tests/test_cg_pairs_predictor.py::test_dev_report_blocks_unreviewed_gold_from_being_called_recall`

Run:

```text
uv run --project ai-service --frozen --extra web --extra dev pytest -q evals/contract_graph/tests/test_cg_pairs_predictor.py -k dev_report_blocks_unreviewed_gold
```

Observed failure: report hiện trả `ground_truth == "gpt-labels (approved=false), dev"` và không có `evaluation_gate`/`gold_provenance`; test yêu cầu dev unreviewed chỉ được dùng calibration-only.

## Open questions

- Cần một tập dev có quyết định `approve|relabel|reject` của người dùng (ít nhất các positive C/D và các probe calibration) trước khi kết luận recall thật hoặc chọn prompt mới.
- Sau khi có reviewed dev gold, mới đánh giá riêng candidate miss, classifier miss và validator rejection; held-out vẫn sealed cho đến P5.


## Fix verification

- `build_report()` now scores only `approved is True`; missing, false and invalid approval values are exposed in `gold_provenance` and block the dev gate.
- P5 `preconditions()` fails before held-out selection/model calls unless the dev report is `OBSERVED`, `evaluation_gate=PASS`, contains exclusively reviewed gold, passes the C/D classifier gate, and carries a manifest-locked dev-review digest.
- P5 now also requires a manifest-locked dev-report file digest and real HG-2 review/sizing artifacts; missing, stale or path-traversing receipts are blocked before any held-out call.
- `--dev-review` is the explicit JSONL path for a future human dev audit; IDs are checked against the frozen dev pool, labels/directions and JSON booleans are validated, and the file SHA is recorded in the report. The manifest lock requires at least one approved C and D row.
- Fresh `cx/gpt-5.5` dev run after the fix: status `BLOCKED_UNREVIEWED_DEV_GOLD`, approved `0`, unapproved `215`, 12 predictions; weak diagnostic CONFLICT `0/5`, DUPLICATE `0/2`, raw `UNRELATED` `23`, three `duplicate_value_mismatch` validation/policy rejections, false DUPLICATE `0`.

## Follow-up gate fix

- Review found a second independent bypass: `predict --split heldout --allow-heldout` could construct the network client and call `predictor.predict_split()` without P3/P4/commit preconditions.
- `_predict()` now calls `bakeoff.preconditions(..., served_model=args.model)` before importing or constructing `NineRouterClient`; a failed lock returns exit code `2` and no held-out document is read.
- Regression coverage proves the CLI stops before client construction. Verification after the fix: eval `251 passed, 1 skipped`, AI focused tests `144 passed`, required Ruff rules pass, manifest verify pass, artifact verification well-formed, code review `PASS`.


## Follow-up: reviewed calibration and false-DUPLICATE provenance

- The seven-row dev audit was recorded from the user's decisions. Four rows are approved gold; two are relabeled GENERAL_SPECIFIC; three are rejected and excluded from recall denominators.
- Prompt `pairs-v7` adds a Vietnamese calibration rule for the approved DUPLICATE case: listing more fields is not GENERAL_SPECIFIC without a real subset, exception, condition, or actor change.
- Canonical dev run with `cx/gpt-5.5` served `gpt-5.5`: 10 relations, CONFLICT `1/1`, DUPLICATE `1/1`, observed false DUPLICATE `0`, 23 raw `UNRELATED` and five `duplicate_value_mismatch` rejections. P3 is `PASS`.
- A provenance review found that a prediction on a reviewed reject was previously counted as `unreviewed`. The scorer now counts every `source=user-review` row as observed false-negative evidence, including `approved=false`, while excluding that row from recall gold. Regression coverage verifies the P3 gate blocks it.
- P4/HG-2 is the only remaining execution gate. The human must select the Wilson lower recall floor and approve any expanded scored gold before held-out bake-off; runtime remains off.



## Follow-up: HG-1 loader provenance guard

- The held-out decision loader now requires `source=user-review`, strict boolean `approved`, valid labels/directions on approvals, no direction on undirected labels, and empty label/direction on rejects.
- Regression coverage rejects both a non-human `source=gpt` approval and a rejected row that still carries `DUPLICATE`.
- After this fix: eval contract graph `257 passed, 1 skipped`; AI focused tests `144 passed`; Ruff and manifest verification pass. P3 report fingerprint and manifest lock were refreshed without reading held-out data.



## Follow-up: final HG-1 duplicate-row hardening

- The loader now rejects duplicate selection `pair_id` rows even if a forged manifest changes `n_rows`; the production bake-off path and helper enforce the same uniqueness invariant.
- Regression/eval status after hardening: predictor tests 39 passed; full eval and AI-service focused suites are rerun below in the verification record.
- Code review verdict: `PASS`. P3 report digest and manifest lock were refreshed after this code change.
