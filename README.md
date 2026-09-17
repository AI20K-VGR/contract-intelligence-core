# Contract Intelligence

Codebase xử lý hợp đồng và phụ lục, hiển thị bằng chứng và hỗ trợ human review. Kiến trúc triển khai lấy từ **[docs/architecture.md](docs/architecture.md)**: FastAPI modular monolith + background worker chung PostgreSQL, artifact local và React/TypeScript UI.

## Chạy nhanh

Cần Docker Desktop chạy Linux containers. Copy `infra/compose/.env.example` thành `infra/compose/.env`; đặt mật khẩu PostgreSQL, token account và `CI_DATA_DIR` là đường dẫn tuyệt đối tới thư mục được phép lưu tài liệu, ngoài Git.

```powershell
.\scripts\demo.ps1 -Profile core
```

Mở **http://localhost:8080**, nhập token đã cấu hình, tải một PDF hợp đồng và phụ lục nếu có. Swagger: **http://localhost:8000/docs**. `-Profile ops` thêm Prometheus tại port 9090; chưa phải toàn bộ observability stack trong kiến trúc.

## Cấu trúc

```text
apps/web/           React + TypeScript, citation overlay và review
backend/app/        API, domain modules và durable worker chung codebase
backend/migrations/ Alembic và immutable-record triggers PostgreSQL
backend/tests/      Synthetic workflow, geometry, queue và review tests
infra/compose/      PostgreSQL, migrate, API, worker, web
infra/prometheus/   Metrics local
scripts/demo.ps1    Bootstrap core/ops
ai-service/         OCR lab/demo hiện có, được giữ độc lập
docs/              Kiến trúc, sản phẩm, trạng thái triển khai
frontend/          Placeholder cũ; UI mới nằm tại apps/web/
```

Đã có nền tảng upload → task theo trang → native/local OCR → fact candidates/citations → review lưu DB → approval. **Chưa phải toàn bộ sản phẩm trong kiến trúc**: trích bảng, semantic AI, Terra, calibration/evaluation, revision manifest và observability đầy đủ còn ở roadmap. Xem [trạng thái chi tiết](docs/IMPLEMENTATION_STATUS.md).

- [Backend: chạy local, API, kiểm thử](backend/README.md)
- [Web](apps/web/README.md) · [OCR lab hiện có](ai-service/README.md)
- [Product vision](docs/DOC-01-product-vision.md)
- [Quy tắc đóng góp](CONTRIBUTING.md) · [Git workflow](GITFLOWS.md)

`docs/DOC-04-architecture.md` và `docs/DOC-05-api-spec.yaml` là thiết kế trước đó. API mới xuất OpenAPI tại `/openapi.json`; spec cũ không phải contract của backend này.

Không commit hợp đồng, scan, phụ lục, key hoặc raw output. Dữ liệu evaluation nằm ngoài repo theo CONTRIBUTING. Không push trực tiếp `develop`/`main`; PR cần review theo quy định team.

Internal / Proprietary.
