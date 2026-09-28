# Scout Report — AI2 ST-044–ST-047 hiện trạng

Ngày: 2026-09-24
Phạm vi: read-only audit `ai-service`, Backend adapter/worker và contract docs.

## Kết luận nhanh

AI2 đã có phần lớn core logic cho cả 4 task. ST-044, ST-045 và ST-047 đã có implementation đáng kể; ST-046 có engine L0→L3 nhưng đường query Backend hiện vẫn fail-closed vì Backend gửi metadata-only vào `/query`. Vì vậy đây chưa phải trạng thái “full task hoàn tất E2E”.

## ST-044 — Validate handoff snapshot + relation graph

### Đã làm

- Wire contract canonical `be.ai2.processing.request.v1` yêu cầu `ai1.snapshot.v1`; schema/identity/digest/membership được kiểm tra tại `ai-service/app/contracts/wire.py:53,107,121-123` và `ai-service/app/pipeline/ai1_snapshot_adapter.py:275-311`.
- P1 vừa bổ sung guard DTO để từ chối snapshot version khác `ai1.snapshot.v1` tại `ai-service/app/contracts/wire.py:123`, kèm test `ai-service/tests/test_processing_wire_contract.py:239-250`.
- Handoff gate không nhận PDF bytes, kiểm tra lifecycle, version pins, page inventory, page quality và node status tại `ai-service/app/pipeline/handoff.py:26-124`.
- Relation graph được tạo trong processing path tại `ai-service/app/pipeline/idp.py:110` và hỗ trợ `PARENT_OF`, `SAME_CLAUSE`, `REFERENCES`, `AMENDS`, `DEFINES`, `USES_DEFINED_TERM` cùng citation/issues tại `ai-service/app/reasoning/relations.py:128-326`.

### Chưa thể coi là hoàn tất

- Full verification bị chặn bởi dependency/fixture và môi trường test.
- Digest/provenance được kiểm tra qua canonical adapter/wire boundary; không nên hiểu `HandoffValidator` đơn lẻ là nơi tự tính lại toàn bộ digest.

Đánh giá: **Core đã làm — chưa đạt E2E verification.**

## ST-045 — Extract fact/finding có citation + pair body–annex

### Đã làm

- `FactExtractor` tạo raw value, normalized value, subject/context, unit/currency, validity/condition/tax basis, citation, provenance và source role tại `ai-service/app/pipeline/fact.py:13-67`.
- `Fact` bắt buộc `raw_value` không rỗng và có citation tại `ai-service/app/contracts/models.py:438-468`.
- `CandidatePairer` gọi compare pipeline tại `ai-service/app/pipeline/candidate.py:7-17`.
- Pair body–annex theo `source_role`, `item_key/scope`, context và validity; xử lý mismatch currency/unit/scope/condition/period tại `ai-service/app/pipeline/compare.py:34-260`.
- Mỗi candidate/finding có `model_disposition`; `LEGAL_WINNER` bị cấm tại `ai-service/app/contracts/models.py:464-477`.
- Citation/evidence issues được đưa vào result tại `ai-service/app/pipeline/idp.py:221-260` và serialize thành canonical wire result tại `ai-service/app/contracts/wire.py:236-385`.

Đánh giá: **Core đã làm khá đầy đủ — Backend/full-suite verification chưa hoàn tất.**

## ST-046 — L0→L3 query reasoning + grounding

### Đã làm trong AI2 core

- `FourLayerReasoner` điều phối L0 → L1 → L2 khi cần → L3 tại `ai-service/app/reasoning/stack.py:15-189`.
- L1 có exact label, structured keys, semantic/BM25-like retrieval và bảo toàn exact hits tại `ai-service/app/reasoning/l1_retrieval.py:63-182`.
- L2 chỉ được gọi cho nhóm compare/cascade tại `ai-service/app/reasoning/stack.py:99-107`.
- L3 kiểm tra citation/node/span, claim grounding và hạ `ANSWERED` xuống `NEEDS_REVIEW` nếu chưa grounded tại `ai-service/app/reasoning/l3_ground.py:13-236`.
- Vector/embedding là optional, có disabled/budget/egress/provider/model-dimension gate tại `ai-service/app/reasoning/vector_recall.py:169-304`; feature flag mặc định tắt tại `ai-service/app/reasoning/vector_recall.py:181`.

### Gap lớn hiện tại

- Endpoint Backend-facing `/query` vẫn trả `INSUFFICIENT_EVIDENCE` tại `ai-service/app/api/main.py:669-696`.
- Backend dossier query vẫn gọi `query_ai2()` với metadata-only payload tại `backend/src/contract_intelligence/api/v1/dossiers.py:184-222`, adapter gửi tới `/query` tại `backend/src/contract_intelligence/infrastructure/ai_adapters.py:281-302`.
- Do đó FourLayerReasoner có thể chạy ở internal/demo/session paths, nhưng chưa chứng minh được query thực tế từ Backend đi xuyên L0→L3.

Đánh giá: **AI2 reasoning engine đã có; Backend query integration chưa hoàn tất.**

## ST-047 — Propose IndexContribution, chờ Backend/reviewer gate

### Đã làm

- `IndexStore.propose()` lọc fact/candidate không đủ evidence, append contribution và luôn đặt `publish="propose"`; không đổi `active_pointer` tại `ai-service/app/pipeline/index.py:6-45`.
- `IndexContribution` khóa kiểu publish chỉ còn `propose` tại `ai-service/app/contracts/models.py:533-547`.
- Canonical result serialize `index_contribution.state="propose"` tại `ai-service/app/contracts/wire.py:330-385`.
- Backend worker đã submit/poll canonical `/jobs/idp` và gọi `persist_ai2_processing_result()` tại `backend/src/contract_intelligence/worker.py:382-410`.
- Persistence adapter map facts/findings/citations về Backend tables tại `backend/src/contract_intelligence/shared/ai/persistence.py:659-790`.

### Chưa thể coi là hoàn tất

- Chưa có verification E2E xanh chứng minh reviewer/publish gate sau persistence; full Backend test bị chặn bởi Python/uv environment.
- AI2 hiện chứng minh được “không tự publish”; quyền publish active vẫn phải được Backend/reviewer gate kiểm chứng riêng.

Đánh giá: **AI2 proposal đã làm — reviewer/publish E2E chưa được chứng minh.**

## Test probe hiện tại

- Contract targeted sau P1: **34 passed**.
- Bộ test liên quan handoff/relation/facts/query/index: **81 passed, 2 errors**.
- Hai error nằm ở vector tests do `PermissionError: C:\Users\dungs\AppData\Local\Temp\pytest-of-dungs`, không phải assertion failure.
- Full suite trước đó vẫn bị collection errors do thiếu module/dependency; Backend `uv` không khởi động được interpreter.

## Trạng thái tổng hợp

| Task | Core implementation | Backend E2E | Kết luận |
|---|---|---|---|
| ST-044 | Có | Chưa đủ gate | Đã làm phần lớn |
| ST-045 | Có | Persistence có, full verify chưa | Đã làm phần lớn |
| ST-046 | Có trong internal AI2 | `/query` Backend còn fail-closed | Chưa hoàn tất |
| ST-047 | Có proposal-only | Reviewer/publish E2E chưa verify | Chưa hoàn tất |

## Open blockers

1. Chốt và triển khai evidence context/projection để Backend query không còn metadata-only.
2. Khôi phục test dependencies/fixtures và quyền temp/cache của pytest.
3. Tạo Backend test environment chạy được `uv run pytest` hoặc Python environment tương đương.
4. Chạy E2E canonical processing + query + persistence trước khi tiếp tục cook P2.
