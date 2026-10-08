# Backlog

<!-- generated from docs/backlog.yaml by backlog_register.py — do not edit -->

## Open

### P2
- BL-001 [debt] contract_edges giữ cạnh của snapshot cũ khi job mới có contract_graph_ran=False; ghi bất biến vào AI2-19/COMMENT hoặc xoá cạnh (review F2, jobs.py:575)
- BL-002 [bug] resolver _resolve_options trả method=EXACT cho kết quả lọc-theo-tồn-tại; tách method trước khi mở cổng PASS (review F4, resolver.py:250)
- BL-006 [feature] Contract graph direction A: supply dossier document identities (contract number of the body, annex numbers) from BE/AI1 metadata to build_contract_graph(known_documents=...). Until then runtime refuses every operation that names a numbered document (FOREIGN_DOCUMENT), including annexes citing their own contract number.

### P3
- BL-003 [debt] builder MAX_EDGES không giới hạn số EvidenceIssue (review F5, builder.py:221)
- BL-004 [debt] golden flag-off so sha256_json(sort_keys) chứ không phải bytes thô (review F7)

## Done

### P1
- BL-005 [bug] Contract graph: operations naming another document ('Điều 11 Thông tư số 156/2013', 'Điều 5 của Hợp đồng số X') resolve to the same-numbered article of the target file. Add a foreign-document guard (compare named document number with the target file identity; else TARGET_FOREIGN_DOCUMENT, no edge), then enable multi-article sources in evals/contract_graph/pipeline_predictor.py (stash 'cg-recall-predictor-A' 80cb239: recall 79->85 but resolved precision 0.865->0.667 without the guard).
