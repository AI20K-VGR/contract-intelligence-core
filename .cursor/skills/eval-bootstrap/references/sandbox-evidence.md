# Sandbox evidence — the R9 gate

Every LLM-generated code-fill lands in the repo only after it runs for real in a
jail and a human reads the proof. This is the L3 lock: `sandbox_run.py` executes,
never you. Full jail mechanics (layers, kill order, comparator table) live in
`sandbox_run.py`'s own module docstring — this drawer is the per-fill workflow
around it: which fill goes through, the exact command, the approval gate, what
each exit code means at that gate, and the two falsifiable rules (eval-turn,
resume) that keep the gate honest across turns.

## 1. Which fills go through R9

| Fill | Where it lands | Suggested `--entry` |
|---|---|---|
| pipeline_mirror fill | `evals/eval_types/<domain>/pipeline_mirror.py` | `run_pipeline` |
| score_dimension fill | `evals/eval_types/<domain>/scorer.py` | a single-arg wrapper — see **entry arity** below |
| check_p0_gates body | `evals/eval_types/<domain>/scorer.py` | `check_p0_gates` |
| a new normalizer/mask profile | `evals/eval_types/<domain>/runner.py` (registered in `NORMALIZERS`/`MASKS`) | the new function's own name |
| (wave 2) target-language mirror | `evals/eval_types/<domain>/pipeline_mirror.<ext>` | the mirror's entry symbol |

Every row above is a judgment-adjacent fill (L2 table, `plan.md` §0.3) — code you
generated, not a value the user typed on the card. That is exactly the class R9
gates.

**Entry arity (important).** The jail invokes the entry as `entry_fn(case_input)` —
exactly ONE per-case argument. `run_pipeline`/`run` and `check_p0_gates` each take
a single argument, so they R9-gate directly. `score_dimension(dimension_name,
results)` takes TWO, so `--entry score_dimension` would raise `TypeError` on every
case (a dead end — exit 0 is unreachable). To gate the scoring logic, add a
single-arg shim beside it in `scorer.py` and point `--entry` at THAT:

```python
def score_dimension_probe(case_input):        # single-arg R9 entry
    return score_dimension("<dimension>", [case_input])
```

so the scanned + jailed bytes are exactly the ones that run.

## 2. The real command

Copied verbatim from `sandbox_run.py --help`:

```
python3 sandbox_run.py --fill <fill.py> --entry <func> \
    --config <eval_config.json> [--case-timeout 10] \
    --evidence-out <path.json> [--extra-file name=path ...]
```

Evidence path convention: `evals/_sandbox_evidence/<fill>-<ts>.json` (e.g.
`evals/_sandbox_evidence/scorer-20260714T101500Z.json`) — sandbox evidence is
the proof that a generated fill actually ran inside the jail and passed. The
directory name is **self-explaining on purpose**: it travels with the generated
evals into the consuming repo, whose reader never saw this skill's internal
R1–R9 gate table. Evidence is **tracked by default** — a feature, not a
leftover: the team gets to see that proof, not just a claim in a commit message.
The user decides whether to keep or prune old evidence files; nothing here
forces it into `.gitignore`.

**Naming rule (general):** any internal name — an R-number, a gate code, a
phase label — that reaches an artifact in the CLIENT / target repo MUST be
self-explanatory on its own, or carry its dictionary with it (e.g. a print line
that names `hs:eval-bootstrap`). The internal R1–R9 vocabulary stays inside this
skill; it does not travel unglossed.

## 3. The approval gate

Present, via **AskUserQuestion** with exactly 3 choices, the stdout prose table
`sandbox_run.py` prints (fill/entry/containment/card_hash + the case→result
rows) plus the card hash and a one-line summary:

1. **Approve** — the fill lands in the repo.
2. **Add guidance** — the user's note is appended to tier-2 memory as a
   `standard` (cross-repo lesson, via the tier-2 memory store —
   `eval_memory.py append`); the fill is rewritten and re-run through R9.
3. **Reject** — the fill is discarded and rewritten from scratch.

Until approved, the fill does **not** land in the repo — it lives only at the
temp sandbox path `sandbox_run.py` created and tears down after evidence is
collected. "Landing" is a distinct, later step: after approval, the model
copies the approved fill's content into the real `evals/` tree. R9 never
writes into `evals/` itself; it only proves and reports.

## 4. Exit-code semantics at the gate

`sandbox_run.py` ships five exit codes; the gate treats them differently:

| Exit | Meaning | At the R9 gate |
|---|---|---|
| 0 | every case (matrix + edge set) PASSed | the only code presented for approval |
| 1 | at least one case FAILed/CRASHed/TIMEDOUT | never presented as "intentional" — go back and fix the fill, or fix the case matrix via a fresh R7 if the matrix itself was wrong |
| 2 | input error (`--fill`/`--config` missing or malformed) | fix the invocation, not the fill; re-run |
| 3 | denylist refuse (fill never executed) | rewrite the fill without the flagged construct; re-run |
| 4 | containment_error (the jail infra itself is broken) | fix the environment (bwrap missing/broken), not the fill; do not retry the fill as-is |

A failing case (exit 1) is **never** approved as "intentional" — there is no
override, no "approve with known failures" path. The card's case matrix is the
sole source of what counts as correct; if a case should not have been in the
matrix, that is a card change, which means back to R7, not a rubber stamp here.

## 5. The eval-turn rule (verbatim, falsifiable)

> An autonomous turn that meets an unfilled judgment blank or a missing fill
> MUST fail with instructions to re-run the human bootstrap; it never fills
> the blank itself.

This is what keeps L1 honest after bootstrap: a CI run, a goal-loop, any turn
without a human at the keyboard is not a place a new judgment call or a new
fill can be minted. It fails loud and points back to the human-in-the-loop
protocol.

## 6. Resume — explicit on card_hash

Before re-asking about a fill, recall prior approval decision records filtered
by domain **and the CURRENT card hash** (`eval_config.py hash`). Verbatim:

> resume only reuses a fill when the record's card hash equals the current
> card hash; a mismatch means the card's criteria changed, so the old fill is
> void and it re-asks.

This closes the silent-reuse hole: a fill approved against an old card's
dimensions/threshold/case-matrix must never be treated as still-valid once the
card has changed underneath it. A decision record (persisted by the memory
step described later) is how resume knows what was already approved and
against which card — described here in words only, since the concrete store
and its recall command do not exist yet at this point in the build.

## 7. Honesty — jail vs best-effort pre-filter

When OS containment (`bwrap`/`unshare`) is active, calling the result a "jail"
is accurate — a real OS-level sandbox boundary. When containment falls
back to the python-level filter (bubblewrap absent, macOS, Windows), the
evidence stamps `containment: python-filter-fallback` and the runner prints a
loud warning; call that mode exactly a **"best-effort pre-filter"**, never a
"real jail". The static denylist scan underneath the fallback is theoretically
evadable (`os.posix_spawn`, string-built `getattr` chains, and similar). The
final gate in either mode is a human reading this evidence — not a claim that
the sandbox is unbeatable.
