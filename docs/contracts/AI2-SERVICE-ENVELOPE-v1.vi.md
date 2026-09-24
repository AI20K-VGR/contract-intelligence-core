# AI2 Service Envelope v1

API processing yêu cầu `service_envelope` ký HMAC-SHA256.

Envelope phải ràng buộc với `tenant_id`, `dossier_id`, `actor_id`, `scopes`, `issuer`, `audience`, `key_id`, thời hạn, `nonce` và SHA-256 của request payload không bao gồm chính trường `service_envelope`.

API kiểm tra:

- `AI2_SERVICE_HMAC_SECRET` phải được cấu hình; thiếu secret là fail-closed.
- `issuer`, `audience` và `key_id` phải khớp cấu hình AI2.
- `issued_at`/`expires_at` nằm trong cửa sổ thời gian cho phép.
- Có scope `ai2.jobs.submit`.
- `payload_sha256` và chữ ký khớp nguyên văn payload.
- `dossier_id` trong envelope khớp request.
- `nonce` không được tái sử dụng cho payload khác trong cùng tenant.

Polling `GET /jobs/{job_id}` dùng header `X-AI2-Service-Envelope`. Envelope polling ký payload dạng:

```json
{
  "operation": "get_job",
  "job_id": "job_...",
  "dossier_id": "dossier-..."
}
```

Job store vẫn lưu tenant/dossier owner; việc xác thực caller và scope là điều kiện trước khi trả wire result.
