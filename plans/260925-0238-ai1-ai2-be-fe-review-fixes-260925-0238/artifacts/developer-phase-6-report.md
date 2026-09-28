# Developer report — phase-6-integrated-verification

## Phạm vi

Đã tạo harness test deterministic cho integrated AI2 review-fixes flow. Lane này
chỉ tạo test/report plan-owned; không chỉnh product code, phase file, plan
frontmatter hoặc approval artifact.

Files mới:

- `backend/tests/integration/test_ai2_review_fixes_flow.py`
- `frontend/tests/ai2-review-fixes-flow.test.tsx`

Fixture dùng ID/digest cố định cho tenant, dossier, run, body document và annex
document. Backend dùng SQLite file tạm và dependency overrides an toàn; không gọi
AI2, Keycloak, live dossier hoặc secret.

## RED rồi GREEN

RED đầu tiên:

- Backend targeted: `1 passed, 3 failed`. Fixture finding hai phía đã bắt lỗi
  runtime `sqlite3.IntegrityError: NOT NULL constraint failed: finding_side.tenant_id`
  tại projection finding.
- Frontend targeted: `2 passed`.

Sau khi seam product hiện có đủ `tenant_id` trong worktree (lane này không sửa
product code), GREEN targeted:

- Backend integration: `4 passed`.
- Frontend flow: `2 passed`.
- Backend Ruff trên test mới: `All checks passed!`.
- Frontend Prettier trên test mới: pass.

## Coverage chính

- Snapshot body + annex → AI2 result → durable read model, chunks, context
  findings, annex link, evidence issue và coverage.
- Query state giữ `BLOCKED`, không suy diễn thành `ANSWERED`; có retrieval trace
  và snapshot digest.
- Anonymous và cross-tenant query bị deny.
- Review queue tạo từ invalid citation; action cập nhật version và stale
  `base_version` trả `409 VERSION_CONFLICT`.
- Duplicate result replay là idempotent; legacy compatibility stub được giữ rõ
  là stub và trả schema extraction riêng.
- Frontend giữ `BLOCKED` cùng context/evidence khi facts/findings rỗng; render
  dynamic citation scope/status và finding hai phía với `base_version`.

## Offline gates

- Backend full: `295 passed`.
- AI-service full: `703 passed, 1 skipped, 26 warnings`.
- Frontend full: `24 passed`.
- Frontend build: PASS; chỉ còn chunk-size warning.
- Frontend lint: `0 errors`, `9 warnings` hiện hữu.
- Frontend repository `format:check`: còn baseline formatting debt; targeted
  test mới đã pass Prettier.
- `git diff --check`: exit `0`; chỉ có cảnh báo line-ending từ dirty files có
  sẵn trong worktree.

## Authenticated E2E

`authenticated E2E NOT_RUN`: không có Keycloak token hợp lệ và stack live sẵn
sàng. Probe read-only đã chạy:

```text
docker compose ps keycloak backend ai-service
→ no such service: ai-service
```

Không suy diễn authenticated E2E từ offline tests hoặc dependency overrides.

## Risks / limitations

- RED đã cho thấy persistence finding projection cần được giữ dưới regression
  nếu seam `finding_side.tenant_id` thay đổi lại.
- SQLite/dependency overrides chỉ xác minh orchestration và contract offline;
  không chứng minh live Postgres, Kafka, AI2 HTTP, Keycloak hoặc restart thật.
- Full lint/format vẫn có warnings/debt ngoài scope; không rewrite unrelated
  files.

Phase frontmatter vẫn `status: pending`. Report này không chứa approval verdict.
