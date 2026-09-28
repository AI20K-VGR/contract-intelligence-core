# Workflow orchestration note

Ngày: 2026-09-23  
Run: `ai2-architecture-research-20260923-v2`

## Strategy

`hs:workflow-orchestrate` đã chia nghiên cứu thành bốn track độc lập:

- `hitl`: HITL reasoning/durable execution;
- `adk-a2a`: ADK/A2A lifecycle và boundary;
- `ui-protocols`: A2UI/AG-UI;
- `transport`: SSE/WebSocket.

Các track có thể chạy song song, sau đó hội tụ qua critique → scenario → evaluation → ADR → implementation plan.

## Execution constraint

Harness đánh dấu workflow execution cần confirmation khi ultracode off. Ngoài ra model selector hiện tại không có đúng lane `gpt-5.6-luna high` mà user từng yêu cầu cho spawned agents. Vì vậy không spawn model khác và không giả mạo provenance.

Đã thực hiện fallback an toàn: main agent đọc/đối chiếu official sources và tạo bốn report riêng, sau đó tự thực hiện consolidation/critique/scenario/evaluation/ADR. Đây là lý do reports có source matrix và limitation statement; không tuyên bố là kết quả của spawned subagents.

## Evidence

- Orchestrator state: `.harness/state/orchestrate/ai2-architecture-research-20260923-v2/state.json`.
- Track reports: `track-a-*` đến `track-d-*` trong cùng thư mục.
- Consolidated artifacts: glossary/source matrix, critique, scenario/failure analysis, evaluation strategy, ADR và implementation plan.

## Consequence

Nội dung đã đủ để lập architecture plan theo evidence hiện có, nhưng không thay thế benchmark/hạ tầng-specific validation. Các claim liên quan DB/queue/LB/auth/SLO vẫn được đánh dấu open question.
