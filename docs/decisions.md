# Decision Register

---
id: DEC-dungskbg2004-1
status: active
date: 2026-10-09
actor: "user:dungskbg2004@gmail.com"
ts: "2026-10-09T01:42:38.515894+00:00"
affects: "ai-service/app/pipeline/ai1_snapshot_adapter.py || ai-service/app/pipeline/contract_graph/pair_builder.py || docs/ai2/AI2-20-contract-graph-pairs.vi.md || docs/contracts/be.ai2.processing.request.v1.schema.json:62"
executed_by: "ai-service/app/pipeline/ai1_snapshot_adapter.py:adapt_be_ai2_processing_request || ai-service/app/pipeline/contract_graph/pair_builder.py:build_pair_relations"
meta: {"plan": "261008-1500-ai2-contract-graph-implicit", "related": "DEC-BE-AI2-01 D6; V5 discovery-brief"}
---

## DEC-dungskbg2004-1 — AI2 luồng 2 đọc policy_flags.egress_allowed làm consent chia sẻ nội dung hợp đồng cho LLM phân loại cặp

Không đổi be.ai2.processing.request.v1; cờ chỉ thu hẹp bằng AND với AI2_PROCESSING_EGRESS_ALLOWED (A8), không nới. BE đang gửi False nên rule-only cho tới khi BE có toggle. Mọi quan hệ NEEDS_REVIEW, không legal winner. Bật cờ cần DEC này, verdict P5 và quyết định của người dùng. Người dùng đã chốt Q1 trong plan được duyệt ngày 2026-10-08.
