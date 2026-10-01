# Nghiên cứu — D3 (phạm vi trong key) và D4 (quản trị lexicon) cho AI2 clause key graph

Ngày: 2026-10-01 · Bối cảnh: sau `plans/reports/ai2-clause-key-critique-report.md` (verdict BLOCKED advisory) và **DEC-dungskbg2004-3** (key graph là lõi; cổng đo theo hồ sơ).
Nhãn: OBSERVED (đã đo/đọc), `[ASSUMED]` (chưa kiểm).

---

## D3 — Có đưa "phạm vi/đối tượng" vào key REMEDY không?

### Vấn đề (từ critique C-10)

Key REMEDY hiện là `(bearer, action, qualifier)` (`evals/spikes/clause_key/mechanism.py:406`). Hai điều khoản cùng hành vi nhưng khác phạm vi bị coi là cùng nhóm:
- `HD-TONG-HOP.vi.md` 5.2 "phạt chậm phần **xây lắp**" ~ 5.3 "phạt chậm phần **thiết bị**" → `COMPARABLE_DIFFERENCE`, trong khi văn bản ghi "khác phạm vi, không gộp".
- 5.1 "phạt chậm tiến độ **chung**" ~ 5.2 → lẽ ra `GENERAL_VS_SPECIFIC`.
- "thanh toán tiền thuê" và "thanh toán tiền điện, nước" ra cùng `('LESSEE','PAY','LATE')`.

### Đo trên dữ liệu thật đã có (OBSERVED)

Quét cue phạm vi tường minh (`phần …`, `hạng mục`, `lô hàng`, `đợt`, `tiền thuê`, `cước phí`, `phí dịch vụ`, `thiết bị`, `công trình`…) trên 68 frame REMEDY có gold key của held-out 1 + 2:

| Chỉ số | Giá trị |
|---|---|
| Frame có ≥ 1 cue phạm vi | 25/68 (37%) |
| Cặp gold cùng key | 135 |
| Cả hai có phạm vi và phạm vi khác chữ | 10 |
| Chỉ một bên có phạm vi | **57** |
| Không bên nào / cùng phạm vi | 68 |

Trong 10 cặp "khác chữ": **chỉ 3 cặp khác phạm vi thật** (H26/H27/H28: chung / xây lắp / thiết bị). 7 cặp còn lại là **cùng phạm vi nhưng viết khác** ("tiền thuê theo thỏa thuận" vs "tiền thuê mặt bằng" vs "tiền thuê nhà").

### Ba phương án

| | A. Phạm vi **trong key** | B. Phạm vi là **thuộc tính so sánh** trong `decide()` | C. Không làm gì |
|---|---|---|---|
| Cách làm | Key = `(bearer, action, qualifier, scope)` | Key giữ 3 thành phần; frame mang thêm `scope` (span nguyên văn + chuẩn hóa nếu chắc); `decide()` xét scope trước khi so giá trị | Giữ như hiện tại |
| Ảnh hưởng recall gom nhóm | **Nặng**: 57 + 10 = 67/135 cặp (≈ 50%) bị tách nhóm nếu scope trích được; recall đang ~12,5% trong hồ sơ sẽ còn thấp hơn | Không đổi (key không đổi) | Không đổi |
| Sai do chuẩn hóa scope | Mỗi lỗi chuẩn hóa scope = **mất cặp im lặng** (không bao giờ so) — 7/10 cặp "khác chữ" là cùng phạm vi | Lỗi chuẩn hóa scope → cặp vẫn hiện, nhãn là "cần xem" | – |
| Trường hợp 5.2 ~ 5.3 | Không bao giờ đặt cạnh nhau → người rà không thấy | Hiện cạnh nhau với nhãn `SCOPE_DIFFERS` (không so giá trị) | Sai: `COMPARABLE_DIFFERENCE` |
| Trường hợp 5.1 chung ~ 5.2 | Tách nhóm | `GENERAL_VS_SPECIFIC` | Sai |
| Gánh nặng lexicon | Cần thêm một **lexicon phạm vi** thứ hai (cùng bài toán đuôi dài) | Không bắt buộc; dùng span nguyên văn + đối chiếu `item_key`/số hạng mục sẵn có | – |
| Độ phức tạp code | Trung bình | Thấp–trung bình | 0 |

### Đề xuất D3: **Phương án B** — phạm vi là thuộc tính so sánh, không nằm trong key

Lý do:
1. Đặt scope vào key nhân đôi đúng bài toán đang thất bại (chuẩn hóa đuôi dài), và mỗi lỗi biến thành **mất cặp im lặng** — trái nguyên tắc "không biến thiếu thành không rủi ro".
2. Trường hợp người rà cần thấy (5.2 vs 5.3) vẫn được thấy, với nhãn đúng, thay vì bị giấu.
3. Không cần lexicon thứ hai.

Quy tắc `decide()` đề xuất (áp dụng trước bước so hậu quả):

| Scope bên A | Scope bên B | Kết quả |
|---|---|---|
| có, chuẩn hóa chắc chắn | có, khác | `SCOPE_DIFFERS` — hiển thị, **không** so giá trị |
| có | không có | `GENERAL_VS_SPECIFIC` |
| có, không chuẩn hóa chắc | bất kỳ | so tiếp nhưng **không bao giờ** trả `DUPLICATE` |
| không có | không có | như hiện tại |

"Chuẩn hóa chắc chắn" giai đoạn đầu chỉ gồm: số/mã hạng mục khớp `item_key` sẵn có, và danh sách đóng nhỏ theo profile (xây dựng: `xây lắp`, `thiết bị`, `phần việc`; thuê: `tiền thuê`, `điện`, `nước`, `phí dịch vụ`). Ngoài danh sách → giữ span, coi là "không chắc".

Kiểm chứng cần làm (không cần LLM, chạy lại trên span đã lưu): thêm 3 mutation golden — "cùng hành vi khác phạm vi", "chung vs riêng", "cùng phạm vi viết khác" — và kiểm `false-DUPLICATE = 0` theo cổng DEC-dungskbg2004-3.

---

## D4 — Ai vận hành vòng tăng trưởng lexicon, và dữ liệu tenant dùng thế nào?

### Ràng buộc đã có (OBSERVED)

| Nguồn | Nội dung | Hệ quả |
|---|---|---|
| `docs/ai2/AI2-01-business-policy-perspective.vi.md:102` | Dữ liệu tenant không dùng train/cải thiện cho tenant khác nếu chưa opt-in | Không có lexicon chung học từ mọi khách hàng mặc định |
| `docs/ai2/AI2-DOC-02-brd.vi.md:35` (BR-A10) | Không train chéo tenant | Như trên |
| `docs/ai2/AI2-DOC-02-brd.vi.md:78` | Cấm "một lần sửa người dùng tự đổi rule/gold" | Quyết định review **không** được tự động thêm alias; cần bước duyệt có version |
| `docs/ai2/AI2-01-business-policy-perspective.vi.md:30,38` | Có pin `tenant_profile_version`; đổi profile phải tạo run mới, giữ kết quả cũ | Chỗ tự nhiên cho lexicon riêng từng tenant, có version |

### Bằng chứng từ spike/critique

- Lexicon v2 đóng góp ròng **0 / −1** frame trên held-out mới; alias rộng mới ("thực hiện") tạo key sai (critique C-09, RV).
- Phần lớn lỗi là **lỗi cấu trúc** (thiếu chủ ngữ, câu danh từ hóa, hậu quả kép…) — thêm alias không sửa được (C-09, BS).
- Ứng viên alias **sai cũng rẻ**: một alias tồi trong ô action biến "không chắc" thành key xác định sai (C-02).

→ Alias **không thể** do người rà thêm tự do; mỗi alias phải qua kiểm tra va chạm/hồi quy.

### Bốn mô hình quản trị

| | G1. Lexicon toàn cục, chỉ dev phát hành | G2. Lớp alias theo tenant, người rà sửa tay | G3. LLM đề xuất → người duyệt → lớp tenant có version | G4. Không tăng trưởng lexicon |
|---|---|---|---|---|
| Nguồn dữ liệu | Mẫu công khai, giả lập, dữ liệu đã opt-in | Hàng đợi `UNMAPPED` của tenant | Hàng đợi `UNMAPPED` của tenant | – |
| Tuân thủ `:102` / BR-A10 | Có (nếu chỉ dùng nguồn công khai/opt-in) | Có (chỉ trong tenant) | Có (chỉ trong tenant; đưa lên toàn cục chỉ khi opt-in) | Có |
| Tuân thủ `BRD:78` | Có | **Không**, nếu sửa áp dụng ngay | Có — đề xuất ≠ áp dụng; áp dụng qua duyệt + tăng `tenant_profile_version` | Có |
| Kiểm soát chất lượng alias | Hồi quy trên dev/held-out trước phát hành | Yếu | Kiểm tra tự động (va chạm, stoplist động từ chung) + duyệt người + đo tỷ lệ key sai theo nguồn alias | – |
| Tốc độ tăng recall | Chậm (theo chu kỳ release) | Nhanh nhưng rủi ro | Trung bình | 0 (recall tĩnh) |
| Người vận hành | Dev team | Người rà | Trưởng nhóm rà của tenant (duyệt) + dev (luật kiểm tra) | Không ai |
| Chi phí | Thấp | Thấp | Trung bình (UI duyệt, LLM đề xuất) | 0 |

### Đề xuất D4: **G1 ngay bây giờ, thiết kế sẵn G3 cho sau thí điểm**

**Giai đoạn hiện tại (thí điểm một người, chưa có tenant thật):**
- Lexicon là **tài sản do dev phát hành** (G1), có version, mỗi bản phải qua cổng DEC-dungskbg2004-3 trên hồ sơ thật ẩn danh.
- Hàng đợi `UNMAPPED` + `?` chỉ **ghi thống kê** (cụm nào, bao nhiêu lần), không tự sinh alias.
- Đánh giá giá trị sản phẩm với **recall tĩnh** (theo product-value-critic); không tính lexicon là lợi thế cạnh tranh.

**Khi có tenant thật (G3), cần 6 quy tắc:**
1. **Hai vòng tách biệt**: vòng *mechanism* (luật, cấu trúc, toàn cục) do dev, có held-out; vòng *alias* (từ vựng, theo tenant).
2. Alias tenant nằm trong `tenant_profile_version`; thêm alias = tăng version = chạy lại tạo run mới, giữ kết quả cũ.
3. LLM chỉ **đề xuất** alias từ `UNMAPPED` (chọn trong action/qualifier có sẵn); người có vai trò **biên tập lexicon tenant** duyệt — đúng `BRD:78`.
4. Kiểm tra tự động trước khi duyệt: alias không va chạm alias của action khác; không nằm trong stoplist động từ chung ("thực hiện", "giao"…); không ngắn hơn 2 âm tiết.
5. Mọi key sinh từ alias tenant mang `method=TENANT_ALIAS` để đo **tỷ lệ key sai theo nguồn alias**; vượt ngưỡng thì thu hồi alias.
6. Đưa alias lên toàn cục chỉ khi tenant **opt-in**, và chỉ chuyển **chuỗi alias trừu tượng** (không chuyển văn bản hợp đồng); dev duyệt và chạy hồi quy.

### Câu hỏi mở cho D4

- Ai là "biên tập lexicon tenant" trong mô hình người dùng hiện tại (vision chưa có vai trò này)?
- Ngưỡng "tỷ lệ key sai theo nguồn alias" để thu hồi alias.
- Có cần điều khoản opt-in trong hợp đồng dịch vụ để đưa alias lên toàn cục không (việc của pháp chế, không phải AI2).

---

## Tóm tắt đề xuất

| Mục | Đề xuất | Lý do chính |
|---|---|---|
| D3 | **B** — phạm vi là thuộc tính so sánh trong `decide()`, không nằm trong key | Đặt vào key tách ≈ 50% cặp cùng nhóm và biến lỗi chuẩn hóa thành mất cặp im lặng; chỉ 3/135 cặp khác phạm vi thật |
| D4 | **G1 ngay, thiết kế sẵn G3** | Tuân thủ `:102`, BR-A10, `BRD:78`; bằng chứng cho thấy alias tự do làm hại precision; chưa có người vận hành trong thí điểm |
