---
name: hs:rops
injectable: false
description: >-
  Run builds, tests, benchmarks, containers or any other heavy command on a remote machine over
  ssh + rsync (optionally through tmux), from ANY repo — it detects the destination, the excludes
  and the command aliases from whatever stack the repo uses. Use when a run is too slow or heavy
  for this machine, when a measurement needs a quiet host, when the user says "run it on homelab
  / on the remote / over there", or when a benchmark needs a clean slate per repetition.
metadata:
  compliance-tier: workflow
---

# rops — run it over there

One CLI for "do this on another machine": sync the tree, run anything, drive whatever the
repo needs, benchmark on a quiet host, kill a runaway, pull results back.

```
"${HARNESS_BIN_ROOT:-.}"/rops/rops <verb> [...]
```

It works in ANY repo. Nothing about a stack, a database, or a directory layout is baked in —
the first `doctor` run detects what it can, writes what it detected to `.rops.env`, and tells
you where every value came from.

## Two things, deliberately separated

rops is **remote control** with a **measurement discipline** layered on top, and the two are
not the same job:

- `sync` · `run` · `fetch` · `kill` · aliases — plumbing correctness. Getting the real exit
  code back, keeping the full log, killing a whole tree.
- `bench` — the only verb that asks *is this machine quiet enough to believe a number*. It
  refuses on a busy host, resets the ground before each repetition, runs at least twice, and
  calls a >10% spread noise rather than a result.

Running work on a busy machine is legitimate. MEASURING on one is not. That is why only
`bench` (and `doctor --measure`) checks load.

## Start with `doctor`

```
rops doctor              # resolved config + provenance + transport
rops doctor --measure    # also: orphaned processes, load average
```

In a repo it has never seen, `doctor` detects the destination, the rsync excludes, and the
command aliases; writes them to `.rops.env`; and adds that file to `.git/info/exclude` (the
LOCAL ignore list — never the repo's `.gitignore`).

**Read what it wrote.** Every line prints its source:

```
  remote_dir     ~/rops/document-intake        [detected]
  cmd_test       uv run python -m pytest -q    [.rops.env]
  host           homelab                       [env]
```

`[detected]` means rops guessed. A guessed destination is why `sync --delete` asks before it
runs. `ROPS_HOST` is never guessed — a wrong host means running commands on someone else's
machine.

## Verbs

| Verb | Use |
|---|---|
| `doctor` | What rops resolved, where from, and whether the far side answers. |
| `sync [--delete] [--back]` | rsync there; `--back` pulls the tree over your working copy (it refuses over uncommitted changes). |
| `run -- <cmd>` | Anything. Real exit code, full log kept remote. |
| `<alias> -- <args>` | Every `ROPS_CMD_<NAME>` becomes a verb: `rops test`, `rops lint`, `rops build`. |
| `bench --label L -- <cmd>` | ≥2 repetitions on a quiet machine, spread reported. |
| `fetch <remote-path> [dest]` | Pull a log or artifact back. |
| `kill <pattern>` / `kill --stray` | Kill a process tree by PGID; reap orphaned CPU burners. |

`--` separates rops's flags from your command. Add `--tmux` to run through a pane you can
attach to; add `--hosts a,b` to fan out across machines.

## The behaviors — do not "simplify" them away

Each one is a measurement this codebase already lost. They live in `ropslib/`; this table is
here so you recognize the symptom rather than routing around the guard.

| # | Behavior | The failure it prevents |
|---|---|---|
| 1 | Wait for the tmux pane to be idle, judged by the shell's **child count** (`pgrep -cP`) | A busy pane feeds keystrokes to the running process's **stdin** — the command "ran" and changed nothing. `pane_current_command` cannot judge this: the `( … ) \| tee` wrapper IS a zsh subshell, so tmux reports `zsh` mid-run while `pgrep -cP` reports 2. |
| 2 | Single-quote-wrap before handing text to ssh | `ssh host tmux send-keys -l -- "$LINE"` does not preserve argv quoting; the remote shell re-splits and the pieces rejoin **without spaces** → `parse error near '}'`. |
| 3 | `pipefail` around the user command | `{ CMD; echo $?; } \| tee` returns **tee's** rc → a red run reported green. |
| 4 | The full log stays remote; only a tail comes back | `\| tail -N` on the run you need to analyze destroys the evidence. Hit five times, once losing all 62 `FAILED` lines. Use `fetch` to go get it. |
| 5 | Kill by **PGID**, never by pid | `kill -9 <pid>` does not take down a `uv run` tree — processes still alive 18 minutes later. |
| 6 | Reset the ground before **each** benchmark repetition (`ROPS_BENCH_PREP`) | A `kill` does not return postgres connections. Measuring on a dirty server produced **three consecutive wrong root-cause attributions**. |
| 7 | `bench` runs ≥2 repetitions and prints the spread | The observed failure shape is "first run fast, later runs slow". A single run proves nothing. |
| 8 | Clear the line buffer (`C-c`) before typing; confirm the command **started** | A leftover partial line puts zsh in PS2 — Enter only adds a newline, `__RC=` never appears, and the tool burns the whole timeout reporting **124 as if the work had run and overrun**. |
| 9 | Check load and reap orphans before measuring | Background jobs a command spawns are **adopted by init** when the tree is killed by PGID. Measured: **56 orphaned CPU burners on a 20-core box**, oldest alive **108 minutes**, load 58, poisoning every measurement in that window. |

Behavior 8 is why **125** ("never started") is distinct from **124** ("started, overran").
Never collapse them.

### The plain lane does not use `tee`

Measured: a background job the command spawns inherits the write end of the pipe, so `tee`
never sees EOF and **ssh never returns**. The plain lane redirects to a file instead; the tmux
lane keeps `tee` because the pane has to see the output — and there the same jam surfaces as
"pane busy forever", which is a symptom you can diagnose rather than a hang. That symptom is
the only reason those 56 orphans were ever found.

## Adapting it to a repo

Three layers, weakest first — and `doctor` tells you which one every value came from:

1. **Detected** — destination (`~/rops/<repo>`), excludes (from `.gitignore` + a hard floor),
   aliases (pyproject/uv, package.json scripts, Makefile targets, go.mod, Cargo.toml).
2. **`.rops.env`** at the repo root — edit anything the detection got wrong.
3. **Real environment variables** — a one-off override needs no edit.

For something detection cannot reach — a compose stack, a database, a deploy step — drop a
verb file in `<repo>/.claude/rops/verbs/`. It appears only in that repo. See
`references/extending.md`.

## Boundaries

- **Do not switch branches** in the local tree — other sessions work in it. Read another
  branch with `git show <branch>:<path>`.
- The remote destination is `~/rops/<repo>` — a directory the tool owns, not a mirror of a
  real checkout. `--delete` still asks when the destination was detected rather than declared.
- `sync --back` writes over your working tree. It refuses over uncommitted changes.
- rops sends whatever you give it to a remote shell. Read the command before you run it.
- When a measurement contradicts an earlier conclusion, the measurement wins — say so plainly
  and correct the earlier claim rather than reconciling it.

## Quick reference

| Content | Drawer |
|---|---|
| Every `.env` key, with defaults and why | `references/config.md` |
| Verb-module contract + worked example | `references/extending.md` |
| Measurement recipes that survived review | `references/measuring.md` |
