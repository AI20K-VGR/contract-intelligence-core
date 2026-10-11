---
phase: 1
title: "AI2 graph read và persistence receipts"
status: completed
plan: 261011-1654-ai2-graph-ui
created: 2026-10-11
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 1 — AI2 graph read và persistence receipts

## Overview

Thêm internal graph read API có service signature và receipt riêng cho operation/pair write. API phải phân biệt graph rỗng đã lưu thành công với write failure dù job vẫn SUCCEEDED (ai-service/app/tools/jobs.py:575-611).

## Requirements

- Scope tenant/dossier/job/snapshot/digest kiểm tra trước khi truy vấn và ràng buộc trên mọi row.
- Receipt ghi riêng theo graph kind; kết quả COMMITTED, FAILED, SKIPPED gồm digest, row_count và safe error code.
- Receipt được insert sau savepoint của graph write nhưng trong transaction completion. Receipt lỗi làm transaction completion rollback.
- READY với 0 cạnh chỉ hợp lệ khi builder stage completed, digest khớp, receipt COMMITTED và row_count bằng 0. PERSIST_FAILED không bao giờ thành empty-ready.
- Cờ contract_graph_ran và pair_relations_ran đã có tại ai-service/app/tools/store.py:64-67; dùng giá trị thực từ pipeline gates ai-service/app/pipeline/idp.py:279-307,370-401,433-436.
- Read projection bỏ Citation.text_span, pair span, new_text, scope_text, raw body/prompt; chỉ trả node IDs/addresses, loại/hướng/review state và citation refs opaque.
- Postgres graph store là nguồn duy nhất hiện tại. SQLite, legacy job thiếu receipt và read failure phải là UNAVAILABLE/PERSISTENCE_UNKNOWN, không empty.
- Giữ ai2.be.processing.result.v1 nguyên trạng.

## Related Code Files

**Create**
- ai-service/app/api/contract_graph_router.py
- ai-service/app/tools/contract_graph_read_model.py
- ai-service/app/db/migrations/versions/0007_contract_graph_write_receipts.py
- ai-service/tests/test_contract_graph_read_api.py
- docs/contracts/ai2.contract-graph.read.v1.schema.json

**Modify**
- ai-service/app/api/main.py — mount internal router cạnh route hiện có.
- ai-service/app/db/tables.py — receipt table/index.
- ai-service/app/tools/jobs.py — ghi receipt operation/pair sau savepoint tại :575-611.

## Implementation Steps

1. Viết test đỏ cho 0 cạnh hợp lệ, operation write failure, pair write failure, outer transaction rollback và job không có receipt.
2. Thêm migration additive cùng unique key (tenant_id,dossier_id,job_id,graph_kind) và index scope/snapshot phù hợp; tránh lưu raw contract content vào receipt.
3. Refactor từng writer để trả persistence outcome an toàn; exception trong nested savepoint được bắt thành FAILED và safe code ổn định, không dùng message exception làm API payload.
4. Ghi receipt ngoài savepoint; nếu có lỗi commit ngoài cùng thì job completion không được báo accepted/READY.
5. Tạo signed GET theo job; lựa chọn snapshot/current job xác định; query operation/pair stores cùng receipt.
6. Build bounded keyset page order ổn định theo graph kind và edge/relation ID. Response gồm total_count, next_cursor/has_more và per-kind processing/persistence status.
7. Thêm migration/schema/contract tests; không đọc citation body.

## Tests Before (RED)

- [ ] COMMITTED/0 sau builder success được thể hiện empty-ready.
- [ ] Lỗi operation và pair store riêng biệt không thành READY; lỗi một store không che status store kia.
- [ ] Builder OFF/skipped và SQLite/unmigrated legacy khác với empty-ready.
- [ ] Sai signature/tenant/dossier/job/digest/cursor bị reject.
- [ ] JSON response không chứa text_span, span_a, span_b, new_text, scope_text hoặc prompt keys.

## Tests After (GREEN)

- [ ] cd ai-service; uv run pytest tests/test_contract_graph_read_api.py -q
- [ ] cd ai-service; uv run ruff check app/api app/tools app/db tests/test_contract_graph_read_api.py
- [ ] Kiểm tra schema cho ready-empty, partial, persistence-failed, skipped, unavailable, persistence-unknown và multi-page.

## Regression Gate

cd ai-service; uv run pytest -q phải qua trước P2.

## Success Criteria

- [ ] Fault injection cho mỗi graph store tạo đúng receipt và không che job/pipeline status.
- [ ] Không thể sinh READY rỗng từ job SUCCEEDED nếu thiếu receipt hoặc stage chưa chạy.
- [ ] Mọi page chỉ chứa row cùng scope và digest.
- [ ] Result wire v1 và events[] không đổi.

## Risk Assessment

- **High (M×H), receipt không commit cùng snapshot:** receipt nằm trong outer completion transaction nhưng ngoài graph savepoint; test rollback/commit fault.
- **High (M×H), API trả nhầm snapshot hoặc empty:** lọc cả graph row và receipt theo job/digest; test stale job và legacy.
- **Medium (M×M), projection lộ evidence:** field allowlist + schema deny raw text/span; test JSON serialization.

## Rollback

Tắt route mới; giữ operation/pair rows và receipt table additive. Không drop table hoặc xóa receipt trong rollback thông thường.

