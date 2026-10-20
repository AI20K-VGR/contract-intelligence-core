# Evidence — Sprint 2 ST-035 → ST-039

Ngày thu thập: 2026-09-28 · Nhánh: `feature/backend-setup` (commit `69f2852`) · Tenant: `tenant_vgr_01`

Bằng chứng gồm ba lớp:

1. **Chạy thật trên docker compose** — Keycloak thật (đăng nhập PKCE), Postgres, MinIO, Kafka, AI1 worker, AI2 service. Dossier bằng chứng: `dos_01M3J729YZDD4F2CZ9XFNMHDCZ`. **28/28 bước đạt.**
2. **Test tự động theo từng task** — 116 test (SQLite) + 9 test chạy trên Postgres 16 thật; tất cả pass.
3. **CI GitHub** — [Backend CI run 36345475672](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/36345475672): import-linter, Ruff, MyPy, Unit, Integration đều xanh.

| Thư mục / file | Nội dung |
|---|---|
| `live/http_transcript.json` | Toàn bộ request/response của lần chạy thật (JWT đã che) |
| `live/db_state.sql` → `live/db_state.txt` | Trạng thái DB của dossier bằng chứng + thử sửa bảng append-only |
| `live/minio_objects.txt` | Object PDF trên MinIO |
| `live/kafka_state.txt` | Topic Kafka + consumer group (lag = 0) |
| `live/pipeline_logs.txt` | Log backend-worker / ai1-worker / ai2-service lọc theo dossier |
| `tests/ST-035.txt` … `tests/ST-039.txt` | Kết quả `pytest -v` theo từng task |
| `tests/postgres-invariants.txt` | Test khoá dòng, unique index, trigger append-only trên Postgres |

## Cách chạy lại

```powershell
docker compose up -d --build
cd backend
uv run python scripts/collect_st035_039_evidence.py --contract <hop-dong.pdf> --annex <phu-luc.pdf> --out ../docs/evidence/ST-035-039/live
```

PDF dùng cho bằng chứng là hợp đồng tổng hợp (không phải dữ liệu thật), cố ý ghi ba giá trị hợp đồng khác nhau (1,2 tỷ / 1,5 tỷ ở thân hợp đồng, 1,35 tỷ ở phụ lục). Theo quy định repo, PDF không được commit.

---

## ST-035 — `POST /dossiers` (upload & ingestion)

| Yêu cầu | Code | Test tự động | Bằng chứng chạy thật | Kết quả |
|---|---|---|---|---|
| Bắt buộc JWT | `get_current_user` trên route `create_dossier` (`contract_router.py:412`) | `test_create_dossier_requires_auth` | Không có JWT → **401** | Đạt |
| RBAC OPERATOR/ADMINISTRATOR | `require_role("OPERATOR","ADMINISTRATOR")` | `test_create_dossier_requires_operator_or_admin`, `test_upload_reviewer_role_forbidden` | REVIEWER → **403** `Insufficient role` | Đạt |
| Bắt buộc `X-Tenant-Id`, khớp claim | `shared/auth/tenant.py:17-40` | `test_upload_without_tenant_header_is_rejected`, `test_upload_with_foreign_tenant_header_is_rejected` | Thiếu header → **400**; `tenant_other` → **403 `TENANT_MISMATCH`** | Đạt |
| Dossier + Document + Job trong một transaction, file lên MinIO | `contract_service.py:87` (`create_dossier`), `:124` (`upload_document`), `:77` (`commit`); `_ingest_upload_file` `contract_router.py:330` | `test_create_dossier_multipart_upload_returns_202`, `test_create_dossier_with_annex` | `db_state.txt`: 1 dossier, 2 document (`blob_uri=s3://dossiers/...`), 1 job cùng `created_at`; `minio_objects.txt`: 2 object `application/pdf` | Đạt |
| Trả `202 {dossier_id, job_id}` | `status_code=HTTP_202_ACCEPTED` (`contract_router.py:398`) | `test_returns_202_with_dossier_created` | `{"data":{"dossier_id":"dos_01M3J729…","job_id":"job_01M3J729…"}}` | Đạt |

Test: `tests/ST-035.txt` — **34 passed**.

## ST-036 — Điều phối AI1 (OCR qua Kafka)

| Yêu cầu | Code | Test tự động | Bằng chứng chạy thật | Kết quả |
|---|---|---|---|---|
| Gửi lệnh qua Kafka `ci.ai1.ocr.commands`, nhận `ci.ai1.ocr.results` (không HTTP poll) | `handle_dossier_uploaded` `worker.py:688`, `handle_ai1_result` `:951`, `run_consumer` `:1270` | `test_upload_opens_run_with_all_steps`, `test_redelivered_upload_resumes_active_run` | `pipeline_logs.txt`: 2 lệnh `ocr_command_published` (mỗi tài liệu 1 lệnh), 2 kết quả `ai1_result.persisted`; `kafka_state.txt`: 3 consumer group lag 0, **không có topic `ci.ai2.idp.*`** | Đạt |
| Validate snapshot; sai/thiếu/khác tài liệu → FAILED | `handle_ai1_result`, `_fail_ai1_run` `:504`, `_resolve_result_job` `:229` (kiểm `schema_version`, run hiện hành, tenant) | `test_invalid_snapshot_marks_job_failed_with_audit`, `test_completed_event_without_result_marks_job_failed`, `test_snapshot_for_foreign_document_marks_job_failed`, `test_envelope_with_wrong_schema_version_is_dropped`, `test_result_claiming_another_tenant_is_rejected` | (nhánh lỗi chỉ chứng minh bằng test) | Đạt |
| EXTRACTED chỉ khi **mọi** tài liệu xong; trạng thái chỉ đi tiến | `_record_ai1_document` `:157`, `_FORWARD_RANK` `:197`, `_worker_transition_allowed` `:206`, `_mark_status` `:422` | `test_extracted_only_after_every_document_has_a_snapshot`, `test_late_success_does_not_override_failed`, `test_upload_event_does_not_reopen_a_job_in_review` | Audit: tài liệu 1 `processing→processing`, tài liệu 2 `processing→extracted` (`all_extracted=True`) | Đạt |
| OCR lại tạo run mới, bỏ kết quả muộn của run cũ | `_mark_processing` `:292` | `test_ocr_restart_supersedes_run_and_ignores_its_late_results`, `test_ocr_restart_recovers_failed_job_with_new_run`, `test_ocr_restart_refused_for_approved_job` | — | Đạt |
| Audit log đầy đủ | `add_audit_event` trong mọi chuyển trạng thái | các test FAILED ở trên kiểm tra audit | `db_state.txt`: `job.status_changed`, `ai1.snapshot_persisted` ×2, `ai2.result_persisted` | Đạt |

Test: `tests/ST-036.txt` — **21 passed**.

## ST-037 — Điều phối AI2 (phân tích & candidate finding)

Quyết định kiến trúc: AI2 chỉ có **một** đường là HTTP submit + poll từ worker; webhook `/webhooks/ai2/findings` và consumer `ci.ai2.idp.results` đã gỡ.

| Yêu cầu | Code | Test tự động | Bằng chứng chạy thật | Kết quả |
|---|---|---|---|---|
| Gửi snapshot đã validate sang AI2 khi manifest xác nhận + đủ snapshot | `_run_ai2_if_ready` `worker.py:731`; `submit_ai2_processing` / `poll_ai2_processing` `ai_adapters.py:168/196` (ký HMAC) | `test_ai2_transient_failure_releases_submission_guard_for_retry`, `test_snapshot_result_read_model_query_and_review_flow` | `pipeline_logs.txt`: `POST /jobs/idp 202` → 2 lần `GET /jobs/{id}` → `worker.ai2.completed source=http_poll` | Đạt |
| Persist fact / finding / review item, chống ghi trùng | `persist_ai2_processing_result` `persistence.py:880`; `_finalize_ai2_success` `worker.py:852` | `test_complete_result_round_trips_after_reload_and_replay_is_idempotent`, `test_duplicate_result_recovery_is_idempotent_and_legacy_stub_is_explicit`, `test_ai2_success_queues_every_finding_and_moves_to_pending_review` | `db_state.txt`: 3 fact (1,2 tỷ / 1,5 tỷ / 1,35 tỷ) | Đạt |
| Dossier → `PENDING_REVIEW`, có audit | `_finalize_ai2_success` | `test_ai2_success_queues_every_finding_and_moves_to_pending_review`, `test_ai2_success_refused_after_job_failed` | Job & dossier `pending_review`; audit `ai2.result_persisted extracted→pending_review` | Đạt |
| AI2 lỗi → FAILED + audit | `_fail_ai2_run` `worker.py:548` | `test_ai2_failure_marks_job_failed_with_audit` | — | Đạt |

Test: `tests/ST-037.txt` — **10 passed** (cộng các test AI2 trong `ST-036.txt`).

**Lưu ý khi chạy thật:** AI2 trả `findings=0` cho PDF tổng hợp dù có ba giá trị mâu thuẫn. Nguyên nhân nằm ở AI2 (`ai-service/app/pipeline/ai1_snapshot_adapter.py:1500-1508`): fact khôi phục từ dòng dùng nguyên câu làm `item_key`, nên các fact không bao giờ cùng nhóm để so sánh. Đây là phạm vi AI2 (ST-045), không thuộc backend ST-037. Vì vậy review item cho ST-038 được mở qua luồng thẩm định điều khoản của FE (xem dưới).

## ST-038 — `POST /review-items/{id}/actions` (append-only, optimistic locking)

| Yêu cầu | Code | Test tự động | Bằng chứng chạy thật | Kết quả |
|---|---|---|---|---|
| RBAC REVIEWER/ADMINISTRATOR + ACL dossier | `review_full_router.py:129`, `dependencies.py` | `test_rbac_rejects_operator`, `tests/unit/test_dossier_acl_consistency.py` | OPERATOR → **403** | Đạt |
| Kiểm `base_version` (bắt đầu từ 1) | `ReviewActionRequestDTO.base_version ge=1` | `test_base_version_zero_is_rejected`, `test_accepts_base_version_one` | `base_version: 0` → **422** | Đạt |
| Đúng version → ghi action, tăng version | `submit_action` `repository_impl.py:132` (khoá item `FOR UPDATE` :159, khoá dossier `FOR SHARE` :170) | `test_returns_200_with_new_version` | **200** `new_version: 3` | Đạt |
| Tranh chấp → **409** kèm `current_state` | nhánh `ReviewVersionConflict` + unique index `uq_review_action_item_base_version` (migration v13); `_is_base_version_race` :499 | `test_returns_409_on_version_conflict`, `test_racing_action_on_same_base_version_returns_409`; Postgres: `test_concurrent_actions_on_same_version_serialize`, `test_unique_index_rejects_duplicate_base_version` | version cũ → **409 `VERSION_CONFLICT`** + `current_state`; `db_state.txt`: không có dòng action nào cho lần bị 409 | Đạt |
| Append-only, không ghi đè kết quả máy | trigger `forbid_mutation` (v7 cho `review_action`, v12 cho `audit_event`/`query_trace`) | Postgres: `test_append_only_tables_refuse_update_and_delete` (6 case) | `GET /revisions` trả lịch sử 1→2; trên DB thật `UPDATE review_action` → `ERROR: Bảng review_action là bất biến` | Đạt |
| Ghi audit | `add_audit_event("review.action_submitted")` `repository_impl.py:218` | `test_action_writes_audit_event` | `db_state.txt`: 3 audit `review.action_submitted` (actor, from/to, base/new version) | Đạt |
| Dossier đã khoá/duyệt → chặn | kiểm `is_locked/is_approved` sau khoá `FOR SHARE`; approve/lock khoá `FOR UPDATE` (`approval_service.py:53,74`) | `test_action_refused_on_locked_or_approved_dossier[is_locked/is_approved]`; Postgres: `test_approval_holding_dossier_blocks_then_refuses_action` | Admin khoá → action → **409 `INVARIANT_VIOLATION`** | Đạt |

Test: `tests/ST-038.txt` — **18 passed**; `tests/postgres-invariants.txt` — **9 passed**.

Review item trong lần chạy thật được mở bằng `POST /clause-nodes/{id}/review` trên hai điều khoản chứa giá trị mâu thuẫn (Điều 2, Điều 6). Lần thẩm định đầu tiên tạo `review_item`, giống cách FE làm.

## ST-039 — `/search`, `/query`, `/ask` (ACL, quota, QueryTrace)

| Yêu cầu | Code | Test tự động | Bằng chứng chạy thật | Kết quả |
|---|---|---|---|---|
| Endpoint cho FE | `search_dossier` `contract_router.py:844`; `query_dossier`/`ask_dossier` `api/v1/dossiers.py:203/221` | `test_maps_ai2_citations_to_hits`, `test_query_and_ask_persist_query_trace_in_db[query/ask]` | search / query / ask → **200** | Đạt |
| ACL + tenant trước khi gọi AI2 | `_acl_check_dossier_access` `dossiers.py:47`; router dùng `get_tenant_id` (`dossiers.py:31`) | `test_query_requires_tenant_header`, `test_anonymous_and_cross_tenant_query_are_denied`, `test_query_rejects_tombstoned_dossier`, `test_dossier_acl_consistency.py` | Thiếu header → **400**; tenant khác → **403** | Đạt |
| Quota / rate limit trước AI2 | `enforce_query_limits` `query_policy.py:95` | `test_rate_limit_returns_429`, `test_tenant_daily_quota_returns_429_before_ai2` | — | Đạt |
| `policy_flags` do server quyết định | `server_query_policy_flags` `query_policy.py:133`; DTO `extra="forbid"` | `test_query_policy_flags_come_from_server_not_client` | Client gửi `policy_flags` → **422 `extra_forbidden`** | Đạt |
| Ghi QueryTrace (actor / version / citations) | `QueryTraceORM` `query_policy.py:33`, `save_query_trace` `:215` | `test_query_and_ask_persist_query_trace_in_db`, `test_ai2_failure_still_writes_query_trace` | `db_state.txt`: 3 dòng `query_trace` (endpoint, actor, state, `acl_decision=passed`, digest, `ai2.query.v1`, latency); sửa/xoá → trigger chặn | Đạt |
| ACL lần 2 trên citation, chặn mặc định | `enforce_result_acl` `query_policy.py:162`, `_withhold` `:207` | `test_second_acl_pass_drops_foreign_citations`, `test_second_acl_pass_drops_citations_without_document_ref`, `test_second_acl_pass_blocks_when_access_revoked_mid_query`, `test_query_second_acl_pass_drops_citation_outside_dossier` | AI2 trả `BLOCKED` (không có hit), backend giữ nguyên state, `dropped_citations=0` | Đạt (lọc citation thật chỉ chứng minh bằng test) |

Test: `tests/ST-039.txt` — **33 passed**.

---

## Lỗi phát hiện và đã sửa trong lúc thu bằng chứng

- **Revision ID v13 dài 38 ký tự** vượt `alembic_version.version_num varchar(32)` → `upgrade head` lỗi trên Postgres. Đã đổi thành `v13__review_action_unique` (đã có trong commit `d58d83b`).
- **DB cũ thiếu cột `review_item.target_snapshot`** → `GET /review-items` trả 500 trên DB thật. Cột có trong ORM từ commit `2f6052c` nhưng không có migration. Đã thêm migration `v14__review_item_snapshot`, DB compose đã lên v14 và không còn lệch schema. **Chưa commit.**

## Còn thiếu (chưa làm, cần backlog)

| Task | Thiếu sót |
|---|---|
| ST-035 | Không dọn file MinIO khi upload lỗi giữa chừng; không có outbox cho sự kiện Kafka (`BackgroundTasks`); không kiểm loại file/dung lượng; không ghi audit lúc tạo job `UPLOADED`; route cũ `/dossiers/upload` vẫn đăng ký |
| ST-036 | Chống xử lý trùng chỉ nằm trong RAM (`_seen_result_ids`, `worker.py:64`); không có DLQ; consumer AI1 bị chặn trong lúc poll AI2 |
| ST-037 | `IndexContribution` chưa lưu riêng (chỉ nằm trong kết quả AI2 + audit `index_contribution_state`); `target_id` rơi về `"unknown"` khi finding thiếu id (`persistence.py:140,1013`) |
| ST-038 | `Idempotency-Key` nhận nhưng chưa replay; chưa tự chuyển `REVIEWED` khi hết item mở; mã 409 là `VERSION_CONFLICT` (spec ghi `REVISION_CONFLICT`); chưa có bảng `ReviewRevision` riêng |
| ST-039 | Rate limiter trong RAM từng process; quota kiểm-rồi-ghi không atomic; `snapshot_version` cố định `"latest"` (thấy rõ trong `query_trace`); request bị 403/429 không ghi trace |
