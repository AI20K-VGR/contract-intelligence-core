#!/usr/bin/env python3
"""protected_ref_guard.py — PreToolUse(Bash) compliance hook: protect refs.

Refuses three dangerous Bash commands, defense-in-depth ahead of the transport
pre-push hook (which is the authoritative floor — it reads git's real ref
stdin and is immune to command-string spelling):
  * force-push / history-rewrite to a protected ref — FLOOR
    (protected_ref_force_push, never lowered by a preset).
  * deletion of a protected ref (`git push origin :main` / `--delete`) — same
    FLOOR (deleting a protected branch is as destructive as a rewrite).
  * a direct `git commit` while the current branch is protected — enforcement
    (protected_ref_commit, lowers to warn under lenient).

Whether a command IS a push/commit is decided by stage_detector (the same
boundary-strict detector the stage gate uses), so env-assignment and
exec-wrapper prefixes (`sudo`, `env`, `VAR=val …`) and option spellings are
handled consistently with the rest of the harness. Target extraction
over-approximates in the SAFE direction: a false refusal on a FLOOR guard is
recoverable via a logged break-glass, a miss is a hole. A missing
protected-branch policy protects nothing (additive).
"""
import os
import sys

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_HERE)
sys.path.append(os.path.join(os.path.dirname(_HERE), "scripts"))

import hook_runtime  # noqa: E402

HOOK_CLASS = "compliance"
_HOOK = "protected_ref_guard"

_FORCE_FLAGS = {"--force", "-f", "--force-with-lease", "--force-if-includes"}
_DELETE_FLAGS = {"--delete", "-d", "--prune"}

# Flags that reach EVERY branch on the remote without naming one. They are the
# reason the "no refspec means the current branch" fallback is unsafe: on a
# feature branch it reported that harmless feature as the only target, so
# `--mirror`, `--all --force` and `--prune` were all allowed while standing next
# to a protected main. `--tags` is deliberately NOT here — it moves tags, and a
# protected BRANCH is out of its reach.
_BROADCAST_FLAGS = {"--all", "--mirror", "--prune"}

# git's shorthands for "the branch I am on". As a refspec destination they used to
# come out as the literal text, which matches no protected pattern — so
# `git push --force origin HEAD` rewrote main and read as an unknown ref.
_HEAD_ALIASES = {"HEAD", "@"}


def _current_branch():
    import subprocess
    try:
        out = subprocess.run(["git", "rev-parse", "--abbrev-ref", "HEAD"],
                             capture_output=True, text=True, timeout=10)
    except Exception:  # noqa: BLE001 — no git → no branch to protect
        return ""
    return out.stdout.strip() if out.returncode == 0 else ""


def _tokens(command):
    import shlex
    try:
        return shlex.split(command)
    except ValueError:
        return command.split()


def _refspec_dst(spec):
    """Destination branch from a refspec: '+src:dst'->dst, ':dst'->dst,
    'src:dst'->dst, 'branch'->branch; leading '+' and refs/heads/ stripped."""
    spec = spec.lstrip("+")
    if ":" in spec:
        spec = spec.split(":", 1)[1]
    if spec.startswith("refs/heads/"):
        spec = spec[len("refs/heads/"):]
    return spec


def _push_analysis(toks):
    """(is_force, is_delete, target_branches) from a `git push` token list.

    --repo supplies the remote, so every positional is a refspec; otherwise the
    first positional is the remote and the rest are refspecs. A '+'-prefixed
    refspec is itself a force; a ':dst' refspec or a --delete/-d flag is a
    delete. With no explicit refspec the target is the current branch (what a
    bare `git push` updates)."""
    if "push" not in toks:
        return False, False, set()
    after = toks[toks.index("push") + 1:]
    is_force = any(t in _FORCE_FLAGS or t.startswith("--force-with-lease=")
                   for t in after)
    is_delete = any(t in _DELETE_FLAGS for t in after)
    # --mirror implies both force + delete (mirrors all ref deletions from remote)
    if "--mirror" in after:
        is_force = True
        is_delete = True
    # git accepts bundled short flags (-fu = --force --set-upstream,
    # -df = --delete --force): decode any single-dash bundle.
    for t in after:
        if len(t) >= 2 and t.startswith("-") and not t.startswith("--"):
            bundle = t[1:]
            # -o takes an attached value (--push-option), e.g. -odeploy;
            # chars from the o onward are the value, not bundled flags.
            if "o" in bundle:
                bundle = bundle[:bundle.index("o")]
            is_force = is_force or "f" in bundle
            is_delete = is_delete or "d" in bundle
    positionals = [t for t in after if not t.startswith("-")]
    has_repo = any(t == "--repo" or t.startswith("--repo=") for t in after)
    refspecs = positionals if has_repo else positionals[1:]
    if any(s.startswith("+") for s in refspecs):
        is_force = True
    if any(s.startswith(":") for s in refspecs):
        is_delete = True
    targets = {_refspec_dst(s) for s in refspecs if _refspec_dst(s)}
    # `HEAD` / `@` name the current branch. Resolved on the DESTINATION only —
    # _refspec_dst has already taken the right-hand side, so `HEAD:feature` keeps
    # feature and is not re-pointed at whatever HEAD is.
    if targets & _HEAD_ALIASES:
        cur = _current_branch()
        targets -= _HEAD_ALIASES
        if cur:
            targets.add(cur)
    if not targets:
        cur = _current_branch()
        if cur:
            targets = {cur}
    return is_force, is_delete, targets


def _is_broadcast(toks):
    """True when the push reaches every ref on the remote instead of a named one.

    Kept separate from _push_analysis so that function stays a pure
    command-string reading with a stable 3-tuple: resolving "every ref" needs the
    protected-branch POLICY, which is IO, and core owns that."""
    if "push" not in toks:
        return False
    return any(t in _BROADCAST_FLAGS for t in toks[toks.index("push") + 1:])


def core(data: dict):
    import branch_policy
    import guard_policy
    import stage_detector

    command = hook_runtime.bash_command(data)
    if not command.strip():
        return None
    session = data.get("session_id")
    actor = hook_runtime.resolve_actor(session_id=session)
    stage = stage_detector.detect_stage(command)

    # 1) force-push / delete / history-rewrite to a protected ref — FLOOR guard.
    if stage == "push":
        toks = _tokens(stage_detector.unwrapped(command))
        is_force, is_delete, targets = _push_analysis(toks)
        broadcast = _is_broadcast(toks)
        if broadcast:
            # A broadcast push names no refspec, so the "current branch" fallback
            # answers with the one branch it is NOT about. Every configured
            # protected pattern is in reach, so every one of them is a target.
            # Additive by design: with no policy this adds nothing and the push
            # stays allowed, which is the guard's documented posture.
            targets = set(targets) | set(branch_policy.load_protected())
        if is_force or is_delete:
            hit = sorted(b for b in targets if branch_policy.is_protected(b))
            if hit:
                verb = "force-push to" if is_force else "deletion of"
                if broadcast:
                    # Say what was actually seen. The entries in `hit` are the
                    # configured PATTERNS, not refs this command named — calling
                    # them "the refs you targeted" sends the author looking for a
                    # ref they never typed, and a refusal nobody can act on costs
                    # the same as a false positive.
                    flag = ", ".join(sorted(set(toks) & _BROADCAST_FLAGS))
                    reason = ("refusing a %s that reaches EVERY ref on the remote "
                              "(%s) while these are protected: %s — name the one "
                              "branch you mean instead (`git push origin "
                              "<branch>`)"
                              % ("force-push" if is_force else "ref deletion",
                                 flag, ", ".join(hit)))
                else:
                    reason = ("refusing %s protected ref(s): %s — a history "
                              "rewrite or deletion on a protected branch is blocked"
                              % (verb, ", ".join(hit)))
                return guard_policy.gate("protected_ref_force_push", reason,
                                         hook=_HOOK, actor=actor, session=session)

    # 2) direct commit while the current branch is protected — enforcement.
    if stage == "commit":
        cur = _current_branch()
        if cur and branch_policy.is_protected(cur):
            reason = ("refusing direct commit on protected branch %r — branch "
                      "off and open a reviewed change instead" % cur)
            return guard_policy.gate("protected_ref_commit", reason,
                                     hook=_HOOK, actor=actor, session=session)
    return None


def main() -> None:
    hook_runtime.compliance_skip_or_run(_HOOK, core, skip_event="protected_ref_skip")


if __name__ == "__main__":
    main()
