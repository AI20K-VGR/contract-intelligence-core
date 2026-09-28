#!/usr/bin/env python3
"""push_gate.py — transport-level routing for `git push`.

The git pre-push hook feeds ref updates on stdin, one line per ref:

    <local ref> <local sha> <remote ref> <remote sha>

push_gate reads the destination branch names (the 3rd field), and picks the
stage to enforce: a push to a PROTECTED branch is a `merge` (it must clear the
same merge-grade artifacts a reviewed PR would), every other push is `push`.
Empty stdin (no ref lines) → `push`, preserving the legacy hook's behavior.

check() routes the merge-stage reason through the merge_gate FLOOR guard so the
decision is audited and can be lowered ONLY by a logged break-glass override in
guard-policy.yaml — never by a preset.
"""
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
if str(_HERE) not in sys.path:
    sys.path.insert(0, str(_HERE))

import branch_policy  # noqa: E402


def targets(refs_text) -> set:
    """Short destination branch names from pre-push stdin. Tags (refs/tags/*)
    are not branches and are ignored."""
    names = set()
    for line in (refs_text or "").splitlines():
        parts = line.split()
        if len(parts) < 3:
            continue
        remote_ref = parts[2]
        prefix = "refs/heads/"
        if remote_ref.startswith(prefix):
            names.add(remote_ref[len(prefix):])
    return names


def stage_for(refs_text) -> str:
    """`merge` if ANY pushed branch is protected, else `push`."""
    for branch in targets(refs_text):
        if branch_policy.is_protected(branch):
            return "merge"
    return "push"


def stage_for_checkout(root) -> str:
    """`stage_for`'s answer for a projection, which has no pre-push stdin.

    A verb reporting what the gate WILL say cannot read the refs git is about to
    push — they do not exist yet. The branch git reports as checked out is the
    one those refs will name, so the same `is_protected` predicate `stage_for`
    calls answers the same question one step earlier.

    Falls back to `push` when the branch cannot be read (detached HEAD, no repo,
    unreadable policy). That is the shipped default and the answer `stage_for`
    itself gives an unprotected target, so an unreadable branch never relaxes a
    requirement — it only declines to add one.
    """
    import subprocess
    try:
        out = subprocess.run(
            ["git", "-C", str(root), "rev-parse", "--abbrev-ref", "HEAD"],
            capture_output=True, text=True, timeout=10)
    except (OSError, subprocess.SubprocessError):
        return "push"
    branch = (out.stdout or "").strip()
    if out.returncode != 0 or not branch or branch == "HEAD":
        return "push"
    try:
        return "merge" if branch_policy.is_protected(branch) else "push"
    except Exception:  # noqa: BLE001 — an unreadable policy claims no protection
        return "push"


def _is_zero(sha) -> bool:
    """A git all-zero object id (any length) — the sentinel for a created or
    deleted ref in pre-push stdin."""
    return bool(sha) and set(sha) == {"0"}


_ANCESTOR_TIMEOUT = 15  # seconds — local object-store query
_FETCH_TIMEOUT = 30     # seconds — one network round-trip to recover an object


def _is_ancestor(root, ancestor_sha, descendant_sha):
    """0 if ancestor_sha IS an ancestor of descendant_sha (a fast-forward),
    1 if it is provably NOT (a non-fast-forward), None if git cannot tell —
    the object is absent from the local store (a shallow clone), the path is
    not a repo, or the query timed out/errored."""
    import subprocess
    try:
        r = subprocess.run(
            ["git", "-C", str(root), "merge-base", "--is-ancestor",
             ancestor_sha, descendant_sha],
            capture_output=True, timeout=_ANCESTOR_TIMEOUT)
    except Exception:  # noqa: BLE001 — cannot verify
        return None
    if r.returncode == 0:
        return 0
    if r.returncode == 1:
        return 1
    return None  # 128 etc. → indeterminate (e.g. object not present locally)


def _fetch_object(root, remote, remote_ref, remote_sha):
    """Best-effort: pull the remote's object into the local store so ancestry
    becomes computable on a shallow clone. Bounded by a short timeout; any
    failure (offline, server policy, timeout) is swallowed — the caller treats
    a still-indeterminate ancestry as a block, not a pass."""
    import subprocess
    for spec in (remote_ref, remote_sha):
        if not spec:
            continue
        try:
            r = subprocess.run(
                ["git", "-C", str(root), "fetch", "--quiet", remote, spec],
                capture_output=True, timeout=_FETCH_TIMEOUT)
            if r.returncode == 0:
                return
        except Exception:  # noqa: BLE001 — try the next spec, else give up
            continue


def destructive_to_protected(refs_text, root, remote=None):
    """Reason if any pushed ref DELETES or non-fast-forwards a protected branch,
    else None. The most irreversible transport ops — refused independent of
    artifacts. Each pre-push line is `<local ref> <local sha> <remote ref>
    <remote sha>`: a delete has an all-zero LOCAL sha; a non-ff has a non-zero
    REMOTE sha that is not an ancestor of the local sha.

    Ancestry is checked against the local object store. When git cannot resolve
    it because the remote object is absent locally (a shallow clone) AND a
    ``remote`` is given, we fetch that object and re-judge; if it is STILL
    indeterminate, we BLOCK rather than fail open (a protected branch must not be
    force-pushed over an unverifiable history). With no ``remote`` to fetch from
    (a programmatic call) we DEFER to None so the merge-grade artifact floor
    still judges the push."""
    for line in (refs_text or "").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_sha, remote_ref, remote_sha = parts[1], parts[2], parts[3]
        prefix = "refs/heads/"
        if not remote_ref.startswith(prefix):
            continue
        branch = remote_ref[len(prefix):]
        if not branch_policy.is_protected(branch):
            continue
        if _is_zero(local_sha):
            return ("refusing to delete protected branch %r — a protected "
                    "branch may not be deleted over the wire" % branch)
        if _is_zero(remote_sha):
            continue  # creating the branch — not a delete or force
        status = _is_ancestor(root, remote_sha, local_sha)
        if status is None and remote:
            # Shallow clone: the remote object is absent so ancestry is unknown.
            # Recover it and re-judge; if still unknown, block to be safe.
            _fetch_object(root, remote, remote_ref, remote_sha)
            status = _is_ancestor(root, remote_sha, local_sha)
            if status is None:
                return ("refusing push to protected branch %r — cannot verify "
                        "it is a fast-forward (remote history unavailable even "
                        "after fetch); blocking to be safe" % branch)
        if status == 1:  # remote is NOT an ancestor of local → non-ff
            return ("refusing non-fast-forward (history rewrite) push to "
                    "protected branch %r" % branch)
        # status == 0 (fast-forward), or None with no remote → not refused here
    return None


def _pushed_diff(root, refs_text):
    """The unified diff of exactly the commits this push would deliver, derived
    from each PUSH_REFS line's <remote_sha>..<local_sha> range -- NOT local
    divergence (`--branches --not --remotes`), which both scans commits that are
    not being pushed AND misses a commit reachable only from a stale remote-
    tracking ref or an explicit-sha push. Returns the concatenated diff ("" when
    nothing is delivered), or None on any unreadable range so the caller fails
    open."""
    import subprocess
    chunks = []
    for line in (refs_text or "").splitlines():
        parts = line.split()
        if len(parts) < 4:
            continue
        local_sha, remote_sha = parts[1], parts[3]
        if _is_zero(local_sha):
            continue  # a branch delete delivers no content to scan
        # Scan the pushed branch's first-parent lane.  A merge brings the
        # target branch's historical commits into reachability; those commits
        # are already present on the destination and must not be reclassified
        # as newly introduced secrets by this source-branch gate.
        args = ["git", "-C", str(root), "log", "-p", "--first-parent", "--no-color"]
        if _is_zero(remote_sha):
            args += [local_sha, "--not", "--remotes"]  # new ref: commits not yet on any remote
        else:
            args.append("%s..%s" % (remote_sha, local_sha))  # exactly the new commits
        try:
            # Git diffs may contain arbitrary UTF-8/binary payloads. Reading
            # with ``text=True`` lets the Windows console codec crash the
            # reader thread and leaves ``stdout`` as None, which then makes
            # the gate fail with an unrelated TypeError. Decode defensively;
            # secret scanning only needs a loss-tolerant text projection.
            r = subprocess.run(args, capture_output=True, text=False, timeout=30)
        except Exception:  # noqa: BLE001 -- additive backstop never bricks a push
            return None
        if r.returncode != 0:
            return None
        chunks.append((r.stdout or b"").decode("utf-8", errors="replace"))
    return "\n".join(chunks)


def _secret_reason(root, refs_text):
    """Transport-level secret backstop: a push that defeated the in-session
    stage-detector still reaches pre-push, so re-scan exactly the about-to-push
    commits here. Blocks on a likely secret; None when clean. On an UNREADABLE
    diff it fails OPEN (unlike the in-session gate, which fails closed) -- an
    additive backstop must not brick a push on a git error/timeout, which would
    be a DoS-disable trap; the in-session secret gate stays the primary, fail-
    closed line. A missing scanner module also fails open (an install issue, not
    a secret)."""
    _hooks = str(Path(__file__).resolve().parent.parent / "hooks")
    if _hooks not in sys.path:
        sys.path.insert(0, _hooks)
    try:
        import secret_scan_before_ship as ss
    except Exception:  # noqa: BLE001 -- scanner unavailable: additive coverage absent
        return None
    diff = _pushed_diff(root, refs_text)
    if diff is None:
        return None  # fail-OPEN: see docstring -- never brick a push on a git error
    hits = ss.scan_diff_text(diff)
    if hits:
        return ("push blocked: the diff being pushed contains likely secrets (%s) -- "
                "remove them from the commits (rotate if real) before pushing."
                % ", ".join(str(h) for h in hits))
    return None


def check(refs_text, root, remote=None):
    """The block-reason for this push, or None to allow. A delete or non-ff of a
    protected branch is refused outright (the merge_gate floor); otherwise a
    protected-branch push is judged at merge grade, also through the floor. The
    ``remote`` (git's pre-push $1) lets the non-ff check recover an absent
    object on a shallow clone."""
    import artifact_check

    destructive = destructive_to_protected(refs_text, root, remote=remote)
    if destructive:
        import guard_policy
        return guard_policy.gate("merge_gate", destructive, hook="push_gate")

    # a secret block is absolute -- intentionally NOT routed through the
    # merge_gate floor, so a break-glass preset cannot lower it.
    secret = _secret_reason(root, refs_text)
    if secret:
        return secret

    # Personal-first transport: the two Tier-A floors above (destructive-to-protected
    # + secret) still BLOCK. A missing/failed receipt only WARNs here — local
    # generates receipts, the remote receipts-gate enforces them.
    stage = stage_for(refs_text)
    reason = artifact_check.check_stage(stage, root)
    if reason:
        sys.stderr.write(
            "[pre-push warn] %s — remote receipts-gate will enforce\n" % reason)
    return None
