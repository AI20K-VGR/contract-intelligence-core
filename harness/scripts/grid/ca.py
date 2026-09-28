"""ca.py — deterministic covering-array (CA) generator.

Pure by design: this module takes only ``shape: list[int]`` (cardinality per
axis) + a strength ``t``, never YAML/config/axes objects. The build-order
dependency graph wires this module with a dependency only on the shared
types module — no edge to `axes.py` (the owner
of `grid-strength.yaml`/`t_for_strength`) — so reading that config here would
create a graph violation. Callers (`costing.py`, `skeleton.py`) resolve
`shape = [len(axis.values) for axis in axes]` themselves and hand this module
plain ints.

Generation goes through ``covertable``; ``verify_full`` and ``lower_bound``
stay hand-written on purpose, as an INDEPENDENT oracle. A generator that
grades its own homework catches nothing, and 0-missing coverage is the one
property the whole grid rests on.

Why the library and not the greedy loop it replaces. The greedy fills axes
left to right in one pass and scores each choice only against the axes already
fixed in that row, so the FIRST axis is picked nearly blind; ``covertable``
ranks pairs globally. Measured by injecting 4000 real 3-way faults:

    planner  (3,4,5,4,4)     31.1% -> 38.3% detected
    planner  (5,4,5,4,4)     26.6% -> 33.9%
    executor (5,3,3,3,3,3)   47.9% -> 50.5%
    8 axes                   61.6% -> 62.2%

That is the whole trade, and it runs the other way on row count: at t=2 on the
CURRENTLY declared axis order the planner grid grows by four rows (20->24,
25->29). Fewer rows is not better here — fewer rows means less redundancy, and
redundancy is what accidentally catches faults above the declared strength.
Hitting the theoretical bound and detecting poorly are two sides of one coin.

Determinism, verified rather than assumed: identical output across
PYTHONHASHSEED 0/1/42/12345 (same sha256 of the row list). ``covertable`` orders
by an FNV-1a hash of its own, not Python's hash. There is still no ``random``
import in this module.

``seeded_extend`` keeps the hand-written greedy: the library generates from
scratch and has no notion of "hold these rows verbatim and extend", which is
the entire point of that path.

The exact row COUNT is NOT a contract — the contract is 0-missing coverage
(`verify_full` empty), determinism, and `lower_bound <= len(rows) <=
product(shape)`.
"""
import itertools
import math

from covertable import make as _covertable_make


def _validate(shape, t):
    if not shape:
        raise ValueError("shape must be a non-empty list of axis cardinalities")
    for card in shape:
        if card < 1:
            raise ValueError(f"every axis cardinality must be >= 1: {shape!r}")
    k = len(shape)
    if t < 1 or t > k:
        raise ValueError(f"t must satisfy 1 <= t <= {k} (len(shape)); got t={t!r}")


def all_ttuples(shape, t):
    """Every t-tuple that must be covered: one entry per (t distinct axes) x
    (one value-index per chosen axis). Each entry is
    ``((param_idx, val_idx), ...)`` with params in ascending axis order.
    """
    _validate(shape, t)
    out = set()
    for params in itertools.combinations(range(len(shape)), t):
        for vals in itertools.product(*(range(shape[p]) for p in params)):
            out.add(tuple(zip(params, vals)))
    return out


def _covered_by(row, shape, t):
    """All t-tuples a single, fully-assigned row touches."""
    return {
        tuple((p, row[p]) for p in params)
        for params in itertools.combinations(range(len(shape)), t)
    }


def _greedy_row(seed, shape, t, uncovered):
    """Build one row starting from a seed t-tuple, filling the remaining
    axes (in fixed ``range(k)`` order) with the value-index that covers the
    most currently-uncovered t-tuples among axes already fixed in this row.
    Tie-break is strict (`gain > best`, `best_v` starts at 0) so the smallest
    value-index wins every tie — this is the third determinism point.
    """
    k = len(shape)
    row = [None] * k
    for p, v in seed:
        row[p] = v
    for p in range(k):
        if row[p] is not None:
            continue
        fixed = [q for q in range(k) if row[q] is not None]
        best_v = 0
        best_gain = 0
        for v in range(shape[p]):
            gain = 0
            for others in itertools.combinations(fixed, t - 1):
                params = tuple(sorted(others + (p,)))
                candidate = tuple((q, v if q == p else row[q]) for q in params)
                if candidate in uncovered:
                    gain += 1
            if gain > best_gain:
                best_gain = gain
                best_v = v
        row[p] = best_v
    return tuple(row)


def greedy_ca(shape, t):
    """Deterministic covering array: rows covering every t-tuple of ``shape``
    at least once. Raises ValueError on an invalid t or shape.

    Name kept for its call sites, which stamp it as the generator label in the
    costing receipt; the greedy loop it is named after now survives only in
    ``seeded_extend``.
    """
    _validate(shape, t)
    # `strength=`, NOT `length=`. covertable takes **params, so a wrong keyword is
    # SWALLOWED rather than rejected — `length=3` silently produced a t=2 array, and the
    # only thing that caught it was verify_full reporting 563 uncovered triples.
    rows = _covertable_make([list(range(n)) for n in shape], strength=t)
    return [tuple(row[i] for i in range(len(shape))) for row in rows]


def verify_full(rows, shape, t):
    """Return the set of t-tuples NOT covered by `rows` — empty means 0-missing
    (full coverage). Shared oracle between the CA tests here and the
    invariants module's inline coverage check.
    """
    uncovered = set(all_ttuples(shape, t))
    for row in rows:
        uncovered -= _covered_by(tuple(row), shape, t)
    return uncovered


def lower_bound(shape, t):
    """Theoretical minimum row count: product of the t largest cardinalities.
    Test/measurement only — never used at runtime to predict/guess a count.
    """
    _validate(shape, t)
    return math.prod(sorted(shape, reverse=True)[:t])


def seeded_extend(existing_rows, shape, t_new):
    """Escalate a CA from its current strength to `t_new` (typically t+1),
    keeping 100% of `existing_rows` VERBATIM as a prefix (preserves whatever
    fill work already went into them), then greedily appending only the
    delta rows needed to reach 0-missing coverage at `t_new`.

    `shape` (not axes objects) keeps this module pure — callers resolve
    `shape = [len(a.values) for a in axes]` themselves.
    """
    _validate(shape, t_new)
    rows = [tuple(r) for r in existing_rows]
    uncovered = set(all_ttuples(shape, t_new))
    for r in rows:
        uncovered -= _covered_by(r, shape, t_new)
    while uncovered:
        seed = min(uncovered)
        row = _greedy_row(seed, shape, t_new, uncovered)
        uncovered -= _covered_by(row, shape, t_new)
        rows.append(row)
    return rows


def infer_max_t(rows, shape):
    """Infer the current strength of `rows`: the largest t for which
    `verify_full(rows, shape, t) == set()`. Re-derives strength from the rows
    themselves (never from a stored `Grid.strength`), so an escalate call
    (`skeleton.py`) always has a re-checkable source of `t` before calling
    `seeded_extend`.
    """
    if not rows:
        raise ValueError("cannot infer strength of an empty row list")
    t = 1
    max_t = len(shape)
    while t <= max_t and not verify_full(rows, shape, t):
        t += 1
    return t - 1
