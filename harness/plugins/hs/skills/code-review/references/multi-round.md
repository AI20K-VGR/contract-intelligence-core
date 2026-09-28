# Multi-round committing review (N rounds + four tactical axes)

The recall engine (`references/recall-mode.md`) scales a SINGLE review pass by an effort level. This drawer adds the **multi-round** layer: run the pass N times, each round committing its safe fixes and feeding the next, under four optional tactical axes. It changes only HOW findings are produced across rounds — never the gate (verdict truth-table, dismissals, `review-decision` are untouched).

Backing decision: review-nhiều-vòng lives inside `hs:code-review`/recall-mode (no new skill). Config: `"${HARNESS_BIN_ROOT:-.}"/harness/data/review-policy.yaml` (profiles + caps), read via `"${HARNESS_BIN_ROOT:-.}"/harness/scripts/review_policy_config.py`.

## Profiles

A **profile** names a round count + effort + the four axes. Three ship:

| Profile | rounds | effort | compounding | per_aspect | blind_main_sub | refute | scope |
|---|---|---|---|---|---|---|---|
| `default` | 1 | low | off | off | off | off | diff |
| `thorough` | 3 | high | on | on | off | on | diff |
| `ship-grade` | 3 | max | on | on | on | on | project |

`default` == today's single low pass — non-breaking. Resolve a profile with `review_policy_config.resolve_profile(name, policy)`; an unknown name falls back to `default`. Map it to a recall breadth with `review_recall.resolve_profile_breadth(profile)` → `{fan_out, lenses, verify, sweep, rounds, compounding, per_aspect, blind_main_sub, refute, aspects, scope}`.

## The round loop

For each round `1..rounds`:

1. **Fan-out** the resolved `lenses` independent finder lenses over the scope.
2. **Verify** confirmed findings per the level's `verify` strategy (and `refute` below).
3. **Fix** the auto-fixable findings (`hs:fix`, red→green) and commit — this is the "committing" in committing-review.
4. **Classify** the remaining findings: a `needs-user` finding (contract / threshold / scope / schema / pricing / compliance / trade-off) is NOT auto-fixed — route it per `references/issue-routing.md` (BACKLOG + report link when headless, AskUserQuestion when interactive).
5. Carry forward to the next round per the axes.

Count the rounds actually run as **`rounds_run`** — Phase-3's stamp writes it onto `review-decision` (see `references/verdict-and-artifact.md` → optional recall stamp).

## The four axes

- **`compounding`** (on for thorough/ship-grade): the previous round's findings + applied fixes become context for the next round, so each round scans deeper and does not re-surface what was already fixed.
- **`per_aspect`**: rotate a single aspect per round (security → DRY → correctness → consistency …) from `profile.aspects`, instead of sweeping every aspect each round. Cheaper, and each round goes deep on one lens.
- **`blind_main_sub`**: the sub-agent payload is built by
  `review_recall.blind_payload(scope, artifact_path)` — scope + artifact path ONLY, never the main's findings (a sealed-room re-derivation, like `hs:independent-revalidator`). The absence of a findings key IS the blind guarantee.
- **`refute`**: the verify round runs a skeptic that defaults to `refuted=true` when unsure — reuse the existing adversarial-verify mechanism. A finding survives only if it is not refuted.

## Caps (token ceiling)

`review-policy.yaml.caps` bounds `rounds × lenses`: `caps = {max_rounds: 5, max_lenses_per_round: 8}`. Apply it with `review_recall.round_budget(rounds, lenses, caps)` → `{rounds, lenses, capped}`. This is a **boundary the model honors** (and the helper clamps the numbers deterministically); there is no runtime guard intercepting each lens invocation — that would be a guard for a non-boundary
(see `recall-mode.md` on why recall adds no runtime guard).

## Per-run overrides

`--profile <name>` and `--rounds <n>` override per run. Precedence, highest first: explicit arg > `review-policy.yaml` profile > `default`. `--rounds` is clamped to `caps.max_rounds` via `round_budget` — a `--rounds 9` request runs at most 5.
