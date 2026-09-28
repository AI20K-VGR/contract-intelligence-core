#!/usr/bin/env python3
"""plan_graph.py — read a plan's machine-readable phase-DAG sidecar and derive
advisory findings (cycles, ordering hazards, parallel batches + file conflicts).

Single responsibility: parse the sidecar + delegate cycle detection + derive read-only
findings. It NEVER edits the plan — option D / red line #4: detection only, no AI auto-fix
after approval. The sidecar `plans/<slug>/plan-graph.yaml` carries ONLY edges + per-phase
file ownership, never status (status lives mutable in plan.md's `## Phases`).

Edge direction is pinned: ``{from: A, to: B}`` means "A runs BEFORE B" (A is B's
prerequisite). build_adj maps that semantics explicitly rather than reusing graph_core's
children_of/parents_of, which read the opposite way.

Parallelism is DERIVED, never authored: a parallel batch is a topological level (an
antichain — phases with no edge between them). But an edge alone lies about parallelism in
a file-based harness: the real blocker is usually a shared file, not a logical dependency.
So a safe parallel batch is an antichain AND a pairwise-disjoint file set; find_parallel_
conflicts turns the prose "shared-file" warning into a machine finding.

Each node MUST declare a `post:` artifact obligation. A missing/malformed
`post` is a structural contract violation, not a heuristic advisory: find_missing_post +
the CLI hard-fail (exit 2, both modes) refuse it at validate + cook-preflight time. The
node_artifacts default is only a runtime backstop for an already-approved graph.
"""
import sys
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve()
if str(_HERE.parent) not in sys.path:
    sys.path.insert(0, str(_HERE.parent))
import graph_core  # noqa: E402

_SIDECAR = "plan-graph.yaml"


def parse_phase_graph(plan_dir) -> dict:
    """Load the sidecar. Returns the parsed mapping, or ``{"error": <msg>}`` on a
    malformed file — never raises (a planner-facing finding, not a crash)."""
    import yaml_io
    path = Path(plan_dir) / _SIDECAR
    if not path.is_file():
        return {"error": "no %s in %s" % (_SIDECAR, plan_dir)}
    try:
        data = yaml_io.safe_load(path.read_text(encoding="utf-8"))
    except yaml_io.YAMLError as exc:
        return {"error": "malformed %s: %s" % (_SIDECAR, exc)}
    if not isinstance(data, dict):
        return {"error": "%s is not a mapping" % _SIDECAR}
    # Normalize EMPTY, reject WRONG-TYPED — two different inputs that used to collapse
    # into the same answer.
    #
    # Absent, or present with an empty value (`edges:` on its own), parses to None. That
    # is a legitimately empty sidecar — a single-phase plan has no edges — so it is
    # coerced and callers always see list/dict. setdefault would not do it: the key is
    # present, its value is just None.
    #
    # A wrong-typed value (`subtasks:` authored as a LIST, a scalar, …) is corruption and
    # must surface as a finding. It used to be coerced too, and the cost was not
    # cosmetic: with the graph silently discarded, `--require` printed
    # "parallel batches: []" and exited 0, so the cook preflight accepted a plan whose
    # phase graph it had thrown away — while the SAME corruption authored in mapping form
    # exited 2 via the missing-post check. The gate's verdict depended on which wrong
    # shape the author happened to write.
    #
    # Returned as {"error": ...} rather than raised, matching this function's contract
    # (a planner-facing finding, never a crash). Advisory mode still exits 0 on it;
    # --require is the door that says no. Do NOT "simplify" this back to a truthiness or
    # isinstance-else-default check — that erases the distinction again. See
    # test_plan_graph.py, the empty-vs-wrong-typed block.
    for key, want, want_label in (("edges", list, "a list"),
                                  ("subtasks", dict, "a mapping")):
        val = data.get(key)
        if val is None:
            data[key] = want()
        elif not isinstance(val, want):
            return {"error": "%s: `%s:` must be %s, got %s"
                             % (_SIDECAR, key, want_label, type(val).__name__)}
    return data


# ---------------------------------------------------------------- adjacency ---

def _all_nodes(graph: dict) -> set:
    nodes = set(graph.get("subtasks", {}) or {})
    for e in graph.get("edges", []) or []:
        nodes.add(e.get("from"))
        nodes.add(e.get("to"))
    nodes.discard(None)
    return nodes


def build_adj(graph: dict) -> dict:
    """edges → adjacency with the plan's own direction: {from: [to, ...]}.
    Every node is a key (targets get an empty list) so cycle detection sees them."""
    adj = {n: [] for n in _all_nodes(graph)}  # every node is a key (incl. pure targets)
    for e in graph.get("edges", []) or []:
        src, dst = e.get("from"), e.get("to")
        if src is not None and dst is not None:
            adj[src].append(dst)  # src is already a key via _all_nodes
    return adj


def find_cycles(graph: dict) -> list:
    return graph_core.find_dep_cycles(build_adj(graph))


# ------------------------------------------------------------ file ownership ---

def _subtask(graph: dict, phase: str) -> dict:
    """The subtask mapping for a phase, coerced to a dict — a non-dict / scalar value
    from a hand-edited sidecar yields {} instead of raising AttributeError downstream
    (keeps the 'never raises' contract)."""
    st = (graph.get("subtasks", {}) or {}).get(phase)
    return st if isinstance(st, dict) else {}


def _files(graph: dict, phase: str, *keys) -> set:
    """The file paths a phase declares under `keys`, coerced the same way
    `_subtask` coerces a non-dict subtask — a hand-edited sidecar is the input
    here, and this module's contract is never to raise.

    The value must be a SEQUENCE of strings. Written as a bare scalar
    (`files_to_modify: harness/tests/test_x.py`, no list dash) `set()` iterated
    it character by character, and two phases sharing that path reported
    conflicts on the letters 'x' and 'y' — the operator is sent to serialize
    phases over a collision that does not exist, which is worse than silence.
    A non-string scalar raised TypeError straight through the contract."""
    st = _subtask(graph, phase)
    out = set()
    for k in keys:
        val = st.get(k)
        if isinstance(val, (list, tuple, set)):
            out |= {v for v in val if isinstance(v, str)}
    return out


def _owned(graph: dict, phase: str) -> set:
    return _files(graph, phase, *_OWNERSHIP_KEYS)


# The keys anything actually READS out of the sidecar. Kept next to the readers so
# adding a key without adding it here is a visible edit, not a silent one — the
# unread-key lint below is only as honest as this list.
_OWNERSHIP_KEYS = ("files_to_create", "files_to_modify", "files_to_delete")
_SUBTASK_KEYS = frozenset(_OWNERSHIP_KEYS) | {
    "post",           # artifact obligation (node_artifacts)
    "status",         # not read here, but it has its own dedicated warning below
    "paused",         # is_paused -> out of the batch, denominator, snapshot sweep
    "paused_reason",  # printed by the lint; a pause without one is a finding
    "reopen_when",    # printed alongside the reason, purely for the reader
}


def is_paused(graph: dict, phase: str) -> bool:
    """True when a phase is deliberately on hold.

    A paused phase leaves three counters at once — the parallel batch (do not hand
    it out as runnable work), the completion denominator (do not hold the plan open
    for it), and the stage gate's snapshot sweep (do not demand a verification it
    was never going to write). All three read THIS function, so they cannot drift
    into three different answers the way they did when nothing read the flag.

    Unknown phase -> False. Answering "paused" about a phase there is no record of
    would silently drop a real one out of every count.
    """
    return bool(_subtask(graph, phase).get("paused"))


def paused_phases(graph: dict) -> set:
    return {p for p in _all_nodes(graph) if is_paused(graph, p)}


def pause_note(graph: dict, phase: str) -> str:
    """One human sentence for a paused phase, for whoever reads a count that got
    smaller. Empty when the phase is not paused."""
    st = _subtask(graph, phase)
    if not st.get("paused"):
        return ""
    reason = str(st.get("paused_reason") or "").strip() or "no reason given"
    note = "%s is paused (%s)" % (phase, reason)
    reopen = str(st.get("reopen_when") or "").strip()
    if reopen:
        note += "; reopens when: %s" % reopen
    return note
_TOPLEVEL_KEYS = frozenset({"edges", "subtasks", "status"})
_EDGE_KEYS = frozenset({"from", "to", "status"})


# ------------------------------------------------------- artifact obligation ---
# A node declares its end-of-phase artifact obligation as `post: [name, ...]`.
# This is the SAME obligation the derive counter (derive_plan_completion) already
# assumed implicitly (node -> verification-<node>.json); naming it here makes it a
# single declarative source the counter reads, instead of a hard-coded prefix. No
# `pre` this round (deferred — schema leaves room, nothing reads it yet).

def _str_list(v):
    """v as a list of non-empty str, or [] when v is anything else (scalar, dict,
    a list containing a non-str). Lets a malformed `post` degrade to the default
    rather than raise — same 'never crash on a hand-edited sidecar' contract."""
    if isinstance(v, list) and v and all(isinstance(x, str) and x for x in v):
        return list(v)
    return []


def node_artifacts(graph: dict, node: str) -> dict:
    """The node's declared artifact obligation: ``{"post": [str, ...]}``.

    RUNTIME reader (derive_plan_completion / artifact_check call it on an already
    *approved* graph). It keeps a defensive default = ``["verification-<node>.json"]``
    when `post` is unstated/malformed, so a node that slipped through resolves instead
    of crashing cook. This default is NOT an authoring allowance: `find_missing_post`
    + the `_main` gate refuse a missing/malformed `post` at validate + cook-preflight
    time, so a graph that reaches the runtime always has explicit
    post. `pre` is deferred: this reader never returns a "pre" key even if authored."""
    st = _subtask(graph, node)
    post = _str_list(st.get("post")) or ["verification-%s.json" % node]
    return {"post": post}


def find_missing_post(graph: dict) -> list:
    """Nodes (sorted) that do NOT declare an explicit, valid ``post`` — the MANDATORY
    end-of-phase artifact obligation. "Missing" covers no subtask entry, no
    `post` key, and a malformed `post` (not a non-empty list-of-str). The `_main` gate
    turns a non-empty result into a hard exit-2 refusal; the node_artifacts default
    still backstops the runtime so this is an authoring gate, not a runtime crash."""
    return sorted(n for n in _all_nodes(graph)
                  if not _str_list(_subtask(graph, n).get("post")))


def _created(graph: dict, phase: str) -> set:
    return _files(graph, phase, "files_to_create")


def _modified_or_deleted(graph: dict, phase: str) -> set:
    return _files(graph, phase, "files_to_modify", "files_to_delete")


def find_ordering_hazards(graph: dict) -> list:
    """For each edge A→B, flag a file the prerequisite A modifies/deletes that the
    dependent B newly creates — A would touch a file that does not exist yet."""
    out = []
    for e in graph.get("edges", []) or []:
        a, b = e.get("from"), e.get("to")
        if a is None or b is None:
            continue
        shared = _modified_or_deleted(graph, a) & _created(graph, b)
        for f in sorted(shared):
            out.append({"prereq": a, "dependent": b, "file": f,
                        "msg": "%s modifies/deletes %s that %s only creates later"
                               % (a, f, b)})
    return out


# --------------------------------------------------------------- parallelism ---

def _bridge_paused(adj: dict, paused: set) -> dict:
    """Remove paused nodes from an adjacency map, reconnecting around them.

    Transitive: a chain of two paused phases still joins its live ends. Self-edges
    that the bridge would create are dropped — a node depending on itself is a cycle
    the caller would report as corruption.
    """
    if not paused:
        return adj

    def _live_successors(node, seen):
        out = set()
        for d in adj.get(node, []):
            if d in paused:
                if d in seen:
                    continue          # a cycle among paused nodes: stop, do not loop
                out |= _live_successors(d, seen | {d})
            else:
                out.add(d)
        return out

    bridged = {}
    for n in adj:
        if n in paused:
            continue
        bridged[n] = sorted(_live_successors(n, {n}) - {n})
    return bridged


def find_parallel_batches(graph: dict) -> list:
    """Topological levels (Kahn). Each level is an antichain — a batch that may run
    in parallel. Returns levels as sorted name lists.

    Paused phases are dropped, and their edges are BRIDGED (every predecessor gains
    every successor). Dropping the node alone would leave a downstream phase waiting
    on a dependency that never resolves — a plan that can never finish, which is a
    worse answer than scheduling the paused work.
    """
    adj = _bridge_paused(build_adj(graph), paused_phases(graph))
    indeg = defaultdict(int)
    for src, dsts in adj.items():
        indeg.setdefault(src, indeg.get(src, 0))
        for d in dsts:
            indeg[d] += 1
    remaining = dict(indeg)
    batches = []
    while remaining:
        level = sorted(n for n, d in remaining.items() if d == 0)
        if not level:  # a cycle remains — stop deriving batches
            if remaining:
                print("plan-graph: cycle detected — %d nodes unreachable: %s" %
                      (len(remaining), ", ".join(sorted(remaining))),
                      file=sys.stderr)
            break
        batches.append(level)
        for n in level:
            del remaining[n]
            for d in adj.get(n, []):
                if d in remaining:
                    remaining[d] -= 1
    return batches


def find_parallel_conflicts(graph: dict) -> list:
    """In any batch of ≥2 phases, flag a file two phases both own — parallel edits
    of a shared path clobber. The machine form of the prose 'shared-file' warning."""
    out = []
    # find_parallel_batches already drops paused phases, so a paused phase cannot
    # appear here — it is not running, so it cannot clobber a file, and warning about
    # it would be noise that trains the reader to skip the real conflicts.
    for batch in find_parallel_batches(graph):
        if len(batch) < 2:
            continue
        for i in range(len(batch)):
            for j in range(i + 1, len(batch)):
                a, b = batch[i], batch[j]
                shared = _owned(graph, a) & _owned(graph, b)
                for f in sorted(shared):
                    out.append({"phases": [a, b], "file": f,
                                "msg": "%s ∥ %s both touch %s — serialize or split "
                                       "ownership" % (a, b, f)})
    return out


def _unread(present, known, where: str) -> list:
    """Warn about keys nobody reads. A sidecar key that no reader consumes is
    invisible in both directions: it changes nothing, and nothing says so — the
    author has every reason to believe it took effect. Measured instance: a plan
    carried `paused: true` + `paused_reason` + `reopen_when`, the phase stayed in
    the parallel batch and in the completion denominator, and not one line was
    printed. This warns on the CLASS, so it also catches the next invented key."""
    extra = sorted(k for k in present if k not in known)
    if not extra:
        return []
    return ["%s: unread key(s) %s in %s — nothing consumes them, so they change "
            "nothing. Remove them, or open an issue for the behaviour you wanted"
            % (where, ", ".join(extra), _SIDECAR)]


def lint_no_status(graph: dict) -> list:
    """A status key must not live in the sidecar (status is mutable, owned by plan.md).
    Warn — do not raise — so a stray status is surfaced, not silently hashed.

    Also warns about keys no reader consumes (see _unread)."""
    warnings = []
    if "status" in graph:
        warnings.append("top-level 'status' key in %s — status belongs in plan.md" % _SIDECAR)
    warnings += _unread(graph, _TOPLEVEL_KEYS, "top-level")
    for phase, st in (graph.get("subtasks", {}) or {}).items():
        if isinstance(st, dict) and "status" in st:
            warnings.append("subtask %s carries 'status' in %s — status belongs in "
                            "plan.md's `## Phases`" % (phase, _SIDECAR))
        # `post` is the declarative artifact obligation; a malformed value silently
        # degrades to the default in node_artifacts, so surface it here instead.
        if isinstance(st, dict) and "post" in st and not _str_list(st.get("post")):
            warnings.append("subtask %s has a malformed 'post' in %s — expected a "
                            "list of artifact names; using default "
                            "[verification-%s.json]" % (phase, _SIDECAR, phase))
        if isinstance(st, dict):
            # A pause removes a phase from three counters at once. Doing that with no
            # sentence attached is the same defect shape as a silent N/A: the number
            # got smaller and nothing on disk says why.
            if st.get("paused") and not str(st.get("paused_reason") or "").strip():
                warnings.append("subtask %s is paused with no 'paused_reason' in %s — "
                                "a pause drops the phase from the batch, the completion "
                                "denominator and the gate; say why" % (phase, _SIDECAR))
            elif st.get("paused"):
                warnings.append("subtask %s: %s" % (phase, pause_note(graph, phase)))
            # The half-edit that outlives a resume: someone cleared `paused` and left
            # the prose behind, so the sidecar READS paused to a human and does not to
            # the machine.
            if not st.get("paused") and (st.get("paused_reason") or st.get("reopen_when")):
                warnings.append("subtask %s carries pause prose but no `paused: true` in "
                                "%s — it reads as paused and is not; clear the prose or "
                                "set the flag" % (phase, _SIDECAR))
            warnings += _unread(st, _SUBTASK_KEYS, "subtask %s" % phase)
    for e in graph.get("edges", []) or []:
        if isinstance(e, dict) and "status" in e:
            warnings.append("edge %s->%s carries 'status' in %s — status belongs in "
                            "plan.md" % (e.get("from"), e.get("to"), _SIDECAR))
        if isinstance(e, dict):
            warnings += _unread(e, _EDGE_KEYS,
                                "edge %s->%s" % (e.get("from"), e.get("to")))
    return warnings


def _main(argv=None) -> int:
    import argparse
    p = argparse.ArgumentParser(description="read a plan's phase-DAG sidecar (advisory)")
    p.add_argument("plan_dir")
    p.add_argument("--require", action="store_true",
                   help="exit 2 if the sidecar is missing (cook preflight gate); "
                        "default stays advisory (exit 0) for validate-time use")
    args = p.parse_args(argv)
    graph = parse_phase_graph(args.plan_dir)
    if graph.get("error"):
        print("error: %s" % graph["error"])
        # The sidecar is a mandatory plan artifact. --require makes its absence a
        # hard cook-preflight block (exit 2); advisory mode never blocks the
        # planner mid-authoring (exit 0).
        return 2 if args.require else 0
    for w in lint_no_status(graph):
        print("status-leak: %s" % w)
    for c in find_cycles(graph):
        print("cycle: %s" % " -> ".join(c))
    for h in find_ordering_hazards(graph):
        print("ordering-hazard: %s" % h["msg"])
    batches = find_parallel_batches(graph)
    print("parallel batches: %s" % batches)
    for c in find_parallel_conflicts(graph):
        print("parallel-conflict: %s" % c["msg"])
    # `post` is MANDATORY per node. Unlike cycles/conflicts (heuristic
    # advisories), a missing `post` is a structural contract violation: HARD-fail (exit 2)
    # in BOTH advisory and --require modes so validate-time + cook-preflight both refuse it.
    missing = find_missing_post(graph)
    for n in missing:
        print("missing-post: node %s must declare 'post:' (required artifact "
              "obligation, e.g. post: [verification-%s.json])" % (n, n))
    return 2 if missing else 0


if __name__ == "__main__":
    raise SystemExit(_main())
