# Spawn discipline — group, batch, early-write

The three habits that keep a fan-out cheap and lossless. All three have script/template backing — not bare promises.

## 1. Group by concern, cap the count

- A **group** is a distinct angle on the task (a research dimension, a critique lens, a subsystem). One group = one sub (or a small set), producing MANY findings.
- Cap subs per group. A group needing >4 subs is usually two groups — split it.
- Feed the group→count map to `plan_orchestration.py --groups "research:4,critique:6,recommend:1"`; `sub_count` is the sum and the approval surface. If the sum surprises you, re-group before spawning.

## 2. Early-write every finding

An agent's output lives only in its return value until consolidation. A stalled, oversized, or crashed consolidation loses it. So each sub flushes as it finishes:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/workflow-orchestrate/scripts/write_finding.py \
    --run-id <slug> --group <group> --title "<finding>" --body "<one-para>" [--product]
```

- Append-only, one file per group → `report_dir/<group>.md`. A batch accumulates into its group file.
- In a `Workflow` script, the sub returns structured findings AND the orchestrator calls the helper (or the sub calls it via Bash) right after each `agent()` resolves — do not wait for the whole `parallel()`.
- `--product` routes under `docs/product/_refs/<slug>/`; default is `plans/reports/<slug>/`.

## 3. Consolidate in batches, not in one shot

- Merge **per group / per direction**. Never hand one agent all N subs' output in a single Write — that is the idle-stall failure mode (~180s on a big single Write).
- Mechanical first: reuse the base template's JS dedup, or `cat report_dir/*.md` and dedup by key. Only then spend an LLM pass on ranking/judgment over the deduped set.
- For the fan-out→dedup shape, `hs:base-fanout-consolidate` already does the barrier + dedup mechanically — do not re-implement it.

## 4. Mint the spawn-budget token on approval (Layer-1b)

The instant the user approves the strategy — never before (a rejected strategy must not bless a fan-out, memory `anchor-cli-self-auth-hole`) and never at the strategy-emit step — write the token so the approved fan-out runs against a real, disk-backed budget instead of the un-ticketed session threshold `spawn_provenance_guard` (when opted in) falls back to:

```bash
python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/skills/workflow-orchestrate/scripts/run_state.py \
    write-token --run-id <slug> --mode <mode> --sub-count <sub_count> \
    --groups '<json: [{"key": "..."}]>' --report-dir <report_dir> \
    --session <session_id>
```

The token authorizes its full `sub_count` across every batch until it expires (~30min default, `spawn-provenance.yaml`'s `token_ttl_seconds`) — no re-minting per batch, and it is never callable by a spawned subagent itself (only this skill, at this one approval point).

## Checklist before you spawn

- [ ] Groups are concerns, not findings.
- [ ] `sub_count` from the lead script matches what you presented for approval.
- [ ] Every sub knows its `report_dir` + group and will early-write.
- [ ] Consolidation is batched per group.
- [ ] Mode A stays within ≤2 subs/turn; Mode B reuses a base template unless bespoke.
