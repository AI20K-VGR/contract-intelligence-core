# Hướng dẫn gán nhãn cặp khoản (luồng 2)

Một nguồn duy nhất cho **người duyệt** (phiếu HG-1) và **prompt của người gán nhãn GPT**
(`labeler.py` đọc nguyên văn khối nằm giữa hai dấu `labeler-definitions` bên dưới; sửa khối đó
là đổi prompt ⇒ phải tăng `LABELER_PROMPT_VERSION`).

Đơn vị gán nhãn: **một cặp không thứ tự (A, B)** gồm hai khoản/điểm/phụ lục của **cùng một**
hợp đồng mẫu. Mỗi khoản có `heading` (tiêu đề Điều/Phụ lục chứa nó — chỉ là ngữ cảnh) và `text`
(nội dung khoản — thứ duy nhất được trích span). Cặp cha–con (một khoản với điểm của chính nó)
không bao giờ có trong pool; cặp đã có cạnh luồng 1 (câu thao tác "Sửa đổi khoản 2 Điều 5…")
cũng đã bị loại.

## Định nghĩa và quy tắc phân xử

<!-- labeler-definitions:begin -->
Chọn đúng MỘT nhãn trong tập đóng sau.

- GENERAL_SPECIFIC — một khoản là quy định chung, khoản kia là trường hợp riêng, ngoại lệ hoặc
  chi tiết hoá của CÙNG nghĩa vụ/quyền/chế tài (cùng chủ thể, cùng hành vi hoặc sự kiện). Bắt
  buộc trường `general`: "A" hoặc "B" = khoản chứa quy định CHUNG.
- CONFLICT — hai khoản quy định cùng một vấn đề (cùng chủ thể, cùng hành vi hoặc sự kiện) nhưng
  cho giá trị, thời hạn, mức phạt, tỷ lệ hoặc hậu quả khác nhau, không thể cùng áp dụng nguyên
  văn. Không nói khoản nào thắng.
- DUPLICATE — hai khoản nói cùng một nội dung (cùng nghĩa vụ/quyền, cùng giá trị) chỉ khác câu
  chữ hoặc vị trí.
- REFERENCE — một khoản dẫn chiếu hoặc kết hợp nội dung của khoản kia bằng lời mô tả hoặc địa chỉ
  Điều/khoản/điểm đã phân giải duy nhất tới đúng khoản đó (ví dụ "theo phương thức thanh toán đã
  thỏa thuận", "như cam kết bảo hành ở trên", hoặc dẫn chiếu số điều cụ thể). Bắt buộc trường
  `referrer`: "A" hoặc "B" = khoản chứa lời dẫn chiếu. Với dẫn chiếu có số, chỉ gán khi địa chỉ
  trỏ duy nhất tới khoản còn lại và nội dung trong `text` xác nhận quan hệ; số điều chỉ xuất hiện
  cùng cặp không đủ.
- UNRELATED — mọi trường hợp còn lại, kể cả hai khoản cùng chủ đề chung (cùng nói về thanh toán,
  cùng nói về giao hàng) nhưng không thuộc bốn nhãn trên.

Quy tắc phân xử:
1. Không chắc chắn và không có bằng chứng quan hệ ⇒ UNRELATED.
2. Hai khoản khác chủ thể hoặc khác hành vi/sự kiện → thường là UNRELATED, trừ khi một khoản dẫn chiếu/kết hợp rõ ràng tới khoản kia.
3. Giá trị khác nhau cho cùng vấn đề ⇒ CONFLICT; nhưng nếu một khoản tự nêu là ngoại lệ hoặc
   trường hợp riêng ("trừ trường hợp", "riêng đối với", "đối với … thì") ⇒ GENERAL_SPECIFIC.
4. Cùng nội dung, cùng giá trị ⇒ DUPLICATE; khác giá trị ⇒ không phải DUPLICATE.
5. Dẫn chiếu/kết hợp tới đúng nội dung khoản kia, có thể xác định referrer ⇒ REFERENCE. Xét sau
   CONFLICT/DUPLICATE và trước GENERAL_SPECIFIC; dẫn chiếu cụ thể không tự chứng minh GENERAL_SPECIFIC.
6. Không kết luận pháp lý, không nói khoản nào có hiệu lực hay được ưu tiên.
7. Span: trích NGUYÊN VĂN một đoạn ngắn (không quá 200 ký tự) từ `text` của A (`span_a`) và của
   B (`span_b`) làm căn cứ cho nhãn. Không lấy từ `heading`, không diễn đạt lại, không ghép đoạn
   rời. Bắt buộc với mọi nhãn trừ UNRELATED.
<!-- labeler-definitions:end -->

## Bảng quyết định cho người gán nhãn

So sánh cùng một vấn đề trong phần văn bản được cung cấp. `heading` chỉ giúp định vị ngữ cảnh;
không dùng nó làm bằng chứng thay cho `text`. Không suy ra ý chí, hiệu lực hoặc thứ tự ưu tiên.

| Câu hỏi | Có | Không |
|---|---|---|
| Cùng chủ thể và cùng hành vi/sự kiện hoặc quyền/nghĩa vụ cụ thể? | Tiếp tục | UNRELATED |
| Hai khoản đặt giá trị/thời hạn/hậu quả khác nhau cho cùng vấn đề và đều áp dụng? | CONFLICT | Tiếp tục |
| Hai khoản giữ cùng nội dung và giá trị, chỉ khác cách diễn đạt/vị trí? | DUPLICATE | Tiếp tục |
| Một khoản dẫn bằng mô tả/ngữ nghĩa hoặc số Điều/điểm đã phân giải đúng tới khoản kia? | REFERENCE; `referrer` trỏ khoản dẫn | UNRELATED |
| Một khoản nói rõ là ngoại lệ, phạm vi riêng hoặc chi tiết hóa của nghĩa vụ kia? | GENERAL_SPECIFIC; `general` trỏ khoản nêu quy tắc chung | Tiếp tục |
| Một khoản thêm hành vi, điều kiện hoặc deliverable khác, dù chỉ áp dụng cho nhóm con? | Không phải GENERAL_SPECIFIC; xét tiếp như vấn đề riêng | Tiếp tục |

Thứ tự này phân biệt ngoại lệ tường minh với hai quy định không thể cùng áp dụng. Ví dụ, quy tắc
chung phạt chậm thực hiện và điều khoản “riêng đối với chậm giao hàng” là GENERAL_SPECIFIC; hai
thời hạn thanh toán 30 và 15 ngày cùng áp dụng là CONFLICT; nghĩa vụ giao thêm biên bản kiểm kê
không phải chi tiết hóa nghĩa vụ thanh toán.

Hướng A/B mô tả vai trò trong cặp hiển thị: A là `general` ở GENERAL_SPECIFIC và là `referrer` ở
REFERENCE. Không đổi thứ tự cặp để làm cho một hướng có vẻ hợp lý. Nếu không xác định được hướng
từ câu chữ, chọn UNRELATED thay vì đoán.

## Ví dụ tổng hợp (tự viết, không lấy từ nguồn nào)

| A (`text`) | B (`text`) | Nhãn | Hướng |
|---|---|---|---|
| Bên Mua thanh toán trong 30 ngày kể từ ngày nhận hóa đơn. | Bên Mua thanh toán trong 15 ngày kể từ ngày nhận hóa đơn. | CONFLICT | — |
| Bên vi phạm nghĩa vụ chịu phạt 8% giá trị phần bị vi phạm. | Riêng việc chậm giao hàng, Bên Bán chịu phạt 0,5% mỗi ngày chậm. | GENERAL_SPECIFIC | `general` = A |
| Hàng hóa được bảo hành 12 tháng kể từ ngày nghiệm thu. | Thời hạn bảo hành hàng hóa là mười hai tháng tính từ ngày nghiệm thu. | DUPLICATE | — |
| Bên Bán giao kèm chứng từ theo danh mục đã thống nhất ở phụ lục. | Danh mục chứng từ gồm hóa đơn, phiếu bảo hành và C/O. | REFERENCE | `referrer` = A |
| Bên Mua thanh toán bằng chuyển khoản. | Bên Bán giao hàng tại kho của Bên Mua. | UNRELATED | — |
| Bên Mua thanh toán trong 30 ngày. | Bên Bán xuất hóa đơn trong 30 ngày. | UNRELATED (khác chủ thể, khác hành vi) | — |

## Cách điền phiếu HG-1

Phiếu do P2 xuất (CSV UTF-8 có BOM, mở bằng Excel/LibreOffice) và **nằm ngoài repo** dưới
`AI2_CG_PAIRS_DATA_DIR`. Mỗi dòng là một cặp đã được chọn mẫu có trọng số; các cột
`gpt_label`, `gpt_direction`, `gpt_span_a`, `gpt_span_b`, `grounded` là gợi ý của GPT.

| Cột | Điền gì |
|---|---|
| `decision` | `approve` (nhãn GPT đúng, kể cả hướng) · `relabel` (nhãn hoặc hướng sai) · `reject` (cặp không dùng được: tách khoản lỗi, văn bản rác) |
| `label_fixed` | Chỉ khi `relabel`: một nhãn trong tập đóng ở trên |
| `direction_fixed` | Chỉ khi `relabel` sang GENERAL_SPECIFIC (khoản CHUNG) hoặc REFERENCE (khoản DẪN CHIẾU): `A` hoặc `B` |
| `note` | Tuỳ ý, không bắt buộc |

- Không để trống `decision`; dòng thiếu hoặc sai giá trị làm `import_sheet` báo lỗi kèm số dòng.
- `grounded=false` nghĩa là span GPT không có nguyên văn trong `text`: đọc kỹ, đừng tin span đó.
- Bạn đang thấy nhãn GPT khi duyệt ⇒ đồng thuận GPT↔người trong báo cáo chỉ là **cận trên**.
- Chỉ dòng `approve`/`relabel` (được ghi `approved=true`) mới vào gold; `reject` không tính.
