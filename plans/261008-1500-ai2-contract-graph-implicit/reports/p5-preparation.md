# Chuẩn bị P5 trước khi gọi held-out

Đây là snapshot tiền chạy; các lần gọi live và blocker quota sau đó được ghi tại
`reports/p5-bakeoff-preflight.json` và `reports/l2-p5-bakeoff.{json,md}`.

Chỉ đọc dữ liệu đã đóng băng qua `manifest.read_split`; chưa gọi classifier trên held-out.

- Held-out: 14 văn bản. Sinh lại ứng viên bằng code P3: B = 165, C = 174, E = 655 cặp duy nhất trong pool ∪ S4; E tối đa 98 cặp/văn bản, dưới trần 300.
- Dev C: 38 ứng viên, 10 dự đoán GENERAL_SPECIFIC, 1 DUPLICATE, 0 CONFLICT, 0 REFERENCE. Dự kiến trên 174 ứng viên C: lần lượt 45,79; 4,58; 0; 0. Không phải mọi nhãn đều dưới MIN_N/2 = 30, nên kế hoạch yêu cầu giữ E.
- C có tổng 174 ứng viên/trial, nhỏ hơn 4 × MIN_N = 240. Mỗi cặp chỉ nhận một nhãn, nên không thể đồng thời đạt n ≥ 60 cho cả bốn nhãn trong một trial hiện tại. Bake-off vẫn đo chất lượng, coverage và khác biệt giữa các biến thể; cổng có thể ưu tiên veto false DUPLICATE trước verdict thiếu n. Giữ số trial và điều kiện chọn E đã được duyệt.
- Tổng token dev: 40.968 prompt + 3.140 completion = 44.108; trung bình 6.301,14 token/văn bản. Ước tính C mỗi trial = trung bình × 14 × 1,5 = 132.324 token. E nhân tỷ lệ ứng viên 655/174 ≈ 498.116 token. Đây là ước tính ngân sách, không phải token đã đo của held-out.
- Độ trễ dev p50 = 6,91961 giây/văn bản. C ước tính p50 × 14 × 1,5 = 145,31 giây/trial; E nhân 655/174 ≈ 547,00 giây/trial. Cả hai dưới trần preflight 600 giây; độ trễ thực có thể vượt ước tính và phải được ghi `over_budget`.
- Trước trial đầu tiên: nhập quyết định approve của chính người dùng, kiểm selection SHA, ghi quyết định JSONL ngoài Git, commit khối `heldout_review` trong manifest. Không đổi prompt, lexicon hoặc K giữa trial.
- Thứ tự đã định: C1, B1, E1, C2, B2, E2. Claude phục vụ thực phải thuộc họ anthropic ở mọi lời gọi.
- Cổng dùng precision bảo thủ, trial tệ hơn; nhập ngưỡng từ `review_policy.py`. Scoreboard phải giữ cả biến thể thua; McNemar dùng cùng gold-positive đã duyệt. Khuyến nghị không tự bật cờ runtime.
- Đã đọc CLI `wilson.py`: `--clusters` nhận path JSON có `clusters: [{k,n},…]`, không nhận số văn bản trực tiếp. `--min-n T` tính trường hợp tất cả dự đoán đúng (`min_n_all_pass`), không tự tính cỡ mẫu theo tỷ lệ quan sát. Runner cần phân biệt cỡ mẫu tốt nhất với ước tính giữ tỷ lệ hiện tại; tỷ lệ không vượt ngưỡng không có cỡ mẫu hữu hạn chỉ bằng tăng n. Không được gắn tên “theo tỷ lệ quan sát” cho kết quả all-pass.

Nguồn: phase-5-bakeoff-rerun.md; l2-p3-classifier-dev.json; bộ dữ liệu ngoài Git đã khớp manifest; các hàm `predictor.candidate_set` hiện tại. Preflight chính thức và dry-run metric còn phải chạy sau khi P4 và runner P5 hoàn tất.
