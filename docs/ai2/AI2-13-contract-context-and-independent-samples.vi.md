# AI2 — Contract Context v1 và ranh giới hai mẫu OCR-lab

## Kết luận về hai file mẫu

Hai file:

- `ocr-run-20260922-093747-doc-001.json`: một hợp đồng mua bán hàng hóa độc lập.
- `ocr-run-20260922-095540-doc-002.json`: một hợp đồng cung cấp thiết bị/dịch vụ độc lập; bên trong cùng file có `PHỤ LỤC 01` ở trang 2–4.

Hai file không phải thân hợp đồng và phụ lục của cùng một hồ sơ. AI2 chạy chúng ở `relation_policy=INDEPENDENT`, tạo scope xử lý riêng cho từng `document_id`, và luôn để `cross_document_findings=[]`. Không được dùng `dossier_id` trùng nhau để suy ra chúng có quan hệ pháp lý.

## Kiểm kê handoff thực tế [OBSERVED 2026-09-23]

`doc-001` là `TEXT_LAYER` 8 trang, có 69 root nodes và 1 table nằm trong
`pages[*].tables`; `doc-002` là `SCANNED_OCR` 4 trang, có 7 root nodes và 3
tables nằm trong `pages[*].tables`. `doc-002` có 2 record trong
`table_continuity`, trong đó có quyết định `SPLIT` theo heading mới; cell
geometry có thể là `CLAIMED` dù table geometry là `MEASURED`.

Vì vậy context inventory phải đọc table theo page/row/cell topology và giữ
continuity như evidence logic. Không được suy ra “không có text” từ
`word_count=0` của `SCANNED_OCR`, và không được dùng root `tables` làm
fallback để bỏ qua table thật.

Replay hiện tại cho kết quả batch `NEEDS_REVIEW`, `batch_issues=0`,
`cross_document_findings=[]`; do đó các con số facts/events/context/evidence
issues trong report là evidence quan sát, không phải cam kết accuracy hay
phê duyệt pháp lý.

## Context inventory

Mỗi contribution của AI2 có thêm `contract_context` với:

- `parts`: phần `BODY` và các `ANNEX` được nhận diện từ heading đầu dòng `PHỤ LỤC <n>` và phạm vi trang liên tục;
- `PART_LINK`: tham chiếu rõ giữa phụ lục và hợp đồng trong cùng snapshot;
- `AMENDMENT_SIGNAL`: ngôn ngữ sửa đổi, bổ sung, thay thế hoặc điều chỉnh; chỉ là tín hiệu cần review;
- `CONTEXT_CONFLICT`: chênh lệch giữa các nguồn trong cùng hợp đồng sau khi đã có evidence;
- `CONTEXT_GAP`: phụ lục được nhận diện nhưng chưa thấy căn cứ gắn rõ với thân hợp đồng.

Context không chọn “văn bản thắng”, không tự kết luận hiệu lực, và không thay thế review pháp lý. Mọi finding đều giữ citation và trạng thái review.

Contribution cũng có `events`: các tín hiệu như ký kết, phạm vi, giá, thanh toán, giao hàng, nghiệm thu, bảo hành, khiếu nại, thông báo, chấm dứt, tranh chấp và sửa đổi. Event chỉ là trích xuất có nguồn; ngày/hiệu lực chưa rõ vẫn giữ `NEEDS_REVIEW`.

## Luồng gọi package

```python
from app.ai2.v1 import process_files

result = process_files([
    r"C:\Users\dungs\Downloads\ocr-run-20260922-093747-doc-001.json",
    r"C:\Users\dungs\Downloads\ocr-run-20260922-095540-doc-002.json",
])
```

Đây là API package v1 (`vsf-ai2` `1.0.0`, input `ai1.snapshot.v1/ocr-lab`). Khi truyền nhiều file độc lập, hãy đọc `documents[*].meta.effective_dossier_id` và `documents[*].job.contribution.contract_context`; không đọc `cross_document_findings` như một kết luận so sánh pháp lý.

Nếu BE đã có JSON trong memory, gọi `process_payloads_full(payloads)` để chạy đầy đủ adapter → validation → extraction → context → review. Hàm `process_payloads` cũ chỉ giữ compatibility adapter và trả `SnapshotAdapterResult`.

## Cổng kiểm thử bắt buộc

1. Kiểm tra schema, digest, page/node/table provenance của từng snapshot.
2. Kiểm tra context parts và link body–annex trong từng snapshot.
3. Kiểm tra không có cross-document relation khi policy là `INDEPENDENT`.
4. Với chênh giá, thời hạn, điều khoản hoặc phiên bản phụ lục: trả về evidence + `NEEDS_REVIEW`, không chọn bên thắng.
5. Chạy deterministic tests, replay hai file thật, sau đó mới chạy live LLM/e2e.

## Kiểm tra bổ sung: events, candidates, findings và hỏi đáp

AI2 hiện phân biệt rõ ba lớp kết quả:

- `events`: tín hiệu sự kiện/nghĩa vụ được trích trực tiếp từ clause hoặc node, gồm `event_type`, actor, trigger, date signal, `source_node_id` và citation. Event không tự kết luận hiệu lực pháp lý.
- `findings`: candidate so sánh chỉ được tạo khi có đủ hai evidence có cùng item/scope; nếu chưa đủ thì không tạo finding giả. Các tín hiệu context như `PART_LINK`, `CONTEXT_GAP`, `AMENDMENT_SIGNAL` được xuất riêng ở `context_findings` và vẫn có citation.
- `evidence_issues`: thiếu dữ liệu, citation không xác minh được, table geometry chưa chắc chắn hoặc quan hệ không resolve được. `n_findings` trong coverage là tổng candidate findings và context findings; `n_candidate_findings` và `n_context_findings` được tách riêng.

Với hai mẫu hiện tại, AI2 phải cho kết quả độc lập: hợp đồng `doc-001` không có phụ lục embedded được nhận diện; `doc-002` có `Phụ lục 01` ở trang 2–4, có `PART_LINK`, các event thanh toán/giao hàng/nghiệm thu/bảo hành và bảng liên trang. Không được dùng `dossier_id` giống nhau để tạo candidate giữa hai hợp đồng.

Các câu hỏi regression đã thêm gồm: đếm số bên, lấy hồ sơ Bên A/B, inventory phụ lục, đọc Phụ lục 01 và hỏi thời hạn. Party card chỉ trả tên/MST khi chúng xuất hiện trong evidence; nếu chỉ có role mention thì trả `NEEDS_REVIEW`, không suy đoán tên.
