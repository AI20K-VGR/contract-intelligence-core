# Research C: Postgres schema `ai2`, queue, lưu hồ sơ, E2E Backend<->AI2, uplift chất lượng

Ngày: 2026-09-30. Phạm vi: 5 câu hỏi mở của plan C (`plan.md` "Quyết định đã khoá" D-1..D-8 và "Features" đã đọc; không re-litigate). Không sửa file nào ngoài báo cáo này. Không chạy probe động nào (chỉ read/grep + web); mọi chỗ cần probe thật đều gắn nhãn.

Nhãn: `OBSERVED` = đọc/grep được, có file:line. `[ASSUMED]` = suy luận chưa chạy. `[PRIOR]` = kiến thức huấn luyện chưa kiểm. Số dòng có dấu `~` là xấp xỉ (đọc qua `sed` cắt đoạn).

Ghi chú nền (cập nhật 2026-09-30): phase files đã được điền sau báo cáo research; nội dung bên dưới là nghiên cứu đầu vào, không phải trạng thái hiện tại của các phase.

---

## PART 1 - OBSERVED trong repo

### 1.1 Trạng thái AI2 hiện tại (jobs, nonce, lease)
- `ai-service/app/tools/jobs.py:24-25,48-51`: đường dẫn mặc định `data/ai2/jobs.sqlite`, override bằng `AI2_JOB_DB`. WAL bật ở `jobs.py:59-60`.
- `jobs.py:68-85`: bảng `jobs` có `request_json`, `wire_json`, `result_json`, `worker_token`, `lease_until_ms`, `UNIQUE (tenant_id, idempotency_key, attempt)` (dòng 84). `jobs.py:96-103`: bảng `service_nonces` PK `(tenant_id, nonce)` + `created_ms`.
- Nonce KHÔNG có TTL/dọn dẹp: trong `jobs.py:140-358` chỉ có một `DELETE` duy nhất là `clear()` xoá bảng `jobs` (~dòng 355). Bảng nonce chỉ tăng.
- Claim: `jobs.py:240-273` (`BEGIN IMMEDIATE`, `lease_ms=60_000`, reclaim khi `RUNNING` và lease đã hết, trả `worker_token`). `set_wire` (~dòng 279+) ghi có điều kiện `WHERE ... worker_token=?` -> đã có fencing chống worker cũ ghi đè.
- `create_or_get` mở `BEGIN IMMEDIATE` (~dòng 157), tra nonce trước, replay khác payload -> `JobNonceReplayConflict`; insert job trạng thái `QUEUED` (~dòng 205-230).
- `list_succeeded` (~dòng 338) trả job thành công, thứ tự cũ -> mới.
- `ai-service/pyproject.toml:33`: chỉ có extra `web = [fastapi, uvicorn, httpx]`. Không có sqlalchemy/psycopg/alembic trong ai-service (grep chỉ khớp dòng 33).

### 1.2 Thực thi job và hydrate
- `ai-service/app/api/main.py:1694`: `background_tasks.add_task(_run_wire_job, job_id, request.model_dump())`; docstring `main.py:1636-1638` tự nói "production may move the same worker function to a durable queue".
- `main.py:1690-1694`: `if created or stored["status"] in {"QUEUED","RUNNING"}` thì thêm task -> Backend gửi lại cùng (key, attempt) sẽ enqueue thêm một task; `claim()` chặn chạy đôi (RUNNING còn lease -> `None`, `main.py:~175-178`).
- `main.py:165-170`: worker gọi lại `verify_service_envelope(payload)` ngay đầu -> job cũ hơn TTL envelope sẽ fail khi requeue (đúng như bạn đã ghi). Đây là chặn cho mọi thiết kế "requeue sau restart".
- `main.py:83-116`: `_hydrate_store_from_jobs` lặp mọi job SUCCEEDED, gọi `adapt_be_ai2_processing_request(payload,...)` rồi `STORE.put(adapted.record)` (dòng ~100-110). Chỉ dựng lại từ REQUEST, KHÔNG nạp kết quả job. Chạy ở `@app.on_event("startup")` (`main.py:119-120`), eager, tuần tự, mọi dossier.
- `ai-service/Dockerfile.ai2` (dòng cuối): `uvicorn app.api.main:app --host 0.0.0.0 --port 8002`, không `--workers` -> một process, một replica.
- `DossierRecord` là `@dataclass` (`ai-service/app/tools/store.py:23-49`) chứa `pages, nodes, tables, facts, chunks, source_files, permissions_by_actor...`; các phần tử là pydantic model (`node.model_dump()` được gọi ở `l1_retrieval.py:~310`). Cần serializer tuỳ biến để lưu.

### 1.3 Ứng viên nguyên nhân "câu trả lời lệch sau restart" (chưa xác nhận)
- `ai1_snapshot_adapter.py` có nhiều `set[str]` (dòng 168, 498, 1105, 1710-1713) và dict-comprehension (165, 167, 257, 592). Một số chỗ có `sorted(...)` (486, 562, 668, 1218, 1360) nhưng không phải mọi `set` đều được sort trước khi lặp.
- `jobs.py` lưu `request_json` bằng `json.dumps(..., sort_keys=True)` (~dòng 215) trong khi lần chạy đầu dùng `request.model_dump()` (`main.py:1694`) -> thứ tự khoá dict khác nhau giữa run đầu và hydrate.
- `[ASSUMED]` Hai điểm trên là ứng viên (a) thứ tự lặp `set[str]` phụ thuộc `PYTHONHASHSEED` mỗi process; (b) thứ tự khoá dict sau `sort_keys`. Chưa chạy nên KHÔNG kết luận. Probe rẻ: chạy adapter trong 2 subprocess với `PYTHONHASHSEED=1` và `=2` trên cùng snapshot, so JSON dump của record; và so record "run đầu" với record "sau hydrate". Nếu khác -> gốc lỗi nằm ở tính không xác định của adapter, không nhất thiết cần lưu record (xem 2.3).
- Cũng có thể hydrate thiếu bước hậu xử lý của `_run_wire_job` (facts/LLM sau `main.py:~195`); dòng 200-268 chưa đọc.

### 1.4 Hạ tầng repo (compose, CI, Alembic, Backend)
- `docker-compose.yml:188-213`: `backend-db` = `postgres:16-alpine`, `POSTGRES_USER: ci` (dòng 194, là superuser của image), volume `backend_pgdata` (dòng 202) -> script `initdb.d` sẽ KHÔNG chạy lại trên volume đã có (Postgres chỉ chạy initdb.d khi data dir rỗng; ghi chú ở dòng 199-201 xác nhận migrations chạy qua alembic chứ không qua initdb.d).
- `docker-compose.yml:442-475`: `ai2-service`, port 8002, volume `ai2_data:/app/data/ai2` (dòng 461; khai báo volume dòng 537), alias `ai2`; Backend nhận `AI2_BASE_URL` (dòng 326, 402). `backend` phụ thuộc keycloak/kafka/minio (dòng 263-270) -> không thể "chỉ Backend+AI2" bằng `docker compose up backend` nguyên trạng.
- `backend/alembic/env.py:33` `target_metadata = Base.metadata`; `env.py:49-57` `context.configure(connection=..., target_metadata, compare_type, compare_server_default)` KHÔNG có `version_table_schema`/`include_schemas`/`include_name` (grep xác nhận). Async engine ở `env.py:60-65`. Backend dùng `sqlalchemy[asyncio]>=2.0.30` (`backend/pyproject.toml:15`), `asyncpg>=0.29.0` (dòng 17); lock `sqlalchemy==2.0.54`, `asyncpg==0.31.0` (`requirements.txt:204,44`).
- Backend không dùng schema tuỳ chỉnh: grep `schema=|search_path|CREATE SCHEMA|MetaData(` trong `backend/src`,`backend/alembic` chỉ ra `v8__dossier_deletion.py:130` (`SET search_path = public` trong hàm). Có `v2__create_app_user.py` (chỉ thấy tên file; chưa đọc xem role app có phải superuser không).
- CI: `backend-ci.yml:125-150` job integration chạy pytest với "SQLite in-memory" (không Postgres). `ai-service.yml:22` là stub "no CI defined for ai-service yet" (bổ sung bởi plan A phase 4).
- Digest: `backend/src/contract_intelligence/worker.py:78-110` `_ai2_query_snapshot_digest` băm `attempt_id = f"attempt:{request.get('attempt')}"` (trong payload băm) -> đổi `attempt` thì digest đổi, đúng như mô tả.
- ADR-02: `docs/DOC-04-architecture.md:93` nói `ai-service` "không kết nối PostgreSQL, không sở hữu queue/lease/callback lifecycle, ... stateless". Lưu ý mâu thuẫn có sẵn: SQLite `jobs.py` đã sở hữu lease từ P3, tức code hiện tại đã lệch ADR-02; ADR-14 nên hợp thức hoá luôn điểm này (changelog ADR-02/03 ở `DOC-04-architecture.md:989`).

### 1.5 Chất lượng: luật rò rỉ và truy xuất
- `ai-service/app/reasoning/l0_rules.py:336-394`: các nhánh khớp chuỗi câu hỏi + id node cố định: "điều 3" (dòng 336, cần label `Điều 3`), "thanh toán" (UNNUMBERED_BLOCK), "phụ lục 7" -> trỏ `cl_9`, `not_comparable` + "usd" -> `field_usd`, "xây lắp/thiết bị" -> `field_penalty_build`/`field_penalty_equip`. Đây là rò test-set (plan A: `plans/260929-2323-ai2-a-measure-baseline/plan.md:77` VD-6, `:207`, `:227` allowlist phải về rỗng khi C nghiệm thu, `:274` R11, `:286` "21/24 bị thổi phồng").
- Plan A đã có sẵn: `--variant-seed`, `--golden-dir`, bucket `fixture_tuned_legacy`, report theo split (`plan.md:286`), lint `evals/tests/test_no_eval_leakage.py` (`:227`). Có thư mục `evals/` trong repo.
- `l1_retrieval.py:301-320` `_lexical_hits`: fallback đếm số term (bỏ dấu, len>=3, stoplist) xuất hiện dưới dạng chuỗi con trong `raw_label + text + structured_value` của từng node, lấy top 12, KHÔNG IDF, KHÔNG chuẩn hoá độ dài. `bm25_lite_score` có sẵn ở `:494-520` nhưng docstring nói chỉ dùng cho test và `search_semantic`, không dùng trong `_lexical_hits`. `expand_query` ở `:51`; các bộ lọc theo cue ở `:345,382,435`; `structured_keys` `:241`; `_exact_label_ids` `:257`; có `VectorRecallService` (import dòng 9).
- Đơn vị truy xuất là node (`record.evidence_nodes()`); câu "chưa bao gồm VAT" nằm trong node đoạn dài chứ không phải node riêng (đã cho trong đề bài). Có sẵn `_char_offset` cho span (`ai1_snapshot_adapter.py:1654`).

---

## PART 2 - External (nguồn độc lập, đánh giá độ tin cậy)

Độ tin cậy: A = tài liệu chính thức; B = maintainer/blog kỹ thuật có code; C = bài tổng hợp/blog chung (chỉ làm chứng phụ).

### Câu 1 - Schema-per-service, role, Alembic, driver

Tài liệu tham chiếu:
- PostgreSQL docs, Schemas (A): https://www.postgresql.org/docs/16/ddl-schemas.html
- Alembic runtime config (A): https://alembic.sqlalchemy.org/en/latest/api/runtime.html
- Alembic autogenerate (A): https://alembic.sqlalchemy.org/en/latest/autogenerate.html
- SQLAlchemy PostgreSQL dialect (A): https://docs.sqlalchemy.org/en/20/dialects/postgresql.html
- Alembic issue #710 (B): https://github.com/sqlalchemy/alembic/issues/710 ; discussion #940 (B): https://github.com/sqlalchemy/alembic/discussions/940 ; gist cấu hình (C): https://gist.github.com/h4/fc9b6d350544ff66491308b535762fee ; thread "alembic_version creation fails ... new schema" (B): https://groups.google.com/g/sqlalchemy-alembic/c/UZ0xZUKjUqI
- Psycopg 3 async docs (A): https://www.psycopg.org/psycopg3/docs/advanced/async.html

Phát hiện (đối chiếu >=3 nguồn):
1. Quyền: mọi người có `USAGE` trên `public` mặc định; `CREATE` trên `public` chỉ còn cho PUBLIC ở DB nâng cấp từ <=14; PG15+ đã đóng. Docs khuyên `REVOKE CREATE ON SCHEMA public FROM PUBLIC` và mẫu "secure schema usage pattern" (mỗi schema một chủ, không schema nào cho PUBLIC CREATE). Compose dùng PG16 (`docker-compose.yml:189`) nên `public` an toàn hơn, nhưng DB được `pg_upgrade` từ <=14 thì phải tự REVOKE.
2. Schema mới do role khác tạo mặc định KHÔNG cấp gì cho PUBLIC -> role Backend "không có quyền" trên `ai2` là mặc định, TRỪ KHI Backend chạy bằng superuser/chủ DB (bypass). Compose đang dùng `ci` = `POSTGRES_USER` (superuser) (`docker-compose.yml:194`). Nếu Backend vẫn chạy bằng `ci` thì tiêu chí "backend role has none" không có ý nghĩa cưỡng chế được. `[PRIOR]` từ mô hình quyền PG chuẩn; nguồn A trên xác nhận mẫu, không nêu riêng trường hợp superuser.
3. `search_path`: SQLAlchemy docs khuyên giữ `search_path` mặc định, tránh trùng tên user với schema (`"$user"`), và dùng schema tường minh khi reflect. Kết luận thực dụng: khai báo `MetaData(schema="ai2")` tường minh + `ALTER ROLE ai2_app SET search_path = ai2` chỉ là lưới an toàn; đừng dựa vào `SET search_path` theo session nếu sau này có PgBouncer transaction pooling `[PRIOR]`.
4. Alembic: `version_table_schema` đặt bảng version vào schema riêng; `include_schemas=True` + `include_name` để giới hạn autogenerate (nếu không lọc, autogenerate quét mọi schema và sẽ đề xuất DROP bảng của Backend); `include_name` nhận `parent_names["schema_name"]`, schema mặc định có `name=None`. Bảng version phải nằm trong schema đã tồn tại: thread Google Groups ghi nhận việc tạo `alembic_version` thất bại khi schema chưa có -> `CREATE SCHEMA` phải làm trước bởi bước bootstrap, không phải bởi migration đầu tiên chạy bằng role thiếu quyền.
5. Driver: psycopg3 có cả sync (`postgresql+psycopg`) lẫn async (`postgresql+psycopg_async`); docs psycopg nêu rõ async KHÔNG tương thích `ProactorEventLoop` mặc định của Windows (cần SelectorEventLoop). Môi trường dev của repo là Windows (env session: win32). asyncpg thì chạy được trên Windows nhưng Backend đã dùng asyncpg, AI2 khác codebase/khác phong cách.

Adoption risk: Postgres schema-per-service + Alembic đa schema là mẫu phổ biến, không có breaking change lớn; Alembic không có hỗ trợ đa-tenant chính thức nhưng dùng 1 schema/1 env riêng thì ổn. Rủi ro chính là vận hành: hai chuỗi migration trên cùng DB, một chuỗi cần role có DDL.

### Câu 2 - Hàng đợi Postgres

- PostgreSQL docs SELECT (A): https://www.postgresql.org/docs/16/sql-select.html . Trích: SKIP LOCKED "provides an inconsistent view of the data ... not suitable for general purpose work, but can be used to avoid lock contention with multiple consumers accessing a queue-like table".
- Prisma blog (B): https://www.prisma.io/blog/you-dont-need-a-job-queue-postgres-already-has-skip-locked
- Netdata academy (C/B): https://www.netdata.cloud/academy/update-skip-locked/
- Amine Diro (B, có code): https://aminediro.com/posts/pg_job_queue/
- Issue ancore #1418 (C, minh hoạ lỗi): https://github.com/ancore-org/ancore/issues/1418 ; Medium advisory-lock (C): https://terrislinenbach.medium.com/why-for-update-skip-locked-isnt-enough-using-pg-advisory-xact-lock-to-build-a-correct-postgresql-d3eb9db46473

Đồng thuận giữa các nguồn: (i) claim và đánh dấu RUNNING trong MỘT câu lệnh `UPDATE ... WHERE id=(SELECT ... FOR UPDATE SKIP LOCKED LIMIT 1) RETURNING`; (ii) giữ transaction ngắn: claim -> commit -> làm việc ngoài transaction -> ghi kết quả bằng transaction thứ hai; (iii) BẮT BUỘC visibility timeout/lease + "janitor" đưa job RUNNING quá hạn về QUEUED, nếu không worker chết = job kẹt vĩnh viễn (issue #1418 là ví dụ thật); (iv) hoàn tất/retry phải kiểm token để worker chậm không ghi đè job đã bị claim lại (AI2 đã có: `worker_token` ở `jobs.py` set_wire).

Bảng so sánh:

| Tiêu chí | A. Giữ in-process + Postgres là nguồn sự thật + sweep khi startup/định kỳ | B. Poller thread `FOR UPDATE SKIP LOCKED` | C. Thư viện ngoài (Celery/RQ/procrastinate...) |
|---|---|---|---|
| Sửa code | Nhỏ: thay `sqlite3` bằng SQL Postgres; thêm `requeue_stranded()` gọi ở startup + timer | Trung bình: vòng poll, backoff, dừng êm | Lớn, thêm phụ thuộc + broker/worker process |
| Đúng cho 1 replica | Đủ | Đủ, hơi thừa | Thừa |
| Đa replica sau này | Cần đổi sang B | Sẵn sàng | Sẵn sàng |
| Khôi phục sau restart | Có nếu sweep | Có (janitor) | Có |
| Rủi ro | Task trong RAM vẫn mất khi crash giữa job (được sweep bù) | Poll latency, hai chỗ cấu hình lease | Bề mặt vận hành rộng, vi phạm YAGNI |

Điểm mấu chốt (suy từ nguồn + code): với dispatch theo `job_id` (Backend gửi -> AI2 nhận -> xử lý ngay), KHÔNG cần SKIP LOCKED; một `UPDATE ... WHERE job_id=? AND (status='QUEUED' OR (status='RUNNING' AND lease_until < now())) RETURNING worker_token` đã atomic và tương đương `claim()` hiện có (`jobs.py:240-273`). SKIP LOCKED chỉ cần khi có vòng "lấy job bất kỳ tiếp theo" với nhiều consumer. Idempotency: giữ `UNIQUE(tenant_id, idempotency_key, attempt)` + `INSERT ... ON CONFLICT DO NOTHING RETURNING` rồi SELECT khi rỗng (`[PRIOR]` cú pháp chuẩn PG). Nonce: thêm cột `expires_at` = `created + TTL envelope + độ lệch đồng hồ` và xoá `WHERE expires_at < now()` cơ hội (mỗi N lần insert) hoặc theo timer; TTL nonce chỉ cần >= thời gian envelope còn được chấp nhận (`[PRIOR]` từ thiết kế replay-protection; TTL envelope thực tế lấy từ `verify_service_envelope`, chưa đọc).

Chi tiết cần tránh: (1) worker re-verify envelope (`main.py:169`) làm requeue của job cũ luôn fail -> sau khi accept ở `POST /jobs`, lưu `tenant_id`/`actor_id` đã xác thực vào cột job và để worker dùng chúng, không verify lại `exp`. (2) Lease 60s cố định, không thấy heartbeat -> job >60s bị claim lại; fencing bằng `worker_token` bảo vệ ghi, nhưng vẫn tốn tính toán đôi; mục tiêu p95<20s (D-6) nên ổn, nhưng thêm heartbeat rẻ nếu có bước LLM dài.

### Câu 3 - Lưu hồ sơ đã xử lý

Nguồn: docs PostgreSQL về TOAST/nén và jsonb `[PRIOR]` (không fetch); ba lựa chọn dưới đây là phân tích thiết kế dựa trên code Part 1, không phải tuyên bố có nguồn ngoài. Nhãn trung thực: phần "kích thước" là `[ASSUMED]`.

| Phương án | Ưu | Nhược |
|---|---|---|
| R1. Chỉ lưu `result_json` (đã có) | Không đổi gì | Không đủ: query cần `DossierRecord` (pages/nodes/tables/facts/chunks, `store.py:24-49`), không chỉ wire result |
| R2. Lưu bản serialize của `DossierRecord` sau khi job SUCCEEDED, nạp lại khi restart | Câu trả lời giống hệt trước restart, không phụ thuộc phiên bản adapter | Cần serializer round-trip; tăng dung lượng; cần `record_schema_version` |
| R3. Dựng lại từ request bằng adapter xác định (hiện tại) | Không lưu thêm | Đã chứng minh lệch (quan sát live); chỉ đúng nếu adapter thực sự xác định và không thiếu bước hậu xử lý |

Khuyến nghị: R2 + fallback R3, nhưng CHẠY PROBE TRƯỚC (1.3): nếu 2 process khác `PYTHONHASHSEED` cho record khác nhau thì phải sửa cả tính xác định (sort mọi `set` trước khi lặp), vì R2 không cứu được câu trả lời của dossier chưa từng lưu (job cũ) và bản build mới có thể lệch khi rebuild.

Thiết kế R2 tối thiểu: bảng `ai2.dossier_record(tenant_id, dossier_id, job_id, attempt, record_schema_version, adapter_version, payload bytea, size_bytes, created_at)`, PK `(tenant_id, dossier_id)` hoặc theo `job_id`. Ghi trong CÙNG transaction với trạng thái SUCCEEDED để không có "job xong mà record chưa lưu". Dùng `bytea` chứa JSON nén (zstd/gzip) thay vì `jsonb`: không truy vấn bên trong, tránh phí parse `jsonb`, TOAST vẫn xử lý giá trị lớn. Nạp LAZY khi `STORE.get` trượt (LRU vài chục dossier) thay vì eager hydrate mọi job như hiện tại (`main.py:95` re-adapt mọi job tuần tự -> thời gian khởi động tăng tuyến tính theo số dossier). Snapshot ~1.6MB (đề bài) -> record cùng bậc, ước 1-5MB thô, nén JSON tiếng Việt thường vài lần `[ASSUMED, cần đo]`. Cần test round-trip: process -> dump -> load -> chạy bộ query vàng -> trả lời byte-identical. Retention: `request_json` (1.6MB) đã được lưu mỗi attempt; thêm record làm dung lượng ~2x/attempt, cần chính sách xoá attempt cũ (mở ở dưới).

### Câu 4 - Harness E2E Backend<->AI2

- testcontainers-python repo/docs (A/B): https://github.com/testcontainers/testcontainers-python ; https://testcontainers-python.readthedocs.io/
- Docker blog về Testcontainers trên GitHub Actions (B): https://www.docker.com/blog/running-testcontainers-tests-using-github-actions/
- freeCodeCamp GitHub service containers (C): https://www.freecodecamp.org/news/how-to-run-integration-tests-with-github-service-containers/
- Issue #905 HealthcheckWaitStrategy + DockerCompose (B): https://github.com/testcontainers/testcontainers-python/issues/905
- DeepWiki DockerCompose module (C): https://deepwiki.com/testcontainers/testcontainers-python/5.1-docker-compose ; QASkills tổng hợp (C): https://qaskills.sh/blog/testcontainers-python-integration-testing

Đồng thuận: Testcontainers chạy trên `ubuntu-latest` không cần cấu hình (Docker sẵn có), không cần khai báo service container/bước migrate riêng; module `DockerCompose` tồn tại nhưng mất phần lớn lợi ích (port động, wait strategy lập trình, dọn Ryuk) và có bug đã biết với healthcheck wait (#905); container reuse chỉ cho local, CI không nên reuse.

Ràng buộc từ repo: Backend service trong compose phụ thuộc keycloak/kafka/minio (`docker-compose.yml:263-270`) và AI2-call nằm trong `worker.py` (Kafka orchestrator). D-2 nói không Keycloak/AI1 -> harness không nên dựng `backend` container đầy đủ. `[ASSUMED]` Backend có thể được gọi in-process (import client AI2 + hàm persist trong `worker.py`) với Postgres thật; cần xác minh (Open question 2).

| Tiêu chí | 1. pytest + testcontainers (PG + AI2 GenericContainer, Backend in-process) | 2. compose profile `e2e` (PG + ai2-migrate + ai2-service) + pytest gọi `docker compose restart` | 3. Cả stack compose |
|---|---|---|---|
| Phạm vi đúng D-2 | Có | Có | Không (kéo keycloak/kafka/minio) |
| Điều khiển restart/mạng | Tốt (`get_wrapped_container().restart()`, Network riêng) | Trung bình (subprocess) | Trung bình |
| Cô lập/dọn dẹp | Tốt (Ryuk, cổng động) | Cần `down -v` thủ công | Kém |
| Thêm phụ thuộc | `testcontainers` (dev) | Không | Không |
| Chạy tay khi demo | Cần pytest | `docker compose --profile e2e up` | Có |
| Rủi ro | Cổng host ngẫu nhiên có thể đổi sau restart container `[PRIOR, phải probe]` -> dùng địa chỉ trong network hoặc cổng cố định | Sửa `docker-compose.yml` dùng chung | Mong manh, chậm |

Cách chạy CI: workflow mới `e2e-backend-ai2.yml` (path filter `backend/**`,`ai-service/**`,`docker-compose.yml`), job build image AI2 cục bộ (buildx + cache GHA) để test đúng commit; job release chạy lại với tag GHCR semver đã pin (D-1). Hiện `backend-ci.yml:125-150` chỉ chạy SQLite in-memory và `ai-service.yml:22` là stub -> E2E là job mới, không mở rộng job cũ.

Khẳng định hành vi tất định (không sleep cố định; poll có deadline):
- LLM tắt: `policy_flags.egress_allowed=False` (`main.py:~196` chỉ tạo `NineRouterClient` khi egress cho phép) + snapshot tổng hợp cố định -> không phụ thuộc mạng/LLM. Benchmark LLM thật vẫn chạy tay (D-7).
- Restart: (1) submit -> poll SUCCEEDED -> query, chuẩn hoá và lưu JSON; (2) restart container AI2 (volume/DB giữ nguyên); (3) query lại -> assert bằng nhau TỪNG byte kể cả thứ tự citation/nhãn nguồn. Đây chính là test hồi quy cho lỗi hiện tại.
- Job kẹt QUEUED: seed một hàng `QUEUED` trực tiếp vào `ai2.jobs` bằng SQL (tất định) rồi khởi động AI2 -> assert sweep chạy nó tới SUCCEEDED; sau đó gọi lại `POST /jobs` cùng (key, attempt) -> cùng `job_id`, không chạy đôi (dựa `claim()` trả `None`). Tránh cách "kill giữa chừng" vì là race.
- Retry `attempt` mới: assert `job_id` khác, digest Backend tính lại khác (`worker.py:78-110`, `attempt_id`), Backend cập nhật `pipeline_run` (cột `ai2_result_json`/digest, nêu trong đề bài), và query với digest cũ bị từ chối (mã lỗi cụ thể cần xác minh ở `main.py:753+`).
- Nonce: replay cùng nonce khác payload -> 409 `SERVICE_NONCE_REPLAY` (`main.py:~1668-1680`); nonce hết hạn thì bị dọn (nếu thêm TTL).
- Kiểm thử quyền: kết nối bằng role Backend `SELECT * FROM ai2.jobs` phải bị `permission denied` (chỉ có nghĩa nếu Backend không phải superuser).

### Câu 5 - Uplift chất lượng (ngắn, bám code)

Nguồn: hold-out/overfitting RAG: TDS Water Cooler #11 (B) https://towardsdatascience.com/water-cooler-small-talk-ep-11-overfitting-in-rag-evaluation/ ; TianPan contamination (C) https://tianpan.co/blog/2026/05/17/test-set-leaks-into-fine-tuning ; QASkills golden dataset (C) https://qaskills.sh/blog/golden-dataset-llm-evaluation-guide ; RAG eval fixes (C) https://ragaboutit.com/rag-evaluation-fixes/ . Table-to-text: survey arXiv 2409.14924 (A/B) https://arxiv.org/pdf/2409.14924 ; arXiv 2503.10677 (A/B) https://arxiv.org/pdf/2503.10677 ; Weaviate chunking (B) https://weaviate.io/blog/chunking-strategies-for-rag ; Medium chunking (C).

Đồng thuận: tập đánh giá bị dùng để chỉnh lỗi sẽ thành tập huấn luyện; giữ phần hold-out mà không ai nhìn khi lặp, chỉ chạy trước release; sau khi dùng để chỉnh thì phải sinh tập mới; báo cáo cuối dựa vào hold-out. Với bảng: linearize/tóm tắt bảng thành văn bản, embed/index phần tóm tắt và LIÊN KẾT ngược về bảng gốc để trích dẫn.

Đề xuất theo nhóm (thay luật fixture, không dùng node id cố định):
1. Tham chiếu cấu trúc vắng mặt ("Điều 3", "Phụ lục 7", `l0_rules.py:336-394`): một luật tổng quát: trích tham chiếu có số (`Điều|Phụ lục|Mục \d+`) từ câu hỏi bằng regex; tra trong outline bằng nhãn đã chuẩn hoá; nếu không có -> `INSUFFICIENT_EVIDENCE`; citation = các node có văn bản CHỨA tham chiếu đó (quét chéo nội dung), không phải `cl_9`.
2. `NOT_COMPARABLE` (USD, xây lắp vs thiết bị): so sánh dựa trên thuộc tính của fact (đơn vị/tiền tệ, `scope`/qualifier). Khác đơn vị mà hồ sơ không có tỷ giá, hoặc khác scope -> `NOT_COMPARABLE`; citation lấy từ fact được truy xuất, không phải `field_usd`/`field_penalty_*`.
3. UNNUMBERED_BLOCK: đã khoá theo `type` node nên tổng quát về bản chất; chỉ cần bỏ điều kiện chuỗi "thanh toán" và khớp term truy vấn với `raw_label` của các node loại này.
4. Bảng tóm tắt (T-GIA): chỉ mục hoá bảng thành node văn bản "tiêu đề/caption + header: value theo hàng" (table-to-text) có `parent=table_id`; `_lexical_hits` (`l1_retrieval.py:301-320`) hiện chỉ đếm term trên node, top 12, không IDF -> đổi sang `bm25_lite_score` (đã có `:494`) với token bỏ dấu và IDF; hàng tổng/summary nên được gắn nhãn cue ("tổng", "cộng", "giá trị hợp đồng") ở cấp ingest.
5. Câu VAT: tách node đoạn dài thành node-câu con (chỉ cho truy xuất), citation vẫn trỏ node cha + `char_start/char_end` (đã có `_char_offset`, `ai1_snapshot_adapter.py:1654`).
6. Chống overfit: giữ cơ chế plan A (`--variant-seed`, `--golden-dir`, split, `test_no_eval_leakage`). Quy tắc kỷ luật cho C: (a) mỗi thay đổi phải gắn với một LỚP lỗi, kèm test đơn vị trên tài liệu tổng hợp KHÁC fixture; (b) chỉnh trên dev split, chỉ đọc hold-out khi chuẩn bị release; (c) sinh bộ biến thể mới (seed mới) cho mỗi release và gate theo hold-out/biến thể; (d) allowlist rò rỉ về rỗng là điều kiện nghiệm thu (`plan A :227`).
7. Cỡ mẫu: với ~24 task (con số 21/24 ở plan A `:286`), 1 câu sai = 4,2 điểm % -> "95%" nghĩa là <=1 sai; khoảng tin cậy rất rộng. Cần tập đủ lớn (`[ASSUMED]` >=60-100 câu hold-out) trước khi coi ngưỡng 95% là bằng chứng chống hồi quy. Suy ra từ số học, không phải từ nguồn.

---

## Kết luận XẾP HẠNG

1. Ngăn xếp lưu trữ: SQLAlchemy 2 SYNC + `psycopg` v3 (`postgresql+psycopg`), pool nhỏ (5-10) sao cho ≤ số thread của anyio threadpool; `MetaData(schema="ai2")` tường minh; hai role (`ai2_owner`/migrator có DDL, `ai2_app` chỉ DML + `USAGE` schema) nếu chi phí chấp nhận được, còn không thì MVP `ai2_app` chủ schema và ghi rủi ro; Alembic riêng trong ai-service với `version_table_schema="ai2"`, `include_schemas=True`, `include_name` chỉ `ai2`; bootstrap role + `CREATE SCHEMA` bởi bước admin (không dựa `initdb.d` vì volume đã tồn tại), chạy `alembic upgrade head` bằng service one-shot `ai2-migrate` trước `ai2-service`. Lý do: code AI2 toàn sync (`def` endpoint, `sqlite3`), async buộc viết lại cả chuỗi gọi và dính lỗi Windows với psycopg async. Xếp sau: psycopg async, rồi asyncpg.
2. Hàng đợi: phương án A (in-process + Postgres là nguồn sự thật + sweep lúc startup và định kỳ, claim bằng một `UPDATE ... RETURNING` nguyên tử, lưu danh tính đã xác thực để worker không verify lại envelope hết hạn, thêm TTL nonce). Chưa dùng SKIP LOCKED; nâng lên B khi > 1 replica. Thư viện ngoài: không.
3. Lưu hồ sơ: probe tính xác định TRƯỚC (2 process khác `PYTHONHASHSEED`), sau đó R2 (record nén trong `bytea`, ghi cùng transaction với SUCCEEDED, nạp lazy, có `record_schema_version` + fallback R3). Sửa luôn mọi lặp `set` không sort ở adapter.
4. E2E: pytest + testcontainers-python (PG + AI2 GenericContainer, Backend in-process), workflow CI riêng; compose profile `e2e` là phương án dự phòng cho demo tay. Không dùng module `DockerCompose` của testcontainers.
5. Chất lượng: thay 6 nhánh fixture bằng 3 cơ chế tổng quát (tham chiếu cấu trúc vắng mặt, so sánh theo đơn vị/scope của fact, table-to-text + BM25 + node-câu), kỷ luật hold-out/biến thể; đo lại trước khi tuyên bố 95%.

Đề xuất bước kế: đưa 3 probe rẻ (hash-seed adapter; cổng testcontainers sau restart; Backend gọi AI2 in-process không cần Kafka) vào đầu phase 2/3 dưới dạng test RED; xem xét `hs:bakeoff` không cần thiết cho các lựa chọn trên (đều quyết được bằng probe nhị phân).

## Giới hạn của nghiên cứu
- Không chạy probe động nào: mọi "hành vi" của Alembic, psycopg, testcontainers là đọc tài liệu, không phải OBSERVED bằng chạy thật.
- Chưa đọc `main.py:200-268` (phần hậu xử lý của `_run_wire_job`), `verify_service_envelope` (TTL thực), phần Backend gọi AI2 trong `worker.py` ngoài 70-115, `v2__create_app_user.py`, nội dung `evals/`.
- Nguồn cho Câu 3 là phân tích thiết kế, không phải case study sản xuất; kích thước record chưa đo.
- Nguồn Câu 2/4/5 chủ yếu blog (B/C) cộng docs PG chính thức; chưa tìm case study production có số đo.
- Không đánh giá chi phí LLM, observability (D-4), GHCR release flow (D-1).

## Open questions
1. ADR-14 có hợp thức hoá luôn việc AI2 sở hữu lease/queue (mâu thuẫn ADR-02 dòng `DOC-04-architecture.md:93` và code SQLite hiện tại) và cho phép AI2 có DDL riêng qua role migrator không? Cần Architecture Lead xác nhận.
2. Backend có thể gọi client AI2 + persist (`pipeline_run.ai2_result_json`, digest) in-process mà không cần Kafka/Keycloak không? Nếu không, E2E phải dựng một `backend-e2e` service lean.
3. Role Backend hiện dùng trong compose là `ci` (superuser) hay role của `v2__create_app_user.py`? Quyết định có thể cưỡng chế tiêu chí "backend không có quyền trên `ai2`".
4. Bootstrap role/schema: qua Backend alembic (v10), script admin, hay init container? Chọn một, vì `initdb.d` không chạy lại trên `backend_pgdata` hiện có.
5. Nguyên nhân thật của lệch sau restart: hash-seed/`set`, `sort_keys`, hay thiếu hậu xử lý facts/LLM khi hydrate? Quyết định R2 có bắt buộc hay chỉ là thêm an toàn.
6. Retention: giữ bao nhiêu attempt cũ của `request_json`/record (mỗi cái cỡ MB)? Có cần import `jobs.sqlite` cũ sang Postgres không, hay bỏ dữ liệu dev?
7. TTL thực của service envelope để đặt TTL nonce (chưa đọc `service_envelope.py`).
8. Kích thước hold-out của plan A đủ để ngưỡng ≥95% có ý nghĩa thống kê không?

---

## PHỤ LỤC (main, 30/09/2026): probe nguyên nhân câu trả lời lệch sau khi khởi động lại — OBSERVED

Script probe: dựng cùng một request 2 file (fixture `tests/test_clause_compare.py`), chạy trong các process riêng với `PYTHONHASHSEED` khác nhau, băm `record_to_dict(record)` (`app/tools/persist.py`).

| Thí nghiệm | Kết quả |
|---|---|
| `adapt_be_ai2_processing_request`, seed 1 vs 2 | **Giống hệt** (`b2d3f06a67f5`) → giả thuyết hash-seed trong adapter **bị loại** |
| Request thô vs request đã `json.dumps(sort_keys=True)` | **Giống hệt** → giả thuyết `sort_keys` **bị loại** |
| Record sau `adapt` vs record sau `run_idp` | **Khác** (phần `facts` và các phần do bước xử lý ghi) → hydrate hiện tại (`main.py:83-117`, chỉ adapt lại request) **thiếu toàn bộ phần hậu xử lý** → **nguyên nhân chính** |
| `run_idp`, seed 1 / 2 / 3 | **Khác nhau** (`155916002caa`, `339679967239`, `9703961f1b6c`); **chỉ phần `chunks` thay đổi** → `run_idp` **không tất định giữa các process** ở bước tạo chunk |

Hệ quả cho C:
1. Muốn câu trả lời sau restart giống hệt lúc xử lý, **phải lưu record đã xử lý** (sau `run_idp`) — chạy lại `run_idp` khi hydrate là **không đủ**, vì `chunks` phụ thuộc hash seed.
2. Cần sửa cho chunk tất định (sắp xếp ổn định / ID chunk không phụ thuộc thứ tự `set`) — vị trí cụ thể chưa khoanh; ứng viên: `app/pipeline/clause.py`, `app/pipeline/index.py`.
3. Test RED đề xuất: chạy `run_idp` trong 2 subprocess với `PYTHONHASHSEED` khác nhau, băm record → phải bằng nhau.
