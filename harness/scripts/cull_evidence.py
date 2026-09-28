#!/usr/bin/env python3
"""cull_evidence.py — reconcile a test-cull ledger against git.

A cull ledger records which test callables were deleted and why. It is only worth
keeping if a later reader can look one up. The convention it enforces is two fields on
every record that removes tests:

    removed:   the deleted callables' NAMES (bare `test_x`, or qualified `path::test_x`)
    baseline:  the rev they were deleted FROM

Both came from a real miss. A ledger recorded four deletions by reason alone ("all four
call 0 product functions"); the reviewer searched by function name, found nothing, and
restored work that was correctly cut. And without a baseline rev, "this name is gone" is
indistinguishable from "this name never existed" — one of those is a ledger citing a
callable that never was.

The reconciliation deliberately does NOT ask a record whether it is a removal record.
Reading a `claim` string for removal-ish words is a phrase list, and a phrase list dies to
the first synonym. Instead:

    vanished    = census(baseline) - census(head)        # git decides, not the prose
    unaccounted = vanished - everything the ledger names  # what nobody wrote down

A record that omits `removed` hides nothing, because the subtraction never consults the
ledger to learn what to subtract. The only thing a record can do is shrink `unaccounted`
by naming names.

Two directions of drift fall out of the same set algebra and are reported separately:

    phantom        named as removed, but not present at the baseline either
    still_present  named as removed, but still alive at head

`ok` is the conjunction of all four being empty (plus every removal record carrying a
baseline). Exit 1 when not ok — this is a gate, not a nudge: it answers one question with
one command, which is exactly the kind of rule `counting-discipline.md` says must not rest
on human memory.

Census is per-FILE-qualified (`path::name`). Two files may define the same callable name,
and reconciling bare names would let a deletion in one file hide behind the survivor in
the other. A ledger may still write the bare name — it resolves against the qualified key
when unambiguous.
"""

import argparse
import ast
import fnmatch
import json
import re
import subprocess
import threading
import sys
from pathlib import Path
from typing import Dict, List, Optional, Sequence, Set

HOOK_CLASS = "compliance"

_TEST_GLOBS = ("test_*.py", "*_test.py")


def _git(root: Path, *args: str) -> str:
    """Run git in `root`, returning stdout. Raises on failure — a git error here means the
    census is about nothing, and a silent empty census would make every downstream set
    trivially empty and every verdict vacuously clean."""
    r = subprocess.run(["git", "-c", "core.quotepath=false", *args],
                       cwd=str(root), capture_output=True)
    if r.returncode != 0:
        raise RuntimeError("git %s failed: %s" % (" ".join(args),
                                                  r.stderr.decode("utf-8", "replace")))
    return r.stdout.decode("utf-8", "replace")


def _under(rel: str, paths: Sequence[str]) -> bool:
    if not paths:
        return True
    return any(rel == p or rel.startswith(p.rstrip("/") + "/") for p in paths)


def _is_test_file(rel: str) -> bool:
    """Driven by `_TEST_GLOBS`, not by a second copy of it. The constant used to be dead
    while this function restated the same patterns inline — two spellings of one rule, and
    the reviewable one was the one that did nothing. It also read as a precedence puzzle
    (`a and b or c` without parentheses); fnmatch over the declared list says the same
    thing without asking anyone to re-derive it."""
    name = rel.rsplit("/", 1)[-1]
    return any(fnmatch.fnmatch(name, pattern) for pattern in _TEST_GLOBS)


def _callables(src: str) -> List[str]:
    """Every `test_*` callable at any depth — a class-nested test counts the same as a
    module-level one. A parse failure yields nothing rather than raising: a rev that
    predates a syntax fix should not take the whole audit down with it."""
    try:
        tree = ast.parse(src)
    except SyntaxError:
        return []
    out = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                and node.name.startswith("test_"):
            out.append(node.name)
    return out


# Keyed on the blob SHA, which is a hash of the content — collisions aside, one key is one
# byte sequence, so a stale answer would require git to hand back different bytes under the
# same sha. Unbounded on purpose: a run reads one repo's test tree (1451 distinct blobs
# here), and the process is a gate that exits.
_CALLABLE_CACHE: dict = {}


def _blobs(root: Path, rev: str, rels: Sequence[str]):
    """Yield `(path, sha, source)` for each path at `rev`, through ONE `git cat-file --batch`.

    The sha rides along because batch mode already prints it and the caller needs it: it is
    a hash of the CONTENT, so two revs naming one sha hold byte-identical files and any
    answer derived from those bytes is the same answer. See `census`.

    A `git show` per file spawns one process per test file: measured, 3.5s for a single
    census of this repo's three suites, and the live gate runs two per baseline — 202s
    against a 120s limit. Batch mode streams `<sha> blob <size>\\n<payload>\\n` on one pipe.

    A path git cannot resolve answers `<spec> missing` and is SKIPPED, not raised: a rev
    that predates a file is a normal question here, and the caller's contract is "what this
    rev holds", not "every path exists at this rev".

    The request goes down a THREAD rather than in one write. Writing it all first deadlocks
    once both pipes fill: git blocks writing a reply we are not reading yet, so it stops
    reading, so our write blocks, and neither side moves. Measured on this repo at HEAD —
    800 paths (60 KB request, 7.8 MB of blobs) returned, 1200 (79 KB, 11.2 MB) hung until
    killed. That is one suite-growth from the live gate, and a hang there reads as flaky
    infrastructure rather than as a finding.
    """
    if not rels:
        return
    proc = subprocess.Popen(["git", "-c", "core.quotepath=false", "cat-file", "--batch"],
                            cwd=str(root), stdin=subprocess.PIPE,
                            stdout=subprocess.PIPE, stderr=subprocess.DEVNULL)

    def _feed():
        try:
            assert proc.stdin is not None
            proc.stdin.write(("".join("%s:%s\n" % (rev, r) for r in rels)).encode("utf-8"))
            proc.stdin.close()
        except (BrokenPipeError, ValueError):
            pass  # the reader stopped early; git will see EOF and exit

    writer = threading.Thread(target=_feed, daemon=True)
    writer.start()
    # Bound locally rather than reached through `proc` each time: Popen types both pipes as
    # Optional, so every `proc.stdout.x` is a union access the checker rejects. They are
    # non-None here because PIPE was requested for both, and asserting that once says so in
    # one place instead of nine.
    assert proc.stdout is not None
    stdout = proc.stdout
    try:
        for rel in rels:
            header = stdout.readline().decode("utf-8", "replace").strip()
            if not header or header.endswith(" missing"):
                continue
            sha, _kind, raw_size = header.rsplit(" ", 2)
            size = int(raw_size)
            payload = stdout.read(size)
            stdout.read(1)  # the trailing newline batch mode writes after each blob
            yield rel, sha, payload.decode("utf-8", "replace")
    finally:
        stdout.close()
        writer.join(timeout=5)
        proc.wait()


def census(root: Path, rev: str, paths: Sequence[str] = ()) -> Set[str]:
    """The set of `path::callable` keys in test files at `rev`.

    Reads the REV via `git show`, never the working tree. That distinction is the point:
    a census built from the worktree describes a tree nobody committed, and answers about
    a commit that never contained it.

    Parsing is memoized on the blob SHA, so a file that did not change between two
    baselines is parsed once. Measured on the live gate's 29 baselines: 26198 blob parses
    over 1451 distinct shas — 18.1x of the work was the same bytes again, and a profile put
    95% of one audit in `_callables` -> `ast.walk`. The key is a content hash, never a rev
    name: `HEAD` moves, a sha does not (`audit` documents the trap this avoids).
    """
    listing = _git(root, "ls-tree", "-r", "--name-only", rev)
    wanted = [rel.strip() for rel in listing.splitlines()
              if rel.strip() and _is_test_file(rel.strip()) and _under(rel.strip(), paths)]
    keys: Set[str] = set()
    for rel, sha, src in _blobs(root, rev, wanted):
        names = _CALLABLE_CACHE.get(sha)
        if names is None:
            names = _CALLABLE_CACHE[sha] = _callables(src)
        for fn in names:
            keys.add("%s::%s" % (rel, fn))
    return keys


def _load(ledger: Path) -> List[dict]:
    """Parse the ledger, refusing anything that is not one JSON OBJECT per line.

    `json.loads` happily returns a str, a list, or None — all valid JSON, none of them a
    record. Left unchecked they reach `.get()` and either raise with a message that points
    at the wrong thing, or worse: a bare `[]` on its own line parses, contributes no names,
    and lets the audit report a clean ledger while the file is malformed. Failing here says
    which LINE is wrong, which is the only form of this error a human can act on.
    """
    recs = []
    for n, line in enumerate(ledger.read_text(encoding="utf-8").splitlines(), 1):
        line = line.strip()
        if not line:
            continue
        try:
            rec = json.loads(line)
        except ValueError as exc:
            raise ValueError("%s line %d is not valid JSON: %s" % (ledger, n, exc))
        if not isinstance(rec, dict):
            raise ValueError("%s line %d is a %s, not a record object — a JSONL ledger "
                             "holds one object per line"
                             % (ledger, n, type(rec).__name__))
        recs.append(rec)
    return recs


def _bare_index(keys: Set[str]) -> Dict[str, List[str]]:
    idx: Dict[str, List[str]] = {}
    for key in keys:
        idx.setdefault(key.split("::", 1)[1], []).append(key)
    return idx


def _named(recs: Sequence[dict], vanished: Set[str],
           universe: Set[str]) -> Dict[str, List[str]]:
    """Resolve every ledger-named callable to a qualified `path::name` key.

    Two lookups, in order, because a bare name answers two different questions and one
    index cannot serve both:

    1. **Against `vanished` first.** A ledger name is a claim about a CUT, so the cut set
       is its natural home. This also disambiguates the common real case: `test_dup`
       defined in two files, deleted from one — one vanished key, no ambiguity, even
       though the universe holds two.
    2. **Against the universe (baseline ∪ head) as fallback.** Needed for the claim that
       never happened: a name still alive is absent from `vanished`, so lookup 1 misses
       it. Without this fallback it would slip past `phantom` too (it IS at the baseline)
       and escape by being wrong in a third direction. Resolved here, it lands in
       `still_present` where it belongs.

    Ambiguity is never resolved silently — a bare name matching several keys in BOTH
    indexes stays unresolved and surfaces, rather than quietly binding to whichever file
    happened to sort first.
    """
    by_vanished = _bare_index(vanished)
    by_universe = _bare_index(universe)
    resolved, unresolved = [], []
    for rec in recs:
        for name in rec.get("removed") or []:
            if "::" in name:
                resolved.append(name)
                continue
            hits = by_vanished.get(name) or by_universe.get(name) or []
            if len(hits) == 1:
                resolved.append(hits[0])
            elif hits:
                # Several files, no way to pick — genuinely unresolvable.
                unresolved.append(name)
            else:
                # NOWHERE, which is a different answer and a harder one: the ledger named
                # something that was never there. Keep it resolved so it reaches `phantom`;
                # routing it to `unresolved` would file a fabrication under "ambiguous" and
                # bury the accusation the audit exists to make.
                resolved.append(name)
    return {"resolved": resolved, "unresolved": unresolved}


def _under_paths(names, paths: Sequence[str]):
    """The claimed names the scan could actually have seen. Empty `paths` means the whole
    tree, so everything is in scope.

    A BARE name carries no path, so nothing about it can be called out of scope — it stays
    in and faces the phantom test. Excusing it here would file every unresolvable
    fabrication as somebody else's suite."""
    if not paths:
        return set(names)
    return {n for n in names if "::" not in n or _under(n.split("::", 1)[0], paths)}


def _cut_at(root: Path, recs, name: str, paths: Sequence[str]) -> bool:
    """Was `name` absent from its own record's commit? A record that names a `commit` is a
    claim about that revision; asking HEAD instead turns every cut-then-recreated file into
    a false accusation. Fail-open: an unreadable rev answers False, so the name stays under
    the HEAD test rather than being excused by a git error."""
    for rec in recs:
        rev = rec.get("commit")
        if not rev or name not in (rec.get("removed") or []):
            continue
        # Scope the census to the ONE file the name lives in. Passing the caller's full
        # `paths` re-walks every test file in every suite per name — measured, that turned
        # the live gate into a 120s timeout. A qualified name already says which file to
        # look in; a bare one has no file, so it keeps the caller's scope.
        scope = [name.split("::", 1)[0]] if "::" in name else paths
        try:
            return name not in census(root, rev, scope)
        except RuntimeError:
            return False
    return False


def audit(root: Path, ledger: Path, baseline: str, head: str = "HEAD",
          paths: Sequence[str] = (), head_keys: Optional[Set[str]] = None) -> dict:
    """Reconcile `ledger` against what git says vanished between `baseline` and `head`.

    `head_keys` lets a caller auditing many records hand in the head census once. It varies
    with neither the record nor the baseline, so a loop over N baselines otherwise pays for
    the same answer N times — measured on the live gate at 29 groups, 104s wall against a
    120s timeout, half of it that repeat.

    The seam is here rather than a cache inside `census` on purpose: `HEAD` is a MOVING
    name, and a cache keyed on that string would keep answering with a pre-commit tree
    after any commit. Only the caller knows its loop holds head fixed.
    """
    root = Path(root)
    base_keys = census(root, baseline, paths)
    if head_keys is None:
        head_keys = census(root, head, paths)
    vanished = base_keys - head_keys

    recs = _load(ledger)
    named = _named(recs, vanished, base_keys | head_keys)
    claimed = set(named["resolved"])

    missing_baseline = [i for i, r in enumerate(recs, 1)
                        if (r.get("removed") or []) and not r.get("baseline")]

    # Three verdicts on a claimed name, and they must stay distinct — each sends a reviewer
    # somewhere different, and collapsing any two produces a confident wrong answer.
    #
    # `ambiguous`: a bare name living in several files. It was filtered out of `phantom`
    # by a `base_keys` membership test — but matching SEVERAL keys is exactly what made it
    # ambiguous, so that filter discarded the one case it was there to keep. Measured: a
    # ledger claiming a cut that never happened audited `ok: true`, and 157 of the 9963
    # census keys under this repo's declared suite roots (1.6%) sit under one of 70 such
    # names. The figure first written here was 2166 of 13930 (15.5%) — arithmetically
    # right, but counted TREE-WIDE, and 2009 of those keys are a vendored suite under
    # `docs/research/` that the census allow-list exists to exclude. Ten times the hazard,
    # over a denominator this module's own docstring argues nobody should use.
    #
    # `out_of_scope`: a qualified name outside `paths`. `phantom` means "this was never
    # there" — an accusation. Narrowing the scan is the caller's choice, not the ledger's
    # lie. Measured: 17 truthful `release/tests` names accused because the caller scanned
    # two other suites.
    ambiguous = sorted(set(named["unresolved"]))
    in_scope = _under_paths(claimed, paths)
    out_of_scope = sorted(set(claimed) - in_scope)
    phantom = sorted(n for n in in_scope if n not in base_keys)
    # `still_present` asks whether the name survives — but a record carrying its own
    # `commit` describes ONE stretch of history, not the present. A callable cut there and
    # recreated later was genuinely cut. Ask the record's own commit; fall back to HEAD only
    # for records that name no commit. Measured: 49 names in one record, every one a file
    # removed by that commit and recreated two commits on.
    still_present = sorted(n for n in in_scope
                           if n in head_keys and not _cut_at(root, recs, n, paths))
    unaccounted = sorted(vanished - claimed)

    ok = not (unaccounted or phantom or still_present or missing_baseline
              or ambiguous or out_of_scope)
    return {
        "ok": ok,
        "baseline": baseline,
        "head": head,
        "counted": {"baseline": len(base_keys), "head": len(head_keys)},
        "vanished": sorted(vanished),
        "unaccounted": unaccounted,
        "phantom": phantom,
        "still_present": still_present,
        "ambiguous": ambiguous,
        "out_of_scope": out_of_scope,
        "records_missing_baseline": missing_baseline,
    }


def reconstruct(root: Path, baseline: str, head: str = "HEAD",
                paths: Sequence[str] = ()) -> List[dict]:
    """Rebuild ledger records from git history, for cuts made before the convention.

    A ledger that predates `removed` + `baseline` is not lost work — git still holds both
    halves: the deleted callable names live in each commit's diff, and the reason lives in
    its message. This walks the range and emits one record per commit that removed a test
    callable, in the shape `audit` reconciles.

    Walks the DIFF of each commit, never `git log -- <file>`. That distinction is not
    pedantry: `git log -1 -- <file>` answers "what last touched this file", which is a
    different question and gets it wrong in two ways at once. Measured here — it credited
    16 deletions to a commit that only ADDED tests, because a file deleted long ago was
    later recreated under the same name with different contents. Any per-file attribution
    inherits that bug; per-diff does not.
    """
    root = Path(root)
    revs = _git(root, "log", "--format=%H", "%s..%s" % (baseline, head))
    out = []
    for rev in revs.split():
        args = ["show", "--format=%s", "--unified=0", rev]
        if paths:
            args += ["--", *paths]
        try:
            text = _git(root, *args)
        except RuntimeError:
            continue
        subject = text.split("\n", 1)[0].strip()
        # Which FILES this commit touched. The path comes from the `---` (pre-image) side,
        # NOT `+++`: a file deleted outright has `+++ /dev/null`, so keying on `+++ b/`
        # drops every callable in exactly the commits that removed the most — measured,
        # 1230 of 1818 deletions vanished, all of them whole-file removals.
        touched = {l[6:].strip() for l in text.splitlines() if l.startswith("--- a/")}
        touched = {f for f in touched if _is_test_file(f) and _under(f, paths)}
        if not touched:
            continue
        # Then ask CENSUS what each file held before and after, instead of reading `-def`
        # lines. Scanning the diff text is a second implementation of the same question,
        # and the two answers diverged in three measured ways: a widened signature emits
        # `-def test_x(a)` with no deletion (4 of 1817 live names); a `def test_x` indented
        # inside a fixture STRING is not a callable at all (1 live name); and requiring
        # column zero to exclude that one would drop every class-nested test, which census
        # does count. A set difference over the parser both halves already share cannot
        # disagree with itself.
        try:
            before = {k for k in census(root, "%s~1" % rev, sorted(touched))}
            after = {k for k in census(root, rev, sorted(touched))}
        except RuntimeError:
            continue
        names = sorted(before - after)
        if names:
            out.append({"claim": subject, "label": "OBSERVED",
                        "baseline": "%s~1" % rev[:8], "commit": rev[:8],
                        "removed": sorted(set(names)),
                        "source": "reconstructed from git history"})
    return out


def main(argv: Optional[Sequence[str]] = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    ap.add_argument("--root", default=".", help="repo root")
    ap.add_argument("--file", help="the cull ledger (JSONL); not needed with --reconstruct")
    ap.add_argument("--baseline", required=True, help="rev the cull started from")
    ap.add_argument("--head", default="HEAD", help="rev to compare against")
    ap.add_argument("--paths", nargs="*", default=[],
                    help="restrict the census to these path prefixes")
    ap.add_argument("--reconstruct", action="store_true",
                    help="emit ledger records rebuilt from git history instead of auditing "
                         "an existing ledger (for cuts made before the convention)")
    a = ap.parse_args(argv)
    if not a.reconstruct and not a.file:
        ap.error("--file is required unless --reconstruct is given")
    if a.reconstruct:
        for rec in reconstruct(Path(a.root), a.baseline, a.head, a.paths):
            print(json.dumps(rec, ensure_ascii=False))
        return 0
    res = audit(Path(a.root), Path(a.file), a.baseline, a.head, a.paths)
    print(json.dumps(res, indent=2, sort_keys=True))
    return 0 if res["ok"] else 1


if __name__ == "__main__":
    sys.exit(main())
