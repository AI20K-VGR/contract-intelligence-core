# Kiểm tra P4 tại main

- Code + test: commit `976521eb`; tài liệu và DEC consent: `599f3677`.
- Full ai-service trên snapshot đã sửa F1/F2: **13 failed, 1523 passed, 9 skipped**, 255,99 giây; log `tmp/p4-full-final.log`. Đã so sánh tập ID của toàn bộ test lỗi với `tmp/p3-full-final.log`: đúng 13 và khớp hoàn toàn. Không có regression mới. Các log PowerShell có BOM UTF-16, đã decode theo BOM khi đối chiếu.
- Eval: **161 passed**, 7,26 giây; `tmp/p4-eval.log`.
- Ruff toàn bộ 19 file Python P4, chạy từ `ai-service/`: PASS. Lượt thử từ repo root cho kết quả import grouping khác do cách xác định first-party; không sửa code theo lượt sai cwd đó.
- `git diff --check`: PASS. Secret scan typed của `hs-run git next` sạch; scan không loại docs/test/fixture có 161 dòng keyword (tên biến và test), không có credential thực theo pattern. `.env` và state ngoài Git không được stage.
- Review độc lập P4: PASS sau sửa log lộ SQL parameters và citation cắt 240 ký tự; 75 focused + 19 golden + 15 Postgres PASS, Ruff sạch. Chi tiết `reviewer-P4-report.md`.
- Simplification: RETAIN, không thêm abstraction; `simplifier-P4-report.md`.
- Golden graph-on 69 case giữ SHA `64ea9e599f9c8f5c1b1fd1ea376287ec772315c08f3bc46f5a17488a631eba74`, được main tái capture độc lập trên detached P3. Flag-off SHA `091421c523715af741bfaca7cad7125a381d6063e0471a7e58d063bd7f64cac2` không đổi. Capture tạm flag-off đã chuyển vào `tmp/p4-flag-off-capture.json`.
- Lượt full trước hai sửa chữa đã được dừng, không dùng làm bằng chứng PASS. Lượt final mới nhất đã hoàn tất.
- `verification-P4.json` được viết bởi `hs-run cook verify`; không ghi tay receipt. CLI không có spawn attestation cho session shell này; báo cáo delegation là lời xác nhận, các lời gọi subagent và probe độc lập nằm trong phiên làm việc.
- DEC `DEC-dungskbg2004-1` được ghi bằng `decision_register.py` theo Q1 đã được người dùng duyệt. Cờ pairs vẫn mặc định tắt.

13 lỗi nền gồm 7 test OCR thiếu `mistralai`, 5 test thiếu `HD-TONG-HOP.sample.pdf`, và 1 test `test_p0_contract_baseline`; không sửa dependency/fixture ngoài phạm vi để che các lỗi này.
