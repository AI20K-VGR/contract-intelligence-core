---
id: 261010-2022-contract-graph-quality-recovery
title: "AI2 contract graph quality recovery"
description: "Hoàn tất sửa kỹ thuật candidate/classifier; theo quyết định người dùng, bỏ yêu cầu bằng chứng đánh giá P4/P5, không tuyên bố product quality PASS, giữ runtime OFF."
status: completed
priority: P1
effort: "3–5 ngày kỹ thuật, cộng thời gian thu thập/duyệt dữ liệu; phụ thuộc yield và budget"
mode: hard
tdd: true
deep: true
branch: feature/ai2-contract-graph
created: 2026-10-10
author: user:dungskbg2004@gmail.com
decisions:
  - "2026-10-11: User waives empirical P4/P5 evaluation evidence and held-out runs; complete technical scope only, report product quality NOT_EVALUATED, keep runtime OFF."
phases:
  - phases/phase-1-evidence-and-pair-telemetry.md
  - phases/phase-2-direction-aware-quality-gates.md
  - phases/phase-3-rubric-and-reviewed-development-corpus.md
  - phases/phase-4-bounded-development-experiments.md
  - phases/phase-4u-bounded-candidates-and-abstention.md
  - phases/phase-5-fresh-heldout-and-product-verdict.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Plan: Khôi phục chất lượng phân loại cặp contract graph

## Tổng quan

P5 lịch sử có `recall_any` C1 `5/101`, B1 `0/101`, C2 `4/101`, B2 `4/101`; cả bốn lặp false DUPLICATE trên pair `61760c76dddc1a35`. Verdict lịch sử là `KEEP_OFF_FALSE_DUPLICATE`.

**Scope amendment được người dùng duyệt ngày 2026-10-11:** không cần bằng chứng đánh giá P4/P5 và không chạy held-out. Hoàn thành plan ở mức kỹ thuật: code, offline regression, provenance và review. Giữ các ngưỡng recall/precision trong tài liệu làm product-readiness gates cho tương lai; không coi chúng đã đạt. Báo `product_quality=NOT_EVALUATED`, giữ runtime OFF.

## Quyết định đã khóa và phạm vi approval

- Giữ classifier `cx/gpt-5.5`; ghi requested model và served model từng request, kiểm model family và khác tên model gán nhãn. Không đổi model để né gate (`predictor.py:107`, `models.py`, research/local-probes.md).
- Giữ precision `MIN_N=60`, Wilson lower `>=0.85`; bổ sung **recall end-to-end theo từng nhãn với Wilson lower >=0.85**, tính cả candidate miss. Với GENERAL_SPECIFIC/REFERENCE, correctness dùng nhãn **và hướng A/B hợp lệ** (`review_policy.py:21`, `score.py:29`, `bakeoff.py:1184`).
- False DUPLICATE `observed=0` và `unreviewed=0` trên tập quyết định; thiếu/unknown không phải zero (`score.py:88`, `predictor.py:81`).
- Hai trial chính thức cho mỗi biến thể được preregister; mỗi trial <=550s và <=500000 tokens. Không tăng budget/scope/ngưỡng ngầm.
- Consent, citation grounding, output nhãn đóng, provenance, `NEEDS_REVIEW` và cờ runtime OFF được giữ (`pair_builder.py:55`, `pair_classifier.py:172`, `pair_builder.py:121`). Không tự bật cờ sau verdict.
- Approval HG-1/HG-2 cũ chỉ bao phủ dataset/version cũ. **HG-QR1** duyệt rubric + dev mới; **HG-QR2** duyệt gold/selection/scope held-out mới trước classification. Chuẩn bị packet cụ thể rồi hỏi người dùng; không tự ghi human-approved.
- HOLD phạm vi: eval + dữ liệu/rubric + candidate/classifier. Không đổi BE/UI, public wire schema, storage hoặc migration; không fine-tune, dependency mới, hoặc production deployment.

## Bằng chứng và độ chắc chắn

| Claim | Loại/evidence | Việc cần làm |
|---|---|---|
| P3 current reviewed run chỉ 4 positives; false DUPLICATE unreviewed1 vẫn PASS | [OBSERVED] calibration artifact `current_reviewed_run`; `predictor.py:81` | P2 yêu cầu đủ bốn nhãn và chặn unreviewed; P3 corpus mới |
| Legacy scorer tính đúng nhãn nhưng sai hướng thành label hit; missing hướng có thể bằng nhau | [OBSERVED] probe scorer thật, research/local-probes.md; `score.py:120` | P2 metric mới giữ legacy không đổi, thiếu A/B fail closed |
| Gate decide có nhánh enable chỉ dựa precision, chưa thực thi recall floor | [OBSERVED, hẹp] injected `_checked_trials` probe; `bakeoff.py:1184` | P2 test full valid preflight/report, không suy probe bypass provenance là E2E |
| Candidate C74/101, B77/101 và decomposition27/56/13/1/4 của C1 | [DERIVED, có điều kiện] historical diagnostic joined P5 | P1 replay pool/doc/config/exclusion/resolver/builder; không kết luận current runtime từ candidate SHA đơn lẻ |
| Current `predictor.candidate_set` tái tạo C174 candidates/74 positives, B165/77 trên đúng14 held-out docs, missing_docs0 | [OBSERVED] main offline probe, research/local-probes.md | Ceiling current74/101 và77/101 đã quan sát trên những docs này; frozen P5 full-context replay vẫn riêng |
| Current candidate SHA LF-normalized khớp frozen7691ba… | [OBSERVED] `dataset.file_digest`, research report | P1 dùng digest chuẩn dự án; raw-byte CRLF khác không phải logic drift |
| Override có thể khiến GS bị dự đoán DUPLICATE | [ASSUMED] `pair_classifier.py:73`; `LABELING.vi.md:18` | P3 adjudicate rubric; P4 ablation dev độc lập, không few-shot held-out |

Nguồn phương pháp và giới hạn: [research](research/research-261010-2022-contract-graph-quality-recovery-report.md); probe main đã chạy: [local-probes](research/local-probes.md). Paper củng cố thiết kế grouped split/annotation/eval; không chứng minh effect size cho pipeline này.

## Chuẩn chung và ràng buộc

Đã đọc `docs/code-standards.md` và `docs/system-architecture.md`. Dùng Python hiện hữu, pytest, provenance/citation immutable, deterministic scorer; LLM suggestions không tự thành gold. `docs/standards/` thiếu không có nghĩa standards trên thiếu; bổ sung tiêu chí chất lượng tại plan này, không tạo/sửa harness core. Architecture doc còn mô tả classifier Claude; model thật của lượt này theo locked user constraint và trace cx/gpt-5.5.

- Worktree `C:/Users/dungs/OneDrive/Documents/VSF-ai2-contract-graph`; branch `feature/ai2-contract-graph`; planning HEAD `681ff4ca300b1d03c131453d5290f8bba1d9bc8f`. HARNESS_BIN_ROOT trỏ main `C:/Users/dungs/OneDrive/Documents/VSF`, HARNESS_DATA_ROOT trỏ worktree `.harness`; active plan phải chỉ định absolute path.
- Code có dirty changes ngoài nhiệm vụ, gồm candidate/builder/resolver/models/IDP và BE. Cook ghi `git status --short`, diff SHA và owner trước P1; đối chiếu lúc bắt đầu mỗi phase. Không reset/stash/revert edits của người khác. Những file ngoài inventory chỉ đọc; phát hiện dependency cần sửa thì báo scope delta để review.
- Raw corpus, clauses, spans gốc, response, endpoint key và review sheets đặt trong `.harness/state/contract-graph-quality-recovery/` sau `git check-ignore`; repo chỉ lưu metadata/safe aggregate. Callback telemetry opt-in eval, không đưa event từng cặp vào product coverage/wire.
- Phases tuyến tính vì chung source; cùng maintainer sở hữu classifier/builder, eval và corpus xuyên phase. Chỉ một phase được ghi tại một thời điểm; không tách module hoặc giấu file chỉ để giảm inventory. Inventory khai báo mọi CLI/schema-dispatch caller và test bị ảnh hưởng.
- Không chạy test implementation hoặc model calls trong planning. Lệnh và fixtures dưới đây là nghĩa vụ cook; probe main không thay test evidence của thay đổi.

## Data flow và caller inventory

1. Nguồn hợp lệ → raw cache local → segmented immutable docs → near-duplicate/template clusters → split theo cluster → **recall frame cố định trước candidate generation** → independent annotations/adjudication → user review → manifest/review lock. Candidate union tạo **precision/safety frame bổ sung**; union-only positive không vào recall numerator/denominator/quota. Row giao hai frame có2 roles nhưng pair dedup. Reuse `corpus.near_duplicate_clusters` (`corpus.py:241`), `manifest.assign_splits` (`manifest.py:89`), `review.import_sheet` (`review.py:184`); schema dispatch mới tại `predictor._read_reviewed_gold` (`predictor.py:501`) không đọc HG1/HG2 legacy cho dataset mới.
2. Dev reviewed docs → `predictor.predict_doc` (`predictor.py:193`) dựng record/index + luồng1 exclusions → `candidate_set` (`predictor.py:169`) → `build_pair_relations` (`pair_builder.py:72`) → consent gate → `classify_pairs` (`pair_classifier.py:213`) → span/direction/number validators → citation verifier → accepted relations. Collector eval opt-in ghi pair events local; product shape không đổi.
3. Approved gold + predictions + per-pair events → `score_relations` (`score.py:29`) → legacy + exact-direction metrics → predictor dev quality gate (`predictor.py:81`) → locked dev report/protocol → `bakeoff.preconditions` (`bakeoff.py:449`) → two held-out trials → `_checked_trials` (`bakeoff.py:986`) → `decide` (`bakeoff.py:1184`) → product verdict + safe report. Candidate miss là FN ở mẫu số gold, không lọc gold theo predictions.

Main đã gọi needs_planner với fact-subjects; `code.callers` unavailable vì thiếu `codemap.yaml`. Inventory dưới là **bounded grep fallback**, không giả AST-complete. Re-grep paths/symbols trước implementation; xác minh alias/additional callers lúc có snapshot.

| Symbol | Callers runtime/eval đã thấy |
|---|---|
| `classify_pairs` (`pair_classifier.py:213`) | `pair_builder.py:102` |
| `build_pair_relations` (`pair_builder.py:72`) | `predictor.py:207`, `ai-service/app/pipeline/idp.py:384` |
| `generate_pair_candidates` (`pair_candidates.py:143`) | `pair_builder.py:83`, `predictor.py:190`, `candidate_eval.py:69` |
| `score_relations` (`score.py:29`) | `predictor.py:288`, `:289`, `:309`; `bakeoff.py:779`, `:786` |
| `_classifier_gate` (`predictor.py:81`) | `predictor.py:313` |
| `preconditions` (`bakeoff.py:449`) | `bakeoff.py:826`, `:1245`; `run.py:193`, `:201`, `:297` |
| `decide` (`bakeoff.py:1184`) | `run.py:210` |
| `predict_split` (`predictor.py:456`) | `run.py:303` |
| `import_sheet` (`review.py:184`) | `bakeoff.py:185`, `:279` |

Telemetry collector phải per-evaluation/per-doc, tạo trong `predict_doc` (`predictor.py:193`); classifier stats tạo mỗi `classify_pairs` (`pair_classifier.py:214`), không dùng global list/cache/client-shared state. Collector không nhận clauses/spans/raw output, chỉ IDs/enums/length/truncation flags và counters.

## Features

- **F1 explain-recall-loss**: biết mỗi cặp mất tại candidate, cap, chưa gửi, model, validator hay citation; unknown evidence ghi đúng unknown.
- **F2 enforce-quality-gates**: quyết định thực thi recall/precision/hướng và false duplicate, fail closed khi thiếu dữ liệu.
- **F3 reviewed-rubric-and-dev**: corpus dev đủ bốn nhãn và negatives, có review/adjudication/provenance độc lập.
- **F4 bounded-quality-improvement**: chọn thay đổi candidate/prompt bằng số dev, trong model/budget đã chốt.
- **F5 independent-product-verdict**: đánh giá fresh held-out, giữ OFF nếu quality chưa đạt.

## Phases

| # | Theme | Phụ thuộc | Cỡ | Trạng thái |
|---|---|---|---|---|
| P1 | [Frozen replay + pair telemetry](phases/phase-1-evidence-and-pair-telemetry.md) | Plan được duyệt; ownership audit | M | PASS |
| P2 | [Metric đúng hướng + gate fail closed](phases/phase-2-direction-aware-quality-gates.md) | P1 | M | PASS |
| P3 | [Rubric + dev đã duyệt](phases/phase-3-rubric-and-reviewed-development-corpus.md) | P2; HG-QR1 | L, review-dependent | PASS kỹ thuật; quality support không dùng làm gate hoàn thành |
| P4T | [Sửa candidate/classifier và offline regression](phases/phase-4-bounded-development-experiments.md) | P3 | M | PASS kỹ thuật; quality NOT_EVALUATED |
| P4U | [Giới hạn candidate work và phân loại abstain](phases/phase-4u-bounded-candidates-and-abstention.md) | P4T | S | PASS kỹ thuật; quality NOT_EVALUATED |
| P5 | [Held-out/product verdict](phases/phase-5-fresh-heldout-and-product-verdict.md) | P4U | WAIVED theo quyết định người dùng |

`P1 → P2 → P3 → P4T → P4U` là phạm vi kỹ thuật đã sửa đổi; P4/P4T giữ kết quả snapshot lịch sử, P4U khép các lỗi review sau đó. P5 được giữ trong lịch sử nhưng waived, không đọc held-out. Quality gates trong phần metric vẫn là điều kiện product readiness, không phải điều kiện đóng plan kỹ thuật theo amendment này.

### File ownership và dependency handoff

| Owner duy nhất cho module | Files chính | Phase ghi tuần tự |
|---|---|---|
| Maintainer runtime pairs | `pair_classifier.py`, `pair_builder.py`, tests tương ứng | P1 rồi P4 |
| Maintainer candidate | `pair_candidates.py`, `candidate_eval.py`, tests tương ứng | P4T/P4U |
| Maintainer eval | `predictor.py`, `score.py`, `bakeoff.py`, `recall_diagnostic.py`, `run.py`, tests tương ứng | P1/P2/P4/P5 theo inventory |
| Maintainer corpus/review | `corpus.py`, `manifest.py`, `review.py`, `LABELING.vi.md`, tests tương ứng | P3 rồi P5 |

Shared files xuất hiện ở graph của phase kế tiếp như handoff nối tiếp; không hai owner/phase ghi đồng thời. Không sửa dirty luồng1 builder/resolver hoặc schema chỉ vì replay thiếu artifact.

## Contract metric và dữ liệu nghiệm thu

| Gate/metric | Mẫu số | Điều kiện |
|---|---|---|
| Candidate dev coverage | Toàn reviewed positives từng nhãn, candidate sau cap | >=0.95 mỗi nhãn; không label nào n0 |
| Exact recall | Reviewed positives của **locked independent recall frame**, kể cả candidate miss/reject | n>=60, Wilson95 lower>=0.85 từng nhãn/từng trial; directed labels phải đúng A/B; union-only positive không cộng vào |
| Conservative precision | Toàn prediction của nhãn trên evaluated candidate frame, unreviewed tính sai | n>=60, Wilson95 lower>=0.85 từng nhãn/từng trial; exact-direction precision bổ sung cho directed labels |
| Direction accuracy | Prediction đúng nhãn directed có gold hướng hợp lệ | Report riêng; thiếu gold/pred A/B không hit và blocks readiness |
| False DUPLICATE | Tất cả prediction DUPLICATE | observed0, unreviewed0; counters typed int không bool/float/string |
| Provenance/budget | Mỗi request/doc/trial | requested/served recognized, differs labeler, source/code/config/consent hashes khớp; <=550s/500000 tokens |

Giữ historical `recall_any`, `precision_conservative`, `recall_observed`, `direction_accuracy` đọc nguyên trạng dưới schema cũ. Schema evaluation mới thêm metric exact label+direction và quality gate; không reinterpret output cũ. Legacy report không có đủ metric mới được xem là historical evidence, không thể authorize new product verdict. Validate counters/rates/Wilson từ raw approved gold + predictions, không tin report fields đơn lẻ.

`MIN_N60` không đảm bảo đạt floor: production `wilson_lower(57,60)=0.8629926537490016`, `wilson_lower(56,60)=0.8407442010623228` (probe main). Precision prediction count và recall positive count độc lập. Giữ existing cluster precision lower gate; report cluster recall/exact-direction intervals và số independent clusters, không dùng total655 thay từng denominator.

Dev thiết kế: >=60 approved positives/label trong recall frame, >=120 representative reviewed negatives, >=5 distinct clusters và >=3 clusters/label; mỗi cluster không quá40% positives của nhãn. Đây là **proposed corpus design** cần HG-QR1 xác nhận. Held-out recall frame mới minimum60 positives/label, target100 positives/label +>=200 negatives từ>=10 fresh clusters/>=5 clusters/label, không cluster>25% nhãn. Candidate union B/C được review đầy đủ riêng cho precision/safety; không thay recall frame sau generation. Manifest khóa frame_version, membership hashes/counts và per-row roles. Yield hoặc budget không đủ → blocker, không đổi quota ngầm.

P4 tối đa4 live tuning runs (baseline+1 prompt ablation, each2 repeats) + oracle20pairs1run; reserve2 same-winner confirmation runs ở P5 sau mọi orchestration/scorer/predictor code đã hoàn tất và freeze. Tổngdev vẫn6live+oracle1. P4 PASS chỉ mở chuẩn bị P5; final2 confirmation trên đúng corpus/rubric/winner không tuning phải PASS trước held-out calls. `code_fingerprints` (`predictor.py:66`) khóa cả predictor/bakeoff; mọi code edit sau final confirmation làm lock stale, không dùng P4 report để vượt drift.

New immutable versioned manifest/report locks có predecessor SHA và audit supersession, không overwrite old locks. P3 khóa gold review-only trước report tồn tại; report lock được tạo sau verified measurements. P2 thêm dedicated CLI report-path plumbing (`run._review_dev_lock`, `run.py:224`; `bakeoff.preconditions`, `bakeoff.py:449`), không phụ thuộc `DEV_REPORT_PATH` legacy. P5 final manifest `.v2.json` tham chiếu stable corpus/review/frame hashes và2 confirmed report digests; không có circular manifest/report self-hash. Final code/data/config không đổi đến hết held-out.

## Test matrix và môi trường cook

Từ worktree root dùng `$env:PYTHONPATH='ai-service;.'`; Python `.\ai-service\.venv\Scripts\python.exe`. Không dùng Python hệ thống cho app imports. Mỗi phase: tests-before (failure có nguyên nhân hợp lệ), implement, tests-after, regression liên quan, verification+review evidence; green bằng bỏ test/xfail không hợp lệ. Fixture ngắn synthetic, không chép text held-out.

| Layer | Kiểm tra |
|---|---|
| Unit | Pair event taxonomy/accounting; A/B exact-direction; Wilson57/60 vs56/60; zero/missing/nonfinite/malformed; false dup observed/unreviewed; cluster split/review hashes |
| Integration offline | Builder→predictor→score→dev gate→preflight→two-trial report→decide bằng mock provider có trace/model thật về shape; full valid fixtures, không inject `_checked_trials` để claim E2E |
| Runtime regression | Flag off byte parity, consent denied zero calls, deadlines/retries, citation invalid, prompt injection, model family mismatch, relations remain NEEDS_REVIEW |
| Live measurement | P4 dev và P5 fresh held-out sau human locks; locked model/code/rubric/manifest, tokens/time đầy đủ; failures không retry để chọn trial đẹp |

Lệnh offline phase ghi trong phase files. Final focused regression: `.\ai-service\.venv\Scripts\python.exe -m pytest -q evals/contract_graph/tests ai-service/tests/test_contract_graph_pair_classifier.py ai-service/tests/test_contract_graph_pair_builder.py ai-service/tests/test_contract_graph_pair_candidates.py ai-service/tests/test_contract_graph_pairs_flag_regression.py ai-service/tests/test_contract_graph_pairs_consent.py -m 'not live' --basetemp .harness/state/pytest-quality-final`.

## Backwards compatibility và rollback

Không đổi public request/result schema, persistence/migrations, default flags, consent hoặc review state. Telemetry opt-in default None và local-only; test output/wire parity trước-sau. Evaluation schema mới version riêng; readers đọc legacy để audit nhưng strict gate đòi schema/locks mới. Manifest/reports mới có tên riêng, không overwrite HG1/HG2/history; có hash-bound migration receipt nếu copy normalized metadata.

Mỗi phase commit hẹp sau ownership audit; chỉ revert commit của nhiệm vụ khi đã xác định dependency, giữ dirty edits khác. P1 rollback telemetry opt-in; P2 rollback code không làm historical OFF thành ON; P3 invalidate corpus lock/version rồi lưu audit; P4 quay về last frozen dev winner; P5 giữ trial artifacts immutable và đánh dấu obsolete nếu protocol/source đổi, chỉ rerun theo protocol mới trên held-out chưa tune. Cờ runtime vẫn OFF trong mọi rollback.

## Acceptance toàn plan

- [x] P1–P4U technical changes có regression và verification PASS; lưu rõ test command, scope và giới hạn.
- [x] P4T/P4U classifier/reference/abstention và candidate-cap code đã kiểm tra bằng test offline; không claim recall/precision đã cải thiện trên hợp đồng thực.
- [x] P5 empirical evaluation/held-out được waive theo quyết định người dùng ngày 2026-10-11; không truy cập held-out.
- [x] Báo `product_quality=NOT_EVALUATED`; recall/precision/direction/false-duplicate product gates chưa được xác nhận.
- [x] Runtime remains OFF; không deployment.
- [x] Final review không có unresolved critical/high findings; artifact verdict nêu technical completion và quality status riêng.

## Risks và mitigation

| Risk | Likelihood × impact | Mitigation |
|---|---|---|
| Tuning trên held-out đã mở | High × High | Fresh clusters, old set historical-only, protocol lock; freeze trước đọc predictions |
| Rubric/gold không nhất quán | High × High | Blind annotations subset, adjudication, human packet; don't relabel historical gold to model |
| Không đủ REFERENCE/independent clusters hoặc prediction count | High × High | Thu thập/yield audit P3/P5, readiness fail closed; truthful blocker không tăng quota bằng nhãn giả |
| Candidate mở rộng vượt budget | High × High | Bounded dev grids, oracle nhỏ diagnostic-only, two trials budget predeclared |
| Correlated samples / positive-enriched frame làm estimate lạc quan | High × High | Grouped split/cap cluster, existing cluster gate, report sampling frame/π; không claim production prevalence |
| Dirty changes ảnh hưởng replay/gates | Medium × High | LF-normalized complete dependency hashes; audit diff owner mỗi phase; freeze code+config before trial |
| Telemetry leak/shared state hoặc gate defaults pass | Medium × High | IDs/enums only opt-in per-doc; exact types/missing fail closed and privacy/parity tests |

## Câu hỏi còn mở

1. Nguồn mới có đủ bốn nhãn và independent clusters trong budget không? P3/P5 đo yield trước lock.
2. Có thể phục hồi toàn frozen P5 context không? P1 đưa inventory và missing hash cụ thể; không dùng current source giả replay.
3. Independent reviewer và thời gian review được cung cấp thế nào? Chuẩn bị blind packet ở HG-QR1/HG-QR2 để người dùng chọn người/duyệt thực; AI draft vẫn advisory.
4. Thiết kế held-out/quota cụ thể có vừa550s/500000 tokens không? Freeze sau sizing dev và human scope; không giảm floor để vừa.
