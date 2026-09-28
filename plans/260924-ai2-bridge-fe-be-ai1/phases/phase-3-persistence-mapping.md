# P3 — Persist raw result và map về BE read model

## Mục tiêu

Đưa kết quả combined của AI2 vào persistence/read API hiện có mà không làm mất provenance, relation hoặc proposed-only index state.

## Module/file dự kiến

- `backend/src/contract_intelligence/shared/ai/persistence.py`
- schema/model/repository run-step, fact, citation, finding, relation/index proposal
- mapper canonical AI2 result → read model
- extraction/run API response nếu cần additive field
- migration additive và seed/test fixtures

## Contract

- Raw result được lưu immutable theo `task_id`, `correlation_id`, source digest và schema version.
- Fact giữ raw, normalized, context, confidence, citation/evidence.
- Finding có đúng một `model_disposition`, severity/confidence/rationale và side A/B citations nếu có.
- `IndexContribution` luôn là `propose`, chờ gate; không active publish.
- Partial/error result phải có status và evidence gap, không giả làm final success.

## Acceptance criteria

- Có thể truy vấn result theo dossier/run/document.
- Fact/citation/finding body–annex hiển thị được nguồn gốc.
- Replaying cùng canonical result không tạo duplicate read model.
- Legacy extraction/comparison records không bị overwrite ngoài run canonical tương ứng.
- Persistence transaction không công bố success trước khi raw result và read model đạt invariant.

## Test cases

- full result body+annex.
- no-finding result.
- evidence gap.
- duplicate result replay.
- partial result rồi terminal failure.
- proposed index bị từ chối gate.
- schema version unknown.

## Verification artifact

Migration dry-run, persistence invariant report, raw-to-read-model trace và API contract snapshot.

## Risk / rollback

Risk là map nhầm document hoặc ghi đè dữ liệu legacy. Rollback: disable canonical read path, giữ raw record và dùng legacy read model; migration additive không rollback phá hủy.

## Dependency

P2 canonical task lifecycle; mapping phải khóa ở Backend trước P4. FE sẽ dùng contract này ở phase riêng sau.
