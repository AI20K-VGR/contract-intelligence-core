# Nghiên cứu AI2 Facts/Findings

Ngày: 2026-09-25  
Phạm vi: read path của AI2 trong backend và màn hình Facts/Findings trong frontend.

## Câu hỏi trung tâm

Vì sao AI2 đã xử lý hồ sơ nhưng màn hình Facts/Findings vẫn cho cảm giác chưa hoàn thiện, và cần thay đổi ở đâu để người dùng nhìn thấy đúng trạng thái evidence/citation?

## Bằng chứng đã kiểm tra

- `frontend/src/api/analysis.ts:174-194` chỉ cung cấp hai lời gọi `listDossierFacts` và `listDossierFindings` cho màn hình phân tích.
- `frontend/src/pages/DossierReviewPage.tsx:364-395` chỉ tải facts/findings khi mở tab risk; `frontend/src/pages/DossierReviewPage.tsx:736-739` mới hiển thị `ContextFindingsPanel` sau một lần query.
- `frontend/src/api/ai2.ts:46-51,222-231` đã có model cho `contextFindings`, `evidenceIssues`, `coverage` và `events`, nhưng màn hình phân tích mới chưa nối các trường này.
- `backend/src/contract_intelligence/shared/ai/persistence.py:102-190` đã tính `completeness_state`, `reason_code`, counts, coverage và evidence issues.
- `backend/src/contract_intelligence/shared/ai/persistence.py:1000-1027` đã có `load_ai2_read_model` để đọc lại projection sau restart.
- `backend/src/contract_intelligence/extraction/infrastructure/persistence/orm.py:45-60` lưu các trường trạng thái AI2 trong `pipeline_run`.

Với hồ sơ `dos_01M3BEVPZKKGXVB9RAC2HFA63E`, dữ liệu runtime/database đã quan sát được:

```text
pipeline_run: succeeded / AI2 SUCCEEDED / NEEDS_REVIEW / NEEDS_REVIEW
output_counts: chunks=241, citations=108, facts=1, findings=0,
               context_findings=5, events=153, evidence_issues=5
facts table: 1
findings table: 0
citations table: 1
```

Kết luận từ bằng chứng: AI2 không “không trả kết quả”. Projection có nhiều output, nhưng UI chỉ hiển thị hai bảng đã persist thành fact/finding. `findings=0` cũng có thể hợp lệ khi hồ sơ chỉ có một tài liệu và không có cặp tài liệu để so sánh; UI cần nói rõ lý do thay vì dùng empty state chung.

## Các phương án

1. **Chỉ sửa UI**: hiển thị thêm câu giải thích và dữ liệu đã có trong facts/findings. Phạm vi nhỏ nhưng không đọc được trạng thái canonical của pipeline, coverage và evidence issues sau restart.
2. **Bổ sung endpoint read model AI2 + UI**: đọc projection mới nhất theo dossier, trả trạng thái, counts, coverage, context findings và evidence issues; UI hiển thị các phần này cùng facts/findings. Đây là phương án được chọn vì dùng đúng dữ liệu backend đã có và không kích hoạt query phụ.
3. **Tái sử dụng endpoint query**: chạy query để lấy context findings. Không chọn vì query là hành động mới, không phản ánh chính xác lần phân tích canonical và có thể quay lại lỗi snapshot/citation.

## Quyết định

Chọn phương án 2. Giữ nguyên AI1/Mistral và không tự sửa nội dung OCR pháp lý. UI sẽ hiển thị quote/citation nguyên bản, trạng thái evidence rõ ràng, và phân biệt `0 findings` hợp lệ với trạng thái chưa đủ dữ liệu.

## Rủi ro và kiểm tra sau triển khai

- Không trả toàn bộ events/AI2 payload thô trong read endpoint để tránh response lớn; chỉ trả các trường phục vụ phân tích.
- Nếu chưa có AI2 projection, endpoint phải trả trạng thái `NOT_AVAILABLE` thay vì làm hỏng toàn bộ màn hình.
- Kiểm tra build, test frontend và kiểm tra import/type backend trong container.
