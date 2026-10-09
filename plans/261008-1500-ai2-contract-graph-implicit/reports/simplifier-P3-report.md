# Đánh giá đơn giản hóa P3

Quyết định: **RETAIN**. Giữ mã P3 tại commit `bffe37e3d0084b000d00ea6d3fbe26a56e23fa60`; chưa có thay đổi nhỏ nào đủ rõ lợi ích để áp dụng trong lượt đánh giá này. Đây là kết luận về độ rõ của mã, không thay gate review, verification hoặc kết quả đo P3/P5.

## Phạm vi và số đo

Đã đọc `CLAUDE.md` từ checkout gốc vì worktree không có file này; đối chiếu `docs/code-standards.md` trong worktree và `harness/rules/harness-contract.md`, `harness/data/output.yaml` từ checkout gốc.

Lệnh xác định file mới sửa: `git diff --name-only HEAD`. Tại đầu lượt đánh giá, chỉ có ba artifact dưới `plans/261008-1500-ai2-contract-graph-implicit/artifacts/`; không có mã P3 trong diff. Theo phạm vi mở rộng do lead chỉ định, đánh giá ba module đã commit ở P3:

| File | Dòng | Kết luận |
|---|---:|---|
| `ai-service/app/pipeline/contract_graph/pair_classifier.py` | 249 | Các guard, rejection counters và giới hạn runtime rõ ràng; giữ nguyên. |
| `ai-service/app/pipeline/contract_graph/pair_builder.py` | 142 | Luồng candidate → gate → classifier → citation giữ boundary kiểm chứng dễ đọc; giữ nguyên. |
| `evals/contract_graph/pairs/predictor.py` | 338 | Có dựng record/graph lặp lại; chưa cần thêm abstraction trong phạm vi P3 đã chốt. |

Số đo `git diff bffe37e3^ bffe37e3 --shortstat -- <ba file>`: `3 files changed, 729 insertions(+)`. Số đo `git diff HEAD --shortstat -- <ba file>` trước/sau lượt đánh giá đều rỗng: **0 files changed, 0 insertions(+), 0 deletions(-)**. Chỉ thêm báo cáo này.

## Các điểm đã cân nhắc

- `predictor.py:123` và `predictor.py:153` cùng gọi `record_from_doc`; `predictor.py:126` và `predictor.py:154` cùng dựng graph. Khi `predict_doc` gọi `candidate_set`, công việc này lặp lại. Có thể đưa phần sinh candidate nhận record/index/edges vào private helper, nhưng sẽ thêm một tầng gọi để bỏ vài lệnh dựng dữ liệu trong bộ đo. Chưa có số đo cho thấy đây là nút thắt; lợi ích hiệu năng vẫn là `[ASSUMED]`. Giữ các hàm hiện tại để caller trực tiếp của `candidate_set` vẫn dễ hiểu và tránh mở phạm vi refactor.
- Nhánh E ở `predictor.py:128` không dùng tập `excluded` đã dựng tại `predictor.py:127`. Chuyển dựng graph xuống nhánh B/C có thể tiết kiệm công việc, nhưng cũng đổi thứ tự thực thi và lỗi đối với input bất hợp lệ. Không coi đó là thay đổi bảo toàn hành vi tuyệt đối trong lượt này.
- `pair_builder.py:58` và `pair_builder.py:96` có thể dựng client hai lần trên đường qua gate. Gom lại cần đổi cách truyền client hoặc phân chia hàm gate; giữ API hiện tại khi chưa có bằng chứng chi phí đáng kể.
- `_decision` ở `pair_classifier.py:129` dùng guard và mã từ chối riêng cho từng điều kiện. Không gom các nhánh vì cần bảo toàn rejection counters. `_grounded_span` ở `pair_classifier.py:106` giữ ánh xạ chuỗi chuẩn hóa về substring gốc; không rút gọn bằng tìm kiếm trên chuỗi chuẩn hóa vì sẽ mất raw offsets.

## Kiểm tra

Lệnh từ root worktree:

```powershell
& 'ai-service/.venv/Scripts/python.exe' -m ruff check --config ai-service/pyproject.toml ai-service/app/pipeline/contract_graph/pair_classifier.py ai-service/app/pipeline/contract_graph/pair_builder.py evals/contract_graph/pairs/predictor.py
```

Kết quả **PASS**, exit `0`, `All checks passed!`. Không chạy lại pytest vì lượt này chỉ thêm báo cáo; không sửa code hoặc test. Regression suite và gate P3 thuộc lượt kiểm tra của lead/reviewer.
