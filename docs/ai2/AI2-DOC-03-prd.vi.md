# DOC-03 — Yêu cầu sản phẩm (phần AI2)

**Phiên bản:** v1.1 · **Ngày:** 20/09/2026  
**Nguồn:** [LF DOC-03](../DOC-03-prd.md), [AI2-03](AI2-03-detailed-design.vi.md), [AI2-06](AI2-06-implementation-gap.vi.md), [AI2-07](AI2-07-full-pipeline.vi.md).  
**Must** = phạm vi yêu cầu, không tự chứng minh đã làm đủ trên mọi PDF.

## 1. Hành trình

1. Chọn PDF thân / phụ lục (hoặc hồ sơ mẫu) → nạp AI1 (thật hoặc giả trong demo).  
2. Kiểm tra bàn giao → dò cấu trúc → trích → so → đề xuất chỉ mục.  
3. Xem phát hiện hai nguồn → xác nhận / sửa lớp / từ chối.  
4. Hỏi hẹp → L0–L3 → mở đúng nút trên trang.  
5. Xuất / lưu phiên thí điểm (SQLite local). Công bố thật = BE, ngoài demo.

## 2. Yêu cầu chức năng

| ID | Yêu cầu | Chấp nhận |
|---|---|---|
| FR-H1 | Validator bàn giao: ghim, vòng đời, cấm PDF thô | Có `pdf_bytes`, lifecycle không active hoặc thiếu pin → `BLOCKED`; trang trống/thấp → `NEEDS_REVIEW` |
| FR-H2 | Định tuyến FIELD / TABLE / CLAUSE | Điều không tạo sự kiện; vẫn cắt đoạn để hỏi |
| FR-H3 | Trích trường: thô + chuẩn hóa + citation | Bí danh profile; không map từ đơn “năm/một” trong câu |
| FR-H4 | Bảng: meta + sandbox; thiếu ≠ 0; không gộp hàng OCR tách | Khớp `table_id` với nút; không lấy bảng đầu nếu lệch; lỗi sandbox → `FAILED` có issue |
| FR-H5 | So hai nguồn theo DOC-02 §5 | Không N×N; không `LEGAL_WINNER` |
| FR-H6 | Neo chữ trên đoạn nguồn | Không bịa hộp; không biến thiếu chứng thành đạt |
| FR-H7 | Chỉ mục chỉ `propose` | Nút công bố demo không đổi đóng góp |
| FR-H8 | Lớp rà: confirm / correct / reject + lý do từ chối | Candidate lạ bị từ chối; không sửa raw; extract lại → overlay cũ stale |
| FR-H9 | Hỏi: phân loại → L0 → L1 k≤8 → L2 tùy chọn → L3 trích đúng chỗ | Câu quá rộng từ chối; `Điều 3` ≠ `Điều 35` |
| FR-H10 | Công cụ chỉ danh sách trắng; sandbox cấm `import` | Phong bì auth trên mỗi lần gọi |

### FR-H11 — Boundary snapshot và table coverage

AI2 nhận `ai1.snapshot.v1` làm contract canonical. Tầng vận chuyển giữ nguyên snapshot và chuyển tiếp cho AI2; catalog edge case không phải document input. Legacy/result envelope cũ không thuộc contract mới và không dùng làm fixture canonical.

`table_coverage=NOT_PRESENT` nghĩa là AI1 đã kiểm tra và không có bảng; AI2 không tạo EvidenceIssue. `UNKNOWN`, `UNAVAILABLE` hoặc `FAILED` không được diễn giải thành “không có bảng”; table-derived fact phải chuyển `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE`.

Chi tiết đầu vào/ra từng bước: [AI2-07](AI2-07-full-pipeline.vi.md). Đã xong / giả / ngoài: [AI2-06](AI2-06-implementation-gap.vi.md).

## 3. Trạng thái

**Rà soát sự kiện/phát hiện:** `PASS` · `NEEDS_REVIEW` · `INSUFFICIENT_EVIDENCE` · `BLOCKED` · `NOT_COMPARABLE` · hỏi: `ANSWERED`.

**Việc trích:** thành công / thất bại. Thành công **không** nghĩa người đã rà xong hay không còn rủi ro.

**Lớp người:** chưa rà / đã rà / hết hạn khi có lần trích mới.

## 4. Giới hạn nhận hồ sơ (mặc định)

Một hợp đồng + tối đa 5 phụ lục khi nối sản phẩm; demo không siết cứng. AI2 chặn rõ snapshot có `ENCRYPTED`; việc nhận diện PDF hỏng/mã hóa ở intake AI1 chưa phải năng lực AI2 end-to-end. Không cắt im lặng trong handoff. Chữ viết tay, scan mờ: hạ review, không bảo đảm. Embedding/vector là capability tuỳ chọn của AI2 demo qua OpenAI-compatible NineRouter; production index có thể thay bằng adapter pgvector/worker, nhưng vector không được đi thẳng vào kết luận.

## 5. Kết quả audit edge case

| Mức | Case tiêu biểu | Cách xử lý hiện tại |
|---|---|---|
| Đã kiểm chứng | EC-003, EC-005, EC-009, EC-010, EC-015, EC-020, EC-024, EC-030, EC-035; HD gold | deterministic rule, sandbox, evidence issue, scope/currency gate, allowlist |
| Review/partial | EC-001/002, EC-004/006/007/008, EC-011..019, EC-021..023, EC-025..033, EC-038..044, EC-046, EC-051/052 | Giữ raw/citation, giới hạn context, hạ `NEEDS_REVIEW`; chưa có assembler/OCR/semantic đầy đủ |
| Blocked hoặc ngoài AI2 | EC-045 intake PDF, EC-047/049/050/055, backend ACL/cache/egress/purge | Chỉ chặn khi snapshot/handoff phát tín hiệu; phần còn lại thuộc AI1/BE/worker |

Các fixture trên được dùng để kiểm tra không crash và không claim quá mức; chỉ nhóm “đã kiểm chứng” mới được ghi là Done trong gap document. Chi tiết từng EC nằm ở [AI2-04](AI2-04-edge-case-test-matrix.vi.md) và [AI2-06](AI2-06-implementation-gap.vi.md).

## 6. Phi chức năng (AI2)

| Chủ đề | Yêu cầu |
|---|---|
| Tin cậy | PDF = dữ liệu, không phải lệnh; không filesystem / URL tùy ý cho mô hình |
| Quan sát | Ghim phiên bản trên kết quả; không dùng confidence chung làm chứng |
| Chi phí | Chỉ gọi LLM khi L0/L1 chưa đủ; thiếu khóa thì chạy deterministic |
| Quyền | Demo: một máy. Sản phẩm: BE lọc trước retrieval |

## 7. Ngoài PRD AI2

OCR lại từng trang, batch 10 hồ sơ, CSRF/session tổ chức, export CSV ghim run sản phẩm — thuộc LF DOC-03 / BE / FE. AI2 cung cấp đóng góp và trạng thái, không thay các màn đó.

Chi tiết contract AI1→AI2 nằm tại [AI1-AI2-CONTRACT](../contracts/AI1-AI2-CONTRACT.vi.md). Contract canonical là `ai1.snapshot.v1`; schema và semantic validation là gate hiện tại, còn quarantine vận hành và re-OCR chưa thuộc phase hiện tại.
