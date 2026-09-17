# Frontend — Contract Intelligence (ST-006)

Vite + **React 19** + **TypeScript**. Chốt stack tại đây; chưa có màn HITL (mockup ST-005 nằm ở `docs/hitl-wireframe/`, không phải app này).

Yêu cầu: **Node.js 20+** (có `.nvmrc`).

## Chạy local

```bash
cd frontend
npm i
npm run dev
```

Dev server mặc định: [http://localhost:5173](http://localhost:5173).

## Lint

```bash
cd frontend
npm run lint
```

Prettier (không bắt buộc cho AC, dùng khi format):

```bash
npm run format
npm run format:check
```

Build: `npm run build`.

## Cấu trúc (cố ý trống HITL)

```
frontend/
├── src/
│   ├── api/           # stub client — chưa gọi backend
│   ├── components/    # stub — chưa HITL
│   ├── pages/         # stub — màn HITL vào ticket sau
│   ├── App.tsx
│   └── main.tsx
├── package.json
├── eslint.config.js
└── README.md          # file này
```

`npm run lint` dùng **ESLint** (không dùng oxlint).
