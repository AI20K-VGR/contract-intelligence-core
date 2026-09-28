# Citation/BBox highlight lệch vị trí — Debug Report

## Executive Summary

- **Issue:** Vùng highlight/citation không trùng vị trí trên hợp đồng.
- **Impact:** Người review có thể nhìn nhầm vùng evidence khi mở citation từ Facts/Findings hoặc search.
- **Root cause:** `CitationPane` vẽ bbox chuẩn hóa của ảnh OCR AI1 lên PDF gốc qua PDF.js; hai nguồn có thể khác crop/rotation/kích thước nội tại.
- **Status:** Đã sửa và kiểm thử.
- **Next step:** Không cần chạy lại OCR; mở lại citation trên UI để xác nhận vùng highlight.

## Evidence

1. `frontend/src/components/CitationPane.tsx` trước sửa gọi `loadDocumentPdf()` và render PDF.js canvas, sau đó đặt bbox theo phần trăm trên canvas.
2. `frontend/src/api/structure.ts:290-331` có endpoint `loadPagePreview()` trả ảnh preview của đúng trang AI1, nhưng trước sửa không được dùng bởi `CitationPane`.
3. DB hồ sơ `dos_01M3BEVPZKKGXVB9RAC2HFA63E` cho thấy page là `kind=scanned`, có `preview_blob_uri=storage://ai1/.../page-003.png`; citation có bbox chuẩn hóa `[0.065296..., 0.189397..., 0.905078..., 0.291150...]`.
4. Kiểm tra DB cho toàn bộ dữ liệu hiện có: OCR bbox và citation segment bbox đều nằm trong hệ 0..1; page mẫu có `rotation=0`. Vì vậy nguyên nhân chính không phải phép chia bbox hoặc xoay trục của dữ liệu mẫu.
5. Regression test `frontend/tests/citation-pane-source.test.tsx` đã chạy **RED** trước sửa vì component không khai báo nguồn preview, sau sửa chạy **GREEN**.

## Root cause chain

`AI1 OCR` tạo bbox theo ảnh trang preview → `CitationPane` nhận bbox 0..1 → `CitationPane` lại rasterize PDF gốc bằng PDF.js → PDF gốc và ảnh OCR có thể không cùng pixel/crop/rotation frame → CSS overlay đúng theo frame canvas nhưng frame không trùng nguồn bbox → highlight lệch.

## Fix

`CitationPane` hiện tải `loadPagePreview(documentId, pageNo)`, tạo object URL cho ảnh preview AI1, rồi đặt overlay lên chính ảnh đó. Luồng này cũng loại bỏ PDF.js worker khỏi citation viewer.

## Verification

- Regression RED → GREEN: đạt.
- Frontend suite: `13` test files, `25` tests passed.
- Production build: đạt.
- ESLint: `0` errors, `9` warning cũ ở file khác/kiểm tra hook đã tồn tại.
- Visual verification: bỏ qua vì phiên này không có browser bridge khả dụng; đã kiểm tra bằng regression test và dữ liệu DB thực tế.
