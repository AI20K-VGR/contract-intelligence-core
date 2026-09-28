# Contract-delta — read the caller, depth-1

A **contract-delta** is a change to the *promise* a symbol makes to its callers, not just its internals. When a diff carries one, the bug is rarely in the changed function — it is in a call-site that still assumes the old promise. Reviewing the diff alone cannot see it; the obligation below makes the reviewer go look.

## Signals — the diff carries a contract-delta when it changes any of:

- **Output shape** — return type, fields added/removed/renamed, list vs scalar, wrapper added (`T` → `Result<T>`), units or encoding of the returned value.
- **Null contract** — `return null` becomes `throw` (or vice-versa); an optional return becomes mandatory; a previously non-null value can now be null.
- **Input shape** — a new **required** parameter; a parameter's type or accepted range narrowed; argument order changed; a default removed.
- **Side-effect** — a function that was pure now writes (DB, file, network, global); an effect removed that callers depended on; ordering/idempotency of an effect changed.
- **Error contract** — the exception type/code thrown changes; a previously caught error now propagates.

## Obligation (advisory — there is no automated detector)

This is **prose, not a polyglot detector**: the harness does not parse arbitrary languages to prove a contract changed. The teeth are the review checklist (`references/checklists/base.md`) and the reviewer/agent who works it. When you judge the diff carries a contract-delta:

1. **grep the call-sites** of every symbol whose contract changed — find where it is actually called, across the repo, not just in the changed file.
2. **Read the caller, depth-1** — open each *direct* caller and judge whether it still holds under the new contract. **Depth-1 only**: the direct callers, not their callers recursively. This bounds the blast radius so review does not explode the context.
3. **If a symbol has more callers than is practical to read** (say > 10), list them all, read a representative sample across distinct usage patterns, and say in the review that the rest were sampled — never silently skip them.
4. Record breakage as a finding with `file:line` evidence, like any other.

This obligation is **advisory**: it tells the reviewer where to look, it does not enforce that they did, and it never blocks a gate on its own. Calling it "enforced" when only a human/agent checklist read backs it would be a false promise.
