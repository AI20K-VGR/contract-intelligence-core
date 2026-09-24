# Hướng dẫn chạy backend và frontend

Backend nằm ở `ci-backend`. Frontend nằm ở `contract-intelligence-core/frontend`. Chạy backend trước, rồi mới chạy frontend.

Cần Docker Desktop và Node.js 20 trở lên.

## Backend

Mở terminal tại `ci-backend`:

```powershell
cd D:\vin\code\ci-backend
docker compose up -d --build
```

Lệnh này dựng và chạy Keycloak, PostgreSQL, Kafka, MinIO, API và worker. Lần đầu sẽ lâu hơn vì phải build image.

Khi xong, kiểm tra API:

- API: http://127.0.0.1:8000/health phải trả `status: ok`
- Keycloak: http://localhost:8080
- MinIO: http://localhost:9001
- Mailpit (hộp thư local): http://localhost:8025

Mailpit nằm trong profile `core`. Nếu http://localhost:8025 không mở, chạy thêm:

```powershell
docker compose --profile core up -d mailpit
```

Thư mời và thư chia sẻ hồ sơ đi vào Mailpit, không ra Gmail.

Xem log API nếu cổng 8000 không lên:

```powershell
docker logs ci-backend --tail 50
```

Dừng stack:

```powershell
docker compose down
```

## Frontend

File cấu hình là `contract-intelligence-core/frontend/.env.local`:

```
VITE_API_BASE_URL=http://127.0.0.1:8000
VITE_KEYCLOAK_URL=http://localhost:8080
VITE_KEYCLOAK_REALM=contract-intelligence
VITE_KEYCLOAK_CLIENT_ID=contract-intel-frontend
```

Cài dependency một lần, rồi chạy dev server:

```powershell
cd D:\vin\code\contract-intelligence-core\frontend
npm install
npm run dev
```

Mở http://localhost:5173

Đăng nhập bằng tài khoản seed trong realm:

- Email: `admin@ci.local`
- Mật khẩu: `Admin@CI123`

Tài khoản này được import từ `ci-backend/keycloak/realm-export.json`.
