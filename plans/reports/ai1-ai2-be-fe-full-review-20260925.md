# Review toàn bộ AI1 → AI2 → Backend → Frontend

Ngày review: 2026-09-25  
Nhánh thực tế: `feature/ai2-integration`  
Commit HEAD: `44930a00ca864b77752b5462fe987166fa5d2ef9`  
Phạm vi: working tree hiện tại, gồm AI2, AI1 adapter, worker, persistence, API và FE. Đây không phải nhánh `feature/code-full` như tên được nhắc trước đó.

## Verdict: BLOCKED

Luồng hiện tại chưa đủ tin cậy để gọi là full production flow. Query yếu là triệu chứng của nhiều lỗi nối tiếp: AI2 nhận snapshot có line/chunk nhưng không sinh facts/findings; Backend chỉ chiếu một phần kết quả vào các bảng cũ; FE chỉ có màn Risk cho facts/findings và một màn đối soát static; ngoài ra route HITL/approve mô phỏng đang đứng trước route có RBAC thật.

## Findings theo mức độ

### C1 — Route mô phỏng che route có RBAC và persistence thật

`backend/src/contract_intelligence/main.py:325-332` đăng ký `hitl_reviews_router` và `hitl_dossiers_router` trước `review_router` và `approval_router`.

Route mô phỏng tại `backend/src/contract_intelligence/api/v1/reviews.py:22-36,56-74` dùng `_REVIEW_STORE` trong memory và không có `get_current_user`/RBAC. Route approve tại `backend/src/contract_intelligence/api/v1/dossiers.py:105-170` cũng không có dependency auth. Trong khi route thật tại `review_full_router.py:105-169` yêu cầu `REVIEWER/ADMINISTRATOR`, còn `approval_router.py:55-73` yêu cầu `ADMINISTRATOR`.

Bằng chứng live:

- `POST /api/v1/dossiers/dos_01M39XPA10F5B70J7VAHQXH0PG/approve` không có token trả `200 OK` và đổi trạng thái dossier.
- `POST /api/v1/review-items/probe-review-item/actions` không có token đi vào route mô phỏng và trả `409 VERSION_CONFLICT`, không phải `401/403`.

Đây là lỗi bảo mật và tính toàn vẹn dữ liệu: caller không xác thực có thể approve dossier hoặc thao tác review state không bền vững. Probe approve đã được hoàn tác về `extracted`, `is_approved=false`, `is_locked=false`; không thay đổi code sản phẩm.

### I1 — Kết quả AI2 bị mất phần context/evidence khi vào Backend

`backend/src/contract_intelligence/shared/ai/persistence.py:667-799` chỉ đọc `facts` và `findings`, sau đó ghi vào extraction/conflict read model. Nó không persist `context_findings`, `events`, `index_contribution.chunks`, `evidence_issues`, `annex_links` hoặc coverage.

Trong khi wire contract tại `ai-service/app/contracts/wire.py:248-347` có đầy đủ các trường trên. Vì vậy AI2 có thể đã tạo context/chunk/event nhưng FE không bao giờ nhìn thấy chúng.

Bằng chứng live từ `ci-ai2-service`:

- Test 2, job `job_bdeac5c7cb`: 58 chunks, 19 citations, 23 events, 0 facts, 0 findings.
- Test 1, job `job_9ccffa28cc`: 514 chunks, 74 citations, 90 events, 1 evidence issue, 0 facts, 0 findings.

Tab Risk tại `frontend/src/pages/DossierReviewPage.tsx:773-867` chỉ gọi facts/findings. Không có tab hoặc panel cho context findings, events, evidence issues, chunk coverage hay AI2 reasoning trace.

### I2 — Query backend hiện không có semantic runtime cho luồng canonical

`backend/src/contract_intelligence/shared/ai/canonical_processing.py:348-355` đặt `egress_allowed=false`. Luồng query canonical tại `ai-service/app/api/main.py:783-803` khởi tạo `QueryRouter(STORE, ToolGateway(STORE))` không truyền LLM hoặc vector service.

Ngoài ra:

- `ai-service/app/reasoning/vector_recall.py:181-186` mặc định vector theo `AI2_VECTOR_RECALL_ENABLED`; môi trường live hiện đang tắt vector.
- `ai-service/app/reasoning/query.py:117-143` chỉ nhận một danh sách intent hẹp rồi rơi vào `unscoped`.
- `ai-service/app/reasoning/l0_rules.py:227-237` xử lý `unscoped` bằng hint và kết thúc, không đi tiếp retrieval tổng quát.

Do đó câu hỏi tự nhiên như nghĩa vụ, điều kiện thanh toán, rủi ro, chấm dứt, trách nhiệm, quan hệ body–annex hoặc “hợp đồng này ảnh hưởng thế nào” không được xử lý như một câu hỏi context tổng quát. Đây giải thích trực tiếp hiện tượng trả lời yếu hoặc `AI2 chưa nhận được snapshot/citation...`.

### I3 — Backend làm mất trạng thái AI2, FE có thể hiển thị sai “đã trả lời”

AI2 trả `state`, `retrieval_layer`, `reasoning_trace` tại `ai-service/app/api/main.py:792-803`. Nhưng DTO search Backend tại `backend/src/contract_intelligence/contract/interfaces/api/routers/contract_router.py:617-622` chỉ còn `query`, `answer`, `connected`, `hits`; phần dựng response tại `:710-717` luôn đặt `connected=True` khi HTTP request thành công.

FE tại `frontend/src/api/ai2.ts:152-161` sẽ suy ra `ANSWERED` nếu có answer và hit khi `review_state` đã bị Backend loại bỏ. Như vậy `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE` hoặc `BLOCKED` có thể bị biến thành trạng thái hiển thị không chính xác.

### I4 — Nút “Đối soát” đang mở màn hình static, không mở citation của dossier

`frontend/src/components/DossierSearchResults.tsx:81-88` chỉ truyền `citation` vào `/doi-soat-trich-dan`. Nhưng `frontend/src/pages/CitationComparePage.tsx:10-38` dùng dữ liệu hard-code; phần save tại `:44-50` chỉ đổi state bằng `setTimeout`, không gọi Backend.

Màn `CitationSplitViewPage` cũng là demo static: `frontend/src/pages/CitationSplitViewPage.tsx:168-223` hard-code dossier `#DOS-2024-884`, version `v3.2`, page và citation từ `splitCitations`. Đây là lý do người dùng bấm xem nguồn nhưng không thấy nguồn thật của `dos_01M38T3PD2Z45CJXGS6FQGKSWX`.

Ngoài ra `DossierStructurePage.tsx:351-355` từ chối citation nếu `sourceFileId` khác document đang mở. Citation của annex vì vậy không có document selector để mở đúng file.

### I5 — Test 1/2 pipeline “succeeded” nhưng read model cho UI rỗng

Bằng chứng DB live sau khi pipeline kết thúc:

| Dossier | Pipeline/AI2 | Facts | Findings | Review items |
|---|---|---:|---:|---:|
| `dos_01M39XPA10F5B70J7VAHQXH0PG` | succeeded / `NEEDS_REVIEW` | 0 | 0 | 0 |
| `dos_01M39XXAHPTZGW1X5RCTEWT52F` | succeeded / `PASS` | 0 | 0 | 0 |
| `dos_01M38T3PD2Z45CJXGS6FQGKSWX` | extracted | 1 | 0 | 1 |

`pipeline_step` vẫn ghi `S4-S10 succeeded` dù metrics AI2 là `facts: 0, findings: 0`. Điều này làm status pipeline xanh nhưng không đảm bảo dữ liệu mà UI cần đã được tạo. Cần phân biệt “service chạy xong” với “evidence/read model đủ dùng”.

### I6 — AI2 phụ thuộc cache snapshot trong memory của Backend

`backend/src/contract_intelligence/worker.py:65` khai báo `_snapshot_cache` trong process memory. `:401-417` lấy snapshot từ cache để build request; nếu worker restart giữa AI1 completed và manifest confirmed, DB vẫn có snapshot nhưng cache rỗng, AI2 chỉ log `waiting_for_snapshots` rồi return.

Không có cơ chế hydrate lại cache từ DB hoặc retry/reconcile durable. Đây là lỗi reliability, đặc biệt với worker restart/redeploy.

### I7 — ACL của query dossier chỉ kiểm tra tenant, không kiểm tra quyền trên dossier

`backend/src/contract_intelligence/api/v1/dossiers.py:74-102` kiểm tra `dossier.tenant_id == user.tenant_id`. Query endpoint gọi thẳng `_acl_check_dossier_access` tại `:184-191`. Search endpoint khác lại dùng `_require_readable` tại `contract_router.py:680`, nên hai đường query có policy khác nhau.

Nếu hệ thống có chia sẻ dossier theo user/role, mọi user cùng tenant có thể gọi endpoint query trực tiếp dù không được share dossier. Cần dùng một ACL service duy nhất cho cả hai đường.

### I8 — Có hai kiến trúc AI service cùng tồn tại, dễ chạy nhầm đường stub/legacy

`docker-compose.yml:323-327` đặt `AI_SERVICE_MODE: stub`. Client cũ tại `backend/src/contract_intelligence/shared/ai/client.py:407-415` có thể chọn stub; HTTP client cũ gọi `/api/v1/jobs/ocr` tại `:323`, trong khi AI2 từ chối OCR tại `ai-service/app/api/main.py:825-833` vì OCR thuộc AI1. Endpoint `/process` tại `ai-service/app/api/main.py:666-674` cũng chỉ là compatibility lane metadata-only.

Worker canonical hiện có đường Kafka/AI1 snapshot → AI2, nhưng các API cũ vẫn tồn tại và tên cấu hình khiến “full” không có một execution path duy nhất. Cần loại bỏ hoặc đánh dấu rõ legacy path khỏi runtime production.

## Chức năng đang thiếu trên UI

1. Bảng/khung `context findings`: quan hệ body–annex, event, dependency, bảng nối trang và evidence issue.
2. Fact extraction thật theo toàn bộ contract fields, không chỉ các fact đã lọt vào bảng `fact`.
3. Trạng thái AI2 chi tiết: `PASS`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`, retrieval layer và reasoning trace.
4. Finding queue chính thức với severity, hai phía evidence, review action, version conflict và revision audit từ DB.
5. Citation viewer động theo `dossier_id`, `document_id`, page/line/bbox; hiện chưa mở đúng annex và còn màn demo static.
6. Query tổng quát có lexical/vector/semantic fallback cho các câu hỏi không khớp intent hẹp.
7. Error/coverage panel cho trường hợp OCR có line nhưng thiếu table/node/citation hoặc AI2 tạo 0 fact.
8. Full authenticated E2E upload → OCR → AI1 → AI2 → query → review → approve bằng Keycloak token. Luồng này chưa được chạy live trong review vì chưa có token hợp lệ và không được giả thành PASS.

## Thứ tự xử lý đề xuất

### P0

- Xóa hoặc tách hẳn simulated HITL routes khỏi production registration; chỉ giữ một route review/approve có auth, RBAC, DB transaction, tenant/dossier ACL.
- Thêm test unauthenticated cho mọi mutation: phải trả `401/403`, không được tạo item mới trong memory.
- Chuẩn hóa adapter `ai2.be.processing.result.v1`: persist events, context findings, evidence issues, chunks, annex links và coverage; không silently skip fact/finding thiếu citation mà phải tạo review/error metric.
- Không cho pipeline báo “thành công đủ dùng” khi read model có 0 facts/findings/citations ngoài trường hợp contract thực sự không có dữ liệu.

### P1

- Giữ `state`, `retrieval_layer`, `reasoning_trace`, `evidence_issues` trong Backend DTO và FE.
- Cho intent không khớp đi qua lexical retrieval trước khi trả hint; bật vector theo policy runtime khi có embedding/index; chỉ gọi LLM khi policy cho phép và phải thể hiện rõ `used_llm`.
- Thay hai màn citation static bằng màn dùng dossier/document/citation thật; thêm chọn tài liệu body/annex.
- Hợp nhất ACL query/search theo dossier sharing policy.

### P2

- Hydrate snapshot từ DB khi worker khởi động và có reconciler cho manifest-confirmed nhưng AI2 chưa submit.
- Loại bỏ hoặc cô lập `AI_SERVICE_MODE=stub`/legacy OCR client khỏi đường production.
- Bổ sung metric: input pages/lines/tables, output chunks/citations/facts/findings, dropped records, evidence issue count và reason code.

## Verification đã chạy

- Docker stack: backend, AI2, DB và các worker đang running; backend/AI2 health OK.
- AI2 targeted tests: `55 passed`.
- Backend targeted tests: `27 passed`.
- FE `npm run build`: PASS.
- FE `npm run lint`: `0 errors`, `7 warnings`.
- `git diff --check`: không có whitespace error mới, nhưng worktree có nhiều thư mục pytest bị permission denied.
- Security scan: dừng ở `leak_found` vì scanner bắt pattern `basic-auth-url` trong chính `harness/hooks/secret_scan_before_ship.py`; không phát hiện tracked `.env` (`tracked_env_files: 0`, `.gitignore` đang cover env). Vì scan không đạt PASS nên security ceremony vẫn chưa hoàn tất.
- Full authenticated E2E: NOT_RUN.

## Ghi chú về artifact

Không sửa code sản phẩm. Báo cáo này là review toàn bộ dirty worktree hiện tại. Plan `260924-2352-ai2-ui-completion` đã ở trạng thái completed và artifact PASS trước đó chỉ ghi cho một diff FE hẹp; tôi không ghi đè artifact lịch sử đó bằng verdict của review toàn bộ này.
