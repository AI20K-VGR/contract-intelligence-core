# AI2 — Full flow cho câu hỏi đếm số bên

## Mục tiêu

Với câu hỏi `Có bao nhiêu bên trong hợp đồng?`, AI2 phải trả lời từ đúng một AI1 snapshot, không suy đoán tên pháp nhân và không trộn hai hợp đồng chỉ vì có cùng `dossier_id`.

## Luồng chuẩn

1. API nhận `ai1.snapshot.v1` và adapter giữ nguyên page, line, node, table, digest.
2. Người dùng gửi câu hỏi qua `/api/workspace/{session_id}/ask`.
3. Query router phân loại thành `count_entity`.
4. L0 gọi `list_structure` và `search_structured` trong đúng dossier scope, đồng thời hydrate node text để tìm MST nằm trong cùng evidence với vai trò bên.
5. Nếu có MST gắn với vai trò, AI2 đếm MST duy nhất; cùng MST lặp lại chỉ là một pháp nhân.
6. Nếu snapshot chỉ có token `Bên A/B/C/Y` nhưng không có tên pháp nhân hoặc MST, AI2 chỉ báo số vai trò và trả `NEEDS_REVIEW`, không khẳng định đó là số bên thực tế.
7. L3 resolve citation về page chứa chính đoạn nhận diện. Node spanning nhiều trang phải được thu hẹp về page/line revision tương ứng.
8. `used_llm` chỉ là `true` khi thực sự có completion được gửi; câu hỏi L0 không gọi LLM dù request đặt `use_llm=true`.

## Không được làm

- Không đếm số lần role xuất hiện thành số bên.
- Không dùng số lần role xuất hiện để thay cho số pháp nhân.
- Không lấy chữ “Công ty” trong phần template làm tên bên.
- Không trả citation có line ID của page khác.
- Không tạo relation hoặc candidate giữa `doc-001` và `doc-002`.

## Acceptance test

Hai file OCR-lab hiện tại phải đạt:

| Snapshot | Kết quả đếm | Citation | Trạng thái |
|---|---:|---|---|
| `doc-001` | chỉ xác nhận 2 vai trò: A, B; chưa có tên/MST | tất cả `VALID` | `NEEDS_REVIEW` |
| `doc-002` | 2 bên/pháp nhân theo MST `0109988776`, `0112233445` | tất cả `VALID` | `ANSWERED` |

Gate này được kiểm tra qua adapter → IDP → QueryRouter → L3 grounding, test package và HTTP demo; không chỉ kiểm tra trực tiếp hàm đếm.
