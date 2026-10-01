# Auto-Decision Ledger — 260929-2323-ai2-a-measure-baseline

> Quyết-định con-AI TỰ ra ở chế-độ tự-quyết (KHÔNG phải sổ DEC user-duyệt `docs/decisions.md`). Sổ **chỉ để đọc, advisory** — không chặn việc gì. Nguồn sự-thật = `artifacts/auto-decisions.jsonl`; file này là VIEW sinh ra.

## ⚠ Phải soát (chưa)

_(none)_


## Đã soát

_(none)_


## Chỉ truy-vết

| id | label | in_plan | skill/mode | what | why | evidence | reviewed |
| --- | --- | --- | --- | --- | --- | --- | --- |
| 0cb9dae63c98 | ASSUMPTION | no | hs:cook/auto | Proceed in the current checkout with P1 despite ai-service/tmp being untracked, and keep the current branch although plan.md names feature/code-full. | The user reissued hs:cook --tdd after the P1 stop condition and branch mismatch were disclosed; preserve all existing tmp data and avoid switching branches. | phase-1-golden-set-synthetic.md Implementation Steps 1; git status --porcelain -- ai-service evals = ?? ai-service/tmp/; plan.md:10; current branch feature/ai2-oracle-full-260928 | no |
| 94173d28b3be | ASSUMPTION | yes | hs:cook/auto | P1 implementation will be committed after verification; P2 open mark was already captured at the foundation SHA, so its future commit-range receipt may include this P1 commit. | The P1 verification advanced cook next and automatically opened P2 before the implementation commit; phase-commits.jsonl is append-only and its first P2 mark cannot be silently rewritten. | plans/260929-2323-ai2-a-measure-baseline/artifacts/phase-commits.jsonl:P2 open mark bdcb297e2522a589539c359b2f864d860754c660 | no |

