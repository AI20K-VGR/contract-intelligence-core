# PR #148 — xử lý review truy xuất và câu trả lời

## Thay đổi

- Bỏ mã tài liệu và mô tả gắn với hồ sơ mẫu trong bảng mở rộng query. Không tự đổi “sự cố/dữ liệu” thành một mã biên bản, hoặc “thanh lý/đối soát” thành một mã thanh lý.
- Nhận diện mã theo dữ liệu filename, document_number và OCR của chính hồ sơ; không có danh sách tiền tố được phép. So khớp nguyên mã, tránh nhầm mã ngắn với một mã dài hơn.
- Khi người dùng gọi theo tên tài liệu, lấy tiêu đề OCR đầu trang làm nguồn truy xuất. Cách này áp dụng cả hồ sơ ghép nhiều biên bản/phụ lục vào cùng một PDF. Bảng SLA được đưa vào COMPOSE bằng trang nguồn thay vì chỉ tiêu đề cột.
- Khi được phép dùng LLM, tài liệu được đưa vào COMPOSE để trả lời câu hỏi. Khi không dùng LLM, trả trích đoạn có nhãn rõ, tối đa 350 ký tự nội dung, trạng thái NEEDS_REVIEW. Giữ giới hạn ngữ cảnh COMPOSE 48.000 ký tự và deadline query hiện có.
- Mọi nhánh truy xuất, kể cả trích đoạn dự phòng, giữ phạm vi selected_member_ids sau khi core xác thực.
- Bổ sung quy ước citation PAGE không có bbox vào BE-AI2-PROCESSING-CONTRACT. Không đổi schema hay API. Không sửa logic xây graph/findings trong lần này.

## Kiểm tra

- 275 tests pass, 3 live/LLM tests deselected trong nhóm query, citation, observability và graph regression, với PostgreSQL riêng cho kiểm thử.
- Ruff lint và format trên các file Python sửa.
- Test bổ sung: các mã ZXQ17, RPT/2026/007, PRJ-QA-042 và NV-93; khớp nguyên mã; không tự ánh xạ chủ đề sang mã mẫu; COMPOSE nhận trang nguồn; trích đoạn không LLM được giới hạn; truy xuất theo tiêu đề OCR; COMPOSE nhận đủ dòng bảng.
- Đã restart AI2 rồi gọi backend search trên bốn hồ sơ có sẵn trong PostgreSQL: 20 câu của đợt audit và 5 câu cho bộ 50 trang. 25 câu đều trả lời kèm hit nguồn, tất cả hit trả về VALID. Đọc lại nội dung cho thấy bảng SLA đã có đủ P1–P4 và ngoại lệ bên thứ ba; các câu giá, thanh toán, BOQ, BB01/BB03/TL01 và hai phiên bản SLA giữ các số liệu nguồn. VALID chỉ xác nhận citation resolve được, không đồng nghĩa mọi câu đều hoàn hảo: câu hỏi trang trống 11–13 vẫn thiếu bao phủ; câu quản lý dự án nêu đúng Lê Quốc Nam/Vũ Ngọc Lan nhưng diễn đạt dè dặt chưa nhất quán.
- Một request ngay lúc service mới restart trả connected=false; đã lưu nguyên kết quả và gọi lại sau khi service sẵn sàng, không tính request này vào 25 câu hợp lệ.
- Read API graph sau sửa giữ nguyên tập edge IDs của cả ba hồ sơ audit (operation/pair: 6/11, 0/29, 6/20); bộ 50 trang vẫn 8/31. Đây là kiểm tra read model hiện có, không tuyên bố đã chạy lại pipeline graph.

## Đo token và chi phí mỗi câu hỏi

Lấy token từ usage của từng lời gọi thực tế, cùng dữ liệu snapshot trong PostgreSQL, cùng câu hỏi và cấu hình. Mỗi câu dưới đây có một lời gọi LLM. Bảng đầu so SHA được review với bản sửa; bảng thứ hai tắt riêng lexical_evidence trên bản sửa để đo phần tăng do lexical recall (ablation), không giả định đây là toàn bộ implementation cũ.

USD là **chi phí quy đổi tham chiếu**, dùng giá cấu hình `gpt-5.5` trong `app/llm/observability.py`: input $5/triệu, cached input $0,50/triệu, output $30/triệu. Đây không phải hóa đơn hoặc cam kết chi phí production. Không có cached input trong các lượt đo này. Thời gian/output có thể thay đổi theo từng lần chạy; một lượt đo không đại diện phân phối latency hay độ chính xác toàn hệ thống.

| C?u h?i | Input tr??c | Output tr??c | USD tr??c | Input sau | Output sau | USD sau |
|---|---:|---:|---:|---:|---:|---:|
| BB01 đã giao đủ thiết bị chưa? | 11417 | 199 | 0.063055 | 11310 | 265 | 0.064500 |
| Sự cố dữ liệu được thông báo có đúng hạn không? | 12736 | 429 | 0.076550 | 13547 | 376 | 0.079015 |
| Biên bản thanh lý có bảo lưu công nợ và bảo hành không? | 3285 | 567 | 0.033435 | 11669 | 483 | 0.072835 |
| Phụ lục 03 có hiệu lực từ ngày nào và điều chỉnh giá trị bao nhiêu? | 5762 | 155 | 0.033460 | 5762 | 170 | 0.033910 |
| Phụ lục 02 sửa đổi thời hạn thanh toán như thế nào? | 6000 | 230 | 0.036900 | 6000 | 274 | 0.038220 |
| Nêu đầy đủ thời gian phản hồi và khắc phục P1 P2 P3 P4 trong SLA. | 3051 | 244 | 0.022575 | 5281 | 467 | 0.040415 |

| C?u h?i | Input t?t lexical | Output t?t lexical | USD t?t lexical | Input b?t lexical | Output b?t lexical | USD b?t lexical |
|---|---:|---:|---:|---:|---:|---:|
| BB01 đã giao đủ thiết bị chưa? | 2843 | 294 | 0.023035 | 11310 | 265 | 0.064500 |
| Sự cố dữ liệu được thông báo có đúng hạn không? | 4089 | 361 | 0.031275 | 13547 | 376 | 0.079015 |
| Biên bản thanh lý có bảo lưu công nợ và bảo hành không? | 2866 | 432 | 0.027290 | 11669 | 483 | 0.072835 |
| Phụ lục 03 có hiệu lực từ ngày nào và điều chỉnh giá trị bao nhiêu? | 2965 | 169 | 0.019895 | 5762 | 170 | 0.033910 |
| Phụ lục 02 sửa đổi thời hạn thanh toán như thế nào? | 4192 | 253 | 0.028550 | 6000 | 274 | 0.038220 |
| Nêu đầy đủ thời gian phản hồi và khắc phục P1 P2 P3 P4 trong SLA. | 1579 | 378 | 0.019235 | 5281 | 467 | 0.040415 |

## Giới hạn

Đợt sửa này không tuyên bố giải quyết lỗi phân loại các dòng BOQ thành mâu thuẫn hoặc bổ sung finding tự động cho sai tổng BOQ/lịch thanh toán. Đây là các lỗi đã ghi nhận ở đợt đọc tài liệu trước và thuộc logic khác. Giữ nguyên tài liệu nguồn và kết quả trước sửa để đối chiếu.
