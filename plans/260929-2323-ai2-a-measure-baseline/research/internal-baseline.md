# Research nội bộ: hạ tầng đo lường AI2 hiện có (probe 29/09/2026)

Mọi dòng dưới đây là **OBSERVED**: đã chạy lệnh thật hoặc đọc file cụ thể trong phiên lập kế hoạch. Nhãn `[ASSUMED]` đánh dấu chỗ chưa kiểm chứng.

## 1. Khung eval `evals/` có sẵn nhưng đang hỏng

| Hạng mục | Hiện trạng | Bằng chứng |
|---|---|---|
| Hai domain | `ai2_contract_package` (trích xuất, structure, relation) và `ai2_grounded_query` (hỏi đáp có citation) | `evals/docs/production-eval-setup.md:147-152` |
| Test domain | **Lỗi collection** ở cả hai domain: `ConfigDriftError: eval_config.json hash mismatch`. **Nguyên nhân thật (OBSERVED 30/09):** card **không** bị sửa. File được lưu trong git bằng LF, nhưng Windows checkout ra CRLF (`core.autocrlf=true`, `git ls-files --eol` → `i/lf w/crlf`), còn `config_integrity.py:64-66` hash byte thô. Bỏ `\r` thì cả `evals/cards/ai2_grounded_query.json` lẫn `evals/eval_config.json` đều khớp đúng hash đã duyệt. Chỉ lỗi trên Windows; CI Linux không gặp. Sửa: `.gitattributes` ép `eol=lf` cho card/sidecar, hoặc hash sau khi chuẩn hoá xuống dòng | `pytest --import-mode=importlib evals/eval_types/*/tests` → `2 errors during collection` mỗi domain; so hash raw với hash LF |
| Script chấm | `run_production_evals.py` và `run_grounded_query_evals.py` dừng ở cùng lỗi hash, **nhưng exit code vẫn 0** | chạy theo đúng lệnh trong `production-eval-setup.md:169-174` |
| `evals/tests` | 9 pass, **2 fail** (`test_mutation_mapping_is_explicit_and_kills_each_rule`, `test_mutation_noop_is_not_counted_as_killed`) | `pytest evals/tests` |
| Golden manifest | `evals/corpus/golden_manifest.json`: **0 case** (`"Empty until a reviewer promotes cases"`) | đọc file |
| Candidate manifest | `evals/corpus/candidate_manifest.json`: 95 case, **tất cả `UNVERIFIED`**, `approved = 0` | đọc file |
| Ground truth `grounded_query` | `production_fixtures/ground_truth.json` không có mục nào khớp `"id"`/`"case_id"` (grep đếm 0) `[ASSUMED: có thể dùng khoá khác; cần mở file]` | grep |
| Scorer field | `evals/workflow_gate.py:55-104`: so khớp chính xác theo field, **bỏ qua nhãn chưa `approved`**, trả `denominator/covered/passed` riêng | đọc code |
| LLM judge | Có (`judge_runner.py`, `judge_rubric.md`), **chỉ advisory**, không đổi exit code | `run_production_evals.py:9`, `run_grounded_query_evals.py:58` |
| Card đã duyệt | `evals/cards/ai2_contract_package.json`, `ai2_grounded_query.json`, `approved_by: user-approved`, `2026-09-23` | đọc file |

### Lỗi thiết kế: eval hỏi đáp chấm bản sao, không chấm pipeline thật

`evals/eval_types/ai2_grounded_query/pipeline_mirror.py` là **bản sao viết tay** của `ai-service/app/reasoning/stack.py`, với quy tắc *"every pipeline-logic change in stack.py MUST be mirrored here"*. Lý do được ghi trong file: `stack.py` "depends on … API keys, database connections".

Lý do đó **không còn đúng**. Benchmark ngày 29/09 đã chạy `FourLayerReasoner` thật trong process, không cần API key (L0/L1/L3 chạy thuần tất định; LLM là tuỳ chọn). Trong khi đó `stack.py` và `l1_retrieval.py` vừa thay đổi (neo, lọc chủ đề, L0 luôn chạy), nên bản sao **gần như chắc chắn đã lệch** `[ASSUMED: parity test không chạy được do lỗi hash]`. Một eval chấm bản sao lệch sẽ cho điểm không phản ánh hệ thống đang chạy.

## 2. CI

- `.github/workflows/ai-service.yml` chỉ có bước `echo "no CI defined for ai-service yet"`, tức **không có gate nào** cho `ai-service`.
- `evals/ci/production-evals.yml` là template (chưa nằm trong `.github/workflows/`). Nó cài `ai-service/requirements.txt`, nhưng **file này không tồn tại**; dự án dùng `pyproject.toml` + `uv.lock`.
- `ai-service/pyproject.toml` **không đăng ký marker** `live`/`llm` (grep rỗng), nên pytest cảnh báo `PytestUnknownMarkWarning`, và `-m "not live"` trong tài liệu code-standards dựa trên marker chưa đăng ký.

## 3. Bộ test của ai-service (baseline sau các sửa ngày 29/09, chưa commit)

- `pytest tests --ignore tests/unit/test_kafka_idp_worker.py --ignore tests/unit/test_production_query.py`: **817 passed, 15 failed, 11 skipped**.
- 15 test fail đều có từ trước:
  - `test_mistral_ocr` (7), `test_structure_reconstruction` (3), `test_ingest` (1), `test_p0_contract_baseline` (1), `test_kafka_contract_compat` (1);
  - `test_hd_gold` (1): thiếu `fixtures/contracts/HD-TONG-HOP.sample.pdf`;
  - `test_core::test_schema_and_config` (1): chỉ fail khi chạy cả suite.
- 2 file lỗi collection có từ trước:
  - `test_kafka_idp_worker.py`: thiếu `aiokafka`;
  - `test_production_query.py`: import `_answer_language_instruction`, hàm không tồn tại ở HEAD.
- Test live `-m "llm and live"`: 3/3 pass khi nạp `.env` thủ công. pytest **không tự nạp** `.env`.

## 4. Dữ liệu có thể dùng làm golden set

| Nguồn | Số lượng | Ghi chú |
|---|---|---|
| `ai-service/fixtures/catalog.py` (`BUILDERS`) | 65 case (6 HAPPY, 56 EC, `HD-TONG-HOP`, `SALE-BRD-07`, `SERVICE-BRD-08`) | Dựng bằng code, đều là dữ liệu giả; phần lớn 1–20 node; lớn nhất `HD-TONG-HOP` 71 node; `EC-001` 62 trang nhưng 22 node |
| `ai-service/fixtures/reasoning/hd_tong_hop_tasks.json` | 15 câu hỏi có `expected_state` | Dùng trong benchmark |
| `ai-service/fixtures/contracts/*.md` | `HD-TONG-HOP.vi.md`, `AI2-TEST-MASTER.body/annexes.md`, `SALE-BRD.vi.md`, `demo-xung-dot/`, `demo-tu-mau-thuan/` | Văn bản hợp đồng giả lập; có thể là nguồn cho hợp đồng dài |
| `docs/contracts/examples/ai1.snapshot.v1.*.example.json` | 2 | **Trang trống** (`PAGE_BLANK_VERIFIED`), không dùng được để chấm nội dung |
| `ai-service/tests/test_clause_compare.py` (`CONTRACT_PAGES`, `ANNEX_PAGES`) | 1 hồ sơ 2 file | Có nội dung thật, cố ý mâu thuẫn (1.286.400.000 và 1.586.400.000) |
| `ai-service/fixtures/eval_inputs/snapshots/*.v1.json` | 6 snapshot v1 nhỏ (≤ 1,9 KB) | full, relation-multi-hop, low-quality, partial-no-geometry, no-table, failed-page |

## 5. Benchmark đã chạy trong phiên (có thể đưa vào repo)

Script trong thư mục tạm của phiên, **chưa có trong repo**:
- `bench.py`: xử lý hồ sơ trên 65 case, có và không có LLM; query 27 câu, lặp 3 lần với câu có L2.
- `bench_ctrl.py`: đối chứng có/không vector.
- `restart_e2e.py`: uvicorn thật, khởi động lại, mất volume, gửi lại.
- `draft_probe.py`, `ctx_probe.py`, `tax_probe.py`.

Số đo mới nhất (`gpt-4o-mini`, 29/09):

| Hạng mục | Kết quả |
|---|---|
| Xử lý hồ sơ | 9/65 hồ sơ gọi LLM, 16 lần gọi, p50 1,6 giây, p95 4,0 giây, 0 lỗi |
| Hỏi đáp | 24/27 câu không cần LLM; 3 câu dùng L2, 9 lần chạy, 0 draft bị loại; prompt p50 2.600 token, max 2.807; latency LLM p50 3,0 giây, p95 6,7 giây |
| Đúng trạng thái kỳ vọng | **21/24 (87,5%)**, dưới ngưỡng 95% đã chốt |
| Ổn định | 3/3 câu cho cùng trạng thái qua 3 lần chạy |

## 6. Kết luận xếp hạng (cho phạm vi A)

1. **Sửa khung eval có sẵn, không viết mới.** Scorer field-level, tách `denominator/covered/passed`, card đã duyệt, judge chỉ advisory: tất cả đều đúng với code-standards (`docs/code-standards.md:42-43`). Việc cần làm: sửa lỗi hash (duyệt lại card theo quy trình bootstrap), sửa 2 test mutation, thêm golden case.
2. **Bỏ `pipeline_mirror`, chấm pipeline thật.** Pipeline thật đã chạy được không cần key. Giữ bản sao là một nguồn lệch vĩnh viễn.
3. **Đưa script benchmark của phiên vào repo** (`ai-service/scripts/` hoặc `evals/scripts/`), dùng chung định dạng báo cáo với scorer.
4. **CI:** đưa template vào `.github/workflows/`, sửa bước cài đặt sang `uv sync`, đăng ký marker `live`/`llm`, và nạp `.env` qua `conftest.py` cho chế độ live.
5. **Các lỗi test có sẵn từ trước** (15 fail + 2 lỗi collection) phải được **phân loại** trước khi CI thành gate: sửa, đánh dấu `xfail` có lý do, hoặc tách khỏi gate. Không được tắt test cho CI xanh.

## Câu hỏi còn mở

- Ai có quyền duyệt card eval và nâng case lên golden (`approved=true`)? Quy trình "re-run bootstrap" cần người duyệt.
- Có giữ domain `ai2_contract_package` trong gate PR không, hay chỉ `ai2_grounded_query`?
- Ngưỡng hiện tại trong card khác ngưỡng mới (≥ 95%, 0 bịa, 100% citation). Duyệt lại card là thay đổi có chủ đích, cần ghi lý do.
