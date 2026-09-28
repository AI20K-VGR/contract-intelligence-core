---
name: hs:contract-test
injectable: false
description: Validate a live contract by running the real probe — call the API/CLI and check status, exit code, and payload — then anchor the result as manual evidence. Use to prove a contract holds after building an endpoint or command, before ship. Never gate-driven.
argument-hint: "[api | cli] <target>"
allowed-tools: [Bash, Read, Grep, Glob]
metadata:
  compliance-tier: workflow
---

# hs:contract-test — contract-validation tier

Catalog of contract-validation **probes**. A probe runs a real interaction against a target and checks the contract held (status / exit code / payload / query result), then records the result as a `manual` check the DoD gate re-reads. It is a *skill-layer* tool: runs only on deliberate invoke, like `hs:test` running pytest. It is
**never gate-driven** — see the red lines below and `references/probe-catalog.md`.

## The four probes

| Probe | Validates | v1? |
|---|---|---|
| **API** | an HTTP endpoint: status code + payload fields | **built (v1)** |
| **CLI** | a command: exit code + stdout/stderr pattern | **built (v1)** |
| **Browser** | a page via Playwright | catalog **stub** (v2) |
| **DB** | a real query result | catalog **stub** (v2) |

Browser and DB pull heavy dependencies (a driver, xvfb, an ephemeral DB, live credentials), so v1 ships only catalog description + anchor convention. Browser v2 reuses `hs:web-testing` (Playwright, already reaching live); DB v2 reuses `hs:manual-test` admissibility for a real query. Details + safe command templates: `references/probe-catalog.md`.

## Red lines (non-negotiable — threat model)

1. **Never gate-driven** — a probe is never in any `stage-policy.yaml requires:` and no hook fires it. A gate that executes target code would turn every push into an RCE trigger.
2. **Actively invoked only** — runs when a human/agent calls this skill, never automatically from cook/test/gate.
3. **No unreviewed AI-text into the shell** — the catalog describes how to build a command; review by human/agent before it runs, like any Bash tool call. A command string must never flow straight from plan/spec text into `sh -c`.
4. **Inherits the tool-execution context** — a probe takes the running context's permissions. It never escalates and never fetches outside credentials — why Browser/DB (needing live creds) are deferred to v2.
5. **No fake teeth** — drop the Aperant "CRITICAL cannot be skipped" framing; an LLM self-report has no sink. The catalog is the value, not an unenforceable promise.

## Evidence — ride the existing `manual` tier (no new tier)

A probe result is written as the `manual` check `hs:manual-test` already defines. Full anchor convention + write path: `references/probe-catalog.md`.

```json
{ "name": "manual", "format": "manual", "status": "PASS",
  "evidence_tier": "anchored", "anchor_id": "<from the manual-test hook telemetry>" }
```

## Boundaries

- This skill catalogs and runs probes; it does not gate. The gate only reads the anchored result, never the target code.
- Browser/DB stay stub until their live-credential model is designed (v2).
- See `references/probe-catalog.md` before building any command.
- Migration/schema change: `references/schema-drift-checklist.md` — expand→contract phasing + cutover checks (knowledge doc, never gate-driven).
