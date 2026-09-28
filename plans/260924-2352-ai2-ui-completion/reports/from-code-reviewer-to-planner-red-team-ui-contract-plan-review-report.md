# Red-team report — AI2 UI completion plan

Ngày: 2026-09-24
Verdict: **CONDITIONALLY APPROVABLE** — hướng đi đúng, nhưng cần khóa các khoảng trống test harness, upload/pipeline ownership, persistence và xung đột file trước khi cook.

## Findings

### High — Frontend TDD chưa có test runner

`frontend/package.json` hiện chỉ có `build`, `lint`, `format`, `preview`; không có Vitest/RTL/Playwright và repo không có frontend test files. Phase 1–4 yêu cầu component/behavior tests nhưng chưa khai báo bước cài hoặc lựa chọn runner.

**Ảnh hưởng:** “TDD xanh” không thể chạy, acceptance trở thành claim không kiểm chứng.

**Sửa trong plan:** Phase 1 phải chọn một test strategy (ưu tiên Vitest + Testing Library nếu phù hợp stack), thêm script/dependency/config và test smoke tối thiểu; nếu không thêm dependency thì ghi rõ kiểm thử manual/E2E thay thế và không gọi là unit TDD.

### High — Upload/OCR/pipeline chưa có owner implementation

Plan acceptance yêu cầu upload → OCR → AI1 → AI2, nhưng Phase 5 chỉ thêm smoke script; phase graph không khai báo frontend upload/pipeline page hoặc backend run/status client là files_to_modify.

**Ảnh hưởng:** có thể “kiểm thử” một đường dẫn chưa được nối, không giải quyết lỗi người dùng đang gặp `MISTRAL_API_KEY is not set`/OCR retry.

**Sửa trong plan:** thêm inventory và owner rõ cho upload, dossier creation, run status, retry OCR, env diagnostic; hoặc hạ acceptance này thành precondition đã có và ghi out-of-scope phần UI chưa tồn tại.

### High — History/export chưa có persistence contract

Phase 5 nói lưu query/action history và export nhưng chưa chỉ ra API/database route, DTO, migration hay backend owner. `frontend/src/data/auditLog` hiện là dữ liệu cục bộ được `DossierReviewPage` dùng.

**Ảnh hưởng:** dễ tạo export đẹp nhưng không phải audit/history canonical.

**Sửa trong plan:** chọn rõ reuse backend audit/revision API hay thêm endpoint/schema; nếu chỉ export phiên hiện tại thì đổi wording acceptance, không gọi là history persisted.

### High — Xung đột file giữa Phase 3 và Phase 4

Cả `phases/phase-3-hitl.md` và `phases/phase-4-analysis.md` đều sửa `frontend/src/pages/DossierReviewPage.tsx`; graph cho phép hai phase này cùng một batch sau Phase 2 vì không có cạnh giữa chúng.

**Ảnh hưởng:** parallel cook có thể overwrite hoặc tạo merge conflict.

**Sửa trong plan:** thêm edge Phase 3 → Phase 4 hoặc tách page shell khỏi feature components và cập nhật ownership.

### Medium — Structured analysis đang quá rộng so với contract inventory

Phase 4 yêu cầu facts, structure, relations, comparison, risk và semantic routing nhưng chưa liệt kê endpoint/DTO thật cho relations/comparison/risk. Chỉ có evidence hiện trạng cho structure/search/review.

**Ảnh hưởng:** phase có thể phình thành một dự án mới và không có definition of done đo được.

**Sửa trong plan:** chia P1 thành các output có endpoint tồn tại; các endpoint thiếu phải có discovery/contract task hoặc hạ thành P2, với số màn hình và fixture cụ thể.

### Medium — Runtime validation chưa nêu thư viện hiện có

Phase 1 yêu cầu runtime validation theo chuẩn TypeScript nhưng `frontend/package.json` chưa có Zod/Yup/io-ts. Kế hoạch chưa quyết định thêm dependency hay viết validator thủ công.

**Sửa trong plan:** chốt lựa chọn và test failure mode; không để `as` cast quay lại trong implementation.

### Medium — RBAC/auth client chưa có touchpoint

Backend contract yêu cầu Bearer token và `X-Tenant-Id`, nhưng Phase 2/3 không nêu API client sẽ lấy token, tenant context, refresh hay map 401/403.

**Sửa trong plan:** thêm auth/tenant boundary vào Phase 1 và test 401/403/tenant mismatch trong Phase 2/3.

## Premortem

Nếu kế hoạch thất bại, xác suất cao nhất là: (1) UI search được nối nhưng route không có dossier id; (2) citation hiển thị text nhưng source viewer không nhận đủ page/line/bbox; (3) reviewer action thành công giả do không refetch canonical state; (4) semantic coverage bị đánh giá bằng câu trả lời trôi chảy thay vì evidence; (5) full-stack smoke bị bỏ qua vì env/provider thiếu.

## Required plan edits before approval

1. Chốt frontend test strategy và command thật.
2. Bổ sung owner cho upload/OCR/retry/pipeline hoặc thu hẹp acceptance.
3. Chốt persistence contract cho history/export.
4. Sửa graph conflict Phase 3/4.
5. Tách Phase 4 thành deliverables có endpoint/fixture/gate cụ thể.
