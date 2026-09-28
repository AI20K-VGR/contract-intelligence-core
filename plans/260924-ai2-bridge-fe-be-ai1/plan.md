---
id: 260924-ai2-bridge-fe-be-ai1
title: "AI2 compatibility facade cho Backend hiện tại"
status: draft
mode: hard
tdd: true
deep: true
created: 2026-09-24
scope: "chỉ ai-service/; Backend feature/backend-setup và FE giữ nguyên"
---

# Implementation plan: kết nối AI2 vào FE–BE–AI1

## 1. Outcome khóa

Sau khi hoàn thành, AI2 sẽ có compatibility facade để Backend hiện tại gọi được mà không sửa Backend/FE:

`BE legacy client → AI2 compatibility facade → AI2 canonical/internal pipeline → legacy-shaped result → BE hiện tại`.

Compatibility facade chạy song song với canonical `/jobs/idp`. Không sửa Backend/FE, không thay đổi AI2 canonical contract, và không giả vờ rằng request legacy có đầy đủ provenance như canonical request.

## 2. Phạm vi và ranh giới

### Trong phạm vi

- AI2 facade cho các endpoint legacy mà Backend hiện tại đang gọi.
- AI2 orchestration map legacy OCR/extract/compare jobs vào pipeline hiện tại.
- Legacy-shaped response giữ các field mà Backend hiện tại cần.
- Giữ toàn vẹn `document_id`, `snapshot_id`, digest, role contract/annex, citation và evidence gap.
- Feature flag, idempotency, correlation, retry an toàn, cancellation/timeout ở boundary.
- Test contract, integration, AI2 E2E tối thiểu và rollback.

### Ngoài phạm vi của lần nối đầu tiên

- Không sửa logic nghiệp vụ AI1.
- Không thay đổi algorithm L0→L3, relation graph, fact extraction, grounding hoặc IndexContribution trong AI2.
- Không sửa Backend, FE, AG-UI/A2UI, SSE/WebSocket, multi-reviewer hoặc durable worker production mới trong phase nối này.
- Không cho AI2 nhận raw PDF.
- Không publish active index tự động.
- Không hiển thị chain-of-thought/token stream; chỉ hiển thị trạng thái, finding, citation, evidence gap và action được phép.
- Không migration phá vỡ schema/read API hiện có.

## 3. Evidence từ codebase và branch snapshot

### Nhánh được yêu cầu

- Chỉ sửa `ai-service/`; Backend `feature/backend-setup` và FE giữ nguyên.

- `origin/feature/backend-setup` tại `e184dbc` — backend pipeline, auth, persistence, run API và client AI cũ.
- `origin/feature/frontend-setup` chỉ được ghi nhận để xác nhận FE boundary; không sửa trong implementation scope lần này.
- Nhánh làm việc AI2 hiện tại: `feature/ai2-integration` tại `8ea7a36` — canonical AI2 `/jobs/idp`, wire contract và pipeline semantics.

Không checkout các nhánh trên vì working tree đang có thay đổi của người dùng.

### Đã biết chắc

1. Backend snapshot hiện gọi một AI service cũ qua các endpoint riêng:
   - `/api/v1/jobs/ocr`
   - `/api/v1/jobs/reocr`
   - `/api/v1/jobs/extract`
   - `/api/v1/jobs/compare`
2. Backend cũ truyền extract chủ yếu `document_text_nfc`, `clause_tree` và schema keys; không truyền canonical snapshot đầy đủ mà AI2 hiện tại yêu cầu.
3. AI2 hiện tại nhận một request dossier-level có nhiều snapshot, identity/digest, dossier members, role relation map và policy flags.
4. AI2 hiện tại yêu cầu signed `ai2.service-envelope.v1` khi submit và poll; header cũ `X-Internal-Service-Key` không đủ để gọi trực tiếp endpoint canonical.
5. AI2 trả một combined result gồm facts, findings/citations, evidence gaps và proposed index contribution; backend cũ đang persist các output extraction/comparison riêng.
6. Backend có auth, tenant/service boundary và persistence riêng; FE không được gọi trực tiếp AI2.

### Inference cần kiểm chứng trong implementation

- AI1 output `ai1.snapshot.v3` có thể được chuyển losslessly sang `ai1.snapshot.v1` chỉ khi đủ page/block/table/citation metadata. Nếu thiếu, adapter phải giữ missing-evidence state, không tự điền.
- Một dossier có thể có nhiều logical document; pairing body–annex phải lấy từ role relation map/context của BE, không suy ra chỉ từ thứ tự mảng.
- FE sẽ không là acceptance surface của lần này; khả năng hiển thị canonical result trên FE để phase sau.

### Dữ liệu còn thiếu

- Fixture AI1 thật chuẩn hóa cho cả body-only và body+annex với đầy đủ digest/citation.
- Quy ước env/secret legacy auth nếu Backend bật internal service key.
- Ground truth nghiệp vụ để đánh giá độ đúng của fact/finding; phase này chỉ có thể kiểm tra contract, provenance và trạng thái.

## 4. Nghiên cứu và constraint scan

### Phương án đã xem xét

| Phương án | Mô hình | Ưu điểm | Rủi ro/failure mode | Quyết định |
|---|---|---|---|---|
| A. AI2 facade tương thích API cũ | AI2 mở thêm `/api/v1/jobs/extract` và `/compare`, backend gần như không đổi | Ít đổi backend caller | Extract request cũ thiếu full snapshot/role/digest; citation có thể không authoritative; tạo hai contract semantics | Không chọn làm đường chính |
| B. Backend canonical adapter/client | BE giữ orchestration cũ, thêm mode canonical để dựng request dossier-level và gọi `/jobs/idp` | Đúng boundary FE→BE→AI; đủ context/citation; rollback bằng flag; giữ pipeline cũ | Cần mapping request/result và ký envelope; cần additive persistence | **Khuyến nghị** |
| C. FE gọi trực tiếp AI2 | FE submit/poll AI2 | Nhanh cho demo | Lộ service credential, phá tenant/auth, mất persistence/audit | Loại bỏ và ngoài scope |

### Recommendation

Do constraint mới, chọn phương án A dưới dạng compatibility facade chỉ trong AI2. Canonical `/jobs/idp` vẫn là đường evidence đầy đủ; facade legacy phải gắn trạng thái compatibility và fail closed khi không thể tạo citation/provenance đáng tin cậy.

## 5. Target flow

```text
BE legacy client
        ▼
AI2 compatibility facade
  - /api/v1/jobs/ocr
  - /api/v1/jobs/extract
  - /api/v1/jobs/compare
  - /api/v1/jobs/{id}
        ▼
AI2 current pipeline / internal job state
                         ▼
              legacy-shaped AI1/AI2 result
                         ▼
              BE raw result + read-model mapper
```

Nguyên tắc: job state, raw result và audit/persistence nằm ở BE/AI2 durable boundary; SSE/WebSocket không nằm trong phase này và không được dùng làm nguồn sự thật.

## 6. Contract decisions cần khóa trước code

1. **Input profile**: canonical path nhận `ai1.snapshot.v1`; adapter phải có profile rõ ràng cho AI1 `v3` và legacy `data/meta` nếu hai dạng này còn xuất hiện.
2. **Evidence policy**: thiếu `document_id`, page/block/table reference, digest hoặc citation không được bù bằng suy diễn; trả `INSUFFICIENT_EVIDENCE`/`NEEDS_REVIEW` theo contract.
3. **Multi-document**: mỗi snapshot có identity độc lập; body/annex relation phải là explicit map từ BE hoặc relation metadata đã xác thực.
4. **Output mapping**: lưu raw canonical AI2 result trước khi map; mapper không được làm mất citation, confidence, model disposition, evidence gaps hoặc proposed-index status.
5. **Idempotency**: key do BE tạo ổn định theo `tenant_id + dossier_id + source_digest + pipeline_version + requested_mode`; retry cùng key không tạo task AI2 thứ hai.
6. **Correlation**: giữ một `correlation_id` xuyên FE run, BE run step, AI2 task và persistence log; `task_id` của AI2 không thay thế correlation ID.
7. **Auth**: canonical client ký service envelope và gửi poll header đúng contract; không hạ AI2 xuống internal-key-only để tiện nối.
8. **Failure**: digest mismatch, tenant mismatch, role ambiguity, missing evidence, invalid signature hoặc result schema lỗi phải fail closed và giữ run ở trạng thái review/error có nguyên nhân.
9. **Index**: BE chỉ lưu `propose`; không publish active index trong integration phase.

## 7. Phase plan

Chi tiết từng phase nằm trong các file `phases/phase-*.md`. Thứ tự bắt buộc là P0 → P1 → P2 → P3 → P4 → P5.

| Phase | Mục tiêu | Phụ thuộc | Verification artifact |
|---|---|---|---|
| P0 | Freeze baseline và contract fixture | Không | baseline report, branch snapshot, compatibility matrix |
| P1 | AI2 legacy request/response facade | P0 | facade contract tests |
| P2 | AI2 legacy job orchestration vào pipeline hiện tại | P1 | async lifecycle integration report |
| P3 | Evidence/provenance guard cho compatibility lane | P2 | citation/insufficient-evidence report |
| P4 | Security, failure, observability và AI2 E2E | P1–P3 | test matrix + failure evidence |
| P5 | Canary, rollback, docs và handoff | P4 | rollout/rollback runbook |

## 8. Global acceptance criteria

- Canonical `/jobs/idp` giữ nguyên behavior.
- Legacy `/api/v1/jobs/extract` trả đúng `JobSubmission`/`JobStatusReport` và không tạo fact khi thiếu citation evidence.
- Legacy `/api/v1/jobs/compare` fail closed với `INSUFFICIENT_EVIDENCE` khi request không có citation authoritative.
- AI2 không thực hiện OCR/re-OCR; endpoint trả mã lỗi ổn định để Backend không nhầm AI2 là AI1.
- Retry/reconnect/poll lặp không tạo duplicate task hoặc duplicate persistence.
- Tenant/user khác không đọc được task/result của nhau.
- AI2 restart hoặc client restart không làm hỏng canonical path; legacy facade được ghi rõ là process-local compatibility lane.
- Legacy path có thể tắt/bật bằng routing/deployment mà không thay đổi canonical contract.
- Test bắt buộc pass: facade contract, unit mapping, canonical regression smoke, failure/recovery smoke.

## 9. Red-team checklist trước approval

- Có vô tình gửi raw PDF hoặc blob URI không được phép sang AI2 không?
- Adapter có biến `data/meta` thiếu provenance thành citation giả không?
- Dossier có hai annex cùng loại thì relation map có mơ hồ không?
- AI1 trả snapshot v3 nhưng digest canonical khác; hệ thống reject hay âm thầm sửa?
- Poll timeout rồi retry submit; idempotency có thật sự ngăn task thứ hai không?
- AI2 trả partial result rồi lỗi; BE lưu partial như final hay giữ trạng thái đúng?
- Một user có thể đọc result của tenant khác bằng `job_id` đoán được không?
- Legacy facade có bị hiểu nhầm là evidence-complete canonical output không?
- Legacy result và canonical result có thể ghi đè lẫn nhau không?
- `IndexContribution` có bị publish active qua một đường phụ không?

## 10. Approval gate

Scope đã được duyệt: chỉ sửa `ai-service/`; không sửa Backend/FE và không thay đổi canonical `/jobs/idp`.
