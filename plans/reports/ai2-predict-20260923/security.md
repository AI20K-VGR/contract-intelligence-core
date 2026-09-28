# AI2 security/privacy review

Ngày: 2026-09-23  
Phạm vi: proposal hiện tại `plans/260923-1023-ai2-completion-release`, tài liệu AI2, runtime `ai-service`, eval/mirror và CI liên quan.  
Phương pháp: read-only review; không sửa production.

## Verdict

**BLOCKED — REVISE THEN RE-REVIEW.**

Proposal có các control tốt về citation resolver, ACL/tenant+dossier lookup ở `ToolGateway`, egress policy, review states và hash-check cho eval card. Tuy nhiên còn các lỗ hổng High ảnh hưởng trực tiếp đến hallucination/citation, prompt injection, PII/egress và unsafe execution. Chưa nên coi proposal là release-ready từ góc security/privacy.

## Findings

### SEC-H-01 — Citation/hallucination gate không bắt buộc cho mọi free-form answer

**Mức độ: High**  
**Trạng thái: mở**

`classify_ask()` khởi tạo `must_cite=[]` cho mọi query (`ai-service/app/reasoning/query.py:16-24`). `L3Ground` chỉ chuyển `ANSWERED` thành `INSUFFICIENT_EVIDENCE` khi không có citation hợp lệ nếu `task.must_cite` được bật (`ai-service/app/reasoning/l3_ground.py:190-196`). Với các task không có `must_cite`, answer vẫn có thể giữ state ban đầu dù không có citation hợp lệ (`ai-service/app/reasoning/l3_ground.py:107-114,215-220`). Fallback `_extractive()` chỉ kiểm tra substring/word overlap lỏng, không chứng minh từng claim được citation (`ai-service/app/reasoning/l3_ground.py:234-249`).

**Tác động:** một free-form answer có thể được trả về dưới state không-blocked/không-review dù citation thiếu hoặc không đủ bao phủ claim; đây là đường hallucination trực tiếp.

### SEC-H-02 — Prompt injection trong contract text chưa được chặn ở trust boundary của LLM

**Mức độ: High**  
**Trạng thái: mở**

Rule security của L0 chỉ kiểm tra query text và hai chuỗi hẹp (`drop_database`, `ignore all instructions`) (`ai-service/app/reasoning/l0_rules.py:74-77,239-247`). Trong khi đó, L2 lấy nội dung node đã retrieve, đưa vào `steps`, rồi gửi nguyên payload đó trong user message đến LLM (`ai-service/app/reasoning/l2_plan.py:126-132`); client gửi trực tiếp system/user messages đến provider (`ai-service/app/llm/client.py:45-55`). Không có evidence về delimiter/taint label bắt buộc, content sanitizer, hoặc detector áp dụng cho source text trước khi đưa vào prompt.

**Tác động:** instruction ẩn trong PDF/OCR text nhưng không chứa đúng hai chuỗi trên có thể được model diễn giải như instruction; allowlist tool ở application không đủ để bảo đảm model không đổi semantics hoặc tạo output độc hại.

### SEC-H-03 — Production boundary không có PII masking; raw evidence được lưu và có thể egress

**Mức độ: High**  
**Trạng thái: mở**

Production persistence serialize toàn bộ pages/nodes/facts/chunks/citations và metadata (`ai-service/app/tools/persist.py:46-76`). Session tiếp tục lưu `ai1`, record, envelope và blob bytes vào SQLite/filesystem (`ai-service/app/tools/persist.py:121-151`); API view trả text trang và job/contribution (`ai-service/app/api/main.py:267-275,303-316`). Khi field `egress_approved` vắng trong persisted record, loader mặc định `True` (`ai-service/app/tools/persist.py:101-107`). L2 có thể gửi retrieved source text ra LLM (`ai-service/app/reasoning/l2_plan.py:126-132`, `ai-service/app/llm/client.py:45-55`).

Masking hiện thấy chỉ thuộc eval display/config; runner còn giữ `extracted_raw` và `expected_raw` trong kết quả (`evals/eval_types/ai2_contract_package/runner.py:206-216,241-251`), không phải production redaction. Proposal nói giữ raw evidence, nhưng chưa định nghĩa trường PII, policy redaction/retention, hoặc default-deny khi privacy metadata thiếu.

**Tác động:** MST, phone, email, tên cá nhân và contract text có thể tồn tại trong artifact/session hoặc rời boundary qua provider; egress flag thiếu không fail-closed.

### SEC-H-04 — Batch input mismatch không fail-closed theo dossier

**Mức độ: High**  
**Trạng thái: mở**

`run_ai2_from_ai1_files()` chỉ ghi `DOSSIER_ID_MISMATCH` khi các file có dossier khác nhau rồi vẫn tiếp tục adapt/process file đó (`ai-service/app/pipeline/ai2_batch.py:100-126`). Cùng hành vi lặp lại ở payload path (`ai-service/app/pipeline/ai2_batch.py:169-192`). Đây trái với posture fail-closed của proposal: mismatch nên bị reject/block trước processing, không chỉ biến thành batch issue. `ToolGateway` có kiểm tra tenant/dossier/pins khi truy cập record (`ai-service/app/tools/gateway.py:32-60`), nhưng check đó không loại bỏ việc package entry nhận và xử lý batch có identity lẫn lộn.

**Tác động:** caller có thể nhận một batch result gắn `dossier_id` đầu tiên nhưng chứa document ngoài dossier đó; hiện chưa chứng minh cross-tenant data leak, nhưng boundary identity/scope không fail-closed.

### SEC-H-05 — `run_code` dùng `compile/exec` trong cùng process, chưa có resource isolation

**Mức độ: High**  
**Trạng thái: mở**

`run_code` nằm trong tool allowlist (`ai-service/app/tools/gateway.py:17-26`) và gọi sandbox (`ai-service/app/tools/gateway.py:256-265`). Sandbox chỉ AST-block một số node/call/name (`ai-service/app/sandbox/__init__.py:7-49`), sau đó vẫn `compile()` và `exec()` code trong process hiện tại (`ai-service/app/sandbox/__init__.py:52-88`). Không thấy giới hạn wall-clock, CPU, memory, output size hoặc process isolation; loop/large allocation không nằm trong forbidden set. Code có thể do LLM sinh qua table pipeline (`ai-service/app/pipeline/table.py:42-72`).

**Tác động:** chưa có bằng chứng RCE, nhưng có đường DoS đáng kể và sandbox escape surface; một table/input độc hại hoặc model output bất thường có thể treo worker/chiếm tài nguyên.

### SEC-M-06 — Eval mirror có thể tạo false assurance so với production

**Mức độ: Medium**  
**Trạng thái: mở**

Mirror tự nhận là dependency-free và không import production stack (`evals/eval_types/ai2_contract_package/pipeline_mirror.py:1-20`), nhưng `run_pipeline()` chủ yếu trả kết quả dựa trên fixture/query cases (`evals/eval_types/ai2_contract_package/pipeline_mirror.py:31-93`). Eval runner dùng direct mirror import khi không có `mirror_contract.json` (`evals/eval_types/ai2_contract_package/runner.py:469-475`). Vì vậy green eval/mirror không phải bằng chứng độc lập rằng production path giữ nguyên citation, tenant scope, prompt-injection và fail-closed semantics; parity test là cần nhưng chưa thay thế integration/security tests trên production entry.

### SEC-M-07 — CI chạy code/eval với dependency range mở, chưa có supply-chain pinning rõ

**Mức độ: Medium**  
**Trạng thái: mở**

CI cài dependency bằng các range `>=` trong `ai-service/requirements.txt:1-20`, rồi chạy toàn bộ service tests và eval code từ checkout (`.github/workflows/production-evals.yml:16-61`). Workflow `ai-service` cũng cài requirements và chạy pytest (`.github/workflows/ai-service.yml:15-35`). Đây là execution của code/dependency thay đổi trong PR/branch; chưa thấy lock/hash verification trong workflow này.

**Tác động:** dependency drift hoặc package compromise có thể làm thay đổi kết quả eval hoặc thực thi mã trong runner; đây là gap hardening CI, không phải bằng chứng đã có compromise.

## Controls đã kiểm chứng

- Citation được re-resolve qua active tree và `CitationResolver` (`ai-service/app/reasoning/l3_ground.py:18-80`).
- `ToolGateway` kiểm tra tenant, dossier, actor permission, ACL revision và version pins trước tool access (`ai-service/app/tools/gateway.py:32-60`).
- Egress denied/budget/index lease có nhánh blocked/review trong IDP (`ai-service/app/pipeline/idp.py:59-83`).
- Eval runner có config hash drift check trước scoring (`evals/eval_types/ai2_contract_package/config_integrity.py:37-67`) và mirror subprocess có env allowlist, loại provider/harness secret names (`evals/eval_types/ai2_contract_package/runner.py:367-401`).
- Proposal đã quy định `NEEDS_REVIEW`/`INSUFFICIENT_EVIDENCE`/`BLOCKED` là safe states và không publish authoritative trong AI2 (`docs/ai2/AI2-DOC-04-architecture.vi.md:21-26,169-176`). Các control này giảm rủi ro nhưng không khắc phục các finding mở ở trên.

## Release disposition

Không approve security/privacy release gate. Tối thiểu phải đóng SEC-H-01 đến SEC-H-05 bằng test/evidence có anchor: bắt buộc citation per claim, source-text injection isolation, PII/retention/egress deny-by-default, reject dossier mismatch trước processing, và process/resource isolation cho `run_code`. SEC-M-06/07 cần được xử lý hoặc ghi nhận rõ là residual risk trước human release decision.

