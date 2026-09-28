#!/usr/bin/env python3
"""graph_core — domain-agnostic graph primitives shared by every artifact graph.

These helpers carry zero domain logic: the closure walk, the parent/child
adjacency build, the expected-child counter, the iterative dependency-cycle
finder, the finding-record constructor (with sentinel hygiene), the scalar
coercions, the snapshot/diff/changed-node delta math, and a reusable id-grammar
validation framework. They behave identically to the equivalents that the
verbatim product-spec port carries inline, but this module is INDEPENDENT — it
imports nothing from that port and that port imports nothing from here, so a
later change to either side cannot ripple into the other.

Two functions are parameterized so one definition serves more than one domain:
`matching_child_counts` takes the expected-child hierarchy map, and
`write_snapshot`/`diff_graphs` take the snapshot dir / scalar-field list instead
of closing over a single domain's module constants.
"""

import datetime as dt
import hashlib
import json
from collections import defaultdict
from pathlib import Path
from typing import Any, Dict, List, Optional, Set, Tuple


# ── adjacency ────────────────────────────────────────────────────────────────

def _closure(adj: Dict[str, List[str]], start: str) -> Set[str]:
    """Transitive closure of `start` over an adjacency map via an iterative stack.

    Excludes `start` itself so a self-edge (start->start) or a cycle that loops
    back to start never reports a node as its own descendant. Iterative, so a
    long chain or a cycle terminates without recursion."""
    out: Set[str] = set()
    stack = list(adj.get(start, []))
    while stack:
        n = stack.pop()
        if n in out:
            continue
        out.add(n)
        stack.extend(adj.get(n, []))
    return out - {start}


def children_of(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """parent id -> list of child ids (the forward adjacency). Edge convention:
    `to` is the parent, `from` is the child (see each builder's build_edges)."""
    out: Dict[str, List[str]] = defaultdict(list)
    for e in graph["edges"]:
        out[str(e["to"])].append(str(e["from"]))
    return out


def parents_of(graph: Dict[str, Any]) -> Dict[str, List[str]]:
    """child id -> list of distinct parent ids, in edge order, str-coerced.

    Self-edges (id == id) are dropped — a node is never its own tree parent,
    which also neutralizes a self/cyclic-parent hang in any client walk."""
    out: Dict[str, List[str]] = defaultdict(list)
    for e in graph["edges"]:
        child, par = str(e["from"]), str(e["to"])
        if par != child and par not in out[child]:
            out[child].append(par)
    return dict(out)


def matching_child_counts(graph: Dict[str, Any],
                          child_type_for_parent: Dict[str, str]) -> Dict[str, int]:
    """For each parent-type node id, count inbound edges whose SOURCE node is of
    the EXPECTED child type, per the injected `child_type_for_parent` map.

    Counting only expected-type children means a stray wrong-type edge (a
    malformed graph where a rule points straight at an std_area) does not mask a
    real gap. The hierarchy map is a PARAMETER (not a module constant) so one
    definition serves the product and standards domains alike."""
    nodes_by_id = {n["id"]: n for n in graph["nodes"]}
    counts: Dict[str, int] = defaultdict(int)
    for e in graph["edges"]:
        src_type = nodes_by_id.get(e["from"], {}).get("type")
        tgt_type = nodes_by_id.get(e["to"], {}).get("type")
        if tgt_type in child_type_for_parent and child_type_for_parent[tgt_type] == src_type:
            counts[e["to"]] += 1
    return dict(counts)


def _scc_tarjan(adj: Dict[str, List[str]]) -> List[List[str]]:
    """Iterative Tarjan's strongly-connected-components over `adj`.

    Deliberately duplicated (not imported) from `check_traceability._scc_tarjan`
    in the spec skill, which carries the same algorithm for the same reason: a
    plugin skill must not import this core and this core must not reach into a
    domain builder. Keep the copies in sync by hand — `test_cycle_finder_copies_
    agree` compares their ANSWERS so a divergence cannot land silently.

    Only edges landing on another key of `adj` are followed — a target absent
    from `adj` (dangling) is skipped; the dangling report is owned elsewhere.

    The prior 3-color DFS (white/gray/black) conflated "already fully
    explored" (BLACK) with "cannot possibly close a cycle": a node reachable
    only through an already-BLACK sibling branch — a diamond
    ``A->[B,C], B->D, C->D, D->A`` — never got its back-edge re-examined once
    that shared descendant (D) was marked done by the first branch explored, so
    the second branch's membership in the same cycle went unreported
    (order-dependent under-count). Tarjan's `lowlink` propagates reachability
    correctly regardless of visit order.

    Iterative (explicit frame stack), not recursive — a ~2000-deep linear
    chain cannot RecursionError."""
    index_of: Dict[str, int] = {}
    lowlink: Dict[str, int] = {}
    on_tstack: Dict[str, bool] = {}
    tstack: List[str] = []
    sccs: List[List[str]] = []
    counter = 0

    for root in sorted(adj):
        if root in index_of:
            continue
        index_of[root] = lowlink[root] = counter
        counter += 1
        tstack.append(root)
        on_tstack[root] = True
        frames: List[Tuple[str, Any]] = [(root, iter(sorted(adj.get(root, []))))]
        while frames:
            node, it = frames[-1]
            descended = False
            for nbr in it:
                if nbr not in adj:
                    continue
                if nbr not in index_of:
                    index_of[nbr] = lowlink[nbr] = counter
                    counter += 1
                    tstack.append(nbr)
                    on_tstack[nbr] = True
                    frames.append((nbr, iter(sorted(adj.get(nbr, [])))))
                    descended = True
                    break
                elif on_tstack.get(nbr):
                    lowlink[node] = min(lowlink[node], index_of[nbr])
            if descended:
                continue
            frames.pop()
            if frames:
                parent = frames[-1][0]
                lowlink[parent] = min(lowlink[parent], lowlink[node])
            if lowlink[node] == index_of[node]:
                scc: List[str] = []
                while True:
                    w = tstack.pop()
                    on_tstack[w] = False
                    scc.append(w)
                    if w == node:
                        break
                sccs.append(scc)
    return sccs


# Elementary-cycle enumeration inside one SCC is worst-case factorial in the
# SCC's size (a complete digraph on n=10 already emits ~1.1M cycles / ~1.2s;
# n=12-15 — an ordinary depends_on count — runs minutes-to-hours). The callers
# are gates that run on every check, so a hand-edited copy-paste that happens
# to produce a dense component must not be able to hang one.
#
# A node-COUNT size gate is density-BLIND: a sparse 9-node dependency ring has
# exactly one elementary cycle (trivial to enumerate) but a size gate keyed on
# `len(scc)` would reject it purely for having 9 members, and a realistic graph
# can easily have a 9+ item ring. The bound tracks actual WORK done, not node
# count, so it stays generous across the realistic range (rings/chains of tens
# of nodes enumerate in milliseconds) and trips only when the search does
# genuinely large work. Two independent trip wires, either enough to fall back
# to `_dense_scc_marker`:
#   - step budget: counts backtracking steps (neighbor visits) spent while
#     enumerating one SCC across all its `start` nodes combined. Note it bounds
#     WORK, not node count: on a very large ring whose ids sort in the SAME
#     direction the edges walk — a sequentially-numbered chain like
#     N-001 -> N-002 -> ... -> N-999 -> N-001 — each non-minimal `start`
#     re-walks an O(n) tail before dead-ending, O(n^2) total, so such a ring
#     reaches the budget at a few hundred nodes and falls to the membership
#     marker (a shuffled-id ring of the same size, whose sort order does not
#     track its edges, stays well under budget). That is a graceful precision
#     trade — full membership is still reported and still blocks the gate, not
#     a missed detection.
#   - cycle-count cap: a secondary OUTPUT-size bound, not a work bound — even a
#     search that stays inside the step budget stops emitting once a single
#     SCC's cycle count would exceed this. It is enforced by letting the search
#     run one cycle past the cap and only then declaring "more exist", so
#     hitting the cap EXACTLY is reported as complete, not capped.
#
# Both constants mirror `check_traceability`; changing one side alone is what
# `test_cycle_finder_copies_agree` exists to catch.
_MAX_SCC_STEPS = 50_000
_MAX_CYCLES_PER_SCC = 500


def _cycles_through_start(
    adj: Dict[str, List[str]], induced: Set[str], start: str, limit: int, step_budget: int,
) -> Tuple[List[List[str]], bool, int]:
    """Every elementary (simple) cycle within the subgraph induced by `induced`
    that begins and ends at `start`. Returns `(cycles, stopped_early, steps_used)`.

    Two independent trip wires can cut the search short, both reported via
    `stopped_early=True`:
      - the `step_budget` (a count of backtracking steps — one per neighbor
        examined) runs out while frames remain unexplored;
      - more than `limit` cycles would be reported — detected by letting the
        search find ONE cycle past `limit` and trimming it off, so reaching
        `limit` exactly via true exhaustion is never confused with being cut
        short. (A naive `len(cycles) >= limit` check would report capped the
        instant the Nth cycle is found, even when that Nth cycle is also the
        LAST one the search would ever find.)

    Iterative backtracking over an explicit frame stack (node,
    neighbor-iterator, path-so-far) — no recursion. Restricting `induced` to
    nodes >= `start` (by the caller) is the standard trick that lets each
    elementary cycle in an SCC be attributed to exactly one of its members (its
    lexicographically-least node), so iterating every SCC member as a `start`
    never double-reports the same cycle."""
    cycles: List[List[str]] = []
    steps = 0
    frames: List[Tuple[str, Any, List[str]]] = [
        (start, iter(sorted(set(n for n in adj.get(start, []) if n in induced))), [start])
    ]
    while frames:
        if steps >= step_budget:
            return cycles, True, steps
        node, it, path = frames[-1]
        descended = False
        for nxt in it:
            steps += 1
            if nxt == start:
                cycles.append(path + [start])
                if len(cycles) > limit:
                    return cycles[:limit], True, steps
                continue
            if nxt in path:
                continue
            if steps >= step_budget:
                return cycles, True, steps
            nbrs = iter(sorted(set(n for n in adj.get(nxt, []) if n in induced)))
            frames.append((nxt, nbrs, path + [nxt]))
            descended = True
            break
        if not descended:
            frames.pop()
    return cycles, False, steps


def _dense_scc_marker(scc: List[str]) -> List[str]:
    """A single closed-path stand-in for an SCC too combinatorially expensive to
    enumerate within budget: the sorted membership, closed like a real cycle path
    (first == last) so it still satisfies `find_dep_cycles`'s return shape, plus a
    trailing note element that a caller's `join` folds into its human-readable
    message. Reports exactly what an operator needs to act — which nodes are
    circular — without pretending to be one specific elementary path."""
    members = sorted(scc)
    return members + [
        members[0],
        "(component too complex to enumerate every elementary cycle within budget; showing membership only)",
    ]


def find_dep_cycles(adj: Dict[str, List[str]]) -> List[List[str]]:
    """Return every elementary dependency cycle in `adj` as a closed path, e.g.
    ``["A","B","A"]`` — except an SCC that blows the work/output budget (see
    `_MAX_SCC_STEPS`/`_MAX_CYCLES_PER_SCC`), which collapses to one
    `_dense_scc_marker` entry reporting membership instead of every path.

    Built on `_scc_tarjan` for COMPLETE cycle-membership (see that helper's
    docstring for the diamond case the old back-edge-per-DFS-path walk
    under-reported), then `_cycles_through_start` enumerates every elementary
    cycle inside each strongly-connected component of size > 1 (a size-1 SCC is
    a cycle only via a self-loop). `_MAX_SCC_STEPS` is a single shared budget
    spent across every `start` node of one SCC (not reset per `start`) — a
    sparse ring stays cheap across its whole scan, a dense component exhausts
    the shared budget quickly regardless of which `start` triggers it. Sorted
    iteration throughout keeps the output byte-deterministic.

    A target absent from `adj` (a dangling dependency) is skipped — it can never
    be on a cycle, and the dangling report is owned elsewhere."""
    cycles: List[List[str]] = []
    for scc in sorted(_scc_tarjan(adj), key=min):
        if len(scc) == 1:
            node = scc[0]
            if node in adj.get(node, []):
                cycles.append([node, node])
            continue
        scc_cycles: List[List[str]] = []
        capped = False
        steps_remaining = _MAX_SCC_STEPS
        for start in sorted(scc):
            induced = {n for n in scc if n >= start}
            found, stopped_early, steps_used = _cycles_through_start(
                adj, induced, start, _MAX_CYCLES_PER_SCC - len(scc_cycles), steps_remaining
            )
            scc_cycles.extend(found)
            steps_remaining -= steps_used
            if stopped_early:
                capped = True
                break
        if capped:
            cycles.append(_dense_scc_marker(scc))
        else:
            cycles.extend(scc_cycles)
    return cycles


# ── content fingerprint ───────────────────────────────────────────────────────

def _content_fingerprint(parts: List[Any]) -> str:
    """sha256 (first 8 hex) over a canonical JSON of `parts`. Deterministic: same
    parts → same hash. List order is significant (reordering a list IS a content
    change); only dict keys are sorted for stability. The generic content-hash
    primitive each domain folds its own field selection into."""
    canon = json.dumps(parts, ensure_ascii=False, sort_keys=True, default=str)
    return hashlib.sha256(canon.encode("utf-8")).hexdigest()[:8]


# ── findings ───────────────────────────────────────────────────────────────

# The two sentinel strings _scalar_id() emits for absent/malformed ids. Callers
# that present valid ids subtract these so an internal sentinel never reaches a
# user-facing finding. Single authoritative home — import, never re-literal.
ID_SENTINELS = ("<missing-id>", "<invalid-id>")


def make_finding(check_id: str, severity: str, node: Dict[str, Any],
                 detail: str, **context) -> Dict[str, Any]:
    """The single home for the finding-record constructor.

    Sentinel hygiene: when the node's id is an internal absent/malformed sentinel
    (`<missing-id>`/`<invalid-id>`), `artifact_id` is nulled and any occurrence of
    that sentinel inside the (caller-interpolated) `detail` is rewritten to the
    file path — so the internal sentinel can NEVER reach a user-facing finding."""
    nid = node.get("id")
    if nid in ID_SENTINELS:
        label = node.get("file") or "(unknown file)"
        detail = detail.replace(nid, label)
        artifact_id = None
    else:
        artifact_id = nid
    return {
        "check": check_id,
        "severity": severity,
        "artifact_id": artifact_id,
        "file": node.get("file"),
        "detail": detail,
        "context": context or None,
    }


# ── scalar coercions ──────────────────────────────────────────────────────────

def _scalar_id(v: Any) -> str:
    """Coerce a frontmatter `id` to a hashable str so it can NEVER raise when used
    as a dict key / set element. Absent → `<missing-id>`; a non-string
    (list/dict/int from a hand-edit) → `<invalid-id>`, which then fails the
    id-grammar regex and surfaces as `invalid_id` instead of crashing the gate."""
    if isinstance(v, str):
        return v or "<missing-id>"
    if v is None:
        return "<missing-id>"
    return "<invalid-id>"


def _scalar_link(v: Any) -> Optional[str]:
    """Coerce a scalar parent link to str|None at the single source. A non-string
    (list/dict from malformed YAML) → None, so build_edges and every parent
    lookup never hash an unhashable value; the now-missing parent surfaces as an
    orphan/dangling finding (fail-soft) rather than crashing the gate."""
    return v if isinstance(v, str) else None


def _as_id_list(v: Any) -> List[str]:
    """Coerce a frontmatter `depends_on` into a sorted list of id strings.

    A non-list (a bare scalar / None / mapping from malformed YAML) yields [] —
    so a build never raises on a mixed-type sorted() and never silently splits a
    bare string into characters. A wrong-artifact-type placement is surfaced
    separately by the structural checks."""
    if not isinstance(v, list):
        return []
    return sorted(x for x in v if isinstance(x, str))


# ── delta / snapshot ──────────────────────────────────────────────────────────

# The single authoritative tuple of node fields whose change between two
# snapshots makes a node "changed" for delta/impact purposes. `body_hash` is the
# body-content signal; `content_hash` additionally covers fields the body hash
# cannot see; the rest are frontmatter facts.
CHANGED_FIELDS = ("status", "scope", "moscow", "horizon", "size", "body_hash", "content_hash")


def _nodes_by_id(snapshot: Dict[str, Any]) -> Dict[Any, Any]:
    """Index a snapshot's nodes by id, SKIPPING any entry that is not a dict or has no
    'id'. The snapshot-diff functions document foreign / pre-upgrade / hand-edited
    snapshots as valid input, so an id-less or malformed node must degrade gracefully,
    never crash the delta with a KeyError."""
    return {n["id"]: n for n in (snapshot.get("nodes") or [])
            if isinstance(n, dict) and n.get("id") is not None}


def changed_nodes(current: Dict[str, Any], previous: Dict[str, Any]) -> List[str]:
    """Node ids present in BOTH snapshots whose any CHANGED_FIELDS value differs.

    A field counts as changed only when it is PRESENT on both sides and the
    values differ. A field ABSENT on one side (e.g. a hash a pre-upgrade snapshot
    predates) is treated as UNKNOWN, not a change — so the first post-upgrade
    delta does not mark every node as changed. Returns ids sorted."""
    cur = _nodes_by_id(current)
    prev = _nodes_by_id(previous)
    out: List[str] = []
    for nid in cur.keys() & prev.keys():
        c, p = cur[nid], prev[nid]
        for field in CHANGED_FIELDS:
            if field not in c or field not in p:
                continue  # unknown on one side → not a change signal
            if c[field] != p[field]:
                out.append(nid)
                break
    return sorted(out)


def diff_graphs(current: Dict[str, Any], baseline: Dict[str, Any],
                scalar_fields: tuple = (), meta_key: str = "meta") -> Dict[str, Any]:
    """Structural diff between two graph snapshots: added/removed node ids plus the
    domain scalar fields (under `graph[meta_key]`) that changed.

    The set-math is generic; the per-domain `scalar_fields` and `meta_key` are
    PARAMETERS instead of a hard-coded product field list, so one definition
    serves any domain. A domain passing `scalar_fields=()` gets added/removed
    only."""
    cur_ids = set(_nodes_by_id(current))
    base_ids = set(_nodes_by_id(baseline))
    cur_m = current.get(meta_key) or {}
    base_m = baseline.get(meta_key) or {}
    scalar_changes: List[str] = []
    for field in scalar_fields:
        if cur_m.get(field) != base_m.get(field):
            scalar_changes.append(field)
    return {
        "added": sorted(cur_ids - base_ids),
        "removed": sorted(base_ids - cur_ids),
        "scalar_changes": scalar_changes,
    }


def write_snapshot(graph: Dict[str, Any], snap_dir: Path) -> Path:
    """Persist a graph snapshot under the INJECTED `snap_dir` as `<ISO>-<hash>.json`.

    Filename is derived from `graph["generated_at"]` plus the first 8 hex digits
    of the SHA-256 of the JSON body. The hash suffix prevents two snapshots taken
    in the same second from silently overwriting each other while keeping the
    filename deterministic (same content → same hash → same path). The target dir
    is a PARAMETER (not a hard-coded product path) so one definition serves any
    domain."""
    snap_dir = Path(snap_dir)
    snap_dir.mkdir(parents=True, exist_ok=True)
    generated_at = graph.get("generated_at") or _now()
    body = json.dumps({"snapshot_at": generated_at, **graph}, indent=2,
                      ensure_ascii=False, default=str)
    content_hash = hashlib.sha256(body.encode("utf-8")).hexdigest()[:8]
    ts = generated_at.replace("-", "").replace(":", "")
    path = snap_dir / f"{ts}-{content_hash}.json"
    path.write_text(body, encoding="utf-8")
    return path


# ── id-grammar framework ──────────────────────────────────────────────────────

def id_grammar_findings(nodes: List[Dict[str, Any]],
                        pattern_by_type: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Validate each node's id against `pattern_by_type[node.type]`.

    Emits one `invalid_id` finding (via make_finding) when a node's id fails the
    regex for its type. A node whose id is one of the absent/malformed sentinels
    is skipped here so it is NOT double-reported — make_finding's hygiene already
    nulls the sentinel for any finding that names it. A type with no registered
    pattern is left unvalidated (the caller owns which types carry a grammar)."""
    findings: List[Dict[str, Any]] = []
    for n in nodes:
        nid = n.get("id")
        if nid in ID_SENTINELS:
            continue
        pattern = pattern_by_type.get(n.get("type"))
        if pattern is None:
            continue
        if not pattern.match(nid or ""):
            findings.append(make_finding(
                "invalid_id", "error", n,
                f"id {nid!r} does not match the {n.get('type')} grammar "
                f"({pattern.pattern}).",
                expected=pattern.pattern,
            ))
    return findings


def _now() -> str:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0, tzinfo=None).isoformat() + "Z"
