# Research: khôi phục chất lượng contract graph sau P5

**Mode:** breadth. **Ngày:** 2026-10-10. **Nguồn:** 5 nguồn sơ cấp độc lập và mã/artifact nội bộ. **Ngôn ngữ:** `output_config.py --resolved` trả `language=vi`, `code_style=3`.

## Kết quả và phạm vi

Ưu tiên phục hồi quy trình đo và dữ liệu duyệt trước hiệu chỉnh model. P5 hiện giữ `KEEP_OFF_FALSE_DUPLICATE`; chưa có bằng chứng một thay đổi prompt/candidate sẽ đạt floor. Chỉ nghiên cứu offline metadata, code, artifact; không đọc thêm clause held-out, không gửi dữ liệu/model request, không sửa mã. Giữ `cx/gpt-5.5`, `MIN_N=60`, Wilson lower `>=0.85`, budget mỗi trial `550s/500000 tokens`.

Câu hỏi: lỗi nào đã có bằng chứng, và chuỗi sửa nào phân biệt được lỗi candidate, classifier, validator, rubric và scoring mà không hiệu chỉnh trên held-out?

## Bằng chứng đã xác nhận

Các đường dẫn nội bộ dưới đây tính từ worktree `C:/Users/dungs/OneDrive/Documents/VSF-ai2-contract-graph`.

| Finding | Bằng chứng | Hàm ý |
|---|---|---|
| [OBSERVED] P5 C1/B1/C2/B2 recall_any lần lượt `5/101`, `0/101`, `4/101`, `4/101`; Wilson95 tương ứng `[0.0213,0.1107]`, `[0,0.0366]`, `[0.0155,0.0974]`, `[0.0155,0.0974]` | `evals/contract_graph/reports/l2-p6-bakeoff.json`, `trials` | Chất lượng label thấp trên mẫu đã duyệt; chưa kết luận chất lượng toàn bộ quần thể production |
| [OBSERVED] Mỗi trial có `false_duplicate.observed=1`, `unreviewed=0`; đều là pair `61760c76dddc1a35`, gold `GENERAL_SPECIFIC`, pred `DUPLICATE` | Cùng artifact, join `gold` và `trials[].predictions` theo pair ID | Một lỗi có tính lặp lại, không phải bốn cặp độc lập; đủ veto hiện hành |
| [OBSERVED] P5 gold `655`: `CONFLICT30`, `DUPLICATE29`, `GENERAL_SPECIFIC34`, `REFERENCE8`, `UNRELATED554`; HG2 `approved_by_label={UNRELATED:474}` | Cùng artifact, `gold`, `manifest.hg2` | 474 dòng thêm chưa tăng mẫu dương tính của bốn nhãn |
| [OBSERVED] P3 current reviewed gold chỉ `4`: C1/D1/GS2; GS đúng `0/2`, Wilson95 `[0,0.6576]`; REFERENCE không có mẫu | `evals/contract_graph/reports/l2-p6-classifier-calibration.json:577`, `current_reviewed_run` | PASS hiện hành chỉ smoke gate; không chứng minh đủ bốn nhãn |
| [OBSERVED] P3 `false_duplicate={observed:0,unreviewed:1}`, dù gate PASS | Cùng calibration artifact `:624`; required_labels chỉ CONFLICT/DUPLICATE `:650` | Có một duplicate chưa có review; không được diễn giải “đã xác nhận không false duplicate” |
| [OBSERVED] `recall_any` chỉ exact label, không hướng | `evals/contract_graph/pairs/bakeoff.py:778`; `score.py:120` kiểm direction riêng | C1 đúng nhãn+hướng còn `4/101` Wilson95 `[0.0155,0.0974]`; C2/B2 còn `3/101` `[0.0102,0.0837]` |
| [OBSERVED từ code] Gate quyết định kiểm `passed/denominator`, denominator là số prediction, tức precision_conservative | `evals/contract_graph/pairs/score.py:104`, `bakeoff.py:1190`, `bakeoff.py:1203` | Manifest có recall_floor đã duyệt, nhưng `decide` chưa thực thi floor theo gold-positive denominator; cần gate recall bổ sung |
| [OBSERVED] Trial requested `cx/gpt-5.5`, served `gpt-5.5`, `over_budget=false`, budget `550/500000` | P5 `trials` | Chưa có lý do đổi model hoặc nới budget |

`false_duplicate.unreviewed=1` thuộc P3 calibration; P5 final là `unreviewed=0`. Hai artifact/phạm vi khác nhau, phải ghi riêng.

## Giới hạn của diagnostic lịch sử

[OBSERVED] `l2-p6-recall-diagnostic.json:2` ghi coverage B `77/101`, C `74/101`, E `101/101`. Wilson95 tính lại offline: B `[0.6707,0.8348]`, C `[0.6390,0.8093]`, E `[0.9634,1]`. Đây là coverage trên diagnostic lịch sử; E chưa chạy trong final bakeoff.

[OBSERVED] SHA `pair_candidates.py` trong diagnostic provenance `:34` và final P5 `:4708` giống nhau: `7691ba5691e8d2e69fde9ba6968ca7801321ca2130a3276f4d3476bb23100e85`. Current code theo đúng `dataset.file_digest` LF-normalization cũng có SHA này. Raw-byte SHA `24657b7707ad6371ccb4620256385121fecb9e04e284ee25977e867520667420` khác chỉ do 337 CRLF; không phải bằng chứng candidate logic đã đổi (`evals/contract_graph/dataset.py:188`). Diagnostic classifier/predictor/bakeoff SHA khác P5; diagnostic gold181 còn final655. Builder/index/config context vẫn cần kiểm riêng trước replay.

[DERIVED, có điều kiện] Ghép candidate presence của diagnostic với predictions P5 theo 101 positive pair ID cho bảng sau. Điều kiện: candidate inventory lịch sử tái hiện đúng runtime/input context P5. Cùng candidate code SHA chưa chứng minh điều kiện này; phải xác minh pool, doc, config, sources, top_k, exclusion, predictor và manifest trước dùng làm root cause chính thức.

| Trial | Candidate miss | Có candidate, không accepted prediction | Sai label | Sai direction | Đúng label+direction |
|---|---:|---:|---:|---:|---:|
| C1 | 27 | 56 | 13 | 1 | 4 |
| B1 | 24 | 66 | 11 | 0 | 0 |
| C2 | 27 | 62 | 8 | 1 | 3 |
| B2 | 24 | 63 | 10 | 1 | 3 |

Không gán các cột “không accepted” thành classifier UNRELATED. `recall_diagnostic.py` có `evidence_scope=aggregate_rejection`; aggregate rejection không xác định nguyên nhân từng pair. `recall_diagnostic.py:180` và `:258` cho thấy inventory được dựng lại, không phải luôn là inventory persisted lúc trial chạy. Chưa biết bao nhiêu pair mất do span, policy hoặc UNRELATED ở final P5.

## Rubric: xác nhận nội dung, chưa xác nhận quan hệ nhân quả

[OBSERVED từ code] `evals/contract_graph/pairs/LABELING.vi.md:18` cho GENERAL_SPECIFIC bao gồm chi tiết hóa cùng nghĩa vụ; quy tắc ngoại lệ ưu tiên GS. Classifier `pair_classifier.py:74` có CALIBRATION OVERRIDE, ưu tiên DUPLICATE cho concise restatement bỏ itemized list, và override fixed price/market adjustment thành CONFLICT. Các tiêu chuẩn này có vùng giao cần phân xử rõ.

[ASSUMED] Override là nguyên nhân trực tiếp của false duplicate lặp lại. Chưa có ablation trên dev tương đương độc lập nên chưa được kết luận. [ASSUMED] GPT suggestions/duyệt approve đã tạo bias gold. Toàn bộ human consent được giữ là hợp lệ; chưa đo blind second-review nên chưa khẳng định gold sai.

Nghiên cứu relation classification ghi nhận khác biệt annotation ảnh hưởng cross-dataset performance; nghiên cứu guideline khuyến nghị ví dụ dương/âm và nhiều vòng independent agreement. Áp dụng vào hợp đồng là đề xuất phương pháp, chưa có benchmark chứng minh model này sẽ cải thiện. [RE survey](https://aclanthology.org/2022.acl-srw.7/), [Guideline refinement](https://aclanthology.org/L12-1441/).

## Phương án xếp hạng

| Hạng/phương án | Chất lượng kỳ vọng | Độ phức tạp/bảo trì | Chi phí | Adoption risk và architectural fit |
|---|---|---|---|---|
| **1. Trace offline + rubric duyệt + dev mới + sửa gate; sau đó cải thiện candidate có giới hạn** | Đo được từng điểm mất; không hứa đạt .85 trước probe | Vừa; thêm schema provenance và metric, tái dùng predictor/review/scorer | Review tăng; model vẫn trong budget hiện hành | Cao về fit: giữ stdlib/Python, validator và feature off. Phương pháp đo trưởng thành; rủi ro chính thiếu mẫu/cluster, không phải dependency abandonment |
| **2. Candidate exhaustive trên corpus dev nhỏ để đo ceiling** | Xác định trần classifier khi loại candidate miss; không chứng minh production recall | Thấp ở oracle offline, cao nếu triển khai O(n²) production | Có thể tăng token/calls mạnh; không nới550s/500k | Chỉ fallback diagnostic; không chọn làm production trước bakeoff budget. Current E100/101 là coverage lịch sử, không phải final classifier result |
| **3. Đổi model/fine-tune hoặc tiếp tục prompt-only với dev4** | [ASSUMED] có thể tăng một số hit nhưng thiếu căn cứ tổng quát | Cao nếu fine-tune; prompt-only dễ overfit | Thêm training/provider ops hoặc lặp model calls | Không phù hợp ràng buộc cx/gpt-5.5; insufficient approved dev; không ưu tiên |

Không đề xuất dependency mới. Cộng đồng/maturity của scikit-learn chỉ làm bằng chứng grouped splitting; không cần cài package đó. Không khảo sát lịch sử breaking changes SDK vì khuyến nghị giữ client hiện tại. Rủi ro endpoint/model routing phải theo requested/served provenance ở mỗi probe, không dựa vào tên alias.

## Khuyến nghị triển khai theo thứ tự

1. **Khóa evidence trước sửa.** Đọc frozen P5 metadata và reconstructed inventory offline, ghi SHA tất cả code/input/config theo `dataset.file_digest` LF-normalization; phân biệt historical/current code và line endings. Add per-pair taxonomy: prefilter miss, cap miss, sent, raw UNRELATED, valid relation, exact validator reason, wrong label, wrong direction. Không lưu clause/response vào report. Unknown evidence là `unknown`, không suy từ aggregate. Kiểm tổng accounting và pair-ID uniqueness.
2. **Chốt rubric dựa vào dev mới.** Viết decision table cho same subject/action, changed numbers, real exceptions, semantic restatement, added obligations, directed references; examples tự viết và real dev cluster chưa dùng trong heldout. Duyệt con người independent/blind trước nhìn GPT label trên subset; ghi confusion+disagreement/adjudication. Giữ schema/user-review provenance; không sửa historical approved gold để khớp classifier.
3. **Mở rộng dev đủ bốn nhãn.** Đề xuất minimum reviewed positives60 mỗi nhãn + hard negatives, ở nhiều cluster; số cụ thể predeclare trước run, không chọn n sau thấy kết quả. 240 positives là minimum design count, không bảo đảm precision denominator hay đủ cluster. Review tất cả predicted DUPLICATE dùng để quyết định; `unreviewed>0` phải remain unresolved, không coi là zero false duplicate. Hai nhãn C/D đúng `1/1` mỗi nhãn có Wilson95 `[0.2065,1]`, chưa đủ hỗ trợ floor.
4. **Tách gate chất lượng khỏi smoke gate.** Giữ existing precision_conservative `MIN_N60`, Wilson lower>=.85; thêm end-to-end per-label recall denominator toàn reviewed positives, missed candidates tính FN. Cho GS/REFERENCE thêm exact label+direction recall và metric direction riêng. Null/n=0 không PASS. Áp dụng recall_floor manifest đúng nhãn/phạm vi; không thay precision denominator thành positives. Kiểm cluster interval cùng gate existing; freeze trial selection và worst-trial policy trước run.
5. **Probe candidate rồi classifier trên dev.** Oracle exhaustive small dev đo classifier ceiling riêng; candidate ablation coverage+tokens+latency riêng; bounded candidate stratification/quota là giả thuyết phải đo. Candidate coverage cần đủ cao mới có khả năng đạt end-to-end recall; classifier cannot recover absent pairs. Prompt ablation minimal rubric changes, giữ validators grounding/citation/number/direction/injection. Không dùng holdout failures như few-shot.
6. **Heldout mới sau dev freeze.** Split theo doc và near-duplicate/template cluster, không theo pair; exclude các cluster đã exposed/tuned. Lấy mẫu positive đủ nhãn và negative từ candidate-independent frame; human gold independent of classifier. Blind second-review subset, adjudicate trước runtime trial. Predeclare sampling/strata/probabilities, labels, scope, n, two repeats, budget, model/code/prompt hashes. Frame label-enriched phải report rõ; precision trên sample enriched không đại diện production prevalence. Giữ old heldout làm historical failure evidence, không dùng làm chứng minh recovery mới.
7. **Bakeoff có điều kiện.** Chỉ chạy khi dev quality gate PASS thật và human decisions đã khóa. Dùng cx/gpt-5.5; từng trial <=550s/500000 tokens. Report precision+recall+direction-aware, Wilson95 và cluster intervals; zero observed false duplicate là veto. Nếu budget hoặc n thiếu, giữ OFF và báo blocker định lượng; không đổi floor, model hoặc scope ngầm.

Grouped split được docs scikit-learn hỗ trợ; Dwork et al. chỉ ra adaptive holdout reuse có thể overfit; RE survey yêu cầu evaluation rõ và nhiều test set. Ba nguồn độc lập củng cố quyết định fresh evaluation, nhưng quy tắc cluster cụ thể của hợp đồng là [ASSUMED] đến khi duplicate/template audit chạy. [Grouped validation](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data), [Adaptive holdout](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html), [RE survey](https://aclanthology.org/2022.acl-srw.7/).

[DERIVED bằng tính offline] Với Wilson95 two-sided và n60, k57 cho lower `0.8629948352365148`, k56 cho `0.8407464268680284`; cần tối thiểu57/60 để vượt .85 ở cỡ mẫu này. Áp dụng riêng từng denominator, chưa điều chỉnh correlation cluster. Threshold MIN_N60 không có nghĩa “60 mẫu luôn đủ”. Zero observed false duplicate không chứng minh xác suất lỗi thật bằng0. Công thức và ý nghĩa confidence bounds: [NIST](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm).

## Nguồn và độ tin cậy

| Nguồn | Credibility | Vai trò và giới hạn |
|---|---|---|
| [scikit-learn grouped CV, docs maintainer](https://scikit-learn.org/stable/modules/cross_validation.html#cross-validation-iterators-for-grouped-data) | Cao; official docs đọc2026-10-10 | Nhóm phụ thuộc phải tách fold; không xác nhận clustering hợp đồng hiện tại |
| [Bassignana & Plank, ACL2022](https://aclanthology.org/2022.acl-srw.7/) | Cao; nghiên cứu RE sơ cấp | Annotation discrepancies/cross-dataset evaluation; domain scientific khác hợp đồng Việt |
| [Hahn et al., LREC2012](https://aclanthology.org/L12-1441/) | Cao cho phương pháp; nghiên cứu annotation sơ cấp | Guideline refinement, positive/negative lists, independent agreement; không suy accuracy model hiện tại |
| [Dwork et al., NeurIPS2015](https://papers.neurips.cc/paper_files/paper/2015/hash/bad5f33780c42f2588878a9d07405083-Abstract.html) | Cao; nghiên cứu thống kê sơ cấp | Adaptive reuse risk; không đề xuất cài differential privacy trong dự án này |
| [NIST confidence intervals](https://itl.nist.gov/div898/handbook/prc/section2/prc241.htm) | Cao; official statistical reference | Wilson và exact bounds; binomial không tự giải quyết cluster dependence |

Không single-source claim về cải thiện model: mọi cải thiện candidate/prompt là giả thuyết cho dev bakeoff. Ba nguồn trên củng cố workflow evaluation; không có ba nghiên cứu độc lập đo pipeline cụ thể này, nên không phát biểu effect size dự kiến.

## Giới hạn và câu hỏi còn mở

- [ASSUMED] Override gây false duplicate: cần ablation dev độc lập; chưa chạy live.
- [ASSUMED] Candidate inventory lịch sử đúng context P5: cần frozen replay input/config/predictor/builder/index. Current candidate SHA chuẩn hóa LF đã khớp; không suy toàn bộ context khớp từ một file.
- [ASSUMED] Blind review sẽ phát hiện rubric/gold disagreement: chưa đo; không vô hiệu hóa approval đã có.
- [ASSUMED] Near-duplicate/template clusters đã đúng: cần audit và kiểm group-disjoint, không chỉ doc_id-disjoint.
- Có đủ nguồn mới để đạt >=60 positive từng nhãn, đặc biệt REFERENCE, và đủ cluster độc lập trong budget không? Chưa định lượng yield nguồn mới.
- Thời gian/cost review mới chưa ước tính đáng tin; không có benchmark production, fine-tuning study hoặc provider reliability study trong lượt này.
- Không coi báo cáo nghiên cứu là PASS sản phẩm. Bước tiếp: parent hs:plan đưa các phép kiểm trên vào phase acceptance rồi xin review kế hoạch cụ thể.
