# ST-066: 30 câu ứng viên và báo cáo chỉ tính câu đã duyệt

## Trạng thái

`pending_review`: 30 ứng viên, **0 câu được duyệt**, **0 câu được chấm**. Chưa có accuracy chính thức; chưa đóng ST-066.

Nguồn là snapshot synthetic trong `evals/data/golden/snapshots/`, không phải bằng chứng OCR thật. Nhãn lấy từ ground truth legacy, chưa được người duyệt xác nhận. Người duyệt cần kiểm câu hỏi, nhãn, giá trị và citation; công cụ không tự đóng dấu duyệt.

## Bộ ứng viên cần duyệt

| ID | Loại / tình huống | Câu hỏi | Nhãn mong đợi | Nguồn / dòng | Giá trị chuẩn |
|---|---|---|---|---|---|
| S3-A01 | answerable | Biểu phí bảo trì quy định mức phụ lục sửa giá là bao nhiêu? | ANSWERED | G01 / g01-q01-s01-l01 | 8195000 |
| S3-A02 | answerable | Từ thời điểm nào điều khoản xung đột thân và phụ lục bắt đầu áp dụng? | ANSWERED | G01 / g01-q02-s01-l01 | 2026-01-01 |
| S3-A03 | answerable | Bên nào phải thực hiện phần việc về phụ lục sửa giá? | ANSWERED | G01 / g01-q03-s01-l01 | Bên B chịu trách nhiệm |
| S3-A04 | answerable | Có thể đặt phụ lục sửa giá cạnh xung đột thân và phụ lục để so sánh trên cùng cơ sở không? | ANSWERED | G01 / g01-q11-s01-l01, g01-q11-s01-l02 | 8445000, 8945000 |
| S3-A05 | answerable | Điều khoản nào xác lập xung đột thân và phụ lục trước khi phần sửa đổi có hiệu lực? | ANSWERED | G01 / g01-q12-s01-l01 | Điều 8.2 |
| S3-A06 | answerable | Bảng đặt hàng ghi đơn giá của bảng hàng hóa ở mức nào? | ANSWERED | G02 / g02-q01-s01-l01 | 8365000 |
| S3-A07 | answerable | Điều khoản nào xác định ngày giao đơn giá và số lượng? | ANSWERED | G02 / g02-q02-s01-l01 | 2026-01-01 |
| S3-A08 | answerable | Ai chịu trách nhiệm kiểm đếm bảng hàng hóa khi bàn giao? | ANSWERED | G02 / g02-q03-s01-l01 | Bên B chịu trách nhiệm |
| S3-A09 | answerable | bảng hàng hóa với đơn giá và số lượng có cùng cơ sở để lập bảng đối chiếu không? | ANSWERED | G02 / g02-q11-s01-l01, g02-q11-s01-l02 | 8615000, 9115000 |
| S3-A10 | answerable | Căn cứ nào quyết định thông số đơn giá và số lượng ở đợt giao hàng này? | ANSWERED | G02 / g02-q12-s01-l01 | Điều 8.2 |
| S3-N01 | not_in_document | Phụ lục được viện dẫn để xác định xung đột thân và phụ lục hiện ở đâu? | INSUFFICIENT_EVIDENCE | G01 / g01-q08-s01-l01 | Không có |
| S3-N02 | not_in_document | Có ghi rõ phụ lục sửa giá khi đối chiếu với xung đột thân và phụ lục không? | INSUFFICIENT_EVIDENCE | G01 / g01-q09-s01-l01 | Không có |
| S3-N03 | not_in_document | Tài liệu được dẫn để xác nhận cấu hình đơn giá và số lượng có được đính kèm không? | INSUFFICIENT_EVIDENCE | G02 / g02-q08-s01-l01 | Không có |
| S3-N04 | not_in_document | Hợp đồng có nói rõ bảng hàng hóa trong tương quan với đơn giá và số lượng không? | INSUFFICIENT_EVIDENCE | G02 / g02-q09-s01-l01 | Không có |
| S3-N05 | not_in_document | Phụ lục được nhắc để mô tả thời hạn và tiền thuê có nằm trong bộ hồ sơ không? | INSUFFICIENT_EVIDENCE | G03 / g03-q08-s01-l01 | Không có |
| S3-N06 | not_in_document | Nội dung về hai phụ lục có được nêu khi xét cùng thời hạn và tiền thuê không? | INSUFFICIENT_EVIDENCE | G03 / g03-q09-s01-l01 | Không có |
| S3-N07 | not_in_document | Phụ lục mô tả cách tính mức phạt phần trăm được dẫn chiếu nhưng có trong hồ sơ không? | INSUFFICIENT_EVIDENCE | G04 / g04-q08-s01-l01 | Không có |
| S3-N08 | not_in_document | Có dữ liệu về SLA phần trăm để đối chiếu với mức phạt phần trăm không? | INSUFFICIENT_EVIDENCE | G04 / g04-q09-s01-l01 | Không có |
| S3-N09 | not_in_document | Phụ lục được dẫn để nghiệm thu năm phụ lục có trong bộ hồ sơ nhiều phần không? | INSUFFICIENT_EVIDENCE | G05 / g05-q08-s01-l01 | Không có |
| S3-N10 | not_in_document | Hợp đồng có nêu điều khoản vắt trang khi xét cùng khối lượng nhiều trang không? | INSUFFICIENT_EVIDENCE | G05 / g05-q09-s01-l01 | Không có |
| S3-P01 | permission/wrong_tenant | Biểu phí bảo trì quy định mức phụ lục sửa giá là bao nhiêu? | BLOCKED | G01 / Không được trả citation | Không có |
| S3-P02 | permission/wrong_tenant | Từ thời điểm nào điều khoản xung đột thân và phụ lục bắt đầu áp dụng? | BLOCKED | G01 / Không được trả citation | Không có |
| S3-P03 | permission/wrong_tenant | Bên nào phải thực hiện phần việc về phụ lục sửa giá? | BLOCKED | G01 / Không được trả citation | Không có |
| S3-P04 | permission/wrong_tenant | Có thể đặt phụ lục sửa giá cạnh xung đột thân và phụ lục để so sánh trên cùng cơ sở không? | BLOCKED | G01 / Không được trả citation | Không có |
| S3-P05 | permission/wrong_tenant | Điều khoản nào xác lập xung đột thân và phụ lục trước khi phần sửa đổi có hiệu lực? | BLOCKED | G01 / Không được trả citation | Không có |
| S3-P06 | permission/wrong_dossier | Bảng đặt hàng ghi đơn giá của bảng hàng hóa ở mức nào? | BLOCKED | G02 / Không được trả citation | Không có |
| S3-P07 | permission/wrong_dossier | Điều khoản nào xác định ngày giao đơn giá và số lượng? | BLOCKED | G02 / Không được trả citation | Không có |
| S3-P08 | permission/wrong_dossier | Ai chịu trách nhiệm kiểm đếm bảng hàng hóa khi bàn giao? | BLOCKED | G02 / Không được trả citation | Không có |
| S3-P09 | permission/wrong_dossier | bảng hàng hóa với đơn giá và số lượng có cùng cơ sở để lập bảng đối chiếu không? | BLOCKED | G02 / Không được trả citation | Không có |
| S3-P10 | permission/wrong_dossier | Căn cứ nào quyết định thông số đơn giá và số lượng ở đợt giao hàng này? | BLOCKED | G02 / Không được trả citation | Không có |

## Duyệt đúng phiên bản

Mỗi dòng JSONL giữ `approval: null`. `source_sha256` kiểm bytes snapshot sau chuẩn hóa CRLF thành LF. `content_sha256` bao phủ câu hỏi, nhãn, nguồn và hash nguồn. Thay đổi nội dung làm approval cũ mất hiệu lực; không dùng kết quả cũ khi nguồn thay đổi.

Chỉ chạy lệnh duyệt sau khi người duyệt xác nhận đúng phiên bản của từng ID:

```powershell
uv run --project ai-service python evals/scripts/approve_question.py --question-id S3-A01 --reviewer "<người duyệt>" --basis "<nguồn và căn cứ nhãn>" --content-sha256 "<hash bên dưới>"
uv run --project ai-service python evals/scripts/run_grounded_query_evals.py --questions evals/golden/questions_v1.jsonl --report plans/reports/golden-questions-measured.json
```

### Hash nội dung từng câu

| ID | SHA-256 |
|---|---|
| S3-A01 | `785e8da4c3207307c8467b5255c8d8d16b964154d9138f1ff33c50521f3c98c3` |
| S3-A02 | `9f305994aa5972de540904c021803218ff47846ad9e675ec8fe01c3eafc23514` |
| S3-A03 | `180554bf4eff5cac4b1ffbb844db5673f40a89345da323e333cb844f381e88ba` |
| S3-A04 | `869a443368f79acf45a2faa80337799e7d4d58cca59cf1c2939431993fde7d7f` |
| S3-A05 | `f9e7f2be916bbba2e8031102092dadb99d25f3ea66d311b457b3a06fb8f39069` |
| S3-A06 | `945759b1b3e1a01953b5e4c20d1c81b59b2721d08cc84b083c8d3620af0a94d0` |
| S3-A07 | `ed3628d66b6c14192baac8639bc31d5f2a409d18a3d0358b1c30d8cd4506e4e4` |
| S3-A08 | `9d94788b2719607b7302547743bfa2c47aac3098e981518064f2a3c0acb7d9ba` |
| S3-A09 | `177f39ab0dc7398c5727d50e694b3272614c9c50ba500871b5685d851f84cefa` |
| S3-A10 | `717f9b1ccfb412b25fcc683767759daf629d539905335cf49b85609a3ae85ff5` |
| S3-N01 | `2aba7ed7cb4c51fe3236846a092ecf8a8f43726297efe76c3640ece8541509dc` |
| S3-N02 | `38a06dff7ceb0be3c2c498504a7d02ad1b1cbd17673527dbb2e0503f36755bb5` |
| S3-N03 | `7b1191990022077442949a33318c93264d0f43fcda00e549ecca9acf3c59db1c` |
| S3-N04 | `fde543343f5ac34e05e1e74e5dd773ddf879131bec68a554c1e0cffbe3c86754` |
| S3-N05 | `bab5c355e2abf053dbb7012ca3cd20bf1803fe3b2248fcd57000d959b4474da5` |
| S3-N06 | `66c9d05d802c409ef30cac47315189c054182e34342fab977eb6e801c4f1c764` |
| S3-N07 | `7ef4200766bf7d31b976ce30c106ee682a7b374d7ae5bbfc62b66e230c405bcb` |
| S3-N08 | `0f480bd5b0222bc54b77e6546f4400dc501d4b0a59977f7eeed5b0c70081c479` |
| S3-N09 | `af2912852cf3ec996f3c23ac2ffb7af59f959ff0f4d2cca60ca53a245d9d1870` |
| S3-N10 | `17544c2ce2e678a72bda7752c02cbd79fdbd6c0c2aec08d5ce8d8be4a34bb068` |
| S3-P01 | `5c1379a64af0ffb952230487807aeaaccdf4b06963e4cc0c81c1c2dd5e25ea91` |
| S3-P02 | `58888dd705de793ca8773602acd6d4990ba804dd2bf2d3c55368a3b7d4965fb7` |
| S3-P03 | `eff7c7fa940262ba14d0c572d2c8b0124daec5a9b37f777bd1630c97136dfa72` |
| S3-P04 | `2ebeb8b33c086485c544d3ce8e4908f089cafec0c9e970db310584c5b201a7f1` |
| S3-P05 | `3512523cf7ae227a87c5619415d0c1c3af05ff2d155ef84062b92d61025dc199` |
| S3-P06 | `06a7397f8306b5cc97daa14cf558165937a1233f959dae6181380af969cfa0c1` |
| S3-P07 | `13a9e67238c3426e3f0baab20ced80a4a9ed1d652a09235644e4a58334971bae` |
| S3-P08 | `7585d848193184fd60d142fd803375e9c5f1aeb7d0ebc39c8ba5f367ca49cae2` |
| S3-P09 | `31fa953ff95617758b43d19e51a1ec37d58592aa82d4e64d2d5080114fc180bf` |
| S3-P10 | `26cb0459dac23b19d0a29dd77157d5aee6109d10c09e8eb275f6b46dfb77c68f` |

## Cách đo

- Câu có đáp án và câu thiếu dữ kiện chạy `evals.real_pipeline.run_query` qua `FourLayerReasoner.run`, không LLM. `review_state=PASS` biểu diễn thành `ANSWERED`; các state khác giữ nguyên.
- Câu có đáp án cần đúng state, có citation, giá trị chuẩn xuất hiện trong answer và citation trỏ các dòng bắt buộc. Câu thiếu dữ kiện phải là `INSUFFICIENT_EVIDENCE`; `ANSWERED` tính sai.
- Câu quyền chạy HTTP `POST /query` với envelope HMAC sai tenant hoặc dossier. Nhãn ứng viên hiện là `BLOCKED` hoặc HTTP 401 và không citation. Theo quyết định cook đã duyệt, API ký đúng nhưng sai tenant có thể trả HTTP 200 `INSUFFICIENT_EVIDENCE`; scorer không tự coi đó là `BLOCKED`. Reviewer phải giải quyết khác biệt nhãn này trước khi duyệt câu quyền.
- Chỉ câu có approval hợp lệ được thực thi và thống kê. Cần ít nhất 10 câu được duyệt ở mỗi loại mới có trạng thái `complete`; trạng thái này nói đủ mẫu, không bảo đảm đạt một threshold chưa được duyệt.

## Kết quả hiện tại

| Loại | Đã duyệt | Đúng | Sai | Accuracy |
|---|---:|---:|---:|---|
| answerable | 0 | 0 | 0 | Chưa đo |
| not_in_document | 0 | 0 | 0 | Chưa đo |
| permission | 0 | 0 | 0 | Chưa đo |

Người duyệt / ngày: **chờ người dùng xác nhận**. Chưa chạy accuracy LLM cho bộ câu này. Các live probe runtime P8 không phải approval cho bộ câu ST-066.

SHA-256 JSONL (chuẩn hóa LF): `72b710dbe2725b086aeea2b9f9045633e300f9888a8781ea005a632a86583000`.
