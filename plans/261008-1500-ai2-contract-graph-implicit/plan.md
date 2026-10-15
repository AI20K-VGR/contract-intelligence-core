---
id: 261008-1500-ai2-contract-graph-implicit
title: "AI2 contract graph - luong 2 quan he ngam"
description: "Luồng 2 (phân loại cặp): bộ nhãn cặp công khai, ứng viên cấu trúc deterministic, classifier LLM thuộc họ được nhận diện nhãn đóng + span kiểm bằng code, sau cờ riêng tắt mặc định, consent từ policy_flags, bake-off lại trên held-out."
status: completed
priority: P2
effort: "~9 ngày công (P1 2 · P2 1,5 · P3 2 · P4 2,5 · P5 1) + người dùng duyệt nhãn HG-1 (250–380 dòng, ~5–8 giờ, sau P2, trước P5)"
mode: hard
tdd: true
branch: feature/ai2-contract-graph-implicit
tags: [ai2, contract-graph, pair-classifier, llm, consent, feature-flag, postgres, bakeoff]
created: 2026-10-08
author: 
decisions: []
phases:
  - phases/phase-1-pair-label-dataset.md
  - phases/phase-2-structural-candidates.md
  - phases/phase-3-llm-pair-classifier.md
  - phases/phase-4-integration-storage.md
  - phases/phase-5-bakeoff-rerun.md
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Plan: AI2 contract graph - luong 2 quan he ngam

Chế độ: `--hard --deep --tdd`. Mỗi phase có file inventory, test-scenario matrix, dependency map, cặp TDD red→green. Không `--parallel`: 5 phase là chuỗi tuyến tính, các phase sau đều cần model/hàm của phase trước (§Dependency).
Nhãn bằng chứng: **OBSERVED** = đã chạy/đọc trong phiên lập plan (2026-10-08, worktree `contract-intelligence-develop`, HEAD `83f2d75`); `file:line` = đã đọc; `[ASSUMED]` = chưa kiểm; `[PRIOR]` = kiến thức có sẵn.

## Tổng quan

Luồng 1 (plan `261007-1735-ai2-contract-graph-op-first`, completed) đã phủ quan hệ có **câu thao tác** ("Sửa đổi khoản 2 Điều 5 như sau:"). Plan này xây **luồng 2 — phân loại cặp** cho quan hệ **ngầm** giữa các khoản/phụ lục: `GENERAL_SPECIFIC`, liên kết mâu thuẫn (`CONFLICT` → finding `COMPARABLE_DIFFERENCE` + liên kết vô hướng), `DUPLICATE`, `REFERENCE` ngữ nghĩa (dẫn chiếu không dùng số Điều).

Kiến trúc theo hướng **C** của bake-off `contract-edge-261007-run1`: cấu trúc sinh ứng viên (deterministic) → LLM phân loại nhãn đóng → **code** kiểm span + dựng citation. Số đo run1 chỉ là smoke (OBSERVED `plans/261007-1618-ai2-contract-graph/bakeoff-verdict.json`: C 10/11 recall, precision 10/10; verdict `insufficient_trials`; 6/11 cặp gold từ fixture tổng hợp `HD-TONG-HOP`). **Bake-off run1 rất có thể đã phân loại bằng GPT (`gpt-4o-mini`), không phải Claude**: probe gọi `NineRouterClient()` đọc `.env` core (`.harness/state/bakeoff/contract-edge-261007/probe.py:78-89`), `.env` đó trỏ OpenAI `gpt-4o-mini` (OBSERVED tên biến), probe không ghi model ⇒ **kết quả run1 không phải bằng chứng cho Claude**.

Thứ tự: bộ nhãn cặp (P1) → ứng viên cấu trúc + mở rộng gold cho ứng viên trên held-out + xuất phiếu duyệt (P2) → bộ phân loại Claude + grounding (P3) → tích hợp `run_idp` sau cờ riêng + lưu trữ (P4) → bake-off lại + cổng quyết định (P5). Cờ mới mặc định **tắt**; tắt thì output `run_idp` không đổi một byte. Contract BE không đổi. Job thật **rule-only** cho tới khi BE gửi consent (D4).

## Quyết định đã khoá (không re-litigate)

| # | Quyết định | Nguồn |
|---|---|---|
| L2-1 | Loại quan hệ: `GENERAL_SPECIFIC`, liên kết mâu thuẫn (finding `COMPARABLE_DIFFERENCE` + đường nối vô hướng, V3), `DUPLICATE`, `REFERENCE` ngữ nghĩa | user 2026-10-08 (`research/researcher-01-brief-and-evidence.md`) |
| L2-2 | Consent: **chỉ phía AI2** đọc cờ consent trong `policy_flags`; không consent ⇒ chỉ ứng viên cấu trúc, không gọi LLM, coverage ghi `graph_mode` rule-only. Toggle UI/BE để sau | user |
| L2-3 | Bộ nhãn cặp: ≥15 mẫu HĐ SALES/SUPPLY_SERVICE công khai; GPT gán nhãn; người dùng duyệt mẫu; khoá held-out sha256; tái dùng probe bake-off | user |
| L2-4 | Phạm vi: bộ nhãn → ứng viên cấu trúc → classifier LLM thuộc họ được nhận diện + grounding bằng code → tích hợp `run_idp` sau cờ riêng (mặc định tắt) → bake-off lại. Không đổi contract BE, không UI | user |
| K-a | Model gán nhãn ≠ model phân loại (GPT gán, classifier LLM thuộc họ được nhận diện) — V4b | discovery-brief §8 |
| K-b | Không legal winner; mọi cạnh/finding `NEEDS_REVIEW`; PASS (cổng bật) chỉ khi cận dưới Wilson ≥ 0,85 với n ≥ 60 và gold đã duyệt | discovery-brief §8 vòng 3; `ai-service/app/pipeline/contract_graph/review_policy.py:21-22` |
| K-c | Auto-PASS từng cạnh **chỉ** cho câu thao tác chuẩn (luồng 1) ⇒ quan hệ luồng 2 không bao giờ tự PASS | discovery-brief §8 vòng 3 |
| K-d | Không dùng LLM output làm evidence; không đổi contract BE (BE so chuỗi `"AMENDS"` ở `backend/src/contract_intelligence/shared/ai/persistence.py:831-835`, `FindingItem`/`Ai2ComparisonPayload` `extra="forbid"` ở `backend/src/contract_intelligence/shared/ai/schemas.py:253-288`) | user |
| K-e | Storage: Postgres schema `ai2` (DEC-BE-AI2-01 D11), không bảng SQLite (tiền lệ luồng 1 D7) | `docs/ai2/AI2-19-contract-graph-operation-first.vi.md` §6 |
| Q1 | **Consent = `policy_flags.egress_allowed`**; ghi DEC (§DEC cần ghi); job thật rule-only cho tới khi BE bật | user 2026-10-08 (validate) |
| Q2 | **Có** issue "độ phủ hạn chế" `NEEDS_REVIEW` mỗi job chạy rule-only, có test | user 2026-10-08 |
| Q3/Q4 | Người dùng cấp dedicated endpoint/model classifier trong ai-service/.env; không dán key; GPT gán nhãn, classifier thuộc họ được nhận diện và khác model cụ thể labeler; thiếu hoặc unknown ⇒ BLOCKED, không thay model ngầm | user 2026-10-08, bổ sung user 2026-10-09 |
| Q5 | Người dùng duyệt HG-1 trước P5; ước tính cập nhật theo RT-12: 250–380 dòng (trần cứng 380) | user 2026-10-08 + RT-12 |
| Q6 | Chấp nhận verdict `KEEP_OFF_INSUFFICIENT_N` | user 2026-10-08 |
| Q7 | Tên cờ `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` | user 2026-10-08 |
| Q8 | Dữ liệu ngoài repo ở `.harness/state/contract-graph-pairs/` (không track: `.git/info/exclude:12` `/.harness/`), env `AI2_CG_PAIRS_DATA_DIR` trỏ tới đó | user 2026-10-08 |

## Quyết định kỹ thuật của plan (có bằng chứng)

| # | Quyết định | Lý do / bằng chứng |
|---|---|---|
| D1 | Tên luồng trong code là **pairs**: cờ `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, module `contract_graph/pair_*.py`, coverage `contract_graph.pairs` | "implicit" đã có nghĩa khác ở luồng 1: `ai-service/app/pipeline/contract_graph/implicit.py`, `ContractEdge.implicit` (`ai-service/app/contracts/contract_graph.py:51`), `coverage.contract_graph.implicit_edges` (`projection.py:107`), `ai-service/tests/test_contract_graph_implicit.py`. Q7 chốt |
| D2 | Cờ pairs là **cờ con**: chỉ chạy khi `AI2_CONTRACT_GRAPH_ENABLED` bật **và** builder luồng 1 thành công (`graph is not None`, `ai-service/app/pipeline/idp.py:280-299`). Đọc env một lần mỗi lượt `run_idp` | Cần cạnh luồng 1 để loại cặp đã phủ (L2-4). Cờ luồng 1 tắt ⇒ golden `ai-service/fixtures/contract_graph/idp_flag_off_golden.json`; cờ luồng 1 bật + pairs tắt ⇒ golden mới `idp_graph_on_golden.json` capture **trước** khi sửa `idp.py` (P4 bước 1; red-team OBSERVED 67 case ổn định ở seed 0/1/7) |
| D3 | **Model + bảng riêng**, không mở rộng `EdgeOp`: `PairLabel`/`PairRelation`/`PairResult` trong `ai-service/app/contracts/contract_graph.py`; bảng `ai2.contract_pair_relations` (migration `0006`) trên `graph_metadata` | (a) `projection.edge_findings` biến **mọi** `ContractEdge` thành finding `AMENDS` (`projection.py:51-85`) ⇒ nhãn luồng 2 ra BE thành `candidate_amendment` severity `high` (`persistence.py:831-851`). (b) Field `ContractEdge` mang ngữ nghĩa sửa đổi (`contract_graph.py:42-57`). (c) `edges_by_op` lặp qua `EdgeOp` (`projection.py:104`, `builder.py:622`) ⇒ đổi shape coverage luồng 1 ngay cả khi pairs tắt. (d) Nới CHECK `ck_ai2_contract_edges_op` (`0005_ai2_contract_edges.py:48-51`) cần DROP/ADD CONSTRAINT + downgrade xoá dòng luồng 2 khỏi bảng luồng 1 |
| D4 | Consent = `policy_flags.egress_allowed` → `DossierRecord.content_sharing_consent` (mặc định `False`), gán trong `adapt_be_ai2_processing_request` cạnh `ai-service/app/pipeline/ai1_snapshot_adapter.py:170` | Q1 chốt. Cách duy nhất không đổi contract: `policy` `additionalProperties: false` (`docs/contracts/be.ai2.processing.request.v1.schema.json:59`), `ProcessingPolicyFlags` `extra="forbid"` (`ai-service/app/contracts/wire.py:93-104`). Chỉ **thu hẹp** (AND với egress server A8, `ai1_snapshot_adapter.py:45-51`). BE gửi cứng `False` (`backend/src/contract_intelligence/shared/ai/canonical_processing.py:377`) ⇒ rule-only. HTTP (`main.py:248`) + Kafka (`kafka_idp_worker.py:146`) đều qua adapter |
| D5 | Cổng LLM theo thứ tự, điều đầu tiên trượt thành `rule_only_reason`: `NO_CONSENT` → `EGRESS_DENIED` (`runtime.egress_allowed` False) → `LLM_UNAVAILABLE` (không dựng được client phân loại configured, D6) → `MODEL_UNSET` → `BUDGET_EXHAUSTED` → `DEADLINE` (`runtime.remaining() < PAIRS_DEADLINE_RESERVE_S + runtime.max_attempts × runtime.call_timeout_seconds`, RT-07) | Fail-closed; dùng cổng có sẵn (`ProcessingRuntime`, `ai-service/app/pipeline/runtime.py:99-257`). Một lô có thể retry `max_attempts` lần × `call_timeout_seconds` (`runtime.py:180-201`) nên dự trữ phải bao trọn lô |
| D6 | Client phân loại: model `AI2_CONTRACT_GRAPH_PAIRS_MODEL` (không default); phải có **đủ cặp** `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL` + `AI2_CONTRACT_GRAPH_PAIRS_API_KEY` để dựng `NineRouterClient` riêng. Thiếu một biến, hoặc cả hai biến khi `llm` là `NineRouterClient`, thì fail-closed (`None` → `LLM_UNAVAILABLE`); test double vẫn được giữ cho unit test. Mọi lời gọi qua `runtime.complete_json` (`runtime.py:158-243`). Trace client ghi `served_model = resp.model` và model yêu cầu (RT-04). | RT-08: không cho phép kế thừa endpoint/key core vì HTTP core có thể trỏ OpenAI (`main.py:278`), không bảo đảm K-a; Q3: người dùng đặt đủ dedicated classifier endpoint/model vào `ai-service/.env`. |
| D7 | Rule-only: vẫn sinh ứng viên cấu trúc, đếm vào coverage, **và** phát đúng một issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` (`NEEDS_REVIEW`, nêu lý do); không quan hệ | Q2 chốt; L2-2 |
| D8 | Đường ra: `GENERAL_SPECIFIC`/`DUPLICATE`/`REFERENCE` **chỉ** vào bảng `ai2` + coverage. `CONFLICT` → `Candidate(COMPARABLE_DIFFERENCE, UNCLEAR, NEEDS_REVIEW)` với evidence = citation **cả node** (`text_span=None`, RT-10), tối đa `PAIRS_MAX_CONFLICT_FINDINGS = 5`/hồ sơ (dư chỉ đếm), + dòng bảng vô hướng (span LLM chỉ ở bảng) | BE biến context finding không phải `AMENDS` thành `insufficient_evidence` high (`persistence.py:831-852`); BE gán severity `high` cho mọi finding `NEEDS_REVIEW` (`persistence.py:1095`); candidate cấp khoản có tiền lệ (`clause_compare.py:442-456`); K-d: việc chọn đoạn bằng chứng không được là output LLM |
| D9 | Không bao giờ PASS: validator `PairRelation.review_state` chỉ nhận `NEEDS_REVIEW`; candidate CONFLICT cứng `NEEDS_REVIEW`. Cổng P5 import `MIN_N`, `MIN_WILSON_LOWER`, `wilson_lower` (`review_policy.py:21-44`), chỉ sinh artifact, không bật cờ | K-b, K-c |
| D10 | Quan hệ luồng 2 **không** vào `relation_pairs` (`idp.py:274-299`), không sửa fact/candidate cũ | K-d |
| D11 | Điểm tích hợp `run_idp`: khối pairs **sau** `issues.extend(graph_issues)` (`idp.py:361`), **trước** `coverage = {...}` (`idp.py:362`): candidate CONFLICT append cuối `candidates`; issue pairs (FAILED / LIMITED_COVERAGE) append cuối `issues`; cập nhật `graph_coverage_value` (`graph_mode` + `pairs`); `record.pair_relations*` cạnh `idp.py:393-394` | RT-03 (OBSERVED repro): candidate đặt trước `build_contract_context` (`idp.py:329`) sinh thêm `CONTEXT_CONFLICT` khi hai phía cùng file (`contract_context.py:254-278`) ⇒ issue chèn trước `graph_issues` ⇒ dịch `review:{code}:{index}` (`idp.py:556`). Đặt sau `:361` thì `build_contract_context` không thấy candidate mới; review item của candidate đứng sau mọi issue (`idp.py:541-570`) |
| D12 | Chống prompt injection: (1) văn bản khoản vào prompt dạng chuỗi JSON, system prompt nói rõ là dữ liệu; (2) **chỉ đếm** tín hiệu injection (mẫu riêng có `\b`, chạy trên văn bản đã `fold_for_match`, áp cho cả `text` lẫn `context`) — **không bỏ cặp** (RT-05); (3) output đóng kiểm bằng code: `id` ∈ lô, nhãn ∈ tập đóng, span nguyên văn trong `text`, hướng bắt buộc, `review_state` do code gán; (4) không log văn bản/response | RT-05 OBSERVED: `classify_prompt_injection` (`ai-service/app/security/policy.py:43`) gắn cờ 5/5 khoản lành tính ("shall not reveal", "printing services", "anti-dumping duty", "dump truck", "blueprint"). Lớp chặn thật là output đóng |
| D13 | Ngân sách: `PAIRS_TOP_K = 40` (chốt ở P2 trên dev), `PAIRS_PER_CALL = 8`, `PAIRS_MAX_CALLS = 5`, `CLAUSE_CHARS_MAX = 1200`, `CONTEXT_CHARS_MAX = 300`, `PAIRS_DEADLINE_RESERVE_S = 30`, `PAIRS_MAX_CONFLICT_FINDINGS = 5` | Run1 ~390 token/cặp trên khoản ngắn (trung bình 225 ký tự — red-team OBSERVED); khoản dài có thể đẩy 10–16k token/hồ sơ lên vài lần `[ASSUMED]` ⇒ đo thật ở P3/P5. BE gửi `max_llm_calls: 20` (`canonical_processing.py:378-382`), dùng chung |
| D14 | Dữ liệu nhãn **ngoài repo** ở `AI2_CG_PAIRS_DATA_DIR` (mặc định `.harness/state/contract-graph-pairs/`). Repo chỉ commit manifest (URL, sha256, số đếm, model, split, seed, π) + báo cáo tổng hợp; test dùng chuỗi tổng hợp ngắn trong test. P1 kiểm `git check-ignore` thư mục dữ liệu trước khi ghi | `CONTRIBUTING.md:56` cấm commit hợp đồng; `:61-62` dữ liệu eval ngoài repo, đọc qua env; Q8 |
| D15 | Chia theo **cụm văn bản**: chuẩn hoá → gom gần trùng (shingle 5-từ Jaccard ≥ 0,8 hoặc cùng sha chuỗi tiêu đề Điều) → cả cụm một split; cụm sắp theo `min sha256(url)`, 2/3 đầu → held-out. Cụm gần trùng (containment ≥ 0,5) với văn bản spike (`evals/spikes/clause_key/clauses_heldout*.jsonl`) hoặc URL spike/fixture ⇒ ép dev | RT-13: mẫu HĐ bị chép qua nhiều domain (spike có "thuê mặt bằng" trên 4 domain); chống rò rỉ tuning dev → held-out |
| D16 | Kiểm K-a bằng model thực phục vụ: family(model_id) nhận diện anthropic, google, openai hoặc unknown; labeler phải openai, classifier phải thuộc họ được nhận diện và tên model cụ thể phải khác labeler; unknown hoặc trùng ⇒ fail-closed (thoát mã 2). | RT-04: id có tiền tố router không được làm kiểm tiền tố fail-open |
| D17 | Pool gán nhãn theo tầng: S1 cùng Điều (đủ), S2 thân↔phụ lục (trần 200/văn bản), S3 mẫu seed khác Điều (`min(40, …)`/văn bản); **S4** (P2, chỉ held-out) = mọi ứng viên B∪C deterministic ngoài pool. Loại cặp có cạnh luồng 1 | RT-02: proxy red-team S3 chỉ ≈3,3% cặp khác Điều ⇒ ứng viên khác Điều của C hầu như không có gold; S4 sinh **trước** mọi lời gọi bộ phân loại trên held-out, theo code đã đóng băng |
| D18 | HG-1 (pre-register, khoá sha selection trước khi chạy bộ phân loại trên held-out): GPT-positive mỗi nhãn **đủ** nếu ≤ 75, vượt thì mẫu seed 75 (π ghi); GPT-UNRELATED mẫu seed tổng 80, phân tầng S1/S2/S3/S4 (π ghi). Trần 380 dòng. Cổng P5: **precision bảo thủ** (dự đoán trên cặp không có gold duyệt = sai) quyết định; ước lượng có trọng số 1/π chỉ để báo | RT-01: chỉ duyệt mẫu UNRELATED mà loại dự đoán chưa duyệt khỏi mẫu số ⇒ precision/recall lệch lạc quan có hướng; RT-12: khối lượng; `docs/code-standards.md` §Testing (chỉ `approved=true` tính accuracy) |
| D19 | Test eval ở `evals/contract_graph/tests/`, chạy từ repo root | `ai-service/pyproject.toml` `testpaths = ["tests"]`; tiền lệ luồng 1 D14 |

## DEC cần ghi (Q1)

Ghi **sau khi P4 xong, trước khi merge** (main thread / người dùng), qua `python harness/scripts/decision_register.py --append-alloc --title … --rationale … --affects … --supersedes …`:

| Trường | Nội dung |
|---|---|
| title | AI2 luồng 2 đọc `policy_flags.egress_allowed` làm consent chia sẻ nội dung HĐ cho LLM phân loại cặp |
| rationale | Không đổi `be.ai2.processing.request.v1` (`policy` `additionalProperties:false`); cờ chỉ **thu hẹp** (AND với `AI2_PROCESSING_EGRESS_ALLOWED`, A8), không nới; BE đang gửi `False` ⇒ rule-only cho tới khi BE có toggle; mọi quan hệ `NEEDS_REVIEW`, không legal winner |
| affects | `ai-service/app/pipeline/ai1_snapshot_adapter.py`, `ai-service/app/pipeline/contract_graph/pair_builder.py`, `docs/ai2/AI2-20-contract-graph-pairs.vi.md`, ý nghĩa `egress_allowed` ở `docs/contracts/be.ai2.processing.request.v1.schema.json:62` (mô tả "Advisory only" vẫn đúng cho mọi đường khác) |
| supersedes | Không DEC nào; liên quan V5 (discovery-brief §8) và DEC-BE-AI2-01 D6 |
| điều kiện | Bật cờ ở bất kỳ môi trường nào cần DEC này + verdict P5 + quyết định của người |

## Ràng buộc (constraint-scan)

- `harness/data/ownership.yaml`: zone `plans: [plans/]`, `docs: [docs/]`, `state: [.harness/state/]` (không enforce), `standards: [harness/standards/]`. Code ở `ai-service/`, `evals/` ngoài zone harness. Plan ghi trong `plans/` [IN]; doc `docs/ai2/AI2-20-…` [IN]; dữ liệu `.harness/state/contract-graph-pairs/` [IN zone state, không enforce].
- `harness/data/stage-policy.yaml`: pr/merge/ship/deploy cần `verification`, `review-decision`, `plan-approval` ⇒ P5 `post: [verification-P5.json, review-decision.json]`.
- Không đụng core (`harness/`, `.claude/settings.json`); `harness/scripts/wilson.py`, `bakeoff_rank.py`, `decision_register.py` chỉ gọi CLI.
- Schema wire `docs/contracts/ai2.be.processing.result.v1.schema.json` không sửa; `coverage` object mở; `item_key: null`, `scope: string` hợp lệ (red-team OBSERVED); `job_result_to_wire` tự validate (`wire.py:389`).
- Request contract không sửa (`be.ai2.processing.request.v1.schema.json:57-66`) ⇒ D4.
- Dữ liệu: `CONTRIBUTING.md:56-62` ⇒ D14. `.harness/` chỉ bị bỏ qua qua `.git/info/exclude:12` (cục bộ, không commit) ⇒ P1 kiểm `git check-ignore` + test quét file repo không chứa văn bản.
- Code standards: không legal winner (`Candidate.no_legal_winner`, `ai-service/app/contracts/models.py:480-485`); thiếu/mơ hồ → `NEEDS_REVIEW`; evals tách `denominator`/`covered`/`passed` + nguồn ground truth; LLM chỉ advisory.
- Caller (grep — `hs-run plan next --fact-subjects …` exit 2 "SHARED bin root" trong phiên subagent, OBSERVED):
  - `run_idp` — 9: `ai-service/app/api/main.py:292, 1136, 1492, 1699, 1714, 1750`; `ai-service/app/pipeline/ai2_batch.py:115, 179`; `ai-service/app/transport/kafka_idp_worker.py:180`. Chỉ `main.py:292` → `complete_with_snapshot` (`main.py:302`).
  - `adapt_be_ai2_processing_request` — 4: `main.py:138, 248, 1785`; `kafka_idp_worker.py:146`. Đường khác ⇒ consent `False` ⇒ rule-only.
  - `PostgresJobStore.complete_with_snapshot` — 1: `main.py:302`.
  - Test gọi `run_idp(`: 25 file `ai-service/tests/`.
  - Test hard-code head `0005`: `ai-service/tests/test_contract_graph_edge_store.py:112-121` (chạy không cần DB — RT-06), `ai-service/tests/test_contract_graph_postgres_store.py:20-21, 85, 116`.
- `migrate()` chạy ở lần dùng DB đầu tiên của **mỗi process** (`ai-service/app/db/engine.py:39-44`) ⇒ rollback phải dừng mọi process code mới trước khi downgrade (RT-11).
- Postgres test chỉ chạy khi có `AI2_TEST_DATABASE_URL`/Docker; máy lập plan không có ⇒ P4 dùng `AI2_REQUIRE_DOCKER=1`, thiếu là BLOCKED.
- LLM (OBSERVED): không NineRouter ở `localhost:20128`; `.env` core trỏ OpenAI `gpt-4o-mini`; `ai-service/.env` của worktree develop **chưa có** (người dùng sẽ tạo, bị `ai-service/.gitignore:9` loại).

## Data flow

```
BE request ─ adapt_be_ai2_processing_request (ai1_snapshot_adapter.py:76)
   └─ record.content_sharing_consent = request.policy_flags.egress_allowed      P4 (D4)
run_idp (idp.py:47)
 … facts → … → relation_pairs (274) → [cờ luồng 1] build_contract_graph (287)
 … pairer (300) → clause_compare (309) → _downgrade (327) → build_contract_context (329)
 … context_issues (359) → issues += graph_issues (361)
 ├─ [cờ luồng 1 ∧ graph OK ∧ AI2_CONTRACT_GRAPH_PAIRS_ENABLED]                         P4 (D11)
 │   build_pair_relations(record, graph.edges, llm=llm, runtime=runtime)                P3
 │     StructureIndex.build → generate_pair_candidates(excluded=cặp luồng 1, top_k)     P2
 │        SAME_ARTICLE · EXPLICIT_REF (bỏ dẫn chiếu văn bản ngoài) · SAME_KEY · REFERENCE_CUE
 │     gate D5 ── trượt ──► rule_only (+ issue LIMITED_COVERAGE)
 │        └─ đạt ──► classify_pairs: đếm tín hiệu injection → lô 8 → runtime.complete_json
 │              → id/nhãn/span/hướng/guard → citation span (bảng) → PairRelation(NEEDS_REVIEW)
 │   candidates += ≤5 CONFLICT → Candidate COMPARABLE_DIFFERENCE (citation cả node)       P4
 │   issues += PAIRS_FAILED | PAIRS_LIMITED_COVERAGE ; graph_coverage_value.update(graph_mode, pairs)
 ├─ coverage (362) → propose → review items (candidate CONFLICT đứng sau mọi issue)
 └─ record.pair_relations / pair_relations_ran (RT-14)                                      P4
main._execute_wire_job → PostgresJobStore.complete_with_snapshot (jobs.py:537)
   └─ savepoint contract_edges ; savepoint contract_pair_relations                          P4
```

Ngoài pipeline: `evals/contract_graph/pairs/` — P1 tải mẫu → tách → gom cụm gần trùng → split → pool S1–S3 → GPT gán nhãn (cache, `served_model`) → freeze; P2 đo ứng viên trên dev, chốt K, sinh S4 trên held-out (không LLM phân loại) → GPT gán S4 → chọn mẫu HG-1 (π) → khoá selection → xuất phiếu; người dùng duyệt (HG-1); P3 đo dev; P5 nhập + khoá quyết định → 2–3 biến thể × ≥2 trial trên held-out → cổng.

## Features

- **F1 pair-label-dataset** — bộ nhãn cặp từ ≥15 mẫu HĐ mua bán/dịch vụ công khai, gom gần trùng trước khi chia, GPT gán nhãn có span, held-out khoá sha256, dữ liệu ngoài repo.
- **F2 structural-pair-candidates** — ứng viên cặp deterministic có ngữ cảnh kế thừa, loại cặp luồng 1 và dẫn chiếu văn bản ngoài, top-k mỗi hồ sơ; gold mở rộng cho ứng viên trên held-out; phiếu duyệt HG-1 có trọng số.
- **F3 llm-pair-classification** — classifier LLM thuộc họ được nhận diện nhãn đóng, span kiểm bằng code, output đóng chống injection, ngân sách lô/lần gọi/hạn.
- **F4 consent-gated-rule-only** — không consent (hoặc egress/model/ngân sách/hạn không đạt) ⇒ không gọi LLM, coverage ghi rule-only + lý do, issue "độ phủ hạn chế".
- **F5 conflict-as-comparable-difference** — mâu thuẫn thành finding `COMPARABLE_DIFFERENCE` `NEEDS_REVIEW` (≤5/hồ sơ, evidence cả node) + liên kết vô hướng trong bảng.
- **F6 pairs-flag** — sau `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` (tắt mặc định, cần cờ luồng 1); tắt ⇒ output không đổi byte.
- **F7 pair-relation-persistence** — bảng `ai2.contract_pair_relations` (migration 0006, downgrade, runbook dừng process).
- **F8 pairs-bakeoff-gate** — bake-off held-out ≥2 trial, McNemar, precision bảo thủ + có trọng số, chi phí/độ trễ, artifact khuyến nghị.

## Phases

| # | Theme | Phụ thuộc | Cỡ | File chính |
|---|---|---|---|---|
| 1 | Pair label dataset | — | L (2 ngày) | `evals/contract_graph/pairs/*` |
| 2 | Structural candidates + gold mở rộng + phiếu HG-1 | P1 | M (1,5 ngày) | `contract_graph/pair_candidates.py`, `pairs/candidate_eval.py` |
| 3 | LLM pair classifier | P2 | L (2 ngày) | `contract_graph/{pair_classifier,pair_builder}.py`, `app/contracts/contract_graph.py`, `app/llm/client.py` |
| 4 | Integration + storage | P3 | L (2,5 ngày) | `idp.py`, `pair_projection.py`, migration `0006`, `tables.py`, `jobs.py`, `store.py`, `ai1_snapshot_adapter.py`, `tools/pair_relation_store.py` |
| 5 | Bake-off rerun + cổng | P4 + HG-1 | M (1 ngày + chạy live) | `evals/contract_graph/pairs/bakeoff.py`, báo cáo `l2-p5-*` |

### Dependency

```
P1 ──► P2 ──► P3 ──► P4 ──► P5
        │                    ▲
        └── HG-1 (người dùng duyệt phiếu xuất cuối P2) ┘   (P5 bước 0 kiểm + khoá)
```

Tuyến tính. P2 cần dữ liệu P1 (đo dev, sinh S4 held-out). P3 cần kiểu ứng viên (P2). P4 cần model + builder (P3). P5 đo đường đã tích hợp và sửa §số đo doc do P4 tạo. HG-1 là cổng người, chạy song song P3–P4.

### File ownership

Mỗi file thuộc một phase, trừ các cặp nối bằng đường đi trong DAG:
- `evals/contract_graph/pairs/run.py` — P1 tạo; P2, P3, P5 thêm subcommand.
- `evals/contract_graph/pairs/manifest.json` — P1 tạo; P2 thêm khối `extension_s4` + `review_selection`; P5 thêm `heldout_review`.
- `ai-service/app/contracts/contract_graph.py` — chỉ P3.
- `docs/ai2/AI2-20-contract-graph-pairs.vi.md` — P4 tạo, P5 điền §Số đo.
- Golden `idp_flag_off_golden.json` không phase nào sửa; `idp_graph_on_golden.json` P4 tạo ở bước 1, không sửa sau đó.

## Out of scope

- UI, toggle consent BE/FE, đổi `be.ai2.processing.request.v1`/`ai2.be.processing.result.v1`, sửa BE.
- Kafka worker ghi bảng (worker gọi `run_idp`, có quan hệ in-memory khi cờ bật, không ghi bảng).
- AI2-18, chuỗi sửa nhiều lớp, query/L1 dùng graph, BL-006.
- Auto-PASS quan hệ luồng 2; tự bật cờ ở bất kỳ môi trường nào.
- NLI/cross-encoder, embedding làm nguồn ứng viên.
- Sửa `relations.py`, `compare.py`, `clause_compare.py`, `contract_context.py`, luồng 1 (`builder.py`, `projection.py`, `review_policy.py`).
- Người gán mù thứ hai (discovery-brief §8 vòng 3) ⇒ ma trận GPT↔người chỉ là cận trên đồng thuận.

## Acceptance (toàn plan)

- [ ] Mỗi phase red→green TDD; test đầu tiên được chạy và thấy FAIL (hoặc PASS nếu khoá regression) trước khi viết code.
- [ ] Suite ai-service: từ `ai-service/` chạy `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider --basetemp=<thư mục ghi được>` → xanh **trừ đúng 13 lỗi môi trường** (OBSERVED 2026-10-08 trên `83f2d75`: `13 failed, 1290 passed, 44 skipped`):
  - `tests/unit/test_mistral_ocr.py` × 7 (`ModuleNotFoundError: mistralai`).
  - Thiếu `HD-TONG-HOP.sample.pdf` × 5: `tests/test_hd_gold.py::test_hd_tong_hop_gold_two_source_findings`, `tests/test_ingest.py::test_hd_tong_hop_sample_pdf_extracts_and_answers_dieu_9`, `tests/test_structure_reconstruction.py::{test_master_contract_reconstruction_keeps_scopes_and_does_not_promote_inline_annex_reference, test_citation_contains_full_structure_path_and_source_scope, test_pdf_party_declarations_are_not_confused_with_clause_mentions}`.
  - `tests/test_p0_contract_baseline.py::test_p0_artifact_freezes_decisions_and_executable_case_refs`.
  - Mọi lỗi khác tên, hoặc passed < 1290 + số test mới, là regression.
- [ ] Suite harness: từ repo root `uv run --project ai-service --frozen --extra web --extra dev python -m pytest -q -p no:cacheprovider evals/contract_graph/tests` xanh (baseline `77 passed`).
- [ ] Lint: `uv run --frozen --extra dev ruff check <file .py mới/sửa>` (từ `ai-service/`) và `uv run --project ai-service --frozen --extra dev ruff check --config ai-service/pyproject.toml evals/contract_graph/pairs evals/contract_graph/tests` sạch. Không có type-check/CI cho ai-service (`.github/workflows/ai-service.yml:24`).
- [ ] Hai golden xanh sau P4; pairs bật rule-only chỉ khác golden graph-on ở `coverage.contract_graph.{graph_mode,pairs}`, issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` (cuối danh sách) + review item của nó, bộ đếm `n_evidence_issues`, và `review_state` chỉ có thể chuyển sang `NEEDS_REVIEW`.
- [ ] Wire khi pairs bật validate schema; ngoài `index_contribution.coverage` không có `\b(GENERAL_SPECIFIC|DUPLICATE|REFERENCE|CONFLICT)\b`.
- [ ] Không quan hệ luồng 2 nào `review_state != NEEDS_REVIEW`.
- [ ] Migration `0006` up/down (`python -m app.db.migrate downgrade 0005_ai2_contract_edges`)/up chạy thật trên Postgres với `AI2_REQUIRE_DOCKER=1`; thiếu ⇒ BLOCKED, không PASS.
- [ ] Báo cáo `evals/contract_graph/reports/l2-p1-dataset.*`, `l2-p2-candidates.*`, `l2-p3-classifier-dev.*`, `l2-p5-bakeoff.*`, `l2-p5-decision.json`: mỗi tỷ lệ `k/n` + Wilson 95% (method nêu tên) + khoảng theo cụm văn bản + số vòng tune; không văn bản khoản trong repo.
- [ ] `MIN_N=60`, `MIN_WILSON_LOWER=0.85` import từ `review_policy.py`, có test.
- [ ] DEC Q1 đã ghi trước merge.

### Test matrix tổng

| Tầng | Cái gì | Ở đâu |
|---|---|---|
| Unit | tách mẫu HĐ, gom gần trùng, split, pool, gán nhãn (mock) + `served_model` + họ model fail-closed, manifest, scorer bảo thủ + trọng số | `evals/contract_graph/tests/test_cg_pairs_{corpus,pool,labeler,review,manifest,score}.py` (P1) |
| Unit | ngữ cảnh, chủ đề, 4 nguồn, loại văn bản ngoài, loại cặp luồng 1, top-k; S4 + chọn mẫu π | `ai-service/tests/test_contract_graph_pair_candidates.py`, `evals/.../test_cg_pairs_candidate_eval.py` (P2) |
| Unit | prompt/lô, injection chỉ đếm, kiểm output, guard, cổng D5/RT-07, client `served_model` | `ai-service/tests/test_contract_graph_pair_{classifier,builder}.py`, `tests/test_llm_complete_json.py` (P3) |
| Integration | 2 golden; rule-only + issue; LLM mock; consent; projection CONFLICT (trần, cả node); review-id với phụ lục nhúng; wire; bảng + Postgres; head động | `ai-service/tests/test_contract_graph_pairs_*.py`, `test_contract_graph_pair_{projection,store}.py`, `test_contract_graph_edge_store.py` (P4) |
| E2E đo | ứng viên (dev), phân loại (dev), bake-off (held-out) | `evals/contract_graph/pairs/{candidate_eval,predictor,bakeoff}.py` |

## Rollback

- Mỗi phase là **một commit** (hoặc dải có tag `l2-p<N>`); `git revert` theo thứ tự ngược (P5 → P1); chạy lại hai suite sau revert.
- **Rollback mặc định = tắt cờ** `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` (không cần deploy).
- P4 có schema — runbook **bắt buộc** (RT-11; `migrate()` chạy mỗi process ở lần dùng DB đầu, `engine.py:39-44`):
  1. Dừng/scale về 0 **mọi** process chạy code mới: API, Kafka worker, `ai2_batch`, job định kỳ.
  2. Từ `ai-service/` với `AI2_DATABASE_URL`: `python -m app.db.migrate downgrade 0005_ai2_contract_edges` (chỉ drop `ai2.contract_pair_relations`).
  3. Deploy code cũ (revert P4), rồi mới khởi động lại process.
  Revert code khi DB còn 0006, hoặc để process code mới chạy giữa bước 2 và 3, ⇒ "Can't locate revision" ở mọi đường Postgres (outage, phục hồi bằng redeploy code mới).
- P1–P3, P5 không schema. Dữ liệu ngoài repo không bị revert.

## Risks

| # | Rủi ro | Khả năng × Tác động | Mitigation |
|---|---|---|---|
| R1 | Cờ tắt mà output đổi | Trung bình × Cao | 2 golden; import lười; field mới chỉ trên dataclass; test không-import |
| R2 | Không đạt n ≥ 60 dự đoán/nhãn | **Cao** × Trung bình | Q6 chấp nhận `KEEP_OFF_INSUFFICIENT_N`; không hạ ngưỡng; `min_n_needed` + số văn bản cần thêm; P5 bỏ biến thể E khi verdict đã chắc (RT-12) |
| R3 | Chưa có dedicated classifier endpoint/model | Cao × Cao | Q3: người dùng cấp vào `ai-service/.env`; probe qua đường production (RT-08) + `served_model` anthropic; thiếu ⇒ BLOCKED, không thay model |
| R4 | Nhãn GPT sai/lệch; người duyệt neo theo GPT | Cao × Cao | HG-1 có trọng số (D18); cổng dùng precision bảo thủ (RT-01); báo ma trận GPT↔người là cận trên |
| R5 | Prompt injection | Thấp × Cao | D12: output đóng + span + trạng thái do code; tín hiệu chỉ đếm (RT-05) |
| R6 | Lộ nhãn luồng 2 ra BE / review BE ngập finding high | Trung bình × Cao | D3, D8; trần 5 CONFLICT/hồ sơ, evidence cả node (RT-10); test wire |
| R7 | Ăn ngân sách/hạn job | Trung bình × Trung bình | D5 dự trữ bao trọn lô (RT-07); chạy sau trích xuất; bắt `ProcessingTimeout` |
| R8 | Bùng nổ ứng viên / dẫn chiếu luật ngoài chiếm top-k | Cao × Trung bình | Top-k chốt trên dev; bỏ địa chỉ kèm tên văn bản ngoài (RT-09) |
| R9 | Rò rỉ held-out (tuning, URL/nội dung gần trùng, chọn lại mẫu/quyết định duyệt) | Trung bình × Cao | D15 gom cụm (RT-13); `verify`; CLI từ chối held-out ở P2/P3 trừ bước S4 deterministic; khoá selection (P2) + khoá quyết định trước trial 1 (RT-15) |
| R10 | Văn bản HĐ vào repo | Trung bình × Cao | D14; `git check-ignore` + test quét |
| R11 | Postgres test bị skip | Cao × Cao | `AI2_REQUIRE_DOCKER=1`; BLOCKED |
| R12 | Test luồng 1 hard-code head 0005 đỏ | Chắc chắn × Thấp | P4 sửa `test_contract_graph_edge_store.py` (RT-06) + `test_contract_graph_postgres_store.py` sang head động |
| R13 | Mẫu công khai không có phụ lục thật | Cao × Trung bình | S2 rỗng ⇒ báo `n=0`; "đo trên mẫu công khai" |
| R14 | Sự cố provider xoá quan hệ đã phân loại | Thấp × Thấp | RT-14: chỉ thay dòng khi có ≥1 lô hoàn tất hoặc `NO_CONSENT` |
| R15 | Outage khi rollback do process code mới tái migrate | Trung bình × Trung bình | Runbook dừng process (RT-11) |

## Red-team disposition

Nguồn: `reports/from-code-reviewer-to-planner-red-team-eval-integrity-plan-review-report.md` (15 finding: 4 High, 9 Medium, 2 Low). Không còn ô mở.

| ID | Mức | Xử lý | Sửa ở đâu | Lý do / cách sửa |
|---|---|---|---|---|
| RT-01 | High | ACCEPTED-FIXED | plan.md D18; phase-1 §Req 6–7 (`review.py` π, `score.py` bảo thủ + 1/π); phase-2 §Req 12 (chọn mẫu π); phase-5 §Req 2, 4 (`decide` bảo thủ), test `test_gate_uses_conservative_precision`, `test_weighted_estimate_reported` | Cổng tính dự đoán không có gold duyệt là **sai**; ước lượng Horvitz–Thompson 1/π chỉ báo; HT đạt mà bảo thủ không ⇒ `HUMAN_DECISION` |
| RT-02 | High | ACCEPTED-FIXED | plan.md D17; phase-2 §Req 11–13 (tầng S4 B∪C ngoài pool trên held-out, GPT gán, khoá selection, xuất phiếu); phase-5 bước 0 (`candidates ⊆ pool ∪ S4`) | Ứng viên deterministic từ code đã đóng băng sinh trước mọi lời gọi bộ phân loại trên held-out; HG-1 dời sau P2 để một phiếu phủ cả S4 |
| RT-03 | High | ACCEPTED-FIXED | plan.md D11, Data flow; phase-4 §Req 4, test `test_existing_review_item_ids_prefix_preserved_embedded_annex`, `test_conflict_candidate_adds_no_context_finding`; fixture phụ lục nhúng cùng file | Khối pairs sau `idp.py:361`, trước `coverage`; `build_contract_context` không thấy candidate mới |
| RT-04 | High | ACCEPTED-FIXED | plan.md D6, D16; phase-3 §Req 5 (client `served_model`), §Req 6 (family), bước 0, tests `test_trace_records_served_model`, `test_family_router_prefix_and_unknown` (P1), `test_family_check_on_served_models` (P3); phase-1 §Req 4 (labeler ghi `served_model`, phải `openai`); phase-5 bước 0 | `family()` lấy đoạn sau `/`, unknown ⇒ thoát mã 2; kiểm trên model thực phục vụ |
| RT-05 | Medium | ACCEPTED-FIXED | plan.md D12; phase-3 §Req 2, tests `test_benign_clauses_have_no_injection_signal`, `test_injection_signal_counted_but_pair_sent`, `test_obeying_injection_cannot_fabricate` | Không bỏ cặp; mẫu riêng `\b` trên văn bản gập dấu, cả `text` + `context`; chỉ đếm |
| RT-06 | Medium | ACCEPTED-FIXED | phase-4 §Req 7, inventory, Tests After; plan-graph P4 `files_to_modify` | `test_0005_is_the_single_head_after_0004` → head động + chuỗi `0006→0005→0004` |
| RT-07 | Medium | ACCEPTED-FIXED | plan.md D5, D13; phase-3 §Req 2, test `test_deadline_reserve_covers_whole_batch` | Trước mỗi lô đòi `remaining() ≥ 30 + max_attempts × call_timeout_seconds` |
| RT-08 | Medium | ACCEPTED-FIXED | plan.md D6; phase-3 §Req 3 (`classifier_client` + env `_PAIRS_BASE_URL/_API_KEY`), bước 0 (probe qua đường production), test `test_classifier_client_env_override_and_fail_closed` | Probe đi qua `classifier_client(NineRouterClient(), model)` với cùng `.env` như runtime; thiếu cấu hình dedicated thì fail-closed, không kế thừa endpoint/key core |
| RT-09 | Medium | ACCEPTED-FIXED | phase-2 §Req 4, test `test_explicit_ref_to_external_law_dropped` | Bỏ địa chỉ khi `named_document` ≠ None hoặc tên loại văn bản (luật/bộ luật/nghị định/thông tư/quyết định/pháp lệnh/nghị quyết) đứng sau địa chỉ |
| RT-10 | Medium | ACCEPTED-FIXED | plan.md D8, D13; phase-4 §Req 5, tests `test_conflict_findings_capped_per_dossier`, `test_conflict_evidence_is_whole_node_citation`; doc AI2-20 ghi severity | Trần 5/hồ sơ; evidence cả node; span LLM chỉ ở bảng |
| RT-11 | Medium | ACCEPTED-FIXED | plan.md §Rollback; phase-4 §Rollback; doc AI2-20 | Runbook: dừng mọi process code mới → downgrade → deploy code cũ |
| RT-12 | Medium | ACCEPTED-FIXED | plan.md frontmatter effort, Q5, D18; phase-1 §Req 3 (in ước số dòng trước freeze); phase-2 §Req 12 (trần 380); phase-5 §Req 1 (khả thi n≥60, bỏ E) | Trần mẫu cố định có trọng số; ước tính in trước khi khoá |
| RT-13 | Medium | ACCEPTED-FIXED | plan.md D15; phase-1 §Req 2, 5, tests `test_near_duplicates_share_cluster`, `test_content_contamination_detected`, `test_contaminated_cluster_forced_to_dev` | Gom cụm gần trùng trước split; kiểm nhiễm bẩn theo nội dung |
| RT-14 | Low | ACCEPTED-FIXED | phase-4 §Req 3–4, tests `test_ran_semantics` | `pair_relations_ran=True` chỉ khi (`mode=="llm"` ∧ ≥1 lô hoàn tất) hoặc `rule_only_reason=="NO_CONSENT"` |
| RT-15 | Low | ACCEPTED-FIXED | phase-5 §Req 1–2, 4, test `test_decide_refuses_decisions_sha_mismatch` | Commit `heldout_review` (sha decisions) trước trial 1; mỗi trial ghi sha; `decide` từ chối khi lệch |

Rủi ro red-team §4 được chấp nhận kèm điều kiện: `KEEP_OFF_INSUFFICIENT_N` (Q6, có `min_n_needed`); người duyệt thấy nhãn GPT (báo cáo ghi ma trận là cận trên); dev ≈5 văn bản (ghi số vòng tune, không dùng số dev làm bằng chứng); pool tất định kiểm bằng subprocess hai `PYTHONHASHSEED` trước freeze (phase-1 test `test_pool_stable_across_hash_seeds`); Kafka gọi LLM không ghi bảng (coverage `pairs.llm_calls`).

## Validation Log

- VL-1 | complexity hint: complex · 5 phases · risk: consent/egress gate + LLM grounding + dữ liệu nhãn | khớp `--hard --deep --tdd` | giữ mode.
- VL-2 | planner 2026-10-08 | baseline OBSERVED: ai-service `13 failed, 1290 passed, 44 skipped`; evals `77 passed`; ruff contract_graph sạch.
- VL-3 | planner 2026-10-08 | `hs-run plan next --fact-subjects …` exit 2 ⇒ caller bằng grep.
- VL-4 | planner 2026-10-08 | probe LLM: `localhost:20128` không phản hồi; `.env` core trỏ OpenAI `gpt-4o-mini` ⇒ Claude chưa có; bake-off run1 có thể đã dùng GPT.
- VL-5 | red-team 2026-10-08 | GO-with-fixes: 15 finding (4 High) ⇒ 15/15 ACCEPTED-FIXED (§Red-team disposition).
- VL-6 | validate 2026-10-08 (người dùng) | Q1 consent = `policy_flags.egress_allowed` + DEC; Q2 có issue độ phủ hạn chế; Q3/Q4 người dùng cấp dedicated classifier endpoint/model vào `ai-service/.env`, GPT gán / classifier LLM thuộc họ được nhận diện, live BLOCKED nếu chưa có; Q5 duyệt trước P5 (250–380 dòng theo RT-12); Q6 chấp nhận `KEEP_OFF_INSUFFICIENT_N`; Q7 `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`; Q8 dữ liệu ở `.harness/state/contract-graph-pairs/`.
- VL-7 | planner 2026-10-08 | cấu trúc đổi theo RT-02: xuất phiếu HG-1 dời từ P1 sang cuối P2 (sau khi sinh S4); `manifest.json` thêm P2 vào chuỗi sở hữu; `plan_graph.py --require` chạy lại exit 0.
- VL-10 | cook P2 2026-10-09 | dev recall không cắt 15/24, recall@K phẳng (≤20 ứng viên/văn bản dev) ⇒ quy tắc cho K=10; **người dùng chốt giữ `PAIRS_TOP_K=40`** (held-out tới 42 node); `tuning_rounds` 0. Đóng băng `pairs-cand-v1` (`b0022c8`). S4 31 cặp (GPT `gpt-4o-mini-2024-07-18`); HG-1 181 dòng khoá trong manifest (`29c4dc1`), phiếu ở `.harness/state/contract-graph-pairs/review/heldout_review.csv`. Deviation: `pairs/manifest.py` `verify` chấp nhận file S4 của `extension_s4`.
- VL-11 | cook P5 live 2026-10-09 | khóa HG-1 commit `836c91ae`; sau các sửa provenance ở `pair_builder.py`/`bakeoff.py`, C1 và B1 cuối cùng chạy bằng classifier model được nhận diện phục vụ `claude-sonnet-4-6`: C `9/101`, 141.264 token, 227,597 s; B `8/101`, 135.026 token, 195,498 s. E1 có ba lần thử được ghi nhận nhưng đều provider-error; không ghi artifact. C2/B2/E2 chưa chạy; artifact trước fingerprint cuối bị loại khỏi scoreboard.
- VL-12 | cook P5 gate 2026-10-09 | probe endpoint trả 503/429 `individual quota reached`; tester độc lập ghi **BLOCKED**, focused tests `62 passed`, targeted Ruff sạch. Không tạo scoreboard/decision mới và không bịa số; cần quota/key hoạt động rồi chạy lại đủ sáu trial trước verification P5.
- VL-13 | cook P5 rerun 2026-10-09 | snapshot Claude trước đó đã superseded vì provider trả response rỗng (completion=0); không dùng cho scoreboard cuối.
- VL-14 | cook P5 current model 2026-10-09 | requested cx/gpt-6-sol, served gpt-6-sol, family openai, labeler gpt-4o-mini-2024-07-18; C1/B1/E1/C2/B2/E2 = 3/101, 2/101, 9/101, 4/101, 3/101, 9/101; E over-budget; rank E > C > B, decision HUMAN_DECISION; 223 eval tests passed.
- VL-9 | cook P1 2026-10-09 | deviation (người dùng chốt): `html_to_text` giữ bình luận/FAQ/footer sau hợp đồng ở 14/15 nguồn web (114/1021 cặp) ⇒ thêm cắt đuôi tất định (`562575d`), freeze lại (`46e6625`): 15 nguồn cắt / 0 sót, pool 1021 → 839, HG-1 ước 216 → 198, pool sha `9167a02c…4019` bằng nhau dưới `PYTHONHASHSEED` 0/1. Diễn giải bảo thủ: `family()` dùng `o\d+` (không fail-open "openchat"). ruff gate dùng `--config ai-service/pyproject.toml` (`evals/` không có config riêng; config toàn cục máy báo lỗi cả file cũ).
- VL-8 | consistency sweep 2026-10-08 (tiếp sau khi planner dừng do limit) | HG-1 chỉ xuất ở P2 (P1 §18, P2 §Req 12–13, P5 §24, plan-graph) — khớp; 20 tên test trong §Red-team disposition đối chiếu với phase: 3 tên lệch (RT-04, RT-13) đã sửa cho khớp phase; `plan_graph.py --require` exit 0, batch tuần tự P1→P5; hai báo cáo red-team trong `reports/` giống hệt nhau (bản `unattributed` là bản sao) | 0 mâu thuẫn còn mở. `hs-run plan next` không chạy được trên Windows (`hs-run` là sh, `hs-run.cmd` lỗi xuống dòng) ⇒ bước được xác định thủ công.

## Quyết định đã chốt (từ câu hỏi mở)

- **Q1** — dùng `policy_flags.egress_allowed` làm consent (D4); ghi DEC (§DEC cần ghi) trước merge; job thật rule-only cho tới khi BE bật.
- **Q2** — có issue `CONTRACT_GRAPH_PAIRS_LIMITED_COVERAGE` (`NEEDS_REVIEW`) mỗi job rule-only (D7), có test.
- **Q3/Q4** — endpoint/model classifier do người dùng đặt vào ai-service/.env; không dán key. GPT vẫn gán nhãn; classifier được phép dùng model Anthropic, Google hoặc OpenAI được nhận diện, với tên cụ thể khác labeler; mọi trial phải ghi requested/served model. Snapshot cuối dùng cx/gpt-5.5.
- **Q5** — người dùng duyệt HG-1 trước P5; ước 250–380 dòng, trần cứng 380 (D18).
- **Q6** — chấp nhận `KEEP_OFF_INSUFFICIENT_N`.
- **Q7** — `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`.
- **Q8** — `AI2_CG_PAIRS_DATA_DIR` = `.harness/state/contract-graph-pairs/`.

P5 đã có đủ scoreboard live dưới model cx/gpt-5.5 (served gpt-5.5, họ OpenAI, khác labeler gpt-4o-mini-2024-07-18). Rank là `tie_within_noise`, E vượt budget ở cả hai trial, và C chưa đủ `MIN_N`, nên decision chính thức là `KEEP_OFF_INSUFFICIENT_N`; cờ vẫn tắt.

## Cook deviation ledger — classifier model family (2026-10-09)

- Người dùng bổ sung cho phép dùng model khác Claude.
- Dedicated classifier family được mở rộng có kiểm soát sang anthropic|google|openai; labeler vẫn phải là OpenAI và classifier model cụ thể phải khác labeler.
- Probe endpoint cho thấy route Claude có response rỗng và route Gemini timeout/quota; route cx/gpt-6-sol phục vụ gpt-6-sol thành công và được dùng nhất quán cho C1/B1/E1/C2/B2/E2.
- Đây là deviation được người dùng ủy quyền trong cook; không đổi ngưỡng, consent, lock HG-1, hay cờ runtime. E vượt budget nên verdict vẫn chỉ là khuyến nghị HUMAN_DECISION.

## Final cook update — cx/gpt-5.5 (2026-10-10)

- P5 rerun sử dụng requested model `cx/gpt-5.5`, served model `gpt-5.5`, family `openai`; sáu trial C1/B1/E1/C2/B2/E2 cùng HG-1 lock, decisions SHA và code fingerprint.
- Recall any theo trial: C1 `5/101`, B1 `2/101`, E1 `7/101`, C2 `4/101`, B2 `3/101`, E2 `10/101`; E vượt time budget ở cả hai trial.
- `bakeoff_rank` ghi `tie_within_noise` (không có winner production). Quy tắc verdict được sửa để kiểm tra denominator `n < MIN_N` trước budget advisory; decision chính thức là `KEEP_OFF_INSUFFICIENT_N`, recommendation-only, feature vẫn tắt.
- Verification/review artifact hiện hành là `PASS`; full eval `225 passed`, focused bakeoff tests `61 passed`, targeted Ruff sạch. Không hạ ngưỡng, không bổ sung nhãn không có bằng chứng.
