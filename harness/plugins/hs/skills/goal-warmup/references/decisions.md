# Goal Warmup v1 decisions

Locked product defaults for implementers and runtime skill text.

| ID | Decision | Default |
|----|----------|---------|
| D1 | Public name | `hs:goal-warmup`; no second skill export |
| D2 | Contract persistence | Session + handoff packet only |
| D3 | Fast path | Only when user accepts reduced assurance AND no external deps/credentials/deploy/approval signals AND task looks local-only |
| D4 | Preflight | Portable baseline first (`command -v`, env presence, config shape, safe identity). Adapter extensions optional. |
| D5 | Handoff | Reviewable copy/paste Markdown; one long-run opener template; no provider context injection claim |
| D6 | Skill dependency | Depends on `hs:advise` + `hs:plan`; unavailable if either is disabled for this install |
| D7 | Red-team | Warmup-local outcome-preserving mode only; do not change `hs:plan`'s red-team files |
| D8 | Decision disposition | This harness's DEC ledger process; no standalone ADR file |

## Abort rules

- Auto-start of the long run
- Silent outcome/scope mutation after contract approval
- Secret values in any artifact
- Mutating/chargeable third-party probes by default
