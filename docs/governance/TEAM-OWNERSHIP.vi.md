# Khung làm việc 4 người

## Mục tiêu

Một monorepo, bốn vai trò, một bộ contract dùng chung. Mỗi người có thể phát triển độc lập trong vùng sở hữu nhưng mọi giao tiếp giữa FE, BE, AIE-1 và AIE-2 phải đi qua contract đã version.

## Phân công

| Vai trò | Vùng chính | Trách nhiệm | Không sở hữu |
|---|---|---|---|
| FE | `frontend/`, `packages/typescript/` | UI reviewer, PDF/evidence viewer, review actions, frontend SDK | DB, AI prompt, trực tiếp gọi AI provider |
| BE | `backend/` | Public API, auth/session, persistence, job orchestration, review transaction | OCR/LLM logic, sửa machine evidence |
| AIE-1 | `ai-service/app/pipeline/ai1_*`, `packages/python/vsf-evidence/` | OCR/layout, page/line/table/geometry, AI1 result contract | Conflict decision, UI, publish approval |
| AIE-2 | `ai-service/app/reasoning/`, `packages/python/vsf-reasoning/` | Structure repair, fact/scope/relation, retrieval, conflict candidate, grounding | Legal conclusion, reviewer approval |

## Ranh giới runtime

```text
FE  ── REST/OpenAPI ──>  BE  ── internal job contract ──>  AI service
│                         │                                  │
└── evidence/review UI    ├── DB + artifact store             ├── AI1 OCR/layout
                          └── review/audit/publish gate       └── AI2 reasoning
```

`docs/contracts/` và `packages/contracts/` là vocabulary chung. FE không import Python; BE không import module nội bộ của AI2; AIE-1 không ghi thẳng DB; AIE-2 không tự approve/reject.

## Cách chia task

Mỗi task phải có:

1. Input contract và output contract.
2. Owner chính và reviewer chéo.
3. Fixture nhỏ, deterministic test và acceptance check.
4. Tác động tới DOC-01..DOC-06 hoặc ADR nếu có.

PR chạm từ hai vùng trở lên cần reviewer của cả hai vùng. Không commit PDF/hợp đồng thật; fixture lớn đặt ngoài repo.

## Quy ước package

- `packages/contracts`: schema và version registry, không chứa business logic.
- `packages/typescript/*`: SDK/types/UI primitives dùng cho FE.
- `packages/python/*`: domain library thuần, không import FastAPI/router/DB.
- `ai-service/app`: adapter/runtime của AI1 và AI2; chỉ gọi library qua public API.
- `backend/src`: application/domain/infrastructure/interfaces; không copy logic AI.

## Luồng thay đổi contract

```text
Proposal → schema + fixture → consumer tests → review FE/BE/AI → version bump → merge
```

Không sửa một field dùng chung mà không thêm fixture tương thích ngược hoặc ghi rõ breaking change.
