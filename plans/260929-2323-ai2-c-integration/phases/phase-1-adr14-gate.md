---
phase: 1
title: "Adr14 Gate"
status: pending
plan: 260929-2323-ai2-c-integration
created: 2026-09-29
harness_version: 6.3.0
harness_kit_digest: 672de2e098c3cb8451018791788f1052b1b812ccec08a1f124191bd8bbc04ebd
harness_schema_version: 1.0
---

# Phase 1 — Adr14 Gate

## Overview
Soạn ADR-14 trong `docs/DOC-04-architecture.md` (trạng thái `Proposed`), sửa phạm vi ADR-02/ADR-03, thêm dòng change record, rồi **Architecture Lead quyết định** (HC-C1). Đây là cổng người: nhóm 2c của P2 (bind Postgres) và toàn bộ P3 chờ kết quả. P2 nhóm 2a/2b và P4 (trừ F4.10) **không** chờ phase này.

Không phụ thuộc phase nào.

## Dependency map
- **Upstream:** D-3 (khoá), research `research/postgres-e2e-quality.md` (Q1, Q2, Open question 1, 3, 4), code hiện tại: `ai-service/app/tools/jobs.py:240-273` (AI2 đã sở hữu lease trong SQLite từ P3, tức đã lệch ADR-02).
- **Downstream:** P2-2c (Accepted → Postgres; Rejected → 2c′ SQLite trên volume), P3 (cạnh P1→P3; Rejected → bỏ E7, thêm E9).
- **Người:** HC-C1 (Architecture Lead, `docs/DOC-04-architecture.md:9`); VD-C2 cần chốt trước khi soạn đoạn "Hệ quả".

## Requirements
Chức năng:
- **F1.1 Dòng ADR-14** trong bảng §2.3 (sau ADR-13, `docs/DOC-04-architecture.md:104`). Nội dung tối thiểu:
  - **Quyết định:** AI2 sở hữu trạng thái riêng của biên Backend↔AI2 (job, idempotency, nonce, record hồ sơ đã xử lý) trong schema `ai2` của DB `contract_intelligence` (Postgres của Backend). AI2 không đọc/ghi `public`; Backend không đọc/ghi `ai2`.
  - **Role:** `ai2_migrator` (chủ schema, DDL, chỉ dùng bởi one-shot `ai2-migrate`), `ai2_app` (DML trên `ai2.*`, `CONNECTION LIMIT 20`, `statement_timeout 30s`, `search_path ai2`). Bootstrap role/schema bằng bước admin (dev: `ai2-migrate` có `AI2_DB_ADMIN_URL`; prod: DBA), không qua `initdb.d`.
  - **Migration:** Alembic riêng trong `ai-service`, `version_table_schema=ai2`, lọc schema; chuỗi migration độc lập với Backend.
  - **Thực thi:** in-process (BackgroundTasks) + Postgres là nguồn sự thật + sweep lúc khởi động và định kỳ; claim nguyên tử `UPDATE … RETURNING`; **1 replica**; > 1 replica cần ADR mới (poller `SKIP LOCKED`).
  - **Hợp thức hoá:** ADR-02 (`:93`, "không kết nối PostgreSQL, không sở hữu queue/lease") sửa phạm vi: AI2 sở hữu lease/queue **nội bộ của job AI2**; task table/lease của Backend dispatcher vẫn do Backend sở hữu (§5). ADR-03 (`:94`, "không thêm second state store"): schema `ai2` dùng chung instance, không thêm store mới.
  - **Hệ quả:** backup/restore chung với Backend; tài nguyên dùng chung (connection, disk) → giới hạn connection + retention (VD-C4); Backend đang chạy bằng superuser `ci` (`docker-compose.yml:276,386`) nên chiều "Backend không có quyền trên `ai2`" chưa cưỡng chế được — follow-up của Backend (theo VD-C2).
  - **Phương án đã cân nhắc:** (B) SQLite trên volume `ai2_data` + Backend resubmit khi mất dữ liệu; (C) Postgres instance riêng cho AI2 (thêm vận hành, trái ADR-03).
  - **Rollback:** bỏ `AI2_DATABASE_URL` → SQLite trên volume (phương án B), không đổi code.
- **F1.2** Cột "Hệ quả" của ADR-02 và ADR-03 thêm ghi chú "(phạm vi sửa bởi ADR-14)". §5 thêm một câu gần `:281`: lease job nội bộ của AI2 tách khỏi task lease của Backend dispatcher.
- **F1.3** Change record §22 (`:981+`): ngày, phiên bản `v0.8.0` (DOC-04 đang `v0.7.0`, `:8`), thay đổi, lý do (D-3, lỗi mất hậu xử lý khi restart), ảnh hưởng (§2, §5, §18), tài liệu đồng bộ (`docs/system-architecture.md` ở P3), owner "Architecture Lead + Backend + AI2".
- **F1.4 Ghi quyết định.** Architecture Lead review PR/commit chứa F1.1–F1.3, đổi trạng thái thành `Accepted` hoặc `Rejected` (kèm lý do). Cook ghi `artifacts/verification-P1.json` gồm `adr14.status`, `approved_by`, `evidence` (URL review hoặc SHA commit), `date`.
- **F1.5 Nếu `Rejected`:** giữ dòng ADR-14 với trạng thái `Rejected` + lý do; báo main để sửa plan theo phương án dự phòng (P2-2c′, P3 E9) và **duyệt lại plan** trước khi cook tiếp P2-2c/P3.

Phi chức năng:
- Không sửa code. Không đổi nội dung các ADR khác ngoài ghi chú phạm vi.
- Văn phong tiếng Việt như phần còn lại của DOC-04; định danh giữ tiếng Anh.

## Related Code Files
**Modify**
- `docs/DOC-04-architecture.md`

**Create / Delete** — không có.

## File inventory

| File | Hành động | Cỡ | Tác động test |
|---|---|---|---|
| `docs/DOC-04-architecture.md` | M | +1 dòng ADR, 2 ghi chú, 1 câu §5, 1 dòng change record (~25 dòng) | không có test code; kiểm bằng grep + review người |

## Implementation Steps
1. Đọc `docs/DOC-04-architecture.md` §2.3 (`:88-106`), §5 (`:243-284`), §22 (`:981-990`) và `docs/governance/DOCUMENT-GOVERNANCE.md`.
2. Xác nhận VD-C2 đã chốt (nội dung đoạn "Hệ quả"). Nếu chưa → dùng khuyến nghị (a) và ghi rõ "chờ xác nhận" trong PR.
3. Soạn F1.1–F1.3, trạng thái `Proposed`. Commit riêng: `docs(doc-04): propose ADR-14 schema ai2 for AI2 state`.
4. Mở PR (hoặc gửi commit) cho Architecture Lead (HC-C1). Trong lúc chờ, cook chuyển sang P2-2a/2b và P4.
5. Khi có quyết định: Architecture Lead (hoặc người được uỷ quyền, ghi tên) đổi trạng thái; cook ghi `verification-P1.json` (F1.4) và chạy `manual_test_anchor.py` cho bằng chứng.
6. Nếu `Rejected` → F1.5.

## TDD
**N/A có lý do:** phase chỉ sửa tài liệu và chờ quyết định của người; không có hành vi code để viết test đỏ. Kiểm chứng thay thế:
- `rg -n "ADR-14" docs/DOC-04-architecture.md` → ≥ 4 hit (dòng ADR, ghi chú ADR-02, ghi chú ADR-03, change record).
- `rg -n "ai2_migrator|ai2_app|version_table_schema" docs/DOC-04-architecture.md` → có hit trong dòng ADR-14.
- Regression: không chạy suite (không đổi code); PR guard hiện có của repo phải xanh.

## Test scenario matrix

| Mức | Kịch bản | Kiểm |
|---|---|---|
| Critical | Cook chạy P2-2c/P3 khi ADR chưa `Accepted` | P2 bước 2c.0 và P3 bước 0 đọc `verification-P1.json`; khác `Accepted` → dừng |
| High | ADR-14 mâu thuẫn ADR-02/03 không được ghi | grep ghi chú phạm vi ở cả hai dòng |
| Medium | Thiếu change record (vi phạm governance) | grep dòng `v0.8.0` ở §22 |

## Success Criteria
- [ ] (invariant) DOC-04 có dòng ADR-14 với đủ 7 mục của F1.1, ghi chú phạm vi ở ADR-02 và ADR-03, câu bổ sung §5, dòng change record `v0.8.0`.
- [ ] (manual — `manual_test_anchor.py`) HC-C1: `verification-P1.json` có `adr14.status ∈ {Accepted, Rejected}`, `approved_by` là Architecture Lead (hoặc người được uỷ quyền có tên), `evidence` là URL review hoặc SHA commit.
- [ ] (invariant) Nếu `Rejected`: plan đã được sửa theo phương án dự phòng và duyệt lại trước khi P2-2c/P3 chạy.

## Risk Assessment

| Rủi ro | Khả năng × Tác động | Giảm thiểu |
|---|---|---|
| R1-1: Architecture Lead chậm phản hồi | Cao × Trung | Cổng cấp bước: P2-2a/2b và P4 chạy tiếp; báo main mỗi khi P2-2b xong mà P1 còn chờ |
| R1-2: ADR bị từ chối | Trung × Trung | Phương án B đã thiết kế (plan.md "Cổng ADR-14 và phương án dự phòng"); store dialect-agnostic nên chi phí đổi nhỏ |
| R1-3: Lead yêu cầu thêm (vd role Backend không superuser) | Trung × Trung | Ghi thành yêu cầu mới, sửa plan + duyệt lại; không tự mở rộng P2/P3 |
