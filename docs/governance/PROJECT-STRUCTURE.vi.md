# Cấu trúc project monorepo

```text
VSF/
├── frontend/                         # FE: reviewer app
├── backend/                          # BE: public API + orchestration
├── ai-service/                       # AIE-1 + AIE-2 runtime hiện tại
├── packages/
│   ├── contracts/                    # schema registry, source of truth
│   ├── typescript/                   # FE SDK và UI libraries
│   └── python/                       # pure domain libraries cho AI
├── docs/                             # SAD/PRD/API/contracts/evaluation
└── scripts/                          # repo-level checks
```

## Dependency rule

```text
contracts ← frontend-sdk ← frontend
contracts ← backend
contracts ← ai-service
evidence/reasoning libraries ← ai-service
```

Không cho phép dependency ngược từ package vào app, từ domain vào adapter, hoặc từ FE vào provider SDK.

## Đóng gói tính năng

Một tính năng mới được chia thành:

1. **Contract package:** schema, DTO, fixture.
2. **Domain library:** validation, matching, comparability, state transition thuần.
3. **Application adapter:** HTTP, DB, LLM, filesystem và UI gọi domain library.

Ví dụ Conflict: `vsf-reasoning` tạo candidate; backend lưu candidate; frontend hiển thị và gửi review action.
