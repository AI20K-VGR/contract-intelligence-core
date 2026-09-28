---
name: verdict-and-artifact
description: How to map a review verdict to review-decision.yaml and its relationship with gate_stage.py
---

# Verdict and artifact

After review completes, `hs:code-review` must emit an artifact conforming to `harness/schemas/artifact-review-decision.json`. The gate `gate_stage.py` reads this artifact to allow or block the pr/ship/deploy stage.

---

## Verdict to artifact mapping

| Review outcome | Verdict artifact | Gate action |
|---|---|---|
| No Critical/Important findings | `PASS` | Stage allowed to proceed |
| Findings exist but owner consciously accepts | `PASS_WITH_RISK` | Stage allowed; risk recorded |
| Unresolved Critical findings | `BLOCKED` | Write artifact with verdict `BLOCKED` — gate blocks because verdict != PASS |

`PASS_WITH_RISK` is a **conscious soft-accept**, not a free ship license. Rationale must explain why the risk is being accepted.

---

## Required schema

Pure-YAML SSOT (the gate also reads a legacy `review-decision.json`):

```yaml
verdict: PASS | PASS_WITH_RISK | BLOCKED
reviewer: <resolve_actor() output>
role: reviewer
rationale: <WHY — a paragraph explaining the verdict>
```

**Optional fields:**
- `plan_hash`: sha of plan.md at review time — detects plan drift after approval
- `ticket_id`: optional free-form issue/MR reference

Full backing schema: `"${HARNESS_BIN_ROOT:-.}"/harness/schemas/artifact-review-decision.json`.

---

## Artifact path

Write to the active plan's artifact path:

```
plans/<active-plan>/artifacts/review-decision.yaml
```

If no plan is active (ad-hoc review): write the report to `plans/reports/` and clearly state that no gate-able artifact exists — the gate will not activate.

---

## Gate relationship

`harness/hooks/gate_stage.py` is a **presence gate**:

- Verifies the artifact EXISTS at the correct path
- Verifies `verdict` satisfies policy (`"${HARNESS_BIN_ROOT:-.}"/harness/data/stage-policy.yaml`, stage's `requires:` lists `review-decision`)
- Hard stages require **exactly `PASS`** — `PASS_WITH_RISK` is not sufficient for a hard stage
- The gate does NOT verify the reviewer is different from the author — that is a role check in `plan_approval`, not in this gate

**When the gate refuses:**
- An actionable reason, naming the artifact that is missing or the verdict that
  is not PASS
- Personal-first: a missing or failed receipt at a hard stage is surfaced as an
  ADVISORY locally, not a block — presence enforcement runs in remote CI
  (`receipts-gate`). Two things still fail closed on the spot: a shell write to
  a receipt path (the forgery arm) and an internal crash of the hook itself.

---

## Artifact emit procedure

```
1. Review complete → determine verdict (PASS / PASS_WITH_RISK / BLOCKED)
2. Always write the artifact via write_review_decision.py — the verdict (incl. BLOCKED)
   is the machine-readable record the gate reads and audit/replay relies on. The script
   stamps run_seq (so the orchestrator can stale-reject a prior run's artifact) and writes
   atomically (same-dir .tmp + os.replace) — do NOT hand-write the YAML with the Write tool,
   which skips both:

     python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/write_review_decision.py <plan-dir> \
       --verdict PASS|PASS_WITH_RISK|BLOCKED \
       --rationale "<WHY — for BLOCKED, the unresolved blockers>" \
       --rounds-run <N> \
       [--reviewer <resolve_actor output>] [--plan-hash <sha>] \
       [--effort <low|medium|high|xhigh|max> --strategy <name>]

   Reviewer defaults to resolve_actor(); the script reports the absolute artifact path.

   **`--rounds-run` is REQUIRED — the writer refuses without it (exit 2, nothing written).**
   It is what keeps the history. The canonical `review-decision.yaml|json`
   is overwritten on every write, so without the round number an earlier BLOCKED vanishes
   the moment a later round clears it — and nobody auditing the plan afterwards can tell a
   one-round PASS from a PASS that took four. With it, the write also drops a first-wins
   `review-decision-r<N>.json` snapshot beside the canonical file, the same shape
   `write_verification.py` uses for `verification-<phase>.json`. Unlike verification, every
   verdict is snapshotted, not just PASS: the BLOCKED rounds are the ones worth keeping.
   Omitting the flag is not an error — it degrades with an advisory on stderr.
3. Report verdict + unresolved questions
   - BLOCKED → gate blocks pr/ship/deploy (verdict != PASS)
   - PASS_WITH_RISK → hard stages still block; soft stages may proceed
   - PASS → hard stage may proceed
```

---

## Example PASS artifact

```yaml
verdict: PASS
reviewer: agent:code-reviewer
role: reviewer
rationale: >-
  No Critical or Important findings. 2 Suggestions for micro slop are noted but
  do not block. Gate logic, error handling, and test coverage are adequate for
  the change scope.
plan_hash: a3f9c1d4e8b2
```

## Example PASS_WITH_RISK artifact

```yaml
verdict: PASS_WITH_RISK
reviewer: agent:code-reviewer
role: reviewer
rationale: >-
  1 Important finding: cache invalidation missing on updateUser(). Owner accepts
  the risk because this PR scope only fixes an auth bug; cache refactor is
  tracked in BACKLOG.md. Shipping with the known stale-cache risk.
plan_hash: b7d2e5f1c9a4
```

---

## Optional recall stamp

Khi `hs:code-review` chạy ở **recall-mode** (nhiều vòng, nhiều lens), nó điền thêm 3 field optional vào artifact `review-decision.yaml`:

| Field | Kiểu | Ý nghĩa |
|---|---|---|
| `effort` | enum `low\|medium\|high\|xhigh\|max` | Mức effort đã resolve từ profile |
| `rounds_run` | int ≥ 0 | Số vòng review thực tế từ vòng lặp recall |
| `strategy` | string | Tên profile đã dùng (vd: `ship-grade`, `thorough`) |

Với review 1-vòng thường, 3 field này **optional** — bỏ trống hoàn toàn được, gate presence vẫn pass (không thêm vào `required`).

### Quy trình điền khi recall-mode kết thúc

```
1. Vòng lặp recall kết thúc (N rounds xong hoặc hội tụ sớm)
2. Ghi verdict + rationale như bình thường (required fields)
3. Thêm các field recall stamp:
   a. effort   ← giá trị đã resolve từ profile (vd: "high")
   b. rounds_run ← số vòng thực tế đã chạy
   c. strategy ← tên profile (vd: "ship-grade")
4. Ghi YAML vào plans/<active-plan>/artifacts/review-decision.yaml
```

### Ví dụ artifact recall (PASS, ship-grade, 3 vòng)

```yaml
verdict: PASS
reviewer: agent:code-reviewer
role: reviewer
rationale: >-
  3-round ship-grade review. No Critical/Important findings survived the
  refute pass. Minor suggestions noted; owner accepts.
plan_hash: c2f8a1d9e4b7
effort: high
rounds_run: 3
strategy: ship-grade
```

### Gate đọc các field này như thế nào

`artifact_check._check_stage_floor` đọc `effort` và `rounds_run` khi `review-policy.yaml` có `stage_floor[stage].enabled: true`. Nếu file vắng hoặc malformed, gate **KHÔNG block** (fail-soft — self-discipline tier, không phải boundary thật). Xem `"${HARNESS_BIN_ROOT:-.}"/harness/data/review-policy.yaml` để bật floor.

**Honesty**: Các field này là **self-report, dễ giả** (forgery-gate). Gate chỉ xác nhận sự hiện diện và giá trị, không authenticate ai đã chạy review. Assurance thật đến từ verdict=PASS + code_evidence trong artifact.
