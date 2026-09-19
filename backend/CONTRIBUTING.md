# Contributing — Backend Code Regulations

> **Mục đích:** Quy định này mô tả tất cả rule mà CI backend enforce. Follow đúng các rule dưới đây → push code pass CI 100%, không cần retry.

Backend CI chạy 5 jobs song song (xem `.github/workflows/backend-ci.yml`):

| Job | Công cụ | Phát hiện |
|---|---|---|
| Layer Conformance | `import-linter` | Vi phạm DDD dependency rule |
| Ruff Lint | `ruff check` + `ruff format --check` | Lint + format violations |
| MyPy Type Check | `mypy --strict` | Type errors |
| Unit Tests | `pytest tests/unit/` + `pytest tests/architecture/` | Logic + boundary regression |
| Integration Tests | `pytest tests/integration/` | End-to-end auth + AI pipeline |

---

## 1. Pre-commit Checklist (chạy local trước khi push)

```bash
cd backend

# 1. Format
uv run ruff format src/ tests/

# 2. Lint (auto-fix những gì có thể)
uv run ruff check src/ tests/ --fix

# 3. Lint final (phải 0 errors)
uv run ruff check src/ tests/

# 4. Type check (phải 0 errors)
uv run mypy src/

# 5. Architecture boundaries (phải 9/9 contracts KEPT)
uv run python -m import_linter --config .importlinter

# 6. All tests
uv run pytest tests/ -v
```

**CI pass khi và chỉ khi** cả 6 bước trên đều xanh. Nếu 1 bước đỏ, CI sẽ đỏ.

---

## 2. Ruff — Lint + Format

### 2.1. Rules đang bật (xem `[tool.ruff.lint] select` trong `pyproject.toml`)

| Code | Nhóm | Ý nghĩa |
|---|---|---|
| `E`, `W` | pycodestyle | Style violations (whitespace, line length, etc.) |
| `F` | pyflakes | Unused imports/variables, undefined names |
| `I` | isort | Import ordering (stdlib → 3rd-party → first-party → local) |
| `B` | flake8-bugbear | Common bug patterns |
| `UP` | pyupgrade | Modernize syntax (PEP 604 union, etc.) |
| `N` | pep8-naming | Class/function naming conventions |
| `C4` | flake8-comprehensions | Simplify comprehensions |
| `RET` | flake8-return | Simplify return statements |
| `SIM` | flake8-simplify | Code simplification |

### 2.2. Rules đã tắt (intentional)

| Code | Lý do |
|---|---|
| `TC001`-`TC003` | TYPE_CHECKING imports không cần enforce |
| `ARG001`, `ARG005` | Stub functions có unused args |
| `PLR0913` | DTOs thường có >5 args |
| `PLR2004` | Magic values OK trong tests |
| `N818` | `DomainException` suffix linh hoạt |
| `B008` | `FastAPI()` defaults phổ biến |

### 2.3. Config tóm tắt

```toml
line-length = 100
target-version = "py311"
quote-style = "double"
known-first-party = ["contract_intelligence", "shared"]
combine-as-imports = true
```

### 2.4. Quy tắc thực hành

- **Import order:** `from __future__ import annotations` → stdlib → 3rd-party → `contract_intelligence.*` → local. Để `ruff check --fix` sửa tự động.
- **Unused imports:** Xóa ngay — không dùng `# noqa` để mask.
- **Format:** `ruff format` (đã thay thế Black) — chạy trước commit.
- **Không tắt rule** bằng `# noqa: E501` trừ khi có comment giải thích lý do chính đáng.

---

## 3. MyPy — Strict Type Checking

### 3.1. Config (xem `[tool.mypy]` trong `pyproject.toml`)

```toml
python_version = "3.11"
strict = true
warn_return_any = true
warn_unused_configs = true
disallow_untyped_defs = true
plugins = ["pydantic.mypy"]
```

`strict = true` bật TẤT CẢ các strict options: `disallow_untyped_defs`, `no_implicit_optional`, `warn_unused_ignores`, v.v.

### 3.2. Per-module overrides (chỉ định relax ở đâu)

| Module | Override | Lý do |
|---|---|---|
| `minio.*`, `alembic.*`, `passlib.*` | `ignore_missing_imports = true` | Lib không có type stubs |
| `contract_intelligence.{contract,extraction,conflict,review}.interfaces.api.routers.*` | `disallow_any_explicit = false` | FastAPI response linh hoạt |
| `contract_intelligence.shared.ai.dispatcher` | `disallow_any_explicit = false` | Tương tự |

**Mọi code ngoài các override trên phải strict** — không được thêm `# type: ignore` để bypass.

### 3.3. Quy tắc thực hành

- **Mọi function/method phải có type annotation** cho params và return type.
- **Không dùng `Any`** nếu có thể type chính xác. Khi buộc phải dùng, dùng `cast(T, expr)` để mypy hiểu rõ intent.
- **Pydantic models:** dùng `BaseModel` — `pydantic.mypy` plugin sẽ check schema.
- **Domain entities:** pure `@dataclass(eq=False) extends BaseEntity[str]` — KHÔNG dùng Pydantic/SQLAlchemy.
- **Domain protocols:** dùng `typing.Protocol` + `@runtime_checkable` (không ABC) cho repository interfaces.
- **Unused `# type: ignore`:** Xóa ngay. mypy báo `unused-ignore` → CI fail.
- **Tên method không shadow builtin:** KHÔNG đặt method tên `list`, `dict`, `type`, `id` trong class (gây `[valid-type]` error ở annotation khác trong cùng class).

```python
# ❌ Sai — shadow builtin `list`
class Repo:
    async def list(self) -> list[Item]:  # mypy: 'list' is not valid as a type
        ...

# ✅ Đúng — đổi tên
class Repo:
    async def list_items(self) -> list[Item]:
        ...
```

---

## 4. Import-linter — DDD Dependency Rule

### 4.1. 9 contracts đang enforce

| Contract | Source modules | Forbidden modules |
|---|---|---|
| `domain_purity` | `*.domain` | `fastapi`, `sqlalchemy`, `alembic`, `minio`, `httpx`, `jwt`, `passlib`, **all** `*.application`, `*.infrastructure`, `*.interfaces` |
| `application_no_infra_or_interfaces` | `*.application` | `*.infrastructure`, `*.interfaces` |
| `infrastructure_no_interfaces` | `*.infrastructure` | `*.interfaces` |
| `cross_module_independence` | `*.application` | cross-module `*.infrastructure`, `*.interfaces` |
| `contract_layers` / `extraction_layers` / `conflict_layers` / `review_layers` / `identity_layers` | (layers) | `interfaces` → `application` → `domain` |

### 4.2. Bounded Contexts

5 BC độc lập: `contract`, `extraction`, `conflict`, `review`, `identity`. Mỗi BC có 3 layers:
- `domain/` — entities, value objects, repository Protocols
- `application/` — services, DTOs (orchestrate use cases)
- `infrastructure/` — SQLAlchemy ORM, concrete repo impls
- `interfaces/api/` — FastAPI routers, dependencies (composition root)

### 4.3. Quy tắc thực hành

- **Domain layer là pure Python** — KHÔNG import FastAPI, SQLAlchemy, httpx, JWT, hoặc application/infrastructure/interfaces của bất kỳ BC nào.
- **Application layer** chỉ depend vào `domain` + `shared`. KHÔNG import infrastructure.
- **Infrastructure layer** impl interface từ domain. Được phép import domain, application (qua `TYPE_CHECKING` nếu cần), và 3rd-party libs.
- **Interface layer** (FastAPI routers) là composition root — DUY NHẤT chỗ được phép wire concrete impl vào Protocol.
- **Cross-BC dependency** chỉ qua `shared/` kernel hoặc domain events — KHÔNG gọi trực tiếp `other_bc.application`.

### 4.4. Khi cần thiết kế hơn strict

Thêm `ignore_imports` trong `.importlinter` cho từng exception cụ thể, kèm comment giải thích lý do + sprint refactor sẽ fix:

```ini
[importlinter:contract:application_no_infra_or_interfaces]
ignore_imports =
    # ApprovalService is CRUD facade over ORM — refactor sprint sau
    contract_intelligence.review.application.services.approval_service -> contract_intelligence.review.infrastructure.persistence.orm_approval
```

**KHÔNG được** thêm `ignore_imports` chung chung (vd `application -> infrastructure` toàn bộ) — sẽ làm rule vô nghĩa.

### 4.5. Hiện tại đang có 11 ignore_imports

Xem `.importlinter` để biết các exception hiện tại. Mỗi exception PHẢI có comment giải thích.

---

## 5. Testing

### 5.1. 3 test directories

| Directory | Loại | DB? | Coverage |
|---|---|---|---|
| `tests/unit/` | Pure logic | No | Domain entities, JWT service, exceptions |
| `tests/architecture/` | Boundary | No | import-linter, ruff, no-fastapi/no-sqlalchemy-in-domain |
| `tests/integration/` | E2E | SQLite in-memory | Auth flow, AI pipeline, SSE events |

### 5.2. Quy tắc

- **Async tests:** `@pytest.mark.asyncio` (đã set `asyncio_mode = "auto"` nên không cần decorator, nhưng vẫn có thể dùng để explicit).
- **Integration tests dùng SQLite in-memory** (aiosqlite) — không cần Postgres local.
- **Mock AI service:** qua `StubAI` client đã wire trong `tests/integration/conftest.py`.
- **Coverage floor:** 70% (xem `[tool.coverage.report] fail_under`).
- **Không skip test** bằng `@pytest.mark.skip` trừ khi có lý do rõ ràng + comment.

### 5.3. Test command

```bash
# Unit + architecture (chạy trong < 1s)
uv run pytest tests/unit/ tests/architecture/ -v

# Integration (chạy trong ~15s)
uv run pytest tests/integration/ -v

# Tất cả (CI chạy tương tự)
uv run pytest tests/ -v
```

---

## 6. Architectural Conventions

### 6.1. Repository Pattern

```
Domain layer:
  contract_intelligence.<bc>.domain.repositories.<entity>_repository
    → defines Protocol (interface)

Infrastructure layer:
  contract_intelligence.<bc>.infrastructure.persistence.repository_impl
    → defines <Entity>RepositoryImpl (concrete, depends on Session + tenant_id)

Interface layer:
  contract_intelligence.<bc>.interfaces.api.dependencies
    → composition root: wire Protocol ← concrete
```

**Khi thêm repository mới:**
1. Define Protocol trong `domain/repositories/<entity>_repository.py`
2. Implement trong `infrastructure/persistence/repository_impl.py`
3. Add factory function trong `interfaces/api/dependencies.py`
4. Application service chỉ type-hint Protocol

### 6.2. Domain Entity Pattern

```python
@dataclass(eq=False)
class Foo(BaseEntity[str]):
    id: str = ""
    name: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"id": self.id, "name": self.name}
```

- Pure Python `@dataclass` — KHÔNG SQLAlchemy, KHÔNG Pydantic.
- Extend `BaseEntity[str]` để có `created_at`, `updated_at` + equality by `id`.
- Override `to_dict()` cho API response.

### 6.3. Service Pattern

- **Application service** nhận `Protocol` (không concrete) qua constructor.
- **Method signature:** chỉ trả về domain entities hoặc plain dicts — KHÔNG bao giờ trả về ORM objects.
- **Logger:** dùng `structlog.get_logger(__name__)` để có structured logging với kwargs.

```python
import structlog

logger = structlog.get_logger(__name__)

async def do_thing(self, x: str) -> Foo:
    result = await self._repo.get(x)
    logger.info("thing.done", x=x, found=result is not None)  # ✅ kwargs
    return result
```

KHÔNG dùng `logging.getLogger(__name__)` với stdlib — sẽ fail mypy vì không nhận kwargs.

---

## 7. Branch & Commit Hygiene

### 7.1. Commit message format

```
<type>(<scope>): <subject>

<body tóm tắt thay đổi>
```

Type: `feat`, `fix`, `refactor`, `test`, `docs`, `chore`, `perf`.
Scope: tên BC (`contract`, `extraction`, `conflict`, `review`, `identity`) hoặc `shared`.

### 7.2. Branch strategy

- `main` — production-ready
- `feature/<name>` — sprint work
- `fix/<name>` — hotfix
- CI trigger: push to `main` hoặc `feature/**` (xem `on.push.branches` trong workflow).

### 7.3. Trước khi push

```bash
git status                          # review changes
git diff                            # spot-check
cd backend && uv run pytest tests/  # full local test
git push origin <branch>
```

---

## 8. Local Dev Setup

```bash
# Lần đầu
cd backend
uv sync --extra dev

# Pre-commit hook (optional, recommended)
# Cài pre-commit + copy .pre-commit-config.yaml nếu có
```

---

## 9. Common Pitfalls

### ❌ Không làm

1. **Import infrastructure trong application** — vi phạm DDD, CI fail ngay.
2. **Tạo ORM instance trong application service** — đẩy sang infrastructure (thêm method vào RepositoryImpl).
3. **Shadow builtin** trong class method names (`list`, `dict`, `id`, `type`) — mypy `[valid-type]`.
4. **Quên `id` field** trong dataclass extends `BaseEntity` — mypy `[attr-defined]`.
5. **Dùng `logging` stdlib với kwargs** — switch sang `structlog`.
6. **Bỏ qua `# type: ignore` đã mypy báo unused** — xóa ngay.
7. **Thêm dependency mới mà không update `pyproject.toml`** — CI sẽ thiếu types và fail mypy.

### ✅ Làm

1. **Mọi service nhận Protocol** qua DI trong `interfaces/api/dependencies.py`.
2. **Domain entity là dataclass pure Python**, extend `BaseEntity[str]`.
3. **Chạy 6 bước pre-commit checklist** trước khi push.
4. **Mỗi ignore_imports exception có comment** giải thích + sprint plan refactor.
5. **Mỗi ORM column nullable** phải handle ở conversion sang domain (vd `orm.sha256 or ""`).

---

## 10. Khi CI fail — Debug

1. Mở **GitHub Actions run** → click job fail → copy log.
2. Chạy local command tương ứng (xem mapping ở §1).
3. Fix → chạy lại full suite → push lại.

**Không** push code chưa pass local — mỗi lần retry CI tốn ~25s runner + quota.

---

## Reference

- CI workflow: `.github/workflows/backend-ci.yml`
- Ruff + MyPy config: `backend/pyproject.toml`
- Import-linter config: `backend/.importlinter`
- Architecture doc: `docs/DOC-04d-backend-architecture.md`
- Database schema: `docs/DOC-04c-database-erd.md`
- BE ↔ AI contract: `docs/DOC-05c-backend-ai-service-contract.md`
