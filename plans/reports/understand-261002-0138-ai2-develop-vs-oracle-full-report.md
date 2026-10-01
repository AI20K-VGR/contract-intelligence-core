# Bản đồ AI2: develop ↔ feature/ai2-oracle-full-260928

Ngày 2026-10-02. Read-only. Nguồn: `git` trên `origin/develop` (8e46857d) và `feature/ai2-oracle-full-260928` (8d267ae9), sau `git fetch --prune`.
Nhãn: **[OBSERVED]** đã chạy hoặc đã đọc thật · **[ASSUMED]** chưa chạy thật.

## 1. Kết luận nhanh

- **develop đã nối AI2 vào hệ thống** [OBSERVED]:
  - compose có `ai2-service` (cổng 8002, alias `ai2`).
  - Backend gọi `POST {AI2_BASE_URL}/jobs/idp` rồi poll `GET /jobs/{id}` (`backend/.../infrastructure/ai_adapters.py:201,253`). AI2 phục vụ đường này tại `ai-service/app/api/main.py:1632`.
  - `/query` nối được với `main.py:751`.
  - `deploy/compose.prod.yml` đã có khối `ai2-service` chỉ chạy nội bộ (`ports: !reset []`).
- **Nhánh oracle-full lệch develop: nhánh có 28 commit develop chưa có, develop có 113 commit nhánh chưa có.** Merge thử ra **19 file xung đột** [OBSERVED, `git merge-tree`]. Phần lớn xung đột nằm ở backend và frontend, không phải AI2 core.
- **Thiếu để go online theo cam kết DOC-14 §4 và DEC-BE-AI2-01 (A1–A8):**
  - A1: `query_snapshot_digest` chưa có. Backend đang chờ việc này.
  - A4: `AI2_QUERY_REQUIRE_SIGNATURE` chưa có.
  - A7: lưu trữ trên Postgres/pgvector chưa có.
  - A8: phần lớn cờ env chưa có.
  - Chi tiết ở §5.
- `ai-service` trên nhánh hiện tại: `pytest tests/unit` → **188 passed** [OBSERVED]. Chưa chạy E2E bằng docker compose [ASSUMED là chạy được].

## 2. Kiến trúc chạy (develop)

```
Frontend ─► backend (FastAPI) ─► backend-worker ─Kafka─► ai1-worker (OCR) ─► MinIO
                                     │
                                     └─HTTP+HMAC─► ai2-service:8002
                                                    POST /jobs/idp → GET /jobs/{id}
                                                    POST /query
                                                    lưu: SQLite trong volume ai2_data (AI2_JOB_DB, AI2_VECTOR_DB)
```

| Khối | Vị trí | Trách nhiệm |
|---|---|---|
| AI2 API | `ai-service/app/api/main.py` | `/health`, `/healthz`, `/jobs/idp`, `/jobs/{id}`, `/query`, legacy `/api/v1/*`, `/api/workspace/*` (demo) |
| AI2 pipeline | `ai-service/app/pipeline/ai2_batch.py`, `app/ai2/v1/` | snapshot AI1 → fact/finding/citation |
| AI2 query | `app/reasoning/query.py`, `app/tools/query_store.py` | hỏi đáp có trích dẫn |
| Kafka (hướng Sprint 3) | `app/transport/kafka_idp_worker.py` | chưa dùng, hiện chạy HTTP (DOC-14 dòng 68) |
| Adapter BE | `backend/src/contract_intelligence/infrastructure/ai_adapters.py` | ký envelope, retry, poll |
| Image | `ai-service/Dockerfile.ai2` | build `ai2-service` |
| Deploy | `deploy/` (compose.prod.yml, Caddyfile, deploy.sh, bootstrap.sh) | có kịch bản, **chưa deploy** (DOC-14 dòng 63) |
| Hợp đồng | `docs/contracts/DEC-BE-AI2-01-contract-decisions.vi.md`, `docs/DOC-05e-kafka-ai2-idp-contract.md`, `docs/ai2/AI2-*.vi.md` | SSOT giữa BE và AI2 |

## 3. Các nhánh AI2: còn sống hay đã gộp

| Nhánh | Chưa vào develop | Chưa vào oracle-full | Đề xuất |
|---|---|---|---|
| `feature/ai2-oracle-full-260928` (hiện tại) | 28 | — | nhánh nguồn AI2 mới nhất |
| `feature/ai2-integration` | 15 | 0 | đã nằm trọn trong oracle-full → xoá được |
| `codex-ai2-production-query`, `feature/ai2-production-query` | 0 | 0 | đã gộp → xoá + gỡ worktree `tmp/e2e-backend-setup-ce86` |
| `feature/ai2-backend-setup-2344`, `codex-ai2-backend-setup-pr` | 0 | 0 | đã gộp → xoá + gỡ worktree `tmp/pr-ai2-backend-setup*` |
| `ai2-deep-research-implementation` | 10 | 10 | chỉ có docs/snapshot cũ (20/09). Lưu trữ hoặc xoá |
| `docs/ai2-sprint1-plan-drafts` | 8 | 8 | docs Sprint 1 cũ → lưu trữ |
| `origin/fix/backend-ai2-dec-b4-b5-b7` (**PR #46 OPEN**) | 4 | 117 | việc của BE (B2–B8). Merge vào develop **trước**, rồi AI2 rebase lên |
| `pr-44`, `pr-45` | 0 | 96 | đã vào develop. Xoá ref local |
| `origin/feature/code-full`, `origin/code-full` | 6 / 3 | 119 / 62 | không phải nhánh AI2. Hỏi chủ nhánh |

## 4. Nhánh oracle-full có gì mà develop chưa có (28 commit)

- **AI2 core:**
  - `eb8709f` không normalize giá trị bị che.
  - `1d296a0` L0 theo vector policy.
  - `d95b202` query trên cây dòng OCR thật.
  - `32106c7` khôi phục code Kafka/query bị mất.
  - Fix EC (`d0d2426`, `b8b633f`, `0095e02`, `198e426`, `2128d23`).
- **Stack:** `831b7b5` nối AI2 trong compose và thêm cột `review_item`. Phần này **xung đột** với develop, vì develop đã viết lại compose và backend.
- **Frontend conflict view:** `86d5608`, `570a338`, `7e43e19`. Xung đột với 10 file FE trên develop.
- **Eval/golden:** `bdcb297`, `8d267ae`. Chỉ nằm dưới `evals/`, ít rủi ro.
- **Rác nên bỏ khi gộp:** `.codex/skills/`, `.cursor/skills/`, `ai-service/artifacts/ai2-eval-live-full/` (khoảng 35% diff theo số file).

**19 file xung đột:**
- Repo: `.gitattributes`, `.gitignore`, `docker-compose.yml`.
- Backend (6): `webhooks.py` (develop đã **xoá**), `settings.py`, `conflict/.../repository_impl.py`, `contract_router.py`, `extraction_full_router.py`, `worker.py`.
- Frontend (10): `CitationPane`, `SearchCitationReview`, `Structure*` ×5, `ClauseConflictPage`, `DossierStructurePage`, `conflictAnchors.ts` + test.

## 5. Còn thiếu để AI2 go online (đối chiếu DEC-BE-AI2-01 §A, DOC-14 §4)

Cách kiểm: `git grep` trên `ai-service/app` của cả hai nhánh. Kết quả giống nhau ở cả hai.

| ID | Việc | Trạng thái | Bằng chứng |
|---|---|---|---|
| A1 | `query_snapshot_digest` trong result + schema (gấp nhất) | ❌ thiếu | 0 file chứa |
| A2 | `retryable` theo mã lỗi | ⚠️ cần xác minh | có `retryable` (9 file), chưa đọc logic |
| A3 | vector `/query` theo egress, trần embedding đọc từ env | ⚠️ cần xác minh | — |
| A4 | `AI2_QUERY_REQUIRE_SIGNATURE` (mặc định true → 401) | ❌ thiếu | 0 file chứa |
| A6 | sửa docstring `kafka_idp_worker.py`, `wire.py` | ⚠️ nhỏ | — |
| A7 | Postgres schema `ai2` + pgvector + alembic, bỏ SQLite | ❌ thiếu | sqlite 5 file, alembic 0, pgvector 0 |
| A8 | cờ env `AI2_PROCESSING_EGRESS_ALLOWED`, `AI2_QUERY_EGRESS_ALLOWED`, `AI2_QUERY_USE_LLM`, `AI2_QUERY_USE_VECTOR` (mặc định false), LLM `/query` ≤ 15s | ❌ phần lớn thiếu | chỉ có `AI2_VECTOR_RECALL_ENABLED` |
| Ops | key OpenAI riêng, trần 5 USD/tháng, `/healthz` không gọi LLM, image không chứa dữ liệu chạy thử | ⚠️ cần xác minh | `/healthz` có ở `main.py:698` |

Hạn trong tài liệu: A1/A2 ngày 01/10 (**đã trễ**), A3/A4/A6 ngày 02/10 (**hôm nay**), A7/A8 trước deploy online 03/10.

## 6. Cấu trúc thư mục rối: những điểm cụ thể

- develop đang commit `apps/web/node_modules` (448 file) và `apps/web/.vite`. Nên xoá khỏi git, thêm vào `.gitignore`.
- Ở root working tree có file rác chưa track: `ocr-result.json`, `result_khoiluong.json`, `output/`, `var/`, `tmp/` (chứa 3 worktree), `node_modules/`, `reports/`.
- `ai-service/` vừa là AI1 benchmark vừa là AI2 service: `src/contract_ocr`, `ocr-benchmark/`, `app/`. Có thêm thư mục `ai1/` riêng ở root.
- Hai plan cùng `in_progress`: `260924-2116-...-epic11-completion` và `260929-2323-ai2-a-measure-baseline`.

Đề xuất: **không tái cấu trúc thư mục hôm nay**. Chỉ dọn rác git (node_modules, artifacts) và xoá nhánh đã gộp.

## 7. Điểm vào cho hs:plan

Thứ tự gợi ý trong ngày:
1. Merge PR #46 vào develop.
2. Tạo nhánh mới từ develop. Cherry-pick hoặc port các commit AI2 core (§4). Bỏ phần compose/FE/rác của oracle-full.
3. Làm A1 → A4 → A8 → A7 (A7 lớn nhất. Nếu không kịp, deploy tạm với SQLite trên volume. Mentor phải đồng ý).
4. Chạy E2E bằng `docker compose up`: upload → OCR → `/jobs/idp` → `/query`.
5. Deploy theo `deploy/README.md`.

## 8. Câu hỏi mở

1. "Go online" = chạy `deploy/deploy.sh` lên server nào? Server đã có chưa? Có đủ secret trong `deploy/.env.prod` chưa?
2. A7 (Postgres) có bắt buộc cho lần online hôm nay không, hay chấp nhận SQLite + volume tạm thời?
3. PR #46 (BE) có merge được ngay hôm nay không? Ai duyệt?
4. Phần FE conflict-view trên oracle-full (10 file xung đột) có cần đưa lên không, hay FE trên develop đã thay thế?
5. Các thay đổi chưa commit trong working tree (`evals/*`, `harness/`, `.claude/`, `docs/ai2/AI2-16-*`) có thuộc phạm vi go online không?
6. Key LLM cho bản online: OpenAI trực tiếp hay NineRouter (`AI2_LLM_BASE_URL` mặc định `host.docker.internal:20128`)?
