"""One reader for "what does this verb result say", across both spellings.

Several gates ask questions about verb results by walking the AST: which rung a
branch names, which states the CLI can emit, whether an 11 carries a runnable
command. Each grew its own `isinstance(node, ast.Dict)` loop, which was correct
while every verb returned a dict literal.

Verb results are migrating onto `StepResult(...)` — the rule this repo already
argued and won for the ledger line, the checklist row and the run context ("a
record that crosses a boundary is a DECLARED object, not a dict literal"). The
first two verbs converted went invisible to a scanner written for the old shape,
and the conformance gate reported their states as dead vocabulary while they
were still printed on every run. A detector that keeps asking the pre-migration
question answers confidently about a tree that no longer exists.

So the shape question is answered HERE, once, and the gates ask this module.
When a third spelling appears, one file learns it and every gate sees it — which
is the same argument the value objects themselves are making, applied to the
tests that police them.

Everything returned is AST NODES, not values: the callers need `.lineno` for
their messages and need to distinguish `None` written explicitly from a key that
is absent, which a normalised dict of values would erase.
"""

import ast

# Constructors whose keyword arguments carry the same meaning the dict keys did.
_RESULT_CLASSES = ("StepResult", "Envelope")


def _kwargs_of(call: ast.Call) -> dict:
    return {kw.arg: kw.value for kw in call.keywords if kw.arg}


def result_literals(tree: ast.AST):
    """Yield `(node, fields)` for every verb-result literal in `tree`.

    `node` is what carries `.lineno` for an error message; `fields` maps a field
    name to its AST value node. Three spellings are recognised:

      * `return {...}`            — the original, still the majority
      * `name = {...}`            — built, conditionally amended, returned later.
        This one hid a real branch from an earlier sweep: `not_approved` was
        assembled this way, so a scan that walked only `ast.Return` reported the
        file clean while the branch it could not see was the one that mattered.
      * `StepResult(...)` / `Envelope(...)` — the value-object form.

    A dict without `state` is not a verb result — `hs_run_review_pr.py` builds
    per-CI-check records shaped `{"name": ..., "state": ...}`, and callers that
    care filter further on `next_action`, which every verb result carries and no
    inner record does."""
    for node in ast.walk(tree):
        if isinstance(node, (ast.Return, ast.Assign)) and isinstance(node.value, ast.Dict):
            fields = {k.value: v for k, v in zip(node.value.keys, node.value.values)
                      if isinstance(k, ast.Constant) and isinstance(k.value, str)}
            if "state" in fields:
                yield node, fields
        elif isinstance(node, ast.Call):
            name = getattr(node.func, "attr", getattr(node.func, "id", None))
            if name in _RESULT_CLASSES:
                fields = _kwargs_of(node)
                if "state" in fields:
                    yield node, fields
                continue
            # A result dict passed as an ARGUMENT: `finalize({...})`. The whole
            # ship domain is spelled this way, so every gate reading through
            # here saw zero results in it and passed by finding nothing — which
            # looks exactly like passing by being clean. Any callee is accepted
            # rather than a name list: what makes this a verb result is the
            # `state` key, and a list of wrapper names would need editing every
            # time somebody adds one, silently exempting the module until then.
            for arg in list(node.args) + [kw.value for kw in node.keywords]:
                if not isinstance(arg, ast.Dict):
                    continue
                fields = {k.value: v for k, v in zip(arg.keys, arg.values)
                          if isinstance(k, ast.Constant) and isinstance(k.value, str)}
                if "state" in fields:
                    yield node, fields


def rung_named(fields: dict):
    """The identifier a result names as its rung (`"EXIT_BROKEN"`), or None.

    Returns the NAME, not a value: these modules spell the ladder through
    constants, and resolving them here would mean re-implementing the import
    graph in a test helper. A literal int (a fixture, mostly) comes back as its
    own repr so a caller can still tell "stated" from "absent"."""
    node = fields.get("exit_code")
    if node is None:
        return None
    if isinstance(node, ast.Name):
        return node.id
    if isinstance(node, ast.Attribute):
        return node.attr
    if isinstance(node, ast.Constant):
        return repr(node.value)
    return "<computed>"


def states_named(fields: dict, scope=None):
    """Every literal state a result can carry, descending into conditionals.

    `"opened" if res.changed else "already_open"` is one return and two states;
    a scan that reads only `ast.Constant` sees neither.

    `scope` — the enclosing function — lets a state that was assigned to a local
    first be resolved. `hs_run_plan.py`'s `graph` verb writes
    `state = "absent" if not sidecar.is_file() else "malformed"` and passes the
    NAME, and without this all four of that verb's states are invisible: a
    routing audit then reported the domain fully covered while four live states
    had no row. Only same-name literal (or conditional-of-literals) assignments
    in that function are followed — anything computed stays unresolvable, which
    is honest, and callers that care assert on the count."""
    out = set()

    def walk(node, depth=0):
        if isinstance(node, ast.Constant) and isinstance(node.value, str):
            out.add(node.value)
        elif isinstance(node, ast.IfExp):
            walk(node.body, depth)
            walk(node.orelse, depth)
        elif isinstance(node, ast.Name) and scope is not None and depth == 0:
            # depth-guarded: follow a name ONCE, so a pair of locals assigned
            # from each other cannot walk forever.
            for assign in ast.walk(scope):
                if not isinstance(assign, ast.Assign):
                    continue
                for tgt in assign.targets:
                    if isinstance(tgt, ast.Name) and tgt.id == node.id:
                        walk(assign.value, depth + 1)

    walk(fields.get("state"))
    return out


def engine_overlay_states(domain, engine_src=None, scope=None):
    """States the ENGINE writes over a domain's answer, for the gates that scan a
    domain module and would otherwise call them phantom rows.

    `hs_run` rewrites a repeated answer into `stuck` before the envelope is built.
    That state is real, routed, and reaches the reader — but it is emitted by the
    engine, so every reader that source-scans `hs_run_<domain>.py` reports it as
    routed-but-never-returned. The choice is between teaching those readers about
    the one overlay seam and moving the overlay into six domain modules, which is
    the copy the seam exists to prevent.

    Derived, never listed. The names come from source-scanning the overlay
    function, and the scope comes from the declared policy — so deleting the
    overlay empties this set and a `stuck` row goes red again, and dropping a
    domain from the policy makes that domain's row go red while the others stay.
    A hard-coded `{"stuck"}` would survive both and turn a live gate into a
    decoration."""
    from pathlib import Path

    src = Path(engine_src) if engine_src else Path(__file__).resolve().parent / "hs_run.py"
    if not src.is_file():
        return set()
    names = set()
    for fn in ast.walk(ast.parse(src.read_text(encoding="utf-8"))):
        if not isinstance(fn, ast.FunctionDef) or fn.name != "_apply_escalation":
            continue
        for node in ast.walk(fn):
            if isinstance(node, ast.Assign) and any(
                    isinstance(t, ast.Subscript)
                    and isinstance(t.slice, ast.Constant) and t.slice.value == "state"
                    for t in node.targets):
                names |= states_named({"state": node.value}, scope=fn)
    if not names:
        return set()
    if scope is None:
        import hs_run
        scope = hs_run.escalation_policy()["domains"]
    return names if domain in set(scope) else set()
