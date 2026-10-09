# AI2 documentation

Tài liệu AI2 mô tả pipeline, thiết kế và trạng thái triển khai hiện tại của `ai-service`.

## Thứ tự đọc

1. [AI2-00 — Pipeline overview](AI2-00-pipeline-overview.vi.md)
2. [AI2-DOC-01 — Product vision phần AI2](AI2-DOC-01-product-vision.vi.md)
3. [AI2-DOC-02 — BRD phần AI2](AI2-DOC-02-brd.vi.md)
4. [AI2-DOC-03 — PRD phần AI2](AI2-DOC-03-prd.vi.md)
5. [AI2-DOC-04 — Architecture phần AI2](AI2-DOC-04-architecture.vi.md)
6. [AI2-01 — Business/Policy](AI2-01-business-policy-perspective.vi.md)
7. [AI2-02 — Extraction Engine](AI2-02-extraction-engine-design.vi.md)
8. [AI2-03 — Detailed design](AI2-03-detailed-design.vi.md)
9. [AI2-04 — Edge-case test matrix](AI2-04-edge-case-test-matrix.vi.md)
10. [AI2-05 — Architecture component](AI2-05-architecture.vi.md)
11. [AI2-05 — Worked examples](AI2-05-worked-examples.vi.md)
12. [AI2-06 — Implementation gap](AI2-06-implementation-gap.vi.md)
13. [AI2-07 — Full pipeline](AI2-07-full-pipeline.vi.md)
14. [AI2-08 — C0–C4 architecture](AI2-08-architecture-c0-c4.vi.md)
15. [AI2-09 — AI1 snapshot handoff](AI2-09-ai1-snapshot-handoff.vi.md)
16. [AI2-10 — Current flow](AI2-10-current-flow.vi.md)
17. [Architecture method](AI2-architecture-method.vi.md)
18. [AI1 snapshot input thực tế và package AI2 v1](AI2-11-ai1-snapshot-input-and-package.vi.md)
19. [AI2-12 - Review and release gate](AI2-12-review-and-release-gate.md)
20. [AI2-13 - Contract context, events and independent OCR-lab samples](AI2-13-contract-context-and-independent-samples.vi.md)
21. [AI2-14 - Full flow đếm số bên](AI2-14-party-count-full-flow.vi.md)
22. [AI2-15 - Contract profiles, structure, relations và free-form Q&A](AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md)
23. [AI2-16 - Clause key graph (AI2 v2): cơ chế, quyết định, bằng chứng và lộ trình](AI2-16-clause-key-graph-v2.vi.md) — đề xuất, chưa triển khai
24. [AI2-18 - Quy tắc phụ lục ký sau sửa văn bản ký trước (ST-068)](AI2-18-amendment-precedence-rules.vi.md) — đề xuất DEC + biên bản 3 cặp, chờ duyệt
25. [AI2-19 - Contract graph luồng 1 (operation-first): cạnh sửa đổi, wire `AMENDS`, bảng `ai2.contract_edges`](AI2-19-contract-graph-operation-first.vi.md) — sau flag `AI2_CONTRACT_GRAPH_ENABLED` (mặc định tắt)
26. [AI2-20 - Quan hệ ngầm giữa các khoản: consent, findings và storage](AI2-20-contract-graph-pairs.vi.md) — sau `AI2_CONTRACT_GRAPH_PAIRS_ENABLED`, cần cổng P5

## Authority

Product scope remains in the root [DOC-01](../DOC-01-product-vision.md) through [DOC-06](../DOC-06-eval-report.md). The AI1–AI2 payload contract is maintained in [contracts](../contracts/README.md).

Diagrams and the legacy decision/traceability bundle are intentionally deferred to a later documentation pass.
