# Devils-advocate review: AI2 proposal

## Trạng thái

Đây là checkpoint findings sớm. Review chỉ đọc; không sửa production code, test, contract hoặc artifact vận hành.

## Phạm vi đã xác định

- Proposal chính: `tmp/plan-ai2-full-20260923.txt`
- Các điểm cần kiểm tra theo yêu cầu: synthetic ground truth, parity skip, mutation coverage mismatch, mirror-induced PASS, scorer/P0 loopholes, và ý nghĩa của maturity 100%.
- Bằng chứng sẽ chỉ dùng anchor có thể truy lại bằng file:line, test/lệnh tái hiện, hoặc artifact/ID hiện có.

## Giả thuyết phản biện đang kiểm chứng

- Synthetic ground truth có thể xác nhận pipeline tự nhất quán nhưng không chứng minh đại diện cho tài liệu/biến thiên production.
- Parity skip có thể biến phần chưa đối chứng thành vùng không chấm điểm, làm PASS không phản ánh coverage thực.
- Mutation score có thể đo khả năng bắt các mutant dễ/được chọn, không đo mismatch giữa taxonomy mutation và failure modes AI2.
- Mirror/replay có thể tái tạo cùng một lỗi hoặc cùng một giả định ở cả expected và actual, tạo ảo giác PASS.
- Scorer/P0 có thể có đường thoát: field không được chấm, thiếu-vs-null bị quy đồng, severity/P0 không được bắc cầu, hoặc fail bị triệt tiêu bởi skip.
- “Maturity 100%” có thể chỉ là độ hoàn tất của rubric nội bộ, không phải bằng chứng production readiness.

Các mục trên chưa phải verdict cuối; sẽ được nâng thành finding chỉ khi có bằng chứng cụ thể.

