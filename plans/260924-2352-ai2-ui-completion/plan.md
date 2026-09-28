---
id: 260924-2352-ai2-ui-completion
title: "Hoàn thiện chức năng AI2 trên UI"
status: completed
mode: hard
tdd: true
branch: feature/ai2-integration
created: 2026-09-24
author: user:dungskbg2004@gmail.com
decisions:
  - "Giữ một master plan 5 phase; không tách thành 20 plan do sizing tổ hợp lifecycle/stakeholder/risk."
  - "Dùng API và schema hiện có trước; chỉ mở rộng backend khi contract evidence chứng minh thiếu."
  - "Giữ fail-closed: không có citation resolve được thì không trình bày như câu trả lời đã xác minh."
phases:
  - phases/phase-1-contract.md
  - phases/phase-2-search-review.md
  - phases/phase-3-hitl.md
  - phases/phase-4-analysis.md
  - phases/phase-5-release.md
harness_version: 6.3.0
harness_schema_version: 1.0
---

# Plan: Hoàn thiện chức năng AI2 trên UI

## Tổng quan

Đưa AI2 từ trạng thái chỉ hỏi đáp cục bộ/mock sang một workflow sử dụng được trên UI: người dùng upload hồ sơ, theo dõi OCR/AI1/AI2, hỏi mọi vấn đề trong phạm vi hợp đồng, xem câu trả lời có citation mở được nguồn, xem fact/structure/relation/risk/comparison, thực hiện review HITL và tạo kết quả có thể kiểm tra khi release. Nền AI2 evidence-first, Docker stack và các API review hiện có được giữ nguyên làm nền.

Hiện trạng đã xác nhận: `frontend/src/pages/DossierReviewPage.tsx:43-64,302,308-317` và `frontend/src/components/DossierSearchResults.tsx:4-8,91-98` còn dùng dữ liệu static; ngược lại `frontend/src/api/structure.ts:464-515` đã có search thật, backend review đã có queue/action/revision tại `backend/src/contract_intelligence/review/interfaces/api/routers/review_full_router.py:45-159`, và AI2 đã có safe states/citation tại `ai-service/app/reasoning/ask_assemble.py:103-149`.

Complexity: complex · 5 phase · rủi ro chính là UI/API contract drift, review-state/optimistic-lock integration và tính toàn vẹn evidence qua upload → OCR → AI1 → AI2 → FE.

## Quyết định đã khóa

- Giữ toàn bộ code và thay đổi chưa commit của người dùng; không reset, không commit/push trong plan.
- AI2 chạy cùng Docker stack hiện tại; không đổi provider/model trong scope này.
- Mọi câu trả lời nghiệp vụ phải có citation/trace; thiếu nguồn phải hiện `INSUFFICIENT_EVIDENCE` hoặc `NEEDS_REVIEW`.
- Scope truy vấn mặc định là tenant → dossier → document/annex được chọn → bounded evidence.
- Không tự suy ra tư cách pháp lý, bên thắng, precedence hoặc quan hệ body–annex khi evidence chưa đủ.

## Ràng buộc (constraint-scan)

- Contract frontend/backend: `docs/DOC-05b-frontend-backend-api-contract.md`; giữ `/api/v1`, auth/RBAC, tenant header, error envelope và polling/realtime.
- Contract AI1/AI2: `docs/contracts/ai1.snapshot.v1.schema.json`, `docs/contracts/ai2.service-envelope.v1.schema.json`, `docs/contracts/ai2.be.processing.result.v1.schema.json`.
- Release safety: `docs/ai2/AI2-12-review-and-release-gate.md`; `NEEDS_REVIEW` không được promote ngầm thành `PASS`.
- Product behavior: `docs/ai2/AI2-15-contract-profiles-structure-relations-and-free-form-qa.vi.md`; không dùng câu hỏi tự do để bypass scope hoặc evidence.
- TypeScript/React: type rõ public shapes, validate boundary, server state qua data-fetching layer theo `harness/standards/areas/STD-REVIEW-TS.std.yaml`.
- Python: typing, exception handling, no hardcoded secret, test marker theo `harness/standards/areas/STD-REVIEW-PY.std.yaml`.

## Features

1. **Theo dõi pipeline hồ sơ:** dùng flow hiện có trong `frontend/src/pages/CreateDossierPage.tsx`, `frontend/src/pages/AnalysisProgressPage.tsx` và `frontend/src/api/dossiers.ts`; upload, OCR, AI1, AI2, retry và lỗi hiển thị theo trạng thái thật.
2. **Hỏi đáp hợp đồng có nguồn:** query theo dossier, answer/hits/review state/citations từ API thật; click nguồn mở đúng document/page/line/bbox.
3. **Kết quả hợp đồng có cấu trúc:** facts/fields, structure, annex, relations, comparison và risk đều có evidence và safe state.
4. **Review HITL:** queue, detail, confirm/correct/reject/needs-more-evidence, revisions, lock/approve và xử lý xung đột phiên bản.
5. **Lịch sử và xuất kết quả:** dùng audit/revision canonical hiện có cho action history; export phiên query/review hiện tại với citation. Query history persisted chỉ làm nếu đã có API/database contract, không tạo local-only audit giả.
6. **Release full-stack:** health/env diagnostics, replay, test/build gate và smoke từ upload đến review.

## Phases

| # | Theme | Phụ thuộc | Kích cỡ | Gate |
|---|---|---|---|---|
| 1 | Contract & evidence model | none | M | DTO/schema map và test boundary xanh |
| 2 | Search & review live | 1 | L | Màn hình hỏi đáp dùng dossier/query thật, citation mở được |
| 3 | HITL review & approval | 1, 2 | L | Action/revision/lock/approve và 409 conflict được kiểm thử |
| 4 | Structured analysis & coverage | 1, 2 | XL | Fact/structure/relation/risk/comparison không bịa; câu hỏi không structured có safe fallback |
| 5 | Release & operations | 2, 3, 4 | L | Full-stack smoke, replay, build/test, Docker/env/secret checks |

## Out of scope

- Đổi model/provider, huấn luyện model mới hoặc xây vector database mới.
- Thiết kế lại toàn bộ visual system/mobile app/voice assistant.
- Cross-dossier search hoặc suy luận giữa hai hồ sơ độc lập.
- External approval provider mới; chỉ nối UI vào external approval API hiện có nếu contract đã đủ.
- Tự động phán quyết pháp lý, chọn “bên đúng”, `LEGAL_WINNER` hoặc promote accuracy khi chưa có golden set do reviewer xác nhận.

## Acceptance (toàn plan)

- [ ] Upload một dossier mới và nhìn thấy trạng thái OCR → AI1 → AI2 thật; lỗi cấu hình/API có hướng xử lý rõ, không còn `MISTRAL_API_KEY is not set` bị che trong UI.
- [ ] Hỏi các nhóm: party, giá trị/thời hạn/thanh toán, nghĩa vụ/điều kiện, phạt/rủi ro, annex/comparison; câu trả lời hoặc safe state đều có citation/trace tương ứng.
- [ ] Click mọi citation locatable mở đúng tài liệu/trang/line/bbox; citation lỗi/thiếu được đánh dấu và không hiển thị như nguồn hợp lệ.
- [ ] Review action cập nhật trạng thái, ghi revision, tôn trọng RBAC và trả lỗi rõ khi `base_version` cũ.
- [ ] Fact/structure/relation/risk/comparison hiển thị đúng scope document/annex; khác scope/unit/currency trả `NOT_COMPARABLE`.
- [ ] Export giữ query, dossier, answer, review state và citations; action history lấy từ audit/revision canonical. Nếu chưa có query-history persistence contract thì phải ghi rõ `not available`, không giả lập bằng local state.
- [ ] Mỗi phase có red → green tests; cuối plan chạy frontend build, backend tests, AI2 offline suite và full-stack smoke/replay.

## Rollback

Mỗi phase là một change set độc lập. Nếu gate phase fail, dừng ở phase đó, giữ artifact/test evidence, revert riêng change set của phase sau khi xác định target; không dùng `git reset --hard` và không đụng các thay đổi có sẵn của người dùng. Có thể tắt feature flag UI để quay về màn hình cấu trúc/search hiện hành trong thời gian sửa lỗi.

## Risks và mitigation

- **Mock còn sót:** cấm import `sampleSearchQuery/searchAnswerText/searchCitations` trong live review path; thêm test/rg check.
- **Contract drift:** chuẩn hóa DTO một lần ở API layer, validate response boundary và test fixture theo schema.
- **Citation không mở được:** chỉ enable link khi có source_file_id + line/page/bbox hợp lệ; hiển thị evidence gap thay vì fallback text.
- **Semantic coverage thiếu:** bổ sung structured keys/query routing và fixtures; không cho LLM tự điền giá trị khi không có snapshot.
- **Race condition review:** gửi `base_version`, xử lý 409 bằng reload/merge UI; test idempotency và retry.
- **Secret/env lỗi:** health check kiểm tra presence/mapping nhưng không log giá trị secret; Docker smoke chạy trong profile thật.
- **False accuracy claim:** tách candidate corpus, reviewed golden set, failed/not-run theo AI2-12.

## Tài liệu nghiên cứu

- `research/current-state-and-contracts.md`
- `artifacts/scope-sizing.json`
