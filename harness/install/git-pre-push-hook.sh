#!/bin/sh
# git-pre-push-hook.sh — transport-level stage gate for `git push`.
#
# Defense-in-depth behind the PreToolUse(Bash) gate: the Bash-command
# detector is boundary-strict and cannot see a push spelled through
# `sh -c 'git push'`, eval, aliases, or a wrapper script — but EVERY push,
# however spelled, passes through this git hook. The installer copies this
# file to .git/hooks/pre-push (chmod +x); it is never active by mere presence
# in the repo.
#
# ENV SCRUB (transport posture): before judging the push, every HARNESS_*
# variable is unset — scrub by PREFIX, not by a name list (a denylist rots
# the moment a loader grows a new env knob: HARNESS_STATE_DIR and
# HARNESS_OWNERSHIP_FILE already slipped past the old four-name idea). The
# repo root comes from `git rev-parse --show-toplevel`. Net effect: a real
# push is judged ONLY by tracked code and tracked config in THIS repo —
# pointing HARNESS_ROOT/HARNESS_STAGE_POLICY/anything-HARNESS_* at permissive
# copies changes nothing here.
#
# Honest limits: the ACTIVE copy of this file lives at .git/hooks/pre-push,
# OUTSIDE the manifest's reach — deleting or editing that copy is not caught
# by manifest verification. verify_install --strict compares the installed
# copy against this source when one exists and names any difference; a repo
# where the hook was never installed gets a warning, not a failure.
# Missing Python fails CLOSED — a transport gate that silently passes when
# its interpreter is gone protects nothing.

# --- scrub: drop every HARNESS_* override before the gate sees the world ---
for _v in $(env | sed -n 's/^\(HARNESS_[A-Za-z0-9_]*\)=.*/\1/p'); do
    unset "$_v"
done

REPO_ROOT=$(git rev-parse --show-toplevel 2>/dev/null)
if [ -z "$REPO_ROOT" ]; then
    echo "pre-push: not inside a git repository — cannot resolve the repo" >&2
    echo "root to judge this push against. Run from a git work tree." >&2
    exit 2
fi

# The interpreter name differs by platform (POSIX python3, a stock Windows
# install python / py), so probe in order; a missing interpreter fails CLOSED.
PY=""
for _cand in python3 python "py -3"; do
    _name=${_cand%% *}
    command -v "$_name" >/dev/null 2>&1 || continue
    PY="$_cand"; break
done
if [ -z "$PY" ]; then
    echo "pre-push: no Python found (looked for python3, python, py -3) — the" >&2
    echo "stage gate cannot run. Install Python, or in an emergency remove" >&2
    echo ".git/hooks/pre-push (verify_install --strict reports an installed" >&2
    echo "copy that differs from the source; a removed copy shows 'not installed')." >&2
    exit 2
fi

# --- capture git's ref-update stdin BEFORE the heredoc shadows it ---
# git feeds the pre-push hook one line per ref on stdin; the heredoc below
# would otherwise inherit (and never read) it. Empty stdin -> the legacy
# 'push' judgement (back-compat). The push_gate routes a protected-branch
# push to the merge-grade gate.
PUSH_REFS="$(cat)"
export PUSH_REFS

# git passes the push DESTINATION as positional args: $1 = remote name
# (or URL), $2 = remote URL. The gate uses it to fetch an absent object
# when deciding whether a protected-branch push is a fast-forward (the
# shallow-clone case).
PUSH_REMOTE="$1"
export PUSH_REMOTE

REPO_ROOT="$REPO_ROOT" $PY - <<'PYEOF'
import os
import sys

# Post-scrub, the ONLY root is the git toplevel exported above.
root = os.environ["REPO_ROOT"]
sys.path.insert(0, os.path.join(root, "harness", "scripts"))

try:
    import push_gate
except ImportError as e:
    sys.stderr.write(
        "pre-push BLOCKED: cannot load the stage gate (%s).\n"
        "Run: python3 harness/scripts/preflight_deps.py\n"
        "or:  pip install pyyaml pytest\n" % e)
    sys.exit(2)

try:
    reason = push_gate.check(os.environ.get("PUSH_REFS", ""), root,
                             remote=os.environ.get("PUSH_REMOTE") or None)
except ImportError as e:
    # PyYAML imports lazily inside load_policy — a machine that skipped
    # preflight should get the install command, same as the main gate.
    sys.stderr.write(
        "pre-push BLOCKED: dependency missing (%s).\n"
        "Run: python3 harness/scripts/preflight_deps.py\n"
        "or:  pip install pyyaml pytest\n" % e)
    sys.exit(2)
except Exception as e:  # noqa: BLE001 — fail CLOSED at the transport layer too
    sys.stderr.write("pre-push BLOCKED: gate crashed (%s: %s)\n"
                     % (type(e).__name__, e))
    sys.exit(2)

if reason:
    sys.stderr.write("pre-push BLOCKED: %s\n" % reason)
    sys.exit(2)
sys.exit(0)
PYEOF
