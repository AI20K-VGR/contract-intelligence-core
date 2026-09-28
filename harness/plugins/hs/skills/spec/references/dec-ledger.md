# DEC ledger — per-workspace

`hs:spec` and `hs:shape` record PO/BA decisions in a **per-workspace** ledger,
`<root>/docs/product/decisions.md` — the same markdown + YAML-frontmatter shape
already used by the existing product ledger. There is no separate PO/BA
namespace: the governing product decision explicitly bakes this in (rejecting a
dossier proposal to isolate PO/BA decisions under their own id space).

## Two ledgers, two mechanisms — never merge

There are **two** DEC ledgers in this repo. They share the `DEC-<n>` id
*syntax* but not the allocation mechanism, the schema, or the scope. Do not
point one tool at the other's file.

| | Workspace product ledger | Harness architecture register |
|---|---|---|
| File | `docs/product/decisions.md` (markdown + YAML frontmatter) | `docs/decisions.yaml` (YAML SSOT) |
| Tool | `dec_ledger.py` (this file, hs:spec) | `decision_register.py` (harness) |
| Allocation | scan every `DEC-<n>` token anywhere in the file (the widest read — frontmatter, headings, prose), max **+1** (collision-free by construction, never fills a gap) | `--append-alloc`, atomic-locked against the YAML SSOT |
| Schema | `id` / `status` / `date` / `actor` / `ts` / `affects` (+ prose body) — see `schemas/decision.schema.json` | `actor` / `ts` / `supersedes` / ... (harness-internal) |
| Scope | PO/BA decisions for **one product workspace** | architecture decisions for the harness itself |
| Concurrency guard | `fcntl.flock(LOCK_EX)` on a sibling `.decisions.lock` file, held across the whole critical section | its own lock, scoped to the YAML SSOT |

`dec_ledger.py` **must not** import `decision_register.py` and **must not**
use its `--append-alloc` mechanism. That allocator is built to manage a
tool-owned YAML SSOT; pointed at a hand-maintained markdown ledger it
double-allocates ids (this exact mismatch bit a hand-maintained ledger once
before). `dec_ledger.py` exists
specifically to give the workspace ledger a correct, race-safe allocator of
its own instead of reusing that mismatched tool.

`docs/product/` is also code-default-skipped from `docs-standardize`
(the harness's own docs governance; see `discover.py`), which is one more
reason the two ledgers must stay on separate tracks: the workspace ledger is
never subject to the harness's structural-docs checks.

## Allocation rule

1. Read the ledger file, scan every `DEC-<n>` token anywhere in it (frontmatter,
   headings, AND prose body) via regex — the widest possible read, so no heading
   style a hand-edit might use (indented, comment-wrapped, an italic `_DEC-<n>_`,
   or an id carried only in frontmatter) can hide an id and let `max + 1` re-hit
   it. An over-count is a harmless gap; only an under-count would collide.
2. New id = `max(existing n) + 1`. **Gaps are never filled** — a ledger whose
   highest heading is `DEC-<k>` (with earlier numbers missing, e.g.
   deleted or migrated elsewhere) allocates `DEC-<k+1>` next, not the lowest free number.
3. No whole-ledger duplicate check runs — `max + 1` is collision-free by
   construction, and a `uniq -d` gate would let one pre-existing hand-edit
   duplicate (a stray copy-pasted `## DEC-<n>`) brick every future `--add`.
   A pre-existing duplicate is therefore tolerated, not blocked or checked.
4. Append one new block: `---`-fenced YAML frontmatter, a blank line, a
   `## DEC-<n> — <title>` heading, a blank line, the prose body.

The ledger is **append-only**: existing bytes are never rewritten, only
appended to. An empty/missing ledger is initialized with a `# Decision
Register` header line before the first block is appended.

## Race-safety under `fcntl.flock`

Two `--add` invocations against the same workspace at the same instant must
not compute the same "next id". The **whole** critical section — read the
current max, compute the new id, verify uniqueness, append the block — runs
while holding an **exclusive** `fcntl.flock(fd, LOCK_EX)` on a sibling lock
file, `<root>/docs/product/.decisions.lock` (created on first use if absent).
The lock is released once the block has been written and re-verified.

This replaces an earlier "single-writer" prose mitigation with an actual
kernel-enforced guard: any second caller that reaches the lock while the
first is mid-allocation blocks until the first releases it, then reads the
now-updated max and allocates past it — no double-allocation, no lost
duplicate check.

**Linux assumption.** `fcntl.flock` is an *advisory* POSIX lock: it only
serializes callers that themselves take the lock (a process that opens the
ledger file directly and writes without locking is not blocked by it), and
its semantics are a Linux/POSIX filesystem guarantee. The harness runs on
Linux; if this module is ever ported to run against a non-POSIX filesystem
(e.g. a network filesystem with weak `flock` support, or a non-Linux host),
re-verify `flock` semantics there before relying on this guard.

## CLI

```bash
# allocate + append a new DEC block
python3 dec_ledger.py --root <workspace> --add \
  --status active --affects "PRD-X,PRD-X-E1" \
  --title "Short decision title" --body "Prose rationale."

# list existing blocks (id, status, date)
python3 dec_ledger.py --root <workspace> --list
```

Programmatic API: `alloc(root, status=..., affects=[...], title=..., body=...,
actor=...) -> str` (returns the new `DEC-<n>` id) and `list_decisions(root) ->
list[dict]` (parsed frontmatter per block, read-only).

`actor` defaults to the OS user (`getpass.getuser()`) when not supplied.
`ts` is a machine-resolved UTC ISO-8601 instant; `date` is its `YYYY-MM-DD`
prefix.

## Schema

New blocks validate against `schemas/decision.schema.json`
(`id`/`status`/`date`/`actor`/`ts`/`affects`, `additionalProperties: true`).
Blocks written before this schema existed (e.g. the harness's own
`docs/product/decisions.md` history, which predates the `actor`/`ts` fields)
are not retroactively rewritten — append-only holds even across a schema
change.
