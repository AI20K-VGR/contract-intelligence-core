# no-orphan-code — code you write is always plugged in

**When:** you are about to add a module, script, engine, hook, schema, or config key — and any time
you are about to mark work `done`, close a phase, or report a slice complete.

**Authority:** the decision ledger — search `docs/decisions.md` for "anti-orphan" and for the
per-area blocking-debt ledger ruling.

## The rule

Code that exists but that no real execution path reaches is **indistinguishable from code that does
not exist** — except that it costs review time, carries maintenance weight, and reads as coverage
that is not there. This is a standing LLM failure mode, not a rare accident: a coherent, well-tested
module gets built and then never wired.

Non-negotiable:

1. **Nothing is `done` without a real call path from a declared entry point.** Not "the function is
   written", not "the tests pass" — a path.
2. **Green tests are NOT evidence of wiring.** A test can call dead code all day. Tests prove the
   code *can run*; they do not prove it *is run*.
3. **Check REACHABILITY from an entry point, not in-degree.** "Something imports it" is the weaker
   measure and it fails on the exact shape that matters: a cluster of modules importing each other
   looks referenced from the outside, so a whole dead island passes.
4. **Declare the entry points** (driver/CLI, each hook, the installer, each skill), and give every
   exemption a machine-readable reason. An exemption list without reasons grows to hide real misses.
5. **Socket first, engine second.** The first slice of a new mechanism ADDS THE SEAM — a phase, a
   hook registration, a call site — pointing at a function that does not exist yet, so the test goes
   RED, and only then do you build. This is red→green applied to the *wiring*, not just the function.
6. **Cannot wire it yet ⇒ say so out loud:** a residual entry with verdict `UNVERIFIED`, plus a line
   in the owning area's blocking-debt ledger. Never `done`.

## The check to run before claiming done

For Python modules under `harness/`, the walk is mechanical and already runs:
`harness/tests/test_module_reachability.py`. It seeds from the DECLARED entry points and
follows four channels — plain imports, the hook registry, the `hs-run` registry, and module
names spelled as string literals for dynamic import. Run it; do not re-derive it by hand.

Read its docstring before extending it: each of those four channels was added because
leaving it out produced a confident wrong answer (missing the string-literal channel alone
reported the whole `lens_*` family dead, and a package-graph tool reported 207 of 222 scripts
orphaned because this repo imports flat, not by package path).

For anything the guard does not cover — a schema, a config key, an asset, a non-Python file —
walk the graph from each declared entry point yourself. Anything unreached is orphaned. Do not
substitute a grep for a name: a name in a comment, a docstring, or another orphan's import is not a
call path.

Three properties the check must have, each one learned from a real miss:

1. **Build the reference set MECHANICALLY from source, never from a hand-typed list.** A hand-list
   shares the exact blind spot it exists to catch: whoever forgets to wire a module also forgets to
   add it to the list, and the guard reports green.
2. **Make the exemption list non-self-satisfying.** If naming an asset in the guard's own
   `known_orphans` literal also removes it from the derived reference set, a declaration grants its
   own exemption and the guard proves nothing. Detect that loop and refuse it.
3. **Measure reachability, not in-degree.** Measured on a real 7-module engine: an in-degree scan
   caught 5 orphans and missed 2, because those 2 were imported only by the other five orphans.

Where a narrower version of this guard already passes — for schemas, for data assets, for config
keys — the job is to WIDEN it to code modules, not to invent a second mechanism next to it.

## Layering: core must never import an engine

The direction is one-way. Engines import core freely; **core importing an engine is forbidden**. Once
core knows an engine's name the two are welded and neither can be extracted, which is also how a
generic core stops being generic. Check it as an import-graph edge: any `core -> engine_*` edge is
red. The usual first leak is thin and looks harmless — core learning one engine's state-file path
through a config default — and that is precisely where the boundary starts to give.

## No "wire it up later" step

Deferring the wiring to a final integration step is the plan that PRODUCES orphans, so it is banned
on the same authority as the orphan itself.

Any two-tier mechanism — cheap check first, expensive path only at the boundary — reliably ships with
**the cheap half live and the expensive half never run**. Measured across three independent systems in
this repo's history, three for three, no exceptions. The expensive half has three predictive
signatures, and you can spot them before writing a line:

1. it has to **reach into a different component** (the cheap half is a self-contained pure function);
2. that component is **owned by someone else**;
3. **no gate forces it done** before the cheap half goes into use.

"Integrate it later" has all three. A roadmap with a final `merge` / `wire up` / `integrate` item has
already declared where it will break.

Therefore:

- **Never place the wiring as a step after every other slice.** There is no integration phase.
- **From its FIRST slice, a new mechanism runs through the real path** — real driver, real hook, real
  sandbox — **even if that phase only returns a stub.** A stub is legitimate; a missing seam is not.
- **The seam is exercised on every run, not once on merge day.** A socket plugged in daily has no day
  left to miss.
- **Stubs expire.** A stub is `UNVERIFIED` plus a debt line, not a resting state. A stub with no debt
  line is an orphan wearing progress as a costume.
- **Any design proposing two tiers must answer: what stops us shipping only the cheap half?** No
  answer means the design is not finished.

This is cheaper, not stricter. Wiring cost does not shrink when deferred — it just concentrates into
one payment, made when the context has gone cold and the author has moved on.

## Blocking-debt ledger

Every `UNVERIFIED` or unwired item this rule forces you to declare belongs in the owning area's
blocking-debt ledger (`DEBTS.md` at that area's root), which is heavier than `BACKLOG.md`: backlog is
"worth doing sometime", the debt ledger is "must clear before this merges into anything else". Four
fields per line — item, why it blocks, binary close condition, status. Close a line by changing its
status and pointing at evidence, never by deleting it.
