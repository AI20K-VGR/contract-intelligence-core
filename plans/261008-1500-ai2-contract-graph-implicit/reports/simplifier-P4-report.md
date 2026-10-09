# Đánh giá đơn giản hóa P4

Quyết định: **RETAIN**. Các nhánh mới giữ rõ điều kiện chạy, trạng thái thất bại và chính sách thay dữ liệu. Chưa có đề xuất đơn giản hóa cần developer xử lý trước commit. Kết luận này chỉ đánh giá độ rõ của mã; review và regression gate do lead/reviewer xác nhận riêng.

## Phạm vi và số đo

Đã chạy `git diff --name-only HEAD` để xác định mã vừa sửa. Lead chỉ định phạm vi P4 so với `bffe37e3`; đối chiếu cả các file mới chưa tracked từ `git status --short`. Đã đọc chuẩn `docs/code-standards.md`, phần kiến trúc liên quan trong `docs/system-architecture.md`, và diff adapter, record, DB table, capture script để hiểu caller của bốn module trọng tâm.

| File trọng tâm | Hiện trạng tại đánh giá | Quyết định |
|---|---|---|
| `ai-service/app/pipeline/contract_graph/pair_projection.py` | File mới, 135 dòng | Giữ guards, kiểm citation, dedup và counters riêng. |
| `ai-service/app/tools/pair_relation_store.py` | File mới, 51 dòng | Giữ row serializer và delete/insert trong transaction caller. |
| `ai-service/app/pipeline/idp.py` | Thêm 42 dòng | Giữ block điều phối trong `run_idp` và điều kiện thay quan hệ. |
| `ai-service/app/tools/jobs.py` | Thêm 15 dòng | Giữ savepoint riêng cho quan hệ cặp. |

`git diff bffe37e3 --shortstat -- <bốn file>` trước/sau lượt đánh giá: `2 files changed, 57 insertions(+)`; lệnh này không tính hai file mới chưa tracked. Tính thêm 135 + 51 dòng của hai file mới: **4 files, 243 insertions(+), 0 deletions(-)** trong phạm vi trọng tâm tại snapshot này. Lượt simplifier sửa **0 dòng code** và chỉ thêm báo cáo này.

## Các điểm đã cân nhắc

- `pair_projection.py:62` tái dùng `_candidate_pair` để chuẩn hóa cặp có evidence. Guard tại `pair_projection.py:68`, `pair_projection.py:72` và `pair_projection.py:75` giữ riêng nhãn, dedup và cap. Đổi sang lọc/gom một comprehension sẽ làm khó quan sát counters và thứ tự xử lý; không rút gọn.
- Vòng kiểm hai citation trong `pair_conflict_candidates` dùng `break` rồi kiểm độ dài; cấu trúc này ngắn, không thêm helper chỉ để kiểm đúng hai node. Giữ `_scope` ba nhánh thay vì tạo bảng dispatch hoặc suy diễn scope từ enum/string.
- `pair_projection.py:120` chọn `active` theo status, sau đó cùng một dictionary sinh đủ coverage cho thành công/thất bại. Các giá trị zero/None khi không active là behavior hợp đồng; không loại bỏ các field hoặc nhập các nhánh FAILED và SKIPPED.
- `pair_relation_store.py:13` đã tái dùng utility serialization/sanitization sẵn có. `_clean` trên phần tử `candidate_sources` ở `pair_relation_store.py:28` khác với `_clean` trên chuỗi JSON hoàn chỉnh ở `pair_relation_store.py:36`: JSON encoding có thể đổi NUL thành escape. Giữ cả hai bước để không mất xử lý trước serialization.
- `pair_relation_store.py:39` có cùng hình thức delete/insert với edge store, nhưng chỉ vài lệnh và khác model/table/serializer. Một generic store sẽ thêm table/serializer/callback parameters để gom hai đoạn ngắn; không tạo abstraction mới.
- `idp.py:282` đọc cờ một lần, liên kết với cờ graph. Block ở `idp.py:364` được đặt sau issue/context hiện có. Tách helper chỉ để giảm nesting cần truyền nhiều trạng thái mutable (`record`, `runtime`, `graph`, `candidates`, `issues`, coverage); giữ block để dễ kiểm thứ tự và side effects.
- Điều kiện ở `idp.py:429` phân biệt ít nhất một batch đã hoàn tất với thu hồi consent. Hai trường hợp này có chủ đích khác lỗi provider/cờ tắt. Không thay bằng điều kiện chung kiểu `pair_result is not None`, vì sẽ đổi chính sách giữ/xóa dữ liệu đã lưu.
- `jobs.py:581` và `jobs.py:597` có hai wrapper savepoint tương tự. Chúng ngắn và giữ rõ module store, tên log và tập quan hệ của từng luồng. Gom thành helper nhận callback sẽ thêm tầng gọi và mở phạm vi sang luồng 1. Giữ điều kiện job mới nhất/worker fence trong caller và savepoint riêng của mỗi enrichment.

## Kiểm tra

Đã chạy từ root worktree:

```powershell
& 'ai-service/.venv/Scripts/python.exe' -m ruff check --config ai-service/pyproject.toml ai-service/app/pipeline/contract_graph/pair_projection.py ai-service/app/tools/pair_relation_store.py ai-service/app/pipeline/idp.py ai-service/app/tools/jobs.py
```

Kết quả **PASS**, exit `0`, `All checks passed!`. Trong lượt đánh giá, tác vụ khác bỏ `exc_info=True` ở log lỗi pair store trong `jobs.py:608`; đã đọc lại đoạn này và chạy lại Ruff với kết quả **PASS**. Số dòng diff vẫn như trên; không có sửa code từ simplifier. Không chạy lại pytest vì lượt này chỉ thêm báo cáo; main đang chạy full suite và reviewer kiểm P4 riêng. Không tạo commit, receipt hoặc sửa gate artifact.
