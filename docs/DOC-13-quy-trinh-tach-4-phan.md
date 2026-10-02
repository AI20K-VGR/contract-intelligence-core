# DOC-13 · Quy trình làm việc khi tách 4 phần

> **Contract Intelligence** — Mỗi người làm phần của mình. Các phần chỉ nối với nhau qua API đã chốt version.

---

## 0. Thông tin

| Trường | Nội dung |
|---|---|
| Mã tài liệu | DOC-13 — Quy trình tách 4 phần |
| Ngày viết | 30/09/2026 |
| Người viết | Trần Thị Kiều Trang (Lead) |
| Team | FE: Trang · BE: Chương · AI1: Đức Dũng · AI2: Văn Dũng |

Thời gian trước, backend chưa deploy được nên cả nhóm gộp code và sửa chung một chỗ. Nay đã thống nhất cách deploy. Nhóm chuyển lại cách làm đã chốt với mentor: vẫn **một repo**, tách theo phần và theo API. Không tách thành bốn repo.

---

## 1. Ai giữ phần nào

| Người | Phần | Được sửa | Không sửa |
|---|---|---|---|
| Trang | Frontend | `frontend/` | Database, prompt, không gọi AI1 hay AI2 |
| Chương | Backend và worker | `backend/` | Logic OCR, logic hỏi đáp, không tự ý đổi kết quả máy |
| Đức Dũng | AI1 | Phần đọc chữ và dựng cấu trúc trong `ai-service` | UI, database nghiệp vụ, quyết định xung đột |
| Văn Dũng | AI2 | Phần rút thông tin, so sánh, hỏi đáp trong `ai-service` | UI, không tự duyệt hồ sơ, không gọi AI1 |

Hạ tầng dùng chung, Chương giữ trên bản online: Keycloak, PostgreSQL, MinIO, Kafka. Frontend là cửa người dùng nhìn thấy. Backend là cửa duy nhất nhận request từ frontend.

---

## 2. Ai được gọi ai

```text
Người dùng
    │
    ▼
Frontend ──đăng nhập──► Keycloak
    │
    └── REST + token ──► Backend ──► PostgreSQL, MinIO
                              │
                              ├── Kafka ──► AI1 ──Kafka──► Backend
                              │
                              └── HTTP nội bộ ──► AI2 ──► Backend
```

Chỉ có bốn đường gọi:

| Đường | Cách gọi | Bản đang chốt |
|---|---|---|
| Frontend → Backend | REST, có token đăng nhập | DOC-05, DOC-05b |
| Backend → AI1 | Kafka. Backend gửi lệnh, AI1 trả kết quả | DOC-05d. Topic `ci.ai1.ocr.commands` và `ci.ai1.ocr.results` |
| Backend → AI2 | HTTP trong mạng nội bộ, có chữ ký HMAC | Đường đang chạy trên compose. Cổng 8002 không mở ra Internet |
| AI1 → file | Tải PDF và ghi ảnh trang bằng link tạm do backend cấp | MinIO |

AI1 không gọi AI2. AI2 không gọi AI1. Frontend không gọi AI1 hay AI2. AI2 không gọi ngược về backend.

---

## 3. Chốt version nghĩa là gì

Một version là một bản API cả hai phía cùng chạy được. Chốt xong thì cả hai phía dùng đúng bản đó.

Một version được coi là đã chốt khi có đủ ba thứ:

1. Schema hoặc mô tả field nằm trong `docs/contracts/` hoặc DOC-05 tương ứng.
2. Một ví dụ request và response đúng field đang chạy.
3. Người gọi và người nhận đều nói chạy được với ví dụ đó.

Sau khi chốt:

- PATCH chỉ sửa lỗi, field giữ nguyên.
- Thêm field thì tăng MINOR. Field cũ vẫn còn, phía đang chạy bản cũ vẫn gọi được.
- Bỏ field, đổi tên, đổi nghĩa, hoặc đổi đường gọi thì tăng MAJOR. Bản MAJOR cũ chạy đến khi cả hai phía chuyển xong.
- Tăng MAJOR là đổi cách nối. Nói với mentor trước khi làm, rồi mới code.

Cách ghi số nằm ở mục 8.

Mỗi người vẫn code phần mình khi người kia chưa xong. Lúc đó dùng ví dụ đã chốt, không bịa field riêng rồi nhờ người kia đọc hiểu.

---

## 4. Một việc đi qua bốn phần như thế nào

Ví dụ: màn hình cần một field mới từ kết quả phân tích.

1. Trang ghi field frontend cần, và màn hình nào dùng.
2. Chương xem field đó đã có trong API backend chưa. Chưa có thì thêm vào version sau của API frontend–backend.
3. Nếu field nằm ở AI1 hoặc AI2, Chương không tự nghĩ ra kết quả. Đức Dũng hoặc Văn Dũng sửa contract phía mình, rồi Chương nhận đúng version đó.
4. Ba thứ được chốt cùng lúc: contract, ví dụ, và người review bên kia.
5. Mỗi người merge phần của mình. Không ai vào thư mục người khác để “nối cho xong”.

Pull request đụng hai phần thì cả hai người review. Contract đổi mà chưa có ví dụ thì chưa merge.

---

## 5. Deploy

Mỗi phần là một service riêng trên bản online.

| Service | Ai đưa lên | Ai được gọi tới |
|---|---|---|
| Frontend | Trang | Người dùng |
| Backend và worker | Chương | Frontend, và nội bộ tới AI1, AI2 |
| AI1 | Đức Dũng | Chỉ backend, qua Kafka |
| AI2 | Văn Dũng | Chỉ backend, qua mạng nội bộ |

Backend và worker dùng chung một secret HMAC với AI2. Secret bản online không dùng lại secret máy dev. AI2 không có cổng public.

Một phần deploy hỏng thì các phần kia vẫn đứng bằng version đã chốt. Không gộp bốn phần vào một image để che chỗ hỏng.

Image gắn tag SemVer của commit đã build ra nó. Phần chưa có pull request mới thì server giữ image cũ của phần đó. Ba phần kia vẫn lên image mới, miễn là MAJOR của API giữa chúng vẫn trùng.

---

## 6. Git

Cả bốn người dùng chung một cây. Cây đó có đủ `frontend/`, `backend/`, `ai-service/`. Có ba nấc: nhánh việc của từng người, nhánh `code-full`, rồi `develop`. Server build từ commit trên `develop`.

Việc của mỗi người:

1. Lấy `develop` mới nhất vào `code-full` khi `develop` đã đi trước.
2. Tạo nhánh ngắn từ `code-full`, đúng quy tắc tên ở dưới.
3. Chỉ sửa thư mục của mình. Giữ nguyên thư mục của ba người kia.
4. Chạy phần mình cho đến khi phần đó chạy được.
5. Đẩy nhánh của mình vào `code-full`. Chỉ đưa commit phần mình, không force-push cả nhánh.
6. Trên `code-full` chạy lại đủ bốn phần một lần.
7. Lần chạy đó xong thì tạo `feature/code-full` từ `code-full`, rồi mở pull request từ `feature/code-full` vào `develop`. GitHub chỉ nhận pull request khi tên nhánh có tiền tố `feature/`.

Backend đã có image trên server vẫn đi cùng đường này. Sửa `backend/` xong, phần backend chạy được, đẩy vào `code-full`, chạy chung bốn phần, rồi mới pull request vào `develop`. Merge xong thì build lại image backend từ commit mới. Frontend, AI1, AI2 làm vậy với image của phần mình.

`main` là bản đã đưa ra demo. Pull request vào `main` chỉ đi từ `develop`, `release/*`, hoặc `hotfix/*`.

| Nhánh | Dùng để |
|---|---|
| `feat/<mô-tả>` hoặc `feature/<mô-tả>` | Việc của một người, đến khi phần đó chạy được |
| `code-full` | Chỗ bốn phần gặp nhau và chạy lại một lần |
| `develop` | Nhận pull request từ `feature/code-full` sau lần chạy trên `code-full`. Server build từ đây |
| `main` | Bản đã demo. Nhận từ `develop` khi đóng một mốc |
| `fix/<mô-tả>` | Sửa lỗi, không đổi field. Cùng đường: vào `code-full`, chạy lại, rồi `develop` |
| `release/vX.Y.Z` | Đóng bản demo từ một tag |
| `hotfix/<mô-tả>` | Vá lỗi trên bản đã ở `main` |

Tên nhánh viết thường, nối bằng gạch ngang, không dấu. Ví dụ: `feat/frontend-bo-nhan-dinh`, `fix/backend-file-lon`, `feat/ai1-ocr-claim-check`, `feat/ai2-so-sanh-ten`.

Tiêu đề pull request: `loại(phần): một câu`. Loại là `feat`, `fix`, `docs`, `chore`, `refactor`, `test`, `ci`. Phần là `frontend`, `backend`, `ai`, `ai-service`, `docs`, `infra`, `repo`. Ví dụ: `feat(frontend): bỏ trạng thái sửa nhận định`.

Hai người duyệt thì mới merge. Pull request đụng hai thư mục thì mỗi thư mục một người duyệt.

---

## 7. Việc ngừng làm

- Xóa `backend/` hoặc `ai-service/` trên nhánh của mình rồi pull request. Merge lần đó làm `develop` mất source để build image.
- Đẩy thẳng vào `develop` hoặc `main`.
- Mở pull request từ nhánh cá nhân thẳng vào `develop` khi chưa chạy đủ bốn phần trên `code-full`.
- Force-push `code-full` làm mất commit của người khác.
- Sửa code phần người khác để né một field chưa chốt.
- Frontend tự gọi AI, hoặc AI1 tự gọi AI2.
- Đổi schema đang chạy mà không tăng version và không có ví dụ.
- Nhét dữ liệu chạy thử, file sqlite, hoặc secret dev vào image online.

---

## 8. SemVer

Số version viết `vMAJOR.MINOR.PATCH`. Ví dụ `v1.4.2`.

| Số | Tăng khi | Việc với hai số còn lại | Ví dụ |
|---|---|---|---|
| MAJOR | Bỏ field, đổi tên, đổi nghĩa, đổi đường gọi | MINOR và PATCH về 0 | `v1.4.2` → `v2.0.0` |
| MINOR | Thêm field, phía cũ vẫn gọi được | PATCH về 0 | `v1.4.2` → `v1.5.0` |
| PATCH | Sửa lỗi, field giữ nguyên | Giữ MAJOR và MINOR | `v1.4.2` → `v1.4.3` |

Ba chỗ dùng cùng một cách đếm:

| Chỗ gắn số | Tên | Ý nghĩa |
|---|---|---|
| Git | Tag `v1.4.0` trên `develop`, rồi đưa sang `main` | Cả repo tại commit đó |
| Image | `frontend:v1.4.0`, `backend:v1.4.0`, `ai1:v1.4.0`, `ai2:v1.4.0` | Lần build của từng service |
| API | Số trong DOC-05 hoặc contract. File schema giữ hậu tố major, ví dụ `ai1.snapshot.v1` | Bản hai phía đang nói với nhau |

File schema đang chốt là major 1 (`*.v1`). Hết tương thích thì tạo file `*.v2`. Trong tài liệu ghi đủ ba số, ví dụ API frontend–backend `v1.5.0`.

Service không sửa trong lần đó giữ tag image cũ. Ví dụ git lên `v1.4.0`, chỉ frontend đổi: build `frontend:v1.4.0`, backend vẫn chạy `backend:v1.3.2`. Bốn service vẫn lên cùng server khi MAJOR của API giữa chúng trùng.

Tăng MAJOR thì nói mentor trước, có schema, có ví dụ, cả hai phía chạy được, rồi mới gắn tag.

---

**Hết DOC-13 · Quy trình tách 4 phần**
