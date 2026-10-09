# Rà soát độc lập cuối P5 — snapshot cx/gpt-6-sol

**Ngày:** 2026-10-09  
**Phạm vi:** diff P3–P5, client/classifier, model-family gate, bake-off provenance, sáu artifact live, decision/rank/preflight/probe và tài liệu deviation. Không gọi provider/API và không đọc hoặc ghi secret.
**Verdict:** **PASS_WITH_RISK**

## Kết luận

Snapshot hiện tại có thể dùng làm bằng chứng bake-off quan sát được. Sáu trial C1, B1, E1, C2, B2, E2 đều là artifact mới dưới cùng code fingerprint, review lock và model provenance. Guard response rỗng đã được sửa fail-closed; các artifact Claude có completion bằng 0 được lưu ở archive superseded và không được đưa vào scoreboard.

Verdict nghiệp vụ vẫn là HUMAN_DECISION và cờ runtime phải giữ tắt. Recall thấp hơn nhiều so với ngưỡng, số mẫu theo nhãn chưa đủ, còn E vượt ngân sách ở cả hai trial. Rank cơ học ghi E đứng đầu, nhưng E bị budget block nên không phải quyết định enablement.

## Bằng chứng snapshot

| Trial | recall_any | calls | tokens | elapsed_s | over_budget |
|---|---:|---:|---:|---:|---|
| C1 | 3/101 = 0.0297 | 28 | 54,743 | 204.675559 | no |
| B1 | 2/101 = 0.0198 | 27 | 51,415 | 186.923525 | no |
| E1 | 9/101 = 0.0891 | 89 | 241,653 | 635.613463 | yes |
| C2 | 4/101 = 0.0396 | 28 | 55,115 | 215.827651 | no |
| B2 | 3/101 = 0.0297 | 27 | 51,388 | 178.249314 | no |
| E2 | 9/101 = 0.0891 | 89 | 241,307 | 639.616101 | yes |

Nguồn số liệu là .harness/state/contract-graph-pairs/bakeoff/t1 và t2, cùng các trường recall_any, llm_calls, prompt_tokens, completion_tokens, elapsed_s và over_budget trong từng JSON.

- Mọi trial có status OBSERVED, prompt_version pairs-v1, requested_model cx/gpt-6-sol và đúng một served_model gpt-6-sol.
- Sáu artifact dùng review_lock_commit 836c91ae8b350ae329546e02cc0808f9ce6954ea, decisions_sha256 1271c998e07c6085345522e0da394b293ae6de6ea19a03b20962170e3f805a64 và cùng code_sha256 map.
- Kiểm tra các trace trong sáu JSON không thấy error_type, completion_tokens bằng 0 hoặc total_tokens lệch tổng prompt_tokens + completion_tokens; false_duplicate có observed=0 và unreviewed=0 ở mọi trial.
- Manifest labeler là gpt-4o-mini-2024-07-18 thuộc họ OpenAI. Classifier phục vụ gpt-6-sol thuộc họ OpenAI và khác model cụ thể của labeler.
- evals/contract_graph/reports/l2-p5-decision.json ghi verdict HUMAN_DECISION, recommendation_only=true và budget_blocked_variants=[E]. plans/261008-1500-ai2-contract-graph-implicit/bakeoff-verdict.json ghi rank E > C > B nhưng over_budget=[E].

## Findings

### P5-R1 — Chất lượng quan sát thấp và E vượt ngân sách — rủi ro trung bình

Decision dùng đúng ngưỡng review_policy: min_n=60 và min_wilson_lower=0.85. Cả C/B đều có recall_any chỉ 2–4/101; E đạt 9/101 nhưng 635.613463 và 639.616101 giây, cùng vượt trần 550 giây; tổng token E là 241,653 và 241,307 trong khi trần là 500,000 nên vi phạm ở thời gian. Vì vậy HUMAN_DECISION là diễn giải đúng. Không có cơ sở để bật candidate hoặc coi E là winner sản phẩm.

Đây là risk nghiệp vụ được ghi nhận, không phải lỗi toàn vẹn artifact. Người dùng vẫn cần quyết định bước tiếp theo trước enablement.

### P5-R2 — Deviation model family đã được phản ánh trong docs hiện tại

Finding này đã được xử lý trong snapshot hiện tại. phase-3-llm-pair-classifier.md:16, :190 và phase-5-bakeoff-rerun.md:16, :150 hiện dùng classifier family được nhận diện, không khóa served_model vào Anthropic. Amendment phase-3:207–209, amendment phase-5:169–171, plan.md:295–308 và HANDOFF.md:31 ghi rõ người dùng cho phép anthropic|google|openai, labeler là OpenAI, classifier phải khác model cụ thể labeler; snapshot cx/gpt-6-sol khớp quy tắc này.

Các cụm Claude/Anthropic còn lại là lịch sử, không phải gate hiện tại: plan.md:37 mô tả thứ tự dự kiến ban đầu; plan.md:236 và :279–286 ghi risk/validation của các lần thử trước; plan.md:305 ghi lại quyết định mở rộng. Không còn mâu thuẫn normative cần block review.

### P5-R3 — Guard family ở classifier còn lặp prefix — rủi ro thấp, không ảnh hưởng snapshot

models.py:26–57 là nguồn quy tắc family chính, nhận anthropic, google và openai. predictor.py dùng classifier_family_ok và kiểm model cụ thể khác labeler. Tuy nhiên pair_classifier.py:213–215 vẫn dùng tuple prefix thủ công, chỉ liệt kê o1, o3 và o4; trong khi models.py:21 nhận mọi o<number>. Model hiện tại là gpt-6-sol nên không có tác động lên sáu artifact. Đây là follow-up rủi ro thấp; không block snapshot. Sửa guard sẽ đổi code fingerprint và buộc chạy lại toàn bộ sáu trial, nên không thực hiện trong gate này.

## Guard code đã kiểm tra

- Empty response: ai-service/app/llm/client.py:172–177 đánh dấu EmptyResponseError, ghi trace metadata an toàn và raise; không còn biến content rỗng thành JSON {}. Test tương ứng nằm trong ai-service/tests/test_llm_complete_json.py.
- Provider/trace gate: evals/contract_graph/pairs/bakeoff.py:387–405 chặn provider error và bắt buộc usage hợp lệ; :626–668 chỉ chấp nhận trace không lỗi hoặc ResponseParseError, kiểm requested/served model, calls, token totals, document provenance và over_budget.
- Model provenance: models.py:11–57; preflight trong bakeoff.py:140–148 kiểm family và model khác labeler; _checked_trials tại :572–638 kiểm từng trial/trace; :689–692 buộc một served model và một fingerprint cho toàn bộ run.
- Review lock/fingerprint: bakeoff.py:209–221 yêu cầu manifest lock đã commit; :551–589 đối chiếu lock, timestamps, decisions SHA và code SHA trước khi chấm.
- Client isolation: pair_builder.py:44–52 yêu cầu đủ cặp dedicated base URL/API key; partial hoặc inherited NineRouterClient trả None để gate chuyển sang LLM_UNAVAILABLE. Không thấy endpoint/key trong artifact.
- Decision là recommendation-only; không có thay đổi tự bật AI2_CONTRACT_GRAPH_PAIRS_ENABLED.

## Scope và gate còn lại

- Tôi không gọi provider và không dùng artifact Claude cũ. Archive tmp/p5-superseded-empty-response-20261009 và tmp/p5-superseded-gemini-before-cx-20261009 được xem là superseded.
- Tester độc lập hiện tại ghi dataset verify ok, full eval 223 passed và targeted Ruff All checks passed trong tester-P5-final.md; các kết quả này khớp snapshot cx/gpt-6-sol. Reviewer không gọi provider.
- Cần tạo/cập nhật verification-P5.json và review-decision.json theo snapshot hiện tại rồi mới đóng cook gate. Giữ cờ runtime tắt cho tới quyết định của người dùng.

**Reviewer recommendation:** PASS_WITH_RISK cho code và tính toàn vẹn artifact; HUMAN_DECISION cho chất lượng/enablement.
