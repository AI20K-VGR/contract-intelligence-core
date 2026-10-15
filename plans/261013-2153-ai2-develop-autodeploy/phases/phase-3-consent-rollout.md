# P3 — Consent rollout và điều khiển hồ sơ

## Overview

Thực thi quyết định chủ sản phẩm đã duyệt: mọi dossier đang hoạt động hiện tại được backfill consent true một lần, hồ sơ mới được tạo với true lưu tường minh; consent missing/null/malformed luôn fail closed. Chủ sở hữu có nút opt-out rõ ràng ngay trang xem hồ sơ/graph. Metadata hiện lưu trong JSON (`orm.py:33-63`); mutation phải đi kèm audit.

## Requirements

- **Functional:** dry-run nêu tổng số/ID count mà không in tên hợp đồng/nội dung; apply idempotent, ghi rollout id + giá trị cũ/mới + actor/system/time vào append-only audit và cập nhật hồ sơ active/non-purged trong cùng transaction. Toggle có ACL owner/operator phù hợp, đọc lại trạng thái đã lưu, ghi audit; false có hiệu lực cho lần run/query tiếp theo.
- **Non-functional:** không lưu nội dung hợp đồng trong backup/audit; rollback chỉ đảo row vẫn giữ giá trị do rollout đặt, tuyệt đối không ghi đè opt-out phát sinh sau đó. Lỗi audit/DB rollback transaction nguyên tử.
- **TDD:** tests red trước cho false hiện hữu, missing/true, deleted/purged, retry/idempotence, rollback có/không có user edit, ACL và UI loading/failure/accessibility.

## Related Code Files

**Create:**

- `backend/scripts/backfill_ai2_content_sharing_consent.py`
- `backend/src/contract_intelligence/contract/interfaces/api/routers/dossier_consent_router.py`
- `frontend/src/components/ai2-graph/ContentSharingConsent.tsx`
- `backend/tests/integration/test_ai2_consent_rollout.py`

**Modify (ownership chỉ P3):**

- `backend/src/contract_intelligence/main.py` (router registration; hiện include routers ở `:354-379`)
- `frontend/src/api/dossiers.ts` (API hiện có `patchDossier` tại `:192`, dùng riêng endpoint có kiểu rõ)
- `frontend/src/pages/DossierStructurePage.tsx` (graph view tại `:973-990,1166-1190`)
- `frontend/src/pages/DossierStructurePage.test.tsx`

**Delete:** —

## Implementation Steps

1. Tạo tests cho command ở dry-run mode, apply `true`, explicit prior false, absent field, deleted/purged exclusions, rerun, audit unavailable/transaction failure và rollback conditional. Chạy đỏ trước implementation.
2. Implement operator command theo rollout ID: snapshot candidate count, select dossier tenant-scoped và active (`deleted_at IS NULL`); audit prior state (missing/bool) + new true; update trong transaction. `--dry-run` là default; `--apply` bắt buộc. Rerun cùng rollout ID không tạo update duplicate. Không log metadata khác.
3. Implement compensation/rollback command hoặc mode sử dụng audit ID: khóa row hoặc dùng compare-and-set theo version/latest consent event; kiểm tra và ghi bù phải ở cùng transaction để user toggle không race với rollback. Chỉ revert nếu consent hiện vẫn true VÀ event consent mới nhất của dossier vẫn là event rollout; nếu user đã đổi opt-out rồi opt-in lại, ghi skip vào report. Giá trị cũ thiếu thì chỉ xóa key consent; nếu cũ là false thì khôi phục false. Tôn trọng bảng audit append-only (`shared/audit.py:24-54`; trigger bảo vệ ở migration `v12__audit_query_trace_immutable.py:20`).
4. Tạo API rõ `/dossiers/{id}/ai2-content-sharing-consent`, check tenant + role/ownership theo đường ACL hiện hành, update JSON field và append event `ai2.content_sharing_consent_changed` cùng transaction. Không dùng generic arbitrary metadata PATCH làm UX contract; response trả bool lưu hiện hành + `effective_from=next_request`.
5. Đặt router vào app bằng `main.py`; nối frontend client và hiển thị trạng thái/checkbox hoặc toggle trong `DossierStructurePage` cạnh graph AI2, nêu rằng bật cho phép provider nhận nội dung ở lần chạy/query sau. Có confirm, trạng thái lưu, retry/error, trạng thái loading; không reset local toggle khi request lỗi.
6. Chạy API/rollout unit, PostgreSQL transaction integration, Frontend unit/build. Thực hiện dry-run sau khi deploy ở giai đoạn vận hành; chỉ chạy apply một lần sau khi diff candidate count được đối chiếu, không trong lúc cook trên dữ liệu production.

## Success Criteria

- [x] Dry-run/apply cho active dossiers đo được, rollout event truy ngược từng record mà không chứa hợp đồng; deleted/purged không bị sửa.
- [x] Cùng rollout ID chạy lại không đổi count đã xử lý/không nhân đôi event; lỗi audit không để metadata cập nhật nửa chừng.
- [x] UI hiển thị consent hiện hành và cho opt-out/in qua endpoint riêng; request unauthorized bị 403; toggle lỗi không báo thành công.
- [x] Rollback dùng row lock/CAS bao trùm check + write; integration test PostgreSQL điều phối rollback đua với opt-out và chứng minh opt-out không bao giờ bị ghi đè; khôi phục prior false/absent nếu chưa có user edit và bỏ qua mọi dossier đã đổi sau rollout.
- [x] Existing consent true/false và hồ sơ mới được test; explicit user false không bị default hoặc backfill tương lai tự bật lại.
- [x] Các capability/global caps xử lý, query LLM/vector và egress giữ ON mặc định trong product/develop. Mọi provider call vẫn phải qua AND giữa server cap, signed request consent và consent true đã lưu trên đúng hồ sơ; consent missing/malformed/false tạo zero provider calls. Không tắt global capability để thay cho consent rollout. Backfill vẫn dry-run + candidate digest trước và cần `--apply` rõ ràng; không apply dữ liệu vận hành trong cook.

## Verification (2026-10-14)

- `pytest tests/integration/test_ai2_consent_rollout.py tests/integration/test_tenant_isolation.py -q`: 7 passed locally; PostgreSQL-specific race is included in CI, skipped locally because no test DB is configured.
- Backend CI run `38462468129` at `7680f1fe`: lint, type, unit, architecture and integration passed; 115 integration tests passed, including the consent rollback/opt-out PostgreSQL race.
- AI-service CI run `38461625336` at `faccf564`: 1609 deterministic tests passed, 17 deselected, 24 warnings; signed query consent and false/missing consent provider-call gates passed.
- Frontend Vitest: 146 passed; production build passed; ESLint had 13 existing warnings and no errors.
- No operational backfill was run; deployment operator must review dry-run count/digest before explicit apply.

## Risk Assessment

**Cao × Rất cao:** blanket backfill mở quyền gửi hợp đồng ra provider. **Mitigation:** đây là quyết định đã được user phê duyệt; mặc định operator chạy `--dry-run`, so sánh count, cần `--apply` rõ; audit + rollout id; UI opt-out; P4 enforce service cap+consent tại egress; runbook nêu provider/network prerequisites.

**Trung bình × Cao:** audit insert thành công nhưng metadata không commit, hoặc retry nhân đôi. **Mitigation:** cùng transaction, unique rollout identity/conditional update và integration test PostgreSQL; command fail closed.

**Rollback:** rollback là lệnh bù có audit, không xóa event cũ; chỉ đổi hồ sơ mà rollout event vẫn là consent event mới nhất và giá trị hiện vẫn là true. Revert UI/API độc lập không xóa consent đã lưu.
