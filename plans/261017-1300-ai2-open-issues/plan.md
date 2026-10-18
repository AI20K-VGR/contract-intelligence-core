# AI2: xử lý các issue đang mở (#124, #113, #116, #121, #106)

## Quy tắc môi trường
- **Production:** OpenAI key thật, `gpt-5.5` (embedding `text-embedding-3-small`). Mọi cấu hình nằm ở `deploy/.env.prod`; người vận hành sửa, không commit key.
- **Local:** router `http://host.docker.internal:20128/v1` với key local, `cx/gpt-5.6-luna` cho mọi lần chạy live, kể cả gate. Không gọi OpenAI từ local nếu người dùng chưa đồng ý. Router không có embedding nên vector tắt ở local.
- **Hệ quả:** số đo trên luna chỉ là ước lượng cho production. Phần nào phụ thuộc hành vi riêng của gpt-5.5 (reasoning, tham số API) thì chỉ được xác nhận trên staging/production, do người dùng chạy.
- Trước khi restart container AI2: kiểm `ai2.jobs` không còn QUEUED/RUNNING. Fixture luôn là dữ liệu tổng hợp.

## Các phần

| # | Phần | Issue | Kiểm chứng ở local (luna) | Cần production/staging | Ước lượng |
|---|---|---|---|---|---|
| P0 | PR `feature/ai2-contract-graph` → `develop` | #124 (một phần) | full test, seeded gate | CI + deploy | 0,5 ngày |
| P1 | Đo từng lần gọi LLM + trace stage `extraction`/`semantic` | #124 | log có latency/token theo stage | đọc log một hồ sơ 4 trang | 0,5 ngày |
| P2 | `reasoning_effort` thấp cho bước semantic/alias (chỉ khi model là gpt-5*) | #124 | test tham số gửi đi (stub) | đo lại thời gian S4→S10; cần Lead duyệt (D6) | 0,5 ngày |
| P3 | Đo RAM đỉnh với hồ sơ ~200 trang tổng hợp, giới hạn 2 GiB | #113 | `docker stats` + `/jobs` poll mỗi giây | — | 0,5–1 ngày |
| P4 | Giảm RAM theo số đo P3 | #113 | RAM đỉnh trước/sau, seeded gate | chạy lại hồ sơ lớn trên staging | 1–2 ngày |
| P5 | Deadline dừng job thật, giải phóng tài nguyên | #113 | test job quá `max_processing_seconds` | — | 0,5–1 ngày |
| P6 | Tách xử lý nặng khỏi process API | #113 | `/jobs`, `/healthz` trả lời khi worker chạy/chết | E2E staging | 1–2 ngày |
| P7 | `progress {step, done, total, unit}` trong `GET /jobs/{id}` | #116 | test contract | xem vòng % trên FE | 0,5 ngày |
| P8 | `/query`, `/ask` không tổng hợp bằng LLM; "phụ lục" bị đẩy sang nhánh liệt kê | #121 | tái hiện với hồ sơ seeded + luna | `used_llm=true` trên staging | 1 ngày |
| P9 | Xung đột giữa các đợt thanh toán khác nhau (5.1 30% với 5.2 40%) và bỏ sót xung đột phụ lục ↔ Điều 5 | #121 | thêm hồ sơ seeded tái hiện; gate live | — | 1 ngày |
| P10 | Biến `AI2_CONTRACT_GRAPH_PAIRS_BASE_URL/API_KEY` trong `deploy/.env.prod` | #106 | — | người vận hành thêm biến, deploy, xem trace pairs | vận hành |

## Thứ tự và phụ thuộc
1. P0 → P1 (P1 cần trên develop để đo production).
2. P3 → P4 → P5 → P6 → P7 (`progress` chỉ hiện được khi `/jobs` còn trả lời).
3. P8, P9 độc lập, làm song song với nhóm #113.
4. P2 sau P1 (cần số đo trước/sau) và sau khi Lead duyệt.
5. P10 không cần code; nhắc người vận hành ngay.

## Tiêu chí xong của mỗi phần
- Test viết trước; full ai-service test pass; seeded offline dev 42/42; `pruning_eval` không mất gold; gate live trên luna đạt.
- Mỗi phần một commit.
