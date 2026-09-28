# Brainstorm AI2 — năm lát, một hướng

**Ngày:** 2026-09-27  
**Nguồn:** năm agent brainstorm độc lập, sau khi đọc code và các lần chạy hồ sơ OCR thật trong phiên này.  
**Không làm:** không viết code trong bước này. Không claim độ chính xác. Không chọn bên thắng.

## Vấn đề

AI2 đã có đường deterministic (L0–L3, fact, so cặp, cổng citation). Hồ sơ OCR thật cho thấy đường đó vẫn trả lời sai hoặc im: thân không viết “Phụ lục 01” thì cặp giá biến mất, câu mô hình bị xóa vì đếm hit nhiễu, cây điều chỉ là dòng phẳng, registry sáu loại hợp đồng không được pipeline gọi, và “llm ready” không có nghĩa cổng mô hình đang sống.

Tầm nhìn giữ nguyên (`docs/ai2/AI2-DOC-01-product-vision.vi.md`): người rà mở lại hai nguồn, máy không kết luận pháp lý.

## Năm lát đã chốt

Người dùng chọn ghi báo cáo và lập plan cho lát so hai nguồn.

### 1. So thân và phụ lục

| Hướng | Việc | Vì sao không chọn làm mặc định |
|---|---|---|
| A. Giữ chặn | Thiếu chữ “Phụ lục 01” ở thân thì không ghép cặp, chỉ `CONTEXT_GAP` | Hồ sơ `dos_01M3BPQFSXW68FGZJ1RPFMYXTY` không có chữ đó ở thân. Người rà không thấy hai giá trị. |
| B. Ghép trong cùng snapshot | Cùng `item_key` thì hiện cặp và hai citation. Thiếu chữ dẫn chiếu là chú thích “quan hệ chưa xác nhận”, không xóa cặp. | Đây là lát nhỏ nhất còn đạt “thấy cả hai số, mở được cả hai nguồn”. |
| C. Embedding / LLM quyết định quan hệ | Model chọn phụ lục nào sửa điều nào | Đẩy mô hình vào phán đoán gần pháp lý. Đắt và chậm. |

**MVS:** hướng B. Không bịa câu dẫn chiếu. Không chọn bên thắng. MST nếu được ghép thì chỉ để thấy khác nhau, không chọn MST đúng.

### 2. Hỏi đáp

Giữ câu mô hình khi citation phủ ít nhất hai phía (thân và phụ lục). Một phía hoặc một citation thì liệt kê nguồn. Đếm “hai node” không đủ: cả hai node có thể nằm cùng thân hợp đồng.

### 3. Cây từ dòng OCR

Giữ sửa trên bản sao `active_nodes`. Dòng gốc AI1 không ghi đè. Bảng nối trang đã kế thừa header, giữ hàng riêng, và gắn cờ cần rà (`result_structure.py`). Ghi đè node gốc hoặc bắt AI1 xuất cây sẵn đều làm mất chỗ đối chiếu hoặc chuyển chỗ đoán cấu trúc.

Mọi cạnh suy ra phải đối chiếu được về dòng gốc. Thiếu tín hiệu thì thành cờ, không thành cạnh im lặng.

### 4. Sáu loại hợp đồng

`ai-service/app/contracts/contract_profiles.py` đã có sáu loại và test, nhưng pipeline trích xuất không import nó. Không xây sáu bộ trích trước khi có bộ mẫu người duyệt. Lát nhỏ, nếu làm sau, chỉ là nhãn loại mặc định cần rà, cùng một bộ trích xuất.

### 5. Gọi LLM

Tắt trong code (`ai2_query_egress_allowed`, `ai2_processing_egress_allowed` mặc định false). Bật trên Compose local. Worker đọc cờ, không hardcode tắt. `/health` báo ready khi có API key, không khi cổng 9router sống. Fact mà L0 chuẩn hóa được thì không gọi LLM dù egress bật.

## Quyết định

So hai nguồn theo hướng B là việc làm tiếp theo. Bốn lát kia là ràng buộc của plan đó: không bịa dẫn chiếu, không chọn bên thắng, không đụng sáu extractor, không bật egress ngoài cấu hình.

## Việc tiếp

Plan lát so hai nguồn: cùng `item_key` trong một snapshot thì ra cặp `COMPARABLE_DIFFERENCE` hoặc `COMPARABLE_MATCH`, hai citation, và chú thích khi thân không nhắc số phụ lục.
