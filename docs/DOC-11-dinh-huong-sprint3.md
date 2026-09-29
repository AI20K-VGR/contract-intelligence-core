# DOC-11 · Định hướng Sprint 3

> **Contract Intelligence** — Việc Sprint 3 của từng người, lấy từ nhận xét mentor ngày 29/09/2026 và đề xuất của Chương, Đức Dũng, Văn Dũng.

---

## 0. Thông tin

| Trường | Nội dung |
|---|---|
| Mã tài liệu | DOC-11 — Định hướng Sprint 3 |
| Ngày viết | 29/09/2026 |
| Người viết | Trần Thị Kiều Trang (Lead) |
| Sprint 2 còn lại | 30/09 – 04/10/2026 |
| Sprint 3 | 05/10 – 18/10/2026 (DOC-06 hạn 18/10) |
| Team | Lead & FE: Trang · BE: Chương · AI1: Đức Dũng · AI2: Văn Dũng |

Nguồn:

- Nhận xét mentor ngày 29/09.
- Đề xuất độ bền file lớn của Chương.
- Kế hoạch AI2 tuần 3 của Văn Dũng (`ke-hoach-ai2-tuan3-260928-261004`).
- Đề xuất cải thiện của Đức Dũng (query trace, test tenant, golden set, Kafka, SSE, `event_id`).

Sprint 3 bám MVP đã chốt: một hồ sơ chạy hết đăng nhập → tải lên → đọc chữ → cấu trúc → xung đột → người kiểm → hỏi đáp có trích dẫn. Muốn đổi đường kỹ thuật thì nói mentor trước khi làm.

---

## 1. Việc mentor yêu cầu

| # | Mentor nói | Việc Sprint 3 | Phụ trách |
|---|---|---|---|
| 1 | Một file tải lên gồm cả hợp đồng và phụ lục thì tách thành nhiều tài liệu trong cùng một bộ hồ sơ | AI1 đề xuất chỗ cắt. Backend tạo từng tài liệu. Người dùng xác nhận vai trò từng phần rồi mới chạy tiếp | Đức Dũng, Chương, Trang |
| 2 | Phân tích vài điều khoản đang chậm ở bước nhận diện chữ | Điều khoản đã có chữ thì dùng chữ đó. PDF có lớp text đi đường đọc text. Không gọi OCR lại chỉ để xem 4 điều khoản | Đức Dũng, Chương |
| 3 | Hợp đồng rất dài (kể cả cỡ 1000 trang) không được gọi một cục. Một phần treo thì xử lý ra sao. Lỗi 429 và 529 xử lý ra sao | Cơ chế ở mục 2 | Chương, Đức Dũng, Văn Dũng |
| 4 | AI2 SQLite đang chạy ở đâu. Thống nhất một database | Mục 3. Dữ liệu chạy thật của AI2 chuyển về PostgreSQL chung với backend | Văn Dũng, Chương |
| 5 | Đang đóng gói và làm khác MVP mà không nói lại | Giữ MVP ở mục 0. Image không nhét dữ liệu chạy thử. Đổi cách thì báo mentor trước | Cả nhóm, Trang theo dõi |
| 6 | "Sửa nhận định" là sai. Không có trạng thái ở giữa. Bỏ lựa chọn đó. Chỗ cần ghi thêm thì gọi là bổ sung hoặc xử lý | Bỏ nút và trạng thái giữa trên màn thẩm định | Trang, Chương |
| 7 | Xung đột là hợp đồng với hợp đồng, không chỉ hợp đồng với phụ lục | Finding so được hai hợp đồng. Phụ lục vẫn so được, nhưng không phải cặp duy nhất | Văn Dũng, Chương, Trang |
| 8 | Mật khẩu người dùng lưu ở đâu | Mục 3. Mật khẩu nằm ở Keycloak | Chương (giữ nguyên), Trang ghi vào tài liệu kiến trúc |
| 9 | Chia sẻ có chỉ đọc hoặc được sửa, hết hạn thì thu hồi | Mỗi quyền có `quyền` (`read` hoặc `edit`) và `hết hạn`. Quá hạn thì API từ chối | Chương, Trang |
| 10 | Triển khai online đủ service | Bản online có frontend, backend, worker, AI1, AI2, Keycloak, Postgres, MinIO, Kafka. Cổng AI2 không mở ra Internet | Cả nhóm, Trang điều phối |
| 11 | Hợp đồng 50MB chưa có bài test | Một bài test tích hợp với file khoảng 50MB, và một bài với PDF cỡ 200 trang (đã vỡ Kafka ở ~14MB) | Đức Dũng, Chương |
| 12 | Trong team chưa rõ người khác đang làm gì | Mỗi người ghi việc đang làm và việc xong trong ngày, Lead gom trước daily | Trang |
| 13 | Cam kết tuần sau phải có trước ngày mai. Đánh giá từng người bằng test và GitHub, gửi trên Teams | Mục 6 và mục 7. Bản chấm gửi Teams ngày 30/09 | Trang |

---

## 2. File lớn, một phần treo, lỗi 429 và 529

Hôm nay hệ thống gọi ra ngoài theo cả tài liệu. AI1 gọi OCR cho cả file rồi nhét toàn bộ kết quả vào một message Kafka. File khoảng 200 trang ra message ~14,3MB, broker từ chối vì trần 10MB (`MessageSizeTooLargeError` tại `kafka_worker.py`). AI2 gọi LLM cho câu so sánh. Healthcheck AI2 còn gọi LLM định kỳ. Hợp đồng dài theo cách này sẽ gọi quá nhiều, dễ hết quota, và một trang treo thì cả job đứng ở `PROCESSING`.

Sprint 3 đổi sang xử lý từng cụm:

1. AI1 ghi kết quả OCR lên MinIO. Kafka chỉ mang đường dẫn, checksum, số trang, trạng thái. Message còn vài KB dù tài liệu dài bao nhiêu.
2. Lệnh OCR chia theo cụm trang và chạy song song, có trần số cụm chạy cùng lúc. Mỗi cụm báo tiến độ.
3. Mỗi cụm có hạn theo số trang. Quá hạn thì cụm đó `FAILED` với `AI1_TIMEOUT`. Cụm khác vẫn ghi kết quả. Job chỉ `FAILED` khi số trang lỗi vượt ngưỡng đã chốt. Dưới ngưỡng thì xong một phần, UI nói rõ trang nào thiếu.
4. Chạy lại AI2 dùng snapshot đã lưu. Không OCR lại những trang đã xong.
5. Link tải PDF tạm (presigned URL) tính theo thời gian cụm chậm nhất. Mặc định hiện tại là 3600 giây trong `settings.py`, ngắn hơn thời gian một file lớn cần.

**429** là hết lượt gọi hoặc bị giới hạn tốc độ (đã gặp với `gh/gpt-4o` ngày 29/09).

- Đọc `Retry-After` nếu có. Không có thì chờ tăng dần, có trần số lần.
- Trong lúc chờ, không mở thêm lệnh mới tới provider đó.
- Hết lượt chờ thì dừng cụm với `OCR_RATE_LIMITED` hoặc `LLM_RATE_LIMITED`. Job không đứng im.
- Demo và bản online dùng provider có hạn mức đã chốt, có người giữ key và trần chi tiêu. Không demo trên gói miễn phí.

**529** là provider quá tải (cùng họ với 503).

- Coi là lỗi tạm: thử lại có trần, cùng kiểu chờ tăng dần.
- Hết lượt thử thì cụm đó lỗi `OCR_UNAVAILABLE` hoặc `LLM_UNAVAILABLE`.
- Trang đã xong giữ nguyên. Người dùng thấy trang nào lỗi và bấm chạy lại đúng phần đó.

Số đo bắt buộc trong sprint: file khoảng **50MB** và PDF khoảng **200 trang**. Cỡ 1000 trang dùng cùng cơ chế (cụm trang, một phần treo không kéo cả job). Có file mẫu và còn hạn mức thì chạy thử và ghi số đo. Chưa đo thì không ghi là đã chịu được 1000 trang.

---

## 3. Một database, và mật khẩu nằm ở đâu

**Mật khẩu** người dùng nằm ở **Keycloak**. Backend không cấp token và không kiểm tra mật khẩu (`identity/interfaces/api/dependencies.py`). Bảng `app_user` không có `password_hash`. Ứng dụng chỉ giữ email, tên, vai trò. Sprint 3 giữ nguyên chỗ này và ghi rõ trong tài liệu kiến trúc để mentor đối chiếu được.

**Dữ liệu nghiệp vụ** về một PostgreSQL dùng chung: hồ sơ, OCR, fact, finding, review, query trace, sự kiện Kafka đã xử lý, trạng thái job AI2.

SQLite của AI2 hiện không phải database chung:

| File | Chỗ trong code | Chạy ở đâu |
|---|---|---|
| `data/ai2/runs.sqlite` | `ai-service/app/tools/persist.py` (`DATA = ROOT.parent / "data" / "ai2"`) | Trên đĩa máy hoặc trong container AI2, cạnh repo. Image đang copy thư mục `data/` nên sqlite chạy thử đi theo bản đóng gói |
| `ai-service/data/ai2/vectors.sqlite` | `vector_recall.py`, biến `AI2_VECTOR_DB` | Cùng process AI2, file local |

Sprint 3: bản online của AI2 ghi dữ liệu bền vào PostgreSQL. SQLite chỉ còn trong test. Image build từ git, không đóng gói `data/`.

Keycloak tiếp tục giữ mật khẩu trong kho của Keycloak. Có thể đặt schema Keycloak trên cùng máy Postgres, nhưng ứng dụng không đọc mật khẩu.

---

## 4. Định hướng từng người

### 4.1 Trang — Frontend

Chỉ những việc người khác đã nêu cho frontend.

| Nguồn | Việc | Xong khi |
|---|---|---|
| Mentor | Bỏ "Sửa nhận định" và mọi trạng thái nằm giữa đúng và sai. Chỗ người dùng ghi thêm gọi là **bổ sung** hoặc **xử lý** | Màn thẩm định điều khoản và màn xung đột còn hai hướng: đúng, sai. Không còn nút nhận định |
| Mentor | Chia sẻ hồ sơ: chỉ đọc hoặc được sửa, có ngày hết hạn, quá hạn thì hết quyền | Form chia sẻ chọn `read` hoặc `edit` và ngày hết hạn. Quá hạn thì mở hồ sơ bị từ chối |
| Mentor | Khi một file gồm cả hợp đồng và phụ lục, người dùng thấy các phần đã tách và xác nhận vai trò từng phần | Bấm xác nhận xong, bộ hồ sơ có nhiều tài liệu, mỗi tài liệu một vai trò |
| Mentor | Xung đột hiện cả cặp hợp đồng–hợp đồng | Màn đối soát đọc finding hai hợp đồng cùng cách với cặp có phụ lục |
| Đức Dũng | Tiến độ chạy bằng SSE `/runs/{id}/events`, hết SSE thì mới hỏi lại định kỳ | Đang chạy thì màn tiến độ đổi ngay khi có sự kiện. Rời trang thì đóng kết nối |
| Văn Dũng (tuần 30/09–04/10) | Luồng demo: danh sách hồ sơ → mở hồ sơ → bấm giá trị thì sáng vùng trích → xác nhận, sửa hoặc từ chối | Tập được trên UI không đứt giữa chừng |
| Văn Dũng | Ghép phần Architecture và API Spec. Sửa `HUONG-DAN-TEST-E2E-UPLOAD.md` vì tài liệu còn ghi AI2 qua Kafka trong khi compose đang gọi HTTP `ai2-service:8002` | Hai tài liệu nộp sprint khớp cấu hình đang chạy |

Lead trong tuần này: chốt provider LLM, người giữ key và trần chi tiêu (hạn 30/09); hỏi mentor lịch demo; review và merge PR AI2 vào `develop`.

### 4.2 Chương — Backend

Hướng của Chương: job không được kẹt hoặc fail âm thầm với PDF lớn. Gắn thêm các việc mentor và Đức Dũng giao cho backend.

| # | Việc | Xong khi |
|---|---|---|
| 1 | Watchdog AI1: hạn theo số trang, quá hạn thì `FAILED` với `AI1_TIMEOUT` | Job không đứng mãi ở `PROCESSING` |
| 2 | Snapshot OCR lên MinIO, Kafka chỉ mang URI | Message kết quả OCR nhỏ hơn trần 10MB với file 200 trang và với file khoảng 50MB |
| 3 | AI2: số lần hỏi trạng thái theo số trang, thử lại lỗi tạm, hủy khi hết hạn. Chạy lại AI2 không OCR lại | Một lần OCR xong, chạy lại phân tích không gọi AI1 |
| 4 | Tính lại thời hạn presigned URL (đang 3600 giây) | File 50MB tải xong trước khi link hết hạn |
| 5 | Chia lệnh OCR theo cụm trang, chạy song song, báo tiến độ từng cụm | UI nhận được trang nào xong, trang nào lỗi |
| 6 | 429 và 529 theo mục 2 | Log có mã `RATE_LIMITED` hoặc `UNAVAILABLE`. Hết lượt thử thì job kết thúc, không treo |
| 7 | Query trace ghi database, thay `_simulate_save_query_trace` trong `dossiers.py` | Restart server vẫn đọc lại được trace. Mỗi lượt tìm hoặc hỏi đáp một dòng |
| 8 | Bảng `processed_events` (`event_id`, consumer, lúc xử lý), ghi cùng transaction với kết quả | Restart worker rồi gửi lại cùng event thì không xử lý lần hai |
| 9 | Test tenant và quyền: user tenant A không thấy tài liệu tenant B; user không có quyền thì tài liệu không ra trong tìm kiếm; câu trả lời không trích tài liệu ngoài quyền | Bộ test trong CI, pass. Ghi nhận M-07 = 0 |
| 10 | Chia sẻ: `read` hoặc `edit`, `expires_at`, quá hạn thì từ chối | API trả 403 sau hạn. Sửa hồ sơ cần quyền `edit` |
| 11 | Tách tài liệu trong bộ hồ sơ khi một file chứa cả hợp đồng và phụ lục | Sau khi người dùng xác nhận, dossier có nhiều document, mỗi document đi OCR riêng |
| 12 | Finding hợp đồng–hợp đồng, cùng điều kiện trích dẫn hai phía như finding có phụ lục | API conflict trả cặp hai hợp đồng |
| 13 | Bản online: cùng secret HMAC mới cho backend và worker; không publish cổng 8002 | Từ Internet không vào AI2. Backend gọi AI2 trong mạng nội bộ |

Việc Chương nêu thêm từ hiện trạng, làm nốt nếu còn mở sau 04/10: tác vụ xóa hồ sơ nhiều file đang ghi cùng `sha256="[purged]"` và vướng `uq_document_dossier_sha`; hồ sơ `NEEDS_REVIEW` cần một trạng thái UI đọc là chờ review; bỏ ignore `alembic/versions/*.py` để migration đi cùng ORM.

### 4.3 Đức Dũng — AI1

| # | Việc | Xong khi |
|---|---|---|
| 1 | Kết quả OCR ghi MinIO, Kafka chỉ gửi đường dẫn. Làm cùng Chương | 200 trang và file khoảng 50MB: OCR xong, backend nhận đủ, message Kafka không phụ thuộc số trang |
| 2 | Khi gửi Kafka lỗi, job thành `failed` kèm lý do. Kiểm tra kích thước trước khi gửi | Không còn job treo sau `MessageSizeTooLargeError` |
| 3 | Cụm trang song song, một cụm treo thì cụm đó timeout, cụm khác giữ kết quả | Log chỉ rõ cụm nào `AI1_TIMEOUT` |
| 4 | 429 và 529 ở provider OCR theo mục 2 | Hết lượt thử thì cụm lỗi có mã, không gọi tiếp đến khi hết quota |
| 5 | PDF có lớp text không đi OCR scan. Phân tích vài điều khoản dùng chữ đã lưu | Xem 4 điều khoản trên hồ sơ đã OCR xong không phát sinh lần gọi OCR mới |
| 6 | Một file trộn hợp đồng và phụ lục: đề xuất chỗ cắt và loại từng phần | Backend nhận được danh sách phần, người dùng xác nhận được |
| 7 | Bản online chạy cả PDF scan và PDF có text. Một phiên bản snapshot (đang ghi cả v1 lẫn v3) | Cùng một schema trên máy chủ. AI2 đọc được không phải đoán version |
| 8 | Nếu còn sức: offset ô bảng phụ lục để citation bảng hết `UNVERIFIED` | AI2 xác minh được citation ô bảng trên hợp đồng mẫu |

Đức Dũng đã nêu query trace, test tenant, golden set, SSE và `event_id`. Các việc đó nằm ở mục 4.1, 4.2 và 4.4, không dồn về AI1.

### 4.4 Văn Dũng — AI2

Việc trong tuần 30/09–04/10 giữ theo kế hoạch AI2 đã viết: PR vào `develop` (kể cả sửa digest `sha256:` đang hỏng trên `develop`), healthcheck sang `/healthz` để khỏi gọi LLM, `.dockerignore` để khỏi đóng gói sqlite, CI `pytest` cho `ai-service`, prompt so sánh nói rõ mâu thuẫn, cấu hình LLM bản online, đóng băng code tối 02/10 nếu demo Sprint 2 đúng lịch.

Sprint 3:

| # | Việc | Xong khi |
|---|---|---|
| 1 | Dữ liệu bền của AI2 vào PostgreSQL chung. Nói rõ sqlite hiện ở mục 3, rồi bỏ sqlite khỏi bản online | Restart service online vẫn còn job và kết quả. Image không chứa `runs.sqlite` |
| 2 | 429 và 529 khi gọi LLM theo mục 2. Hết hạn thì trả lỗi có mã, không nuốt job | Một lần giả lập 429 thì job kết thúc với `LLM_RATE_LIMITED` sau đúng số lần thử đã cấu hình |
| 3 | So hai hợp đồng, không chỉ thân hợp đồng với phụ lục. Tên các bên và mã số thuế đưa lại vào phép so (đang bị loại ở `compare.py`) | Một cặp hai hợp đồng ra finding có citation hai phía, có tên bên và MST khi tài liệu có các trường đó |
| 4 | Golden set có người duyệt. Eval chạy trên snapshot OCR thật, không chỉ fixture cây node gọn | Bộ đã chốt (mốc đề xuất ≥ 50 câu) ra được độ đúng và độ đúng citation. `golden_manifest.json` không còn 0 case. DOC-06 có số đo |
| 5 | Câu hỏi trong golden set gồm câu có đáp án, câu không có trong tài liệu, câu đụng quyền. AI2 từ chối trích tài liệu ngoài quyền | Test đi cùng bộ M-07 của Chương |
| 6 | Conflict ngữ nghĩa: thử trên vài cặp soạn sẵn, có người duyệt, rồi mới cam kết phạm vi. Quy tắc phụ lục ký sau sửa văn bản ký trước viết thành một quyết định (DEC) trước khi code | Có biên bản vài cặp và một DEC. Chưa có DEC thì chưa nhận là đã làm conflict ngữ nghĩa |
| 7 | Nếu Sprint 2 chưa kịp: tách nhãn Khoản và Điểm (`structure.py`, `ai1_snapshot_adapter.py`) | Node "3.1." là khoản, node "a)" là điểm, có test |
| 8 | CI `ai-service` chạy `pytest -m "not live and not llm"` trên mỗi PR | Workflow không chỉ in một dòng thông báo |

---

## 5. Thứ tự làm

Làm từ trên xuống. Việc dưới nhường khi sát hạn demo hoặc hết sức sprint.

1. Bản online đủ service, LLM có hạn mức, AI2 không mở cổng ra ngoài.
2. File 50MB và PDF ~200 trang đi hết OCR → backend, job lỗi thì `failed` có mã, không treo.
3. Một database nghiệp vụ. Mật khẩu vẫn ở Keycloak.
4. Bỏ trạng thái nhận định. Chia sẻ có hạn và có đọc/sửa.
5. Tách file trộn hợp đồng với phụ lục. Xung đột hợp đồng–hợp đồng.
6. Query trace, `event_id`, test tenant, SSE.
7. Golden set và DOC-06.
8. Conflict ngữ nghĩa sau khi có DEC và vài cặp thử.

---

## 6. Cam kết gửi mentor

### Tuần 30/09 – 04/10

| Người | Cam kết |
|---|---|
| Trang | Chốt provider LLM và trần chi tiêu. Gửi lịch demo đã hỏi mentor. Merge PR AI2 khi test xanh. Gửi bản đánh giá trên Teams ngày 30/09 |
| Chương | Bản online không mở cổng 8002, secret HMAC mới trùng giữa backend và worker. Job demo 20 trang không kẹt. Ghi nhận thiết kế cụm trang để khỏi sửa tay lần hai ở Sprint 3 |
| Đức Dũng | PDF scan và PDF có text đều ra snapshot trên máy chủ trước 02/10. Một version snapshot |
| Văn Dũng | PR `develop` đã merge, CI ai-service chạy test. Ba câu hỏi mẫu trên hồ sơ 20 trang đúng như kế hoạch AI2. Phần AI2 trong Architecture và API Spec khớp bản đang chạy |

### Sprint 3, xong trước 18/10

| Người | Cam kết |
|---|---|
| Trang | Bỏ nhận định. Chia sẻ đọc/sửa có hạn. SSE tiến độ. Màn xác nhận file đã tách. Màn xung đột hiện cặp hai hợp đồng |
| Chương | Watchdog, MinIO + URI, cụm trang, presign, thử lại 429/529, trace, `event_id`, test tenant, quyền chia sẻ có hạn |
| Đức Dũng | 50MB và ~200 trang qua được bước Kafka. OCR không chạy lại khi chỉ xem điều khoản đã có chữ. Đề xuất chỗ cắt file trộn |
| Văn Dũng | AI2 trên Postgres. Finding hợp đồng–hợp đồng, có tên bên và MST. Golden set đã duyệt và DOC-06 có số. LLM hết quota thì job lỗi có mã |

---

## 7. Khung đánh giá gửi trên Teams ngày 30/09

Lead chấm từ GitHub (commit, PR, review) và từ file test chạy được. Mỗi người một đoạn: việc đã xong, việc chưa xong, bằng chứng.

| Tiêu chí | Nhìn ở đâu |
|---|---|
| Đúng việc đã nhận | Commit và PR trong vùng sở hữu (`frontend/`, `backend/`, AI1, AI2) |
| Test | Số test pass trong CI hoặc lệnh test ghi trong PR. Test bị nới điều kiện để pass thì ghi riêng |
| Hỏng phần người khác | PR làm đỏ CI hoặc làm lệch contract mà không sửa |
| Việc mentor vừa nói | Đã có trong code, mới nằm trên nhánh, hay chưa bắt đầu |
| Nói khi đổi cách | PR hoặc tin nhắn có báo trước khi đổi đường MVP |
| Tài liệu khớp code | DOC và hướng dẫn chạy còn mô tả đúng thứ đang chạy |

Bản chấm ghi tên từng người, không chấm trong file này trước khi đối chiếu GitHub và log test.

---

**Hết DOC-11 · Định hướng Sprint 3**
