---
phase: 2
title: "AI2 durable processing trace"
status: pending
plan: 261011-1654-ai2-graph-ui
created: 2026-10-11
harness_version: 7.0.0
harness_kit_digest: 3d7949cb37672c0adc9085ddeddad1b8ac1617ee19b3ab4d9179877708328595
harness_schema_version: 1.0
---

# Phase 2 — AI2 durable processing trace

## Overview

Thêm trace append-only cho worker HTTP AI2, tách khỏi result wire và graph receipts. Worker chết giữa stage vẫn để lại durable start event; sweeper/read model thể hiện stage INTERRUPTED_UNKNOWN/INCOMPLETE_UNKNOWN, không tự hoàn tất stage.

## Requirements

- Source-of-truth là bảng trace riêng, hỗ trợ PostgreSQL và SQLite job-store đang được chọn bởi job_store_from_env() (ai-service/app/tools/jobs.py:656-660).
- Event key gồm tenant, dossier, job, snapshot digest, execution ID, sequence và stage ID; event có STARTED hoặc terminal status, times/counts/safe reason code.
- Không ghi raw contract text, excerpts/citation spans, prompt, provider response, secret hay hidden reasoning.
- Persist STARTED trước thao tác stage, terminal event sau boundary. Trace write failure không làm đổi job result; GET phải báo TRACE_UNAVAILABLE.
- Worker token/lease phải fence writer cũ sau reclaim; execution ID mới không trộn attempt.
- Khi sweep_stale đóng job, finalize stage còn mở thành INTERRUPTED_UNKNOWN. Nếu marker finalizer lỗi hoặc process dừng giữa job sweep/finalizer, projection thấy terminal job + dangling start và trả INCOMPLETE_UNKNOWN.
- Trace chưa tồn tại ở job cũ/direct demo/Kafka/batch không được dựng từ thứ tự code.

## Related Code Files

**Create**
- ai-service/app/api/processing_trace_router.py
- ai-service/app/tools/processing_trace_store.py
- ai-service/app/db/migrations/versions/0008_ai2_processing_trace.py
- ai-service/tests/test_contract_graph_trace_durability.py
- docs/contracts/ai2.processing-trace.v1.schema.json

**Modify**
- ai-service/app/api/main.py — mount route, truyền execution/worker scope vào worker HTTP tại :292, finalize sau stale sweep tại :343-364.
- ai-service/app/pipeline/idp.py — instrument branches thật tại :279-307,370-401, không đổi extraction semantics.
- ai-service/app/db/tables.py — trace event table.
- ai-service/app/tools/jobs.py — SQLite trace DDL/transaction helper nếu cần để cùng job store tồn tại qua restart.

P1 đã chạm main.py, tables.py và jobs.py; P2 thay đổi các file này tuần tự sau P1, không chạy song song. P2 chỉ sở hữu các phần trace được liệt kê ở trên.

## Implementation Steps

1. Thêm test đỏ cho stage start/terminal, event ordering, scope mismatch, lease fencing, trace-store outage và same-job retry.
2. Thêm schema/migration trace Postgres; lưu bảng SQLite trong database hiện dùng cho SQLite jobs, với index theo job/execution/sequence.
3. Tạo stateless store adapter cho SQLite/Postgres; mỗi lần ghi mở transaction nhỏ riêng để crash giữa hai stage không rollback mốc đã ghi trước.
4. Instrument đúng nhánh ở run_idp; truyền writer/worker token rõ ràng chỉ từ main.py worker HTTP path. Các call-site khác vẫn trace unavailable.
5. Sweeper append interrupt marker cho stage mở của execution đã hết lease; reader luôn xử lý dangling start fail-closed nếu finalizer không chạy được.
6. Reader scope theo tenant/dossier/job/digest/current execution; events cũ không được nối sang lần retry mới.
7. Chạy process test: persist STARTED, dừng worker, restart, sweep, đọc lại INTERRUPTED_UNKNOWN; lặp lại tình huống finalizer lỗi để xác nhận fallback INCOMPLETE_UNKNOWN.
8. Snapshot event shape vào schema; giữ result wire v1/events[] không đổi.

## Tests Before (RED)

- [ ] Assertion append STARTED đã commit trước operation/pair work.
- [ ] Kill/restart sau STARTED trước terminal giữ marker dù worker process mất.
- [ ] Lease fencing từ chối worker cũ ghi sau lần reclaim.
- [ ] Fail trace DB làm trace_status=UNAVAILABLE, không đổi AI2 job SUCCEEDED/FAILED.
- [ ] Stage pair OFF/consent skip khác với stage không có trace.

## Tests After (GREEN)

- [ ] cd ai-service; uv run pytest tests/test_contract_graph_trace_durability.py -q
- [ ] cd ai-service; uv run ruff check app/api app/pipeline app/tools app/db tests/test_contract_graph_trace_durability.py
- [ ] Test SQLite và Postgres adapter; process recovery test cần Postgres hoặc migration test environment được cấu hình trong CI.

## Regression Gate

cd ai-service; uv run pytest -q phải qua trước P3.

## Success Criteria

- [ ] Trace sống qua process restart và recovery.
- [ ] Worker loss không biến stage mở thành success; fail-closed fallback hoạt động nếu finalizer lỗi.
- [ ] Trace không làm job thất bại chỉ vì telemetry storage lỗi.
- [ ] Scope/retry fence ngăn trộn events giữa tenant, dossier, digest hoặc execution.

## Risk Assessment

- **High (M×H), worker mất giữa stage:** durable start trước stage + sweep finalizer + dangling-start fallback; kill/restart test.
- **High (M×H), trace của worker cũ ghi đè retry:** lease token fence + execution ID; test reclaim race.
- **Medium (M×H), telemetry store làm chậm/hỏng job:** bounded small transaction và best-effort errors, status TRACE_UNAVAILABLE; đo write latency trong process test.
- **Medium (M×M), chỉ instrument HTTP lane:** caller audit định danh rõ 9 call-sites; UI đánh dấu non-instrumented routes unavailable, không dựng trace.

## Caller inventory

rg -n 'run_idp\\(' ai-service/app vì plan-next không trả code callers: api/main.py:292,1136,1492,1699,1714,1750; transport/kafka_idp_worker.py:180; pipeline/ai2_batch.py:115,179. Chỉ line 292 là async signed Backend job path trong scope. Không thêm writer mặc định vào các demo/batch/Kafka call-sites; chúng hiển thị TRACE_UNAVAILABLE.

## Rollback

Tắt trace route/writer; không đổi contract/job result. Giữ bảng/event rows để debug; schema additive. Nếu store không sẵn sàng, trace đọc TRACE_UNAVAILABLE.

