# Triage Routing — Severity, Reproduction Protocol, Mode Decision

## Severity matrix

| Level | Signals | Default mode |
|---|---|---|
| critical | production down, data loss, security breach, entire flow broken | `hotfix` |
| high | main feature broken, test suite broadly red, regression blocking deploy | `standard` |
| medium | local bug, workaround exists, does not block release | `standard` |
| low | cosmetic, rare edge case, minor UX issue | `standard` (or BACKLOG.md if not urgent) |

Self-assess severity; confirm with the user via AskUserQuestion when uncertain.

## Reproduction protocol

### Required collection before classification

1. **Full error message** — exact copy-paste (no paraphrasing).
2. **Stack trace** (if available) — read to the last line.
3. **Minimal reproduction steps**: command / action → actual output → expected output.
4. **Environment**: OS, Python version, branch, most recent commit SHA.
5. **Frequency**: always / intermittent / only under specific conditions.

### Reproduction procedure

```
1. Run minimal steps → confirm defect reproduces
2. Record the exact command (per SKILL.md — this is the baseline for comparison after the fix)
3. Reproducible → proceed to Step 2 (scout)
4. Not reproducible → load references/defect-repro.md
```

Cannot reproduce after 2 attempts → STOP, load `references/defect-repro.md`, gather more data from the user (logs, core dumps, CI artifacts).

### Baseline snapshot

Before routing to `hs:debug`, record:
- Exact error output (used for comparison after the fix).
- Reproduction test command (used as input for the failing repro test).
- Suspected files (preliminary estimate — `hs:scout` will confirm).

## Mode decision tree

```
Receive defect
  ↓
Reproducible?
  No  → references/defect-repro.md
  Yes ↓
        Architecture affected?  (see references/escalation-criteria.md)
          Yes → mode escalate → hs:plan
          No  ↓
                Severity critical + defect scope clearly local?
                  Yes → mode hotfix → hs:fix mode quick
                  No  → mode standard → full pipeline
```

## Handoff to hs:scout

After stable reproduction, pass the following to `hs:scout`:
- Error message + stack trace (if available).
- Reproduction command.
- Suspected files (preliminary, optional — scout will locate them if absent).
- Request: blast radius (callers, dependents, related tests).

Scout output → `plans/reports/<slug>-scout-report.md`.
