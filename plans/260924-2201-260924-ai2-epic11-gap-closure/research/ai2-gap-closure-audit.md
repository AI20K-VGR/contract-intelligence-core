# Research report — AI2 gap closure

Ngày: 2026-09-24

## Evidence sources

1. `plans/reports/ai2-epic11-current-state.md` — read-only audit và test probe.
2. `ai-service/app/api/main.py:622-696,1419-1510` — metadata-only `/process`/`/query` và canonical `/jobs/idp`.
3. `backend/src/contract_intelligence/infrastructure/ai_adapters.py:163-302` — canonical submit/poll cùng legacy process/query adapter.
4. `backend/src/contract_intelligence/api/v1/dossiers.py:184-222` — Backend query forwarding hiện tại.
5. `backend/src/contract_intelligence/worker.py:382-410` và `backend/src/contract_intelligence/shared/ai/persistence.py:659-790` — canonical processing persistence path.
6. `ai-service/app/reasoning/stack.py:15-189`, `l1_retrieval.py:63-182`, `l3_ground.py:13-236`, `vector_recall.py:169-304` — core reasoning đã có nhưng chưa được Backend query path gọi xuyên suốt.

## Findings

- ST-044 core đã validate snapshot/pins/no-PDF và dựng graph; gap còn lại là contract/E2E proof và digest/provenance test chạy được trong môi trường chuẩn.
- ST-045 core đã extract raw/normalized/citation/context, pair body–annex và emit disposition; gap còn lại là result persistence/idempotency/full regression proof.
- ST-046 là gap lớn nhất: engine L0→L3 tồn tại nhưng Backend `/dossiers/{id}/query` gọi metadata-only `/query`, AI2 chủ động trả `INSUFFICIENT_EVIDENCE`.
- ST-047 AI2 chỉ propose đúng thiết kế; cần chứng minh reviewer/publish command ở Backend không bypass bởi retry/duplicate và active pointer không bị mutation.
- Test probe liên quan cho thấy 81 pass và 2 lỗi do quyền pytest temp; full suite/Backend suite chưa chạy được do dependency/interpreter blockers.

## Options

### A — Giữ `/query` fail-closed và chỉ bổ sung test

An toàn nhưng không hoàn thành ST-046 vì user query thật không vào L0→L3. Loại.

### B — Wire query qua evidence projection theo composite scope key

Backend process canonical result/snapshot trước, AI2 lưu hoặc truy cập projection theo `(tenant_id, dossier_id, snapshot_digest)`, query kiểm tra ACL/staleness rồi gọi FourLayerReasoner. Phù hợp nhất với code hiện tại, giữ raw PDF ngoài AI2 và cho phép fail-closed khi thiếu projection.

### C — Gửi toàn bộ snapshot trong từng query

Đơn giản về state nhưng tăng payload, chi phí và nguy cơ leak; không phù hợp nguyên tắc bounded evidence/query context.

## Ranked conclusion

1. Chọn B; tạo seam query context/projection, không refactor core reasoner đã có.
2. Giữ A làm fallback khi projection thiếu/stale.
3. Không chọn C trong gap closure; chỉ dùng bounded evidence package nếu mentor yêu cầu thay cho projection.

## Open questions

- Projection lưu ở AI2 hay Backend sở hữu và gửi bounded context mỗi query?
- Reviewer publish command/API hiện có là gì; nếu chưa có, cần tạo command riêng hay chỉ persist review state?
- Environment owner nào khôi phục `uv`/Python, pytest temp permission và missing test dependencies?
