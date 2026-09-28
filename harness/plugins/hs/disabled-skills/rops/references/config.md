# rops configuration

Keys live in `.rops.env` at the repo root. A real environment variable of the same name always
wins, so a one-off override needs no edit:

```
ROPS_HOST=other-box rops doctor
```

`doctor` writes this file on first use in a repo and adds it to `.git/info/exclude` — the LOCAL
ignore list, never the repo's `.gitignore`, which belongs to the repo and may not be yours to
change.

Inline comments are stripped at the first `" #"` (space-hash). A value containing `" #"` would be
truncated — keep values quote-free and comment-free.

## Connection

| Key | Default | Notes |
|---|---|---|
| `ROPS_HOST` | — | **Never detected.** An ssh alias or `user@host`. Put `HostName`/`Port`/`User`/`IdentityFile` in `~/.ssh/config` and add `ControlMaster auto` + `ControlPersist 10m` — without multiplexing every verb pays a fresh TCP+auth handshake, and a verb makes several ssh calls. Measured: the same command took 3.3s on a multiplexed alias and 6.4s on a bare one. |
| `ROPS_SSH_OPTS` | *(empty)* | Extra `ssh` flags, split with `shlex`. |

## Paths

| Key | Default | Notes |
|---|---|---|
| `ROPS_REMOTE_DIR` | `~/rops/<repo-name>` | Detected. A directory the tool owns, not a mirror of a real checkout — so `--delete` cannot eat someone's working tree. |
| `ROPS_RSYNC_EXCLUDES` | detected | Comma-separated; the floor (`.git/`, `.venv/`, `__pycache__/`, `node_modules/`, caches) is always present, plus whatever `.gitignore` lists. Negations (`!x`) are dropped — rsync has no equivalent and passing one through would exclude a literal `!` filename. |
| `ROPS_LANE_KEEP` | empty | Comma-separated directories a `lane` REBUILD carries over from the old tree, on top of the floor. See **Keeping a directory across a rebuild** below. |
| `ROPS_LOG_DIR` | `/tmp/rops` | Where full logs stay, ON THE REMOTE. Behavior 4. |
| `ROPS_TAIL` | `60` | Lines returned. The rest stays remote; rops prints the path and line count so you can `fetch` it. |

### Keeping a directory across a rebuild

The floor a `lane` rebuild always carries is `.venv` + `logs`, plus whatever the
`ROPS_CMD_*` lines put on PATH as `$PWD/<name>/bin` — this repo's `.venv-ci` is found
that way and needs no entry. Every kept name is also protected from the lane's
`--delete`, so the two can never disagree.

Declare a name in `ROPS_LANE_KEEP` only when it lives ONLY on the lane and detection
cannot see it — a model cache, a fixture corpus. Measured 260910: a 457 M venv named in
no list was destroyed twice over, by `rm -rf` on a rebuild and by `--delete` on every
run after.

## Execution

| Key | Default | Notes |
|---|---|---|
| `ROPS_PATH_PREPEND` | — | Prepended to `PATH`. A non-interactive ssh shell often lacks `~/.local/bin`, so `uv` is simply missing — and rc=127 "command not found" reads as "uv is not installed over there", not as "PATH is wrong". `doctor` checks every alias's binary for exactly this reason. |
| `ROPS_ENV` | — | Comma-separated `K=V` exported before every command. Database URLs belong here. |
| `ROPS_TMUX_SESSION` | `live` | Only used with `--tmux`. Created on demand with `window-size latest`, so the pane sizes to whichever client is attached rather than the smallest one. |

## Command aliases

Every `ROPS_CMD_<NAME>` becomes a verb. The name is uppercase in the key, lowercase on the
command line:

```
ROPS_CMD_TEST=uv run python -m pytest -q      ->  rops test -- -n 8
ROPS_CMD_LINT=uv run ruff check .             ->  rops lint
ROPS_CMD_BUILD=docker build -t app .          ->  rops build
```

Detection proposes these from the repo's own files: `pyproject.toml` (+`uv.lock`/`[tool.uv]`),
`package.json` scripts (with pnpm/yarn/npm chosen by lockfile), `Makefile` targets, `go.mod`,
`Cargo.toml`. First source that answers a key wins; later ones only fill gaps.

## Benchmarking

| Key | Default | Notes |
|---|---|---|
| `ROPS_BENCH_REPEAT` | `2` | The floor, not a target — a 50%-flaky test needs ≥10 repetitions to show its base rate. |
| `ROPS_BENCH_PREP` | — | **Required** (or pass `--no-prep`). A shell command run ON THE REMOTE before EACH repetition, to return the ground to a known state: `docker compose -p x restart db`, `redis-cli flushall`, `rm -rf .cache`. A failing prep aborts the bench rather than measuring an unknown state. See below. |
| `ROPS_MAX_LOAD` | `0.2 x cores` | `bench` refuses, and `doctor --measure` reports a failure, above this 1-minute load average. The default is SCALED by the remote's `nproc`. |
| | | A load average is a run-queue length, so it only means something against the cores that can drain it: an absolute 4.0 is 20% utilisation on a 20-core box and 200% on a 2-core one. A 20-core host resolves to 4.00, unchanged; absent `nproc`, it falls back to an absolute 4. |
| | | A value you SET is used as typed, never scaled — scaling a number an operator wrote would make it mean something other than what they wrote. Raise it only if the host genuinely idles higher, never to get past a red gate on a busy machine, which is the exact failure the number exists to stop. |
| `ROPS_COOLDOWN_TIMEOUT` | `300` | How long a hot host is given to COOL before the gate calls it busy. `bench --repeat N` measures run 2 right after run 1's workers exit, so the 1-minute average still carries the run that ENDED — measured 12.94 → 5.46 over five minutes with nothing of ours alive. Raising it does not widen what passes, only how long rops waits. |
| `ROPS_MIN_FREE_KB` | *(unset)* | Refuse to measure when `ROPS_SCRATCH_PATH` has less than this free. OFF unless declared — see **A full scratch filesystem** below. |
| `ROPS_SCRATCH_PATH` | `/tmp` | Which filesystem `ROPS_MIN_FREE_KB` measures, and which `run` reports on after a command. Set it to whatever your command actually writes to (`/dev/shm` when `TMPDIR` points there). |
| `ROPS_SCRATCH_WARN_PCT` | `85` | Above this, `run` prints a one-line warning AFTER the command — it never deletes and never changes the rc. |
| | | `bench` clears the ground between repetitions via `ROPS_BENCH_PREP`; `run` does not, and `run` is what drives a suite by hand. Measured: three full-suite `run` passes left 19 GB in `/dev/shm`, and the NEXT run died with `Errno 122 Disk quota exceeded` — surfacing as `git init` exit 128, a red test rather than a disk message. |
| `ROPS_LOGIN_SHELL` | `zsh` | What an orphaned shell looks like in `ps`. A shell with PPID 1 in state `R` is never legitimate. |

### A full scratch filesystem returns a number, not an error

`ROPS_MIN_FREE_KB` is off unless you declare it: rops cannot know what your workload writes,
and a guessed floor turns away healthy hosts. Declare it when a repeated `bench` writes real
volume, because running out of room does not announce itself.

Measured (2026-09-01, 20-core host, 32 GiB `/dev/shm`):

- one run of the suite under test wrote **6.4-6.7 GiB** of temp trees;
- pytest keeps the **last three** run directories (`_retention_count=3`), so without a prep
  step that clears them ~20 GiB stays resident;
- the run that tipped it over did **not** say "out of space". One repetition returned a
  plausible number 6s off its siblings; the next died with `INTERNALERROR` on a worker whose
  test passes in isolation.

A wrong number that does not look wrong is the failure this gate exists to stop, which is why
the check lives beside the load check rather than in the workload's own prep step.

**Size the floor for ONE run, not for the leftovers.** Set it to what a single run needs plus
headroom, and clear the previous run's trees in `ROPS_BENCH_PREP`. A floor set to
one-run x retention was measured refusing a host with 20.8 GiB free whose prep had just
cleaned it — a 223 MiB shortfall that could never have mattered, and it cost the final
repetition of a benchmark. A floor exists to stop a run that will not fit; sizing it for
files the caller already deletes makes it a second failure mode.

### `ROPS_BENCH_PREP` runs over there

It is a shell string executed on the REMOTE, so `rops` itself is not available inside it. Name the
underlying command:

```
ROPS_BENCH_PREP=rops db reset        # rc=127, command not found — measured
ROPS_BENCH_PREP=docker compose -p docintake-test -f docker-compose.test.yml up -d --force-recreate postgres-test
```

The gate correctly refuses to measure through a failing prep, so the mistake surfaces immediately
rather than as a quietly wrong number.

## Repo-local keys

A verb under `<repo>/.claude/rops/verbs/` may read any key it likes. It should call
`cfg.require(KEY, why)` rather than defaulting, so a missing value fails loudly.

Worked example — the `db` verb in document-intake declares `ROPS_COMPOSE_PROJECT`,
`ROPS_COMPOSE_FILES`, `ROPS_COMPOSE_ENV`, `ROPS_DB_SERVICE`, `ROPS_DB_CONTAINER`,
`ROPS_DB_USER`, `ROPS_DB_NAME`.

`ROPS_COMPOSE_ENV` is not optional there: `docker compose up -d postgres-test` interpolates the
WHOLE file before it picks a service, so a variable another service marks required must still be
set even when you only touch postgres. Leaving it out fails with an interpolation error naming a
service you never asked to start — and if the verb pipes that through `tail`, the error reaches
you as rc=0 and a reset that silently did nothing. (Both halves measured, 260901.)
