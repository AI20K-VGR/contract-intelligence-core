# Nghiên cứu phương pháp đánh giá (eval) cho AI2-A: metrics, golden set, thống kê, benchmark live-LLM, CI

Ngày: 2026-09-29 | Plan: `260929-2323-ai2-a-measure-baseline` (features: `golden-set-scorer`, `live-llm-benchmark`, `ai2-ci`) | Mode: breadth

## 0. Cách đọc báo cáo này (giới hạn bằng chứng)

- Ngân sách ~8 tool call, nên phần lớn nguồn là **kết quả WebSearch (snippet), chưa fetch đọc toàn văn**. Theo `hs:research` đó là *giả thuyết có anchor URL*, không phải probe. Claim nào không có URL hoặc chỉ dựa kiến thức nền được gắn `[PRIOR]`; số học do mình tự tính gắn `[TÍNH]` (kiểm được bằng 1 dòng Python, xem Open questions).
- Không chạy thử gì trên repo/API thật. Mọi con số về giá, model snapshot, rate limit của OpenAI là `[PRIOR]`/`[ASSUMED]` cho tới khi có 1 run thật (Phase 3).
- Nguồn vendor-blog (tenki, futureagi, kinde, dev.to) credibility thấp; chỉ dùng để xác nhận pattern, không dùng làm bằng chứng số liệu.

## 1. Metrics: định nghĩa & chấm điểm

### 1.1 Các framework có sẵn định nghĩa gì (và vì sao không dùng nguyên xi)

| Framework | Định nghĩa liên quan | Cần LLM/NLI? | Dùng cho AI2? |
|---|---|---|---|
| ALCE (Gao et al., EMNLP 2023) | 3 trục: fluency, correctness, citation quality; citation recall/precision tính bằng NLI model kiểm "đoạn trích dẫn có entail câu không" | Có (NLI) `[PRIOR]` chi tiết NLI; trục 3 chiều xác nhận ở snippet | Lấy **khái niệm** citation precision/recall; thay NLI bằng so khớp `node_id`/span tất định vì AI2 có ID + bbox |
| LongCite (2024) | Citation mức câu/span trong long-context QA | Có (judge) | Tham khảo cho granularity span (hợp đồng 50+ trang) |
| RAGAS | Faithfulness, answer relevance (generation); context precision/recall (retrieval) | Chủ yếu LLM-judge | Chỉ dùng làm advisory. Có biến thể ID-based cho context precision/recall `[PRIOR]` (không cần LLM) |
| ARES (Stanford, NAACL 2024) | context relevance, answer faithfulness, answer relevance; judge fine-tune + **prediction-powered inference (PPI)** cho confidence interval | Có (judge) | Ý tưởng PPI hữu ích *nếu sau này* dùng LLM judge; hiện chưa cần |
| TruLens, HELM, OpenAI evals | Groundedness / RAG triad; scenario-metric; eval registry + model-graded | Hỗn hợp | `[PRIOR]` — không tra trong đợt này; không có phát hiện nào đổi khuyến nghị |

Nguồn:
- ALCE: https://arxiv.org/abs/2305.14627 · https://aclanthology.org/2023.emnlp-main.398/ · https://github.com/princeton-nlp/ALCE
- LongCite: https://arxiv.org/pdf/2409.02897
- RAGAS: https://docs.ragas.io/en/stable/concepts/metrics/available_metrics/ · https://docs.ragas.io/en/v0.1.21/concepts/metrics/ · https://langfuse.com/guides/cookbook/evaluation_of_rag_with_ragas
- ARES: https://arxiv.org/abs/2311.09476 · https://aclanthology.org/2024.naacl-long.20/ · https://github.com/stanford-futuredata/ARES

Kết luận nhận xét: cả 3 framework đo "câu trả lời có được nguồn ủng hộ không" bằng **model** (NLI/LLM) vì họ không có ID bằng chứng chuẩn. AI2 có `node_id+page+bbox` do hệ thống tự phát, nên phần lớn chấm được bằng **so khớp tập hợp tất định**. Đây là lợi thế cấu trúc, phải khai thác: gate chặn = tất định; LLM judge = advisory.

### 1.2 Định nghĩa đề xuất cho AI2 (tất định trừ khi ghi khác)

Đơn vị chấm: **unit**, không phải "question". Một answer có m citation và f giá trị → m + f unit. Denominator báo cáo luôn là số unit *và* số question.

**(a) Citation correctness, 2 tầng**
1. *Integrity* (không cần gold, hoàn toàn tất định, nên là gate chặn "100%"): mỗi citation phải (i) `node_id` tồn tại trong snapshot; (ii) `page` == page của node đó; (iii) `bbox` == (hoặc nằm trong dung sai) bbox của node đó. Vi phạm = citation giả (fabricated citation).
2. *Support* (cần gold evidence set G cho mỗi câu hỏi): 
   - citation precision = |cited ∩ G| / |cited| (có citation thừa/sai node thì giảm);
   - citation recall = |cited ∩ G| / |G| (bỏ sót bằng chứng bắt buộc);
   - node-level là chính (so `node_id`); span-level (bbox IoU ≥ τ, hoặc bbox gold nằm trong bbox cited) là phụ. Chọn τ ở Phase 2 và đóng băng vào scorer version. `[ASSUMED]` τ=0.5 là điểm khởi đầu, chưa có nguồn.
   - Với answer NEEDS_REVIEW/INSUFFICIENT_EVIDENCE: định nghĩa rõ có bắt buộc citation không (ví dụ NOT_COMPARABLE phải cite cả 2 phía) — đây là quyết định spec, không phải thống kê.

**(b) Fabrication / hallucination (giá trị bịa)** — 3 mức, chỉ 2 mức đầu vào gate "0":
1. *Ungrounded*: giá trị (số, ngày, tiền, tên bên) trong answer không xuất hiện trong text của các node được cite, sau normalization tất định (bỏ dấu tách nghìn, "1.000.000 đồng"/"một triệu đồng", định dạng ngày dd/mm/yyyy vs "ngày … tháng … năm …").
2. *Unsupported-in-doc*: không xuất hiện ở bất kỳ node nào của tài liệu.
3. *Wrong-but-present*: có trong tài liệu nhưng sai clause/sai thực thể → đây là **accuracy** (so gold), không phải fabrication.
- Giới hạn: giá trị suy ra (tổng, cộng ngày) sẽ bị báo ungrounded oan. Cần whitelist "derivation" khai báo tường minh trong output có cấu trúc; không cho LLM prose tự do mang số ngoài payload. Vì L2 chỉ có **1 draft call**, hãy chấm **payload có cấu trúc** (values, citations, state) và thêm 1 check regex: mọi số trong prose phải ∈ payload.

**(c) State-match / abstention** (5 state ANSWERED/NEEDS_REVIEW/INSUFFICIENT_EVIDENCE/NOT_COMPARABLE/BLOCKED)
- State exact-match accuracy + confusion matrix 5×5.
- Abstention (gộp INSUFFICIENT_EVIDENCE, NOT_COMPARABLE, BLOCKED làm "không trả lời"): abstention precision, abstention recall, **over-refusal rate** (câu answerable bị từ chối), **false-answer rate** (câu unanswerable mà vẫn ANSWERED — nặng nhất, nên là metric chặn cùng fabrication).
- Golden set phải có tỷ lệ unanswerable đáng kể (`[ASSUMED]` ≥ 20–25%); nếu không, abstention recall không đo được. Ý tưởng unanswerable questions lấy từ SQuAD 2.0 `[PRIOR]`, không tra URL.

**(d) Phần nào cần LLM judge:** chỉ (i) paraphrase prose tự do có tương đương gold không; (ii) faithfulness của diễn giải. Mọi thứ khác ở trên tất định. Bằng chứng thực hành: judge-based gate từng trôi gần ngưỡng trong 8 tháng, deterministic assertion đặt trong đường chặn, judge để advisory là thiết kế sống sót (https://dev.to/ethanwritesai/we-gated-ci-on-six-open-source-llm-eval-frameworks-only-two-survived-the-merge-queue-5elf; vendor blog, credibility thấp nhưng khớp https://www.promptfoo.dev/docs/integrations/ci-cd/ và https://futureagi.com/blog/ci-cd-llm-eval-github-actions-2026/).

## 2. Xây golden set cho hợp đồng

### 2.1 Bằng chứng về quy trình annotate pháp lý
- CUAD: 510 hợp đồng, 13.000+ nhãn, 41 loại clause; annotator (sinh viên luật) được huấn luyện 70–100 giờ, theo 100+ trang guideline; mỗi annotation được **3 annotator khác verify** (https://arxiv.org/abs/2103.06268 · https://github.com/The-Atticus-Project/cuad · https://www.worldcc.com/portals/iaccm/Resources/10045_0_CUADpaper.pdf). Con số 70–100h/100 trang là quy mô nghiên cứu; team AI2 không cần bằng đó, nhưng nó cho thấy **guideline viết ra + verify độc lập** là bắt buộc, không phải tuỳ chọn.
- ACORD (expert-annotated contract dataset) https://arxiv.org/pdf/2501.06582 và Better Call CLAUSE (benchmark discrepancy hợp đồng — sát bài toán body-vs-annex conflict) https://arxiv.org/pdf/2511.00340: cả hai cho thấy cộng đồng dùng expert annotation + mutation/synthetic discrepancy có kiểm soát. Chưa đọc toàn văn.
- Cohen's kappa: giải thích/định nghĩa https://surge-ai.medium.com/inter-annotator-agreement-an-introduction-to-cohens-kappa-statistic-dcc15ffa5ac4 · http://www.collocations.de/UCS/UCS-R-html/iaa.kappa.html. Thang Landis–Koch 1977 (0.61–0.80 substantial, >0.80 almost perfect) `[PRIOR]`.

### 2.2 Quy trình đề xuất
1. **Guideline ngắn (≤ 5 trang) trước khi annotate**: định nghĩa đơn vị bằng chứng (node nào tính là "đủ"), cách xử lý số bằng chữ, annex ghi đè body, khi nào là NOT_COMPARABLE vs INSUFFICIENT_EVIDENCE. Ví dụ biên đưa vào guideline sau mỗi vòng bất đồng.
2. **Double annotation + adjudication**: 2 người độc lập, không nhìn output của hệ thống; bất đồng do người thứ 3 (hoặc lead) phân xử, ghi lý do vào guideline. Báo cáo kappa **theo từng loại nhãn** (state, evidence set, giá trị), không gộp.
3. **Mục tiêu kappa**: `[ASSUMED]` κ ≥ 0.80 cho state và giá trị; ≥ 0.70 cho evidence set (nhiều đáp án hợp lệ). Với ~95 case, CI của κ rộng (± ~0.1), nên báo cả khoảng, không chỉ điểm.
4. **95 case `UNVERIFIED` hiện có — cảnh báo circularity**: nếu fixture được sinh/soạn từ output của chính hệ thống, review một người liếc qua sẽ xác nhận lại lỗi của hệ thống (anchoring bias). Phải review **từ trang nguồn/bbox, ẩn output hệ thống**, ghi `reviewer`, `verified_at`, `basis`. Case chưa qua double annotation giữ nhãn `UNVERIFIED` và **không tính vào mẫu số gate**. `[ASSUMED]` — suy luận, không có nguồn.
5. **Sinh synthetic từ spec có cấu trúc, không sinh văn bản rồi gán nhãn sau**: sinh facts/clauses từ template/spec → render thành snapshot (node, page, bbox) → gold **có sẵn by construction**; conflict body-vs-annex chèn bằng mutation có kiểm soát (đổi số, đổi ngày, annex ghi đè, tham chiếu sai điều khoản). Cách này tránh lỗi nhãn và cho phép sinh 50+ trang rẻ. `[ASSUMED]` (kỹ thuật chuẩn, nhưng chưa tra nguồn cụ thể cho miền này).
6. **Bẫy synthetic** `[ASSUMED]`, đều đáng check:
   - *Distribution shift*: văn bản sạch, không nhiễu OCR, bố cục đều; hợp đồng thật có bảng, con dấu, chữ ký, chữ nghiêng, lỗi dấu tiếng Việt. Cần ít nhất một nhóm case qua **OCR thật hoặc mô phỏng nhiễu** (mất dấu, nhầm 0/O, ngắt dòng giữa số tiền).
   - *Leakage*: cùng LLM (gpt-4o-mini) vừa sinh vừa bị đo → văn phong quen thuộc, điểm thổi phồng. Sinh bằng template/model khác, hoặc để LLM chỉ diễn đạt lại phần văn xuôi còn số liệu/ID lấy từ spec.
   - *Đa dạng giả*: 10 hợp đồng cùng template = 1 hợp đồng. Đa dạng hoá loại hợp đồng, cấu trúc điều khoản, cách viết số/ngày tiếng Việt.
   - *Leakage dev/test*: tách split **theo hợp đồng** (không theo câu hỏi), vì câu hỏi cùng hợp đồng tương quan. Giữ 1 tập `held-out` không dùng để tinh chỉnh prompt/luật.
7. **Versioning/freeze**: manifest có sha256 từng file + `golden_version` (semver) + changelog; đổi nhãn = PR có reviewer; scorer ghi `golden_version` + `scorer_version` vào mọi kết quả; đổi ngưỡng/definition cũng qua PR. Bản real anonymized bổ sung sau = major/minor bump, giữ kết quả synthetic riêng để so sánh (không trộn mẫu số).

## 3. Thống kê: ">= 95%" thực sự nghĩa là gì

### 3.1 Công cụ
- Nên báo **Wilson** (hoặc Clopper–Pearson khi cần bảo thủ / khi 0 lỗi); tránh Wald (kém ở n nhỏ và gần 100%). Clopper–Pearson "exact" nhưng bảo thủ, coverage vượt danh nghĩa; Wilson gần danh nghĩa và ngắn hơn (https://www.afit.edu/STAT/statcoe_files/12_Binomial%20proportion%20intervals%20DRAFT%20-%20PA%20copy(1).pdf · https://www.mwsug.org/proceedings/2008/pharma/MWSUG-2008-P08.pdf · https://arxiv.org/pdf/2109.02516).
- **Rule of three**: quan sát 0 lỗi trong n lần độc lập → cận trên 95% của tỷ lệ lỗi ≈ 3/n; chính xác là 1 − 0.05^(1/n) (https://en.wikipedia.org/wiki/Rule_of_three_(statistics) · https://dev.to/alex_spinov/zero-failures-isnt-zero-risk-the-rule-of-three-for-evals-4hcd · https://www.statology.org/a-concise-guide-to-the-statistical-rule-of-three/).

### 3.2 Bảng số `[TÍNH]` (95%, Clopper–Pearson một phía cho hàng 0 lỗi; Wilson hai phía cho hàng 48/50)

| Quan sát | n | Cận dưới của tỷ lệ đúng thật |
|---|---|---|
| 0 lỗi | 30 | ~90.5% |
| 0 lỗi | 50 | ~94.2% |
| 0 lỗi | 59 | 95.0% (n tối thiểu để 0 lỗi "chứng minh" ≥95%) |
| 0 lỗi | 100 | ~97.0% |
| 0 lỗi | 300 | ~99.0% |
| 48/50 = 96% | 50 | Wilson hai phía ≈ [86.5%, 98.9%] |
| 50/50 = 100% | 50 | Wilson hai phía cận dưới ≈ 92.9% |

Để cận dưới ≥ 90% (95% tin cậy): cần n ≥ 29 nếu 0 lỗi, n ≥ 46 nếu cho phép 1 lỗi `[TÍNH]`.

### 3.3 Hệ quả cho ngưỡng của team (thẳng thắn)
1. **"0 fabricated" và "100% citation đúng" không thể chứng minh bằng 30–50 câu**. Chỉ nói được "0/n quan sát, cận trên lỗi ≈ 3/n". Với n=50 câu: "thật ra có thể vẫn lỗi tới ~6%". Giữ chúng làm **tripwire chặn** thì hợp lý, nhưng báo cáo phải ghi rõ denominator + cận, không tuyên bố "đã đạt 100%".
2. **Denominator theo unit, không theo question**: 40 câu × ~2–3 citation ≈ 100 citation unit → 0 lỗi cho cận dưới ~97%. Nhưng unit cùng câu hỏi/cùng hợp đồng tương quan (cluster), nên n hiệu dụng < số unit. Dùng **cluster bootstrap theo hợp đồng** để lấy CI khi có ~10 hợp đồng; CI này sẽ rộng hơn Wilson ngây thơ. `[PRIOR]` (design effect chuẩn của cluster sampling).
3. **Ngưỡng ≥95% trên n≈40 là lật bằng 1 câu**: 2 lỗi/40 = 95% qua, 3/40 = 92.5% rớt. Điểm gate nhạy với 1 item → dễ flaky, dễ bị "sửa ngưỡng". Khuyến nghị: gate = *điểm ≥ ngưỡng* **và** *không có item nào từng pass mà nay fail* (per-item regression) cho metric chặn; luôn in danh sách item lỗi, không chỉ %.
4. Muốn tuyên bố "≥95% với độ tin cậy" cần ≥ ~59 unit không lỗi, hoặc ~100–300 unit nếu chấp nhận vài lỗi. Kế hoạch: mở rộng golden lên ≥ 100 unit cho từng metric chặn trước khi gọi nó là "đạt".
5. So sánh trước/sau (baseline A → B/C): dùng kiểm định ghép cặp theo item (McNemar hoặc liệt kê flip) thay vì so hai % — power tốt hơn nhiều ở n nhỏ `[PRIOR]`.

### 3.4 Run-to-run variance của LLM
- temperature 0 vẫn không tất định: OpenAI cookbook nói `seed` cho kết quả "mostly deterministic", `system_fingerprint` đổi khi backend đổi; cộng đồng/blog xác nhận vẫn thấy biến thiên dù seed+fingerprint giống nhau (https://cookbook.openai.com/examples/reproducible_outputs_with_the_seed_parameter · https://community.openai.com/t/lack-of-determinisim-even-with-temp-0-and-fixed-seed/777533 · https://learn.microsoft.com/en-us/azure/ai-foundry/openai/how-to/reproducible-output?view=foundry-classic · https://www.zansara.dev/posts/2026-03-24-temp-0-llm/).
- Snippet tìm được nói `seed` là Beta và `system_fingerprint` bị đánh dấu deprecated trong spec (nguồn: kết quả tìm kiếm tổng hợp, chưa tự kiểm spec) → **đừng dựa vào fingerprint để phát hiện đổi backend**; ghi field `model` của response (trả về snapshot cụ thể) và phiên bản prompt/hash thay thế. `[ASSUMED]` cần kiểm khi làm Phase 3.
- Số lần lặp `[ASSUMED]` (không có nguồn định lượng; suy luận): **baseline k=5, run định kỳ k=3, smoke k=1**. Lặp không tăng n câu hỏi; nó chỉ giảm nhiễu của xác suất pass từng câu. Đừng nhân n lên k khi tính CI (giả độc lập). Báo `mean`, `min` và `pass^k` (câu chỉ tính đạt nếu đạt cả k lần — khái niệm từ tau-bench `[PRIOR]`). Metric chặn (fabrication, citation) dùng quy tắc **any-fail-in-k = fail**.
- Phần lớn nhiễu có thể loại bằng thiết kế: LLM chỉ ở normalization + 1 draft call, nên đo riêng "quyết định state/citation là tất định trước LLM" vs "phần LLM".

## 4. Thiết kế benchmark live-LLM

Bằng chứng: chủ yếu `[PRIOR]` + OpenAI cookbook ở trên; chưa tra tài liệu rate-limit/pricing. Coi mục này là checklist thiết kế, xác minh bằng run thật ở Phase 3.

- **Pin model**: dùng snapshot dated (dạng `gpt-4o-mini-YYYY-MM-DD`) thay vì alias `gpt-4o-mini`; log `model` trả về trong response. `[PRIOR]` Kiểm snapshot còn được phục vụ vào 2026-09 chưa (nguy cơ deprecation) — Open question #1.
- **Latency**: đo end-to-end query (thứ team gate: p95 < 20s) *và* tách LLM-call vs phần còn lại. Báo p50/p95/p99/max + n. **p95 với n=40 chính là ~mẫu lớn thứ 2**, cực nhiễu; cần ≥ ~100 mẫu (lặp k lần × câu hỏi) hoặc báo CI bootstrap cho p95. `[PRIOR]` thống kê phân vị.
- **Warm vs cold**: chạy 1–3 request warm-up bỏ ra ngoài mẫu (kết nối, cache import, JIT), báo riêng cold-start. Gate p95 nên định nghĩa rõ là warm hay gồm cold.
- **Token/cost**: lấy từ `usage.prompt_tokens` / `completion_tokens` (và cached tokens nếu có) của từng response; tính tiền bằng bảng giá **ghi trong file config có ngày hiệu lực**, không hard-code; báo cost/query, cost/run, cost/1k query. Giá `[PRIOR]` (gpt-4o-mini rẻ, cỡ vài chục cent/1M token) → **kiểm giá hiện hành trước khi ghi vào baseline**.
- **Rate limit & retry**: xử lý 429 bằng exponential backoff có jitter; **ghi retries và thời gian chờ riêng** (đừng để backoff làm p95 sai lệch mà không ai biết); giới hạn concurrency cố định và ghi vào metadata run.
- **Cost cap**: (1) đếm token/tiền tích luỹ trong runner, abort với exit code riêng khi vượt `MAX_USD`/`MAX_CALLS`; (2) giới hạn ngân sách ở phía project/key OpenAI làm lớp thứ hai `[PRIOR]`; (3) chạy dry-run in ước tính trước khi bắn.
- **Reproducibility metadata mỗi run**: git SHA, `golden_version`, `scorer_version`, model snapshot, hash prompt, `seed` (nếu dùng), k, concurrency, timestamp, giá áp dụng. Lưu **kết quả từng item** (JSONL), không chỉ tổng hợp — để làm paired comparison sau này.
- **Dữ liệu**: chỉ synthetic/ẩn danh (đã chốt) → thêm check tự động chặn file không có cờ `synthetic|anonymized` trong manifest trước khi gọi API.

## 5. Pattern CI cho LLM eval

Nguồn (đều practitioner/vendor, mức tin cậy thấp–trung; khớp nhau): https://www.promptfoo.dev/docs/integrations/ci-cd/ · https://github.com/promptfoo/promptfoo-action · https://dev.to/ethanwritesai/we-gated-ci-on-six-open-source-llm-eval-frameworks-only-two-survived-the-merge-queue-5elf · https://tenki.cloud/blog/github-actions-llm-evaluation-pipeline · https://www.kinde.com/learn/ai-for-software-engineering/ai-devops/ci-cd-for-evals-running-prompt-and-agent-regression-tests-in-github-actions/ · https://futureagi.com/blog/ci-cd-llm-eval-github-actions-2026/

Pattern hội tụ: **PR = rẻ, tất định, chặn**; **nightly/manual = live, tốn tiền, báo cáo + cảnh báo**. Một nguồn nêu ví dụ 2.000-mẫu LLM-judge mỗi PR ≈ $9/PR và 22 phút → bị chuyển sang nightly (số của blog, không kiểm chứng).

Khuyến nghị cụ thể cho `ai2-ci`:
1. **Workflow PR** (`pull_request`, không secret): ruff/lint, type-check, pytest offline, **scorer chế độ no-LLM** trên golden frozen. Cần chốt "no-LLM" nghĩa là gì (Open question #2): (a) tắt LLM → chỉ test đường tất định; (b) replay "cassette" phản hồi LLM đã ghi → test cả phần LLM đông cứng. Đề xuất làm (a) bắt buộc, (b) tuỳ chọn sau; (b) cho phép gate fabrication/citation trên output LLM *đã ghi* mà không tốn tiền.
2. **Workflow live** (`schedule` + `workflow_dispatch`): chạy k lần, có cost cap, secret `OPENAI_API_KEY` chỉ ở GitHub Environment có required reviewer; không bao giờ để secret vào job PR từ fork, và tránh `pull_request_target` chạy code PR `[PRIOR]` — docs: https://docs.github.com/en/actions/security-for-github-actions/security-guides/using-secrets-in-github-actions (chưa fetch). Pin action bằng commit SHA; `concurrency` group để không chạy chồng; che log nội dung hợp đồng.
3. **Lưu kết quả/trend**: artifact JSONL từng run (retention mặc định GitHub có hạn `[PRIOR]`) + commit bản tóm tắt vào nhánh/thư mục `evals/results` riêng (hoặc gh-pages) để vẽ trend; file nằm ngoài `plans/reports/` nếu là markdown phải tuân CI invariant của harness (kiểm khi làm Phase 4).
4. **Ngưỡng regression**: PR gate = (i) 0 fabricated, 100% citation integrity trên tập tất định; (ii) metric khác ≥ ngưỡng; (iii) không item nào pass→fail. Live run = so với baseline bằng paired diff; cảnh báo (không chặn) khi tụt vượt biên nhiễu đo được từ k lần lặp; cập nhật baseline chỉ qua PR có review.
5. **Judge (nếu thêm)** chỉ ở kênh advisory, hiệu chuẩn vào tập người-gán-nhãn (ý tưởng PPI của ARES), không đặt trong đường chặn.

## 6. Ma trận đánh đổi (các lựa chọn chính)

| Lựa chọn | Độ tin cậy gate | Chi phí | Độ phức tạp | Rủi ro |
|---|---|---|---|---|
| Gate tất định (ID/bbox/normalized-value) | Cao, tái lập 100% | ~0 | Thấp–vừa | Miss lỗi ngữ nghĩa (wrong-but-present) — bù bằng gold accuracy |
| Gate bằng LLM-judge (RAGAS/ARES style) | Trung, trôi gần ngưỡng | $/PR + chậm | Vừa | Flaky, judge cũng hallucinate |
| Hybrid: tất định chặn + judge advisory | Cao | Thấp | Vừa | Cần duy trì 2 kênh |
| Golden 100% synthetic-from-spec | Nhãn chuẩn, rẻ | Thấp | Vừa | Distribution shift |
| Golden real-anonymized đầy đủ | Sát thực tế | Cao (người) | Cao | Chậm; PII |

## 7. Kết luận xếp hạng (RANKED)

1. **(Ưu tiên 1) Định nghĩa gate bằng scorer tất định 2 tầng** (citation integrity + support vs gold; fabrication ungrounded/unsupported-in-doc; state confusion matrix + false-answer rate). Judge chỉ advisory. Lý do: cả 3 framework chuẩn đo bằng model vì thiếu ID; AI2 có ID → tất định được, tái lập được, chạy PR miễn phí. Rủi ro thấp, fit cao.
2. **(Ưu tiên 2) Sửa cách nói về ngưỡng**: giữ chặn "0 fabricated / 100% citation" như tripwire nhưng luôn báo `x/n` + Wilson/CP + cận trên 3/n; thêm gate per-item no-regression; mở rộng golden tới ≥ 59 (tốt hơn ≥ 100) unit không lỗi trước khi tuyên bố "đạt". Lý do: n=30–50 không chứng minh nổi 95%, và ngưỡng ≥95% flaky vì lật bằng 1 câu.
3. **(Ưu tiên 3) Golden set: sinh từ spec có cấu trúc + double annotation & adjudication cho 95 case UNVERIFIED (review mù output hệ thống), tách split theo hợp đồng, đóng băng bằng hash + semver.** κ mục tiêu ≥ 0.8 (state/giá trị), báo CI của κ. Thêm nhóm nhiễu OCR/tiếng Việt để giảm distribution shift; tránh cùng LLM sinh & bị đo.
4. **(Ưu tiên 4) Live benchmark**: pin snapshot dated + log `model` trả về, k=5 baseline / k=3 định kỳ, any-fail-in-k cho metric chặn, p95 dựa ≥ ~100 mẫu + bootstrap CI, warm-up tách riêng, cost cap 2 lớp, lưu JSONL từng item.
5. **(Ưu tiên 5) CI 2 workflow**: PR offline tất định (không secret); live theo lịch/tay trong GitHub Environment có reviewer, budget guard, trend lưu ngoài repo chính hoặc nhánh kết quả.

Không cần `hs:bakeoff` cho mục này; các lựa chọn xếp hạng theo lập luận thống kê/thiết kế, không phải so sánh đo lường được. Ngoại lệ: **k lặp bao nhiêu** và **p95 thực tế** nên do chính Phase 3 đo (probe), không dùng số `[ASSUMED]` ở trên.

## 8. Open questions

1. Snapshot `gpt-4o-mini-<date>` nào còn được phục vụ/không bị deprecate đến hết vòng đời plan A→C? Giá hiện hành? (cần 1 lệnh gọi thật + trang pricing/deprecations.)
2. "Chế độ không LLM" trong CI = tắt LLM (đường fallback) hay replay cassette? Đường fallback hiện có của L2/processing cho ra output đủ để chấm citation/fabrication không?
3. Citation gold: node-level đủ, hay bắt buộc bbox/span-level? Chọn τ (IoU) và dung sai bbox — quyết định spec.
4. State nào bắt buộc có citation (NOT_COMPARABLE, INSUFFICIENT_EVIDENCE, BLOCKED)? Ảnh hưởng mẫu số citation.
5. 95 case `UNVERIFIED` sinh từ đâu (có từ output hệ thống không)? Quyết định mức độ nghi ngờ circularity và cách review.
6. Ai là annotator thứ 2/3 (có kiến thức pháp lý tiếng Việt không)? Kappa vô nghĩa nếu cùng một người hoặc cùng bias.
7. Cách viết số/ngày tiếng Việt trong hợp đồng thật (số bằng chữ, "ngày … tháng … năm …") — danh sách normalization tất định cần chốt trước khi định nghĩa "ungrounded".
8. Hợp đồng 50+ trang: latency p95 < 20s áp dụng cho mọi câu hỏi hay câu hỏi trên tài liệu ngắn? Có tách ngưỡng theo cỡ tài liệu không?
9. Chưa tra: TruLens, HELM, OpenAI evals (chỉ `[PRIOR]`); tài liệu chính thức về rate limit/pricing OpenAI; GitHub docs về secrets/fork; tau-bench `pass^k`. Chưa kiểm số học ở §3.2 bằng code (khuyến nghị 1 dòng `scipy.stats.beta`/`proportion_confint` khi cook Phase 2).
10. Nơi lưu trend: artifact, nhánh kết quả, hay dịch vụ ngoài — phụ thuộc chính sách repo (CI invariant về markdown/`plans/reports/`).
