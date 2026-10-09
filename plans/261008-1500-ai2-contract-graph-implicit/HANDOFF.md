# Bàn giao — AI2 contract graph luồng 2 (cook đang dở)

Ngày: 2026-10-09 · nhánh `feature/ai2-contract-graph` · người tiếp nhận: agent bất kỳ (Codex, Claude Code…).
Đọc theo thứ tự: file này → `plan.md` (§Quyết định, §Acceptance, §Validation Log VL-8…VL-10) → file phase đang làm.

## 1. Dựng lại môi trường trên máy mới

1. `git fetch origin && git checkout feature/ai2-contract-graph`.
2. **Dữ liệu ngoài git (bắt buộc):** giải nén `contract-graph-pairs-data-20261009.zip` (bàn giao kèm, ~4 MB) sao cho có `<repo>/.harness/state/contract-graph-pairs/{cache,work,dev,heldout,review}`. Thư mục phải bị git bỏ qua: `git check-ignore -q .harness/state/contract-graph-pairs/probe` exit 0 (nếu không, thêm `.harness/` vào `.git/info/exclude`). Kiểm: `uv run --project ai-service --frozen --extra web --extra dev python -m evals.contract_graph.pairs.run verify` ⇒ `verify ok`.
3. `cd ai-service && uv sync --extra web --extra dev --extra kafka --extra openai`.
4. **Bí mật (không commit, không dán vào chat/log):** tạo `ai-service/.env` (đã git-ignore):
   - Dedicated classifier endpoint/model đã được đặt trong ai-service/.env (không commit, không dán key). Snapshot Claude trước đó superseded vì response rỗng; snapshot cuối dùng cx/gpt-6-sol, phục vụ gpt-6-sol, họ openai.
   - Người gán nhãn GPT (chỉ cần khi gán nhãn thêm): đặt `AI2_CG_LABELER_BASE_URL/_API_KEY/_MODEL` trong môi trường process (máy cũ lấy từ `AI2_LLM_*` của `.env` core: OpenAI `gpt-4o-mini`). Không thêm fallback trong code.
5. Mốc test sau P5 (2026-10-09): ai-service full ⇒ **13 failed / 1492 passed / 41 skipped**; đúng 13 lỗi môi trường đã biết: `test_mistral_ocr.py` ×7 (thiếu `mistralai`), thiếu `HD-TONG-HOP.sample.pdf` ×5, `test_p0_contract_baseline` ×1. Evals contract graph ⇒ **219 passed**; focused P5/client ⇒ **62 passed**; targeted Ruff sạch. Windows: dùng `--basetemp` ngắn (lỗi `WinError 206`).
   - ruff: file `ai-service/` chạy từ `ai-service/`; file `evals/` chạy từ root với `--config ai-service/pyproject.toml` (không có config ở root).

## 2. Trạng thái phase

| Phase | Trạng thái | Commit | Ghi chú |
|---|---|---|---|
| P1 bộ nhãn cặp | PASS | `474cfdd`, `0f499b4`, `562575d`, `46e6625` | 21 văn bản (held-out 14 / dev 7), pool 839, nhãn GPT `gpt-4o-mini-2024-07-18`; cắt đuôi trang web (người dùng chốt) |
| P2 ứng viên cấu trúc | PASS | `b0022c8`, `29c4dc1` | `pair_candidates.py` **đóng băng** (`pairs-cand-v1`, `PAIRS_TOP_K=40` — người dùng chốt thay K=10 của quy tắc); S4 31 cặp; mẫu HG-1 181 dòng khoá trong `pairs/manifest.json` |
| P3 bộ phân loại LLM | PASS | `bffe37e3` | Code/test + dev probe Claude; trace provider/fingerprint hardening tiếp trong P5 |
| P4 tích hợp + lưu trữ | PASS | `976521eb`, `599f3677`, `cd6a1994` | Integration/storage, golden, DEC consent và verification đã ghi |
| P5 bake-off | live complete, final gates pending | (chưa commit) | Model cx/gpt-6-sol → gpt-6-sol; C1 3/101, B1 2/101, E1 9/101, C2 4/101, B2 3/101, E2 9/101; E vượt budget; decision HUMAN_DECISION, rank E > C > B |

Artifact verify từng phase: `artifacts/verification-P1.json`, `verification-P2.json`.

## 3. Quyết định đã chốt — không đảo lại

- K-a: GPT gán nhãn; classifier dùng model thuộc họ anthropic|google|openai được nhận diện, tên cụ thể khác labeler; kiểm trên served_model và fail-closed (mã 2).
- `PAIRS_TOP_K=40`, `CANDIDATES_VERSION=pairs-cand-v1`: không sửa `ai-service/app/pipeline/contract_graph/pair_candidates.py` (P3–P5 chỉ gọi). `extend-heldout` từ chối khi lệch báo cáo.
- **HG-1 do người dùng tự duyệt** (Q5, D13): phiếu `.harness/state/contract-graph-pairs/review/heldout_review.csv`, cột `decision` = `approve|relabel|reject` (+`label_fixed`, `direction_fixed` cho nhãn có hướng). Agent **không** điền phiếu. P5 bước 0 cần phiếu đủ.
- Không chạy bộ phân loại trên held-out trước P5; mọi đọc dữ liệu đóng băng đi qua `manifest.read_split` (verify trước).
- Không nới ngưỡng, không bịa số: thiếu điều kiện ⇒ ghi BLOCKED kèm lý do.
- TDD từng phase: test RED chạy và thấy FAIL trước khi viết module; sau đó cổng regression như §1.5.
- Deviation đã chấp nhận: `pairs/manifest.py` `verify` chấp nhận file S4 trong `extension_s4`; `family()` dùng `o\d+`.

## 4. Việc tiếp theo

1. Đọc `evals/contract_graph/reports/l2-p5-bakeoff.{json,md}`, `l2-p5-decision.json` và `plans/.../bakeoff-verdict.json` của model mới; artifact model cũ nằm trong `tmp/p5-superseded-before-model-switch` và không dùng.
2. Chạy lại tester/reviewer độc lập trên snapshot mới; ghi `verification-P5.json` và `review-decision.json`. Verdict nghiệp vụ vẫn cần người quyết định vì `HUMAN_DECISION`/E over-budget.
3. Ghi nhận full-suite baseline 13 lỗi môi trường và chạy lại focused/eval/Ruff sau mọi thay đổi gate.
4. Xử lý secret-scan gate của `hs:git`: diff chỉ có tên field/sentinel test (`token`, `api_key`, `PRIVATE_KEY`), không có credential; cần quyết định/điều chỉnh trước commit cục bộ. Không push nếu chưa được yêu cầu.

Commit: conventional commit, mỗi message kết thúc bằng dòng trống rồi dòng attribution của công cụ đang dùng. Không commit `.env`, `.harness/state/`, key.

## Tiếp tục sau khi chạy model cx/gpt-6-sol (2026-10-09)

- Đã chạy đủ C1/B1/E1/C2/B2/E2 dưới fingerprint hiện tại, cùng lock HG-1 và cùng requested/served model.
- Bảng hiện tại: C1 3/101, B1 2/101, E1 9/101 (over-budget), C2 4/101, B2 3/101, E2 9/101 (over-budget).
- l2-p5-decision.json là HUMAN_DECISION, recommendation_only=true, budget_blocked_variants=[E]; rank artifact là winner=E nhưng phải đọc kèm over_budget=[E].
- Cần hoàn tất gate cook: tester/reviewer độc lập đọc snapshot này, verification-P5.json, review-decision.json, rồi cook next/close theo envelope. Không bật cờ và không commit key.
