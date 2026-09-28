#!/usr/bin/env python3
"""floor_bash_guard.py — PreToolUse(Bash) compliance floor for Bash-spelled writes.

Closes the "guard blind to Bash" hole: write_guard sees tool Writes,
not `echo >`, `sed -i`, `tee`, `cp`. This gate blocks a Bash write into the deny-list
floor (core-immune, OR harness/** minus the tests carve), fail-closed, for EVERY actor
— the Bash path never reads agent_type (probed: gate_stage / bash_write_guard /
bash_safety_guard do not), so there is NO parent exemption here (mirrors write_guard's
whole-bin catch-all "for every actor").

Detection is two arms plus two narrow extras:
  ARM 1 (precise): shell_write_targets() -> each resolved write target -> deny_matcher.
    A hard-tier target blocks. This is a WRITE floor, not a read gate: `cat core > /tmp/y`
    writes /tmp/y (allowed); reading guard source does not disarm the cage.
  ARM 2 (obfuscation, triple-coincidence): a wrapper token (eval / sh -c / python -c /
    $() / backtick / xargs) AND a protected-zone literal AND a write-verb, all in the RAW
    command -> block. shell_write_targets returns 0 candidates for a quoted/wrapped write,
    so without this the wrapper is a clean bypass. Over-block is bounded to the triple-
    coincidence (undecidable read/write inside a wrapper).
  ln-into-carve: `ln -s* <src> harness/tests/**` + a redirect in the same command ->
    block. The symlink does not exist yet at PreToolUse, so realpath membership cannot
    catch it; block on the command shape instead.
  dynamic tail: a write token with an unresolved $VAR whose directory-qualified tail
    (e.g. `hooks/<name>.py`, derived from CORE_IMMUNE, never a bare *.py) matches a core
    tail -> block.

RESIDUAL — NOT airtight (honesty, mirrors write_guard's own scope note): a fully dynamic
no-literal target (`D=harness/hooks; echo x > $D/x.py`) or a base64/encoded construction
slips arm 2 (no protected literal in the raw text). Those are caught by the detective tier
+ git-diff + (shared bin) OS-level read-only, NOT here. This floor is a speed bump +
tamper-EVIDENT record, not an airtight wall.
"""
import fnmatch
import os
import re
import sys
from pathlib import Path

_HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.append(_HERE)
sys.path.append(os.path.join(os.path.dirname(_HERE), "scripts"))

import hook_runtime     # noqa: E402
import trace_log        # noqa: E402
import write_guard      # noqa: E402
import bash_write_guard  # noqa: E402 — reuse shell_write_targets (one parser, N observers)
import deny_matcher     # noqa: E402
import write_deny_policy as wdp  # noqa: E402

HOOK_CLASS = "compliance"
_HOOK = "floor_bash_guard"
_POLICY_REL = "harness/data/write-deny-policy.yaml"

# A shell construct that hides a write from the token parser (wrapper gate).
_WRAPPER_RE = re.compile(
    r"(?:\beval\b|\bxargs\b|\bsh\s+-c\b|\bbash\s+-c\b|\bpython3?\s+-c\b|\$\(|`)")
# A write verb/redirect anywhere in the raw command (write-verb gate). `open(` counts
# ONLY with a write mode ('w'/'a'/'x' in a 2nd arg) — a bare open()/open(...).read() is
# a read and must not trip the WRITE floor. A redirect followed by `&` is a file
# DESCRIPTOR duplication (`2>&1`, `>&2`), not a filesystem write, so it must not
# count either: under a global install every harness CLI is spelled with an
# absolute $HARNESS_BIN_ROOT/harness/... path (a protected literal), which made a
# documented command ending in `2>&1` trip the wrapper arm's triple-coincidence.
# `&>file` still matches — its `>` is followed by the target, not by `&`.
_WRITE_VERB_RE = re.compile(
    r"(?:>>?(?!&)|\btee\b|\bsed\s+-i|\bdd\b[^\n]*\bof=|\.write_text|\.write_bytes|"
    r"\.truncate\b|\binstall\b|\bln\s+-s|\bopen\s*\([^,)]*,[^)]*['\"][^'\")]*[waxWAX]|"
    r"\.write\b)")
# A real redirect (NOT counting the ln itself) — the "write after the ln".
_REDIRECT_RE = re.compile(r"(?:>>?(?!&)|\btee\b|\bsed\s+-i|\bdd\b[^\n]*\bof=)")
# ln -s / ln -sf whose link name lands inside the tests carve.
_LN_INTO_CARVE_RE = re.compile(r"\bln\s+-s\w*\b[^\n;&|]*\bharness/tests/")


def _resolve_roots():
    """(bin_root, [roots]) from agent-uncontrolled sources; ([], []) when the bin
    root cannot be resolved so the caller fails closed."""
    try:
        bin_root = write_guard._bin_root()
    except Exception:  # noqa: BLE001
        return None, []
    if not bin_root or not Path(bin_root).is_dir():
        return None, []
    roots = [Path(bin_root)]
    try:
        proj = write_guard._project_root(bin_root)
    except Exception:  # noqa: BLE001
        proj = None
    if proj and Path(proj).is_dir() and Path(proj).resolve() != Path(bin_root).resolve():
        roots.append(Path(proj))
    return bin_root, roots


def _policy(bin_root):
    try:
        soft = wdp.load_soft_rules(Path(bin_root) / _POLICY_REL)
    except wdp.DenyPolicyError:
        soft = []  # detective config broken: keep the HARD floor, drop soft (never brick)
    return wdp.assemble_policy(soft)


def _dir_tails(core_immune):
    """Directory-qualified tails (last-dir/filename) derived from CORE_IMMUNE — for
    the dynamic-prefix check. Never a bare `*.py` (that would over-block every .py)."""
    tails = set()
    for glob in core_immune:
        segs = glob.split("/")
        if len(segs) >= 2 and not any(c in segs[-2] for c in "*?["):
            tails.add(segs[-2] + "/" + segs[-1])
    return tails


def _wild_index(s):
    for i, ch in enumerate(s):
        if ch in "*?[":
            return i
    return len(s)


def _protected_literals(policy):
    """Specific raw-text needles for the obfuscation-wrapper gate. A needle is a
    wildcard-free literal path, a whole-subtree prefix (`<dir>/**` -> `<dir>/`), a
    multi-segment prefix (`harness/hooks/`), or — for a glob whose only literal prefix
    is a single top-level dir that is otherwise an ALLOW zone (e.g.
    `plans/*/artifacts/plan-approval.json`) — the distinctive tail (`plan-approval.json`).
    NEVER a bare single allow-zone segment like `plans/` (that over-blocks every wrapped
    write under plans/); arm-1's precise resolve still catches those exact targets."""
    lits = set()
    for glob in tuple(policy.core_immune) + tuple(policy.hard_binary_deny):
        if not any(c in glob for c in "*?["):
            if len(glob) >= 4:
                lits.add(glob)  # literal path: .env, docs/decisions.yaml
            continue
        pre = glob[:_wild_index(glob)].rstrip("/")
        if glob in (pre + "/**", pre + "/*"):
            if len(pre) >= 3:
                lits.add(pre + "/")  # whole subtree: harness/, .git/, the cage hooks slot
        elif "/" in pre and len(pre) >= 6:
            lits.add(pre + "/")  # multi-segment prefix: harness/hooks/
        else:
            base = glob.rsplit("/", 1)[-1]
            base = base[:_wild_index(base)]
            if len(base) >= 5:
                lits.add(base)  # distinctive tail: plan-approval.json
    return lits


def _has_protected_literal(command, policy):
    """True when a protected-zone needle appears in the raw command. A directory needle
    (ending `/`) matches as a substring; a file/dotfile needle anchors on a path boundary
    so `.env` matches neither `.environment` nor a `*.env.sample` template."""
    for lit in _protected_literals(policy):
        if lit.endswith("/"):
            if lit in command:
                return True
        elif re.search(r"(?<![\w.])" + re.escape(lit) + r"(?![\w.])", command):
            return True
    return False


def _dynamic_tail_hit(rel, tails):
    if "$" not in rel:
        return False
    return any(fnmatch.fnmatch(rel, "*/" + t) or fnmatch.fnmatch(rel, t) for t in tails)


# Arm name shared by the detector and the message builder, so the one arm
# that resolves no write target cannot drift back to claiming one.
_ARM_WRAPPER = "obfuscation-wrapper"

# The floor is not only the harness. It also holds git's own bookkeeping, a narrow
# secrets set, and the switches that arm the guards. One sentence saying "the
# protected harness floor" was accurate while the floor WAS the harness; it stopped
# being accurate when the git rule widened to any depth, because a nested
# `.git/config` belongs to git, and telling its author they wrote into the harness
# sends them looking in the wrong tree. A refusal the caller cannot act on costs the
# same as a false positive, so the subject is keyed off the rule that matched.
_GIT_RULES = ("**/.git/**", ".git")
_CLAUDE_PREFIX = ".claude/"   # kept short so no banned contiguous path appears here


# The default route out. It promises a reviewable diff, which is only true for a
# floor path that git actually tracks — so the two classes it is false for carry
# their own route instead. An empty promise is what makes a caller stop believing
# the rest of the message.
_ROUTE_TRACKED = ("Edit the file with an editor OUTSIDE the agent session; it is "
                  "git-tracked, so the change stays reviewable.")


def _floor_subject(rule):
    """(what the matched rule protects, how to change it legitimately) — both in
    the caller's own terms.

    Falls back to the harness wording for anything unrecognised, so a NEW rule
    added to the floor gets a correct-if-generic message rather than a confidently
    wrong specific one.
    """
    if rule in _GIT_RULES:
        return (("git's own bookkeeping — a write under a `.git` path can point git "
                 "at an arbitrary hook script, so the next git command in that tree "
                 "would run it"),
                # NOT "git-tracked": git's own state is not in the index, so there
                # would be no diff to review.
                ("Change it through git itself (`git config ...`) or with an editor "
                 "OUTSIDE the agent session."))
    if isinstance(rule, str) and rule.startswith(".env"):
        return ("a secrets file",
                # A dotenv is never committed, so promising a reviewable diff is
                # empty — and this is the one floor class where the file's contents
                # must not be echoed anywhere either.
                ("Edit it with an editor OUTSIDE the agent session; it is "
                 "deliberately never committed."))
    if isinstance(rule, str) and rule.startswith(_CLAUDE_PREFIX):
        return ("the switches that arm this harness's guards", _ROUTE_TRACKED)
    return ("the protected harness floor", _ROUTE_TRACKED)


def _block(data, target, arm, decision=None):
    session = data.get("session_id")
    tier = decision.tier if decision is not None else "hard"
    rule = decision.matched_rule if decision is not None else None
    try:
        trace_log.append_event(
            hook=_HOOK, event=wdp.EVENT_HARD_BLOCK, session=session,
            tool=data.get("tool_name"),
            actor=hook_runtime.resolve_actor(session_id=session),
            status="BLOCKED", note="arm=%s tier=%s rule=%s" % (arm, tier, rule),
            target=str(target).replace("\\", "/"))
    except Exception:  # noqa: BLE001 — the audit write is telemetry; never block on it
        pass
    if arm == _ARM_WRAPPER:
        # This arm resolved NO write target: it fired on a coincidence of a
        # wrapper (eval / sh -c / python -c), a write verb, and a protected
        # path appearing somewhere in the text. Saying "this command writes
        # into the floor" claims something the guard did not observe — and it
        # sent an author whose real write went to plans/ off to hand-edit a
        # floor file they were only reading.
        return (
            "floor: this Bash command WRAPS its real command (eval / sh -c / "
            "python -c), contains a write verb, and names a protected harness "
            "path — so the actual write target cannot be read out of it, and it "
            "is refused fail-closed for every actor. This is not a claim that "
            "the command writes into the floor; it is a refusal to guess. Run "
            "it UNWRAPPED (or split the compound so each write target is "
            "visible) and it will be judged on its real target. If you do mean "
            "to change a floor file, edit it with an editor OUTSIDE the agent "
            "session — it is git-tracked, so the change stays reviewable.")
    subject, route = _floor_subject(rule)
    return ("floor: this Bash command writes into %s ('%s', %s) — blocked "
            "fail-closed for every actor. %s" % (subject, str(target), arm, route))


def core(data: dict):
    """None ⇒ pass; string ⇒ block reason (run_compliance_hook contract)."""
    tool_input = data.get("tool_input")
    if not isinstance(tool_input, dict):
        return None
    command = tool_input.get("command")
    if not isinstance(command, str) or not command.strip():
        return None

    bin_root, roots = _resolve_roots()
    if not roots:
        return ("floor: cannot resolve the harness binary root, so a Bash write into "
                "the protected floor cannot be checked — blocked fail-closed. Set "
                "HARNESS_BIN_ROOT to the harness tree.")

    policy = _policy(bin_root)
    tails = _dir_tails(policy.core_immune)

    # Arm 1 — precise write targets (+ dynamic tail on the same tokens).
    for rel in bash_write_guard.shell_write_targets(command, include_copy_move=True):
        decision = deny_matcher.evaluate(Path(bin_root) / rel, policy, roots)
        if decision.is_hard:
            return _block(data, rel, "precise write-target", decision)
        if _dynamic_tail_hit(rel, tails):
            return _block(data, rel, "dynamic core-tail")

    # ln into the tests carve + a redirect in the same command (TOCTOU).
    if _LN_INTO_CARVE_RE.search(command) and _REDIRECT_RE.search(command):
        return _block(data, "harness/tests/<symlink>", "ln-into-carve TOCTOU")

    # Arm 2 — obfuscation-wrapper triple-coincidence.
    if (_WRAPPER_RE.search(command)
            and _WRITE_VERB_RE.search(command)
            and _has_protected_literal(command, policy)):
        return _block(data, "<wrapped>", _ARM_WRAPPER)

    return None


def main() -> None:
    hook_runtime.compliance_skip_or_run(_HOOK, core, skip_event="floor_bash_skip")


if __name__ == "__main__":
    main()
