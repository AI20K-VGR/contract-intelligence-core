# Evidence — Sprint 3 Backend (4 task)

Ngày thu thập: 2026-10-02 · Nhánh: `feature/code-full` (commit `62b7852`) · Người thu thập: Chương (BE)

Bằng chứng gồm hai lớp:

1. **Test tự động theo từng task**: 126 test, tất cả pass. Test Postgres chạy trên `pgvector/pgvector:pg16` thật, không test nào bị skip. Kết quả `pytest -v` nằm trong `tests/`.
2. **CI GitHub**: Backend CI xanh trên các commit gần nhất của `feature/code-full`, ví dụ [run 36962017341](https://github.com/AI20K-VGR/contract-intelligence-core/actions/runs/36962017341) (`9f0acc1`). Gồm import-linter, Ruff, MyPy, Unit, Integration.

Lần này **chưa có bằng chứng chạy thật** trên docker compose như ST-035-039. Task 1 vì vậy chưa đạt đủ tiêu chí, xem mục "Còn thiếu" của Task 1.

| File | Nội dung |
|---|---|
| `tests/task1-ho-so-lon.txt` | Hồ sơ lớn: giới hạn, watchdog, OCR qua MinIO, giữ phần đã xong (32 test) |
| `tests/task2-chia-se.txt` | Chia sẻ xem hoặc sửa, hết hạn (49 test, có 1 test trên Postgres) |
| `tests/task3-lich-su-hoi-dap.txt` | Lịch sử hỏi đáp, không xem chéo dữ liệu (9 test) |
| `tests/task4-tach-file.txt` | Tách file trộn thành từng tài liệu (36 test) |

## Cách chạy lại

```powershell
docker run -d --rm --name ci-pg-ev -e POSTGRES_USER=ci -e POSTGRES_PASSWORD=ci -e POSTGRES_DB=ci_test -p 55434:5432 pgvector/pgvector:pg16
cd backend
$env:CI_TEST_POSTGRES_URL="postgresql+asyncpg://ci:ci@127.0.0.1:55434/ci_test"
uv run pytest -v tests/unit/test_share_permissions.py tests/integration/test_query_history.py tests/integration/test_split_mixed_file.py
```

Danh sách đầy đủ các test của từng task nằm ở đầu mỗi file trong `tests/`.

---

## Task 1 — Hồ sơ lớn chạy xong hoặc báo lỗi, không treo

> Tiêu chí: file khoảng 50MB và PDF khoảng 200 trang xử lý xong. Một phần lỗi thì phần đã xong vẫn giữ.

PR: #28 (merge 29/09), #36 (merge 30/09), #46 (merge 02/10).

| Yêu cầu | Code | Test tự động | Kết quả |
|---|---|---|---|
| Nhận file tới 50 MiB, quá thì `413` rõ ràng; file không đọc được thì `422` trước khi tạo gì | `upload_max_file_bytes = 50 MiB` (`config/settings.py:280`); `_ingest_upload_file` (`contract_router.py:425`) | `test_rejects_file_over_size_limit`, `test_rejects_unreadable_pdf_before_creating_anything` | Đạt |
| Proxy không chặn hồ sơ 6 file × 50 MiB | Caddy `max_size 320MiB` (`deploy/Caddyfile:26`) | (cấu hình, kiểm bằng `caddy adapt` trong PR #46) | Đạt |
| Kết quả OCR không phụ thuộc trần Kafka 10MB: AI1 ghi kết quả lên MinIO, Kafka chỉ mang đường dẫn | `result_uri` trong lệnh OCR (`worker.py:880`); `_load_ai1_result_ref` (`worker.py:1330`) kiểm đúng đường dẫn của tài liệu và run | `test_result_by_reference_is_downloaded_and_persisted`, `test_bad_result_reference_fails_the_run` | Đạt |
| Link tải PDF tạm (presigned) không hết hạn giữa chừng với file lớn | `_presign_ttl_seconds` (`worker.py:126`): kéo dài theo hạn AI1 của run, không quá giới hạn S3 | `test_presign_ttl_never_exceeds_the_s3_limit` | Đạt |
| **Không treo:** run quá hạn AI1 thì `failed` có mã; hạn tăng theo số trang | `ai1_deadline_seconds` (`worker.py:98`), `run_ai1_watchdog` (`worker.py:1712`) | `test_watchdog_fails_run_past_its_ai1_deadline`, `test_watchdog_deadline_grows_with_page_count`, `test_watchdog_leaves_runs_within_deadline_and_finished_jobs`, `test_ocr_result_after_timeout_does_not_revive_the_job` | Đạt |
| **Không treo:** AI2 quá hạn thì `failed` (`AI2_TIMEOUT`); lỗi tạm của AI2 được thử lại | `ai2_deadline_seconds` (`worker.py:107`); retry trong `ai_adapters.py` | `test_ai2_deadline_miss_fails_run_as_ai2_timeout`, `test_poll_rides_out_transient_errors`, `test_poll_gives_up_after_too_many_errors_in_a_row`, `test_submit_retries_transient_errors_then_succeeds` (+3) | Đạt |
| Message Kafka lỗi lớn không làm kẹt consumer | Dead letter lưu dạng con trỏ | `test_large_failed_record_is_parked_as_a_pointer`, `test_persistent_failure_is_dead_lettered_then_committed` | Đạt |
| **Phần đã xong vẫn giữ:** chạy lại chỉ OCR tài liệu lỗi, tài liệu đã xong mang sang run mới | `_carry_extractions` (`worker.py:474`); `POST /dossiers/{id}/ocr/retry-failed` (`contract_router.py:733`) | `test_retry_failed_re_ocrs_only_the_missing_document`, `test_retry_failed_with_everything_kept_goes_straight_to_ai2`, `test_carried_snapshot_keeps_its_stored_time`, `test_plain_restart_still_re_ocrs_everything`, `TestRetryFailedOcrEndpoint` | Đạt (ở mức tài liệu) |
| Chỉ chuyển sang AI2 khi mọi tài liệu đã có kết quả OCR | `_record_ai1_document` (`worker.py:274`) | `test_extracted_only_after_every_document_has_a_snapshot`, `test_six_document_dossier_reaches_ai2_whole` | Đạt |

Test: `tests/task1-ho-so-lon.txt`: **32 passed**.

### Còn thiếu (chưa đạt đủ tiêu chí)

- **Chưa chạy thật với file khoảng 50MB và PDF khoảng 200 trang.** Đây là bước E6 của DEC-BE-AI1-01: chạy end-to-end, đo thời gian và số lần 429, rồi ghi số đo vào DOC-11. Hiện chưa có số đo nào. Bước này cần file mẫu và hạn mức Mistral, và cần AI1 (Đức Dũng) cùng chạy.
- **"Phần đã xong vẫn giữ" mới ở mức tài liệu, chưa ở mức cụm trang.** Với một PDF 200 trang (một tài liệu), một trang lỗi vẫn làm OCR lại cả tài liệu. Phần chia cụm trang (E1–E5, E7 của DEC-BE-AI1-01, đã `accepted`) chưa được triển khai ở Backend.

## Task 2 — Chia sẻ có mức xem hoặc sửa, hết hạn thì từ chối

> Tiêu chí: quá hạn thì không vào được hồ sơ. Sửa hồ sơ thì phải có quyền sửa.

PR: #28 (`ce0633e`, `c212496`, merge 29/09). Ba commit làm rõ câu từ chối và quyền tải PDF (`3d705ae`, `d15d072`, `c097ae9`) mới nằm trên `feature/code-full`, chưa vào `develop`.

| Yêu cầu | Code | Test tự động | Kết quả |
|---|---|---|---|
| Mỗi quyền chia sẻ có `permission` (`read` hoặc `edit`) và `expires_at`; chỉ chủ hồ sơ hoặc quản trị viên được đổi | `AccessGrantBody` (`contract_router.py:188`); `PUT /dossiers/{id}/access` (`contract_router.py:1496`) | `test_owner_stores_permission_and_utc_expiry`, `test_missing_permission_keeps_edit`, `test_rejects_unknown_permission`, `test_rejects_expiry_in_the_past`, `test_only_owner_or_admin_changes_access`, `test_manage_is_owner_or_administrator_only`, `test_plain_patch_cannot_add_acl_fields` | Đạt |
| **Quá hạn thì không vào được:** mọi hành động, kể cả xem, bị từ chối `403`; quyền bị tắt cũng vậy | `dossier_access_decision` (`shared/acl.py:57`) | `test_grant_decision` (bảng 15 trường hợp, gồm hết hạn đúng mốc giây, ngày hỏng, `disabled`), `test_naive_expiry_is_read_as_utc`, `test_denial_for_expired_or_missing_grant` | Đạt |
| Danh sách hồ sơ ẩn hồ sơ có quyền đã hết hạn hoặc bị tắt (cả SQLite lẫn Postgres) | bộ lọc danh sách | `test_list_hides_expired_and_disabled_grants`, Postgres: `test_list_applies_expiry_and_status_on_postgres` | Đạt |
| **Sửa phải có quyền sửa:** quyền `read` chỉ xem, không thẩm định, duyệt hay sửa hồ sơ | `_EDIT_ACTIONS` (`shared/acl.py:52`); `require_dossier_action` (`api/dossier_guard.py:85`) | `test_read_grant_cannot_edit`, `test_guard_resolves_ids_and_refuses_read_only_edits`, `test_read_grant_denial_says_view_only` | Đạt |
| Câu `403` nói rõ lý do (chỉ xem, thiếu vai trò, hết hạn) | `dossier_denied_message` (`shared/acl.py:151`); `role_denied_message` (`shared/auth/dependencies.py`) | `test_denial_tells_read_grantee_they_can_only_view`, `test_denial_names_role_before_grant`, test vai trò trong `test_auth_dependencies.py` | Đạt |
| Tải PDF cũng cần quyền xem hồ sơ; người được chia sẻ không thấy người được chia sẻ khác | `acl_document`; `visible_dossier_metadata` (`shared/acl.py:179`) | `test_content_requires_dossier_read_access`, `test_grantee_sees_only_own_grant`, `test_owner_sees_every_grant`, `test_no_access_is_forbidden` | Đạt |
| Không có API nào lộ dữ liệu ngoài tenant hoặc ngoài quyền (M-07 = 0) | guard trên mọi route theo hồ sơ (`api/dossier_guard.py:138-166`) | `test_m07_no_request_returns_data_outside_tenant_or_acl`, `test_every_dossier_scoped_parameter_is_mapped` | Đạt |

Test: `tests/task2-chia-se.txt`: **49 passed** (có 1 test trên Postgres).

## Task 3 — Lưu lịch sử hỏi đáp và không cho xem chéo dữ liệu

> Tiêu chí: tắt server rồi mở lại vẫn xem được lịch sử. Người này không thấy dữ liệu của người khác.

PR: #36 (`bdcb62d`, merge 30/09).

| Yêu cầu | Code | Test tự động | Kết quả |
|---|---|---|---|
| Câu hỏi và câu trả lời lưu trong DB, không trong bộ nhớ | bảng `query_answer` (migration `v18__query_answer.py`); `GET /dossiers/{id}/queries` (`api/v1/dossiers.py:263`) | `test_history_is_per_user_and_survives_a_restart`: tạo engine và client mới sau khi hỏi (giả lập khởi động lại), lịch sử vẫn đủ câu hỏi và câu trả lời | Đạt |
| Câu hỏi lỗi vẫn được lưu, không có câu trả lời | | `test_failed_query_is_kept_without_an_answer` | Đạt |
| **Không xem chéo:** mặc định mỗi người chỉ thấy lịch sử của mình; `scope=all` chỉ dành cho chủ hồ sơ | tham số `scope: mine \| all` (`api/v1/dossiers.py:267`) | `test_history_is_per_user_and_survives_a_restart` (reviewer chỉ thấy câu của mình, gọi `scope=all` bị `403`) | Đạt |
| Người ngoài hồ sơ, người tenant khác không đọc được | guard hồ sơ + tenant | `test_outsiders_cannot_read_history` (3 trường hợp), `test_m07_no_request_returns_data_outside_tenant_or_acl` | Đạt |
| Quyền bị thu hồi giữa lúc hỏi thì không trả dữ liệu | kiểm ACL lần hai | `test_second_acl_pass_blocks_when_access_revoked_mid_query` | Đạt |
| Xoá hồ sơ thì xoá câu trả lời, giữ dấu vết audit | | `test_purge_removes_answers_and_keeps_the_audit_trace` | Đạt |

Test: `tests/task3-lich-su-hoi-dap.txt`: **9 passed**.

Ghi chú: "tắt server mở lại" được kiểm bằng test (engine và client mới trên cùng file DB). Chưa có bản ghi chạy thật kiểu `docker compose restart backend`.

## Task 4 — Tạo từng tài liệu sau khi tách file trộn

> Tiêu chí: người dùng xác nhận xong, một bộ hồ sơ có nhiều tài liệu, và mỗi tài liệu được xử lý riêng.

PR: #36 (`d667bd9`, merge 30/09), #46 (`b1199fa`, merge 02/10).

| Yêu cầu | Code | Test tự động | Kết quả |
|---|---|---|---|
| File trộn tải lên với `split_pending` thì chờ, chưa gửi OCR | `contract_router.py:603-615` | `test_mixed_file_waits_then_splits_into_documents` (không có lệnh OCR trước khi tách) | Đạt |
| Người dùng xác nhận khoảng trang và vai trò, mỗi phần thành một tài liệu PDF thật, đúng số trang | `POST /dossiers/{id}/split` (`split_dossier_document`, `contract_router.py:792`); `_check_split_parts` (`contract_router.py:664`) | `test_mixed_file_waits_then_splits_into_documents`: 10 trang tách thành hợp đồng 6 trang và phụ lục 4 trang, file gốc bị thay, mỗi phần tải về đúng số trang | Đạt |
| Phần không hợp lệ bị từ chối; giữ cả file khi chỉ có một phần | `_check_split_parts` | `test_bad_parts_are_refused`, `test_single_part_keeps_the_file_and_starts_processing`, `test_normal_upload_cannot_be_split` | Đạt |
| Hồ sơ đúng dáng AI2 nhận: tối đa 6 tài liệu, đúng một hợp đồng | `MAX_DOSSIER_DOCUMENTS`; `_dossier_shape_error` (`worker.py:1186`) | `test_split_into_too_many_documents_names_documents_not_pages`, `test_upload_of_more_than_six_files_is_refused`, `test_dossier_shape_error` (6 trường hợp) | Đạt |
| Manifest được xác nhận sau khi tách; tách lại sau khi đã bắt đầu xử lý thì `409` | | `test_mixed_file_waits_then_splits_into_documents`, các test trong `test_manifest_router.py` | Đạt |
| **Mỗi tài liệu được xử lý riêng:** mỗi tài liệu một lệnh OCR và một kết quả riêng; tài liệu lỗi chạy lại một mình; AI2 chỉ chạy khi đủ mọi tài liệu | `handle_dossier_uploaded` (`worker.py:932`) | `test_plain_restart_still_re_ocrs_everything` (lệnh OCR cho `DOC_A` và `DOC_B`), `test_retry_failed_re_ocrs_only_the_missing_document` (chỉ `DOC_A` lỗi được gửi lại, `DOC_B` giữ kết quả), `test_extracted_only_after_every_document_has_a_snapshot`, `test_six_document_dossier_reaches_ai2_whole` | Đạt |

Test: `tests/task4-tach-file.txt`: **36 passed**.
