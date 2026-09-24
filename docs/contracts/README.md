# Contract registry

The canonical Backend ↔ AI2 processing wire contracts are:

- `be.ai2.processing.request.v1`: Backend submits the complete dossier snapshots, membership/role relations, and authoritative policy flags.
- `ai2.be.processing.result.v1`: AI2 returns an asynchronous processing result with facts, findings, resolvable citations, and a proposed index contribution.

Runtime transport (MVP body-only): Kafka — see [DOC-05e](../DOC-05e-kafka-ai2-idp-contract.md).
HTTP `POST /jobs/idp` remains demo/lab only.

See [BE-AI2-PROCESSING-CONTRACT.vi.md](BE-AI2-PROCESSING-CONTRACT.vi.md) for the lifecycle, idempotency, and ownership rules.

The AI1 snapshot contract remains the evidence-level contract. The processing
schemas below are the canonical Backend↔AI2 transport contract for this phase.

Đây là thư mục authority cho wire/data contracts. Contract AI1–AI2 được mô tả tại [AI1-AI2-CONTRACT.vi.md](AI1-AI2-CONTRACT.vi.md).

## Canonical AI1–AI2 contract

| Schema | Mục đích |
|---|---|
| [`ai1.snapshot.v1.schema.json`](ai1.snapshot.v1.schema.json) | Snapshot OCR/layout bất biến của một document |

`packages/contracts/schemas/registry.json` là registry machine-readable tương ứng. Schema legacy, result envelope cũ và catalog edge case không phải contract canonical mới.

## Quy tắc

- Schema mô tả hình dạng; canonical runtime kiểm tra schema và semantic constraints trước khi xử lý. Quarantine vận hành vẫn là future phase.
- Breaking change phải tạo major version mới.
- Không thêm AI2 facts, findings hoặc legal decision vào AI1 snapshot.
- Không dùng file output thật trong repository làm fixture; fixture phải synthetic và sanitized.

Phase hiện tại chốt payload contract AI1 → AI2 và schema/semantic validation gate. Transport/API envelope, dossier grouping, quarantine, publish gate và re-OCR là future scope.
