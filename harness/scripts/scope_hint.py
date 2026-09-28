#!/usr/bin/env python3
"""scope_hint.py — Lever A: a coarse, suggest-only difficulty classifier.

Reads a raw user prompt and returns a difficulty band + whether a heavy SDLC
skill was invoked. The context-injection hook uses the verdict ONLY to append a
one-line advisory when a trivial task rides a heavy skill (e.g. `/hs:plan fix
typo`). It never selects a mode, never downgrades, never blocks — advisory input.

Design bias: over-flag AWAY from `trivial`. A false `trivial` is the harmful
verdict (it nudges "drop the plan/cook ceremony" over work that needed it), so
`trivial` requires POSITIVE evidence of a small scope — either a tiny-scope verb
(`typo`/`rename`/`bump version`) or 1..3 concretely-named files. Absence of any
signal (a prose task naming no file) reads `standard`, NOT `trivial`: the natural
way to invoke a heavy skill is prose, and the old `no file mention -> trivial`
default fired the nudge on the majority of legitimate `/hs:plan` calls.

The risky-keyword match is by STEM (substring), not word-boundary, so
`migrations`/`authentication`/`schemas` all trip `risky` — also the safe
direction, since a false `risky` merely WITHHOLDS the suggestion. Pure +
stdlib-only; must not import hook code (the hook imports it, not the reverse).
"""
import re

# Risky-topic stems (substring match on the lowercased prompt). Touching any of
# these is treated as high-stakes regardless of how few files are named — the
# suggestion engine must never nudge these toward a lighter path. Stems are
# truncated roots (e.g. `delet`, `truncat`, `migrat`) so plurals and variants
# (deletion, truncating, migrations) all trip. Includes destructive data/ops
# verbs, not just topics: a `drop the users table` under a heavy skill must never
# read as trivial.
_RISKY_STEMS = ("schema", "auth", "migrat", "pricing", "secret", "delet",
                "force", "rbac", "credential", "payment", "token",
                "drop", "truncat", "revoke", "grant", "deploy", "prod",
                "rollback", "wipe", "purge", "password", "permission",
                "apikey", "api key", "access key")

# Heavy SDLC skills where a trivial scope is worth a "consider a lighter mode"
# nudge. Matched as `hs:<name>` with an optional leading slash.
_HEAVY_SKILLS = ("plan", "cook", "ship", "discover", "understand", "review-pr",
                 "vibe", "team", "afk")
_HEAVY_RE = re.compile(r"/?hs:(" + "|".join(_HEAVY_SKILLS) + r")\b", re.IGNORECASE)

# Tiny-scope verb stems (substring match). Their presence is POSITIVE evidence of
# triviality even when no file is named — the one signal that lets a zero-file
# prompt read `trivial`. Kept tight and unambiguous: a too-generous list would
# re-introduce the false-`trivial` this rewrite exists to kill.
_TRIVIAL_STEMS = ("typo", "rename", "reword", "spelling", "docstring",
                  "bump version", "bump the version", "update comment",
                  "update the comment", "fix comment")

# A path-ish token: a slash-separated token, or a `name.ext` shape whose ext
# STARTS WITH A LETTER (so version numbers like 3.12 don't count as files). The
# slash branch is bounded ([^\s/]+) to avoid a greedy backtracking tail on a long
# slash-free prompt.
_PATHISH_RE = re.compile(r"[^\s/]+/[^\s/]+|\b[\w.-]+\.[A-Za-z]\w{0,4}\b")
# An explicit "N files/modules" count.
_NFILES_RE = re.compile(r"\b(\d+)\s+(?:files?|modules?|tests?)\b", re.IGNORECASE)

_TRIVIAL_FILE_CEILING = 3


def _file_mentions(text: str) -> int:
    """Best-effort count of distinct files the prompt implicates: the larger of
    the path-ish token count and any explicit 'N files' number. Scans a bounded
    prefix — the prompt is user-controlled and the count is a coarse band, so a
    length cap keeps the regex off a pathological tail."""
    text = text[:8000]
    pathish = {m.group(0) for m in _PATHISH_RE.finditer(text)}
    n_explicit = max((int(m.group(1)) for m in _NFILES_RE.finditer(text)), default=0)
    return max(len(pathish), n_explicit)


def classify(prompt_text) -> dict:
    """Return {level: trivial|standard|risky, reason, heavy_skill}. Never raises
    on odd input — a non-string or empty prompt is trivial with no heavy skill."""
    text = prompt_text if isinstance(prompt_text, str) else ""
    low = text.lower()
    heavy = bool(_HEAVY_RE.search(text))

    hit = next((s for s in _RISKY_STEMS if s in low), None)
    if hit:
        return {"level": "risky", "reason": "risky-topic stem %r" % hit,
                "heavy_skill": heavy}

    files = _file_mentions(text)
    if files > _TRIVIAL_FILE_CEILING:
        return {"level": "standard", "reason": "%d files, no risky stem" % files,
                "heavy_skill": heavy}

    # <=3 files, no risky stem. `trivial` now needs POSITIVE evidence, not the
    # mere absence of a large scope — a tiny-scope verb, or 1..3 named files.
    verb = next((s for s in _TRIVIAL_STEMS if s in low), None)
    if verb:
        return {"level": "trivial", "reason": "tiny-scope verb %r" % verb,
                "heavy_skill": heavy}
    if files >= 1:
        return {"level": "trivial", "reason": "%d named file(s), no risky stem" % files,
                "heavy_skill": heavy}

    # zero files, no tiny-scope verb: no scope signal at all -> NOT trivial. A prose
    # task (the natural heavy-skill invocation) lands here and earns no nudge.
    return {"level": "standard", "reason": "no concrete scope signal",
            "heavy_skill": heavy}


if __name__ == "__main__":  # tiny manual probe
    import json
    import sys
    print(json.dumps(classify(" ".join(sys.argv[1:])), ensure_ascii=False))
