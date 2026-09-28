# Nghiên cứu hiện trạng và hợp đồng liên quan

Ngày: 2026-09-24
Phạm vi: frontend AI2, backend review/approval, AI2 evidence-first và các hợp đồng hiện hành.

## Kết quả chính

### 1. Màn hình review trung tâm vẫn là mock/static

- `frontend/src/pages/DossierReviewPage.tsx:7-9, 43-64` đang lấy `sampleSearchQuery`, `auditTotalCount` và dữ liệu audit cục bộ; trạng thái tìm kiếm chỉ là local state.
- `frontend/src/pages/DossierReviewPage.tsx:302` render `DossierSearchResults` mà không truyền dossier id, query hoặc kết quả API.
- `frontend/src/components/DossierSearchResults.tsx:4-8, 91-98` đọc `searchAnswerText` và `searchCitations` từ `frontend/src/data/dossierSearch`, nên câu trả lời và citation trên màn hình này không phải kết quả AI2 live.
- `frontend/src/pages/DossierReviewPage.tsx:308-317` ghi rõ tab clause/risk hiện chỉ là placeholder.

Kết luận: ưu tiên đầu tiên của UI là đưa search/review trung tâm sang API thật, có loading/error/empty/evidence-gap state; không tiếp tục mở rộng mock copy.

### 2. API thật cho search, citation và review đã tồn tại một phần

- `frontend/src/api/structure.ts:464-515` đã có type `DossierSearchHit`, `DossierSearchResult` và hàm `searchDossier`.
- `backend/src/contract_intelligence/review/interfaces/api/routers/review_full_router.py:45-159` đã có queue review, detail, revisions và action `confirm/correct/reject/needs_more_evidence` với optimistic locking.
- `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:37-139` đã có lock, approve và external approval routes.

Kết luận: phase UI nên dùng các contract này trước; chỉ bổ sung backend DTO/endpoint khi evidence cho thấy contract hiện tại không đủ. UI phải hiển thị xung đột version/HTTP 409, không nuốt lỗi.

### 3. AI2 đã có nền evidence-first nhưng coverage free-form chưa đầy đủ

- `ai-service/app/reasoning/ask_assemble.py:103-149, 235-265` phân biệt `ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE` và chỉ trả lời từ structured facts có citation.
- `ai-service/app/reasoning/l0_rules.py:233-269, 322-350` fail closed khi thiếu bằng chứng; comparison khác scope/unit/currency được trả safe state.
- `ai-service/app/reasoning/l1_retrieval.py:190-202, 298-325` đã nhận diện từ khóa `penalty` và tìm structured key, nhưng nếu producer không tạo key phù hợp thì UI không thể tự biến kết quả text thành fact có thẩm quyền.
- `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md:1-8, 5` yêu cầu mọi câu trả lời có citation/trace và câu hỏi nhiều bước phải đi qua structure/relation/comparison.

Kết luận: UI phải hiển thị rõ trạng thái thiếu evidence, nguồn lỗi và review action. Coverage câu hỏi hợp đồng như phạt, nghĩa vụ, điều kiện, ngoại lệ cần một workstream semantic riêng, nhưng không được nới fail-closed thành phỏng đoán.

### 4. Release gate đã định nghĩa, nhưng hiện trạng không phải PASS mặc định

- `docs/ai2/AI2-12-review-and-release-gate.md` yêu cầu replay offline, strict citation validation, giữ `NEEDS_REVIEW` là trạng thái hợp lệ và không tự promote lên `PASS`.
- `docs/DOC-05b-frontend-backend-api-contract.md` quy định API `/api/v1`, auth/RBAC, tenant header, polling/realtime và các màn hình upload, pipeline, explorer, review, approval, re-OCR.
- `docs/contracts/ai2.service-envelope.v1.schema.json` và `docs/contracts/ai2.be.processing.result.v1.schema.json` là các schema cần giữ tương thích khi chuẩn hóa dữ liệu frontend.

Kết luận: release phase phải chạy full-stack smoke từ upload → OCR → AI1 → AI2 → query → citation → review; chỉ claim những gì có artifact kiểm chứng.

## Ràng buộc áp dụng

1. Không thay đổi model/provider AI2 trong kế hoạch này; dùng stack Docker hiện tại.
2. Không đưa dữ liệu dossier này sang dossier khác nếu không có scope/evidence rõ ràng.
3. Không hiển thị câu trả lời nghiệp vụ không có citation resolve được.
4. Không phá hoặc ghi đè thay đổi chưa commit của người dùng.
5. TypeScript phải có type rõ cho response API; dữ liệu ngoài boundary phải được validate trước khi dùng, theo `harness/standards/areas/STD-REVIEW-TS.std.yaml`.
6. Python backend/AI2 giữ typing, xử lý exception có chủ đích và test có marker, theo `harness/standards/areas/STD-REVIEW-PY.std.yaml`.

## Xếp hạng quyết định

1. **P0 — Search/review live:** loại bỏ dữ liệu mock trên màn hình hỏi đáp; hiển thị answer/hits/citations từ dossier đang chọn.
2. **P0 — Evidence interaction:** click citation phải mở đúng document/page/line/bbox; thiếu nguồn phải là trạng thái rõ ràng.
3. **P1 — HITL:** nối queue/detail/action/revision/lock/approve, gồm optimistic conflict.
4. **P1 — Contract analysis UI:** facts, structure, relations, comparison, risk và trạng thái review dùng dữ liệu evidence-backed.
5. **P1 — Full-stack release:** export có citation, lịch sử thao tác, health/env checks và replay/e2e gate.

## Sources

- `frontend/src/pages/DossierReviewPage.tsx:7-9, 43-64, 302, 308-317`
- `frontend/src/components/DossierSearchResults.tsx:4-8, 91-98`
- `frontend/src/api/structure.ts:464-515`
- `backend/src/contract_intelligence/review/interfaces/api/routers/review_full_router.py:45-159`
- `backend/src/contract_intelligence/review/interfaces/api/routers/approval_router.py:37-139`
- `ai-service/app/reasoning/ask_assemble.py:103-149, 235-265`
- `ai-service/app/reasoning/l0_rules.py:233-269, 322-350`
- `ai-service/app/reasoning/l1_retrieval.py:190-202, 298-325`
- `docs/ai2/AI2-12-review-and-release-gate.md`
- `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md`
- `docs/DOC-05b-frontend-backend-api-contract.md`
- `docs/contracts/ai2.service-envelope.v1.schema.json`
- `docs/contracts/ai2.be.processing.result.v1.schema.json`

## Kết luận

Kế hoạch nên là một master plan 5 phase: đóng băng contract evidence trước, nối search/review thật, triển khai HITL, mở các màn hình phân tích có citation, rồi chạy release gate full-stack. Các yêu cầu “hỏi mọi vấn đề hợp đồng” được đưa vào coverage semantic và structured-result tests; không xử lý bằng cách cho LLM trả lời tự do khi không có snapshot/citation.
