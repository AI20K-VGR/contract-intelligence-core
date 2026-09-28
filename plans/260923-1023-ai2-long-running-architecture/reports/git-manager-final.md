# Git manager hậu kiểm — AI2 long-running architecture

Ngày audit: 2026-09-24  
Branch: `feature/ai2-integration`  
HEAD: `f0dc320` (`wip: checkpoint AI2 contract integration before OCR review`)  
Remote tracking: `origin/feature/ai2-integration` tại `6319bc5`; branch đang ahead 1.

## Phạm vi và kỷ luật thao tác

Đây là audit read-only của Git status/diff/ignore và scan heuristic cho secret. Theo chỉ dẫn người dùng:

- Không stage.
- Không commit.
- Không push.
- Không reset hoặc checkout.
- Không xóa file.

Tôi đã không thực hiện các thao tác trên. Index đã có thay đổi staged từ trước audit; audit chỉ ghi nhận và để nguyên.

## Snapshot Git

`git diff HEAD --stat` cho thấy 143 file tracked khác `HEAD`, với `13,564 insertions(+), 230 deletions(-)`.

| Khu vực | Số file | Tóm tắt |
|---|---:|---|
| Staged (`git diff --cached`) | 94 | `11,601 insertions(+), 2 deletions(-)`; 92 file mới, 2 file sửa |
| Unstaged (`git diff`) | 52 | `1,964 insertions(+), 229 deletions(-)`; tất cả là file sửa |
| Untracked non-ignored | 956 | Chưa được Git theo dõi và hiện không bị ignore |

Có file đồng thời staged và còn sửa tiếp trong working tree, cần review tách hai lớp trước khi dùng bất kỳ commit workflow nào:

- `ai-service/pyproject.toml` — `MM`.
- `ai-service/src/contract_ocr/application/use_cases/ai2_snapshot_handoff.py` — `AM`.
- `docs/reviews/AI1-AI2-CANONICAL-HANDOFF-IMPLEMENTATION-2026-09-22.vi.md` — `AM`.

## Phân loại thay đổi

### Có vẻ thuộc scope AI2 — cần human review nội dung

Nhóm source/test/docs chính có tín hiệu phù hợp với plan:

- `ai-service/app/ai2/`, canonical contract, migration, ops, transport và các adapter/runtime mới.
- `ai-service/src/contract_ocr/` và `ai-service/tests/` liên quan snapshot handoff, contract, HITL, persistence/events, execution adapter, API security, evaluation và production readiness.
- Các thay đổi trong `ai-service/app/`, `ai-service/tests/`, `ai-service/configs/`, `ai-service/scripts/`.
- `docs/ai2/`, `docs/contracts/ai2.be.processing.result.v1.schema.json`, các review AI1/AI2 và cây plan đích `plans/260923-1023-ai2-long-running-architecture/`.

Các nhóm này không được tự động kết luận là đúng scope chỉ dựa trên tên đường dẫn; cần đối chiếu từng file với plan và acceptance criteria trước khi stage/commit.

### Artifact/test temp noise hoặc cần phân loại lại

956 untracked non-ignored file là điểm rủi ro chính. Phân bố nổi bật:

- `ai-service/artifacts/`: 304 file; có vẻ là output/evidence/runtime artifact.
- `ai-service/.pytest-*`, `ai-service/tmp/`, root `tmp/`: nhiều cây test run và database tạm.
- `ai-service/fixtures/generated_pdfs/`: fixture sinh ra; cần xác nhận có thuộc contract data policy hay không.
- Các file output/log tạm: `compare_*.txt`, `*_test_output.txt`, `full_test*.txt`, `l0_err.txt`, `pytest_*.txt`, `test_results.txt`.
- Theo phần mở rộng: 322 `.sqlite`, 293 `.json`, 102 `.md`, 70 `.py`, 42 `.pyc`, 29 `.xml`, 25 `.jsonl`, 17 `.txt`.
- `evals/` có 100 file untracked, gồm `evals/eval_types`, `evals/_sandbox_evidence`, scripts và tests; cần xác định phần nào là source/evidence cần giữ, phần nào là generated output.

Riêng cây plan đích có 62 file untracked, gồm plan/phases/artifacts/reports. Đây có thể là deliverable của plan và không nên xóa tự động; cần review retention theo harness.

Các cây ngoài plan đích cũng đang untracked, đáng kiểm tra scope trước khi giữ lại:

- `plans/260923-1023-ai2-completion-release/` — 32 file.
- `plans/reports/` — 24 file.
- `plans/260923-ai2-evidence-first-discovery/` — xuất hiện trong nhóm candidate ngoài AI2 plan đích.

### Candidate ngoài scope hoặc cần review riêng

Các path sau không nên gộp mặc định vào thay đổi AI2 long-running architecture:

- `.github/workflows/production-evals.yml`.
- `.gitignore` — diff hiện tại thêm rule cho harness/local install.
- `docs/DOC-02-brd.md`, `docs/DOC-03-prd.md`.
- `docs/contracts/ai1.snapshot.v1.ocr-lab.schema.json`.
- `docs/reviews/AI1-AI2-CANONICAL-HANDOFF-IMPLEMENTATION-2026-09-22.vi.md` — liên quan AI2 nhưng đang `AM`, cần tách staged/unstaged.
- `docs/ai2/` và `docs/contracts/` — có thể thuộc scope, nhưng cần kiểm tra ownership và mục tiêu thay đổi từng file.

Đây là recommendation phân loại, không phải quyết định loại bỏ hay thay đổi gate.

## Ignore coverage

Các kiểm tra đại diện bằng `git check-ignore -v` cho kết quả:

| Path đại diện | Kết quả |
|---|---|
| `tmp/ai2-full-phase2` | `NOT_IGNORED` |
| `ai-service/.pytest-final-full` | `NOT_IGNORED` |
| `ai-service/artifacts` | `NOT_IGNORED` |
| `ai-service/compare_results.txt` | `NOT_IGNORED` |
| `ai-service/fixtures/generated_pdfs` | `NOT_IGNORED` |
| `plans/260923-1023-ai2-completion-release/artifacts/review-decision.json` | `NOT_IGNORED` |
| `evals/README.md` | `NOT_IGNORED` |
| `.env` | ignored bởi `.gitignore:36` |
| `ai-service/.env` | ignored bởi `.gitignore:90` |

`.gitignore` hiện có rule cho `.env`, key/cert và một số AI/harness artifacts, nhưng chưa bao phủ trực tiếp các pattern đang tạo noise như `/tmp/`, `ai-service/tmp/`, `ai-service/.pytest-*/`, toàn bộ `ai-service/artifacts/` hoặc các file output tạm. Nên bổ sung rule sau khi owner xác nhận những thư mục nào là evidence cần lưu.

## Potential secrets

Kết quả scan heuristic trên tên file của toàn bộ tracked diff/untracked non-ignored:

- Không có tên file khớp `.env`, private-key/certificate/key-store hoặc tên chứa `secret`, `credential`, `password`, `token`, `api-key`.
- Không có literal indicator phổ biến được phát hiện: PEM private-key header, AWS access-key pattern, OpenAI-style key, GitHub token, Slack token hoặc assignment literal phổ biến cho `api_key`/`client_secret`/`access_token`/`password`.

Đây không phải secret audit đầy đủ. Các artifact OCR/model response và database SQLite có thể chứa dữ liệu nhạy cảm dù không giống secret token. Trước khi commit, cần review nội dung các artifact/eval outputs và chạy secret scanner chính thức của repo nếu có.

## Kiểm tra kỹ thuật read-only

- `git diff --check` và `git diff --cached --check`: không quan sát thấy lỗi whitespace; Git phát cảnh báo LF sẽ được chuyển thành CRLF nếu Git chạm vào working copy.
- Git phát cảnh báo không đọc được global ignore `C:\Users\dungs/.config/git/ignore` và không mở được một số thư mục test/temp do permission. Vì vậy, kết quả ignore/untracked có caveat về quyền đọc môi trường.
- Không chạy test, build hoặc formatter; đây là hậu kiểm Git-only theo yêu cầu.

## Cleanup/review recommendations — không thực hiện trong turn này

1. Giữ nguyên working tree hiện tại cho owner review; phân biệt rõ staged set 94 file với unstaged set 52 file trước mọi commit.
2. Review và giữ có chủ đích source/tests/docs/evidence thuộc `plans/260923-1023-ai2-long-running-architecture`; không xóa cây plan chỉ vì đang untracked.
3. Tách hoặc loại khỏi candidate commit các output `.sqlite`, `.pyc`, PDF sinh ra, `.pytest-*`, `tmp/`, `ai-service/artifacts/` và file log/text tạm sau khi xác định retention policy.
4. Kiểm tra riêng `evals/`, `.github/workflows/production-evals.yml`, `plans/260923-1023-ai2-completion-release/` và `plans/reports/` vì chúng có thể là scope khác hoặc evidence cần lưu độc lập.
5. Cân nhắc cập nhật `.gitignore` để ngăn tái phát noise, nhưng chỉ sau khi xác định artifact nào là deliverable bắt buộc.
6. Chạy secret scan chính thức và review dữ liệu trong artifact/eval outputs trước khi stage/commit.

## Kết luận

Repository chưa sạch: có thay đổi staged/unstaged lớn, 956 untracked non-ignored và nhiều test/artifact noise. Có một lõi thay đổi phù hợp với AI2, nhưng chưa thể coi toàn bộ working tree là một candidate commit duy nhất. Report này chỉ ghi nhận và đề xuất review/cleanup; không thực hiện cleanup, không stage, không commit và không push theo chỉ dẫn người dùng.
