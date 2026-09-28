#!/usr/bin/env python3
"""scope_match.py — the canonical path-glob matcher for the rule subsystem.

Two gates already share a fnmatch matcher (`path_glob.py`: the deny matcher +
component-policy). The RULE side needs different, richer semantics: gitignore-style
`**` plus the relation predicates `globs_overlap` / `glob_subsumes` that
conflict-detect and coverage-derive rely on. fnmatch cannot answer "do these two
globs intersect", so this is a separate module with a regex/automaton model — it
does NOT change path_glob's semantics for the other two gates.

Glob semantics (identical to the old review_rules/risk_rubric `_glob_to_re`):
  `**/` zero-or-more leading path segments, `**` anything (incl `/`),
  `*` within one segment (no `/`), `?` one non-slash char.

The duplicated `_glob_to_re` copies (review_rules.py + risk_rubric.py) re-point
here. Case-sensitivity is NOT unified into one default: review-rules/consumer use
case-sensitive (gitignore), risk-rubric keeps case-insensitive on purpose (a
case-sensitive match would miss AuthService.java / AuthGuard.tsx and silently
under-rate security risk). The CODE is unified; the `case_insensitive=` knob keeps
the two semantics distinct.
"""

import functools
import re


def glob_to_regex(glob: str, case_insensitive: bool = False) -> "re.Pattern":
    """Compile a path glob to an anchored regex with gitignore-style `**`.

    `**/` -> `(?:.*/)?` (zero-or-more leading segments), `**` -> `.*`,
    `*` -> `[^/]*` (within a segment), `?` -> `[^/]`.
    """
    out = []
    i, n = 0, len(glob)
    while i < n:
        if glob[i:i + 3] == "**/":
            out.append("(?:.*/)?")
            i += 3
        elif glob[i:i + 2] == "**":
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    flags = re.IGNORECASE if case_insensitive else 0
    return re.compile("^" + "".join(out) + "$", flags)


def scope_matches(globs, changed_files, case_insensitive: bool = False) -> bool:
    """True when >=1 changed file matches at least one glob in `globs` (OR-fan)."""
    for glob in globs or []:
        rx = glob_to_regex(glob, case_insensitive=case_insensitive)
        for f in changed_files or []:
            if rx.match(f):
                return True
    return False


# --- glob relation predicates (overlap / subsumption) -------------------------
#
# Implemented as a small token automaton over the path alphabet. fnmatch/regex
# alone can decide "does a string match a glob"; deciding "do two globs share any
# string" / "does one glob's language contain another's" needs the automaton.
# Path globs are short, so the powerset product stays tiny and bounded.
#
# Token kinds after parsing:
#   ('LIT', c)  exactly char c (c may be '/')
#   ('Q',)      one non-slash char            (`?`)
#   ('STAR',)   zero+ non-slash chars         (`*`)
#   ('DSTAR',)  zero+ any chars incl '/'      (`**`)
# `**/` -> `(?:.*/)?` is an OPTIONAL "(.* then /)", so it is expanded at parse
# time into two alternative token lists: the empty branch, and `[DSTAR, '/']`.

def _tokenize_alts(glob: str):
    """Parse a glob into a list of token-lists, expanding each `**/` into its two
    branches (empty | `.*` then `/`). Usually one alt; >1 only with `**/`."""
    alts = [[]]
    i, n = 0, len(glob)
    while i < n:
        if glob[i:i + 3] == "**/":
            nxt = []
            for seq in alts:
                nxt.append(list(seq))                                  # empty branch
                nxt.append(list(seq) + [("DSTAR",), ("LIT", "/")])     # `.*/` branch
            alts = nxt
            i += 3
        elif glob[i:i + 2] == "**":
            for seq in alts:
                seq.append(("DSTAR",))
            i += 2
        elif glob[i] == "*":
            for seq in alts:
                seq.append(("STAR",))
            i += 1
        elif glob[i] == "?":
            for seq in alts:
                seq.append(("Q",))
            i += 1
        else:
            for seq in alts:
                seq.append(("LIT", glob[i]))
            i += 1
    return alts


def _can_empty_from(toks, k: int) -> bool:
    """Can toks[k:] match the empty string? (STAR/DSTAR can, LIT/Q cannot.)"""
    for t in toks[k:]:
        if t[0] in ("LIT", "Q"):
            return False
    return True


def _consume(toks, k: int, ch: str):
    """Next token indices after consuming char `ch` at position k (no epsilon)."""
    t = toks[k]
    kind = t[0]
    if kind == "LIT":
        return [k + 1] if ch == t[1] else []
    if kind == "Q":
        return [k + 1] if ch != "/" else []
    if kind == "STAR":
        return [k] if ch != "/" else []   # stay in the star (exit via epsilon)
    if kind == "DSTAR":
        return [k]                          # stay in the star (any char)
    return []


def _eps_closure(toks, states):
    """Expand STAR/DSTAR k -> k+1 (matching empty) to closure."""
    out = set(states)
    stack = list(states)
    while stack:
        k = stack.pop()
        if k < len(toks) and toks[k][0] in ("STAR", "DSTAR") and (k + 1) not in out:
            out.add(k + 1)
            stack.append(k + 1)
    return frozenset(out)


def _step(toks, states, ch: str):
    nxt = set()
    for k in states:
        if k < len(toks):
            nxt.update(_consume(toks, k, ch))
    return _eps_closure(toks, nxt)


def _accepts(toks, states) -> bool:
    return any(_can_empty_from(toks, k) for k in states)


def _probe_chars(*alt_groups):
    """A sound finite alphabet partition: every literal that appears, plus one
    representative non-slash char not among them, plus '/'."""
    lits = set()
    for alts in alt_groups:
        for toks in alts:
            for t in toks:
                if t[0] == "LIT" and t[1] != "/":
                    lits.add(t[1])
    probes = list(lits)
    gen = None
    for c in "abcdefghijklmnopqrstuvwxyz0123456789_.-":
        if c not in lits:
            gen = c
            break
    if gen is not None:
        probes.append(gen)
    probes.append("/")
    return probes


@functools.lru_cache(maxsize=4096)
def globs_overlap(a: str, b: str) -> bool:
    """True when some path matches BOTH globs (their languages intersect).

    Memoized because the answer is a pure function of the two glob strings and
    the callers repeat themselves structurally: the rule conflict audit compares
    every rule's scope against every other's, and rules share scopes, so it asked
    8085 overlap questions over 1459 distinct pairs — 5.5 repeats each. Each
    answer is a product-automaton reachability search, which is what made that
    audit cost 17.8s cold.

    Bounded rather than unbounded: the keys are globs read from rule files, a set
    that does not grow with input size, and a ceiling keeps a long-lived process
    from holding every pair it ever saw.
    """
    a_alts = _tokenize_alts(a)
    b_alts = _tokenize_alts(b)
    probes = _probe_chars(a_alts, b_alts)
    for ta in a_alts:
        for tb in b_alts:
            if _alts_intersect(ta, tb, probes):
                return True
    return False


def _alts_intersect(ta, tb, probes) -> bool:
    """Product reachability: is there a string accepted by both token lists?"""
    start = (_eps_closure(ta, {0}), _eps_closure(tb, {0}))
    seen = {start}
    stack = [start]
    while stack:
        sa, sb = stack.pop()
        if _accepts(ta, sa) and _accepts(tb, sb):
            return True
        for ch in probes:
            nxt = (_step(ta, sa, ch), _step(tb, sb, ch))
            if nxt[0] and nxt[1] and nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return False


def glob_subsumes(a: str, b: str) -> bool:
    """True when every path matching `b` also matches `a` (L(b) subset of L(a)).

    Checked by product of b's automaton with the UNION of a's alternatives: if a
    reachable product state accepts on the b side but not on the a side, there is
    a witness in L(b) outside L(a), so a does not subsume b.
    """
    a_alts = _tokenize_alts(a)
    b_alts = _tokenize_alts(b)
    probes = _probe_chars(a_alts, b_alts)
    for tb in b_alts:
        if not _alt_included_in_union(tb, a_alts, probes):
            return False
    return True


def _alt_included_in_union(tb, a_alts, probes) -> bool:
    """L(tb) subset of union(L(a) for a in a_alts)."""
    b_start = _eps_closure(tb, {0})
    a_start = tuple(_eps_closure(a, {0}) for a in a_alts)
    start = (b_start, a_start)
    seen = {start}
    stack = [start]
    while stack:
        sb, sa = stack.pop()
        if _accepts(tb, sb) and not any(_accepts(a_alts[k], sa[k]) for k in range(len(a_alts))):
            return False    # witness accepted by b, rejected by every a-alt
        for ch in probes:
            nb = _step(tb, sb, ch)
            if not nb:
                continue    # no b-string continues this way; nothing to cover
            na = tuple(_step(a_alts[k], sa[k], ch) for k in range(len(a_alts)))
            nxt = (nb, na)
            if nxt not in seen:
                seen.add(nxt)
                stack.append(nxt)
    return True
