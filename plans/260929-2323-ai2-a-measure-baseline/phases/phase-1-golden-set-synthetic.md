---
phase: 1
title: "Golden Set Synthetic"
status: pending
plan: 260929-2323-ai2-a-measure-baseline
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Golden Set Synthetic

## Overview
Phase này tạo golden set giả lập tất định (D-A7, D-A11), gồm 8 hợp đồng tiếng Việt G01–G08 (G05 dài từ 55 trang), với tối thiểu 84 câu hỏi, trong đó ≥ 15 câu kiểu so sánh. Dữ liệu ở định dạng `ai1.snapshot.v1`, có bbox cho từng dòng. Nhãn gồm hai loại:
- **Span và giá trị**: có sẵn theo cách dựng, vì bộ sinh biết mỗi giá trị nằm ở dòng nào.
- **Trạng thái kỳ vọng**: sinh theo luật từ `MutationSpec`, và luật được **commit trước khi reasoner chạy lần đầu** (RT-05).

Phase cũng làm công cụ duyệt mù 95 case `UNVERIFIED` cho Văn Dũng (D-A10). Worksheet không hiện nhãn cũ lẫn output của hệ thống. Người duyệt tự điền quyết định, và promote có kiểm tra.

Cuối cùng, phase sửa gốc lỗi CRLF gây `ConfigDriftError` giả trên Windows (PB-3, PB-13).

Không phụ thuộc phase nào. Tiền đề: WIP đã commit. Lý do phải tự sinh dữ liệu: fixture cũ không có hình học dòng (PB-7). 15 task HD **không** vào golden, vì bị rò rỉ tập test (PB-11); P2 chỉ báo chúng như chẩn đoán.

## Dependency map
- **Upstream (chỉ đọc):**
  - `docs/contracts/ai1.snapshot.v1.schema.json`
  - `ai-service/app/pipeline/ai1_snapshot_adapter.py:334` `adapt_ai1_input` (smoke)
  - `ai-service/app/reasoning/stack.py:17` và `ai-service/app/reasoning/query.py:14` (smoke, không xem state)
  - `ai-service/fixtures/eval_suite.py:93` `all_eval_cases` (nguồn worksheet: 65 catalog + 30 SYN)
  - `evals/release_verification.py:60-111` `validate_corpus_separation`
- **Downstream:**
  - P2 đọc `evals/data/golden/**` và `evals/corpus/golden_manifest.json`.
  - P3 đọc cờ `synthetic` trong manifest.
  - B/C dùng `--variant-seed` cho verdict release.
- **Người:** HC-1 (duyệt golden), HC-2 (95 quyết định). Hai việc này không chặn việc đóng P1, nhưng chặn các chỉ số có gate ở P2.

## Requirements
Chức năng:
- **F1.1 Spec + catalog.** 8 hợp đồng:

  | Mã | Loại | Điểm cần có |
  |---|---|---|
  | G01 | dịch vụ bảo trì | phụ lục sửa giá, xung đột thân/phụ lục |
  | G02 | mua bán thiết bị | bảng hàng hoá |
  | G03 | thuê văn phòng | 2 phụ lục |
  | G04 | SaaS | SLA %, phạt % |
  | G05 | thi công | ≥ 55 trang, 5 phụ lục, bảng khối lượng nhiều trang, điều khoản vắt qua trang |
  | G06 | vận chuyển | phụ lục được dẫn chiếu nhưng thiếu |
  | G07 | tư vấn | trùng tên, khác MST |
  | G08 | dịch vụ | bản nhiễu OCR |

  Ràng buộc trên bộ câu hỏi:
  - ≥ 84 câu tổng.
  - Theo trạng thái: ANSWERED ≥ 35, NEEDS_REVIEW ≥ 15, INSUFFICIENT_EVIDENCE ≥ 17, NOT_COMPARABLE ≥ 4.
  - **≥ 15 câu kiểu so sánh**, để đủ lượt LLM cho VD-7.
  - ≥ 20% câu không trả lời được.
  - Câu hỏi diễn đạt theo nhiều cách, không lặp khuôn của task HD.
- **F1.1b Luật trạng thái kỳ vọng** `expected_state_for(question_kind, mutations)` trong `spec.py` (hàm thuần), khớp `docs/code-standards.md:18,20,48`:

  | Tình huống | Trạng thái |
  |---|---|
  | xung đột thân/phụ lục, trùng tên khác MST, sửa đổi chồng lấn | NEEDS_REVIEW |
  | phụ lục thiếu, thông tin không có, câu hỏi quá rộng | INSUFFICIENT_EVIDENCE |
  | so sánh hai đại lượng khác loại | NOT_COMPARABLE |
  | tra cứu một giá trị hoặc điều khoản không xung đột | ANSWERED |

  Không có ngoại lệ gõ tay theo từng câu. Gặp trường hợp luật không phủ thì phải bổ sung luật và guideline, không gán tay.
- **F1.2 Render.** Toạ độ chuẩn hoá [0, 1], 36–42 dòng mỗi trang, làm tròn 4 chữ số. `page_revision_id = <snapshot_id>:p<n>:r1`. Digest sha256 tính trên text LF. Enum viết thường (PB-5). Text chuẩn NFC.
- **F1.3 Gold theo cách dựng (tập dòng, RT-08).**
  - `required_spans`: `{span_id, page_no, line_ids, bbox}`.
  - `acceptable_spans`: **tập dòng tường minh cho từng câu**. Gồm dòng required, dòng tiếp nối của cùng câu văn (nếu câu văn vắt dòng), và span phía bên kia khi có xung đột. **Không** lấy cả điều khoản hay dòng heading. Mỗi acceptable span ≤ 3 dòng.
  - `gold_values`: `{value_id, kind, raw, normalized, span_id}`.
- **F1.4 Mutation có kiểm soát.** Xung đột tiền/ngày/%; phụ lục thiếu; trùng tên khác MST; sửa đổi hiệu lực. G08: mất dấu khoảng 10% dòng không phải gold; ngắt dòng giữa số tiền ở dòng không phải gold.
- **F1.5 Split theo hợp đồng.** dev {G01, G02, G03, G05, G08}, val {G04}, holdout {G06, G07}.
- **F1.6 Manifest** `ai2.golden.synthetic.v1`:
  - `golden_version: "1.0.0"`, `generator_version`, `synthetic: true`, `anonymized: false`;
  - `files[]{path, sha256_lf, contract_id, pages, split}`;
  - `units{...}`;
  - `spec_commit` (SHA commit guideline + catalog, xem bước 4);
  - `approval: null | {approved_by, approved_at, content_sha256}`.
- **F1.7 CLI `python -m evals.golden.build_golden`:**
  - `build`: giữ nguyên `approval` hiện có. Nếu nội dung đổi khi `approval` khác null thì từ chối (exit 2), trừ khi có `--reset-approval`; cờ này đặt `approval` về null.
  - `--check`: chỉ so `files[]` (sha256 LF), không so `approval`. Lệch → 1, lỗi setup → 2.
  - `stats`: thiếu sàn → 1.
  - `approve --by`: do người chạy; có `CI` → 2.
  - `--variant-seed N --out <dir>`: sinh tập biến thể tất định theo seed (đổi tên, số liệu, cách hỏi) vào `evals/results/golden-variant/<N>/`. **Không commit** (RT-04), B/C dùng khi release.
- **F1.8 `evals/scripts/candidate_review.py`:**
  - `worksheet`: 95 mục. Mỗi mục có id, nguồn + sha, tiêu đề/kịch bản/notes, số trang/node, tags. **Không** có nhãn cũ (`expected_state` của `eval_suite.py`) và **không** có output hệ thống (RT-05).
  - `init-decisions`: 95 mục `decision: "PENDING"`, `final_label: null`. Người duyệt tự điền, không có giá trị điền sẵn.
  - `promote --reviewer`: như trước. Từ vựng cho phép: PASS, NEEDS_REVIEW, INSUFFICIENT_EVIDENCE, BLOCKED.
  - `agreement`: sau HC-2, tính tỉ lệ đồng thuận và Cohen's κ giữa `final_label` của người duyệt với nhãn tác giả fixture (sau khi map REVIEW→NEEDS_REVIEW, INSUFFICIENT→INSUFFICIENT_EVIDENCE). Kết quả ghi vào mục hạn chế của AI2-16 (hai nguồn, không đổi D-A10).
- **F1.9 `evals/docs/golden-guideline.vi.md`** (≤ 5 trang):
  - luật trạng thái (F1.1b);
  - quy tắc tập dòng required/acceptable;
  - bảng định dạng giá trị;
  - quy trình duyệt mù;
  - mục "Nhật ký thay đổi nhãn": mọi sửa `expected_state` hay span sau `spec_commit` phải ghi lý do, và HC-1 duyệt;
  - hạn chế D-A10.
- **F1.10 `.gitattributes`:** thêm `evals/cards/* text eol=lf`, `evals/eval_config.* text eol=lf`, `evals/data/golden/** text eol=lf`, `evals/baselines/* text eol=lf`, `evals/corpus/*.json text eol=lf`.

Phi chức năng:
- Chỉ dùng stdlib (`jsonschema` chỉ cho test và `--check`).
- `build` chạy < 30 s.
- Cùng sha trên Windows và Linux.
- Dung lượng ≤ 3 MB `[ASSUMED]`.
- Không có `.pdf` hay `.png`.
- Tên và MST là hư cấu.

## Related Code Files
**Create**
- `evals/golden/__init__.py`
- `evals/golden/spec.py`: dataclass + `expected_state_for`
- `evals/golden/catalog.py`
- `evals/golden/render_snapshot.py`
- `evals/golden/build_golden.py`
- `evals/data/golden/manifest.json`, `evals/data/golden/questions.json`, `evals/data/golden/snapshots/G01.json` … `G08.json` (sinh tự động)
- `evals/docs/golden-guideline.vi.md`
- `evals/scripts/candidate_review.py`
- `evals/corpus/candidate_review_worksheet.md` (sinh tự động), `evals/corpus/candidate_decisions.json` (template)
- `evals/tests/test_golden_generator.py`, `evals/tests/test_golden_pipeline_smoke.py`, `evals/tests/test_candidate_review.py`

**Modify**
- `.gitattributes`
- `evals/corpus/golden_manifest.json`, `evals/corpus/candidate_manifest.json` (chỉ sửa qua `promote` do Văn Dũng chạy)

**Delete**: không có. **Cấm** sửa `evals/**/*.sha256` trong P1 (RT-11).

## File inventory

| File | Hành động | Cỡ | Tác động test |
|---|---|---|---|
| `evals/golden/spec.py` | C | ~160 dòng (thêm luật) | `test_expected_state_rules` |
| `evals/golden/catalog.py` | C | ~650 dòng | mọi test golden |
| `evals/golden/render_snapshot.py` | C | ~250 dòng | schema, span, determinism |
| `evals/golden/build_golden.py` | C | ~240 dòng | check/stats/approve/variant |
| `evals/data/golden/**` | C (sinh) | ~2–3 MB | hash, unit floor |
| `evals/scripts/candidate_review.py` | C | ~260 dòng | worksheet/promote/agreement |
| `evals/corpus/candidate_*` | C | ~50 KB | 95 mục |
| `evals/docs/golden-guideline.vi.md` | C | ≤ 5 trang | — |
| 3 file test | C | ~550 dòng | RED trước |
| `.gitattributes` | M | +5 dòng | 2 test mutation CRLF |
| `golden_manifest.json`, `candidate_manifest.json` | M (HC-2) | — | `validate_corpus_separation` |

## Implementation Steps
1. **Tiền đề.** Ghi `git rev-parse HEAD`. Kiểm `git status --porcelain -- ai-service evals`; có thay đổi thì dừng và báo.
2. **Sửa gốc CRLF (PB-3, PB-13).**
   - Thêm 5 luật vào `.gitattributes`.
   - Nếu `git status --porcelain -- evals/cards evals/eval_config.json evals/eval_config.sha256` rỗng: **xoá** các file đó rồi `git checkout -- evals/cards evals/eval_config.json evals/eval_config.sha256`. Chỉ `checkout` thì git bỏ qua file đã sạch theo stat.
   - Kiểm `git ls-files --eol evals/cards evals/eval_config.json` phải báo `w/lf`.
   - **Không** được sửa `*.sha256`.
   - Chạy `$PY -m pytest -q -p no:cacheprovider evals/tests`. Nếu vẫn đỏ vì `ConfigDriftError`, ghi vào `verification-P1.json`; P2 (F2.9) sẽ xử lý.
   - Lưu ý: từ đây tới P2, eval mirror có thể xanh giả. **Không dùng con số đó.**
3. **Guideline + luật trước tiên (RT-05).** Viết `evals/docs/golden-guideline.vi.md` và `spec.py` (có `expected_state_for`), rồi viết `test_expected_state_rules`, RED → GREEN.
4. **Catalog + nhãn trước reasoner.** Viết `catalog.py` (G01–G08, 84+ câu, `expected_state` lấy từ luật) và `render_snapshot.py` + `build_golden.py build`. Commit `feat(ai): spec golden + guideline (trước lần chạy hệ thống đầu tiên)`, ghi SHA vào `manifest.spec_commit` và `verification-P1.json`. **Chưa có lần chạy reasoner nào trước commit này.**
5. **RED còn lại.** Viết `test_golden_generator.py`, `test_golden_pipeline_smoke.py`, `test_candidate_review.py`.
6. **Smoke.** Chạy adapter + reasoner cho 8 snapshot. Smoke chỉ kiểm không lỗi và gold định vị được; **không in, không assert state** so với gold. Nếu adapter tách/gộp dòng khác spec thì chỉ sửa **layout render**. Muốn sửa `expected_state` hay span thì phải ghi vào "Nhật ký thay đổi nhãn", và việc đó cần HC-1.
7. `build_golden --check`, `stats`, rồi `--variant-seed 1 --out evals/results/golden-variant/1` (không commit).
8. `candidate_review.py`: `worksheet` + `init-decisions` sinh 2 file. `promote` và `agreement` chỉ chạy trên bản sao trong test.
9. Lint các file của phase (`cd ai-service; .venv/Scripts/ruff.exe check <các file .py của P1 ở plan-graph, tiền tố ../>`), chạy regression gate, commit.
10. **Bàn giao HC-1 và HC-2.** Agent **không** tự chạy `approve` hay `promote` trên file thật.

## TDD

### Tests Before (RED)
Mọi test happy-path gọi `monkeypatch.delenv("CI", raising=False)`; test từ chối gọi `monkeypatch.setenv("CI", "true")` (RT-09).

- [ ] `test_expected_state_rules`: mỗi loại mutation/câu hỏi cho đúng trạng thái; loại lạ → raise (không có mặc định).
- [ ] `test_catalog_states_come_from_rules`: mọi câu trong catalog có `expected_state == expected_state_for(...)`, không có override.
- [ ] `test_build_is_deterministic` và `test_manifest_hash_is_lf_normalized`.
- [ ] `test_check_ignores_approval_and_build_preserves_approval`: `--check` bỏ qua `approval`; `build` khi nội dung đổi và `approval` khác null → exit 2, trừ khi có `--reset-approval`.
- [ ] `test_snapshots_validate_against_schema`: 8/8 hợp lệ.
- [ ] `test_gold_spans_resolve`: `line_ids` tồn tại; bbox = hợp các dòng; required ⊆ acceptable; mỗi acceptable span ≤ 3 dòng và không chứa heading điều khoản.
- [ ] `test_gold_values_inside_span_text`.
- [ ] `test_unit_floors`: câu ≥ 60; so sánh ≥ 15; required ≥ 60; value ≥ 60; không trả lời được ≥ 20%; trang ≥ 55; tổng ≤ 3 MB.
- [ ] `test_split_is_by_contract`, `test_all_entries_synthetic_and_no_binary_assets`.
- [ ] `test_variant_seed_is_deterministic_and_differs`: cùng seed → cùng byte; khác seed hoặc khác bản commit → câu hỏi và giá trị khác nhau.
- [ ] `test_golden_pipeline_smoke`: 8/8 adapt được, mỗi hợp đồng có ≥ 1 node CLAUSE, `line_ids` gold có trong `line_texts`, reasoner không lỗi. Test **không** so state với gold.
- [ ] `test_worksheet_is_blind`: 95 mục; không chứa nhãn cũ (so với `eval_suite` expected_state theo từng id); sinh ra mà không nạp `app.pipeline.idp` hay `app.reasoning.stack`.
- [ ] `test_decisions_template_has_no_prefill`: `final_label` null ở cả 95 mục.
- [ ] `test_promote_requires_reviewer_and_basis`, `test_promote_moves_is_idempotent_and_keeps_separation`, `test_approve_and_promote_refuse_in_ci`.
- [ ] `test_agreement_reports_kappa`: nhãn giả lập → κ và tỉ lệ đồng thuận đúng.

### Implement
Theo bước 3–8.

### Tests After
- [ ] `stats` và `--check` exit 0.

### Regression Gate
- `$PY -m pytest -q -p no:cacheprovider evals/tests`: test mới xanh. Test có sẵn chỉ được phép fail trong 2 test mutation CRLF, và chỉ khi bước 2 không gỡ được (khi đó ghi lại và chuyển P2).
- `$PY -m pytest -q -p no:cacheprovider --import-mode=importlib evals/eval_types`: không tệ hơn trước phase.
- `cd ai-service; .venv/Scripts/python.exe -m pytest -q -p no:cacheprovider -m "not live" tests/test_reasoning.py tests/test_catalog.py` → xanh.

## Test scenario matrix

| Mức | Kịch bản | Test |
|---|---|---|
| Critical | Nhãn trạng thái neo vào output hệ thống | `test_expected_state_rules`, `test_catalog_states_come_from_rules`, commit spec trước reasoner (SHA), smoke không so state |
| Critical | Sha lệch giữa OS | `test_build_is_deterministic`, `test_manifest_hash_is_lf_normalized` |
| Critical | Span gold không định vị được sau adapter | `test_golden_pipeline_smoke` |
| Critical | Worksheet lộ nhãn cũ hoặc output | `test_worksheet_is_blind`, `test_decisions_template_has_no_prefill` |
| Critical | Agent tự duyệt hoặc tự promote | `test_promote_requires_reviewer_and_basis`, `test_approve_and_promote_refuse_in_ci`; bằng chứng HC là SHA commit của Văn Dũng |
| High | `acceptable_spans` quá rộng, khiến mọi dòng trong điều khoản đều đúng | `test_gold_spans_resolve` (≤ 3 dòng, không heading) |
| High | Golden công khai bị tối ưu theo | `test_variant_seed_is_deterministic_and_differs`; lint rò rỉ ở P2 |
| High | Sai schema, thiếu sàn, rò rỉ giữa split | các test tương ứng |
| Medium | NFD/NFC, nhiễu của G08, dung lượng | `test_gold_values_inside_span_text`, `test_unit_floors` |

## Success Criteria
- [ ] (invariant) `$PY -m evals.golden.build_golden --check` exit 0 trên Windows; P4 kiểm lại trên Linux.
- [ ] (test) `stats`: câu ≥ 60 (mục tiêu 84), so sánh ≥ 15, required ≥ 60, value ≥ 60, không trả lời được ≥ 20%, trang lớn nhất ≥ 55.
- [ ] (invariant) `manifest.spec_commit` là tổ tiên của mọi commit có chạy reasoner trong phase. Kiểm bằng `git merge-base --is-ancestor <spec_commit> HEAD`, và SHA được ghi trong verification.
- [ ] (invariant) 8/8 snapshot hợp lệ schema; 0 file `.pdf`/`.png`.
- [ ] (test) Worksheet có 95/95 mục và không lộ nhãn; template có 95 mục `PENDING`, không điền sẵn.
- [ ] (test) `evals/tests`: test mới xanh. Hai test mutation CRLF xanh, hoặc được ghi lại để P2 xử lý.
- [ ] (manual — `manual_test_anchor.py`) HC-1: Văn Dũng chạy `approve --by "Văn Dũng"` trong commit của chính mình; SHA ghi vào verification. Theo dõi ở acceptance toàn plan.
- [ ] (manual — `manual_test_anchor.py`) HC-2: Văn Dũng điền 95 quyết định, rồi chạy `promote --reviewer "Văn Dũng"` và `agreement`. Theo dõi ở acceptance toàn plan.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| Nhãn neo vào hệ thống (RT-05) | Trung × Cao | Luật + commit trước; smoke không in state; nhật ký thay đổi nhãn cần HC-1 |
| Không tất định giữa OS | Trung × Cao | Băm LF, `sort_keys`, làm tròn, timestamp cố định |
| Bản sửa CRLF không có hiệu lực (RT-11) | Trung × Trung | Xoá rồi checkout lại, kiểm `git ls-files --eol`; cấm sửa sha; chuyển P2 nếu còn đỏ |
| Adapter khác spec | Trung × Cao | Chỉ sửa layout; nhật ký nhãn |
| Golden quá dễ hoặc bị tối ưu theo | Cao × Trung | Diễn đạt đa dạng; tập biến thể theo seed; lint rò rỉ (P2); bản ẩn danh về sau |
| HC-2 kéo dài (95 mục, ~3–5 giờ) | Cao × Trung | Không chặn P2/P3; thiếu thì báo `UNDERPOWERED` |
