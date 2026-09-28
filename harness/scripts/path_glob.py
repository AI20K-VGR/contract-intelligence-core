#!/usr/bin/env python3
"""path_glob.py — the canonical path-glob matcher shared by the harness gates.

Before this, the component-policy gate (artifact_check._matching_components) and
the deny matcher each rolled their own fnmatch
loop with subtly different rules, so the SAME pattern could match in one gate and
not the other. This is the single place that decides "does this path match this
glob", so a pattern author predicts one behavior everywhere.

Semantics — fnmatch (`*` spans `/`), case-sensitive, with two conveniences:
  - a leading `**/` is ALSO tried stripped, so `**/auth/**` matches a top-level
    `auth/x` as well as a nested `src/auth/x` (fnmatch gives `**` no special
    meaning, so without this `**/auth/**` would miss the top-level case);
  - the pattern is ALSO tried against the path's basename, so a file glob like
    `*.tf` or `config.yaml` matches at any depth.
Both conveniences are no-ops for a multi-segment directory glob (e.g.
`harness/**`), so existing lane/component patterns keep their behavior.
"""

import fnmatch
import os


def match_path_glob(target: str, patterns) -> bool:
    """True when POSIX path `target` matches ANY glob in `patterns`. Non-string
    or empty patterns are skipped (never raise)."""
    if not isinstance(target, str):
        return False
    name = os.path.basename(target)
    for pat in patterns or []:
        if not isinstance(pat, str) or not pat:
            continue
        alts = (pat, pat[3:]) if pat.startswith("**/") else (pat,)
        for a in alts:
            if fnmatch.fnmatch(target, a) or fnmatch.fnmatch(name, a):
                return True
    return False


def match_any_path(targets, pattern: str) -> bool:
    """True when ANY path in `targets` matches the single `pattern` (the inverse
    fan: one glob against many changed paths, what the component gate needs)."""
    return any(match_path_glob(t, [pattern]) for t in (targets or []))
