# `plan-graph.yaml` — the shape, and what each state is telling you

Routed at `absent`, `malformed` and `invalid`: the three states where `plan
graph` cannot answer and the next move is an edit to this file. Not routed at
`ok` — there is nothing to fix there.

Read the state the envelope printed, then the matching section. Every rule below
is the parser's actual behaviour (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/plan_graph.py`),
not a style preference.

## The file

Two top-level keys, both optional, both with a required type:

```yaml
edges:
  - {from: P1, to: P2}        # P1 is a PREREQUISITE OF P2 — not the reverse
subtasks:
  P1:
    file: phases/phase-1.md
    post: [verification-P1.json]
    files_to_create: [src/new.py]
  P2:
    file: phases/phase-2.md
    post: [verification-P2.json]
    files_to_modify: [src/new.py]
```

`edges` must be a **list**, `subtasks` must be a **mapping**. Either may be
absent, or present with an empty value (`edges:` alone) — a single-phase plan has
no edges, and that is normalised to an empty container rather than treated as
corruption. What is NOT accepted is the wrong type: `subtasks:` authored as a
list lands in `malformed` with the message naming the key and the type it found.
That message exists because the shape used to be coerced silently, and a
discarded graph printed "parallel batches: []" while exiting 0.

Edge direction is the one thing everybody gets backwards. `{from: P1, to: P2}`
means **P1 must finish before P2 starts**. Reverse it and the ordering checks
still run — against the wrong order, silently.

Node names are free-form; a node exists if it appears as a `subtasks` key OR at
either end of an edge. An edge naming a node with no `subtasks` entry is legal
and creates that node — which is also how a typo becomes an invisible extra node
with no `post`, so `invalid` fires below.

### Per-node keys

| Key | Type | What reads it |
|---|---|---|
| `file` | str | the phase document this node is about |
| `post` | list[str], non-empty | **mandatory** — the end-of-phase artifact obligation |
| `files_to_create` | list[str] | ordering-hazard + parallel-conflict checks |
| `files_to_modify` | list[str] | same |
| `files_to_delete` | list[str] | same |
| `paused` | bool | drops the phase from the batch, the completion denominator, and the gate's snapshot sweep |
| `paused_reason` | str | **mandatory when `paused: true`** — printed wherever the smaller count is |
| `reopen_when` | str | what has to happen before the pause lifts; printed with the reason |

The three `files_to_*` lists are what let the graph say "these two phases cannot
run in parallel because both write `src/api.py`". Leaving them out does not make
a plan invalid; it makes those checks silent, which is worse than a complaint.

### Pausing a phase

```yaml
subtasks:
  p3:
    post: [verification-p3.json]
    paused: true
    paused_reason: "upstream vendor API is down; nothing to integrate against"
    reopen_when: "the vendor sandbox answers again"
```

A pause says *this work is deliberately deferred*. Three consumers act on it at
once: the phase is not handed out as runnable work, the plan is not held open
waiting for it, and the stage gate stops demanding a verification snapshot it was
never going to write. Edges are reconnected around it, so a phase downstream of a
paused one still runs — and still runs after whatever the paused phase depended on.

Two things a pause is NOT:

* **Not a way to retire a red phase.** If the phase ran and its snapshot says FAIL,
  that snapshot is still read and still blocks. Pausing changes what the plan
  *expects*, never what already happened.
* **Not silent.** `paused: true` with no `paused_reason` is a finding — a count that
  got smaller with no sentence attached is one nobody can check. So is
  `paused_reason` left behind on a phase whose flag was cleared: it reads as paused
  to a human and does not to the machine.

## `absent` — no sidecar at all

Exit 0 plain, **exit 2 under `--require`**. Not an error on its own: a plan that
has not been decomposed yet has no graph. It becomes one the moment anything asks
for parallel batches or file ownership — which is what `--require` is for.

Write the file at the plan directory root, next to `plan.md`. The minimum that
parses AND passes `--require`:

```yaml
edges: []
subtasks:
  P1: {file: phases/phase-1.md, post: [verification-P1.json]}
```

## `malformed` — the file exists and cannot be read

Exit 0 plain, **exit 2 under `--require`** — and cook's preflight hard-stops on
this parser message regardless of the flag, so a malformed sidecar stops a run
just as surely as `invalid` does. `next_action` carries the parser's own message;
read it first, since it distinguishes three failures that look alike from
outside:

* **YAML will not parse** — a tab, an unquoted `:` inside a value, a broken
  indent. The message quotes the parser's line and column.
* **the top level is not a mapping** — the file opens with a list, or a bare
  scalar. Usually a stray leading `- `.
* **`edges:` is not a list / `subtasks:` is not a mapping** — the message names
  which key and what type it found. The common one is writing `subtasks` as a
  list of single-key maps, which is valid YAML and the wrong shape here.

## `invalid` — it parses, and a node has no `post`

Exit **2** in both modes — the only state that stops a run with no flag needed.
`next_action` lists the offending nodes by name.

`post` is the end-of-phase artifact obligation: the file a phase must leave
behind for anything downstream to check it happened. "Missing" covers three
cases, and they do NOT all read the same in the message:

* the node has no `subtasks` entry at all (usually a node created by a typo'd
  edge — check the spelling in `edges` before adding an entry for it);
* the entry has no `post` key — the bare `missing-post:` line, nothing else;
* `post` is present with the wrong shape — `post: verification.json` as a bare
  scalar, or `post: []`. These print a `status-leak:` line FIRST, naming the
  default that already applied, and only then the `missing-post:` line. Two
  lines, one node: read the leak line as "the default is live right now", not
  as a second problem.

Watch the block-vs-inline distinction: `post:` on its own line under a block
mapping reaches `invalid` as above, but `{file: a.md, post:}` inline is a YAML
syntax error and lands in `malformed` instead.

This is an AUTHORING gate. The runtime has a default (`verification-<node>.json`)
so nothing crashes without it — which is exactly why the gate exists: a default
that quietly applies is a decision nobody made.
