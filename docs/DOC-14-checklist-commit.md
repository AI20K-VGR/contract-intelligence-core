# DOC-14 · Checklist cam kết với mentor

> **Contract Intelligence** — Mỗi người điền phần của mình rồi gửi lại.

---

## 0. Thông tin

| Trường | Nội dung |
|---|---|
| Mã tài liệu | DOC-14 — Checklist cam kết với mentor |
| Ngày viết | 30/09/2026 |
| Người viết | Trần Thị Kiều Trang (Lead) |
| Team | FE: Trang · BE: Chương · AI1: Đức Dũng · AI2: Văn Dũng |

Tick ô khi tính năng đó sẵn sàng deliver. Cột mô tả ghi tính năng. Cột xử lý ghi mình làm phần đó như thế nào.

---

## 1. Trang — Frontend

| | Mô tả tính năng sẵn sàng deliver | Mình xử lý như nào |
|---|---|---|
| - [ ] | Màn thẩm định điều khoản và màn xung đột chỉ còn hai hướng: đúng, sai | Bỏ nút "Sửa nhận định" và mọi trạng thái nằm giữa |
| - [ ] | Chia sẻ hồ sơ: chỉ đọc hoặc được sửa, có ngày hết hạn | Form chọn `read` hoặc `edit` và ngày hết hạn. Quá hạn thì mở hồ sơ bị từ chối |
| - [ ] | Một file gồm cả hợp đồng và phụ lục tách thành nhiều tài liệu trong cùng bộ hồ sơ | Người dùng thấy các phần đã tách và xác nhận vai trò từng phần. Bấm xác nhận xong, mỗi tài liệu một vai trò |
| - [ ] | Xung đột hiện cả mâu thuẫn trong cùng một hợp đồng | Màn đối soát đọc cùng cách với cặp có phụ lục. So hai hợp đồng khác nhau vẫn là D12, Sprint 3 |
| - [ ] | Tiến độ phân tích cập nhật ngay khi có sự kiện | Màn tiến độ nghe SSE `/runs/{id}/events`. Hết SSE thì mới hỏi lại định kỳ. Rời trang thì đóng kết nối |
| - [ ] | Luồng demo đi một mạch: danh sách hồ sơ, mở hồ sơ, xem trích dẫn, rồi xác nhận | Danh sách hồ sơ → mở hồ sơ → bấm giá trị thì sáng vùng trích → xác nhận hoặc từ chối |

---

## 2. Chương — Backend

| | Mô tả tính năng sẵn sàng deliver | Mình xử lý như nào |
|---|---|---|
| - [x] | **Đăng nhập, tenant và phân quyền.** Đăng nhập Keycloak SSO; 3 vai trò OPERATOR / REVIEWER / ADMINISTRATOR; mỗi người chỉ thấy hồ sơ của tenant mình và hồ sơ mình sở hữu hoặc được chia sẻ; chia sẻ có mức `read` / `edit` và ngày hết hạn | Backend kiểm JWT RS256, `issuer`, `audience`, `exp`; header `X-Tenant-Id` phải khớp claim. Mọi thao tác trên hồ sơ đi qua **một** hàm quyết định quyền (`shared/acl.py`), mặc định từ chối. Có bộ test tự quét mọi endpoint từ OpenAPI: người ngoài (khác tenant, cùng tenant không quyền, quyền hết hạn, quyền bị tắt) không lấy được dữ liệu nào: **M-07 = 0/136 trên 32 endpoint** |
| - [x] | **Tải hồ sơ lên và OCR không treo.** Tải PDF lên, AI1 OCR qua Kafka, file lớn không vỡ Kafka, OCR lỗi một phần thì giữ phần đã xong, màn tiến độ cập nhật trực tiếp | Upload → MinIO → Kafka `dossier.uploaded` → worker gửi lệnh AI1. Kết quả OCR lớn đi qua MinIO, Kafka chỉ mang đường dẫn (kiểm URI, dung lượng, sha256). Worker commit offset thủ công, thử lại có backoff, đẩy bản ghi hỏng sang `<topic>.dlq`, bỏ qua bản ghi đã xử lý (`processed_event`). Watchdog: quá hạn theo số trang thì `FAILED` với `AI1_TIMEOUT`, không treo. `POST /ocr/retry-failed` chỉ OCR lại tài liệu còn thiếu. Tiến độ đẩy qua SSE từ bảng `run_event` |
| - [x] | **Tách file trộn và duyệt hồ sơ.** Một PDF có cả hợp đồng và phụ lục được tách thành từng tài liệu; reviewer xử lý từng mục; đóng hết mục thì hồ sơ thành "Đã rà soát", admin bấm duyệt thành "Đã duyệt" | `POST /split` cắt PDF theo khoảng trang người dùng xác nhận, trước khi OCR, để không trang nào bị OCR hai lần. Review action có khoá phiên bản (`base_version`, trùng thì 409) và khoá dòng hồ sơ `FOR UPDATE` để hai reviewer không đè nhau. Đóng mục cuối → `reviewed`; `POST /approve` → `approved`; hồ sơ và job cùng đổi; ghi `audit_event` cho review, duyệt, khoá. Frontend đã xác nhận màn hình chạy đúng (review PR #36, 30/09) |
| - [x] | **Hỏi đáp có lịch sử và xoá hồ sơ sạch.** Câu hỏi và câu trả lời còn sau khi khởi động lại; mỗi người chỉ thấy lịch sử của mình; xoá hồ sơ nhiều file không lỗi | Lưu câu trả lời vào bảng `query_answer` cùng transaction với `query_trace` (bảng chỉ thêm, không sửa). `GET /queries?scope=mine\|all`: `all` chỉ cho chủ hồ sơ hoặc admin. Xoá hồ sơ: tombstone ngay, purge nền, xoá cả câu trả lời và object MinIO; sửa lỗi hồ sơ nhiều tài liệu vướng ràng buộc `sha256` (migration `v19`) |
| - [x] | **Cấu hình an toàn để đưa lên server, và contract đã chốt.** Server không chạy với mật khẩu mặc định; phiên bản API rõ ràng; database tạo lại được từ đầu; contract với Frontend và AI2 có văn bản | Staging/prod từ chối khởi động nếu secret còn rỗng, `password123`, `generate`, `changeme` hoặc `*_dev` (lỗi chỉ nêu tên biến). Backend `2.0.0`, contract FE–BE `v1.1.0` (DOC-05b). 19 migration nối thẳng, một head, chạy sạch trên PostgreSQL 16. Contract: DOC-05 (spec), DOC-05b v1.1.0 (FE–BE), DEC-BE-AI2-01 (BE–AI2, Lead và AI2 đã duyệt), DOC-05e (hướng Kafka Sprint 3) |

### 2.1 Bằng chứng Backend

Tất cả đã merge vào `develop` (đầu `bb17cec`, 30/09). PR #36 merge sau khi có 2 approval trên `41ce4c2` (Trang, Đức Dũng); cây code của `develop` trùng với `41ce4c2`.

**CI trên GitHub** (commit `41ce4c2`, đúng bản đã merge): [Backend CI, success](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/36698956541) gồm import-linter, Ruff, MyPy, Unit, Integration.

**Chạy lại trên máy ngày 30/09** (PostgreSQL 16 thật, không bỏ qua test nào): `uv run pytest tests/unit tests/architecture tests/integration tests/contract_intelligence` → **542 passed**.

| # | PR và commit chính | Test (số test pass khi chạy lại) |
|---|---|---|
| 1 | PR #28: `c212496` (ACL mọi route đọc, M-07), `ce0633e` (chia sẻ read/edit, hết hạn) | `test_auth_jwt_service.py`, `test_auth_dependencies.py`, `test_route_registration_authz.py`, `test_auth_endpoints.py`, `test_upload_tenant_header.py`: **37 passed**. `test_dossier_acl_consistency.py`, `test_share_permissions.py`, `test_tenant_isolation.py` (M-07 = 0/136), `test_postgres_share_filter.py`: **37 passed** |
| 2 | PR #28: `fc6f19e` (worker chịu restart), `b3d0418` (watchdog AI1), `db7f8d9` (`processed_event`), `a348fbc` (DLQ), `116a252` (kết quả OCR qua MinIO), `584435b` (AI2 theo số trang, thử lại lỗi tạm). PR #29 → #28: `b189ddd` (SSE). PR #36: `709e70d` (giữ OCR đã xong) | `test_worker_pipeline_run.py`, `test_worker_consumer.py`, `test_ai2_adapter_retry.py`, `test_run_events.py`, `test_postgres_run_events.py`: **76 passed**. Hợp đồng Kafka AI1: `docs/DOC-05d-kafka-ai1-ocr-contract.md` |
| 3 | PR #36: `d667bd9` (tách file), `cd9205a` (luồng duyệt); PR #28: `d58d83b` (review action) | `test_split_mixed_file.py`, `test_review_action_hardening.py`, `test_review_to_approval_flow.py` (đi hết review → reviewed → approve qua API, không gán sẵn trạng thái), `test_postgres_invariants.py` (khoá dòng, hai reviewer đóng hai mục cuối cùng lúc), `test_approval_router.py`: **37 passed** |
| 4 | PR #36: `bdcb62d` (lịch sử hỏi đáp), `3610b5a` (xoá hồ sơ nhiều file) | `test_query_history.py`, `test_dossier_deletion.py`, `test_postgres_purge.py`, `test_dossier_deletion_service.py`: **14 passed** |
| 5 | PR #38 → #36: `3e06608` (chặn secret, 2.0.0); PR #36: `fbd1f13` (API contract v1.1.0); PR #37 (DEC-BE-AI2-01), PR #41 (DOC-05b v1.1.0) | `test_settings_prod_guard.py`, `test_versioning.py`, `tests/architecture`: **22 passed**. `alembic heads` → một head `v19`; `alembic upgrade head` chạy sạch trên PostgreSQL 16 |

### 2.2 Chưa sẵn sàng (không tick)

| Việc | Tình trạng |
|---|---|
| Bản online trên server | Đã deploy 04/10/2026 lên một máy chủ Ubuntu (`app-`, `api-`, `auth-150-95-104-132.sslip.io`) bằng `deploy/` và workflow `deploy` (tự chạy khi merge vào `develop`); kiểm tra từ bên ngoài qua, cổng AI2 không mở. Chưa xong: nghiệm thu luồng tải lên → OCR → AI2 → thẩm định trên server; máy mới có 2 GB RAM (đang dùng swap); bước duyệt trước khi deploy chờ admin repo bật (`deploy/README.md`) |
| Nghiệm thu file ~50 MB và PDF ~200 trang | Chưa chạy trên server (DOC-11 §1 mục 10–11) |
| Gửi lại cùng attempt sang AI2 không bị 409 (DEC B1) | Lỗi đã biết: `created_at` của snapshot lấy giờ hiện tại mỗi lần dựng request, nên worker gửi lại sau khi restart bị AI2 trả 409. Hạn 01/10 |
| Việc Backend còn lại của DEC-BE-AI2-01 (B2–B8) | Digest `/query` do AI2 trả, chặn hồ sơ quá 6 tài liệu, ánh xạ `BLOCKED`, override compose online và DB `ai2`/pgvector, xoá hàm AI2 cũ, test ký mẫu. Theo lịch 01–03/10 |
| Re-OCR theo trang và proxy `/ai/jobs` | Còn gọi AI1 qua client HTTP cũ (`AI_SERVICE_URL`), không hợp với đường Kafka hiện tại; `/ai/jobs` chưa kiểm tenant. Cần gỡ hoặc chuyển sang Kafka |
| Kafka Backend ↔ AI2 | Hướng Sprint 3 (DOC-05e, kế hoạch `plans/260930-be-ai2-kafka/plan.md`), chờ AI2 duyệt DOC-05e §13; hiện vẫn chạy HTTP |
| DOC-11 §4.2 mục 5, 6, 12 | Chia OCR theo cụm trang, mã lỗi 429/529, finding hợp đồng–hợp đồng: chưa làm |
| Audit đầy đủ | Duyệt, khoá, review đã ghi `audit_event`; đổi chia sẻ, xoá hồ sơ, đổi vai trò người dùng mới ghi vào activity feed |

---

## 3. Đức Dũng — AI1

| | Mô tả tính năng sẵn sàng deliver | Mình xử lý như nào |
|---|---|---|
| - [ ] | Đọc được hợp đồng scan tiếng Việt chất lượng xấu. Bộ thử là file 202 trang, 150 DPI, nhiễu, hơi nghiêng, chữ nhỏ 6–7 pt | Đo lượng mực để định tuyến từng trang → Mistral đọc → kiểm chéo. Hai bản lệch nhau thì GPT phân xử |
| - [ ] | PDF có lớp text thì không tốn tiền OCR | File số đi thẳng đường đọc text. Trang trắng được bỏ qua |
| - [ ] | Dựng lại bảng, kể cả bảng kéo qua nhiều trang | Nối bảng qua ba lớp: luật cứng → chấm điểm → trọng tài |
| - [ ] | AI2 dẫn chứng đúng Điều / Khoản / Điểm | Dựng cấu trúc Điều / Khoản / Điểm thành StructuralNode |
| - [ ] | Bấm vào một giá trị trên UI là thấy vùng chữ trên trang gốc và mức tin cậy OCR | Mỗi citation mang bbox |

---

## 4. Văn Dũng — AI2

| | Mô tả tính năng sẵn sàng deliver | Mình xử lý như nào |
|---|---|---|
| - [ ] | **Xử lý cả hồ sơ nhiều file** (thân hợp đồng + phụ lục): trích xuất fact, finding, mỗi mục có citation trỏ đúng dòng và bbox của AI1 | Backend gọi `POST /jobs/idp` rồi poll `GET /jobs/{id}`, ký HMAC theo DEC-BE-AI2-01. Gửi trùng thì trả lại cùng job, không xử lý hai lần. AI2 tự kiểm mọi citation trước khi trả; kết quả chỉ là đề xuất, reviewer duyệt mới publish. Bổ sung trước 01/10: trả `query_snapshot_digest` (A1), cờ retry theo mã lỗi (A2) |
| - [ ] | **Phát hiện mâu thuẫn giữa thân hợp đồng và phụ lục**, có trích dẫn ở cả hai phía | LLM `gpt-4o-mini` trích xuất fact (giá trị, phí, thời hạn…); luật cố định so từng cặp giữa thân hợp đồng và phụ lục, và giữa các phụ lục. Thiếu citation một phía thì hạ xuống "cần rà soát"; phụ lục chưa xác nhận quan hệ thì gắn nhãn "chưa xác nhận". LLM lỗi hoặc hết trần (20 lần gọi mỗi hồ sơ) thì vẫn trích xuất bằng luật, không làm hỏng job |
| - [ ] | **Phát hiện mâu thuẫn trong cùng một hợp đồng** (một thông tin ghi hai giá trị khác nhau, ví dụ giá trị hợp đồng) | So các fact trích xuất trong thân hợp đồng; mỗi loại thông tin báo một cặp giá trị khác nhau, citation trỏ cả hai chỗ. Chưa so hai điều khoản trong cùng hợp đồng. Bổ sung unit test và script dữ liệu mẫu trước demo |
| - [ ] | **Hỏi đáp trên hồ sơ** (`/query`): trả lời kèm trích dẫn, không bịa khi thiếu bằng chứng | Truy xuất theo từ khoá + vector (`text-embedding-3-small`, lưu pgvector), rồi `gpt-4o-mini` trả lời chỉ từ đoạn đã truy xuất. Câu hỏi gắn với đúng bản snapshot của hồ sơ. Trả 1 trong 4 trạng thái (`ANSWERED`, `NEEDS_REVIEW`, `INSUFFICIENT_EVIDENCE`, `BLOCKED`). LLM quá 15 giây thì trả kết quả truy xuất có citation. Chỉ nhận request có chữ ký của Backend |
| - [ ] | **Dữ liệu AI2 bền trên PostgreSQL**: khởi động lại hay tạo lại container không mất job và không hỏng hỏi đáp | Chuyển job store, query store, run store và vector sang schema `ai2` trong Postgres chung (ADR-14), migration riêng bằng alembic, bỏ hẳn SQLite. Test chạy trên Postgres thật. Hạn: trước deploy online 03/10 (A7) |
| - [ ] | **Chạy an toàn và kiểm soát chi phí trên bản online** | LLM, embedding, egress bật/tắt bằng env của `ai2-service` (A8); key OpenAI riêng cho bản online, không đưa vào git; trần 5 USD/tháng, hết trần thì tắt env. Chỉ xử lý hợp đồng mẫu đã ẩn thông tin. Không mở cổng 8002 ra Internet, healthcheck `/healthz` không gọi LLM, image không chứa dữ liệu chạy thử |

---

**Hết DOC-14 · Checklist cam kết với mentor**
