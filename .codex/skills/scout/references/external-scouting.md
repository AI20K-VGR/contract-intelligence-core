# External scouting — gemini/agy/OpenCode CLI

Use the `ext` flag when a large context window (1M+ tokens) is needed or SCALE is 3-5.

The primary CLI is **`gemini` + `GEMINI_API_KEY`**: Google discontinued only the *consumer OAuth tiers* of the `gemini` CLI on 2026-06-18 — **API-key auth is unaffected** and runs headless, so keyed `gemini` is the automation-safe path. `agy` (Antigravity) is the OAuth-only fallback; both accept the same `gemini-*` ids.

## Tool selection

| SCALE | Tool | Fallback |
|---|---|---|
| ≤ 3 | gemini CLI (key) → agy CLI | internal-scouting |
| 4-5 | OpenCode CLI | internal-scouting |
| ≥ 6 | → use `internal-scouting.md` | — |

## Installation check

```bash
which gemini    # primary (needs GEMINI_API_KEY exported)
which agy       # fallback (OAuth)
which opencode
```

If missing → ask user:
- **Yes, want to install** → guide installation + auth (`export GEMINI_API_KEY=...` for gemini)
- **No** → fall back to `internal-scouting.md`, record `[FALLBACK_INTERNAL]` in the report

## gemini CLI — primary (SCALE ≤ 3)

Model id comes from the single-source resolver (`data/models.yaml`), never hardcoded:

```bash
MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py)   # $GEMINI_MODEL overrides
gemini -y -m "$MODEL" --prompt "[prompt]" 2>&1      # needs GEMINI_API_KEY exported
```

If `gemini` is absent, fall back to `agy` (requires prior OAuth sign-in):

```bash
agy --dangerously-skip-permissions --model "$MODEL" --print-timeout 120s --prompt "[prompt]" 2>&1
```

On 429 / capacity: wait and retry, or switch path (agy → internal) — do not downgrade the model.

## OpenCode CLI (SCALE 4-5)

```bash
opencode run "[prompt]" --model opencode/grok-code
```

## Parallel spawn (Bash subagents)

Use the Agent tool with multiple Bash subagents in a single message:

Each subagent resolves the model itself (self-contained, avoids quoting issues):

```
Agent 1 (Bash): "MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py); gemini -y -m \"$MODEL\" --prompt 'Scout harness/hooks/ for gate scripts' 2>&1"
Agent 2 (Bash): "MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py); gemini -y -m \"$MODEL\" --prompt 'Scout harness/scripts/ for analytical scripts' 2>&1"
Agent 3 (Bash): "MODEL=$(python3 "${HARNESS_BIN_ROOT:-.}"/harness/plugins/hs/scripts/resolve_model.py); gemini -y -m \"$MODEL\" --prompt 'Scout harness/rules/ for rule files' 2>&1"
```

(If `gemini` is unavailable, swap the primary for the agy fallback: `agy --dangerously-skip-permissions --model "$MODEL" --print-timeout 120s --prompt '...' 2>&1`.)

## Error handling

| Error signal | Action |
|---|---|
| Exit code ≠ 0 | Drop agent, record error in report |
| `RESOURCE_EXHAUSTED` / `429` | Try fallback model, do not retry |
| `PERMISSION_DENIED` / `UNAUTHENTICATED` | Notify user, fall back to internal |
| 2+ agents fail | Switch entirely to `internal-scouting.md` |

## File content chunking

See `internal-scouting.md` — same formula (500 lines/chunk), via Bash subagents.
