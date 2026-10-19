# Báo cáo kiểm thử hệ thống — Contract Intelligence

| | |
|---|---|
| Ngày kiểm thử | 2026-10-19 (cập nhật lần 2, theo phản hồi của team) |
| Người thực hiện | nguyenddung |
| Môi trường | **Local** (`docker compose`) và **Production** (`contract-intelligence.tech`, chỉ đọc + 1 luồng E2E nhỏ, có sự đồng ý) |
| Phiên bản | Prod chạy `origin/develop` @ `a9260f8e`. Local: image build 2026-10-03 (backend `2.0.0+sprint3-backend`). |
| Bộ test | [`qa/`](../../qa/README.md) — `QA_ENV=local` hoặc `QA_ENV=prod`; chạy `qa/scripts/run-qa.ps1` |

> **Lưu ý phương pháp — ngân sách performance:** Hiện **chưa có NFR số chính thức**. `DOC-03` NFR-07 ghi rõ *"Chưa cam kết latency, throughput, cost, accuracy, availability… cho tới khi có số trong DOC-06"*. Vì vậy các ngưỡng p95 trong báo cáo này là **ngưỡng QA tự đề xuất** để phát hiện hồi quy, **không phải SLO hợp đồng**; chỉnh qua biến `QA_PERF_*`. Khi NFR có số thật, thay ngưỡng vào.

## 1. Kết luận

| Hạng mục | Local | Production | Đánh giá |
|---|---|---|---|
| **Smoke** | 20 pass | 14 pass (7 skip local-only) | Stack sống, 3 vai trò đăng nhập, đường đọc chính OK ở cả hai |
| **Security** | 111 pass, 9 xfail | 86 pass, 2 xfail, **0 fail** | Không có lỗ hổng nghiêm trọng. Prod chặt hơn local rõ rệt (xem §2) |
| **Performance** | 7/10 đạt ngưỡng | *không chạy trên prod* | Ổn ở tải thấp; **PERF-01** (backend 1 tiến trình) và **PERF-02** (`/runs`) là nút thắt |
| **End-to-end** | 16 pass | 12 pass (share skip trên prod) | Luồng upload→OCR→AI2→review chạy đúng. Prod tới `PENDING_REVIEW` ~23s, local ~5–18s |
| **SCA** | Python 0 lỗ hổng; npm 4 (chỉ dev-deps) | — | Không có lỗ hổng trong dependency chạy thật |
| Unit/arch có sẵn | backend 563/563, frontend 139/139 | — | Không hồi quy |

**Phát hiện mở còn lại cần xử lý** (giảm dần ưu tiên): **PERF-01** (scale backend) → **ARCH-01** (tenant_id hardcode trong token) → **AUTH-01** (token không thu hồi được trước khi hết hạn) → **BUG-01** (commit trước khi trả response) → **PERF-02** (`/runs` chậm) → **SEC-04** (NUL byte trong query param vẫn 500 trên prod) → **SEC-03/SEC-01** (endpoint lab AI2 / clickjacking). Chi tiết §2–§6, tổng hợp §8.

**Đã được xác nhận FIX trên prod** so với lần 1: **SEC-02** (`/docs`, `/redoc`, `/openapi.json` → 403) và **SEC-05** (`/process` legacy → 404). NUL byte trong **path** cũng đã bị chặn ở biên (400).

## 2. Khác biệt Local ↔ Production (quan trọng)

Prod đứng sau **Cloudflare** + **Caddy** và chạy `origin/develop`. Những khác biệt quan sát được:

| Chủ đề | Local (image cũ) | Production | Ý nghĩa |
|---|---|---|---|
| `/docs`, `/openapi.json` | 200 (mở) — SEC-02 | **403** | SEC-02 đã fix trên prod; local cần cập nhật image |
| `/process`, `/jobs/idp` ngoài | stub 202 / lộ cổng | **404** | SEC-05 đã gỡ; AI2 không lộ ra ngoài |
| `%00` trong path id | 500 — SEC-04 | **400** (chặn ở biên) | Edge đỡ được path; **query param vẫn 500** (còn hở) |
| Payload JNDI/traversal | tới app (404/200) | **403** (WAF) | Cloudflare WAF chặn pattern tấn công |
| Header bảo mật | — | HSTS + `nosniff` có; **thiếu** `X-Frame-Options`/CSP | SEC-01 vẫn mở |
| AI2 / MinIO | lộ cổng 8002/9000 | nội bộ `ci-network` | Bề mặt tấn công nhỏ hơn nhiều trên prod |
| Chia sẻ hồ sơ | nhận grant theo `id` | validate theo **email + thành viên active** | Prod chặt hơn (gửi thư mời thật) |

Bộ test nhận biết môi trường qua `QA_ENV`: trên prod tự bỏ qua test cần truy cập host (docker/MinIO/Keycloak-admin), coi WAF-403 là hợp lệ, và không chạy load.

## 3. Security — phát hiện

### 3.1. Đã chặn đúng (cả hai môi trường)

Xác thực (token giả `alg=none`/HS256/khoá lạ/sửa claim/sai issuer/hết hạn → 401; TTL 15 phút; `aud=contract-intel-backend`); phân quyền vai trò (ma trận ADMINISTRATOR/OPERATOR/REVIEWER); cô lập theo header tenant; **BOLA/IDOR giữa hai Operator cùng tenant** (Operator B không đọc/sửa/xoá được hồ sơ, document, OCR lines, clauses, pages, runs của Operator A — tất cả 403/404); **mass-assignment** (inject `created_by`/`shared_with`/`access_scope` vào metadata bị bỏ qua, không chiếm được quyền; field lạ trên PATCH bị bỏ qua; `POST /users` field lạ → 422); chữ ký HMAC AI2 (sai secret/payload/hết hạn/sai audience → 401); webhook Keycloak và callback phê duyệt ngoài yêu cầu xác thực; xử lý file xấu (PE/HTML giả PDF → 422, PDF bomb → 413/422, PDF chứa JS không bị thực thi, path traversal trong tên file multipart không thoát khỏi storage); MinIO từ chối truy cập ẩn danh (403); TTL presigned URL có chặn trên (≤24h); ảnh trang đi qua API xác thực, không phát URL công khai.

### 3.2. Phát hiện

| Mã | Mức | Môi trường | Mô tả | Đề xuất |
|---|---|---|---|---|
| **ARCH-01** | Trung bình | Cả hai | `tenant_id` trong token là **hardcoded-claim mapper = `tenant_vgr_01`** cho mọi user (kể cả user có attribute `tenant_id` khác). Cô lập tenant hiện chỉ dựa trên so khớp header↔claim, nhưng claim luôn là một tenant → **không thể vận hành đa tenant thật** và test 2-tenant không chạy được qua luồng đăng nhập thật | Đổi mapper `tenant_id` sang **User Attribute mapper** (đọc attribute của user). Khi đó chạy lại `qa/security/test_multitenant.py` sẽ kiểm tra cô lập 2 tenant thật |
| **AUTH-01** | Trung bình | Cả hai | Sau khi admin **vô hiệu hoá** user, access token đã cấp **vẫn dùng được tới khi hết hạn** (≤15 phút). JWT xác thực stateless, không có denylist/kiểm tra user-active mỗi request. (User bị disable không lấy được token mới — điểm này đúng) | Chấp nhận cửa sổ 15 phút + back-channel logout, hoặc thêm kiểm tra trạng thái user/denylist theo request cho thao tác nhạy cảm |
| **SEC-03** | TB (local) / Thấp (prod) | Local lộ cổng | Endpoint lab AI2 (`/api/workspace/*`, `/api/cases/*`) **không xác thực**; compose dev publish 8002 trên `0.0.0.0`. Prod không lộ cổng nhưng mọi container trong `ci-network` vẫn gọi được | Tắt route lab mặc định (cờ `AI2_LAB_ENABLED=false`) hoặc yêu cầu envelope; bind cổng dev về `127.0.0.1` |
| **SEC-04** | Thấp | Local (mọi route) / Prod (query param) | NUL `%00` tới asyncpg → **500** + full traceback trong log. Prod đã chặn ở path (400) nhưng **query param `?q=…\x00` vẫn 500** | Middleware trả 400 khi path/query/body chứa `\x00` |
| **SEC-01** | Thấp | Cả hai | Thiếu `X-Frame-Options`/CSP `frame-ancestors` (clickjacking) | Thêm `X-Frame-Options "DENY"` + CSP vào block `(common)` của Caddy |
| **SEC-02** | ~~Thấp~~ **Đã fix (prod)** | Local image cũ | `/docs` công khai — đã fix trên prod | Cập nhật image local để đồng bộ |
| **SEC-05** | ~~Thông tin~~ **Đã fix (prod)** | Local image cũ | `/process` legacy nhận request không ký — đã gỡ trên prod | Cập nhật image local |

## 4. SCA — quét lỗ hổng dependency

Chạy bằng `qa/scripts/sca-scan.sh` (pip-audit + npm audit; trivy cho image là tuỳ chọn `--images`).

| Thành phần | Công cụ | Kết quả |
|---|---|---|
| `backend` (Python) | pip-audit | **0 lỗ hổng** |
| `ai-service` (Python) | pip-audit | **0 lỗ hổng** |
| `frontend` (npm) | npm audit | 4 (2 critical, 1 high, 1 moderate) — **tất cả thuộc dev-dependency của vitest** (`tinypool`, `@vitest/mocker`, `source-map-js`), **không vào bundle chạy thật** |

Đề xuất: `npm audit fix` / nâng vitest khi tiện (giảm nhiễu CI); quét image bằng `trivy` trước khi release (`sca-scan.sh --images`).

## 5. Performance (local)

Tải đóng, 500 request, 20 đồng thời (mẫu lớn hơn lần 1 để p99 có ý nghĩa). Ngưỡng p95 là **QA đề xuất** (xem lưu ý đầu báo cáo).

| Kịch bản | RPS | p50 (ms) | p95 (ms) | Ngưỡng | Đạt |
|---|---|---|---|---|---|
| `GET /health` | 76,7 | ~100 | 594 | 150 | ❌ |
| `GET /auth/me` | 75,4 | ~180 | 652 | 800 | ✅ |
| `GET /dossiers?limit=20` | 42,1 | ~470 | 672 | 800 | ✅* |
| `GET /runs` | 12,4 | ~1700 | **3285** | 800 | ❌ |
| `GET /dossiers/{id}` | 64,8 | ~165 | 690 | 800 | ✅ |
| `GET /documents/{id}/lines` | 79,0 | ~80 | 262 | 1600 | ✅ |
| `/dossiers` c=1 / c=10 / c=50 | 22 / 44 / 38 | 48 / — / — | 58 / 285 / 2133 | – | độ trễ tăng tuyến tính |
| 401 flood (20 đồng thời) | 74,3 | ~185 | 672 | 150 | ❌ |

\* dao động quanh ngưỡng qua các lần chạy. **0% lỗi** ở mọi mức tải.

| Mã | Mức | Mô tả | Đề xuất |
|---|---|---|---|
| **PERF-01** | Cao | Backend (cả prod) chạy **1 tiến trình uvicorn** trên máy nhiều core; throughput chạm trần ~40 RPS, độ trễ tăng tuyến tính theo tải. Đo **từ trong container** cho cùng kết quả → nghẽn ở app, không phải mạng Docker | `uvicorn --workers N` / gunicorn+UvicornWorker; kèm metrics multiprocess + khoá cho vòng bảo trì |
| **PERF-02** | TB | `GET /runs` ~90ms kể cả `limit=1` (chi phí cố định), p95 ~3,3s ở 20 đồng thời | Profile `list_pipeline_runs`; chỉ select cột summary; index `(tenant_id, created_at)` |

**Kịch bản tải bổ sung (đã có sẵn, opt-in):** stress/spike kèm thu **CPU/RAM/DB connection** (`QA_RUN_STRESS=1`, `qa/performance/test_stress.py` + `lib/resources.py`); **throughput pipeline** nhiều hồ sơ đồng thời (`QA_RUN_STRESS=1 QA_RUN_PIPELINE=1`, `test_pipeline_throughput.py`, ghi peak tài nguyên vào `perf.json`); **soak** bằng `qa/performance/locustfile.py`. *Về "tách máy sinh tải":* lần này tải sinh cùng máy, nhưng đã **đối chứng bằng đo từ trong container** (cùng kết quả) nên kết luận nghẽn-ở-app không bị sai lệch bởi Docker Desktop; để lấy số tuyệt đối nên chạy máy sinh tải riêng. Biến thể PDF nhiều trang / 50 MB để chạy tay (ghi trong README).

## 6. Lỗi chức năng & quan sát

| Mã | Mức | Mô tả |
|---|---|---|
| **BUG-01** | TB (chập chờn) | Sau `PUT /access` trả 200, request ngay sau của reviewer vào `review-items` từng bị 403 (1 lần, lúc chia sẻ kèm email). Giả thuyết: handler ghi không commit trước khi trả response (commit nằm ở teardown dependency; từ FastAPI ≥0.118 phần sau `yield` chạy sau khi response đã gửi). Đề xuất: `await svc.commit()` trước khi trả; gửi email qua `BackgroundTasks` sau commit |
| **OBS-01** | Thấp | Log worker có `citation_guard.quote_mismatch` (lệch 1–2 ký tự giữa trích dẫn AI2 và span OCR) — kiểm tra chuẩn hoá khoảng trắng |
| **OBS-02** | Thông tin | AI2 `/health`: LLM `unreachable`, embedding `RateLimitError`; `readyz` của backend gắn nhãn `ai_service_mode: "stub"` khi healthcheck AI thất bại dù worker vẫn gọi AI2 thành công — dễ gây hiểu nhầm |

## 7. Phạm vi bộ test (sau cập nhật)

- **Smoke (20):** health/readiness backend·AI2·Keycloak·MinIO·frontend; **bundle JS của frontend tải được**; login 3 vai trò; đọc danh sách/chi tiết (không tự pass khi rỗng — `QA_EXPECT_DATA`); **Kafka broker + consumer group `ci-ai1-ocr`/`ci-backend-ai1-results` + backend-worker + ai1-worker** (qua docker, local).
- **Security (~120):** authn, RBAC, tenant, injection (+WAF-aware), phân trang, **NUL byte**, **BOLA/IDOR 2 Operator**, **multi-tenant thật** (tự skip + ghi ARCH-01), **mass-assignment/BOPLA**, **thu hồi token** (AUTH-01), **xử lý file xấu** (bomb/JS/polyglot/traversal), **MinIO & presign TTL**, CORS/headers, HMAC AI2, cấu hình prod tĩnh, SCA. `xfail` của SEC-01/03/05 đặt `strict=True` để báo khi được fix.
- **Performance (10 + opt-in):** latency có ngân sách; scaling 1→10→50; **stress/spike + thu tài nguyên**; **throughput pipeline**; soak (locust).
- **E2E (16):** upload→OCR→AI2→`PENDING_REVIEW`→đọc OCR/cấu trúc/finding→chia sẻ→reviewer mở hàng đợi; **nội dung đối kháng** (prompt injection + stored-XSS phía API): pipeline vẫn hoàn tất, text trả về là JSON (không phải HTML thực thi), injection "approve tất cả" không tự duyệt hồ sơ.

**Chưa phủ (khuyến nghị tiếp):** XSS render phía trình duyệt (cần Playwright/DOM); multi-tenant thật (chờ ARCH-01); quét image trivy trong CI; perf PDF nhiều trang/50MB và máy sinh tải riêng.

## 8. Việc cần làm theo ưu tiên

| # | Việc | Liên quan |
|---|---|---|
| 1 | Backend nhiều worker + metrics multiprocess + khoá vòng bảo trì | PERF-01 |
| 2 | Đổi `tenant_id` mapper sang user-attribute; chạy lại test multi-tenant | ARCH-01 |
| 3 | Kiểm tra user-active/denylist cho thao tác nhạy cảm (hoặc back-channel logout) | AUTH-01 |
| 4 | Commit trước khi trả response ở handler ghi; email qua BackgroundTasks | BUG-01 |
| 5 | Chặn `\x00` ở middleware → 400 (đặc biệt query param) | SEC-04 |
| 6 | Profile & tối ưu `GET /runs` | PERF-02 |
| 7 | Tắt route lab AI2 mặc định; bind cổng dev về localhost | SEC-03 |
| 8 | Thêm `X-Frame-Options`/CSP vào Caddy | SEC-01 |
| 9 | Cập nhật image local theo `develop` (SEC-02/05 đã fix); `npm audit fix` | SEC-02/05, SCA |
| 10 | Đưa `pytest -m "security and static"` + SCA vào CI; chạy `run-qa` sau deploy | — |

## 9. Chạy lại

```powershell
# Local
.\qa\scripts\run-qa.ps1 -Pipeline

# Production (chỉ đọc + E2E nhỏ) — đặt mật khẩu qua biến môi trường, không ghi vào file
$env:QA_ENV="prod"; $env:QA_BACKEND_URL="https://api.contract-intelligence.tech"
$env:QA_KEYCLOAK_URL="https://auth.contract-intelligence.tech"
$env:QA_FRONTEND_URL="https://contract-intelligence.tech"
$env:QA_KEYCLOAK_REDIRECT_URI="https://contract-intelligence.tech/auth/callback"
$env:QA_ALLOWED_ORIGIN="https://contract-intelligence.tech"
# $env:QA_ADMIN_PASSWORD=... (và OPERATOR/REVIEWER)
uv run --with-requirements qa\requirements.txt pytest qa\smoke qa\security
```

Kết quả: `qa/reports/SUMMARY.md` (local), `qa/reports-prod/SUMMARY.md` (prod), `qa/reports/sca/`. Chi tiết biến cấu hình và chế độ free: [`qa/README.md`](../../qa/README.md).
