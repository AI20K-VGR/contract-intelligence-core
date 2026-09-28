# Measurement recipes

## Before you believe any number

1. `rops doctor --measure` — transport green, no orphans, load under the ceiling.
2. Make sure `ROPS_BENCH_PREP` actually returns the ground to a known state. `bench` refuses to
   run without it, because a leaked connection or a warm cache from run 1 lands inside run 2's
   number.
3. Establish the **noise floor** before comparing anything. A difference smaller than the floor
   is not a result.
4. Run the control **back-to-back with the variant**, never against a number from an hour ago.
   The machine is shared; three consecutive wrong root-cause attributions in the codebase this
   tool was built for all came from comparing against a stale baseline.

## Comparing two configurations

```bash
rops bench --label baseline -- python -m pytest -q -p no:cacheprovider
rops bench --label variant  -- python -m pytest -q -p no:cacheprovider -n 16 --dist load
```

`bench` resets the ground before each repetition, runs at least twice, and flags a spread over
10% as noise. **A flagged spread invalidates the comparison** — it does not merely weaken it.

`--hosts` is refused here on purpose: two boxes have two noise floors, so a spread across them
means nothing. Bench each host separately.

## Before calling an A/B difference a mechanism

Measure the **base rate under a control condition**, ≥10 repetitions:

```bash
rops run --label flake -- 'P=0; F=0; for i in $(seq 1 12); do \
  if python -m pytest -q "$T" >/tmp/f-$i.log 2>&1; then P=$((P+1)); else F=$((F+1)); fi; done; \
  echo "pass=$P fail=$F"'
```

A two-phase test architecture was once built on one A/B observation that turned out to be a
50%-flaky test flipping. With a coin-flip test, a single A/B pair invents an effect one time
in four. Twelve serial repetitions cost 90 seconds and killed the claim outright.

## Reading a failure

The tail is a preview, not the evidence. The full log stays remote; rops prints its path and line
count. Go get it:

```bash
rops fetch /tmp/rops/<stamp>-test.log /tmp/full.log
sed -n '/=\{5,\} FAILURES/,/short test summary/p' /tmp/full.log | head -60
```

Never pipe the run itself through `tail` — behavior 4, hit five times.

## Exit codes

| Code | Meaning |
|---|---|
| 0 | The remote command's own rc, passed through (behavior 3) |
| 124 | Started and overran `--timeout` |
| 125 | **Never started** — the tmux pane held a partial line (behavior 8). Not a timeout. |
| 2 | rops itself refused (transport gate, missing prep, a bad `--repeat`) |

## Shell traps inside the remote command

rops hands your string to the remote shell unchanged. Three traps bite hard, and all three fail
by producing an empty result that reads exactly like a clean one:

- **zsh does not word-split a bare variable.** `F="a.py b.py"; pytest $F` passes ONE argument
  `"a.py b.py"` → `no tests ran in 0.00s`, which looks like "nothing to run" rather than "you
  asked wrong". Write `${=F}`, use an array, or inline the paths.
- **A `grep` that matches nothing exits 1** and prints nothing. Under `pipefail` that turns the
  whole command red even when the real work succeeded — and read the other way, an empty grep
  result reads as "clean".
- **`time prog a; b > out 2> timing` measures `prog a` but redirects `b`.** A trailing redirect
  binds to the LAST clause, so `/usr/bin/time`'s output goes to the shell's own stderr and the
  timing file stays empty — measured:

  ```
  $ bash -c "/usr/bin/time -f 'WALL=%e' sleep 0.2; echo done > L.out 2>L.time"
  WALL=0.20        # straight to the terminal
  $ cat L.time     # empty
  ```

  Read the failure the other way to see why it is nasty: if the redirect HAD bound to the first
  clause, the timing file would hold the number and there would be no bug at all. `bench` wraps
  your command in `sh -c` for exactly this; if you build such a command by hand, do the same.

  The number is misfiled, not destroyed. rops's own wrapper captures the whole line, so a run
  that printed `wall=TIMEOUT` still has its figure: `grep -o 'WALL=[0-9.]*' <the .log>`.

All three have one antidote: **a positive control in the same command**. Print the collected test
count, or grep for a string you know is there. `[]` and `0` only mean something next to a
denominator.

## Measuring your own measurement

Two mistakes made while building this tool, both worth knowing:

- `rops run ... | tail -8; echo $?` reports **tail's** exit code, not rops's. That is behavior 3
  wearing a different hat, and it happened twice in one session. Redirect to a file and check
  `$?` on the bare command.
- `pkill -f "sleep 300"` matches the ssh command line carrying it, so it kills its own session
  (exit 255). Match with `pgrep -x`/`pkill -x`, or anchor on `args`.
