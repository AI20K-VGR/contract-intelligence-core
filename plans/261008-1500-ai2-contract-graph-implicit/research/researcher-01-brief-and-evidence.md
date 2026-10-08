# Brief — Contract graph đợt 2 (luồng 2: quan hệ ngầm)

Ngày: 2026-10-08 · Base: nhánh `feature/ai2-contract-graph` (`83f2d75`), luồng 1 đã xong (plan `261007-1735-ai2-contract-graph-op-first`, completed).
Nguồn: `discovery-brief.md` (cùng thư mục), `research-addendum-operation-first.md`, `bakeoff-verdict.json`, `plans/reports/rootcause-261007-1610-ai2-16-key-graph-low-recall-report.md`, `plans/reports/contract-graph-research-261007.md`, `docs/ai2/AI2-19-contract-graph-operation-first.vi.md`.

## Mục tiêu

AI2 phát hiện **quan hệ ngầm** giữa các khoản/phụ lục: những quan hệ mà văn bản không có câu thao tác "sửa đổi/bổ sung/bãi bỏ". Luồng 1 đã phủ phần có câu thao tác.

## Quyết định người dùng chốt (2026-10-08)

| # | Quyết định |
|---|---|
| L2-1 | Loại quan hệ: `GENERAL_SPECIFIC`, **liên kết mâu thuẫn** (finding `COMPARABLE_DIFFERENCE` + đường nối vô hướng, V3), `DUPLICATE`, `REFERENCE` ngữ nghĩa (dẫn chiếu không dùng số Điều) |
| L2-2 | Consent: **chỉ phía AI2** đọc cờ consent trong `policy_flags`. Không có consent ⇒ chỉ ứng viên cấu trúc, không gọi LLM, coverage ghi `graph_mode` rule-only. Toggle UI/BE để sau |
| L2-3 | Dữ liệu: plan có phase dựng **bộ nhãn cặp**: ≥15 mẫu HĐ mua bán/dịch vụ công khai; GPT gán nhãn; người dùng duyệt mẫu; khóa held-out (sha256); tái dùng probe bake-off `.harness/state/bakeoff/contract-edge-261007/probe.py` |
| L2-4 | Phạm vi: bộ nhãn → ứng viên cấu trúc → LLM phân loại (Claude) + grounding bằng code → tích hợp `run_idp` sau **flag riêng** (mặc định tắt) → bake-off lại. **Không** đổi contract BE, **không** UI |
| Kế thừa | Model gán nhãn ≠ model phân loại (GPT gán, Claude phân loại). Không legal winner. Mọi cạnh `NEEDS_REVIEW`; PASS chỉ khi Wilson ≥ 0,85, n ≥ 60 và gold đã duyệt. Profile ưu tiên: SALES + SUPPLY_SERVICE |

## Bằng chứng nền (OBSERVED)

- **Bake-off `contract-edge-261007-run1`** (11 cặp gold, smoke test, verdict `insufficient_trials`):
  - C (SAME_ARTICLE + EXPLICIT_REF + SAME_KEY → LLM phân loại) đạt 10/11 recall, 10/10 precision, khoảng 4.300 token.
  - B (không SAME_KEY) đạt 8/11.
  - E (LLM so mọi cặp) đạt 11/11 recall nhưng precision 11/32, gán CONFLICT tràn lan.
  - A (key graph + ngữ cảnh) đạt 7/11, tốn 75k token.
- **Root cause AI2-16:** trích từng khoản thiếu ngữ cảnh kế thừa; 12/16 cặp gold nằm cùng Điều.
- **Gold cũ yếu:** 6/11 cặp lấy từ fixture tổng hợp HD-TONG-HOP; gold không có quan hệ chung–riêng.
- **Hạ tầng sẵn có:**
  - `relation_markers.py`;
  - `contract_graph/` gồm address, resolver, operations, builder, projection, documents;
  - `ContractEdge`/`EdgeOp` ở `app/contracts/contract_graph.py`;
  - bảng `ai2.contract_edges` (migration 0005; CHECK op chỉ nhận 5 op luồng 1);
  - `coverage.contract_graph`;
  - cạnh ra BE dưới dạng `AMENDS`.
- **Ràng buộc BE:**
  - `persistence.py:834` so chuỗi `"AMENDS"`;
  - `schemas.py:253-288` đặt `extra="forbid"`;
  - `coverage` là object tự do.

## Câu hỏi mở cho plan

- Cạnh luồng 2 ra BE thế nào khi không đổi contract: chỉ nằm trong bảng `ai2` và coverage, hay ánh xạ vào `context_findings` sẵn có?
- `EdgeOp` mới cho luồng 2 có mở rộng CHECK của bảng `contract_edges` không (cần migration 0006), hay dùng bảng/model riêng?
- Ngân sách token mỗi hồ sơ, và cách chặn ứng viên SAME_ARTICLE quá nhiều (top-k theo điểm cấu trúc).
- Chống prompt injection từ văn bản hợp đồng khi đưa vào LLM.

## Ngoài phạm vi

UI, toggle consent BE/FE, đổi contract BE, Kafka, thứ tự hiệu lực theo ngày ký (AI2-18), chuỗi sửa nhiều lớp, query/L1 dùng graph, BL-006 (danh tính hợp đồng).
