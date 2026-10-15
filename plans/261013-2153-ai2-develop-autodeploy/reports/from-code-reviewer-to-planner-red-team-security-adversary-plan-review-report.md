# Red-team report: AI2 develop autodeploy and cross-machine setup

**Plan:** `plans/261013-2153-ai2-develop-autodeploy`
**Review lenses:** Security Adversary, Failure Mode Analyst, Bad-day Operator
**Scenario coverage:** consent missing/false, concurrent rollback, PR required checks, manual dispatch ref, provider/deploy prerequisites, clean-machine validation.
**Verdict:** **STOP** — sửa các finding High đã chứng minh và cập nhật phase liên quan trước validate/cook.

## Findings (severity-ranked)

| ID | Severity | Evidence | Anchor | Cheapest fix |
|---|---|---|---|---|
| RT-01 | High · proven | Với dossier có `metadata={}` hoặc consent field sai kiểu, P1 yêu cầu fallback `true`; P4 lại yêu cầu payload thiếu consent fail-closed nhưng bước 3 dùng cùng centralized default. Khi cap và provider sẵn sàng, hồ sơ bị bỏ sót khỏi backfill vẫn có thể egress. | `phases/phase-1-ci-green.md:28-30`; `phases/phase-4-consent-enforcement.md:36,47`; `backend/src/contract_intelligence/worker.py:1122-1127`; `backend/src/contract_intelligence/shared/ai/canonical_processing.py:376-384` | Phân biệt consent được cấp rõ với consent thiếu: chỉ ghi `true` tường minh khi tạo hồ sơ mới hoặc backfill đã duyệt; resolver thiếu/sai kiểu phải trả `false`. Bổ sung test metadata absent/null/wrong-type qua cả processing và hai query routes. |
| RT-02 | High · proven | `workflow_dispatch` cho phép chạy từ ref người gọi chọn; job không có guard `develop`, dùng `production` environment rồi SSH deploy đúng `github.sha`/`github.ref_name`. Plan ghi environment production hiện không có protection/branch policy nhưng P5 chỉ yêu cầu kiểm tra, chưa buộc workflow chặn ref khác. Một lần dispatch từ `feature/*` vì vậy có thể chạy code chưa merge với deploy credentials. | `.github/workflows/deploy.yml:22-24,38-45,58-60,85-88`; `plan.md:57`; `phases/phase-5-develop-autodeploy.md:11-20,34` | Thêm job-level guard chỉ chấp nhận `refs/heads/develop` trước khi nạp environment secrets; hoặc tạm bỏ manual dispatch cho tới khi production Environment giới hạn branch. Thêm kiểm tra cấu hình: dispatch từ feature branch không thể dùng secrets/deploy. |
| RT-03 | High · proven | Ruleset hiện chỉ yêu cầu `pr-guard`; workflow `ai-service` tự ghi chú chưa phải required check. P1 làm nó chạy test thật nhưng P1/P5 không thiết lập hoặc ghi thành blocker một check bắt buộc cho CI AI-service. PR có thể merge và kích hoạt deploy dù test AI-service đỏ. | `plan.md:57,98`; `phases/phase-1-ci-green.md:31,36-38`; `phases/phase-5-develop-autodeploy.md:34,43`; `.github/workflows/ai-service.yml:2,6-24` | Nêu rõ gate vận hành trước merge: một required aggregate check phụ thuộc backend + frontend + ai-service, hoặc required `ai-service` check tương ứng. Vì plan loại trừ tự sửa branch rules, đánh dấu P5/merge BLOCKED cho tới khi admin cấu hình và xác minh required contexts. |
| RT-04 | Medium · suspected `[ASSUMED]` | Rollback đọc “giá trị hiện vẫn true + rollout event mới nhất” rồi khôi phục/xóa key. Nếu user opt-out commit sau lần đọc nhưng trước lần ghi rollback, thao tác bù có thể xóa opt-out; prior `absent` sau đó rơi về default true. Kế hoạch yêu cầu transaction nhưng không buộc row lock/CAS bao trùm cả kiểm tra lẫn ghi. | `phases/phase-3-consent-rollout.md:35-36,45`; `plan.md:40,120`; `backend/src/contract_intelligence/worker.py:1122-1127` | Ràng buộc cập nhật bù bằng row lock hoặc compare-and-set theo version/latest consent event trong cùng transaction; rollback ghi event riêng. Thêm test PostgreSQL điều phối race opt-out-vs-rollback. Route xác minh này vào P3. |

## Đường đi không thể hoàn tác

RT-01 có thể gửi toàn văn hợp đồng/phụ lục tới provider khi consent không tồn tại hoặc malformed; rollback chỉ ngăn egress tương lai, không thu hồi nội dung đã gửi. RT-02 có thể phơi deploy key hoặc đưa mã chưa review vào production. Không chạy apply/backfill hoặc production deployment cho đến khi các đường này đã bị chặn và được kiểm thử.

## Rủi ro còn lại được chấp nhận có điều kiện

- Backfill `true` bao gồm các giá trị `false` cũ theo quyết định sản phẩm đã ghi tại `plan.md:40`; chỉ an toàn trong phạm vi người ra quyết định có thẩm quyền với tất cả dossier thuộc candidate set. Dry-run phải công bố count/scope trước apply và người vận hành phải đối chiếu đúng phạm vi đã duyệt. Không mở lại quyết định này nếu chỉ có phản đối trừu tượng.
- P6 tuyên bố xác minh trên Windows và Linux/macOS (`plan.md:104`), nhưng bước dogfood hiện mô tả checkout **hoặc** Windows clean profile (`phases/phase-6-local-runbook.md:33`). Cần chạy cả PowerShell và ít nhất một POSIX clean clone; nếu hứa hỗ trợ macOS riêng thì thêm run macOS hoặc thu hẹp acceptance.
- Smoke inference thật phụ thuộc provider key và outbound egress (`plan.md:92,141-142`); nếu thiếu, chỉ có thể nghiệm thu trạng thái degraded/offline, không được gọi đó là xác nhận full AI2 inference.
