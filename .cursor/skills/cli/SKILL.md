---
name: hs:cli
injectable: false
description: "Operate the harness's own CLIs — hs-run (the step engine) and hs-cli (the config door) — without changing state the user did not ask you to change. Use when the next action is running an hs-run or hs-cli command, choosing between a reporting command and a mutating one, confirming which project a command will act on, or reading an hs-run envelope."
when_to_use: "Invoke when the next concrete action is an hs-run or hs-cli invocation, or when an envelope's exit rung has to be turned into a decision. Not for deciding which skill to run."
argument-hint: "[goal or command]"
allowed-tools: [Bash, Read]
metadata:
  compliance-tier: workflow
---

# hs:cli — safe operation of the harness CLIs

Two binaries live in `harness/bin/`, and they are not interchangeable.

- **`hs-run`** is the step engine. It answers *what happens next* and returns a JSON
  envelope. It reports; it does not approve, push, or open a PR.
- **`hs-cli`** is the config door. It reports too, but it is also the only place where
  the install's shape changes: which skills are on, which components are installed,
  what is trusted.

This skill owns the operating model, not a flag reference. `hs-cli <verb> --help` and
the envelope itself are always authoritative over anything written here.

## Do not invoke for

| Intent | Route to |
|---|---|
| Deciding which skill fits the task | `hs:find-skills` |
| Reaching a skill that is switched off | `hs:use` |
| Writing or executing a plan | `hs:plan`, `hs:cook` |
| Committing, pushing, or opening a PR | `hs:git` |

## hs-run has one door

    hs-run <domain> next

Read the envelope instead of re-deciding the next step. Do not hand-type a second verb:
a verb you typed is a second answer to a question the engine already answered, and it
arrives without the arguments the engine would have supplied.

Obey the exit rung:

| Rung | Meaning | What you do |
|---|---|---|
| `0` | done | stop; report the result |
| `10` | a model turn is required | do the work the envelope names, then re-run `next` |
| `11` | one more deterministic step remains | run the envelope's `next_command`, then re-run `next` |
| `2` | broken | stop; report the envelope's reason. Do not work around it |

Every `hs-run` verb reports and writes nothing except `plan scaffold`, which creates a
plan directory from templates. Treat that one as a mutation and confirm the target
first.

## Classify an hs-cli verb before you run it

**Reporting** — returns state, changes nothing:
`version`, `doctor`, `gates`, `guards`, `capabilities`, `list`, `render`,
and `emit` when neither `--out` nor `--ledger` is given.

**Mutating** — changes durable state:
`skills --on/--off` (moves skill directories on disk), `components --enable/--disable`,
`trust` (records the repo in the per-machine trust store), `cleanup --apply` (bare
`cleanup` only lists the buckets — it deletes nothing),
`emit --out` / `--ledger` (writes an install or a ledger).

**Passthrough** — hands its arguments to an engine with its own contract:
`migrate`, `install`. Read that engine's own `--help` and prefer its dry-run path first.

`components` and `skills` are reporting when bare and mutating when given a flag. The
verb name is not enough; classify the verb **with its flags**.

## Confirm which project the command acts on

Under a global install one shared binary serves many projects, each with its own data
home. A command that resolves the wrong project is not an error — it succeeds, against
someone else's tree.

Before any mutation, and before trusting any report:

1. Check the envelope's `root` and `root_source`. `root_source` names *how* the root was
   decided; anything other than an explicit source means it was inferred.
2. Confirm `HARNESS_BIN_ROOT` and `HARNESS_DATA_ROOT` reach the process. Without them the
   engine walks up the tree looking for `plans/` and answers confidently for whatever
   ancestor happens to have one — a run started from a scratch directory has resolved its
   root to `/tmp`.
3. Invoke by a path you control, not a bare name that may resolve to a different install.

## Read before you write

- Before `skills --on/--off`, run `hs-cli list` and see the current state. The core spine
  cannot be switched off; asking to is a sign the intent is wrong.
- Before `components --enable/--disable`, run `components` bare.
- Before `cleanup`, `migrate`, or `install`, run `hs-cli doctor`.
- Before acting on a skill by name, resolve whether it is on, off, or unknown, and route
  accordingly. A skill that is off is normal, not broken.

Switching a skill on or off takes effect only after a restart. So does a newly created or
renamed skill. Do not report a toggle as active in the session that performed it.

## Never suppress a refusal to make a command succeed

Some commands refuse on purpose. `emit` exits non-zero when a compliance gate would be
absent from the install it is about to write, and `--allow-inert-gates` exists so a human
can accept that consciously — it suppresses the exit, never the record.

Reaching for the override because a command failed is the failure. Read what the refusal
says is missing, decide whether the user accepts losing it, and say so out loud when you
proceed.

## Never test destructive paths against the user's real state

For any smoke test of install, migrate, cleanup, or recovery, point every applicable
environment variable at a throwaway tree and verify the redirect took effect before the
first mutating call. A test that silently ran against the live install is worse than no
test, because it reports success.

## Report what actually happened

Name the exact command, the resolved root, and what changed on disk. When a command
returned an envelope, quote its `state` and exit rung rather than paraphrasing them. When
something is still unresolved, say which command would settle it.
