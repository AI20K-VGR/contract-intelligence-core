# Research report — EPIC-11 AI2 completion

Ngày: 2026-09-24

## Câu hỏi cần giải đáp

1. Contract nào là đường canonical cho ST-044–ST-047?
2. Vì sao processing hiện có nhưng query chưa thể trả grounded answer?
3. Embedding nên nằm ở đâu và mức nào là đủ cho Sprint 2?
4. Gate nào phải giữ nguyên để không biến AI2 thành OCR/legal decision engine?

## Findings

### 1. Canonical handoff là `ai1.snapshot.v1` trong processing lane

- `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:8,20,77,102` mô tả Backend gửi đầy đủ `ai1.snapshot.v1` của dossier tới `/jobs/idp`, AI2 trả processing result và đây là contract processing hiện hành.
- `docs/ai2/AI2-10-current-flow.vi.md:34,41,70` xác nhận snapshot lane chỉ nhận `ai1.snapshot.v1` và `be.ai2.processing.request.v1`; demo/compatibility lane không thay thế canonical snapshot.
- `ai-service/app/contracts/wire.py:53,107` enforce `snapshot_version == ai1.snapshot.v1` và `schema_version == be.ai2.processing.request.v1`.
- `backend/src/contract_intelligence/shared/ai/canonical_processing.py:204,338` tạo đúng snapshot/request shape; `backend/src/contract_intelligence/shared/ai/ai1_adapter.py:28` giữ v3 ở compatibility boundary.

Kết luận quan sát được: không nên đổi AI2 canonical sang v3 trong cùng task; cần ghi rõ v3/v2 là legacy adapter và tách quyết định migration nếu Backend muốn thay contract.

### 2. Processing path đã có lõi, integration/query còn là gap

- `ai-service/app/api/main.py:1419` có canonical async `/jobs/idp`; `ai-service/app/pipeline/idp.py:39` chạy policy, handoff, relation graph, extraction, pairing, citation validation và index proposal.
- `ai-service/app/pipeline/handoff.py:26` reject raw PDF và validate lifecycle/version/page/node gates; `ai-service/app/reasoning/relations.py:128` dựng parent/reference/role/citation relation graph.
- `backend/src/contract_intelligence/infrastructure/ai_adapters.py:163,191` đã có submit/poll canonical; `backend/src/contract_intelligence/shared/ai/persistence.py:659` đã có hàm persist canonical result.
- `ai-service/app/api/main.py:622,669` vẫn có `/process` và `/query`; current behavior fail-closed khi chỉ nhận metadata/no canonical evidence. `backend/src/contract_intelligence/infrastructure/ai_adapters.py:262,294` còn gửi metadata-only vào hai endpoint này.

Kết luận quan sát được: ưu tiên hoàn thiện route `/jobs/idp` và wire persistence trước; không lấy metadata-only endpoint làm đường chính để “làm cho có”. Query cần evidence projection hoặc canonical query context có digest/scope.

### 3. Embedding là retrieval enhancement, không phải prerequisite của contract

- `ai-service/app/reasoning/l1_retrieval.py` định nghĩa thứ tự exact label → structured keys → BM25-like/semantic fallback và giữ exact hits cho compare/cascade.
- `ai-service/app/reasoning/vector_recall.py:169` có vector service với status disabled/budget/egress/provider errors, model/dimension/digest filtering và citation span validation.
- `docs/ai2/AI2-03-detailed-design.vi.md:351` yêu cầu đo riêng recall exact/structured/semantic và chi phí/query; `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:139` đặt query routing ở `query.py`/`stack.py`, không biến vector thành input contract.

Kết luận quan sát được: Sprint 2 phải làm deterministic retrieval và grounding trước; embedding chỉ bật khi policy/provider/budget cho phép, luôn fallback về exact/structured/BM25.

### 4. Safety gates là acceptance invariant

- `docs/AI2-MENTOR-HANDOFF.vi.md:50` ghi AI2 chỉ xử lý snapshot/query qua Backend, không gọi OCR; `EvidenceGap` trả Backend quyết định re-OCR.
- `docs/AI2-MENTOR-HANDOFF.vi.md:111` đã nêu version snapshot đang không thống nhất và cần mentor/Backend chốt.
- `docs/contracts/BE-AI2-PROCESSING-CONTRACT.vi.md:20` yêu cầu gửi snapshots đầy đủ để AI2 pair body–annex; `docs/ai2/AI2-12-review-and-release-gate.md:5,10` coi snapshot/profile là input thực tế và review gate là boundary.
- `ai-service/app/pipeline/index.py:6` và `ai-service/app/reasoning/stack.py:15` là code anchors cho proposal-only index và four-layer reasoning.

Kết luận quan sát được: không được “fix” thiếu evidence bằng suy đoán, không publish active index, không để L2 legal conclusion và không trả `ANSWERED` trước L3.

## Options và trade-off

### Option A — Chỉ sửa `/process` và `/query` metadata-only

- Ưu: ít thay đổi adapter.
- Nhược: không có evidence content/citation để grounding; vẫn fail-closed hoặc buộc AI2 đoán.
- Đánh giá: không đạt ST-044/045/046; loại.

### Option B — Dùng canonical `/jobs/idp`, lưu evidence projection theo digest rồi query trên projection

- Ưu: khớp contract hiện có, đủ dữ liệu cho body–annex và query, retry/idempotency/audit rõ, không cần gửi raw PDF.
- Nhược: cần thống nhất ownership/TTL/storage và invalidation khi snapshot đổi.
- Đánh giá: phù hợp nhất cho Sprint 2; chọn làm hướng mặc định.

### Option C — Đổi toàn bộ sang `ai1.snapshot.v3` và legacy result v2

- Ưu: bám một số tài liệu/backend cũ.
- Nhược: mâu thuẫn với canonical v1 code/tests/docs, mở rộng scope thành migration contract; rủi ro cao trong Sprint 2.
- Đánh giá: chỉ mở thành decision riêng sau EPIC-11; không chọn hiện tại.

## Ranked conclusion

1. **Chọn Option B:** giữ `be.ai2.processing.request.v1` + `ai1.snapshot.v1`, hoàn thiện canonical `/jobs/idp`, persist evidence/result theo digest, sau đó query L0→L3 grounded.
2. **Giữ embedding optional:** không block deterministic retrieval; đo recall/cost sau khi contract và citation gate xanh.
3. **Tách migration v3/v2:** ghi compatibility boundary và không âm thầm đổi version trong task này.

## Open questions cần mentor/owner duyệt

- Evidence projection do AI2 giữ với TTL nào, hay Backend gửi lại bounded evidence package cho mỗi query?
- Query result canonical schema/state đã chốt chưa, hay phase 4 cần tạo `ai2.query.result.v1`?
- Ai có quyền review/publish `IndexContribution` và Backend persist ở bảng nào?
- Test fixture/catalog bị thiếu trong checkout hiện tại là artifact ngoài scope hay cần owner khôi phục trước full-suite gate?
