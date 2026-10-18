# Bản đồ luồng AI2 theo tính năng (phục vụ đánh giá giải pháp)

Phạm vi: `ai-service/app` (khoảng 20.000 dòng trong các module chính). Chỉ đọc. Nguồn: các lần đọc code và đo đạc trong phiên 2026-10-16, cùng số dòng của từng file.

## 1. Luồng tổng (một job IDP)

```
Backend worker ─(be.ai2.processing.request.v1, ký HMAC)─▶ POST /jobs/idp (api/main.py)
  └─ _execute_wire_job → adapt_be_ai2_processing_request (ai1_snapshot_adapter.py, 3063 dòng)
       └─ adapt_snapshot (mỗi tài liệu) → _adapt_page → _line_nodes (ghép đoạn văn trong trang)
          + _cross_page_wrap_issues → enrich_result_structure → assign_contract_units
  └─ run_idp (pipeline/idp.py) với ProcessingRuntime (budget lời gọi/thời gian/token)
       ├─ fact/clause/table (fact.py, table.py) ── LLM: fact_normalize, table
       ├─ contract graph luồng 1: builder.build_contract_graph (address → resolver → operations)
       ├─ luồng 2 pairs: pair_builder → pair_candidates (tất định) → pair_classifier (LLM: pairs)
       │     → pair_projection (coverage, conflict findings)
       ├─ semantic: frame_context.build_semantic_extension → frame_extraction → _enrich (LLM: slot_context, alias)
       │     → clause_keys.build_candidates → frame_comparison/semantic_alignment
       └─ job_result_to_wire (contracts/wire.py) → JobStore (Postgres) + query snapshot
Backend: persist_ai2_processing_result → citation_guard.verify_citation → finding/review items
Query: POST /query → STORE (cache bộ nhớ) | load_query_snapshot → reasoning/* (l0 rules, l1 retrieval,
       vector_recall (embedding, index cache theo snapshot), l2_plan/orchestrator (LLM), l3_ground)
```

## 2. Tính năng → file chính → thông số giới hạn

| Tính năng | File chính | Giới hạn / thông số | Khi tràn |
|---|---|---|---|
| OCR → node | `ai1_snapshot_adapter._line_nodes`, `_continues_previous`, `_cross_page_wrap_issues` | ghép khi dòng ≥ 45 ký tự và ≥ 60% dòng dài nhất | qua trang: chỉ báo `CLAUSE_CONTINUES_ON_NEXT_PAGE` |
| Luồng 1 (sửa đổi) | `contract_graph/builder.py`, `resolver.py`, `operations.py`, `address.py` | địa chỉ phải UNIQUE, không đoán | `TARGET_NOT_FOUND` / ambiguous thành issue |
| Luồng 2, sinh ứng viên | `pair_candidates.py` | `PAIRS_TOP_K=40`, `_CORE_TOP_K_SHARE=1.0`; nguồn SAME_ARTICLE, EXPLICIT_REF, SAME_KEY, REFERENCE_CUE, VALUE_MISMATCH, STRUCTURED_KEY, VERBATIM | cắt theo top-K; **SAME_ARTICLE/SAME_KEY ghép mọi cặp trong nhóm (O(k²))** |
| Luồng 2, classifier | `pair_classifier.py` | `PAIRS_PER_CALL=8`, `PAIRS_MAX_CALLS=5`, timeout 45 giây × 3 lần thử | `PARTIAL_<lý do>` trên trace |
| Semantic | `frame_context.py` (919 dòng), `frame_extraction.py`, `frame_comparison.py`, `clause_keys.py`, `semantic_alignment.py` | `max_nodes=256`, `max_context_tokens=32768` byte, `max_llm_calls=20`, `max_seconds=300`; một frame cho mỗi lời gọi LLM | **duyệt theo thứ tự tài liệu, `break`** khi chạm trần |
| Runtime / budget | `runtime.py`, `llm/client.py` | Backend đặt cứng `max_llm_calls=20` (schema `le=20`); thời gian = base + per_page × số trang | `LLM_BUDGET_EXCEEDED`, `LLM_QUOTA_EXHAUSTED`, `PROCESSING_TIMEOUT` |
| Citation | `citations.py`, `outline.py`; Backend `citation_guard.py` | 1 trang, chuỗi con chính xác, `quote_sha256` | INVALID / `citation_guard_rejected` |
| Query | `reasoning/*` (khoảng 6.000 dòng), `vector_recall.py` | timeout LLM 15 giây; `max_embedding_tokens=50000` | rơi về trả lời bằng retrieval; vector `BUDGET_EXCEEDED` (tắt hẳn) |

## 3. Ranh giới ngoài

OpenAI (chat, embedding), Backend (request đã ký, persist, citation guard), PostgreSQL (`ai2.jobs`, trace, snapshot, pair relations), AI1 (snapshot OCR).

## 4. Thước đo hiện có

`fixtures/seeded/score.py` (offline: dev 42/42, held-out 20/21), `run_live` (classifier), `evals/contract_graph` (VBHN luồng 1, bộ nhãn pairs 600 dòng).

## 5. Điều chưa biết

1. Thời gian của từng nguồn sinh ứng viên trên hồ sơ 11.770 node: lần đo bị ngắt sau 25 phút, ngay ở SAME_ARTICLE. Nghi bùng nổ O(k²) **[ASSUMED]**.
2. Chất lượng query (l0–l3) chưa có gold nào đo.
3. Tỉ lệ citation `VALID` trên toàn hồ sơ thật chưa đo.
4. `table.py` (sinh code sandbox bằng LLM): chưa đánh giá.
