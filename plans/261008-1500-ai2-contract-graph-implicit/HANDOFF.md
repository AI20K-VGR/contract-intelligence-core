# Bàn giao — AI2 contract graph luồng 2 (cook đang dở)

Ngày: 2026-10-09 · nhánh `feature/ai2-contract-graph` · người tiếp nhận: agent bất kỳ (Codex, Claude Code…).
Đọc theo thứ tự: file này → `plan.md` (§Quyết định, §Acceptance, §Validation Log VL-8…VL-10) → file phase đang làm.

## 1. Dựng lại môi trường trên máy mới

1. `git fetch origin && git checkout feature/ai2-contract-graph`.
2. **Dữ liệu ngoài git (bắt buộc):** giải nén `contract-graph-pairs-data-20261009.zip` (bàn giao kèm, ~4 MB) sao cho có `<repo>/.harness/state/contract-graph-pairs/{cache,work,dev,heldout,review}`. Thư mục phải bị git bỏ qua: `git check-ignore -q .harness/state/contract-graph-pairs/probe` exit 0 (nếu không, thêm `.harness/` vào `.git/info/exclude`). Kiểm: `uv run --project ai-service --frozen --extra web --extra dev python -m evals.contract_graph.pairs.run verify` ⇒ `verify ok`.
3. `cd ai-service && uv sync --extra web --extra dev --extra kafka --extra openai`.
4. **Bí mật (không commit, không dán vào chat/log):** tạo `ai-service/.env` (đã git-ignore):
   - `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL=https://api.anthropic.com/v1/`, `AI2_CONTRACT_GRAPH_PAIRS_API_KEY=<key Anthropic>`, `AI2_CONTRACT_GRAPH_PAIRS_MODEL=claude-sonnet-5-5` — bộ phân loại (P3/P5). Endpoint này **chưa được probe** `[ASSUMED]`.
   - Người gán nhãn GPT (chỉ cần khi gán nhãn thêm): đặt `AI2_CG_LABELER_BASE_URL/_API_KEY/_MODEL` trong môi trường process (máy cũ lấy từ `AI2_LLM_*` của `.env` core: OpenAI `gpt-4o-mini`). Không thêm fallback trong code.
5. Mốc test (OBSERVED 2026-10-09, trước P3):
   - ai-service (từ `ai-service/`): `uv run --frozen --extra web --extra dev --extra kafka --extra openai pytest -q -p no:cacheprovider` ⇒ **13 failed / 1313 passed / 44 skipped**; 13 lỗi môi trường đã biết: `test_mistral_ocr.py` ×7 (thiếu `mistralai`), thiếu `HD-TONG-HOP.sample.pdf` ×5, `test_p0_contract_baseline` ×1. Lỗi khác = regression. Windows: dùng `--basetemp` ngắn (lỗi `WinError 206`).
   - evals (từ repo root): `uv run --project ai-service --frozen --extra web --extra dev --extra kafka --extra openai python -m pytest -q -p no:cacheprovider evals/contract_graph/tests` ⇒ **145 passed**.
   - ruff: file `ai-service/` chạy từ `ai-service/`; file `evals/` chạy từ root với `--config ai-service/pyproject.toml` (không có config ở root).

## 2. Trạng thái phase

| Phase | Trạng thái | Commit | Ghi chú |
|---|---|---|---|
| P1 bộ nhãn cặp | PASS | `474cfdd`, `0f499b4`, `562575d`, `46e6625` | 21 văn bản (held-out 14 / dev 7), pool 839, nhãn GPT `gpt-4o-mini-2024-07-18`; cắt đuôi trang web (người dùng chốt) |
| P2 ứng viên cấu trúc | PASS | `b0022c8`, `29c4dc1` | `pair_candidates.py` **đóng băng** (`pairs-cand-v1`, `PAIRS_TOP_K=40` — người dùng chốt thay K=10 của quy tắc); S4 31 cặp; mẫu HG-1 181 dòng khoá trong `pairs/manifest.json` |
| P3 bộ phân loại LLM | xem `git log` sau `29c4dc1` và `reports/developer-P3-report.md` nếu có | — | Code + test làm với fake; **đo live BLOCKED** tới khi có key Claude và probe bước 0 |
| P4 tích hợp + lưu trữ | chưa làm | — | `phases/phase-4-integration-storage.md` |
| P5 bake-off | chưa làm | — | cần HG-1 + Claude |

Artifact verify từng phase: `artifacts/verification-P1.json`, `verification-P2.json`.

## 3. Quyết định đã chốt — không đảo lại

- K-a: GPT chỉ gán nhãn, **Claude** phân loại. Không bao giờ cho bộ phân loại chạy bằng GPT; model thực phục vụ phải kiểm bằng `family(served_model)` (fail-closed, mã 2).
- `PAIRS_TOP_K=40`, `CANDIDATES_VERSION=pairs-cand-v1`: không sửa `ai-service/app/pipeline/contract_graph/pair_candidates.py` (P3–P5 chỉ gọi). `extend-heldout` từ chối khi lệch báo cáo.
- **HG-1 do người dùng tự duyệt** (Q5, D13): phiếu `.harness/state/contract-graph-pairs/review/heldout_review.csv`, cột `decision` = `approve|relabel|reject` (+`label_fixed`, `direction_fixed` cho nhãn có hướng). Agent **không** điền phiếu. P5 bước 0 cần phiếu đủ.
- Không chạy bộ phân loại trên held-out trước P5; mọi đọc dữ liệu đóng băng đi qua `manifest.read_split` (verify trước).
- Không nới ngưỡng, không bịa số: thiếu điều kiện ⇒ ghi BLOCKED kèm lý do.
- TDD từng phase: test RED chạy và thấy FAIL trước khi viết module; sau đó cổng regression như §1.5.
- Deviation đã chấp nhận: `pairs/manifest.py` `verify` chấp nhận file S4 trong `extension_s4`; `family()` dùng `o\d+`.

## 4. Việc tiếp theo

1. Xác nhận P3 trong `git log`; nếu dở thì hoàn tất theo `phases/phase-3-llm-pair-classifier.md` (code + test xanh, báo cáo dev ghi BLOCKED).
2. Khi có key: P3 bước 0 probe (một lời gọi thật qua `classifier_client(NineRouterClient(), model)`, họ `anthropic`), rồi đo dev ⇒ `evals/contract_graph/reports/l2-p3-classifier-dev.{json,md}`.
3. P4 theo `phases/phase-4-integration-storage.md` (flag `AI2_CONTRACT_GRAPH_PAIRS_ENABLED` mặc định tắt; flag tắt ⇒ output `run_idp` không đổi một byte — golden luồng 1 không được sửa; migration `0006`).
4. Sau khi người dùng duyệt xong HG-1: P5 theo `phases/phase-5-bakeoff-rerun.md`.
5. Cuối: test độc lập, code review, cập nhật doc (`docs/ai2/AI2-20…`), đồng bộ plan. Push chỉ khi người dùng yêu cầu.

Commit: conventional commit, mỗi message kết thúc bằng dòng trống rồi dòng attribution của công cụ đang dùng. Không commit `.env`, `.harness/state/`, key.
