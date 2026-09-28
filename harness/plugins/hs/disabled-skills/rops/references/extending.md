# Adding a verb

## Where it goes

| Scope | Location | Appears |
|---|---|---|
| Every repo | `rops/verbs/` | always |
| One repo | `<repo>/.claude/rops/verbs/` | only in that repo |

Prefer the repo-local location for anything that names a service, container, database, or
deploy target. Those are the repo's facts, not rops's.

## Contract

Five names in one file:

```python
"""<one line: what the verb does>."""
from __future__ import annotations
import argparse
from ropslib import hosts
from ropslib.exec import report, run_remote

VERB, HELP, ORDER = "deploy", "build an image and run it over there", 45

def add_args(p: argparse.ArgumentParser) -> None:
    p.add_argument("--tag", default="dev")
    p.add_argument("--timeout", type=int, default=1800)

def run(args: argparse.Namespace) -> int:
    host = hosts.gate(args)[0]
    return report(run_remote(args.cfg, host,
                             f"docker build -t app:{args.tag} . && docker run --rm app:{args.tag}",
                             timeout_s=args.timeout, label="deploy"))
```

That is the whole registration. The router imports every module under `verbs/` in **sorted
filename order** — not filesystem order, which is an OS detail that would make a merge's meaning
depend on it — then the repo's own directory, then the aliases.

`ORDER` only affects where the verb appears in `--help`.

## Rules

- **Never edit `rops.py` to add a verb.** If you are adding a branch to the router, the design
  has been broken. Borrowed from `hs-run` (`"${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_run.py`), survival invariant #3.
- Two modules declaring the same `VERB` is a **hard error naming both files**. Silent last-wins
  would turn a mistyped filename into a verb that quietly disappears.
- Go through `run_remote()`, never a raw `Host.run(...)`, for anything the user is waiting on.
  `run_remote` is what carries behaviors 3, 4 and the P0.2 redirect; a bare call carries none of
  them. Raw calls are for short, non-measured queries (that is all `doctor` uses them for).
- **Return through `report()`.** Returning `run_remote(...).rc` throws the tail away — an early
  version of the `db` verb did exactly that, and a failing compose call printed nothing at all.
- **Never pipe the remote command through `tail` or `tee` for tidiness.** The pipe hands back the
  pipe's exit code, so a failure returns rc=0. This is behavior 3, and it bit inside a verb, not
  just in the core.
- `cfg.require(KEY, why)` for anything the verb cannot work without. A default that silently
  papers over a missing value is how a command ends up pointing somewhere unintended.

## Calling one verb from another

Import the module and call `run` with a hand-built namespace:

```python
from verbs import db as db_verb
db_verb.run(argparse.Namespace(action="reset", sql=None, cfg=args.cfg,
                               host=args.host, hosts=None, tmux=False))
```

Build the namespace with **every** attribute that verb's `add_args` declares, plus the router's
own (`cfg`, `host`, `hosts`, `tmux`). A missing one raises `AttributeError` deep inside the
callee, far from the line that forgot it.

Prefer `ROPS_BENCH_PREP` over doing this from `bench`: a shell string in config keeps the core
from knowing what any particular repo's ground looks like.
