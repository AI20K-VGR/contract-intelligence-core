# Trusting this repo for shell-detector auto-fire

A standards rule may carry a **shell detector** — an arbitrary command the review-time runner executes. To stop a hostile checkout from auto-running code, a shell detector fires ONLY against a repo the operator has explicitly **trusted**. `/hs:setup` is the deliberate "this repo is mine" moment, so it is the one place that grants that trust. Installing the harness never does (a fresh clone
stays grep-only until trusted — that is the intended safe default).

As the final setup step, do this in the open (never silently):

1. State plainly: *"Trusting this repo so its standards shell-detectors may auto-fire — this grants shell-exec from rule config. It is idempotent and reversible."*
2. Run `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_cli.py trust "$(pwd)"` (the repo root). It is idempotent — re-running changes nothing. (If the operator opted into the on-PATH launcher at install, `hs-cli trust "$(pwd)"` is the same thing — but the `python3 …` form always works, so prefer it.)
3. Mention how to inspect or undo it: `python3 "${HARNESS_BIN_ROOT:-.}"/harness/scripts/hs_cli.py trust --list` shows trusted roots; deleting `~/.harness/trust.json` (or removing the entry) revokes trust. The grant is per-machine and is never written to git.

The step is best-effort: if the trust write fails (e.g. a misconfigured store path), report the warning and continue — a failed trust must not break setup.

> Caution: do NOT run `/hs:setup` on a repo you are only inspecting (a foreign checkout you downloaded
> to review). Trusting it would let its rule shell-detectors auto-fire. Trust only repos you own.
