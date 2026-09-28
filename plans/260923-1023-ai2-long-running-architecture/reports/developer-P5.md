# Báo cáo developer P5 — API, authorization và security

## Kết quả

Đã thêm `ai-service/app/security/policy.py` theo mô hình deny-by-default, không thêm dependency mới và không sửa các module P2/P3 hoặc `service_envelope.py`.

- `AuthzRequest` và `SecurityPolicy.authorize()` giới hạn theo tenant/dossier, role và action.
- Các role được hỗ trợ là `reviewer`, `owner`, `admin`, `read_only`; action ngoài contract và role lạ đều bị từ chối.
- `hitl.command` có cache idempotency theo `(tenant_id, dossier_id, idempotency_key)` và trả `IDEMPOTENCY_CONFLICT` khi digest command khác.
- Redaction đệ quy loại bỏ trường chứa `raw_contract`, `hidden_reasoning`, `prompt`, `secret` hoặc `token`, đồng thời giới hạn độ dài chuỗi.
- Audit event giữ actor/tenant/dossier/correlation/action/outcome và chỉ ghi details đã redact.
- Tool policy cho phép tool đọc, chặn tool lạ và side-effect nếu chưa có approval rõ ràng.
- Prompt-injection classifier chỉ gắn nhãn `untrusted`; không có nhánh thực thi input.

## Kiểm thử

Lệnh dự kiến:

```text
python -m pytest tests/test_p5_api_security.py -q --basetemp=.pytest-p5-basetemp
```

Kết quả independent verification: `11 passed, 1 warning in 0.04s`, exit code `0`, đã ghi vào artifact `artifacts/p5-api-security-contract.json`. Warning là `PytestCacheWarning` vì `.pytest_cache` không writable trên Windows; không có test failure.

Đã bổ sung và kiểm chứng public compatibility contract gồm `Principal`, `ResourceScope`, `RequestContext`, `validate_request_context`, `CommandLedger`, `AuditLog` và `PromptInput`.

## Hạn chế

Cache idempotency hiện là in-process và không phù hợp làm nguồn sự thật khi có nhiều worker/process; production cần store dùng chung với TTL/chính sách dọn dẹp. Module này chỉ tạo decision/audit metadata, chưa gắn vào HTTP route và không tự thực thi HITL command/tool. Approval tool hiện là tín hiệu explicit từ caller, chưa thay thế approval ledger bền vững.
