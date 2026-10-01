---
id: 260929-2323-ai2-a-measure-baseline
title: "AI2-A measurement baseline: golden set, scorer, live-LLM benchmark, CI"
description: "Đo AI2 trên pipeline thật: golden set giả lập có nhãn span, bộ chấm theo đơn vị (>=60 đơn vị/chỉ số, Wilson + cluster CI, chặn pass->fail so với baseline của nhánh đích), benchmark gpt-4o-mini có trần chi phí, CI thật cho ai-service."
status: in_progress
priority: P1
effort: "10-12 ngày công agent + khoảng 1 ngày duyệt của Văn Dũng"
mode: hard
tdd: true
branch: feature/code-full
tags: [ai2, evals, golden-set, benchmark, ci]
created: 2026-09-29
author: 
decisions: []
phases:
  - phases/phase-1-golden-set-synthetic.md
  - phases/phase-2-scorer-and-thresholds.md
  - phases/phase-3-live-llm-benchmark.md
  - phases/phase-4-ai2-ci-gate.md
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Plan: AI2-A measurement baseline: golden set, scorer, live-LLM benchmark, CI

> hs:cook đọc file này làm hợp đồng. Mỗi claim mang một nhãn: **OBSERVED** (đã chạy lệnh thật, xem mục "Bằng chứng nền"), **DERIVED** (tính từ dữ liệu đã quan sát), `[ASSUMED]` (chưa kiểm) hoặc `[PRIOR]` (kiến thức nền, chưa kiểm lại). Mọi lệnh chạy từ root repo. `$PY` là `.\ai-service\.venv\Scripts\python.exe` trên Windows (kèm `$env:PYTHONIOENCODING="utf-8"`) hoặc `ai-service/.venv/bin/python` trên Linux/CI. Bản này đã sửa theo red-team (REVISE, RT-01..RT-15); cách xử lý từng finding nằm ở mục "Red-team disposition".

## Tổng quan

A dựng nền đo lường cho AI2 trước khi B (dịch vụ có version) và C (tích hợp, nâng chất lượng) thay đổi hệ thống. Khung `evals/` hiện tại cho kết quả sai theo hai hướng ngược nhau:

- **Xanh giả trên Linux/CI.** Khi hash card khớp, runner chấm `pipeline_mirror.py`. File này là bảng tra từ tên fixture ra đáp án (`evals/eval_types/ai2_grounded_query/pipeline_mirror.py:57-93`), nên cả 5/5 chiều đều đạt 100% (PB-2).
- **Đỏ giả trên Windows.** `ConfigDriftError` xuất hiện vì CRLF, không phải vì card bị sửa. Hash sidecar được tính trên byte LF, còn checkout Windows (`core.autocrlf=true`) đổi dòng cuối thành CRLF (PB-3).

A thay bằng bốn thứ:

1. **Golden set giả lập** sinh từ spec. Nhãn span/giá trị có sẵn theo cách dựng, và nhãn trạng thái sinh theo luật (commit trước lần chạy hệ thống đầu tiên). Có 1 hợp đồng từ 55 trang trở lên. Kèm 95 case `UNVERIFIED` được Văn Dũng duyệt mù.
2. **Bộ chấm tất định** chạy `FourLayerReasoner.run` và `run_idp` thật. Chấm theo đơn vị với Wilson CI và cluster-bootstrap CI, sàn 60 đơn vị. Gate chặn pass→fail so với baseline **của nhánh đích** và chặn mọi đơn vị tripwire mới bị FAIL.
3. **Benchmark `gpt-4o-mini`** pin snapshot, có trần chi phí. Mỗi lượt live chạy tay sẽ đỏ khi tripwire hồi quy.
4. **CI**: job PR offline không dùng secret, cộng workflow live chỉ chạy tay (`workflow_dispatch`).

A **không** nâng chất lượng. Con số 21/24 (87,5%, Wilson 95% [69,0%; 95,7%], DERIVED) của phiên lập kế hoạch **bị thổi phồng**: `ai-service/app/reasoning/l0_rules.py` (~336-394) hardcode câu trả lời và node id của fixture HD-TONG-HOP (`field_usd`, `field_penalty_build`, `field_penalty_equip`, `cl_9`) cho đúng các câu hỏi thi (PB-11, main đã kiểm). A chỉ báo nó như một tham chiếu có cảnh báo, và đo baseline mới trên golden không bị rò. Việc nâng lên ≥ 95% và gỡ các luật riêng cho fixture thuộc C (VD-6).

## Quyết định đã khoá
Chốt qua AskUserQuestion ngày 29/09/2026 (không re-litigate):

| # | Quyết định | Hệ quả cho A |
|---|---|---|
| D-A1 | Đóng gói AI2 = image Docker có tag semver trên GHCR + HTTP API; Backend gọi qua HTTP | A đo trên image/endpoint thật ở B/C; A tự nó không đóng gói |
| D-A2 | E2E = chỉ Backend ↔ AI2 (không AI1/OCR, không Keycloak) | Thuộc C; A cung cấp bộ chấm cho E2E |
| D-A3 | Lưu trữ AI2 = schema `ai2` trong Postgres của Backend (P2, cần ADR-14) | Thuộc C |
| D-A4 | Phạm vi = EXPANSION (thêm observability, CI đầy đủ, chi phí LLM) | A làm CI thật cho `ai-service` |
| D-A5 | Registry = GHCR của repo | Thuộc B |
| D-A6 | Benchmark/eval LLM = OpenAI `gpt-4o-mini`, **chỉ dữ liệu giả lập/ẩn danh** | A pin phiên bản model, có giới hạn chi phí |
| D-A7 | Golden set = giả lập thực tế ngay (có 1 bản 50+ trang) + duyệt 95 case `UNVERIFIED`; hợp đồng thật ẩn danh bổ sung sau | Nguồn dữ liệu của A |
| D-A8 | Ngưỡng **chặt**: 0 giá trị bịa và 100% citation đúng là gate chặn; mọi chỉ số khác ≥ 95%; query p95 < 20 giây | Baseline hiện 21/24 (87,5%)¹ → A báo khoảng cách; nâng chất lượng thuộc C |
| D-A9 | Chấm **theo đơn vị** (citation / giá trị / câu), **≥ 60 đơn vị cho mỗi chỉ số**, báo `x/n` + khoảng tin cậy Wilson, thêm gate "không item nào từ đạt → trượt" | Golden set phải đủ ≥ 60 đơn vị/chỉ số |
| D-A10 | **Một người** gán nhãn và duyệt card/golden (Văn Dũng) | Không đo được inter-annotator agreement; báo cáo phải ghi hạn chế này |
| D-A11 | Citation chấm ở **mức đoạn (span/bbox)**, không chỉ node | Nhãn span của dữ liệu giả lập nên sinh by construction từ bộ tạo; cần chốt ngưỡng IoU |
| D-A12 | **Bỏ `pipeline_mirror.py`**, eval chấm pipeline thật (`ai-service/app/reasoning/stack.py`) | Duyệt lại card eval vì đổi cách chấm |
| D-A13 | Tách 3 kế hoạch theo phụ thuộc: A đo lường → B dịch vụ có version → C tích hợp | A làm trước để có baseline |

¹ Main đã kiểm ngày 30/09/2026: con số 21/24 **bị thổi phồng do rò rỉ tập test**. `l0_rules.py` (~336-394) trả lời bằng node id cố định của HD-TONG-HOP lấy từ một commit cũ (PB-11). A không dùng con số này làm mốc có gate. Mốc thay thế là baseline trên golden giả lập (P2/P3).

## Quyết định validate (người dùng chốt ngày 30/09/2026)

Cả 9 điểm đã được người dùng chốt ở bước validate. Cook làm theo cột "Đã chốt"; mỗi điểm có một dòng tương ứng trong `## Validation Log` (VL-7..VL-15).

| # | Câu hỏi | Đã chốt | Hệ quả | Ảnh hưởng |
|---|---|---|---|---|
| VD-1 | Ngưỡng τ và đơn vị IoU (D-A11; RT-08) | (a) IoU trên **tập dòng** (Jaccard), τ = 0,5. `acceptable_spans` là tập dòng tường minh cho từng câu. Bbox IoU chỉ dùng làm chẩn đoán `bbox_consistency` | Card có `span_iou_unit: "line_set"`, `span_iou_threshold: 0.5`. Revisit khi B/C phát bbox thật | P1 F1.3, P2 F2.4 |
| VD-2 | D-A8 chặn ở đâu trong giai đoạn A→C | (a) PR gate chặn khi có một trong các trường hợp: hồi quy so với baseline của nhánh đích; đơn vị tripwire mới bị FAIL; P0 invariant hồi quy; lỗi setup. Ngưỡng D-A8 luôn được tính và in ra. C bật `enforce_thresholds_in_pr`. Release của B/C bắt buộc `threshold_verdict = PASS` | CI không bị ngưỡng làm tắc trước C. Khoảng cách tới D-A8 luôn hiện trong report | P2 exit code, P4 workflow |
| VD-3 | `value_accuracy` tìm giá trị ở đâu | (a) Chỉ trong `answer`, kèm chỉ số chẩn đoán `value_in_evidence` | Hệ thống trích nguyên văn nhưng không nêu giá trị trong answer thì bị tính là thiếu | P2 `units.py` |
| VD-4 | Domain `ai2_contract_package` | (a) Bỏ mirror; chấm `run_idp` thật. Đây là mở rộng D-A12, người dùng đã xác nhận | Khoảng 25 file của domain đổi ở P2 | P2 |
| VD-5 | Trần chi phí và cách chạy live | **Đã đổi:** chỉ chạy tay, **không có lịch**. Trần giữ nguyên: baseline k=5, lượt ad-hoc k=3, `MAX_USD` = 5 USD/lượt, `MAX_CALLS` = 1000/lượt, project OpenAI trần cứng 20 USD/tháng | **Trôi model hay provider âm thầm sẽ không được phát hiện tự động.** Giảm thiểu: pin snapshot có ngày; ghi `response_model` trả về; bắt buộc chạy benchmark live trước **mỗi** release B/C (mục checklist release, xem "Out of scope và bàn giao") | P3, P4 F4.2, HC-5 |
| VD-6 | Ai gỡ các luật riêng cho fixture trong `l0_rules.py` | (a) Giao cho C. A giao `test_no_eval_leakage` với allowlist đóng băng, chỉ được giảm, và phải rỗng khi C nghiệm thu | Baseline của A vẫn chứa bucket bị rò; bucket này đã tách khỏi gate | P2 F2.15, bàn giao C |
| VD-7 | Gate p95 < 20 s đo trên tập lượt nào | (a) Chỉ lượt `used_llm=true`, n ≥ 60, thiếu thì `UNDERPOWERED`. p95 gộp chỉ để chẩn đoán. Bootstrap theo `question_id` | P1 cần ≥ 15 câu kiểu so sánh. Có thể phải tăng k nếu n < 60 | P1 F1.1, P3 F3.3 |
| VD-8 | Mô hình duyệt và nghiệm thu CI live (RT-07) | **Đã đổi:** chỉ `workflow_dispatch`, bỏ lịch. Environment `ai2-live` **giới hạn deployment branch `main`**, cộng trần cứng OpenAI. Required reviewer **không bắt buộc**, vì chính thao tác dispatch tay đã là hành động của người; nếu muốn thì bật, việc này tuỳ chọn và có ghi tài liệu. Nghiệm thu live-CI = workflow đã có trên `main` + 1 lượt dispatch tay thành công | Bằng chứng live của A vẫn là lượt baseline local ở P3. Nghiệm thu live-CI có thể xong sau khi A đóng | P4 F4.2, bước 10, HC-5 |
| VD-9 | Phạm vi tripwire `fact_value_fabricated` | (a) Fact của cả 95 case eval. `processing_state_match` chỉ tính trên case GOLDEN | Tripwire có hiệu lực ngay (~11.280 fact) | P2 F2.7 |

## Bằng chứng nền (probe của planner, red-team và main, 29–30/09/2026)

| # | Quan sát | Nhãn |
|---|---|---|
| PB-1 | `run_grounded_query_evals.py` và `run_production_evals.py` thoát **2** khi gặp `ConfigDriftError`, dưới cả bash lẫn PowerShell `$LASTEXITCODE`. Tiến trình `powershell -Command` bao ngoài lại trả **0**, vì runbook `evals/docs/production-eval-setup.md:26-36` chạy nối lệnh mà không kiểm exit code. Lỗi code thật: `evals/scripts/run_release_verification.py:108` trả 0 cho `UNVERIFIED`. Ngoài ra `:48` import một module không tồn tại, và `:105` ghi vào một plan dir không tồn tại | OBSERVED |
| PB-2 | Khi hash được băm lại trên bản sao: 3/3 test mutation pass, và eval grounded chấm mirror được 100% cả 5 chiều. Eval hiện tại là tautology | OBSERVED |
| PB-3 | Card kết thúc bằng `\r\n`; `core.autocrlf=true`. Sau khi đổi CRLF→LF, sha256 **khớp** sidecar cho cả `evals/cards/ai2_grounded_query.json` và `evals/eval_config.json`. `config_integrity.py:64-66` băm byte thô | OBSERVED |
| PB-4 | `FourLayerReasoner` thật trả citation có `line_ids`, `page`, `char_start/char_end`, nhưng `bbox: []` và `geometry_available: False`. Citation ở mức dòng (red-team probe; `outline.py:114-117,162`) | OBSERVED |
| PB-5 | Snapshot giả lập đi qua `adapt_ai1_input` rồi `FourLayerReasoner` offline: sinh node CLAUSE "Điều 1…5". Câu về giá trị có xung đột ra NEEDS_REVIEW; câu một giá trị không xung đột cũng ra NEEDS_REVIEW; "MST Bên B là gì?" ra INSUFFICIENT_EVIDENCE dù MST có trong văn bản. Schema bắt `geometry_status` viết thường. Mỗi câu 0–6 ms | OBSERVED |
| PB-6 | Suite `ai-service` với `-m "not live"`: **16 failed, 811 passed, 10 skipped, 6 deselected**, cộng 2 file lỗi collection. Có 23 cảnh báo marker lạ (`integration`, `live`, `llm`) | OBSERVED |
| PB-7 | Catalog 65 case. HD-TONG-HOP 65 trang, 71 node; 52/296 node có bbox; **0/248** trang có `line_bboxes` | OBSERVED |
| PB-8 | `run_idp` offline trên 95 candidate: khớp 69/95 nhãn `UNVERIFIED`; 0 lỗi; p95 0,044 s; 11.280 fact. Chỉ là xem trước | OBSERVED |
| PB-9 | `ruff`: `ai-service` 82 lỗi (63 I001, 15 F401, 3 F601 `tests/test_p6_event_ui_convergence.py:345-347`, 1 F841 `app/reasoning/gold.py:48`); `evals` 30 lỗi. F401 autofix sẽ xoá re-export có chủ đích ở `app/tools/jobs.py:12-20` | OBSERVED |
| PB-10 | Wilson 95%: 60/60 → [94,0%; 100%]; 57/60 → [86,3%; 98,3%]; 0 lỗi / 60 đơn vị → cận trên tỉ lệ lỗi 4,87% | DERIVED |
| PB-11 | `ai-service/app/reasoning/l0_rules.py` ~336-394 hardcode câu trả lời và node id của fixture HD-TONG-HOP (`field_usd`, `field_penalty_build`, `field_penalty_equip`, `cl_9`), đúng với `must_cite` ở `fixtures/reasoning/hd_tong_hop_tasks.json:17,53,62`. Ít nhất 5/15 task HD được trả lời nhờ luật khớp sẵn câu hỏi thi | OBSERVED (red-team, main) |
| PB-12 | `app/api/main.py:63` gọi `load_dotenv` ngay khi import. `ai-service/.env` có `OCR_DPI`, và `src/contract_ocr/infrastructure/config.py:40` dùng giá trị này để đè cấu hình. `OCR_DPI=300 pytest tests/unit/test_core.py::test_schema_and_config` báo `DID NOT RAISE`, tức đây là nguyên nhân gốc của T10. Khoá API và cờ vector cũng lọt vào suite "offline" theo cùng đường | OBSERVED (red-team) |
| PB-13 | Có `.gitattributes eol=lf` mà chỉ chạy `git checkout --` thì file vẫn CRLF (git bỏ qua file sạch theo stat); phải xoá file rồi checkout lại. PyYAML parse khoá `on:` thành `True`. GitHub luôn đặt `CI=true`. `workflow_dispatch` chỉ chạy được khi file workflow đã nằm trên default branch. `uv.lock` có `aiokafka` và `mistralai` | OBSERVED (red-team; docs GitHub) |

## Ràng buộc (constraint-scan)

- **Zone ghi file.** `harness/data/ownership.yaml:8-16` chỉ khoanh `docs/`, `.harness/state/`, `harness/standards/`, `plans/`, và chỉ áp cho script harness. Path của A không bị chặn. `harness/hooks/write_guard.py:130-180` không chứa file nào của A. `harness/data/write-deny-policy.yaml:14` có `soft_rules: []`.
- **Stage policy.** `harness/data/stage-policy.yaml:62-64`: bước `pr` cần `verification`, `review-decision`, `plan-approval`, nên P4 phát thêm `review-decision.json`.
- **PR guard.** `.github/workflows/pr-guard.yml` chặn PDF/ảnh (golden chỉ được là JSON/MD), kiểm tên nhánh và tiêu đề PR. Luồng merge là feature → `develop` → `main` (`:44-50`). `.gitignore:3` bỏ qua `*.pdf`.
- **CODEOWNERS.** `.github/CODEOWNERS:3` đặt `*` cho cả team; `/.github/` cần `@hieubui2409`. Đặt required check là quyết định của mentor.
- **Line ending.** `.gitattributes:1` chỉ có `*.sh text eol=lf` (PB-3, PB-13).
- **Code standards.** `docs/code-standards.md:39-43`: có marker `not live`; tách `denominator/covered/passed`; candidate không phải ground truth; judge chỉ advisory. `:50`: không log secret hay văn bản hợp đồng thô. `:7`: Python ≥ 3.12.
- **DOC-06 eval report.** `docs/DOC-06-eval-report.md:19-20,28-37` đòi 2 reviewer (D-A10 lệch khỏi yêu cầu này, được ghi thành hạn chế) và split 60/20/20 theo hợp đồng.
- **ADR.** A không cần ADR. OpenAI chỉ phục vụ benchmark (chọn qua env `ai-service/app/llm/client.py:23-26`); không thêm data store; chỉ dùng dữ liệu giả lập. ADR-14 thuộc C.
- **Tiền đề cook.** WIP trên `feature/code-full` phải được commit trước. Mọi baseline ghi `git_sha` và `dirty`.

## Kiến trúc và luồng dữ liệu

```
P1  guideline + evals/golden/catalog.py (expected_state = rule(MutationSpec)) ──COMMIT TRƯỚC khi chạy reasoner──►
    render_snapshot.py ──► evals/data/golden/snapshots/G0x.json (ai1.snapshot.v1) + questions.json (tập dòng gold) + manifest.json
    candidate_manifest (95) ──worksheet mù (không nhãn cũ, không output hệ thống)──► Văn Dũng ──promote──► golden_manifest.json
P2  golden ──evals/real_pipeline.py (adapt_ai1_input → FourLayerReasoner(llm=None, vector off).run(env, classify_ask(q)))──► output
    output ──units.py (IoU tập dòng ≥ τ; value regex)──► unit records ──unit_metrics.py (x/n, Wilson, cluster-bootstrap, sàn 60)
    ──► diff với baseline ở `git show origin/<base>:evals/baselines/*` (tripwire: mọi đơn vị FAIL mới đều là hồi quy) ──► exit 0/1/2
    15 task HD ──► bucket chẩn đoán `fixture_tuned_legacy` (KHÔNG vào mẫu số gate)
P3  golden + case xử lý ──BudgetedClient(gpt-4o-mini pin)──► k lượt ──► runs.jsonl (không có raw text) + summary; diff tripwire với ai2_live.baseline.json
P4  PR: uv sync → ruff → pytest offline (.env bị vô hiệu) → run_ai2_gate.py --mode pr --base-ref origin/$BASE
    live: chỉ workflow_dispatch (chạy tay), environment ai2-live (deployment branch main) → run_live_benchmark.py --fail-on-threshold --tripwire-only
```

### Danh mục chỉ số (mọi chỉ số có gate cần n ≥ 60, D-A9)

| Chỉ số | Đơn vị (id ổn định) | Ngưỡng (D-A8) | Loại | DOC-06 |
|---|---|---|---|---|
| `citation_correct` | citation phát ra `<qid>#cit#<page>:<line_ids>` | 100% | tripwire | M03 |
| `citation_recall` | `required_spans` `<qid>#rs<i>` | ≥ 95% | | M04 |
| `value_fabricated` | giá trị trong `answer` `<qid>#val#<normalized>` | 0 | tripwire | – |
| `value_accuracy` | `gold_values` `<value_id>` | ≥ 95% | | M02 |
| `state_match` | câu hỏi golden giả lập `<qid>` (**không** gồm task HD) | ≥ 95% | | – |
| `latency_p95_s` | lượt query live (tập lượt theo VD-7) | p95 < 20 s | chỉ live | – |
| `processing_state_match` | case GOLDEN | ≥ 95% | (VD-4a) | – |
| `fact_value_fabricated` | fact `<case_id>#fact#<fact_id>` (phạm vi theo VD-9) | 0 | tripwire (VD-4a) | – |
| `fixture_tuned_legacy` | 15 task HD | — | **chỉ chẩn đoán**, gắn nhãn rõ | – |

- **Citation đúng**: qua integrity (node tồn tại, `page_revision_id` khớp, `text_span` ⊂ text trang), **và** tập dòng được cite có IoU ≥ τ với ít nhất một `acceptable_span` tường minh của câu hỏi (VD-1).
- **Giá trị bịa**: mức 1 là không có trong span được cite; mức 2 là không có trong tài liệu.
- **P0 invariant**: 20 case cũ, chấm bằng vị từ trên output thật.
- Report tách theo split (dev/val/holdout). Gate tính trên toàn bộ tập, vì từng split có n < 60.

### Hợp đồng verdict và exit code

- Trạng thái mỗi chỉ số:
  - `PASS(point)`: n ≥ 60 và ước lượng điểm đạt ngưỡng. Luôn in kèm cận dưới Wilson và cận dưới cluster-bootstrap theo `contract_id` (RT-13).
  - `FAIL`, `UNDERPOWERED` (n < 60, không bao giờ tính là PASS), `NOT_RUN`.
- **Hồi quy**:
  - Chỉ số thường: item đạt trong baseline mà nay trượt.
  - Chỉ số tripwire: **mọi** `(item_id, unit_id)` FAIL chưa có trong tập FAIL của baseline, kể cả item mới (RT-02).
  - Lệch `golden_version` hoặc `scorer_version` với baseline → lỗi setup.
- **Nguồn baseline** (RT-01): ở `--mode pr` với `--base-ref`, gate đọc baseline, card và golden manifest từ `git show <base>:<path>`, không từ cây của PR. PR có sửa `evals/baselines/**`, `evals/cards/**` (trừ `proposed/`) hoặc `evals/data/golden/manifest.json` → in diff và exit 1, trừ khi workflow báo `AI2_BASELINE_CHANGE_APPROVED=true` (label `ai2-baseline-update` cộng review bắt buộc của CODEOWNER cho các path này, HC-5).
- **Exit code**:
  - `0`: không có lỗi chặn.
  - `1`: có hồi quy; P0 invariant hồi quy; ngưỡng trượt khi enforce; hoặc thay đổi baseline/card/golden chưa được duyệt.
  - `2`: lỗi setup/config/dữ liệu.
  - `3`: `UNVERIFIED` (chỉ `run_release_verification.py`).
  - `--draft` không bao giờ ghi baseline.
  - **Không đường nào trả 0 khi có lỗi.**

### Thay đổi hợp đồng (before / after / ai bị ảnh hưởng / đường chuyển)

| Bề mặt | Before | After | Ai bị ảnh hưởng | Đường chuyển |
|---|---|---|---|---|
| Card | `ai2.eval.strategy.v1` (`dimensions`, `threshold: 90`, `mirror_invoke`) | `ai2.eval.strategy.v2`: `metrics{}`, `unit_floor: 60`, `span_iou_threshold`, `span_iou_unit`, `enforce_thresholds_in_pr`, `scorer_version`. Giữ `p0_rules` và `case_matrix`. Bản đề xuất nằm ở `evals/cards/proposed/<domain>.v2.json` (RT-06) | scorer, test, `test_p4_release_verification.py`, `run_release_verification.py` | `approve_card.py` (Văn Dũng) là đường duy nhất chuyển bản đề xuất sang `evals/cards/` |
| `run_grounded_query_evals.py` | `--sample-dir --ground-truth` | Mặc định đọc golden + legacy. Giữ `--sample-dir/--ground-truth` làm alias. Thêm `--baseline --base-ref --update-baseline --draft --card-proposal --enforce-thresholds --report-json --golden-dir` | runbook | P2 |
| `run_production_evals.py` | `--sample-dir --ground-truth` | `--golden-manifest --candidates --baseline --base-ref --update-baseline --draft --card-proposal --enforce-thresholds`. Cờ cũ → exit 2 kèm chỉ dẫn | runbook | P2 |
| `pipeline_mirror.py` ×2, `evals/eval_config.json(.sha256)` | có | xoá; card contract chuyển sang `evals/cards/` | `judge_runner.py:150`, release script, test | P2 |
| Trace `NineRouterClient` | chỉ có `model` yêu cầu | thêm `response_model` (additive) | chỉ người đọc trace | P3 |
| Marker pytest; `.env` trong test | chưa đăng ký; `.env` bị nạp khi import `app.api.main` | đăng ký `live`, `llm`, `integration`, `requires_pdf_fixture`; conftest vô hiệu `load_dotenv` và xoá biến nhạy cảm, trừ khi `AI2_LIVE_TESTS=1` | CI, dev | P3 |

## Features
- `golden-set-scorer`: golden set (hợp đồng giả lập thực tế ngay, có 1 bản 50+ trang; duyệt 95 case `UNVERIFIED`; hợp đồng thật ẩn danh bổ sung sau) + bộ chấm tất định với ngưỡng chặt: 0 giá trị bịa, 100% citation đúng, các chỉ số khác ≥ 95%, p95 < 20 giây.
- `live-llm-benchmark`: benchmark chạy `gpt-4o-mini` thật (chỉ dữ liệu giả/ẩn danh), báo cáo baseline trước khi B/C thay đổi hệ thống, dùng lại được để đo sau.
- `ai2-ci`: CI thật cho `ai-service` thay placeholder hiện tại: lint, test offline, bộ chấm chế độ không LLM ở mỗi PR; chế độ LLM chạy tay/theo lịch.

Kế hoạch này là A trong bộ 3 (A đo lường → B dịch vụ có version → C tích hợp). B: `plans/260929-2323-ai2-b-versioned-service`; C: `plans/260929-2323-ai2-c-integration`.

## Phases
| # | Theme | Phụ thuộc | Cỡ |
|---|---|---|---|
| 1 | Golden Set Synthetic: guideline và `expected_state` sinh theo luật được commit trước khi chạy hệ thống; bộ sinh `ai1.snapshot.v1` + gold theo tập dòng; công cụ duyệt mù 95 case; sửa gốc CRLF (`.gitattributes eol=lf` + xoá rồi checkout lại, PB-3/PB-13) để hết `ConfigDriftError` giả trên Windows | — (tiền đề: WIP đã commit) | L, 2–3 ngày |
| 2 | Scorer And Thresholds: pipeline thật cho 2 domain; chỉ số theo đơn vị (Wilson + cluster CI); gate hồi quy dùng baseline của nhánh đích, có tripwire; card v2 dạng đề xuất; lint chống rò rỉ; gate CLI; sửa exit code | P1 | XL, 3–4 ngày, 4 commit 2a–2d |
| 3 | Live Llm Benchmark: `BudgetedClient`, k lượt, diff tripwire với baseline live, marker, `.env` bị cô lập, báo cáo baseline | P2 | M, 2 ngày, cần khoá và HC-4 |
| 4 | Ai2 Ci Gate: workflow PR (baseline của nhánh đích) và live (branch `main`, trần cứng), triage lỗi test có sẵn, lint, CODEOWNERS, tài liệu | P2, P3 | M, 2 ngày, cần mentor và HC-5 |

Các phase chạy nối tiếp P1 → P2 → P3 → P4. Không áp `--parallel` (xem Validation Log). Mỗi file chỉ thuộc một phase (`plan-graph.yaml`).

## Mốc duyệt của người (agent không tự làm)

| # | Việc | Người | Bằng chứng | Chặn gì |
|---|---|---|---|---|
| HC-1 | Duyệt golden v1 (guideline, luật `expected_state`, catalog, mẫu Q/A), rồi chạy `$PY -m evals.golden.build_golden approve --by "Văn Dũng"` | Văn Dũng | SHA của commit do Văn Dũng tạo | Các chỉ số có gate ở P2 (trước đó chỉ chạy `--draft`) |
| HC-2 | Điền `evals/corpus/candidate_decisions.json` cho 95 case (worksheet mù), rồi `promote --reviewer "Văn Dũng"` | Văn Dũng | SHA commit | `processing_state_match`; acceptance D-A7 |
| HC-3 | Duyệt 2 card đề xuất: `$PY evals/scripts/approve_card.py --proposal evals/cards/proposed/<domain>.v2.json --approved-by "Văn Dũng"` | Văn Dũng | SHA commit | Baseline chính thức ở P2 |
| HC-4 | Cho phép chạy live baseline (khoá đặt qua env, trần theo VD-5) | Văn Dũng | xác nhận trong phiên | Acceptance P3 |
| HC-5 | (i) Environment `ai2-live`: **deployment branch `main`** (required reviewer tuỳ chọn, VD-8), secret là khoá của **project OpenAI riêng có trần cứng** (VD-5). (ii) Thêm CODEOWNERS cho `/evals/baselines/`, `/evals/cards/`, `/evals/data/golden/` (Văn Dũng + mentor) và bật "Require review from Code Owners". (iii) Tạo label `ai2-baseline-update`. (iv) Mentor duyệt `/.github/` | admin repo + `@hieubui2409` | ảnh chụp cấu hình hoặc URL | Acceptance live-CI của P4 (VD-8) |

Giới hạn trung thực: sidecar hash, khối `approval` và guard `CI` chỉ giúp **lộ ra** việc sửa (tamper-evident), không chứng minh ai đã duyệt. Guard `CI` không phải kiểm soát bảo mật. Bằng chứng thật là commit do Văn Dũng tạo, cộng review bắt buộc của CODEOWNER cho các path đã khoá (RT-01).

## Out of scope và bàn giao
- **B** (`plans/260929-2323-ai2-b-versioned-service`): contract có version, image GHCR, bật LLM, observability. Phụ thuộc A. **Bàn giao cho B:** chuyển `load_dotenv` (`app/api/main.py:63`) từ lúc import sang lúc startup; A chỉ cô lập nó trong test (PB-12).
- **C** (`plans/260929-2323-ai2-c-integration`): schema `ai2` (ADR-14), E2E, nâng chất lượng lên ≥ 95%. Phụ thuộc A và B. **Bàn giao cho C (VD-6a):**
  - gỡ các luật riêng cho fixture trong `l0_rules.py` ~336-394, đến khi allowlist của `evals/tests/test_no_eval_leakage.py` rỗng;
  - bật `enforce_thresholds_in_pr` khi đạt ngưỡng;
  - ra verdict release trên tập biến thể `build_golden --variant-seed` chưa từng commit;
  - làm fixture PDF có font tiếng Việt cho 5 test T4–T8 (issue có hạn chót trước khi C đóng).
- **Ngoài A:** hợp đồng thật ẩn danh (D-A7 "sau"); benchmark vector/embedding (embedding không đi qua trần chi phí); `restart_e2e.py`; probe tạm; đo qua HTTP API (không import `app.api.main` từ evals); inter-annotator agreement (D-A10; A chỉ báo độ đồng thuận giữa nhãn của người duyệt và nhãn của tác giả fixture); hiệu chuẩn judge; cập nhật DOC-06; đặt required check; type-check (repo không có cấu hình).

## Acceptance (toàn plan)
- [ ] Mỗi phase red→green TDD; test suite của project xanh sau mỗi phase (dùng lệnh test thật của repo).
- [ ] Lint + type-check + build của project sạch (theo lệnh thật của repo):
  - Lint: `cd ai-service; .venv/Scripts/ruff.exe check . ../evals` → `All checks passed` (trước là 82 + 30 lỗi).
  - Build: `cd ai-service; uv sync --frozen --extra dev --extra web --extra mistral --extra kafka` exit 0.
  - Type-check: N/A, repo không có cấu hình.
- [ ] (invariant) `$PY -m evals.golden.build_golden --check` exit 0 trên Windows và Linux. `stats` phải thoả:
  - câu hỏi ≥ 60 (mục tiêu 84), trong đó ≥ 15 câu kiểu so sánh;
  - `required_spans` ≥ 60, `gold_values` ≥ 60;
  - câu không trả lời được ≥ 20%;
  - có 1 hợp đồng ≥ 55 trang; 8/8 snapshot hợp lệ schema.
- [ ] (manual — `manual_test_anchor.py`) HC-1: manifest có `approval.approved_by = "Văn Dũng"`, **và** SHA của commit duyệt do Văn Dũng tạo được ghi vào `verification-P1.json`. Đây không còn là "invariant" (RT-01).
- [ ] (manual — `manual_test_anchor.py`) HC-2: 95/95 quyết định khác `PENDING` với `reviewer_id = "Văn Dũng"`; số case GOLDEN bằng số APPROVE; `validate_corpus_separation` PASS; độ đồng thuận với nhãn của tác giả fixture được báo cáo.
- [ ] (invariant) D-A12: `git ls-files "*pipeline_mirror*"` rỗng; `git grep -n pipeline_mirror -- evals ai-service` ra 0 hit.
- [ ] (invariant) `evals/tests/test_no_eval_leakage.py` xanh. Allowlist liệt kê đúng các literal hiện có ở `l0_rules.py`, có `file:line`, và không tăng.
- [ ] (test) `$PY evals/scripts/run_ai2_gate.py --mode pr --base-ref <base>` exit 0. Report có `x/n` + Wilson + cluster CI cho mọi chỉ số, tách theo split. `threshold_verdict` hiện khoảng cách so với D-A8. `evals/tests/test_gate_exit_codes.py` chứng minh các kịch bản:
  - drift → 2;
  - hồi quy → 1;
  - tripwire có item mới FAIL → 1;
  - PR vừa hồi quy vừa cập nhật baseline → 1;
  - sạch → 0;
  - `UNVERIFIED` → 3.
- [ ] (manual — `manual_test_anchor.py`) Live baseline (HC-4), 1 lượt k=5:
  - `response_model` trùng model đã pin;
  - lượt `used_llm=true` ≥ 60, nếu thiếu thì báo `UNDERPOWERED` (VD-7);
  - p95 kèm CI bootstrap theo câu hỏi;
  - chi phí ≤ `MAX_USD`;
  - `runs.jsonl` không có văn bản thô;
  - `docs/ai2/AI2-16-measurement-baseline.vi.md` có bảng khoảng cách so với D-A8 và mục hạn chế (D-A10, dữ liệu giả lập, 21/24 bị thổi phồng, n hiệu dụng).
- [ ] (test) Suite offline `ai-service` (`-m "not live and not llm" --strict-markers`) → 0 failed, 0 error. 18/18 mục ở PB-6 có quyết định trong bảng triage. T10 được sửa bằng cách cô lập env, không xfail.
- [ ] (manual — `manual_test_anchor.py`) CI: 1 lượt PR của workflow `ai-service` xanh trên GitHub (URL ghi trong `verification-P4.json`). Live-CI theo VD-8: 1 lượt dispatch từ `main` thành công, và 1 lượt dispatch từ nhánh khác bị từ chối (xác minh RT-07). Mục này có thể hoàn tất sau khi A đóng, nếu VD-8(a) được chọn.

## Test matrix (tóm tắt)

| Tầng | Cái gì | Ở đâu |
|---|---|---|
| Unit | Luật `expected_state`; bộ sinh tất định; Wilson/cluster CI, sàn 60, verdict, hồi quy tripwire; chuẩn hoá giá trị; IoU tập dòng; vị từ invariant; trần chi phí; `approve_card`; exit code; lint rò rỉ; bất biến workflow (`on` parse thành `True`) | `evals/tests/*`, `evals/eval_types/*/tests/*`, `ai-service/tests/*` |
| Integration | Golden → adapter thật → reasoner offline → scorer; `run_idp` → `processing_units`; gate CLI trên repo git tạm (baseline lấy từ base ref); benchmark với client giả; suite chạy với `CI=true` | P1–P4 |
| E2E / live | 1 lời gọi OpenAI smoke; lượt baseline k=5; run CI thật | P3, P4 (manual anchor) |

## Rollback
- Mỗi bước là một commit riêng. Hoàn tác bằng `git revert <range>`, rồi chạy lại regression gate của phase trước.
- P1 chỉ thêm dữ liệu. Revert promote thì khôi phục được 2 manifest; `candidate_decisions.json` vẫn giữ quyết định của người duyệt.
- P2 revert thì mirror và card v1 quay lại (kèm drift CRLF trên Windows). Baseline revert cùng commit.
- P3: `response_model` là thay đổi additive. Có thể tắt live bằng cách xoá environment hoặc disable workflow.
- P4: đưa `ai-service.yml` về placeholder. CODEOWNERS và ruff autofix nằm ở commit riêng.

## Risks

| # | Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|---|
| R1 | Scorer cho PASS giả | Trung × Cao | Test đối nghịch cho mỗi chỉ số; `UNDERPOWERED` không bao giờ là PASS; lỗi setup exit 2; tripwire bắt cả item mới (RT-02); luôn in cận dưới cạnh `PASS(point)` |
| R2 | Hash lệch Windows/Linux vì CRLF | Cao × Cao | Băm theo LF ở `config_integrity`, `build_golden`, `approve_card`; `.gitattributes eol=lf` + xoá rồi checkout lại (PB-13); P1 cấm sửa `*.sha256`; `--check` chạy trên cả hai OS |
| R3 | Golden giả lập lệch phân phối | Cao × Trung | 8 loại hợp đồng, có bản nhiễu; split theo hợp đồng; ghi hạn chế; tập biến thể dùng khi release |
| R4 | Nhãn neo vào output hệ thống, hoặc chỉ một người gán (D-A10) | Trung × Cao | `expected_state` sinh theo luật và commit trước lần chạy reasoner đầu tiên; smoke test không in state; worksheet không có nhãn cũ; báo độ đồng thuận hai nguồn (RT-05) |
| R5 | Mốc duyệt của người làm tắc tiến độ | Cao × Trung | `--draft --card-proposal` chạy được trước HC (RT-06); `UNDERPOWERED` được ghi trung thực |
| R6 | Lộ khoá hoặc vượt chi phí | Thấp × Cao | Khoá chỉ đọc từ env; test vô hiệu `.env` (PB-12); PR không có secret; trần kiểm trước mỗi lời gọi; **trần cứng ở project OpenAI + deployment branch `main`** (RT-07) |
| R7 | Snapshot hoặc giá của model thay đổi | Trung × Trung | Preflight so `response_model`; `pricing.json` có ngày hiệu lực |
| R8 | Triage che lỗi thật | Trung × Cao | Mặc định là **sửa**; skip chỉ dùng cho tài nguyên nằm ngoài repo, có marker và được đếm; T10 sửa bằng cách cô lập env (không xfail); xfail còn lại (nếu có) đặt `strict=True` |
| R9 | P2 quá lớn (~55 file) | Cao × Trung | Chia 4 commit, mỗi commit có gate riêng |
| R10 | Đo trên cây WIP bẩn | Trung × Cao | Commit WIP trước; baseline từ chối `dirty` |
| R11 | Rò rỉ tập test: luật tự khớp câu hỏi thi (PB-11) | Cao × Cao | Task HD không vào mẫu số gate; `test_no_eval_leakage` với allowlist đóng băng; report theo split; tập biến thể khi release; C gỡ luật (VD-6) |
| R12 | Gate hồi quy tự tham chiếu | Trung × Cao | Baseline lấy từ nhánh đích; thay đổi path đã khoá cần label + CODEOWNER (RT-01) |

## Red-team disposition

Nguồn: `reports/from-code-reviewer-to-planner-red-team-goodhart-stats-cisec-feasibility-plan-review-report.md` (verdict REVISE).

| RT | Mức | Disposition | Sửa ở đâu | Lý do |
|---|---|---|---|---|
| RT-01 | High | fixed-in-plan | P2 F2.12 + bước 7 + test `test_pr_updating_baseline_cannot_hide_regression`; P4 F4.1 (`fetch-depth: 0`, `--base-ref`, label) + F4.8 (CODEOWNERS); plan.md "Hợp đồng verdict", HC-5, Acceptance HC-1 chuyển sang manual | Baseline lấy từ nhánh đích; path đã khoá cần label cộng review của CODEOWNER; chữ ký duyệt không còn được gọi là "invariant" |
| RT-02 | High | fixed-in-plan | P2 F2.1 (`diff_regressions` cho tripwire) + test `test_tripwire_new_item_fail_is_regression`; plan.md "Hợp đồng verdict" | Mọi đơn vị FAIL mới ở tripwire đều là hồi quy, kể cả item mới; unit id ổn định cho phía phát ra |
| RT-03 | High | fixed-in-plan | P3 F3.3/F3.4 (`--fail-on-threshold --tripwire-only`, diff tập FAIL tripwire với `ai2_live.baseline.json`); P4 F4.2 truyền cờ; AI2-16 ghi `value_fabricated` offline kém nhạy | Lượt live chạy tay đỏ khi LLM bịa, PR vẫn không bị chặn (giữ đúng VD-2) |
| RT-04a | High | fixed-in-plan | plan.md: Tổng quan, D-A8¹, danh mục chỉ số, PB-11, R11; P1 F1.7 (`--variant-seed`), F1.8 (bỏ task HD khỏi review); P2 F2.6 (bucket `fixture_tuned_legacy`, report theo split, `--golden-dir`), `evals/tests/test_no_eval_leakage.py` | Task HD không vào mẫu số gate; lint chặn luật rò mới; tập biến thể dùng khi release; 21/24 được ghi là bị thổi phồng ở mọi chỗ trích dẫn |
| RT-04b | High | fixed-in-plan (VD-6 đã chốt: phương án (a), VL-12) | plan.md VD-6, "Out of scope và bàn giao" | Người dùng chọn (a): giao việc gỡ luật trong `l0_rules.py` cho C, A cung cấp lint và allowlist phải về rỗng. Gỡ luật là việc chất lượng, kéo theo baseline (D-A13) |
| RT-05 | High | fixed-in-plan | P1 F1.1b (`expected_state_for`), bước 3–4 (commit guideline và catalog trước reasoner, ghi SHA), F1.8 (worksheet không có nhãn cũ; lệnh `agreement`), R-P1; plan.md R4 | Nhãn sinh theo luật và commit trước; smoke test không lộ state; sửa gold sau lần chạy đầu phải ghi nhật ký và qua HC-1 |
| RT-06 | High | fixed-in-plan | P2 F2.8 (`evals/cards/proposed/*.v2.json`), F2.6 (`--card-proposal`, `tau_provisional`), F2.10 (approve chuyển file), bước 4/6/8; `plan-graph.yaml` | Chạy draft được trước HC-3 và không bao giờ ghi baseline, nên agent không cần tự duyệt |
| RT-07a | High | fixed-in-plan | HC-5 (deployment branch `main`, project OpenAI riêng có trần cứng); P4 F4.2 + bước 10 (thử dispatch từ nhánh khác, phải bị từ chối); R6 | Thêm trần phía provider (lớp thứ hai) và giới hạn ref; nếu nhánh khác bị từ chối thì finding hạ xuống Low |
| RT-07b | High | fixed-in-plan (VD-8 đã chốt: chỉ dispatch tay) | plan.md VD-8, Acceptance CI | Người dùng chọn: chỉ `workflow_dispatch`, không lịch; environment `ai2-live` giới hạn deployment branch `main` + trần cứng OpenAI; required reviewer tuỳ chọn. Nghiệm thu live-CI = workflow trên `main` + 1 lượt dispatch tay thành công (VL-14) |
| RT-08 | Medium | fixed-in-plan (VD-1 mở rộng đã chốt: phương án (a), VL-7) | plan.md VD-1; P1 F1.3 (`acceptable_spans` là tập dòng tường minh); P2 F2.4 (IoU tập dòng, chẩn đoán `bbox_consistency`, test cite đúng điều khoản nhưng sai dòng → FAIL) | Người dùng chọn (a): IoU trên tập dòng, τ = 0,5, bbox chỉ chẩn đoán. Vẫn đúng D-A11 (mức span, có ngưỡng IoU), nhưng đổi đơn vị IoU nên cần người dùng xác nhận |
| RT-09 | Medium | fixed-in-plan | P1/P2/P3 TDD (`monkeypatch.delenv("CI")` cho happy path, `setenv` cho kịch bản từ chối); P4 bước 7 chạy thêm với `CI=true` | Test không đỏ riêng trên GitHub; ghi rõ guard `CI` không phải kiểm soát bảo mật |
| RT-10 | Medium | fixed-in-plan | P4 F4.7 + TDD (`wf.get("on", wf.get(True))`, assert khác rỗng, fixture YAML âm) | Test bất biến không còn xanh một cách rỗng |
| RT-11 | Medium | fixed-in-plan | P1 F1.10 (thêm `evals/eval_config.*`), bước 2 (xoá rồi checkout lại; cấm sửa `*.sha256`), Success (hạ claim 11/11: còn đỏ thì chuyển P2); plan.md PB-13, R2 | Bản sửa CRLF có hiệu lực thật; không có đường tắt băm lại sidecar |
| RT-12 | Medium | fixed-in-plan | P3 F3.8 (conftest vô hiệu `load_dotenv` + xoá biến nhạy cảm) + `test_offline_env_is_isolated`, R3-6 nâng lên Trung; P4 T10 sửa bằng `delenv("OCR_DPI")`; plan.md PB-12, R8, bàn giao B | Sửa đúng nguyên nhân gốc thay vì xfail; khoá không lọt vào suite offline |
| RT-13 | Medium | fixed-in-plan | P2 F2.1 (`cluster_bootstrap_ci` theo `contract_id`, nhãn `PASS(point)` kèm cận dưới) + test; AI2-16 ghi n hiệu dụng | Không đổi ngưỡng D-A8 hay D-A9; chỉ báo trung thực độ bất định |
| RT-14 | Medium | fixed-in-plan (VD-7 đã chốt: phương án (a), VL-13) | plan.md VD-7; P1 F1.1 (≥ 15 câu kiểu so sánh); P3 F3.3 (bootstrap theo `question_id` cố định; tập lượt theo VD-7) | Người dùng chọn (a): gate p95 trên lượt `used_llm=true`, n ≥ 60. Chạm cách hiểu câu chữ D-A8 nên cần người dùng chốt |
| RT-15 | Low | accepted-risk | P3 F3.7 (marker `requires_pdf_fixture`); P4 F4.4 (T4–T8 dùng marker, CI summary đếm), bàn giao C (issue có hạn chót) | 5 test PDF skip trên CI vì PDF không commit được (pr-guard); chấp nhận khi `verification-P4.json` liệt kê đúng 5 test này và không có skip nào khác |
| (khác) | – | fixed-in-plan | P4: `git ls-remote` thay cho `gh`; job `evals-offline` có `uv sync` riêng; `__all__`/`noqa` cho `app/tools/jobs.py` trước autofix; README ghi cảnh báo required check với paths filter. P2: test hermetic dùng spy đếm lời gọi. P1: `--check` chỉ so `files[]`, `build` không xoá `approval` | Các điều kiện chấp nhận trong mục "Rủi ro còn lại" của report |
| (khác) | – | fixed-in-plan (VD-9 đã chốt: phương án (a), VL-15) | plan.md VD-9; P2 F2.7 | Người dùng chọn (a): tripwire `fact_value_fabricated` chạy trên fact của cả 95 case (không cần nhãn) |

## Validation Log
- VL-1 | complexity: complex · 4 phases · risk: gate cho PASS giả, dữ liệu chấm | mode `--hard --tdd` | giữ nguyên.
- VL-2 | Áp **`--deep`**: rủi ro chính là gate cho PASS giả, nên mỗi phase cần file inventory, ma trận kịch bản test và dependency map. **Không `--parallel`**: DAG là chuỗi P1→P2→P3→P4; phần duy nhất tách được (triage ở P4) tiết kiệm ít.
- VL-3 | Phase > 8 file: P1 (~15 + dữ liệu), P2 (~55, trong đó 17 file xoá), P3 (~16), P4 (~24 + autofix). Giữ đúng 4 phase theo yêu cầu; P2 chia 4 commit.
- VL-4 | Sửa research: "script trả 0 khi lỗi" và "card bị sửa" đều sai (PB-1, PB-3).
- VL-5 | Lỗi test có sẵn là 16 + 2, không phải 15; T10 có nguyên nhân gốc là `.env` (PB-12).
- VL-6 | Red-team REVISE (30/09): 15 finding được xử lý theo bảng "Red-team disposition". Còn 5 mục chờ người dùng: VD-1 (mở rộng), VD-6, VD-7, VD-8, VD-9.
- VL-7 | VD-1 | chọn (a) IoU trên tập dòng, τ = 0,5 | bbox IoU chỉ chẩn đoán; xem lại khi B/C phát bbox thật.
- VL-8 | VD-2 | chọn (a) PR chặn hồi quy so với baseline nhánh đích + tripwire FAIL mới + lỗi setup; ngưỡng D-A8 luôn in | C bật `enforce_thresholds_in_pr` khi đạt; release B/C bắt buộc `threshold_verdict = PASS`.
- VL-9 | VD-3 | chọn (a) giá trị chỉ tìm trong `answer` | thêm chẩn đoán `value_in_evidence`.
- VL-10 | VD-4 | chọn (a) bỏ mirror `ai2_contract_package`, chấm `run_idp` thật | mở rộng D-A12, người dùng xác nhận.
- VL-11 | VD-5 | **đổi so với khuyến nghị:** chỉ chạy tay, không lịch; giữ trần k=5/k=3, 5 USD và 1000 lời gọi mỗi lượt, 20 USD/tháng | trôi model không tự phát hiện; bù bằng pin snapshot + ghi `response_model` + chạy live trước mỗi release B/C.
- VL-12 | VD-6 | chọn (a) C gỡ luật riêng cho fixture; A giao `test_no_eval_leakage` với allowlist chỉ được giảm | allowlist phải rỗng khi C nghiệm thu.
- VL-13 | VD-7 | chọn (a) p95 chỉ trên lượt `used_llm=true`, n ≥ 60, thiếu thì `UNDERPOWERED` | P1 thêm ≥ 15 câu so sánh.
- VL-14 | VD-8 | **đổi so với khuyến nghị:** chỉ `workflow_dispatch`; environment `ai2-live` giới hạn `main`; required reviewer tuỳ chọn | nghiệm thu live-CI = workflow trên `main` + 1 lượt dispatch tay thành công.
- VL-15 | VD-9 | chọn (a) tripwire `fact_value_fabricated` trên fact của cả 95 case | `processing_state_match` chỉ tính trên GOLDEN.
- VL-16 | Consistency sweep (main, 30/09) | đã gỡ mọi `schedule`/"định kỳ" khỏi phase 3, phase 4 (5 chỗ); không còn "required reviewer bắt buộc"; plan-graph không nhắc lịch.

## Câu hỏi còn mở
1. ~~VD-1..VD-9~~: đã chốt ở bước validate ngày 30/09 (VL-7..VL-15).
2. Snapshot `gpt-4o-mini` có ngày nào còn được phục vụ, và giá hiện hành bao nhiêu (P3 bước 1 probe).
3. GitHub handle của Văn Dũng dùng cho CODEOWNERS (HC-5).
4. Có cập nhật `docs/DOC-06-eval-report.md` trong A hay không; đề xuất để sau.
