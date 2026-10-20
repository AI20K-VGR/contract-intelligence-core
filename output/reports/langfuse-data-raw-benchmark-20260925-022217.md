# Báo cáo benchmark OCR và Langfuse

- Thời điểm tạo (UTC): `2026-09-25T02:24:08.928003+00:00`
- Số file: **16**
- Thành công / thất bại: **16 / 0**
- Tổng số trang: **85**
- Trang có text native / trang cần OCR: **1 / 84**
- Tổng thời gian tuần tự: **105.492 giây**
- Độ trễ file trung bình: **6.593 giây**
- P50 / P95 / Max: **5.432 / 20.136 / 20.136 giây**
- Chi phí Mistral ước tính: **$0.336000 USD**

> Chi phí dùng đơn giá Mistral OCR 4 là $4/1.000 trang. Langfuse hiện chưa suy luận được cost cho alias `mistral-ocr-4`; xem cột trace để đối chiếu từng lần chạy.

| # | File | Trang | Native | Scan | Trạng thái | Độ trễ (s) | Chi phí USD | Trace |
|---:|---|---:|---:|---:|---|---:|---:|---|
| 1 | `data/raw_scanned_only/690758295-Scan-HỢP-ĐỒNG-Feddy.pdf` | 4 | 0 | 4 | completed | 7.261 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/1f95f4cf1d653aaf71f7b8b527d3edf3) |
| 2 | `data/raw_scanned_only/736532046-Scan-0012.pdf` | 2 | 0 | 2 | completed | 3.291 | 0.008000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/0c74181e77372d9a961103499fbeb6de) |
| 3 | `data/raw_scanned_only/739058507-Bản-Scan-Hợp-Đồng-Cong-Ty-Tnhh-Samt-Vina.pdf` | 6 | 0 | 6 | completed | 8.772 | 0.024000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/7e54183f132a3224f5111c9feef39865) |
| 4 | `data/raw_scanned_only/HD01_khong_bang_nhieu_chu_scan.pdf` | 3 | 0 | 3 | completed | 5.745 | 0.012000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/4be4d8a6e213f9da5113fdc6608dbc4b) |
| 5 | `data/raw_scanned_only/HD02_co_bang_phu_luc_lien_trang_scan.pdf` | 4 | 0 | 4 | completed | 6.088 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/8d606d2fe9442382c4ab5d90a2290e56) |
| 6 | `data/raw_scanned_only/HD03_co_phu_luc_khong_bang_scan.pdf` | 4 | 0 | 4 | completed | 5.432 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/45d2fa3b8f8d4a635a6ffb1c580c963d) |
| 7 | `data/raw_scanned_only/HD04_bi_watermark_scan.pdf` | 4 | 0 | 4 | completed | 6.615 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/68498b6ef64ae320790c6c99a4e8efac) |
| 8 | `data/raw_scanned_only/HD05_bang_khong_STT_khong_header_scan.pdf` | 3 | 0 | 3 | completed | 3.526 | 0.012000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/a3870d96fe59fdcfab4e081d3730d03e) |
| 9 | `data/raw_scanned_only/HD10_case_kho_tong_hop_scan.pdf` | 3 | 0 | 3 | completed | 5.030 | 0.012000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/de3ca5303298a6312d6907c2a5a0767a) |
| 10 | `data/raw_scanned_only/Hop_dong_dich_vu_12_trang_scan.pdf` | 12 | 0 | 12 | completed | 11.670 | 0.048000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/00f86953b14cd68b7dd68b36a9abf340) |
| 11 | `data/raw_scanned_only/Hop_dong_kinh_te_20_trang_scan.pdf` | 20 | 0 | 20 | completed | 20.136 | 0.080000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/8d0a1808cd85146d457be6d5313e651a) |
| 12 | `data/raw_scanned_only/Hop_dong_scan_bang_lien_trang_OCR_test.pdf` | 4 | 0 | 4 | completed | 5.228 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/6509521b0f62ae2a9612ec6ac20ccacc) |
| 13 | `data/raw_scanned_only/Hop_dong_scan_cover_test_full.pdf` | 6 | 0 | 6 | completed | 7.342 | 0.024000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/90831ead0c71e2c4a4ef711f4f3c80e5) |
| 14 | `data/raw_scanned_only/Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf` | 5 | 0 | 5 | completed | 5.035 | 0.020000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/fc87fe4af8930462f5949a1f4cfb6248) |
| 15 | `data/raw_scanned_only/Hop_dong_scan_testcase_bang_dut_doan_con_dau_v2.pdf` | 4 | 0 | 4 | completed | 4.131 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/0006d33a8a873cc34d68d7a9ad270a5b) |
| 16 | `data/raw_scanned_only/Mentor_Test_Case_Summary.pdf` | 1 | 1 | 0 | completed | 0.190 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/52bf913d5232ccfa7cb79bc197d04cd3) |
