# AI2 proposal — architect findings (checkpoint)

**Phạm vi:** chỉ đánh giá kiến trúc proposal AI2 hiện tại ở các mặt eval `contract_package`/`grounded_query`, pipeline mirror, scorer/runner, card/hash, CI, AI1→AI2 handoff và mở rộng contract/annex. Không sửa production.

## Findings sớm

### ARCH-C01 — Lệnh CI hiện tại không collect được hai domain cùng lúc (Critical)

Workflow gọi pytest với cả hai thư mục test trong cùng một invocation. Hai domain dùng cùng basename (`test_config_conformance.py`, `test_mirror_parity.py`, `test_scorer.py`) và không phải package test riêng, nên pytest đã lỗi `import file mismatch` khi collection. Đây là lỗi gate trực tiếp: job `eval-contract-tests` không đạt được tới các assertion.

**Bằng chứng quan sát:** lệnh `ai-service/.venv/Scripts/python.exe -m pytest -q evals/eval_types/ai2_contract_package/tests evals/eval_types/ai2_grounded_query/tests --basetemp tmp/architect-ai2-evals-20260923` trả `3 errors during collection` cho ba basename trùng. Workflow gọi đúng hai path đó tại `evals/ci/production-evals.yml:38-42`.

### ARCH-H01 — Parity mirror có thể không chạy trong CI (High)

`test_mirror_parity.py` thêm repository root vào `sys.path` rồi import module production từ card (`app.pipeline...`), nhưng production code nằm dưới `ai-service/app`; workflow chỉ cài dependencies và chạy pytest, không đặt `ai-service` vào import path. Khi import thất bại, test được đánh dấu skip; chính test ghi rõ SKIP không phải PASS. Vì vậy CI có thể xanh trong khi mirror không hề được đối chiếu với production.

**Bằng chứng:** `evals/eval_types/ai2_contract_package/tests/test_mirror_parity.py:32-45,63-95`; `evals/eval_types/ai2_grounded_query/tests/test_mirror_parity.py:32-49,63-95`; `evals/ci/production-evals.yml:29-42`.

### ARCH-H01 — Gate production eval hiện score mirror, không score production (High)

Runner production chọn `pipeline_mirror.run_pipeline` trực tiếp khi không có subprocess contract; nó không gọi `production_entry`. Production entry chỉ xuất hiện trong parity test. Probe chạy cả hai CLI cho kết quả `MATURITY SCORE: 100.0%`, `P0 GATE: PASS`, nhưng đó là kết quả của mirror symbolic. Vì parity hiện bị lỗi/skip, release gate có thể xanh dù production pipeline đã regress.

**Bằng chứng quan sát:** `evals/eval_types/ai2_contract_package/runner.py:468-484,515-562`; `evals/eval_types/ai2_grounded_query/runner.py:460-476,515-554`; kết quả CLI ngày 2026-09-23: cả hai domain 100.0%/PASS. Parity contract skip tại `evals/eval_types/ai2_contract_package/tests/test_mirror_parity.py:98-108`; grounded query skip do `app/reasoning/stack.py` không có `FourLayerReasoner.run` tại test environment.

### ARCH-H01 — Một thay đổi logic phải duy trì hai implementation độc lập (High)

Mirror bị ràng buộc phải là dependency-free và “IDENTICAL” với production, đồng thời docstring yêu cầu mọi thay đổi pipeline phải copy sang mirror. Đây là coupling thủ công, không có cơ chế sinh/kiểm tra coverage theo branch ngoài case matrix. Nếu parity bị skip như finding trên, drift sẽ trở thành silent false confidence; khi production mở rộng profile/annex, chi phí nhân đôi tăng theo số domain và nhánh logic.

**Bằng chứng:** `evals/eval_types/ai2_contract_package/pipeline_mirror.py:1-21`; `evals/eval_types/ai2_grounded_query/pipeline_mirror.py:1-21`; `evals/eval_types/ai2_contract_package/tests/test_mirror_parity.py:98-113`.

### ARCH-H01 — Card case matrix và ground truth runner không cùng một contract (High)

Runner production đọc `ground_truth.json` và sample files; nó không lấy `case_matrix` từ strategy card để dispatch hoặc assert coverage. Ngược lại, parity test lấy `case_matrix` từ card, nhưng lại skip mọi contract case không có `snapshot_id`. Vì vậy card có 25/20 case symbolic còn production score lần lượt 10/20 ground-truth items; không có invariant buộc hai tập này phải bao phủ cùng surface. Đây là coupling sai hướng giữa approval artifact và dữ liệu thực thi, làm denominator/case coverage khó audit.

**Bằng chứng:** card `evals/cards/ai2_contract_package.json:1`, `evals/cards/ai2_grounded_query.json:1`; runner `evals/eval_types/ai2_contract_package/runner.py:486-549,561-562`; runner query `evals/eval_types/ai2_grounded_query/runner.py:478-541,553-554`; parity skip `evals/eval_types/ai2_contract_package/tests/test_mirror_parity.py:98-108`.

### ARCH-M01 — Dữ liệu trống/answer null có thể trở thành `SKIP`, làm denominator không rõ (Medium)

Runner coi ground-truth `null` hoặc chuỗi rỗng và extracted null là `SKIP`, rồi `case_passed` chỉ fail trên `MISS`/`MISMATCH`. Trong grounded-query production output, hai field `answer: null` ở `egress_block` và `lifecycle_block` được in là `SKIP` nhưng case vẫn PASS. Đây có thể là chủ ý cho “không được trả answer”, nhưng cần semantics riêng `EXPECTED_ABSENT`/negative assertion; nếu không, scorer không phân biệt “đúng là không có output” với “không có expected value để score”.

**Bằng chứng quan sát:** output `query-eval` ngày 2026-09-23 in `[SKIP] answer` cho `egress_block.json` và `lifecycle_block.json` nhưng `OVERALL: PASS`; logic tại `evals/eval_types/ai2_grounded_query/runner.py:219-231,528-551`.

### ARCH-M01 — Card/hash đang có hai nguồn sự thật theo domain (Medium)

`ai2_contract_package` có card riêng nhưng `config_integrity.py` lại hash/đọc `evals/eval_config.json`; `ai2_grounded_query` hash/đọc `cards/ai2_grounded_query.json`. Hiện tại `cards/ai2_contract_package.json` trùng byte với `eval_config.json`, nhưng đó là trạng thái trùng lặp chứ chưa phải invariant được kiểm tra. Một sửa card contract mà không sửa `eval_config.json` có thể không ảnh hưởng runner; sửa ngược lại có thể làm card domain stale. Cách này làm provenance approval và cache scorer khó mở rộng thành registry nhiều eval surface.

**Bằng chứng:** `evals/eval_types/ai2_contract_package/config_integrity.py:32-67`; `evals/eval_types/ai2_grounded_query/config_integrity.py:32-73`; `evals/cards/ai2_contract_package.json:1`; `evals/eval_config.json:1`; `evals/cards/ai2_grounded_query.json:1`.

### ARCH-M01 — Scorer/runner hiện phân domain bằng copy, chưa có abstraction chung (Medium)

Hai domain lặp runner, scorer, config loader và CLI; mỗi domain có `DOMAIN_CONFIG`, normalizer/mask registry và p0 rules riêng. Điều này phù hợp để bootstrap hai surface, nhưng chưa tạo một domain contract rõ ràng cho việc thêm loại hợp đồng/phụ lục hoặc thêm eval surface. Mọi domain mới sẽ sao chép glue, tăng nguy cơ lệch exit code, hash semantics, report schema và mutation coverage.

**Bằng chứng:** `evals/eval_types/ai2_contract_package/runner.py:1-20,34-40`; `evals/eval_types/ai2_grounded_query/runner.py:1-20,34-40`; `evals/scripts/run_production_evals.py:28-90`; `evals/scripts/run_grounded_query_evals.py:10-64`.

### ARCH-H01 — Processing request giới hạn một dossier ở tối đa 6 member (High)

Canonical request/schema và Pydantic model đều khóa `snapshots`, `snapshot_identities`, `dossier_members` ở `maxItems=6`. Đây là giới hạn tài liệu, không phải giới hạn sáu loại profile. Trong khi mục tiêu mở rộng nói về nhiều annex và tài liệu còn có scenario `1 contract + 12 annex`; nếu không có batching/partitioning contract rõ ràng, request v1 không biểu diễn được dossier lớn. Chia request làm nhiều phần cũng có nguy cơ phá cross-annex relation, denominator và idempotency nếu không có parent dossier/run identity.

**Bằng chứng:** `docs/contracts/be.ai2.processing.request.v1.schema.json:76-81`; `ai-service/app/contracts/wire.py:97-112`; `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:22-38`; `docs/ai2/AI2-06-implementation-gap.vi.md:90-97`.

## Tạm kết kiến trúc

Proposal có boundary đúng hướng: canonical `ai1.snapshot.v1` và processing request tách nhau, raw evidence bất biến, relation mặc định `INDEPENDENT`, và profile contract-type được đặt ở Phase 1. Tuy nhiên, trước khi coi eval/CI là release gate đáng tin, cần xác minh parity thật sự chạy và hợp nhất nguồn card/hash; nếu không, scorer có thể đo mirror hoặc config khác với artifact đã được phê duyệt.
