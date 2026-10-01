# Hướng dẫn gán nhãn tập held-out — AI2 clause key spike

Mục đích: đo cơ chế tách key (bản đóng băng **v1.1**, `evals/spikes/clause_key/results/v1.1-freeze.sha256`) trên điều khoản **thật, đã ẩn danh**, nhãn do **người khác Claude** gán. Đo **một lần**; không sửa code/lexicon/prompt sau khi xem kết quả.

## 1. Chuẩn bị

1. Mở `evals/spikes/clause_key/heldout_template.csv` bằng Excel (UTF-8). Xem mẫu điền ở `heldout_example.csv`.
2. Lưu file của bạn thành `evals/spikes/clause_key/heldout.csv`.
3. **Ẩn danh trước khi dán**: thay tên công ty, MST, địa chỉ, số tài khoản bằng giá trị giả; giữ nguyên cấu trúc câu và con số tiền/ngày (chỉ dữ liệu ẩn danh được gửi tới LLM — D-A6).

## 2. Chọn điều khoản

- Mục tiêu 20–40 điều khoản, rải cả 6 loại hợp đồng nếu có.
- **Ưu tiên nhiều cách viết cho cùng một chuyện** (vd 5–8 điều khoản về chậm giao hàng từ các hợp đồng khác nhau) — đây là nguồn cặp để đo gom đúng/gom đủ; mục tiêu ≥ 120 cặp.
- Chọn cả câu dài nhiều mệnh đề, câu bị động ("được/không được"), câu tham chiếu điều khác, câu mà bạn thấy **không có key phù hợp**.
- Không chọn lại câu đã có trong `clauses_dev.jsonl` / `clauses_test.jsonl`.

## 3. Mỗi dòng = một frame

Một khoản có 2 mệnh đề chế tài → 2 dòng cùng `clause_id`; dòng thứ hai để trống `text`.

| Cột | Điền gì |
|---|---|
| `clause_id` | Mã tự đặt, vd `H01` |
| `profile` | `SALES`, `SUPPLY_SERVICE`, `LEASE`, `CONSTRUCTION_WORK`, `EMPLOYMENT`, `NDA` |
| `text` | Nguyên văn điều khoản (chỉ dòng đầu của khoản) |
| `context_parties` | Nếu hợp đồng dùng "Bên A/Bên B": `Bên A=BUYER; Bên B=SELLER` |
| `frame_type` | `REMEDY` (vi phạm → hậu quả) hoặc `PARAMETER` (giá, tiền thuê, lương, thời hạn…) |
| `bearer` | Bên **vi phạm** (xem bảng 4.1) |
| `action` | Hành vi bị vi phạm (bảng 4.2); **`NONE` nếu không mục nào đúng nghĩa** |
| `qualifier` | Cách vi phạm (bảng 4.3); để trống nếu câu không nói |
| `param` / `object` | Với `PARAMETER`: tên đại lượng (bảng 4.4) và đối tượng (vd `hàng hóa A`), hoặc `NONE` |
| `anchor` | **Một đoạn chép nguyên văn ngắn** giúp nhận ra frame (thường là cụm hậu quả, vd `chịu phạt 5.000.000 đồng`) |
| `consequence_type` | `PENALTY_FIXED`, `PENALTY_RATE`, `INTEREST`, `DAMAGES`, `TERMINATION`, `SUSPENSION`, `WITHHOLD` |
| `consequence_value` | Số đã chuẩn hóa: `5000000` cho 5 triệu, `0.05` cho 0,05% |
| `note` | Tùy chọn: lý do chọn nhãn khó |

**Quy tắc quan trọng — gán theo nghĩa thật, không theo chữ:**
- "Bên Bán không được thanh toán đúng hạn" → bearer là **BUYER** (bên phải trả), action `PAY`, qualifier `LATE`.
- "Bên nhận sử dụng thông tin sai mục đích" → **không** phải `DISCLOSE` → `NONE`.
- "Bên Mua chậm nhận hàng" → **không** phải `DELIVER`/`ACCEPT` → `NONE`.
- Nếu không chắc qualifier nào, để trống thay vì đoán.

## 4. Từ vựng key (lexicon v1)

### 4.1 Bearer (bên)
`SELLER`, `BUYER`, `SUPPLIER`, `CUSTOMER`, `LESSOR`, `LESSEE`, `CONTRACTOR`, `OWNER`, `EMPLOYER`, `EMPLOYEE`, `DISCLOSER`, `RECIPIENT`, `ANY_PARTY` (câu chung: "bên vi phạm", "mỗi bên")

### 4.2 Action

| Key | Nghĩa |
|---|---|
| `DELIVER` | Bên bán/cung cấp giao hàng hóa, thiết bị (không gồm bên mua nhận hàng, không gồm giao chứng từ/hóa đơn) |
| `PAY` | Trả tiền theo hợp đồng: tiền hàng, phí, tiền thuê, tiền lương (không gồm xuất hóa đơn) |
| `ACCEPT` | Kiểm tra và chấp nhận kết quả công việc (không phải nhận hàng) |
| `WARRANT` | Sửa chữa/thay thế trong thời gian bảo hành |
| `HANDOVER_ASSET` | Bàn giao tài sản thuê/mặt bằng |
| `RETURN_ASSET` | Trả lại tài sản thuê khi kết thúc |
| `COMPLETE_WORK` | Hoàn thành công việc/công trình xây dựng |
| `PROVIDE_SERVICE` | Cung cấp dịch vụ |
| `DISCLOSE` | Tiết lộ/để lộ/rò rỉ thông tin mật (không gồm tự dùng sai mục đích) |
| `WORK` | Người lao động thực hiện công việc |
| `TERMINATE_EARLY` | Một bên tự chấm dứt/nghỉ việc trước hạn (không gồm tự ý bỏ việc) |
| `ANY_OBLIGATION` | Vi phạm nghĩa vụ chung, không chỉ rõ nghĩa vụ nào |
| `NONE` | Không mục nào đúng nghĩa → hệ thống đúng khi trả `UNMAPPED` |

### 4.3 Qualifier
`LATE` (chậm, trễ, không đúng hạn), `NOT_PERFORMED` (không thực hiện), `DEFECTIVE` (sai chất lượng/quy cách/thiết kế), `WRONG_QTY` (thiếu/sai số lượng), `UNAUTHORIZED` (trái phép, chưa được đồng ý)

### 4.4 Parameter
`PRICE` (đơn giá), `CONTRACT_VALUE` (giá trị/tổng giá trị hợp đồng), `RENT`, `DEPOSIT`, `SALARY`, `WARRANTY_PERIOD`, `CONFIDENTIALITY_PERIOD`, `NONE` (vd giá trị bảo lãnh, tạm ứng)

## 5. Chạy đo

```bash
ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.import_heldout evals/spikes/clause_key/heldout.csv evals/spikes/clause_key/clauses_heldout.jsonl
AI2_LLM_BASE_URL=http://127.0.0.1:20128/v1 ai-service/.venv/Scripts/python.exe -m evals.spikes.clause_key.run_spike --mode llm-full --lexicon evals/spikes/clause_key/lexicon_v1.json --data evals/spikes/clause_key/clauses_heldout.jsonl
```

Script import báo lỗi theo số dòng nếu nhãn không hợp lệ (key không có trong từ vựng, anchor không có trong câu…). Trước khi chạy đo, kiểm tra hash code chưa đổi so với `results/v1.1-freeze.sha256`.

## 6. Cổng quyết định

| Kết quả held-out | Quyết định |
|---|---|
| Cận dưới Wilson precision ≥ 95% **và** recall ≥ 80% | Chọn phương án 3 (frame phân tầng), viết lại plan B/C |
| Precision điểm ≥ 95% nhưng cận dưới < 95% | Mở rộng mẫu |
| Precision < 90% | Lùi về phương án 1 (Fact++) |
