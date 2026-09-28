# Scope and contract discipline (on-demand)

Load when `hs:plan` writes the scope-boundary fact (Understand step, "what is explicitly
OUT this round") and the design-contract step (a change that touches an existing public
surface — API, CLI, schema, contract).

### Not-Doing empty-list

An empty "explicitly OUT this round" answer is a PUSH-BACK TRIGGER, not a pass — scope
is never truly unbounded. Ask: "are you truly excluding nothing?" before accepting an
empty Not-Doing list; a real answer almost always excludes something (a platform, a
migration path, a performance tier) even on a narrow task.

### contract-delta template

When a design changes an existing contract (public function signature, API shape, CLI
flag, schema field), record the delta in 4 fields: **before** (the current shape) ·
**after** (the new shape) · **who-affected** (which callers/consumers break or must
adapt) · **migration-path** (how an existing caller moves from before to after).
Skipping any of the 4 fields leaves a caller to discover the break at runtime instead of
in the plan.

## Examples

IN: Not-Doing answer "not supporting bulk-delete this round, not touching the admin
API" -> accepted, concrete exclusions named.
OUT: Not-Doing answer "" (nothing) accepted at face value -> the push-back question
("are you truly excluding nothing?") was skipped; re-ask before finalizing scope.
