# backend/

> **Sẽ generate chi tiết ở bước tiếp theo — phụ trách: Backend Engineer**

Thư mục này chứa REST API server cho dự án **Contract Intelligence**.

## Tech stack dự kiến

- Java 17+, Spring Boot 3.x
- Spring Web, Spring Data JPA, Spring Validation
- PostgreSQL + Flyway migration
- Springdoc OpenAPI (Swagger UI)
- Lombok
- Maven

## Kiến trúc đích

Clean Architecture + DDD, chia theo **Bounded Context**:

```
com.vsf.contractintel
├── contract/      # Upload & quản lý hợp đồng
├── extraction/    # Trích xuất điều khoản
├── conflict/      # Phát hiện xung đột
├── review/        # HITL review
└── shared/        # Shared kernel (BaseEntity, DomainEvent, ApiResponse…)
```

Mỗi module có đủ 4 layer: `domain` → `application` → `infrastructure` → `interfaces`.

> Chi tiết sẽ được generate trong bước tiếp theo. Trước đó thư mục này giữ trống.

Backend là public API, owner của domain/persistence/Flyway, auth và orchestration. Không nhận callback do client cung cấp; worker Python chỉ trả artifact versioned qua internal authenticated boundary. Contract chuẩn: [`docs/DOC-04-architecture.md`](../docs/DOC-04-architecture.md) và [`docs/DOC-05-api-spec.yaml`](../docs/DOC-05-api-spec.yaml).
