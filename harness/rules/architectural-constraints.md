# Architectural constraints (on-demand)

Load during `hs:plan`'s constraint-scan step — two invariants the harness's whole
verification apparatus rests on. Both are framed as invariants to design AROUND,
not a TODO to eventually fix.

### model opacity

Verification cannot inspect what a model "understood" or "intended" mid-run — only
what it DID (files touched, commands run, artifacts written). Design consequence:
every verification mechanism in this harness rests on external, re-derivable
evidence (a `file:line`, a test result, a diff) — never on trusting a model's
self-report of its own reasoning. `harness/rules/verification-mechanism.md` is the
evidence contract this constraint grounds.

### presence gate blindness

A gate that checks an artifact exists and matches schema cannot tell WHO produced
it or whether its content is honest — see the "Three honest truths" in
`harness/rules/harness-contract.md:26-31` (do not restate them here). Design
consequence: this is why the harness pairs a presence gate with an independent
reviewer/tester pass (`hs:code-review`, `hs:test`) rather than trusting the artifact
alone — an agent-authored receipt is never self-authenticating evidence of
correctness.

Both constraints are invariants of the mechanism, not gaps waiting on a future fix
— design around them; neither is solvable by a smarter prompt.
