# Preflight matrix

## Rule

Inspect **every** plan phase — not only the first. Prefer `unknown` + blocking
over false Ready when a check cannot run safely.

## Matrix columns

| Phase | Requirement | Check method | Status | Owner / unblock action | Blocking? |
|-------|-------------|--------------|--------|------------------------|-----------|

**Status:** `available` | `missing` | `pending` | `unknown` | `n/a`

## Portable check catalog (v1)

| Check | Method | Secret-safe |
|-------|--------|-------------|
| CLI present | `command -v <bin>` | yes |
| Env var present | name exists; **never print value** | yes |
| Config shape | parse keys/schema only | yes |
| GitHub auth | `gh auth status` (no token dump) | yes |
| Adapter-specific | optional documented probes | yes |

## Output groups

1. **Must provide before long-run** — `Blocking? = yes` and status not available
2. **Should decide before long-run** — choices that would cause drift
3. **Can be deferred** — non-blocking and already allowed by contract

## Redaction

- Matrix and chat show `ENV_NAME: present|missing` only.
- Scrub tool stdout/stderr before copying into matrix rows.
- Never persist raw probe output that may contain secrets.

## Prohibited by default

- Creating cloud resources
- Writing/deleting remote data
- Chargeable API calls
- Printing tokens, cookies, private keys
