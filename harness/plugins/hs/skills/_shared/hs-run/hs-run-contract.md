# `hs-run` — the machine contract shared by `hs:plan` and `hs:cook`

`hs-run <domain> <verb>` owns the **deterministic** half of the workflow: the ORDER of the
steps and the PARAMETERS each step needs. It never decides **whether** a step applies — that
judgment stays in the skill prose and in you. A CLI that starts skipping a step "because it
looked unnecessary" has stopped being a CLI; report it, do not follow it.

Read this once; both skills assume it.

## The loop you actually run

```
hs-run <domain> next          # ask DISK what comes next — never a progress file
```

| exit | meaning | what you do |
|---|---|---|
| `0` | nothing left | stop |
| `11` | one more **deterministic** step | run the printed `next_action` verbatim, call `next` again |
| `10` | a **model turn** is required | do the judgment work the state names, then call `next` again |
| `2` | the CLI cannot answer its own question | read `warnings`, fix the input/plan, **do not proceed** |

`status` is the one verb that always exits `0` (read-only report) — except when it hits a
`state_conflict`, where it cannot give a trustworthy answer and exits `2`.

**Never write a driver as `while [ $? -ne 0 ]`.** `10` and `11` are both "not done" but they
are not interchangeable: `11` you may automate, `10` you may not.

## Three outputs, three readers

Every verb prints **JSON on stdout** (`state`, `next_action`, `artifacts`, `warnings`,
`registry_sources`, and — when no plan resolved — `searched_dirs`) plus **one human line**
(`state=… · <numbers> · <next thing> · <re-run command>`). The exit code is the real machine
contract; the JSON is what you and the tests read; the human line is for the person watching.

`artifacts: []` with no `searched_dirs` would be an unverifiable answer — the envelope always
says where it looked.

### Never read the exit code through a pipe

A shell pipeline reports the exit status of its **last** stage, so `hs-run … | anything`
reports the reader's `0` and the blocking `2` disappears. The exit code is the machine
contract; a pipe silently replaces it. Capture it first, then forward it explicitly:

```
hs-run <domain> <verb> > /tmp/env.json; rc=$?
hs render --upstream-rc "$rc" < /tmp/env.json     # exits with the code hs-run gave
```

`hs render` re-derives nothing: `--upstream-rc` **forwards** the status you captured, and
rejects a value outside the closed ladder — a code from somewhere other than `hs-run` is an
error, not a result. Without the flag it exits `0`, which honestly reports on the rendering
and nothing else.

## `next` is a PROJECTION, not a progress ledger

State is re-derived from artifacts on disk on every call. Delete an artifact and the state
regresses — that is correct behaviour, not a bug. Consequences you must respect:

- **The `status:` line in `plan.md` frontmatter has no authority.** It is corroboration only.
  When frontmatter and artifacts disagree, `hs-run` reports `state: state_conflict` at exit
  `2` and names **both** sides. Do not pick a side yourself and carry on; find out which one
  is lying. Proceeding on a state you cannot trust is worse than stopping.
- No verb writes `status:` as a side effect of projecting.
- A step that produced no artifact is **not done**, however sure you are that you did it.

## Steps that need a model are TWO beats

The CLI cannot spawn a subagent — you are the outer loop. So a model-requiring step splits:

```
hs-run <domain> prompt <role>            # beat 1: prints the delegation brief, always exit 10
# you spawn the subagent, get its result, write it to a file
hs-run <domain> record <role> --out F    # beat 2: ingests the result, re-projects, returns the new state
```

`record` is an **attestation that you ran the step**, never proof that the step was done well.
Reviewing the subagent's output is your job, and it happens before you call `record`.

## What `hs-run` deliberately does NOT know

Some obligations cannot be proved from disk. `hs-run` names them in `warnings` instead of
pretending: whether a `Task(...)` delegation really happened, whether a red-team finding was
genuinely dispositioned, whether a consistency sweep really found nothing. When a warning
says "not disk-provable", that is your cue to check it yourself — not permission to skip it.
