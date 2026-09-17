# Web workspace

React + TypeScript + Vite. Dùng backend tại `http://127.0.0.1:8001` qua dev proxy. Cổng 8000 dành cho OCR lab độc lập trong `ai-service/`; trỏ nhầm backend đó sẽ trả HTTP 404 cho `/api/v1/...`. Docker vẫn dùng cổng nội bộ 8000 qua Nginx.

```powershell
npm ci
npm run dev
npm run build
```

Chức năng: upload contract + nhiều appendix, poll job, facts/findings, xem PNG với line bbox, review confirm/correct/reject/needs-more-evidence, lịch sử và approval. Không có màn hình đăng nhập — backend không yêu cầu xác thực, chỉ dành cho chạy local một người vận hành.

UI có chọn Machine/Effective để đối chiếu kết quả gốc với giá trị đã sửa. Correction tạo revision và mở lại review finding phụ thuộc cùng completeness trước approval. Chưa có chỉnh bbox, tạo batch hoặc hiệu chỉnh cấu trúc bảng. Các endpoint batch có trong Swagger. Bản Docker phục vụ static build bằng Nginx và proxy cùng origin tới API.
