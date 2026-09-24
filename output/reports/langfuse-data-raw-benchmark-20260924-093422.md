# Báo cáo benchmark OCR và Langfuse

- Thời điểm tạo (UTC): `2026-09-24T09:37:45.667425+00:00`
- Số file: **59**
- Thành công / thất bại: **59 / 0**
- Tổng số trang: **474**
- Trang có text native / trang thực tế gọi OCR: **439 / 36** (TC08 là mixed nên thuộc cả hai nhóm)
- Tổng thời gian batch: **202.820 giây**
- Tổng độ trễ xử lý riêng của 59 file: **166.814 giây**
- Độ trễ file trung bình: **2.827 giây**
- P50 / P95 / Max: **0.901 / 15.727 / 46.428 giây**
- Độ trễ Mistral generation trung bình: **3.488 giây**
- P50 / P95 / Max của Mistral generation: **2.674 / 8.155 / 8.222 giây**
- Chi phí Mistral ước tính: **$0.144000 USD**

> Langfuse xác nhận 36 generation / 36 trang OCR. Chi phí dùng đơn giá Mistral OCR 4 là $4/1.000 trang. Langfuse hiện trả `totalCost = null` vì chưa có model definition khớp alias `mistral-ocr-4`; xem cột trace để đối chiếu từng lần chạy.

| # | File | Trang | Native | Scan | Trạng thái | Độ trễ (s) | Chi phí USD | Trace |
|---:|---|---:|---:|---:|---|---:|---:|---|
| 1 | `data/raw/digital/01_Bien_ban_ghi_nho_MOU.pdf` | 4 | 4 | 0 | completed | 0.901 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/676c082950df4877dec5d3932645d4eb) |
| 2 | `data/raw/digital/03_Hop_dong_mua_ban_hang_hoa.pdf` | 8 | 8 | 0 | completed | 2.103 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/9834f5f6c4a564aef48912f7ab3f79bc) |
| 3 | `data/raw/digital/05_Hop_dong_thue_mat_bang.pdf` | 10 | 10 | 0 | completed | 2.655 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/ff578e039deba6ad0580365e616e1efb) |
| 4 | `data/raw/digital/08_Hop_dong_chuyen_nhuong_co_phan.pdf` | 6 | 6 | 0 | completed | 1.533 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/72a637a6b18db544607e41b7ced1353a) |
| 5 | `data/raw/digital/09_Hop_dong_chuyen_nhuong_phan_von_gop.pdf` | 6 | 6 | 0 | completed | 1.588 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/227957dd1efedbae9c013f89ea27d5f3) |
| 6 | `data/raw/digital/14_Hop_dong_mua_ban_hang_hoa_qua_mang.pdf` | 10 | 10 | 0 | completed | 2.588 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/8d1a5ae333f78eff1ddd3750dd8a9236) |
| 7 | `data/raw/digital/15_Hop_dong_dao_tao_nghe_giua_NLD_va_NSDLĐ.pdf` | 5 | 5 | 0 | completed | 1.267 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/82110bf251b6b1694f32caa6f13376df) |
| 8 | `data/raw/digital/17_Hop_dong_sua_chua.pdf` | 9 | 9 | 0 | completed | 2.318 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/9c2694cb38d6be437dfc6106d15265b3) |
| 9 | `data/raw/digital/18_Hop_dong_li-xang_chuyen_giao_quyen_su_dung_nhan_hieu.pdf` | 7 | 7 | 0 | completed | 1.827 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/46fe5155fa80350c2ee20cae04c55c11) |
| 10 | `data/raw/digital/19_Hop_dong_dai_ly.pdf` | 12 | 12 | 0 | completed | 3.161 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/ebab180de163ba27ad977744972c8c3c) |
| 11 | `data/raw/digital/1_ 20 MAU HOP DONG MCAC BẢN VN(1).pdf` | 186 | 186 | 0 | completed | 46.428 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/ed5e0f4082109ebb3d8cfa3e8e9bede1) |
| 12 | `data/raw/digital/20_Hop_dong_mua_ban_va_lap_dat_thiet_bi.pdf` | 8 | 8 | 0 | completed | 2.126 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/dbd24ee94398a95290e650ea99cc4539) |
| 13 | `data/raw/digital/496685149-HỢP-ĐỒNG.pdf` | 7 | 7 | 0 | completed | 1.350 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/77d942577900c50c23f652bf339c5518) |
| 14 | `data/raw/digital/BXD_1040QDBXD_26062026_PL2.Mauhopdongthitk.pdf` | 30 | 30 | 0 | completed | 7.259 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/2ffa2359b1944c82ee6d2ae4b73f624f) |
| 15 | `data/raw/digital/BXD_1040QDBXD_26062026_PL4.Mauhopdonggimst.pdf` | 30 | 30 | 0 | completed | 7.120 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/4d9072da45748cbf7e187b15e3687be6) |
| 16 | `data/raw/digital/BXD_1346-QD-BXD_03082026.pdf` | 56 | 55 | 1 | completed | 15.727 | 0.004000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/f0ec480b037c23a72e9a2fbff21f78c7) |
| 17 | `data/raw/digital/VanBanGoc_Phu luc II - TT 5-2023-TT-BNV.pdf` | 5 | 5 | 0 | completed | 1.960 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/7b49ae479a05a25865da82b0a645a806) |
| 18 | `data/raw/hard_cases/744287578-Hợp-đồng.pdf` | 11 | 11 | 0 | completed | 2.126 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/b1fceeff3ac32f59203141c66d7a245c) |
| 19 | `data/raw/hard_cases/Hop_dong_scan_bang_lien_trang_OCR_test.pdf` | 4 | 0 | 4 | completed | 9.452 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/641043bff41c7e7d46794d1211b49bc1) |
| 20 | `data/raw/hard_cases/Hop_dong_scan_stress_bang_lien_trang_khong_header.pdf` | 5 | 0 | 5 | completed | 5.626 | 0.020000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/4b05d4d29188147733c29d492a471575) |
| 21 | `data/raw/hard_cases/Hop_dong_scan_testcase_bang_dut_doan_con_dau_v2.pdf` | 4 | 0 | 4 | completed | 5.210 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/0a7985c4d81e730b1ef3c7c31f805528) |
| 22 | `data/raw/scanned_bad/739058507-Bản-Scan-Hợp-Đồng-Cong-Ty-Tnhh-Samt-Vina.pdf` | 6 | 0 | 6 | completed | 16.454 | 0.024000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/ed8626d949fffb047ce0c4547777681c) |
| 23 | `data/raw/scanned_clean/690758295-Scan-HỢP-ĐỒNG-Feddy.pdf` | 4 | 0 | 4 | completed | 9.775 | 0.016000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/b613f01e81e37d5f21b2e4784b86d8ec) |
| 24 | `data/raw/scanned_clean/736532046-Scan-0012.pdf` | 2 | 0 | 2 | completed | 4.045 | 0.008000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/9c5be135b8e1b0ff248e088c7e911042) |
| 25 | `data/raw/scanned_clean/batch_20_dossiers/dossier_01.pdf` | 1 | 1 | 0 | completed | 0.062 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/8bc2f677d6dc44a8b78fea3555af99b6) |
| 26 | `data/raw/scanned_clean/batch_20_dossiers/dossier_02.pdf` | 1 | 1 | 0 | completed | 0.082 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/b3207a4da10e288495f88dd852a2b5a7) |
| 27 | `data/raw/scanned_clean/batch_20_dossiers/dossier_03.pdf` | 1 | 1 | 0 | completed | 0.059 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/6c9d151fbeb7ecb18433beb94c9399ba) |
| 28 | `data/raw/scanned_clean/batch_20_dossiers/dossier_04.pdf` | 1 | 1 | 0 | completed | 0.060 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/5b187eb301040888a96212949fae5b44) |
| 29 | `data/raw/scanned_clean/batch_20_dossiers/dossier_05.pdf` | 1 | 1 | 0 | completed | 0.095 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/1e703282f28311f6747d8ade06f35494) |
| 30 | `data/raw/scanned_clean/batch_20_dossiers/dossier_06.pdf` | 1 | 1 | 0 | completed | 0.072 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/43dfe24ee04670aecae2e8768c35b7d1) |
| 31 | `data/raw/scanned_clean/batch_20_dossiers/dossier_07.pdf` | 1 | 1 | 0 | completed | 0.083 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/5a151b99fcc2b3651dfba72b057d2b2a) |
| 32 | `data/raw/scanned_clean/batch_20_dossiers/dossier_08.pdf` | 1 | 1 | 0 | completed | 0.075 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/bf0e0ee3ddeefdf55a757c056629d5ed) |
| 33 | `data/raw/scanned_clean/batch_20_dossiers/dossier_09.pdf` | 1 | 1 | 0 | completed | 0.060 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/1cfbee3f820a2c6eeb31c7d7caeacabc) |
| 34 | `data/raw/scanned_clean/batch_20_dossiers/dossier_10.pdf` | 1 | 1 | 0 | completed | 0.069 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/642354cadf6accb766346d189f31219e) |
| 35 | `data/raw/scanned_clean/batch_20_dossiers/dossier_11.pdf` | 1 | 1 | 0 | completed | 0.069 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/f0616114df1b6bec4d90f7b5530f0d1f) |
| 36 | `data/raw/scanned_clean/batch_20_dossiers/dossier_12.pdf` | 1 | 1 | 0 | completed | 0.072 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/627f577a58aee2082f644443ccd46fd4) |
| 37 | `data/raw/scanned_clean/batch_20_dossiers/dossier_13.pdf` | 1 | 1 | 0 | completed | 0.068 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/fc2843c0ed7226920239d17652565ab3) |
| 38 | `data/raw/scanned_clean/batch_20_dossiers/dossier_14.pdf` | 1 | 1 | 0 | completed | 0.059 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/daec02b09ee4d3cc06273ea601e50121) |
| 39 | `data/raw/scanned_clean/batch_20_dossiers/dossier_15.pdf` | 1 | 1 | 0 | completed | 0.080 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/460335ccf34678fd10760dc73f19b430) |
| 40 | `data/raw/scanned_clean/batch_20_dossiers/dossier_16.pdf` | 1 | 1 | 0 | completed | 0.054 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/bd25751b9e8aa4d7331a760dda159ab6) |
| 41 | `data/raw/scanned_clean/batch_20_dossiers/dossier_17.pdf` | 1 | 1 | 0 | completed | 0.063 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/95de7fcb375e854bba98e93eb0622a1a) |
| 42 | `data/raw/scanned_clean/batch_20_dossiers/dossier_18.pdf` | 1 | 1 | 0 | completed | 0.071 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/3f358833237deef600dfdc80531218d2) |
| 43 | `data/raw/scanned_clean/batch_20_dossiers/dossier_19.pdf` | 1 | 1 | 0 | completed | 0.063 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/c8e4977b3a1b3dd78e0cb49e8c463fb4) |
| 44 | `data/raw/scanned_clean/batch_20_dossiers/dossier_20.pdf` | 1 | 1 | 0 | completed | 0.071 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/9145e5f2926a429f068c9ba2a12f96c8) |
| 45 | `data/raw/scanned_clean/inputs/TC01_value_grounding_scan.pdf` | 1 | 0 | 1 | completed | 1.340 | 0.004000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/106e79856c793b85c30fda7b7674bce3) |
| 46 | `data/raw/scanned_clean/inputs/TC02_orphan_total_vector.pdf` | 1 | 1 | 0 | completed | 0.091 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/5787b8d3bcba2e0a0e847baf8809193b) |
| 47 | `data/raw/scanned_clean/inputs/TC03_bbox_provenance_vector.pdf` | 1 | 1 | 0 | completed | 0.093 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/fb48aa837b47689604e2f5d3741ef86f) |
| 48 | `data/raw/scanned_clean/inputs/TC04_rotation_and_skew_scan.pdf` | 2 | 0 | 2 | completed | 2.530 | 0.008000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/5dddb15c9d72eee4cfff6e786364180d) |
| 49 | `data/raw/scanned_clean/inputs/TC05_unreadable_annex_scan.pdf` | 2 | 0 | 2 | completed | 1.855 | 0.008000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/04eaa2baee6ab4b675b9b0e589055a4b) |
| 50 | `data/raw/scanned_clean/inputs/TC06A_contract_master.pdf` | 1 | 1 | 0 | completed | 0.080 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/c9ccce42d16395b76e9ac719a4e6a690) |
| 51 | `data/raw/scanned_clean/inputs/TC06B_annex_agree.pdf` | 1 | 1 | 0 | completed | 0.064 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/58557890709e1c82ad29b4b734229efc) |
| 52 | `data/raw/scanned_clean/inputs/TC06C_annex_conflict.pdf` | 1 | 1 | 0 | completed | 0.066 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/d623d1fd6d9833a3774b9b86b92283f1) |
| 53 | `data/raw/scanned_clean/inputs/TC06D_annex_unreadable.pdf` | 1 | 0 | 1 | completed | 1.345 | 0.004000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/3d98d197482a2505d1523cf45e6a7a1c) |
| 54 | `data/raw/scanned_clean/inputs/TC07_table_continuity_no_header_no_stt.pdf` | 3 | 0 | 3 | completed | 1.347 | 0.012000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/82048d2dfc6133a47784e144cb0061f8) |
| 55 | `data/raw/scanned_clean/inputs/TC08_mixed_text_scan_overlay.pdf` | 1 | 1 | 1 | completed | 1.439 | 0.004000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/3fd6b60f08e069c34b2d2a713a1b3889) |
| 56 | `data/raw/scanned_clean/inputs/TC09_duplicate_columns.pdf` | 1 | 1 | 0 | completed | 0.074 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/d38396c434c2466d157fd6e8f5f57e58) |
| 57 | `data/raw/scanned_clean/inputs/TC10_citation_normalization.pdf` | 1 | 1 | 0 | completed | 0.086 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/dca5eea4fcf0d1a482ac877e074606ce) |
| 58 | `data/raw/scanned_clean/inputs/TC11_confidence_repeatability.pdf` | 1 | 1 | 0 | completed | 0.066 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/ca7fef2cbaa463939992200e44b88c23) |
| 59 | `data/raw/scanned_clean/Mentor_Test_Case_Summary.pdf` | 1 | 1 | 0 | completed | 0.352 | 0.000000 | [mở](https://us.cloud.langfuse.com/project/cmudva300014fad0c07vqhqca/traces/04b43a0510acc2ad75e87c9b0db23123) |
