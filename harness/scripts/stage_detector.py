#!/usr/bin/env python3
"""stage_detector.py — map a Bash command to the SDLC stage it advances.

detect_stage(command) returns one of push|commit|pr|ship|deploy, or None.
Patterns are BOUNDARY-STRICT: they only match where a command can
actually start — string start or right after `;`, `&`, `|`, `(`, or a
newline. So `echo "git push"` (the string is an argument) and `git pushing`
(word boundary) do NOT match.

Wrapper reach (hardening): a wrapper AT a command head is unwrapped and
recursed — `sh -c 'git push'`, `bash -c "..."`, `eval '...'` — and a
path-qualified binary (`/usr/bin/git`, `./gh`) is still that binary. A wrapper
name INSIDE a quoted argument is NOT unwrapped (boundary rule), and obfuscation
the unwrap cannot reach (unquoted eval args, `$var` indirection, base64) stays
the floor. The git pre-push hook still covers the push stage at the transport
level regardless of how the push command was spelled. guess_stage() additionally
samples a NARROW set of free-floating words — only the ship/deploy class
(release / publish / ship / deploy*, see _GUESS_PATTERNS) — as advisory trace
(never a gate signal). push/commit/pr words are deliberately NOT sampled: they
are far too common in ordinary prose to be signal, so a wrapper-hidden
`sh -c 'git push'` stays invisible to this guess channel and is covered ONLY by
the transport-level pre-push hook, not by the trace sample.
"""

import re

# Where a command head can begin: start-of-string or right after a shell
# separator. Quoted strings never satisfy this, which is the whole point.
# Backtick opens a command substitution and `{` a brace group — both run
# their body, so both are command positions. A backtick inside single quotes
# is literal text; treating it as a boundary anyway can only over-detect
# (false block), never let a real stage command through.
_BOUNDARY = r"(?:^|[;&|({\n`])\s*"

# `do`/`then`/`else` introduce a command position inside compound statements
# (loop and conditional bodies). Whole words only — `dosomething` is a name.
_KEYWORDS = r"(?:(?:do|then|else)\s+)*"

# Benign prefixes that leave the following verb a real command head — they
# RUN their argument vector rather than quoting it:
#   * VAR=value assignments, values possibly quoted;
#   * exec-style wrappers (sudo, env, timeout 30, nice -n 10, …) with their
#     own flags. `-u <arg>`/`-g <arg>`/`-p <arg>`/`-n <arg>` are the
#     separated-argument flags these wrappers commonly take (`-p` is npx's
#     --package); bare numbers cover timeout durations. The package-runner
#     wrappers (`npx`/`bunx`, and the two-token `pnpm dlx`/`yarn dlx`) RUN the
#     following tool, so `npx vercel deploy` is a real deploy — they belong
#     here. `sh -c '…'` stays out by design: its payload is a quoted string, not
#     a command head (documented limitation).
_PREFIXES = (
    r"(?:(?:\w+=(?:'[^']*'|\"[^\"]*\"|\S*)"
    r"|(?:sudo|env|command|exec|eval|nohup|nice|stdbuf|timeout|time|xargs|npx|bunx|setsid|doas|chronic|ifne)"
    r"(?:\s+(?:-[ugpn]\s+\S+|-{1,2}[\w.,:=/+-]+|\d+(?:\.\d+)?[smhd]?))*"
    r"|(?:pnpm|yarn)\s+dlx(?:\s+(?:-{1,2}[\w.,:=/+-]+))*"
    r"|flock(?:\s+(?:-[sxun]+|-w\s+\d+|-{1,2}[\w.,:=/+-]+))*\s+[^\s-]\S*"
    r")\s+)*"
)

# A binary may be named by a path: `/usr/bin/git`, `./gh`, `bin/vercel`. The
# verb head is still that tool, so allow an optional path prefix before it.
_PATHPFX = r"(?:[\w./+-]*/)?"

_HEAD = _BOUNDARY + _KEYWORDS + _PREFIXES + _PATHPFX

# Ordered: first hit wins. More specific stages (pr/ship/deploy) before the
# generic git verbs is not required — patterns are mutually exclusive — but
# keep deploy CLIs grouped for readability.
# `\b` treats `-` as a boundary, so `push\b` would match `push-helper`; the
# lookahead requires a real end-of-word (whitespace/end/separator) instead.
_EOW = r"(?![\w-])"
# Line continuation (`\\\n`) is not whitespace, so `git \\<nl>push` would slip
# `git\\s+push`; join it. And the shell strips quotes around a verb, so
# `npm "publish"` runs publish — unwrap quotes that wrap a release verb only
# (quotes wrapping a whole `sh -c` payload wrap the command, not the verb).
_LINE_CONT_RE = re.compile(r"\\\r?\n")
# Intra-token quoting collapses to the bare token in the shell, so also match a
# collapsed view: strip a quote (optionally $-prefixed) or a backslash before a
# letter. Catches the partially-quoted / ANSI-C / escaped verb spellings.
_INTRA_QUOTE_RE = re.compile(r"""\$?['\"]|\\(?=[A-Za-z])""")
_VERB_QUOTE_RE = re.compile(
    r"""([\'"])(publish|deploy|push|commit|create|merge|ready|upload)\1""")

# Intervening flags/args between a tool and its verb must not let a publish/deploy
# slip the gate: `npm --registry x publish`, `vercel --prod deploy`. Mirror the
# flag-tolerance the git push/commit patterns already use (a flag is -x / --xx with
# an optional =value or space value). Over-detection favors fail-closed by design.
_FLAGS = r"(?:-[-\w]+(?:[= ]\S+)?\s+)*"

# Pattern SPECS (uncompiled) — compiled lazily on first detect via _stage_patterns.
# Keeping these as strings makes `import stage_detector` cheap: the ~30-regex
# battery is a per-PreToolUse:Bash cold-compile the tier-1 gate below avoids for
# any command that carries no tool token (the common case).
_STAGE_SPECS = [
    ("push", _HEAD + r"git\s+(?:-[-\w]+(?:[= ]\S+)?\s+)*push" + _EOW),
    ("commit", _HEAD + r"git\s+(?:-[-\w]+(?:[= ]\S+)?\s+)*commit" + _EOW),
    ("pr", _HEAD + r"gh\s+" + _FLAGS + r"pr\s+(?:create|merge|ready)" + _EOW),
    ("ship", _HEAD + r"gh\s+" + _FLAGS + r"release\s+create" + _EOW),
    ("ship", _HEAD + r"(?:npm|pnpm|yarn)\s+" + _FLAGS + r"publish" + _EOW),
    ("ship", _HEAD + r"(?:bun|deno)\s+" + _FLAGS + r"publish" + _EOW),
    # Polyglot package release verbs — each unambiguously ships a package; the
    # in-session gate is their only gate (no git transport to backstop).
    ("ship", _HEAD + r"cargo\s+" + _FLAGS + r"publish" + _EOW),
    ("ship", _HEAD + r"poetry\s+" + _FLAGS + r"publish" + _EOW),
    ("ship", _HEAD + r"twine\s+" + _FLAGS + r"upload" + _EOW),
    ("ship", _HEAD + r"gem\s+" + _FLAGS + r"push" + _EOW),
    ("ship", _HEAD + r"dotnet\s+nuget\s+" + _FLAGS + r"push" + _EOW),
    ("deploy",
        _HEAD + r"(?:wrangler|vercel|netlify|firebase|fly|flyctl|railway)\s+" + _FLAGS + r"deploy" + _EOW),
    ("deploy", _HEAD + r"(?:npm|pnpm|yarn)\s+" + _FLAGS + r"(?:run\s+)?deploy" + _EOW),
    # container / registry image + chart push -> ship (a pushed artifact with a
    # baked secret cannot be unpublished)
    ("ship", _HEAD + r"(?:docker|podman)\s+" + _FLAGS + r"push" + _EOW),
    ("ship", _HEAD + r"docker\s+buildx\b[^\n]*--push"),
    ("ship", _HEAD + r"(?:helm|oras)\s+" + _FLAGS + r"push" + _EOW),
    ("ship", _HEAD + r"skopeo\s+" + _FLAGS + r"copy" + _EOW),
    # more polyglot release verbs
    ("ship", _HEAD + r"mvn\s+" + _FLAGS + r"deploy" + _EOW),
    ("ship", _HEAD + r"gradle\s+" + _FLAGS + r"publish" + _EOW),
    ("ship", _HEAD + r"goreleaser\s+" + _FLAGS + r"release" + _EOW),
    # infra deploy CLIs -> deploy (apply / install mutate live infra)
    ("deploy", _HEAD + r"terraform\s+" + _FLAGS + r"apply" + _EOW),
    ("deploy", _HEAD + r"kubectl\s+" + _FLAGS + r"apply" + _EOW),
    ("deploy", _HEAD + r"helm\s+" + _FLAGS + r"(?:install|upgrade)" + _EOW),
    ("deploy", _HEAD + r"(?:serverless|sls)\s+" + _FLAGS + r"deploy" + _EOW),
    ("deploy", _HEAD + r"gcloud\s+" + _FLAGS + r"(?:app|run|functions)\s+deploy" + _EOW),
    ("deploy", _HEAD + r"aws\s+" + _FLAGS + r"(?:deploy|cloudformation\s+deploy)" + _EOW),
    ("deploy", _HEAD + r"eb\s+" + _FLAGS + r"deploy" + _EOW),
]

# Free-floating words worth SAMPLING (advisory `stage_guess` trace event):
# they appear anywhere — file names, sh -c payloads, prose — so they are far
# too noisy to gate on, but exactly the data that reveals evasion patterns.
_GUESS_SPECS = [
    ("ship", r"\b(?:release|publish)\b"),
    ("ship", r"\bship\b"),
    ("deploy", r"\bdeploy\w*\b"),
]

# Tier 1 — cheap literal gate. Every stage/wrapper pattern is anchored on one of
# these tool/wrapper heads at a word boundary; a command containing none of them
# (in either the raw or quote-collapsed view) cannot match, so detect_stage bails
# before compiling or running the battery. Sound: the anchoring token always
# appears \b-bounded in a real match (a path prefix ends in `/`, a benign prefix
# in whitespace), so \b(?:…)\b matches whenever any pattern would.
_TRIGGER_RE = re.compile(
    r"\b(?:git|gh|npm|pnpm|yarn|bun|deno|cargo|poetry|twine|gem|dotnet|docker|"
    r"podman|helm|oras|skopeo|mvn|gradle|goreleaser|terraform|kubectl|"
    r"serverless|sls|gcloud|aws|eb|wrangler|vercel|netlify|firebase|fly|flyctl|"
    r"railway|sh|bash|dash|zsh|ash|ksh|eval)\b")

# Lazily-compiled batteries (None until first use — see the accessors below).
_STAGE_PATTERNS = None
_GUESS_PATTERNS = None
_WRAPPERS = None


def _stage_patterns():
    global _STAGE_PATTERNS
    if _STAGE_PATTERNS is None:
        _STAGE_PATTERNS = [(stage, re.compile(rx)) for stage, rx in _STAGE_SPECS]
    return _STAGE_PATTERNS


def _guess_patterns():
    global _GUESS_PATTERNS
    if _GUESS_PATTERNS is None:
        _GUESS_PATTERNS = [(stage, re.compile(rx)) for stage, rx in _GUESS_SPECS]
    return _GUESS_PATTERNS


# Wrapper unwrap (boundary-anchored, so a wrapper name inside a quoted argument
# is NOT unwrapped): `sh -c '<payload>'` / `bash -c "<payload>"` and
# `eval '<payload>'` hide the real command head in a quoted string the
# boundary-strict patterns cannot see. detect_stage recurses, so a nested
# `sh -c 'sh -c "git push"'` resolves by repeated unwrap. Obfuscation the unwrap
# does NOT reach (unquoted eval args, `$var` indirection, base64) stays the
# documented floor — the transport pre-push hook backstops push regardless.
_WRAP_C_SPEC = (
    _BOUNDARY + _KEYWORDS + _PREFIXES +
    r"(?:[\w./+-]*/)?(?:sh|bash|dash|zsh|ash|ksh)(?:\s+--?[\w-]+)*?\s+-\w*c\s+"
    r"(['\"])(.*?)\1")
_EVAL_SPEC = _BOUNDARY + _KEYWORDS + _PREFIXES + r"eval\s+(['\"])(.*?)\1"


def _wrappers():
    global _WRAPPERS
    if _WRAPPERS is None:
        _WRAPPERS = (re.compile(_WRAP_C_SPEC, re.S), re.compile(_EVAL_SPEC, re.S))
    return _WRAPPERS


def detect_stage(command):
    """Stage name for a command that REALLY advances that stage, else None."""
    if not command or not isinstance(command, str):
        return None
    command = _LINE_CONT_RE.sub(" ", command)
    collapsed = _INTRA_QUOTE_RE.sub("", command)
    # Tier 1: no tool/wrapper token in either view -> no pattern can match. Bail
    # before the lazily-compiled battery (the cost path this hook pays per Bash).
    if not (_TRIGGER_RE.search(command) or _TRIGGER_RE.search(collapsed)):
        return None
    command = _VERB_QUOTE_RE.sub(r"\2", command)
    views = [command]
    if collapsed != command:
        views.append(collapsed)
    for view in views:
        for stage, pattern in _stage_patterns():
            if pattern.search(view):
                return stage
    # No direct head: try unwrapping a boundary-anchored wrapper and recurse.
    for rx in _wrappers():
        for m in rx.finditer(command):
            inner = detect_stage(m.group(2))
            if inner:
                return inner
    return None


def unwrapped(command):
    """The inner command of a boundary-anchored sh -c / bash -c / eval wrapper,
    peeled to the deepest level (or `command` itself if not wrapped). Lets a gate
    that branches on detect_stage analyze the command detect_stage actually
    MATCHED, instead of re-parsing the outer wrapper string (which hides the inner
    refspec/flags/cd)."""
    if not isinstance(command, str):
        return command
    wrap_c, eval_re = _wrappers()
    for _ in range(6):
        m = wrap_c.search(command) or eval_re.search(command)
        if not m:
            break
        command = m.group(2)
    return command


def guess_stage(command):
    """Advisory-only guess from free-floating stage words. Never a gate
    signal — feeds the `stage_guess` trace sampling. None when nothing hints."""
    if not command or not isinstance(command, str):
        return None
    hard = detect_stage(command)
    if hard:
        return hard
    for stage, pattern in _guess_patterns():
        if pattern.search(command):
            return stage
    return None
